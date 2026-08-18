"""V4.12 Agent API Contract — hermetic tests.

Covers the 15 required cases:
   1.  request schema                9.  cancellation response
   2.  response schema              10.  citation/source serialization
   3.  execution status mapping     11.  cost/token serialization
   4.  successful response          12.  stable SSE events
   5.  partial execution response   13.  malformed request
   6.  failed response              14.  internal exception → stable error
   7.  blocked response             15.  backwards-compatible chat response
   8.  timeout response

Zero live pipeline / API / DB / LLM calls — the pipeline is a duck-typed
fake; the contract module is pure (no FastAPI, no pipeline imports).
"""

import json
from types import SimpleNamespace

from app.agent.contract import (
    AgentApi,
    AgentError,
    AgentRequest,
    AgentResponse,
    CitationSource,
    ExecutionSummary,
    StreamEvent,
    VALID_STREAM_EVENTS,
    build_execution_summary,
    build_response,
    build_sources,
    build_stream_events,
    build_usage_summary,
    map_status,
    to_agent_error,
)
from app.agent.pipeline.trace import AgentTrace
from app.agent.pipeline.cost import TokenBudget


# ── Context fakes (duck-typed surfaces the contract reads) ───────────────────

def _step_result(step_id, status, tool_result_status=None, error_code=None):
    tool_result = None
    if tool_result_status is not None:
        tool_result = SimpleNamespace(
            status=tool_result_status, error_code=error_code, tool="web_search",
        )
    return SimpleNamespace(
        step_id=step_id, status=status, output="", error=None,
        tool="web_search", tool_result=tool_result,
    )


def _state(request_id="req-1", cancelled=False, timed_out=False):
    return SimpleNamespace(
        request_id=request_id, cancelled=cancelled, request_timed_out=timed_out,
    )


def _ctx(
    *,
    execution_status="completed",
    step_results=None,
    loop=None,
    ranked_chunks=None,
    budget=None,
    validation=None,
    answer="final answer",
    intent="rag_query",
    route="retrieval",
    execution_id="exec-1",
    cancelled=False,
    timed_out=False,
    trace=None,
    answer_mode="grounded",
):
    return SimpleNamespace(
        agent_state=_state(cancelled=cancelled, timed_out=timed_out),
        execution_id=execution_id,
        execution=SimpleNamespace(
            status=execution_status,
            step_results=step_results or [],
        ),
        execution_loop=loop,
        ranked_chunks=ranked_chunks or [],
        token_budget=budget,
        validation=validation,
        synthesis=SimpleNamespace(answer=answer),
        intent=SimpleNamespace(value=intent),
        intent_label=intent,
        route=SimpleNamespace(value=route),
        agent_trace=trace,
        answer_mode=answer_mode,
    )


def _loop(completed=False, iterations=1, stopped_reason="step 1 failed"):
    return SimpleNamespace(
        completed=completed, iterations=iterations, stopped_reason=stopped_reason,
    )


def _chunk(source, page=None, score=0.9, chunk_id="c1"):
    return SimpleNamespace(
        chunk=SimpleNamespace(
            source=source, page=page, score=score, chunk_id=chunk_id,
        ),
        reranker_score=None,
    )


def _budget_with_usage():
    budget = TokenBudget()
    budget.record(model="gpt-4o-mini", input_tokens=1000, output_tokens=500)
    budget.record(model="deepseek-chat", input_tokens=200, output_tokens=100)
    return budget


