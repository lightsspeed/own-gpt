"""Memory extraction observability helpers (V2.2 P2.1).

Single home for:

- extraction_run_id — one stable uuid4 per extraction attempt, generated at
  schedule time and propagated through Redis coordination, the executor,
  run_extraction, memory creation, MemoryEvent metadata, and logs.
- log_event() — structured logging with the event-name + whitelisted
  extras contract (see app/core/logging_config.JsonFormatter).
- emit_*() — the small event/metric taxonomy: each terminal extraction
  exit path emits exactly one event and one metric increment.

Privacy rules (enforced here and by JsonFormatter):
- Never log conversation content, prompts, statements, tokens, or keys.
- session_id is emitted (operational necessity, existing convention);
  user identity is reduced to user_hash (sha256 prefix) — never raw
  user_id, never in metrics.
- All metrics go through app.core.metrics (bounded labels, fail-open).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Optional

from app.core import metrics as core_metrics
from app.core.logging_config import ALLOWED_EXTRA_FIELDS

logger = logging.getLogger("app.extraction")

# Fields permitted on structured log events. Mirrors the formatter whitelist;
# emitting anything else is a no-op (dropped silently).
SAFE_FIELDS: frozenset[str] = ALLOWED_EXTRA_FIELDS


def new_run_id() -> str:
    """One stable identifier per extraction attempt (uuid4 string)."""
    return str(uuid.uuid4())


def user_hash(user_id: str) -> str:
    """Short, non-reversible user identifier for logs. Never a metric label."""
    return hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:8]


def log_event(level: int, event: str, **fields) -> None:
    """Emit one structured log line: message=event, extras=whitelisted fields.

    Never raises (logging framework swallows handler errors; extras are
    whitelisted so no content can reach the payload).
    """
    extra: dict[str, object] = {"event": event}
    for key, value in fields.items():
        if key in SAFE_FIELDS and value is not None:
            extra[key] = value
    try:
        logger.log(level, event, extra=extra)
    except Exception:  # pragma: no cover - fail-open contract
        pass


# -- Event/metric emission helpers (one taxonomy) -----------------------------

def emit_scheduled(session_id: str, turn: object, run_id: str) -> None:
    core_metrics.safe_count("scheduled_total")
    log_event(logging.INFO, "memory_extraction_scheduled", session=session_id, turn=turn, run_id=run_id)


def emit_skip(
    session_id: str,
    turn: object,
    run_id: str,
    reason: str,
    gate: Optional[str] = None,
) -> None:
    core_metrics.safe_count("skipped_total", reason=reason)
    if gate is not None:
        core_metrics.safe_count("gate_rejections_total", gate=gate, reason=reason)
    fields = {"session": session_id, "turn": turn, "run_id": run_id, "reason": reason}
    if gate is not None:
        fields["gate"] = gate
    log_event(logging.INFO, "memory_extraction_skipped", **fields)


def emit_failed(
    session_id: str,
    turn: object,
    run_id: str,
    reason: str,
    error_class: str,
    error_message: str,
) -> None:
    core_metrics.safe_count("failed_total", reason=reason)
    log_event(
        logging.ERROR,
        "memory_extraction_failed",
        session=session_id,
        turn=turn,
        run_id=run_id,
        reason=reason,
        error_class=error_class,
        error_message=error_message,
    )


def emit_completed(
    session_id: str,
    turn: object,
    run_id: str,
    written: int,
    duration_ms: float,
) -> None:
    core_metrics.safe_count("completed_total")
    log_event(
        logging.INFO,
        "memory_extraction_completed",
        session=session_id,
        turn=turn,
        run_id=run_id,
        written=written,
        duration_ms=round(duration_ms, 1),
    )


def emit_llm_started(run_id: str, provider: str, model: str, attempt: int) -> None:
    core_metrics.safe_count("llm_calls_total", provider=provider, model=model)
    log_event(
        logging.INFO,
        "memory_extraction_llm_started",
        run_id=run_id,
        provider=provider,
        model=model,
        attempt=attempt,
    )


def emit_llm_completed(
    run_id: str,
    provider: str,
    model: str,
    attempt: int,
    duration_ms: float,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
) -> None:
    core_metrics.safe_observe("llm_duration_seconds", duration_ms / 1000.0, provider=provider, model=model)
    fields = {
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "attempt": attempt,
        "duration_ms": round(duration_ms, 1),
    }
    if tokens_in is not None:
        fields["tokens_in"] = tokens_in
    if tokens_out is not None:
        fields["tokens_out"] = tokens_out
    log_event(logging.INFO, "memory_extraction_llm_completed", **fields)


def emit_llm_failed(
    run_id: str,
    provider: str,
    model: str,
    attempt: int,
    error_class: str,
    error_message: str,
) -> None:
    core_metrics.safe_count("llm_errors_total", provider=provider, model=model)
    log_event(
        logging.WARNING,
        "memory_extraction_llm_failed",
        run_id=run_id,
        provider=provider,
        model=model,
        attempt=attempt,
        error_class=error_class,
        error_message=error_message,
    )


def emit_redis_unavailable(
    op: str, error_class: str, error_message: str, run_id: Optional[str] = None
) -> None:
    core_metrics.safe_count("redis_fallback_total", operation=op)
    fields = {"op": op, "error_class": error_class, "error_message": error_message}
    if run_id is not None:
        fields["run_id"] = run_id
    log_event(logging.WARNING, "memory_extraction_redis_unavailable", **fields)
