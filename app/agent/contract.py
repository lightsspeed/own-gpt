"""
V4.12 - Agent API Contract

The stable boundary between clients (frontend / integrations) and the
internal V4 agent layers. Nothing from PipelineContext, the executor, the
planner, or the loop leaks into the API contract.

    Client
      ↓
  Agent API Contract   ← this module (AgentRequest / AgentResponse /
  ↓                       StreamEvent / AgentError)
  RAGPipeline
      ↓
  V4 internal layers

Design invariants:
  - Pure DTO layer: frozen dataclasses + deterministic builders. No
    FastAPI, no I/O, no DB, no LLM calls — fully hermetic-testable.
  - The contract reads pipeline outputs ONLY through duck-typed getattr
    access on the returned context; it never imports internal pipeline
    modules, so the mapping is by contract, not by implementation.
  - Statuses are sticky and stable:
        completed | partial | failed | blocked | cancelled | timed_out
    Cancellation wins over everything; timed-out is its own status;
    otherwise the execution outcome is surfaced as-is.
  - Errors follow a stable error contract: code + safe message +
    request_id. Internal exception text NEVER reaches clients.
  - SSE events have a fixed vocabulary with explicit payload projection:
        started | stage | step | tool | terminated | completed | error
    No free-form metadata passthrough — payload keys are enumerated.
  - Backwards compatibility: AgentResponse.to_dict() carries the legacy
    chat payload keys (session_id, response, resources, answer_mode,
    record_id) so existing clients keep working unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Stable vocabulary ────────────────────────────────────────────────────────

VALID_API_STATUSES = frozenset({
    "completed", "partial", "failed", "blocked", "cancelled", "timed_out",
})

# Stable error codes (transport/request-level failures; execution outcomes
# are represented as statuses, NOT as errors).
ERROR_INVALID_REQUEST = "invalid_request"
ERROR_INTERNAL = "internal_error"

# Stable SSE event names (the full vocabulary).
VALID_STREAM_EVENTS = frozenset({
    "started", "stage", "step", "tool", "terminated", "completed", "error",
})

# Trace events projected onto "stage" events (stage name → public label).
_STAGE_EVENTS = {
    "intent_classified": "intent",
    "route_selected": "routing",
    "plan_created": "planning",
    "capability_selected": "capability_selection",
    "tool_selected": "tool_selection",
    "synthesis_completed": "synthesis",
    "validation_completed": "validation",
}

# Trace step events projected onto "step" events (default status per event).
_STEP_EVENTS = {
    "step_started": "running",
    "step_completed": "completed",
    "step_failed": "failed",
    "step_blocked": "blocked",
    "step_cancelled": "blocked",
}

# Trace tool events projected onto "tool" events (default status per event).
_TOOL_EVENTS = {
    "tool_completed": "completed",
    "tool_failed": "failed",
    "tool_blocked": "blocked",
}

# Stable terminated reasons emitted at the end of a cancelled/timed-out run.
TERMINATED_CANCELLED = "cancelled"
TERMINATED_TIMED_OUT = "timed_out"


# ── AgentRequest ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentRequest:
    """Structured client request. Validated before any pipeline work."""
    question: str
    session_id: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    filename: Optional[str] = None
    retriever_mode: Optional[str] = None

    MAX_QUESTION_CHARS = 50_000

    def validate(self) -> list[str]:
        """Return a list of issues (empty = valid). Deterministic."""
        issues: list[str] = []
        if not isinstance(self.question, str) or not self.question.strip():
            issues.append("question is required")
        elif len(self.question) > self.MAX_QUESTION_CHARS:
            issues.append(f"question exceeds {self.MAX_QUESTION_CHARS} characters")
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            issues.append("session_id is required")
        return issues

    def to_dict(self) -> dict:
        return {
            "question": self.question[:200],
            "session_id": self.session_id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "filename": self.filename,
            "retriever_mode": self.retriever_mode,
        }


# ── AgentError (stable error contract) ───────────────────────────────────────

@dataclass(frozen=True)
class AgentError:
    """Stable, client-safe error. Never carries internal exception text."""
    code: str
    message: str
    request_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
        }


def to_agent_error(exc: Exception, request_id: Optional[str] = None) -> AgentError:
    """Map any internal exception to the stable error contract.

    The exception text is logged and never returned: clients receive a
    fixed safe message plus the correlation request_id.
    """
    logger.error(
        "agent_api_internal_error error_type=%s request_id=%s",
        type(exc).__name__, request_id,
    )
    return AgentError(
        code=ERROR_INTERNAL,
        message="Agent processing failed.",
        request_id=request_id,
    )


# ── ExecutionSummary ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExecutionSummary:
    """Public view of the execution outcome (no executor internals)."""
    status: str
    completed: bool
    iterations: int
    stopped_reason: str
    steps_total: int
    steps_completed: int
    steps_failed: int
    steps_blocked: int
    has_timeout: bool
    cancelled: bool

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "completed": self.completed,
            "iterations": self.iterations,
            "stopped_reason": self.stopped_reason,
            "steps_total": self.steps_total,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "steps_blocked": self.steps_blocked,
            "has_timeout": self.has_timeout,
            "cancelled": self.cancelled,
        }


def map_status(ctx: object) -> str:
    """Stable API status from a pipeline context.

    Cancellation and timeout (V4.11 flags) win over execution outcomes;
    an absent execution (empty plan) is completed.
    """
    state = getattr(ctx, "agent_state", None) if ctx is not None else None
    if state is not None:
        if getattr(state, "cancelled", False) is True:
            return "cancelled"
        if getattr(state, "request_timed_out", False) is True:
            return "timed_out"
    execution = getattr(ctx, "execution", None) if ctx is not None else None
    status = getattr(execution, "status", "") if execution is not None else ""
    if status in VALID_API_STATUSES:
        return status
    # Missing/unknown execution status → nothing executed (vacuous success).
    return "completed"


def build_execution_summary(ctx: object) -> ExecutionSummary:
    """Deterministic public summary derived ONLY from the context."""
    execution = getattr(ctx, "execution", None) if ctx is not None else None
    step_results = getattr(execution, "step_results", None)
    if not isinstance(step_results, (list, tuple)):
        step_results = []

    total = len(step_results)
    completed_n = sum(1 for r in step_results if getattr(r, "status", "") == "completed")
    failed_n = sum(1 for r in step_results if getattr(r, "status", "") == "failed")
    blocked_n = sum(1 for r in step_results if getattr(r, "status", "") == "blocked")

    loop = getattr(ctx, "execution_loop", None) if ctx is not None else None
    iterations = getattr(loop, "iterations", 0)
    stopped_reason = getattr(loop, "stopped_reason", "")
    loop_completed = getattr(loop, "completed", None)
    completed = (
        loop_completed if isinstance(loop_completed, bool)
        else (total > 0 and completed_n == total)
    )

    state = getattr(ctx, "agent_state", None) if ctx is not None else None
    cancelled = bool(getattr(state, "cancelled", False))
    request_timed_out = bool(getattr(state, "request_timed_out", False))
    has_timeout = request_timed_out or any(
        getattr(getattr(r, "tool_result", None), "status", "") == "timeout"
        or getattr(getattr(r, "tool_result", None), "error_code", "") == "TOOL_TIMEOUT"
        for r in step_results
    )

    return ExecutionSummary(
        status=map_status(ctx),
        completed=completed,
        iterations=iterations,
        stopped_reason=stopped_reason,
        steps_total=total,
        steps_completed=completed_n,
        steps_failed=failed_n,
        steps_blocked=blocked_n,
        has_timeout=has_timeout,
        cancelled=cancelled,
    )


# ── Usage/Cost ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelUsageSummary:
    """Per-model token + estimated cost (public, never a billing system)."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


