"""
V4.8 - Agent Execution Observability

Structured, event-based trace of the agent execution lifecycle.

Design invariants:
  - PASSIVE: tracing never changes execution behavior; record() and
    publish() never raise.
  - Reuses the existing observability infrastructure (the module-level
    logger, the existing PipelineTrace/TracingService in tracing.py).
    No new metrics DB, Prometheus, Grafana, or telemetry framework.
  - Safety: prompts, memory contents, secrets, authorization codes,
    API keys, raw tool outputs, and raw document/web results are NEVER
    recorded. Metadata is redacted and size-bounded.
  - Every event carries request_id / execution_id / session_id /
    project_id for correlation.
  - A clean TraceObserver interface allows the existing telemetry
    backend to consume the trace later.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional

logger = logging.getLogger(__name__)

# The nine lifecycle stages. record() rejects anything else (defensive).
VALID_STAGES = frozenset({
    "intent", "routing", "planning", "capability_selection",
    "tool_selection", "execution", "synthesis", "validation", "learning",
})

# The lifecycle events the platform records. Anything else is ignored.
VALID_EVENTS = frozenset({
    "request_started", "intent_classified", "route_selected", "plan_created",
    "capability_selected", "tool_selected", "step_started",
    "tool_completed", "tool_failed", "tool_blocked",
    "step_completed", "step_failed", "step_blocked",
    "synthesis_completed", "validation_completed", "request_completed",
    # V4.10: security decisions (same nine stages; recorded under "execution").
    "security_flag", "security_blocked",
    # V4.11: reliability decisions (same nine stages; recorded under
    # "execution"). request_cancelled / request_timeout fire once per run;
    # step_cancelled fires per cancelled step.
    "request_cancelled", "step_cancelled", "request_timeout",
})

# Tool events map from ToolResult.status.
_TOOL_EVENT_BY_STATUS = {
    "completed": "tool_completed",
    "blocked": "tool_blocked",
    "failed": "tool_failed",
    "timeout": "tool_failed",
    "empty": "tool_failed",
}

# Metadata keys whose values are NEVER recorded (memory, raw output,
# prompts, credentials, codes).
_SENSITIVE_KEY_TERMS = (
    "key", "secret", "token", "password", "authorization",
    "memory", "fact", "prompt", "output", "content", "question", "query",
)

# Exact keys that identify authorization/code material (always dropped).
_SENSITIVE_EXACT_KEYS = frozenset({
    "code", "auth_code", "access_code", "exchange_code", "confirmation_code",
})

# Value-level redaction for accidental credential leaks.
_SECRET_PATTERN = re.compile(
    r"\bsk-[A-Za-z0-9_-]{8,}\b"
    r"|\bcode['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9_-]{8,}"
    r"|\bapi[_-]?key[=: ]+[^\s,;]{8,}",
    re.IGNORECASE,
)

# Hard bound on serialized per-event metadata.
MAX_METADATA_CHARS = 2000

# Cap on scalar string fields inside an event.
MAX_FIELD_CHARS = 200


def _redact_text(value: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", str(value))


def _sanitize_metadata(metadata: Optional[dict]) -> dict:
    """Drop sensitive keys, redact values, and bound total size.

    Never raises: un-serializable or malformed metadata degrades to {}.
    """
    try:
        if not isinstance(metadata, dict):
            return {}
        clean: dict[str, Any] = {}
        for key, value in metadata.items():
            k = str(key)
            k_lower = k.lower()
            if any(term in k_lower for term in _SENSITIVE_KEY_TERMS):
                continue
            if k_lower in _SENSITIVE_EXACT_KEYS:
                continue
            if isinstance(value, str):
                clean[k] = _redact_text(value)[:MAX_FIELD_CHARS]
            elif isinstance(value, (int, float, bool)) or value is None:
                clean[k] = value
            else:
                # Non-scalar values are never recorded (no repr leaks).
                continue

        # Deterministic size bound: drop trailing keys (sorted) until the
        # serialized payload fits.
        while True:
            payload = json.dumps(clean, sort_keys=True)
            if len(payload) <= MAX_METADATA_CHARS or not clean:
                return clean
            drop_key = sorted(clean.keys())[-1]
            del clean[drop_key]
    except Exception as exc:
        logger.warning("agent_trace_metadata_sanitize_failed error=%s", exc)
        return {}


@dataclass
class TraceEvent:
    """One immutable record of a lifecycle decision or outcome."""
    request_id: str = ""
    execution_id: str = ""
    session_id: str = ""
    project_id: str = ""
    timestamp: float = 0.0
    stage: str = ""
    event: str = ""
    status: str = ""
    step_id: Optional[int] = None
    tool: str = ""
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


class AgentTrace:
    """Append-only, event-based trace of one agent execution run.

    record() is defensive: invalid stage/event or bad metadata can never
    raise or break the caller. events() and snapshot() return safe copies.
    """

    def __init__(
        self,
        request_id: str = "",
        execution_id: str = "",
        session_id: str = "",
        project_id: str = "",
    ) -> None:
        self.request_id = request_id
        self.execution_id = execution_id
        self.session_id = session_id
        self.project_id = project_id
        self.trace_id = f"atr-{request_id or execution_id or 'anon'}"
        self.created_at = time.time()
        self._events: list[TraceEvent] = []

    # ── Recording ────────────────────────────────────────────────────────

    def record(
        self,
        stage: str,
        event: str,
        status: str = "",
        step_id: Optional[int] = None,
        tool: str = "",
        duration_ms: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Append one sanitized event. Never raises."""
        try:
            if stage not in VALID_STAGES or event not in VALID_EVENTS:
                logger.warning(
                    "agent_trace_ignored stage=%r event=%r (invalid)",
                    stage, event,
                )
                return
            duration = 0.0 if duration_ms is None else round(float(duration_ms), 2)
            self._events.append(TraceEvent(
                request_id=self.request_id,
                execution_id=self.execution_id,
                session_id=self.session_id,
                project_id=self.project_id,
                timestamp=time.time(),
                stage=stage,
                event=event,
                status=_redact_text(str(status))[:MAX_FIELD_CHARS],
                step_id=step_id,
                tool=_redact_text(str(tool))[:MAX_FIELD_CHARS],
                duration_ms=duration,
                metadata=_sanitize_metadata(metadata),
            ))
        except Exception as exc:
            logger.warning("agent_trace_record_failed event=%s error=%s", event, exc)

    # ── Read access (safe copies only) ───────────────────────────────────

    def events(self) -> list[TraceEvent]:
        """Safe snapshot of recorded events (copy, never the internal list)."""
        return [replace(e) for e in self._events]

    def snapshot(self) -> "AgentTrace":
        """Deep-ish copy safe for persistence or publishing."""
        clone = AgentTrace(
            request_id=self.request_id,
            execution_id=self.execution_id,
            session_id=self.session_id,
            project_id=self.project_id,
        )
        clone.trace_id = self.trace_id
        clone.created_at = self.created_at
        clone._events = [replace(e, metadata=dict(e.metadata)) for e in self._events]
        return clone

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "events": [
                {
                    "stage": e.stage, "event": e.event, "status": e.status,
                    "step_id": e.step_id, "tool": e.tool,
                    "duration_ms": e.duration_ms, "metadata": dict(e.metadata),
                    "timestamp": e.timestamp,
                }
                for e in self._events
            ],
        }

    # ── Derived observability (metrics PREPARATION, no backend) ─────────

    def metrics(self) -> dict:
        """Derived counters/aggregates for the existing observability stack.

        Exposed only — this module implements NO metrics backend. The
        existing Prometheus/telemetry layer can consume these directly.
        """
        completed_status = None
        step_total = 0.0
        tool_total = 0.0
        tool_failures = 0
        tool_blocked = 0
        stages: dict[str, float] = {}
        for e in self._events:
            if e.event == "request_completed":
                completed_status = e.status
            if e.event == "step_completed":
                step_total += e.duration_ms
            if e.event == "tool_completed":
                tool_total += e.duration_ms
            if e.event == "tool_failed":
                tool_failures += 1
            if e.event == "tool_blocked":
                tool_blocked += 1
            stages[e.stage] = stages.get(e.stage, 0.0) + e.duration_ms
        return {
            "agent_requests_total": 1,
            "agent_requests_failed": 1 if completed_status == "failed" else 0,
            "agent_requests_partial": 1 if completed_status == "partial" else 0,
            "agent_step_duration": round(step_total, 2),
            "agent_tool_duration": round(tool_total, 2),
            "agent_tool_failures": tool_failures,
            "agent_tool_blocked": tool_blocked,
            "agent_stage_duration": {s: round(d, 2) for s, d in stages.items()},
        }

    # ── Observer dispatch (existing infra adapter) ───────────────────────

    def publish(self, observer: "TraceObserver") -> None:
        """Deliver a snapshot to the observer. Never raises."""
        try:
            observer.publish(self.snapshot())
        except Exception as exc:
            logger.warning("agent_trace_publish_failed error=%s", exc)

    @staticmethod
    def tool_event_for(status: str) -> str:
        """Map a ToolResult status onto the trace tool event name."""
        return _TOOL_EVENT_BY_STATUS.get(status, "tool_failed")