class _FakePipeline:
    """Duck-typed RAGPipeline stand-in for hermetic facade tests."""

    def __init__(self, ctx=None, error=None):
        self._ctx = ctx
        self._error = error
        self.calls = 0
        self.last_kwargs = None

    def process(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self._error is not None:
            raise self._error
        return self._ctx


# ── 1: Request schema ────────────────────────────────────────────────────────

def test_request_schema():
    req = AgentRequest(
        question="What is RBAC?",
        session_id="s1",
        project_id="p1",
        user_id="u1",
        filename="docs.pdf",
        retriever_mode="hybrid",
    )
    assert req.question == "What is RBAC?"
    assert req.session_id == "s1"
    assert req.project_id == "p1"
    assert req.user_id == "u1"
    assert req.filename == "docs.pdf"
    assert req.retriever_mode == "hybrid"
    assert req.validate() == []
    d = req.to_dict()
    assert d["question"] == "What is RBAC?"
    assert d["session_id"] == "s1"


def test_request_schema_defaults_and_validation():
    req = AgentRequest(question="q", session_id="s")
    assert req.project_id is None
    assert req.user_id is None
    assert req.filename is None
    assert req.retriever_mode is None

    assert AgentRequest(question="   ", session_id="s").validate() == [
        "question is required"
    ]
    assert AgentRequest(question="q", session_id="  ").validate() == [
        "session_id is required"
    ]
    long_q = AgentRequest(question="x" * (AgentRequest.MAX_QUESTION_CHARS + 1), session_id="s")
    assert long_q.validate() == [
        f"question exceeds {AgentRequest.MAX_QUESTION_CHARS} characters"
    ]


# ── 2: Response schema ───────────────────────────────────────────────────────

def test_response_schema():
    ctx = _ctx()
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)
    assert isinstance(response, AgentResponse)
    assert isinstance(response.execution, ExecutionSummary)
    d = response.to_dict()
    expected_keys = {
        "request_id", "execution_id", "session_id", "status",
        "response", "answer", "answer_mode", "intent", "route",
        "execution", "validation", "sources", "resources",
        "usage", "estimated_cost_usd", "errors", "record_id",
    }
    assert set(d.keys()) == expected_keys
    assert d["request_id"] == "req-1"
    assert d["execution_id"] == "exec-1"
    assert d["session_id"] == "s1"
    assert d["status"] == "completed"


def test_response_rejects_unknown_status():
    try:
        AgentResponse(
            request_id="r", execution_id="e", session_id="s",
            status="mystery",
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


# ── 3: Execution status mapping ──────────────────────────────────────────────

def test_execution_status_mapping():
    assert map_status(_ctx(execution_status="completed")) == "completed"
    assert map_status(_ctx(execution_status="partial")) == "partial"
    assert map_status(_ctx(execution_status="failed")) == "failed"
    assert map_status(_ctx(execution_status="blocked")) == "blocked"

    cancelled = _ctx(execution_status="completed", cancelled=True)
    assert map_status(cancelled) == "cancelled"

    timed_out = _ctx(execution_status="partial", timed_out=True)
    assert map_status(timed_out) == "timed_out"

    # Cancellation wins over timeout.
    both = _ctx(execution_status="failed", cancelled=True, timed_out=True)
    assert map_status(both) == "cancelled"

    # No execution at all → vacuous completed.
    assert map_status(SimpleNamespace(agent_state=None, execution=None)) == "completed"
    assert map_status(SimpleNamespace(
        agent_state=None,
        execution=SimpleNamespace(status="weird"),
    )) == "completed"


def test_execution_summary_counts():
    ctx = _ctx(
        execution_status="partial",
        step_results=[
            _step_result(1, "completed"),
            _step_result(2, "failed", tool_result_status="failed",
                         error_code="TOOL_FAILED"),
            _step_result(3, "blocked"),
        ],
        loop=_loop(),
    )
    summary = build_execution_summary(ctx)
    assert summary.status == "partial"
    assert summary.completed is False
    assert summary.iterations == 1
    assert summary.stopped_reason == "step 1 failed"
    assert summary.steps_total == 3
    assert summary.steps_completed == 1
    assert summary.steps_failed == 1
    assert summary.steps_blocked == 1
    assert summary.has_timeout is False


# ── 4: Successful response ───────────────────────────────────────────────────

def test_successful_response():
    ctx = _ctx(
        execution_status="completed",
        step_results=[_step_result(1, "completed")],
        loop=SimpleNamespace(completed=True, iterations=1, stopped_reason="all steps completed"),
        ranked_chunks=[_chunk("docs/intro.pdf", page=3, score=0.92, chunk_id="c-9")],
        budget=_budget_with_usage(),
        validation=SimpleNamespace(valid=True, issues=[]),
    )
    response = build_response(
        AgentRequest(question="q", session_id="s1"), ctx, record_id="rec-42",
    )

    assert response.status == "completed"
    assert response.answer == "final answer"
    assert response.intent == "rag_query"
    assert response.route == "retrieval"
    assert response.validation is not None and response.validation.valid is True
    assert response.errors == ()
    assert response.record_id == "rec-42"
    assert response.execution.completed is True
    assert len(response.sources) == 1
    assert response.estimated_cost_usd > 0


# ── 5: Partial execution response ────────────────────────────────────────────

def test_partial_execution_response():
    ctx = _ctx(
        execution_status="partial",
        step_results=[
            _step_result(1, "completed"),
            _step_result(2, "failed", tool_result_status="failed", error_code="TOOL_FAILED"),
        ],
        loop=_loop(completed=False, iterations=2, stopped_reason="step 2 failed"),
    )
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)

    assert response.status == "partial"
    assert response.execution.steps_completed == 1
    assert response.execution.steps_failed == 1
    assert response.answer == "final answer"  # completed steps remain valid