def build_usage_summary(ctx: object) -> tuple[tuple[ModelUsageSummary, ...], float]:
    """Token/cost summary from the context's token budget (duck-typed)."""
    budget = getattr(ctx, "token_budget", None) if ctx is not None else None
    usage = getattr(budget, "usage_by_model", None)
    if not callable(usage):
        return (), 0.0
    try:
        by_model = usage()
        summaries = tuple(
            ModelUsageSummary(
                model=str(model),
                input_tokens=int(v.get("input_tokens", 0) or 0),
                output_tokens=int(v.get("output_tokens", 0) or 0),
                cost_usd=float(v.get("cost_usd", 0.0) or 0.0),
            )
            for model, v in sorted((by_model or {}).items())
        )
        total = float(getattr(budget, "total_cost_usd", lambda: 0.0)() or 0.0)
        return summaries, round(total, 6)
    except Exception as exc:
        logger.warning("agent_api_usage_summary_failed error=%s", exc)
        return (), 0.0


# ── Sources / citations ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class CitationSource:
    """One public citation: provenance fields only, never chunk content."""
    source: str
    page: Optional[int] = None
    score: Optional[float] = None
    chunk_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "page": self.page,
            "score": None if self.score is None else round(self.score, 6),
            "chunk_id": self.chunk_id,
        }


