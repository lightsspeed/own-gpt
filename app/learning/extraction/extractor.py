"""Memory extraction — three deterministic gates into the V2.1 store.

Pipeline (V2.2 spec §9):
    Gate 1  deterministic eligibility (no LLM): eval-* sessions, explicit
            memory commands, non-substantive chat, and per-session throttle.
    Gate 2  LLM extraction (gpt-4o-mini, temp 0): structured JSON candidates,
            retried ONCE per batch.
    Gate 3  deterministic validation (no LLM): batch-atomic — malformed JSON,
            statement > MAX_STATEMENT_CHARS, unknown domain, candidate count
            > MAX_CANDIDATES, or secret-pattern content drops the WHOLE batch.

Writes: via MemoryService.create_memory with source=extracted — status
pending, authority extracted (rank 1), confidence DEFAULT_CONFIDENCE
(0.65). Nothing is ever auto-approved; humans promote via the V2.1 lifecycle.

Execution model (spec §10): run_extraction is invoked detached, after the
response is complete ([DONE] in streaming / after persist in sync), on a
daemon thread with its own SyncSessionLocal. It never blocks the request
path and never raises into it.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Optional

from app.core.config import settings
from app.models.memory import (
    DOMAINS,
    SOURCE_EXTRACTED,
)

logger = logging.getLogger(__name__)

# Extraction LLM: the provider default when running on Ollama, the classic
# OpenAI extraction model otherwise. Structured-JSON reliability differs by
# provider — Gate 3 validation is provider-agnostic and batch-atomic.
EXTRACTION_MODEL = settings.LLM_MODEL if settings.LLM_PROVIDER == "ollama" else "gpt-4o-mini"
MAX_CANDIDATES = 3
MAX_STATEMENT_CHARS = 500
# Throttle: at most one extraction per N user turns, per session.
EXTRACTION_TURN_INTERVAL = 3

# Explicit memory commands handled by the agent tools — those turns are
# already persisted by the explicit path (active, explicit_user).
_COMMAND_PATTERNS = (
    r"\b(remember|memorize|store|save|don[\'']t forget)\b.{0,40}\b(this|that|my|me|it)\b",
    r"\bmy name is\b",
    r"\bcall me\b",
    r"\bforget\b.{0,20}\b(this|that|everything)\b",
    r"\bwhat do you (know|remember) about me\b",
    r"\bwhat('| i)?s my\b",
    r"\b(do you|did you|have you) (remember|forgot(ten)?|noticed|known)\b",
    r"\bwhat (did|have) i (tell|say|told|shared|mentioned|said)( you)?\b",
)

# Operational throttle bookkeeping: session_id -> last extracted user-message
# sequence. In-process only (resets on restart) — NOT a system of record.
_throttle: dict[str, int] = {}
_throttle_lock = threading.Lock()


def _command_or_recall_turn(text: str) -> bool:
    """Gate 1: explicit memory commands / recall questions are handled by the
    tool path or answered from live memory — skip extraction."""
    return any(re.search(p, text.lower()) for p in _COMMAND_PATTERNS)


def _substantive(text: str) -> bool:
    """Gate 1: a turn worth extracting from — real content, not filler."""
    stripped = text.strip()
    if len(stripped) < 3:
        return False
    # Pure punctuation / emoji-only turns carry no durable facts.
    if re.fullmatch(r"[\W\s]+", stripped):
        return False
    return True


def _is_eligible(session_id: str, last_user: str, last_assistant: str) -> bool:
    """Gate 1 — deterministic, no LLM."""
    if session_id.startswith("eval-"):
        return False
    if not _substantive(last_user) or not last_assistant.strip():
        return False
    if _command_or_recall_turn(last_user):
        return False
    # Non-substantive chat (greetings, thanks, yes/no) carries no durable facts.
    from app.agent.pipeline.intent import IntentClassifier  # deferred import

    rule = IntentClassifier().rule_classify(last_user)
    if rule is not None and rule.intent.value == "general":
        return False
    return True


def _throttle_allowed(session_id: str, sequence: int) -> bool:
    """Gate 1 throttle: extract at most once per EXTRACTION_TURN_INTERVAL
    user turns per session. Operational, in-memory."""
    with _throttle_lock:
        last = _throttle.get(session_id)
        if last is not None and (sequence - last) < EXTRACTION_TURN_INTERVAL:
            return False
        _throttle[session_id] = sequence
        return True


def _extract_with_llm(exchange: str) -> list[dict]:
    """Gate 2 — LLM extraction with ONE retry per batch.

    Returns the raw candidate list on success, [] when the LLM returns
    malformed JSON twice (batch dropped).
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core.llm_provider import build_llm

    model = build_llm(model=EXTRACTION_MODEL, temperature=0.0)
    system = (
        "You are a memory extraction service. From the conversation turn below, "
        "extract at most %d durable facts about the user or their projects "
        "(preferences, background, goals, decisions, stable attributes). "
        "Ignore transient statements, one-off requests, and anything temporal. "
        "Domains must be one of: %s. "
        "Output ONLY valid JSON with no markdown:\n"
        '{"candidates": [{"statement": "<fact, max %d chars>", '
        '"domain": "<domain>", "importance": <0.0-1.0>}]}'
        % (MAX_CANDIDATES, ", ".join(DOMAINS), MAX_STATEMENT_CHARS)
    )
    payload = [
        SystemMessage(content=system),
        HumanMessage(content=exchange),
    ]
    for attempt in range(2):
        try:
            import json

            reply = model.invoke(payload)
            content = reply.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            data = json.loads(content.strip())
            candidates = data.get("candidates", [])
            if not isinstance(candidates, list):
                return []
            return candidates
        except Exception as exc:
            logger.warning(
                "extraction_llm_failed attempt=%d session_batch_dropped error=%s",
                attempt + 1, exc,
            )
    return []