# ── 6: Failed response ───────────────────────────────────────────────────────

def test_failed_response():
    ctx = _ctx(
        execution_status="failed",
        step_results=[_step_result(1, "failed", tool_result_status="failed", error_code="TOOL_FAILED")],
        loop=_loop(completed=False, iterations=1, stopped_reason="step 1 failed"),
    )
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)

    assert response.status == "failed"
    assert response.execution.steps_failed == 1
    assert response.execution.completed is False
    assert response.errors == ()  # failures are STATUSES, not errors


# ── 7: Blocked response ──────────────────────────────────────────────────────

def test_blocked_response():
    ctx = _ctx(
        execution_status="blocked",
        step_results=[_step_result(1, "blocked"), _step_result(2, "blocked")],
        loop=_loop(completed=False, iterations=1, stopped_reason="step 1 blocked"),
    )
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)

    assert response.status == "blocked"
    assert response.execution.steps_blocked == 2
    assert response.execution.steps_completed == 0


# ── 8: Timeout response ──────────────────────────────────────────────────────

def test_timeout_response_from_request_flag():
    ctx = _ctx(execution_status="partial", timed_out=True)
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)

    assert response.status == "timed_out"
    assert response.execution.has_timeout is True


def test_timeout_detected_from_step_tool_result():
    ctx = _ctx(
        execution_status="failed",
        step_results=[
            _step_result(1, "failed", tool_result_status="timeout", error_code="TOOL_TIMEOUT"),
        ],
    )
    summary = build_execution_summary(ctx)
    assert summary.has_timeout is True
    # A plain tool failure is NOT a timeout.
    plain = _ctx(
        execution_status="failed",
        step_results=[
            _step_result(1, "failed", tool_result_status="failed", error_code="TOOL_FAILED"),
        ],
    )
    assert build_execution_summary(plain).has_timeout is False


# ── 9: Cancellation response ─────────────────────────────────────────────────

def test_cancellation_response():
    ctx = _ctx(execution_status="partial", cancelled=True)
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)

    assert response.status == "cancelled"
    assert response.execution.cancelled is True
    assert response.answer == "final answer"  # partial answer still surfaced


# ── 10: Citation/source serialization ────────────────────────────────────────

def test_source_serialization():
    chunks = [
        _chunk("docs/intro.pdf", page=3, score=0.92, chunk_id="c-9"),
        _chunk("web.example.com", page=None, score=0.87, chunk_id="c-8"),
        SimpleNamespace(chunk=SimpleNamespace(source="", score=0.5), reranker_score=0.1),
    ]
    sources = build_sources(_ctx(ranked_chunks=chunks))

    assert len(sources) == 2
    assert sources[0] == CitationSource(
        source="docs/intro.pdf", page=3, score=0.92, chunk_id="c-9",
    )
    assert sources[0].score
    assert sources[1].page is None
    d = sources[0].to_dict()
    assert d == {"source": "docs/intro.pdf", "page": 3, "score": 0.92, "chunk_id": "c-9"}
    # A duplicate source line is kept (citations, not a set).
    assert build_sources(_ctx(ranked_chunks=[_chunk("a.pdf", score=0.1)] * 2))[0] == \
        build_sources(_ctx(ranked_chunks=[_chunk("a.pdf", score=0.1)] * 2))[1]


