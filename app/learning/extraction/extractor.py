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

Observability (V2.2 P2.1): every terminal exit path emits exactly one
structured event + one metric increment (see app/learning/extraction/
observability.py). extraction_run_id correlates schedule → Redis claim →
executor → run → MemoryEvent metadata → logs. All instrumentation is
fail-open — observability can never break chat or extraction.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

from app.core.config import settings
from app.core.logging_config import classify_exception, sanitize_exception_message
from app.core import metrics as core_metrics
from app.models.memory import (
    DOMAINS,
    SOURCE_EXTRACTED,
)
from app.learning.extraction import observability
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


def _token_usage(reply) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Best-effort token usage from the provider response.

    OpenAI exposes response_metadata.token_usage (prompt/completion/total).
    Ollama (ChatOllama) exposes usage-adjacent fields only when the model
    reports them — never assumed. Returns (input, output, total), each None
    when absent. Never an extra LLM call.
    """
    meta = getattr(reply, "response_metadata", None) or {}
    usage = meta.get("token_usage") or meta.get("usage") or {}
    if not isinstance(usage, dict):
        return None, None, None
    t_in = (
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("prompt_eval_count")
    )
    t_out = (
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("eval_count")
    )
    t_total = usage.get("total_tokens")
    return (t_in or None), (t_out or None), (t_total or None)


def _extract_with_llm(exchange: str, run_id: Optional[str] = None) -> Optional[list]:
    """Gate 2 — LLM extraction with ONE retry per batch.

    Returns the raw candidate list on success, [] when the LLM produced a
    valid but empty/no-candidate response, None when the LLM failed twice
    (malformed JSON twice or a provider error) — the batch is dropped.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core.llm_provider import build_llm

    provider = core_metrics.provider_label()
    model = core_metrics.model_label(EXTRACTION_MODEL)

    model_obj = build_llm(model=EXTRACTION_MODEL, temperature=0.0)
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
        observability.emit_llm_started(run_id, provider, model, attempt + 1)
        t0 = time.perf_counter()
        try:
            import json

            reply = model_obj.invoke(payload)
            duration_ms = (time.perf_counter() - t0) * 1000
            t_in, t_out, t_total = _token_usage(reply)
            if t_in is not None:
                core_metrics.safe_count("llm_tokens_total", t_in, provider=provider, model=model, kind="input")
            if t_out is not None:
                core_metrics.safe_count("llm_tokens_total", t_out, provider=provider, model=model, kind="output")
            if t_total is not None:
                core_metrics.safe_count("llm_tokens_total", t_total, provider=provider, model=model, kind="total")

            content = reply.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            data = json.loads(content.strip())
            candidates = data.get("candidates", [])
            if not isinstance(candidates, list):
                candidates = []
            observability.emit_llm_completed(
                run_id, provider, model, attempt + 1, duration_ms, tokens_in=t_in, tokens_out=t_out
            )
            return candidates
        except Exception as exc:
            observability.emit_llm_failed(
                run_id,
                provider,
                model,
                attempt + 1,
                error_class=type(exc).__name__,
                error_message=sanitize_exception_message(str(exc)),
            )
    return None


def _validate_candidates(candidates: list) -> tuple[list, Optional[str]]:
    """Gate 3 — deterministic validation. Batch-atomic: any violation drops
    the whole batch (returns ([], reason)).

    Returns (validated, None) on success; ([], reason) where reason is one
    of NO_CANDIDATES / INVALID_CANDIDATE / SECRET_DETECTED.

    Pure decision function: no events, no metrics, no logging. The caller
    emits the single terminal skip event/metric for the returned reason.
    """
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        return [], "INVALID_CANDIDATE"
    if not candidates:
        return [], "NO_CANDIDATES"

    from app.agent.guardrail import SECRET_PATTERNS  # deterministic, stdlib-only

    validated: list[dict] = []
    for c in candidates:
        if not isinstance(c, dict):
            return [], "INVALID_CANDIDATE"
        statement = str(c.get("statement", "")).strip()
        domain = str(c.get("domain", ""))
        if not statement or len(statement) > MAX_STATEMENT_CHARS:
            return [], "INVALID_CANDIDATE"
        if domain not in DOMAINS:
            return [], "INVALID_CANDIDATE"
        try:
            importance = float(c.get("importance", 0.5))
        except (TypeError, ValueError):
            return [], "INVALID_CANDIDATE"
        if not 0.0 <= importance <= 1.0:
            return [], "INVALID_CANDIDATE"
        lower = statement.lower()
        if any(re.search(p, lower) for p in SECRET_PATTERNS):
            return [], "SECRET_DETECTED"
        validated.append(
            {"statement": statement, "domain": domain, "importance": importance}
        )
    return validated, None