def build_sources(ctx: object) -> tuple[CitationSource, ...]:
    """Structured citations from the ranked chunks (defensive duck-typing)."""
    ranked = getattr(ctx, "ranked_chunks", None) if ctx is not None else None
    if not isinstance(ranked, (list, tuple)):
        return ()

    sources: list[CitationSource] = []
    for item in ranked:
        base = getattr(item, "chunk", None)
        source = getattr(item, "source", None) or (
            getattr(base, "source", None) if base is not None else None
        )
        if not isinstance(source, str) or not source:
            continue
        page = getattr(base, "page", None)
        chunk_id = getattr(base, "chunk_id", None) or ""
        score = getattr(item, "reranker_score", None)
        if score is None and base is not None:
            score = getattr(base, "score", None)
        sources.append(CitationSource(
            source=source,
            page=page,
            score=float(score) if score is not None else None,
            chunk_id=chunk_id or None,
        ))
    return tuple(sources)


# ── Validation ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationSummary:
    """Public validation verdict (never internal validator details)."""
    valid: bool
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "issues": list(self.issues[:5]),
        }


def build_validation_summary(ctx: object) -> Optional[ValidationSummary]:
    validation = getattr(ctx, "validation", None) if ctx is not None else None
    if validation is None:
        return None
    valid = bool(getattr(validation, "valid", False))
    issues = getattr(validation, "issues", None) or ()
    issues = tuple(str(i) for i in issues if isinstance(i, str))
    return ValidationSummary(valid=valid, issues=issues)