def _validate_candidates(candidates: list) -> list[dict]:
    """Gate 3 — deterministic validation. Batch-atomic: any violation drops
    the whole batch (returns [])."""
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        return []
    if not candidates:
        return []

    from app.agent.guardrail import SECRET_PATTERNS  # deterministic, stdlib-only

    validated: list[dict] = []
    for c in candidates:
        if not isinstance(c, dict):
            return []
        statement = str(c.get("statement", "")).strip()
        domain = str(c.get("domain", ""))
        if not statement or len(statement) > MAX_STATEMENT_CHARS:
            return []
        if domain not in DOMAINS:
            return []
        try:
            importance = float(c.get("importance", 0.5))
        except (TypeError, ValueError):
            return []
        if not 0.0 <= importance <= 1.0:
            return []
        lower = statement.lower()
        if any(re.search(p, lower) for p in SECRET_PATTERNS):
            logger.warning("extraction_gate3_secret_dropped batch_dropped=True")
            return []
        validated.append(
            {"statement": statement, "domain": domain, "importance": importance}
        )
    return validated


def run_extraction(
    session_id: str,
    user_id: str,
    project_id: Optional[str] = None,
) -> int:
    """Full extraction run for one completed turn. Returns the number of
    memory entities written (0 when gates reject or anything fails).

    Detached by design: must be called off the request path. Never raises —
    failures are logged, never surfaced to the caller.
    """
    if not settings.MEMORY_V2_GRAPH:
        return 0
    try:
        from app.core.database import SyncSessionLocal
        from app.services import chat_persistence as store
        from app.services import memory as mem
        from app.services.embeddings import build_embedding_provider

        with SyncSessionLocal() as db:
            conv = store.get_conversation(db, session_id, user_id)
            if conv is None:
                return 0
            messages = store.list_messages(db, conv.id)

            last_user: str = ""
            last_assistant: str = ""
            last_user_sequence: int = 0
            for m in messages:
                content = (m.content or "").strip()
                if m.role == "user" and content and m.status != "failed":
                    last_user = content
                    last_user_sequence = m.sequence or 0
                elif m.role == "assistant" and content and m.status != "failed":
                    last_assistant = content

            if not _is_eligible(session_id, last_user, last_assistant):
                return 0
            if not _throttle_allowed(session_id, last_user_sequence):
                return 0

            exchange = f"User: {last_user}\n\nAssistant: {last_assistant}"
            candidates = _extract_with_llm(exchange)
            validated = _validate_candidates(candidates)
            if not validated:
                return 0

            provider = build_embedding_provider()
            written = 0
            for c in validated:
                entity = mem.create_memory(
                    db,
                    user_id=user_id,
                    statement=c["statement"],
                    domain=c["domain"],
                    source=SOURCE_EXTRACTED,
                    importance=c["importance"],
                    project_id=project_id,
                    source_conversation_id=session_id,
                    embed=provider.embed if provider else None,
                )
                written += 1
            logger.info(
                "memory_extraction_done session=%s user=%s written=%d",
                session_id, user_id, written,
            )
            return written
    except Exception as exc:
        logger.error(
            "memory_extraction_failed session=%s user=%s error=%s",
            session_id, user_id, exc, exc_info=True,
        )
        return 0


def schedule_extraction(
    session_id: str,
    user_id: str,
    project_id: Optional[str] = None,
) -> None:
    """Fire-and-forget detached execution after the response completes.

    Own daemon thread, own SyncSessionLocal — never touches the request path.
    Mirrors the learning_collector fire-and-forget precedent.
    """

    def _work() -> None:
        run_extraction(session_id, user_id, project_id)

    threading.Thread(
        target=_work, name=f"memory-extraction-{session_id}", daemon=True
    ).start()