def run_extraction(
    session_id: str,
    user_id: str,
    project_id: Optional[str] = None,
    user_msg_id: Optional[object] = None,
    run_id: Optional[str] = None,
) -> int:
    """Full extraction run for ONE completed logical turn. Returns the number
    of memory entities written (0 when gates reject or anything fails).

    The turn is identified by the immutable chat_messages primary key of its
    user message (user_msg_id) — never "the last message". Detached by design:
    must be called off the request path. Never raises — failures are logged,
    never surfaced to the caller.

    Observability: extraction_run_id is generated here when the scheduler
    did not supply one; every terminal exit emits exactly one event + one
    metric increment.

    Outcome accounting distinguishes schedule-time from run-time outcomes:
    - Schedule-time (emitted by schedule_extraction, NEVER via this run):
      DISABLED, CLAIM_CONFLICT, QUEUE_FULL — count into skipped_total only.
    - Run-time (started_total incremented at run entry):
      started = completed + failed + run skips (CONVERSATION_MISSING,
      NO_TURN, INELIGIBLE, THROTTLED, NO_CANDIDATES, INVALID_CANDIDATE,
      SECRET_DETECTED).
    The `inflight` gauge is owned exclusively by the executor (one
    increment per running extraction task); this run never touches it.
    """
    if run_id is None:
        run_id = observability.new_run_id()
    if not settings.MEMORY_V2_GRAPH:
        observability.emit_skip(session_id, user_msg_id, run_id, "DISABLED")
        return 0

    t0 = time.perf_counter()
    core_metrics.safe_count("started_total")
    try:
        from app.core.database import SyncSessionLocal
        from app.services import chat_persistence as store
        from app.services import memory as mem
        from app.services.embeddings import build_embedding_provider

        with SyncSessionLocal() as db:
            conv = store.get_conversation(db, session_id, user_id)
            if conv is None:
                observability.emit_skip(session_id, user_msg_id, run_id, "CONVERSATION_MISSING")
                return 0
            messages = store.list_messages(db, conv.id)

            turn = _turn_pair(messages, user_msg_id)
            if turn is None:
                observability.emit_skip(session_id, user_msg_id, run_id, "NO_TURN")
                return 0

            user_msg, assistant = turn
            last_user = (user_msg.content or "").strip()
            last_assistant = (assistant.content or "").strip()
            last_user_sequence = user_msg.sequence or 0

            if not _is_eligible(session_id, last_user, last_assistant):
                observability.emit_skip(session_id, user_msg_id, run_id, "INELIGIBLE", gate="1")
                return 0
            if not coordinator.throttle_allowed(session_id, last_user_sequence):
                observability.emit_skip(session_id, user_msg_id, run_id, "THROTTLED", gate="1b")
                return 0

            observability.log_event(
                logging.INFO,
                "memory_extraction_started",
                session=session_id,
                turn=user_msg_id,
                run_id=run_id,
            )
            exchange = f"User: {last_user}\n\nAssistant: {last_assistant}"
            candidates = _extract_with_llm(exchange, run_id=run_id)
            if candidates is None:
                observability.emit_failed(
                    session_id, user_msg_id, run_id,
                    reason="LLM_ERROR",
                    error_class="LLMError",
                    error_message="extraction LLM produced invalid output after retries",
                )
                return 0
            if not candidates:
                observability.emit_skip(session_id, user_msg_id, run_id, "NO_CANDIDATES", gate="3")
                return 0

            validated, gate3_reason = _validate_candidates(candidates)
            if not validated:
                observability.emit_skip(
                    session_id, user_msg_id, run_id, gate3_reason or "INVALID_CANDIDATE", gate="3"
                )
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
                    extraction_run_id=run_id,
                )
                written += 1
            observability.log_event(
                logging.INFO,
                "memory_extraction_persisted",
                session=session_id,
                turn=user_msg_id,
                run_id=run_id,
                written=written,
            )
            duration_ms = (time.perf_counter() - t0) * 1000
            observability.emit_completed(session_id, user_msg_id, run_id, written, duration_ms)
            return written
    except Exception as exc:
        reason = classify_exception(exc)
        observability.emit_failed(
            session_id, user_msg_id, run_id,
            reason=reason,
            error_class=type(exc).__name__,
            error_message=sanitize_exception_message(str(exc)),
        )
        return 0
    finally:
        core_metrics.safe_observe("duration_seconds", time.perf_counter() - t0)


def _run_task(
    session_id: str,
    user_id: str,
    project_id: Optional[str],
    user_msg_id: object,
    run_id: str,
) -> None:
    """Executor task wrapper: run the extraction and release the turn claim
    when done (success or failure). Claim release on completion lets a later
    legitimate re-schedule proceed; the Redis TTL covers crashed workers."""
    try:
        run_extraction(session_id, user_id, project_id, user_msg_id, run_id=run_id)
    finally:
        coordinator.release_turn(session_id, user_msg_id, run_id=run_id)


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

    Observability: the extraction_run_id is born here (on the request path)
    and travels with the claim, the executor task, run_extraction, the
    memory write, MemoryEvent metadata, and every log line for this attempt.
    """
    if not settings.MEMORY_V2_GRAPH or user_msg_id is None:
        observability.emit_skip(session_id, user_msg_id, observability.new_run_id(), "DISABLED")
        return False
    run_id = observability.new_run_id()
    if not coordinator.claim_turn(session_id, user_msg_id, owner=f"pid-{os.getpid()}:{run_id}", run_id=run_id):
        observability.emit_skip(session_id, user_msg_id, run_id, "CLAIM_CONFLICT")
        return False
    if not extraction_executor.submit(_run_task, session_id, user_id, project_id, user_msg_id, run_id):
        coordinator.release_turn(session_id, user_msg_id)
        observability.emit_skip(session_id, user_msg_id, run_id, "QUEUE_FULL")
        return False
    observability.emit_scheduled(session_id, user_msg_id, run_id)
    return True