def test_source_serialization_empty():
    assert build_sources(SimpleNamespace(ranked_chunks=None)) == ()
    assert build_sources(SimpleNamespace(ranked_chunks=[])) == ()


def test_source_uses_reranker_score_when_present():
    item = SimpleNamespace(
        chunk=SimpleNamespace(source="docs/b.pdf", page=1, score=0.5, chunk_id="b1"),
        reranker_score=0.77,
    )
    sources = build_sources(SimpleNamespace(ranked_chunks=[item]))
    assert sources[0].score == 0.77


# ── 11: Cost/token serialization ─────────────────────────────────────────────

def test_cost_token_serialization():
    budget = _budget_with_usage()
    usage, total = build_usage_summary(SimpleNamespace(token_budget=budget))

    assert len(usage) == 2
    assert [u.model for u in usage] == ["deepseek-chat", "gpt-4o-mini"]  # sorted
    by_model = {u.model: u for u in usage}
    assert by_model["gpt-4o-mini"].input_tokens == 1000
    assert by_model["gpt-4o-mini"].output_tokens == 500
    assert total == budget.total_cost_usd()
    d = usage[0].to_dict()
    assert set(d.keys()) == {"model", "input_tokens", "output_tokens", "cost_usd"}


def test_cost_serialization_without_budget():
    usage, total = build_usage_summary(SimpleNamespace(token_budget=None))
    assert usage == ()
    assert total == 0.0 or total == 0


# ── 12: Stable SSE events ────────────────────────────────────────────────────

def test_stable_sse_events():
    trace = AgentTrace(request_id="req-1", execution_id="exec-1", session_id="s1")
    trace.record("intent", "intent_classified", status="rag_query")
    trace.record("planning", "plan_created", status="created")
    trace.record("execution", "step_started", step_id=1, tool="web_search")
    trace.record("execution", "tool_completed", step_id=1, tool="web_search", duration_ms=12.5)
    trace.record("execution", "step_completed", step_id=1, tool="web_search", duration_ms=15.0)
    trace.record("execution", "step_failed", step_id=2, tool="web_search", duration_ms=5.0)

    ctx = _ctx(trace=trace)
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)
    events = build_stream_events(AgentRequest(question="q", session_id="s1"), ctx, response)

    assert [e.event for e in events] == [
        "started", "stage", "stage", "step", "tool", "step", "step", "completed",
    ]
    assert [e.sequence for e in events] == list(range(len(events)))
    # started payload: correlation IDs only.
    assert events[0].payload == {
        "request_id": "req-1", "execution_id": "exec-1", "session_id": "s1",
    }
    # stage payload: enumerated keys only.
    assert events[1].payload == {"stage": "intent", "status": "rag_query"}
    assert events[2].payload == {"stage": "planning", "status": "created"}
    # step payload: enumerated keys only (no metadata passthrough).
    assert events[3].payload == {
        "step_id": 1, "status": "running", "tool": "web_search", "duration_ms": 0.0,
    }
    assert events[5].payload == {
        "step_id": 1, "status": "completed", "tool": "web_search", "duration_ms": 15.0,
    }
    # tool payload.
    assert events[4].event == "tool"
    assert events[4].payload == {
        "tool": "web_search", "status": "completed", "duration_ms": 12.5,
    }
    # completed payload: enumerated keys only.
    assert set(events[-1].payload.keys()) == {
        "status", "answer_mode", "iterations", "stopped_reason", "estimated_cost_usd",
    }
    # Serialization is stable JSON.
    assert json.loads(json.dumps([e.to_dict() for e in events])) is not None


