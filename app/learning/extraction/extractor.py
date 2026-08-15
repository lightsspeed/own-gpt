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

Execution model (spec §10 + V2.2 P1 hardening): run_extraction is invoked
detached, after the response is complete ([DONE] in streaming / after persist
in sync), through a BOUNDED daemon worker pool (executor.py) coordinated
across workers by Redis (coordinator.py):

- single-flight claim per logical turn (session_id + immutable user message
  id) — at most one extraction per turn across all workers
- distributed, TTL-protected throttle per session
- every coordination failure fails open: extraction scheduling can never fail
  the chat request, and duplicates degrade to idempotent memory writes
- run_extraction operates ONLY on a completed persisted turn (the user message
  identified by id plus its first completed assistant reply) — it never reads
  partially-written assistant content
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from app.core.config import settings
from app.models.memory import (
    DOMAINS,
    SOURCE_EXTRACTED,
)
from app.learning.extraction.coordinator import coordinator
from app.learning.extraction.executor import extraction_executor

logger = logging.getLogger(__name__)

# Extraction LLM: the provider default when running on Ollama, the classic
# OpenAI extraction model otherwise. Structured-JSON reliability differs by
# provider — Gate 3 validation is provider-agnostic and batch-atomic.
EXTRACTION_MODEL = settings.LLM_MODEL if settings.LLM_PROVIDER == "ollama" else "gpt-4o-mini"
MAX_CANDIDATES = 3
MAX_STATEMENT_CHARS = 500

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


def _turn_pair(messages: list, user_msg_id: object) -> Optional[tuple]:
    """Resolve ONE logical turn from persisted messages: the user message
    identified by user_msg_id plus the FIRST completed assistant reply that
    follows it (by sequence). Returns None when the turn is absent or not
    complete — partially-written assistant content is never extracted."""
    if user_msg_id is None:
        return None
    user_msg = None
    for m in messages:
        if user_msg is None:
            if m.role == "user" and m.id == user_msg_id:
                user_msg = m
        elif m.role == "assistant" and m.status != "failed" and (m.content or "").strip():
            return user_msg, m
    return None


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
    user_msg_id: Optional[object] = None,
) -> int:
    """Full extraction run for ONE completed logical turn. Returns the number
    of memory entities written (0 when gates reject or anything fails).

    The turn is identified by the immutable chat_messages primary key of its
    user message (user_msg_id) — never "the last message". Detached by design:
    must be called off the request path. Never raises — failures are logged,
    never surfaced to the caller.
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

            turn = _turn_pair(messages, user_msg_id)
            if turn is None:
                logger.info(
                    "memory_extraction_skipped_incomplete session=%s turn=%s",
                    session_id, user_msg_id,
                )
                return 0

            user_msg, assistant = turn
            last_user = (user_msg.content or "").strip()
            last_assistant = (assistant.content or "").strip()
            last_user_sequence = user_msg.sequence or 0

            if not _is_eligible(session_id, last_user, last_assistant):
                logger.info(
                    "memory_extraction_skipped_eligibility session=%s turn=%s",
                    session_id, user_msg_id,
                )
                return 0
            if not coordinator.throttle_allowed(session_id, last_user_sequence):
                logger.info(
                    "memory_extraction_skipped_throttle session=%s turn=%s",
                    session_id, user_msg_id,
                )
                return 0

            logger.info(
                "memory_extraction_started session=%s turn=%s",
                session_id, user_msg_id,
            )
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
                "memory_extraction_done session=%s user=%s turn=%s written=%d",
                session_id, user_id, user_msg_id, written,
            )
            return written
    except Exception as exc:
        logger.error(
            "memory_extraction_failed session=%s user=%s error=%s",
            session_id, user_id, exc, exc_info=True,
        )
        return 0


def _run_task(
    session_id: str,
    user_id: str,
    project_id: Optional[str],
    user_msg_id: object,
) -> None:
    """Executor task wrapper: run the extraction and release the turn claim
    when done (success or failure). Claim release on completion lets a later
    legitimate re-schedule proceed; the Redis TTL covers crashed workers."""
    try:
        run_extraction(session_id, user_id, project_id, user_msg_id)
    finally:
        coordinator.release_turn(session_id, user_msg_id)


def schedule_extraction(
    session_id: str,
    user_id: str,
    project_id: Optional[str] = None,
    user_msg_id: Optional[object] = None,
) -> bool:
    """Schedule extraction for a completed turn, detached from the request
    path. Single-flight (at most one in-flight extraction per turn across all
    workers) then bounded enqueue on the daemon worker pool.

    NEVER raises and NEVER fails the caller: Redis failures, claim failures,
    a full queue or a stopped pool all degrade to a logged skip (fail-open).
    Returns True when the extraction was enqueued.
    """
    if not settings.MEMORY_V2_GRAPH or user_msg_id is None:
        return False
    if not coordinator.claim_turn(session_id, user_msg_id, owner=f"pid-{os.getpid()}"):
        logger.info(
            "memory_extraction_skipped_duplicate session=%s turn=%s",
            session_id, user_msg_id,
        )
        return False
    if not extraction_executor.submit(_run_task, session_id, user_id, project_id, user_msg_id):
        coordinator.release_turn(session_id, user_msg_id)
        logger.warning(
            "memory_extraction_skipped_concurrency session=%s turn=%s",
            session_id, user_msg_id,
        )
        return False
    logger.info(
        "memory_extraction_scheduled session=%s turn=%s",
        session_id, user_msg_id,
    )
    return True