# ── AgentResponse ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentResponse:
    """Stable, complete response contract. No internal types leak."""
    request_id: str
    execution_id: str
    session_id: str
    status: str
    answer: str = ""
    answer_mode: str = "grounded"
    intent: str = ""
    route: str = ""
    execution: Optional[ExecutionSummary] = None
    validation: Optional[ValidationSummary] = None
    sources: tuple[CitationSource, ...] = ()
    usage: tuple[ModelUsageSummary, ...] = ()
    estimated_cost_usd: float = 0.0
    errors: tuple[AgentError, ...] = ()
    record_id: str = ""
    legacy_resources: tuple[dict, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in VALID_API_STATUSES:
            raise ValueError(f"invalid agent status {self.status!r}")

    def to_dict(self) -> dict:
        """Serialization-safe view.

        `response`/`resources` are the LEGACY chat payload keys (existing
        clients keep working); `answer`/`sources` are the stable contract
        names.
        """
        if self.legacy_resources:
            resources = [dict(r) for r in self.legacy_resources]
        else:
            resources = [
                {"type": "source", "title": s.source, "url": None, "snippet": None}
                for s in self.sources
            ]
        return {
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "status": self.status,
            "response": self.answer,
            "answer": self.answer,
            "answer_mode": self.answer_mode,
            "intent": self.intent,
            "route": self.route,
            "execution": self.execution.to_dict() if self.execution else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "sources": [s.to_dict() for s in self.sources],
            "resources": resources,
            "usage": [u.to_dict() for u in self.usage],
            "estimated_cost_usd": self.estimated_cost_usd,
            "errors": [e.to_dict() for e in self.errors],
            "record_id": self.record_id,
        }


def build_response(
    request: AgentRequest,
    ctx: object,
    answer: Optional[str] = None,
    legacy_resources: Optional[list] = None,
    record_id: str = "",
    errors: tuple[AgentError, ...] = (),
) -> AgentResponse:
    """Deterministic context → AgentResponse mapping (the ONLY bridge)."""
    if not isinstance(request, AgentRequest):
        raise TypeError("request must be an AgentRequest")

    state = getattr(ctx, "agent_state", None) if ctx is not None else None
    request_id = getattr(state, "request_id", "") or ""
    execution_id = getattr(ctx, "execution_id", "") or request_id

    if answer is None:
        synthesis = getattr(ctx, "synthesis", None) if ctx is not None else None
        answer = getattr(synthesis, "answer", "") if synthesis is not None else ""

    intent = ""
    intent_label = getattr(ctx, "intent_label", None)
    if isinstance(intent_label, str):
        intent = intent_label
    else:
        intent_obj = getattr(ctx, "intent", None) if ctx is not None else None
        intent = getattr(intent_obj, "value", "") or getattr(intent_obj, "intent", "") or ""
    route = ""
    route_value = getattr(ctx, "route", None) if ctx is not None else None
    if route_value is not None:
        route = getattr(route_value, "value", "") or getattr(route_value, "decision", "")
        if not isinstance(route, str):
            route = str(route)

    usage, total_cost = build_usage_summary(ctx)
    resources = tuple(
        dict(r) for r in (legacy_resources or []) if isinstance(r, dict)
    )

    return AgentResponse(
        request_id=request_id,
        execution_id=execution_id,
        session_id=request.session_id,
        status=map_status(ctx),
        answer=str(answer) if answer is not None else "",
        answer_mode=getattr(ctx, "answer_mode", "grounded") or "grounded",
        intent=intent,
        route=str(route),
        execution=build_execution_summary(ctx),
        validation=build_validation_summary(ctx),
        sources=build_sources(ctx),
        usage=usage,
        estimated_cost_usd=total_cost,
        errors=tuple(errors),
        record_id=record_id,
        legacy_resources=resources,
    )


# ── SSE stream events (stable schema) ────────────────────────────────────────

@dataclass(frozen=True)
class StreamEvent:
    """One stable lifecycle event for SSE streaming."""
    event: str
    sequence: int
    payload: dict

    def __post_init__(self) -> None:
        if self.event not in VALID_STREAM_EVENTS:
            raise ValueError(f"invalid stream event {self.event!r}")

    def to_dict(self) -> dict:
        return {"event": self.event, "sequence": self.sequence, "payload": dict(self.payload)}


def build_stream_events(
    request: AgentRequest,
    ctx: object,
    response: AgentResponse,
) -> list[StreamEvent]:
    """Deterministic SSE event sequence from context + response.

    Payload keys are ENUMERATED per event type — trace metadata is never
    passed through as-is.
    """
    events: list[StreamEvent] = []
    seq = 0

    def emit(event: str, payload: dict) -> None:
        nonlocal seq
        events.append(StreamEvent(event=event, sequence=seq, payload=payload))
        seq += 1

    emit("started", {
        "request_id": response.request_id,
        "execution_id": response.execution_id,
        "session_id": response.session_id,
    })

    trace = getattr(ctx, "agent_trace", None) if ctx is not None else None
    trace_events = getattr(trace, "events", None)
    terminated: Optional[str] = None

    if callable(trace_events):
        for e in trace_events():
            name = getattr(e, "event", "")
            status = getattr(e, "status", "") or ""
            if name in _STAGE_EVENTS:
                emit("stage", {
                    "stage": _STAGE_EVENTS[name],
                    "status": status or "completed",
                })
            elif name in _STEP_EVENTS:
                emit("step", {
                    "step_id": getattr(e, "step_id", None),
                    "status": status or _STEP_EVENTS[name],
                    "tool": getattr(e, "tool", "") or "",
                    "duration_ms": getattr(e, "duration_ms", 0.0) or 0.0,
                })
            elif name in _TOOL_EVENTS:
                emit("tool", {
                    "tool": getattr(e, "tool", "") or "",
                    "status": status or _TOOL_EVENTS[name],
                    "duration_ms": getattr(e, "duration_ms", 0.0) or 0.0,
                })
            elif name == "request_cancelled":
                terminated = TERMINATED_CANCELLED
            elif name == "request_timeout":
                terminated = TERMINATED_TIMED_OUT

    if terminated is not None:
        emit("terminated", {"reason": terminated})
    elif response.status == "cancelled":
        emit("terminated", {"reason": TERMINATED_CANCELLED})
    elif response.status == "timed_out":
        emit("terminated", {"reason": TERMINATED_TIMED_OUT})
    else:
        emit("completed", {
            "status": response.status,
            "answer_mode": response.answer_mode,
            "iterations": (
                response.execution.iterations if response.execution else 0
            ),
            "stopped_reason": (
                response.execution.stopped_reason if response.execution else ""
            ),
            "estimated_cost_usd": response.estimated_cost_usd,
        })

    return events


# ── Facade (the only entry a client never touches internals through) ─────────

class AgentApi:
    """Thin facade over the pipeline: request → validated context → response.

    The pipeline is injected (duck-typed): tests provide fakes; production
    provides a RAGPipeline. The facade never exposes PipelineContext,
    executor, planner, or loop types to callers.
    """

    def __init__(self, pipeline) -> None:
        self._pipeline = pipeline

    def process(
        self,
        request: AgentRequest,
        answer: Optional[str] = None,
        legacy_resources: Optional[list] = None,
        record_id: str = "",
    ) -> AgentResponse:
        """Full request flow: validate → run pipeline → stable response."""
        issues = request.validate()
        if issues:
            return AgentResponse(
                request_id="",
                execution_id="",
                session_id=request.session_id,
                status="failed",
                errors=(
                    AgentError(
                        code=ERROR_INVALID_REQUEST,
                        message="; ".join(issues),
                    ),
                ),
            )
        try:
            ctx = self._pipeline.process(
                question=request.question,
                session_id=request.session_id,
                retriever_mode=request.retriever_mode,
                filename=request.filename,
                project_id=request.project_id,
                user_id=request.user_id,
            )
        except Exception as exc:
            return AgentResponse(
                request_id="",
                execution_id="",
                session_id=request.session_id,
                status="failed",
                answer="",
                errors=(to_agent_error(exc),),
            )
        return build_response(
            request, ctx, answer=answer,
            legacy_resources=legacy_resources, record_id=record_id,
        )

    def stream_events(
        self,
        request: AgentRequest,
        ctx: object,
        response: AgentResponse,
    ) -> list[StreamEvent]:
        """Stable SSE lifecycle events for one processed request."""
        return build_stream_events(request, ctx, response)