def test_sse_cancelled_emits_terminated_not_completed():
    trace = AgentTrace(request_id="req-1", execution_id="exec-1", session_id="s1")
    trace.record("execution", "step_cancelled", step_id=2, tool="")
    trace.record("execution", "request_cancelled")
    ctx = _ctx(cancelled=True, trace=trace)
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)
    events = build_stream_events(AgentRequest(question="q", session_id="s1"), ctx, response)

    names = [e.event for e in events]
    assert names[-1] == "terminated"
    assert "completed" not in names
    assert events[-1].payload == {"reason": "cancelled"}


def test_sse_timed_out_without_trace_events():
    ctx = _ctx(timed_out=True, trace=None)
    response = build_response(AgentRequest(question="q", session_id="s1"), ctx)
    events = build_stream_events(AgentRequest(question="q", session_id="s1"), ctx, response)

    assert [e.event for e in events] == ["started", "terminated"]
    assert events[-1].payload == {"reason": "timed_out"}


def test_stream_event_schema_validation():
    event = StreamEvent(event="started", sequence=0, payload={})
    assert event.to_dict() == {"event": "started", "sequence": 0, "payload": {}}
    try:
        StreamEvent(event="mystery", sequence=0, payload={})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert "started" in VALID_STREAM_EVENTS


# ── 13: Malformed request ────────────────────────────────────────────────────

def test_malformed_request_never_reaches_pipeline():
    fake = _FakePipeline(ctx=_ctx())
    api = AgentApi(fake)

    response = api.process(AgentRequest(question="   ", session_id=""))

    assert response.status == "failed"
    assert len(response.errors) == 1
    assert response.errors[0].code == "invalid_request"
    assert "question is required" in response.errors[0].message
    assert "session_id is required" in response.errors[0].message
    assert fake.calls == 0  # the pipeline was never touched


# ── 14: Internal exception → stable API error ────────────────────────────────

def test_internal_exception_becomes_stable_error():
    fake = _FakePipeline(error=RuntimeError("super secret internal detail"))
    api = AgentApi(fake)

    response = api.process(AgentRequest(question="q", session_id="s1"))

    assert response.status == "failed"
    assert len(response.errors) == 1
    err = response.errors[0]
    assert err.code == "internal_error"
    assert err.message == "Agent processing failed."
    # The internal exception text never reaches the client.
    assert "secret" not in json.dumps(response.to_dict())
    assert "internal detail" not in json.dumps(response.to_dict())
    assert fake.calls == 1  # the failure happened INSIDE the pipeline


def test_to_agent_error_mapping_is_stable():
    err = to_agent_error(ValueError("boom"), request_id="req-9")
    assert isinstance(err, AgentError)
    assert err.code == "internal_error"
    assert err.message == "Agent processing failed."
    assert err.request_id == "req-9"
    assert err.to_dict() == {
        "code": "internal_error", "message": "Agent processing failed.",
        "request_id": "req-9",
    }


# ── 15: Backwards-compatible existing chat response ──────────────────────────

def test_legacy_chat_response_keys_preserved():
    ctx = _ctx(answer="hello world")
    legacy_resources = [
        {"type": "file", "title": "docs/intro.pdf", "url": None, "snippet": "RBAC"},
    ]
    response = build_response(
        AgentRequest(question="q", session_id="s1"), ctx,
        legacy_resources=legacy_resources, record_id="rec-7",
    )
    d = response.to_dict()

    # Legacy frontend keys (existing clients keep working unchanged):
    assert d["session_id"] == "s1"
    assert d["response"] == "hello world"
    assert d["resources"] == legacy_resources
    assert d["answer_mode"] == "grounded"
    assert d["record_id"] == "rec-7"
    # And the stable contract names coexist:
    assert d["answer"] == "hello world"
    assert d["status"] == "completed"
    assert d["sources"] == []


def test_legacy_resources_derived_when_not_provided():
    ctx = _ctx(ranked_chunks=[_chunk("docs/intro.pdf", page=3, score=0.9, chunk_id="c1")])
    d = build_response(AgentRequest(question="q", session_id="s1"), ctx).to_dict()
    assert d["resources"] == [
        {"type": "source", "title": "docs/intro.pdf", "url": None, "snippet": None}
    ]