class TraceObserver:
    """Interface for consuming an AgentTrace.

    The existing logging layer implements this today; the platform's
    telemetry backend can replace it later without changing the trace.
    """

    def publish(self, trace: AgentTrace) -> None:
        raise NotImplementedError


class LoggingTraceObserver(TraceObserver):
    """Reuses the EXISTING logging infrastructure — no new telemetry.

    Emits one structured key=value log line per trace event through the
    module logger (the same logger the rest of the pipeline uses).
    """

    def __init__(self, log: Optional[logging.Logger] = None) -> None:
        self._log = log or logger

    def publish(self, trace: AgentTrace) -> None:
        for e in trace.events():
            self._log.info(
                "agent_trace request_id=%s execution_id=%s session_id=%s "
                "project_id=%s stage=%s event=%s status=%s step_id=%s tool=%s "
                "duration_ms=%s metadata=%s",
                e.request_id, e.execution_id, e.session_id, e.project_id,
                e.stage, e.event, e.status, e.step_id, e.tool, e.duration_ms,
                json.dumps(e.metadata, sort_keys=True),
            )


def record_trace(context, stage: str, event: str, **kwargs) -> None:
    """Passive recorder: emits on context.agent_trace, never raises.

    Used by every pipeline stage (executor, synthesizer, validator, ...).
    If tracing is absent or fails, execution proceeds untouched.
    """
    try:
        tr = getattr(context, "agent_trace", None)
        if tr is not None and hasattr(tr, "record"):
            tr.record(stage, event, **kwargs)
    except Exception:
        pass
