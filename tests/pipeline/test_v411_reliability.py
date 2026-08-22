"""V4.11 Production Reliability & Cancellation — hermetic tests.

Covers the required scenarios:
   1.  Per-tool timeout        -> TOOL_TIMEOUT, step failed, no exception
   2.  Per-step timeout        -> step boundary wins over tool boundary
   3.  Request timeout         -> pending steps blocked before any handler
   4.  Cancellation before execution (loop) -> iterations 0, all blocked
   5.  Cancellation between/during steps    -> completed stays, pending blocked
   6.  Cancellation during a running step   -> current step completes, rest blocked
   7.  Failed step (V4.7 taxonomy preserved: TOOL_FAILED, no retry, no replan)
   8.  Partial recovery: independent steps continue after a failure
   9.  Partial recovery: dependent steps are blocked, never executed
  10.  Idempotency: terminal (execution_id, step_id) result is replayed
  11.  Trace/state consistency (request_cancelled / step_cancelled / flags)
  12.  No retry / no replan on cancellation or failure
  13.  V3.13 authorization semantics preserved (AUTHORIZATION_REQUIRED)
  14.  V4.7 taxonomy preserved end-to-end (statuses + error codes)

Zero live API / DB / LLM calls; deterministic fake clock.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.executor import Executor
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.tool_selection import ToolSelection
from app.agent.pipeline.loop import AgentExecutionLoop
from app.agent.pipeline.state import AgentState, StepExecutionState
from app.agent.pipeline.trace import AgentTrace
from app.agent.pipeline.reliability import (
    IdempotencyLedger,
    ReliabilityGuard,
    TimeoutPolicy,
    REASON_REQUEST_CANCELLED,
    REASON_REQUEST_TIMED_OUT,
)


# ── Deterministic clock ──────────────────────────────────────────────────────

class FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


# ── Shared helpers (same shape as the V3.12 suite) ───────────────────────────

def _step(step_id, action, tool=None, deps=None, description=None) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        description=description if description is not None else f"step {step_id}",
        action=action,
        dependencies=deps or [],
        expected_output="output",
        tool=tool,
    )


def _plan(*steps) -> Plan:
    return Plan(
        goal="test plan",
        steps=list(steps),
        requires_tools=any(s.tool is not None for s in steps),
        estimated_complexity="simple",
    )


def _cap(step_id, allowed=True, reason="", tool=None) -> CapabilitySelection:
    return CapabilitySelection(
        step_id=step_id, capability="capability-x", tool=tool,
        allowed=allowed, reason=reason,
    )


def _tsel(step_id, tool=None, arguments=None, allowed=True, reason="") -> ToolSelection:
    return ToolSelection(
        step_id=step_id, tool=tool, arguments=dict(arguments or {}),
        allowed=allowed, reason=reason,
    )


def _gate_result(text: str) -> MagicMock:
    mock = MagicMock()
    mock.status = "executed"
    mock.result = text
    mock.error = None
    return mock


def _pending_gate_result() -> MagicMock:
    mock = MagicMock()
    mock.status = "pending"
    mock.result = None
    mock.error = None
    return mock


def _failed_gate_result(err: str) -> MagicMock:
    mock = MagicMock()
    mock.status = "failed"
    mock.result = None
    mock.error = err
    return mock


def _patch_gate(monkeypatch, impl) -> None:
    monkeypatch.setattr("app.agent.pipeline.executor.request_tool_execution", impl)


def _explode_gate(tool, args):
    raise AssertionError(f"tool gate must never be called, got {tool} {args}")


def _explode_llm(**kw):
    raise AssertionError("LLM must never be called")


def _ctx(
    steps,
    *,
    cancel=False,
    guard=None,
    ledger=None,
    trace=True,
    execution_id="exec-v411",
) -> SimpleNamespace:
    state = AgentState(request_id="req-v411", question="q", plan_steps=len(steps))
    state.steps = [StepExecutionState(step_id=s.step_id) for s in steps]
    tr = (
        AgentTrace(request_id="req-v411", execution_id=execution_id)
        if trace else None
    )
    return SimpleNamespace(
        question="q",
        final_query="",
        user_id="u1",
        project_id="p1",
        session_id="s1",
        context=SimpleNamespace(
            knowledge_context=None, document_context=None, web_context=None,
        ),
        agent_state=state,
        execution_id=execution_id,
        agent_trace=tr,
        cancel_requested=cancel,
        reliability=guard,
        idempotency=ledger,
    )


def _events(ctx) -> list:
    return ctx.agent_trace.events()


def _event_names(ctx) -> list:
    return [e.event for e in _events(ctx)]


def _run(plan, ctx, caps=None, tsel=None, **loop_kwargs):
    return AgentExecutionLoop(executor=Executor(), **loop_kwargs).run(
        plan,
        context=ctx,
        capability_selections=caps or [_cap(s.step_id) for s in plan.steps],
        tool_selections=tsel or [
            _tsel(s.step_id, tool=s.tool, arguments={"query": "q"})
            if s.tool else _tsel(s.step_id, tool=None, arguments={})
            for s in plan.steps
        ],
    )


def _memory_tsel(steps):
    """Tool selections with memory-friendly arguments (fact, not query)."""
    return [
        _tsel(s.step_id, tool=s.tool,
              arguments={"fact": "x"} if s.action == "memory" else {"query": "q"})
        if s.tool else _tsel(s.step_id, tool=None, arguments={})
        for s in steps
    ]


# ── Unit: TimeoutPolicy ──────────────────────────────────────────────────────

def test_timeout_policy_rejects_non_positive_values():
    with pytest.raises(ValueError):
        TimeoutPolicy(tool_timeout_s=0)
    with pytest.raises(ValueError):
        TimeoutPolicy(step_timeout_s=-1.0)
    with pytest.raises(ValueError):
        TimeoutPolicy(request_timeout_s="30")


def test_timeout_policy_defaults():
    policy = TimeoutPolicy()
    assert policy.tool_timeout_s > 0
    assert policy.step_timeout_s > 0
    assert policy.request_timeout_s > 0


# ── Unit: ReliabilityGuard ───────────────────────────────────────────────────

def test_guard_clock_decisions():
    clock = FakeClock(0.0)
    guard = ReliabilityGuard(
        TimeoutPolicy(tool_timeout_s=15.0, step_timeout_s=30.0, request_timeout_s=120.0),
        clock=clock,
        request_started=0.0,
    )
    assert guard.request_expired() is False
    assert guard.tool_exceeded(0.0) is False

    clock.advance(15.0)
    assert guard.tool_exceeded(0.0) is True
    assert guard.step_exceeded(0.0) is False

    clock.advance(20.0)  # t=35
    assert guard.step_exceeded(0.0) is True
    assert guard.request_expired() is False

    clock.advance(100.0)  # t=135
    assert guard.request_expired() is True
    # elapsed is never negative
    assert guard.elapsed(500.0) == 0.0


# ── Unit: IdempotencyLedger ──────────────────────────────────────────────────

def _fake_result(status, output="", error=None, tool_result=None):
    return SimpleNamespace(
        status=status, step_id=1, output=output, error=error, tool="web_search",
        tool_result=tool_result,
    )


def test_ledger_first_terminal_wins_and_ignores_non_terminal():
    ledger = IdempotencyLedger()
    ledger.record("e1", 1, _fake_result("completed", output="out-1"))
    ledger.record("e1", 1, _fake_result("failed", error="overwrite attempt"))
    ledger.record("e1", 2, _fake_result("pending"))
    ledger.record("e1", 3, _fake_result("running"))

    assert ledger.terminal_for("e1", 1).status == "completed"
    assert ledger.terminal_for("e1", 1).output == "out-1"
    # First terminal result is never overwritten.
    assert ledger.terminal_for("e1", 1).error is None
    # Non-terminal statuses are never cached; unknown keys return None.
    assert ledger.terminal_for("e1", 2) is None
    assert ledger.terminal_for("e1", 3) is None
    assert ledger.terminal_for("e2", 1) is None
    assert len(ledger) == 1


# ── 1: Per-tool timeout ──────────────────────────────────────────────────────

def test_tool_timeout_relabels_to_tool_timeout(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search"))
    clock = FakeClock(0.0)
    guard = ReliabilityGuard(
        TimeoutPolicy(tool_timeout_s=15.0, step_timeout_s=30.0),
        clock=clock, request_started=0.0,
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        clock.advance(20.0)  # exceeds the 15s tool cap
        return _gate_result("late results")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps, guard=guard)

    result = Executor().execute_one(
        plan.steps[0], context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )

    assert result.status == "failed"
    assert result.tool_result is not None
    assert result.tool_result.status == "timeout"
    assert result.tool_result.error_code == "TOOL_TIMEOUT"
    assert "Tool timed out." in result.tool_result.error
    assert result.tool_result.output == ""  # late output never surfaces
    assert calls == [("web_search", {"query": "q"})]
    # The step failed through the EXISTING step_failed/tool_failed events.
    assert _event_names(ctx) == ["step_started", "step_failed", "tool_failed"]


# ── 2: Per-step timeout (tool boundary untouched) ────────────────────────────

def test_step_timeout_wins_when_tool_cap_not_exceeded(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search"))
    clock = FakeClock(0.0)
    guard = ReliabilityGuard(
        TimeoutPolicy(tool_timeout_s=25.0, step_timeout_s=10.0),
        clock=clock, request_started=0.0,
    )

    def _gate(tool, args):
        clock.advance(20.0)  # under the 25s tool cap, over the 10s step cap
        return _gate_result("slow but ok")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps, guard=guard)

    result = Executor().execute_one(
        plan.steps[0], context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )

    assert result.status == "failed"
    assert result.tool_result.status == "timeout"
    assert result.tool_result.error_code == "TOOL_TIMEOUT"
    assert "Step timed out." in result.tool_result.error
    assert ctx.agent_state.steps[0].status == "failed"


# ── 3: Request timeout (executor gate, before any handler) ───────────────────

def test_request_timeout_blocks_before_handler(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search"))
    clock = FakeClock(0.0)
    guard = ReliabilityGuard(
        TimeoutPolicy(request_timeout_s=5.0),
        clock=clock, request_started=0.0,
    )
    clock.advance(10.0)  # request already expired
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("never")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps, guard=guard)

    result = Executor().execute_one(
        plan.steps[0], context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )

    assert result.status == "blocked"
    assert result.error == REASON_REQUEST_TIMED_OUT
    assert calls == []  # handler never ran
    assert ctx.agent_state.steps[0].status == "blocked"
    assert _event_names(ctx) == ["step_blocked"]


# ── 3b: Request timeout (loop level) ─────────────────────────────────────────

def test_loop_request_timeout_settles_remaining(monkeypatch):
    plan = _plan(
        _step(1, "web_search", tool="web_search"),
        _step(2, "memory", tool="remember_user_fact"),
    )
    clock = FakeClock(0.0)
    guard = ReliabilityGuard(
        TimeoutPolicy(request_timeout_s=5.0),
        clock=clock, request_started=0.0,
    )
    clock.advance(10.0)
    _patch_gate(monkeypatch, _explode_gate)
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", _explode_llm)
    ctx = _ctx(plan.steps, guard=guard)

    result = _run(plan, ctx)

    assert result.completed is False
    assert result.iterations == 0
    assert result.stopped_reason == "request timed out"
    assert result.execution.status == "blocked"
    assert all(r.status == "blocked" for r in result.execution.step_results)
    assert all(r.error == REASON_REQUEST_TIMED_OUT for r in result.execution.step_results)
    # State flags + per-step and request-level events.
    assert ctx.agent_state.request_timed_out is True
    assert [s.status for s in ctx.agent_state.steps] == ["blocked", "blocked"]
    assert _event_names(ctx) == ["step_blocked", "step_blocked", "request_timeout"]


# ── 4: Cancellation before execution ─────────────────────────────────────────

def test_cancel_before_execution_blocks_everything(monkeypatch):
    plan = _plan(
        _step(1, "web_search", tool="web_search"),
        _step(2, "memory", tool="remember_user_fact"),
    )
    _patch_gate(monkeypatch, _explode_gate)
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", _explode_llm)
    ctx = _ctx(plan.steps, cancel=True)

    result = _run(plan, ctx)

    assert result.completed is False
    assert result.iterations == 0
    assert result.stopped_reason == "request cancelled"
    assert result.execution.status == "blocked"
    assert [r.step_id for r in result.execution.step_results] == [1, 2]
    assert all(r.status == "blocked" for r in result.execution.step_results)
    assert all(r.error == REASON_REQUEST_CANCELLED for r in result.execution.step_results)
    # State: nothing left running or pending.
    assert ctx.agent_state.cancelled is True
    assert [s.status for s in ctx.agent_state.steps] == ["blocked", "blocked"]
    # Trace: per-step + one request-level event.
    events = _events(ctx)
    assert _event_names(ctx) == ["step_cancelled", "step_cancelled", "request_cancelled"]
    assert all(e.step_id is not None for e in events[:2])
    assert events[2].step_id is None
    assert all(e.event in ("step_cancelled", "request_cancelled") for e in events)


# ── 4b: Executor cancel gate (direct execute_one path) ───────────────────────

def test_executor_cancel_gate_blocks_direct_calls(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search"))
    _patch_gate(monkeypatch, _explode_gate)
    ctx = _ctx(plan.steps, cancel=True)

    result = Executor().execute_one(
        plan.steps[0], context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )

    assert result.status == "blocked"
    assert result.error == REASON_REQUEST_CANCELLED
    assert ctx.agent_state.steps[0].status == "blocked"
    assert _event_names(ctx) == ["step_cancelled"]


# ── 5/6: Cancellation between / during steps ─────────────────────────────────

def test_cancel_during_step_completes_current_and_blocks_rest(monkeypatch):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "web_search", tool="web_search", description="latest release"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        if tool == "remember_user_fact":
            # The operator cancels WHILE step 1 is running.
            step1_ctx.cancel_requested = True
            return _gate_result("stored")
        return _gate_result("never")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps)
    step1_ctx = ctx

    result = _run(plan, ctx, tsel=_memory_tsel(plan.steps))

    # Step 1 completed (its outcome is valid), step 2 was never started.
    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "request cancelled"
    assert result.execution.status == "partial"
    assert result.execution.step_results[0].status == "completed"
    assert result.execution.step_results[0].output == "stored"
    assert result.execution.step_results[1].status == "blocked"
    assert result.execution.step_results[1].error == REASON_REQUEST_CANCELLED
    assert calls == [("remember_user_fact", {"fact": "x"})]
    # State consistent: completed stays completed, blocked is blocked.
    assert [s.status for s in ctx.agent_state.steps] == ["completed", "blocked"]
    assert ctx.agent_state.cancelled is True
    assert _event_names(ctx) == [
        "step_started", "step_completed", "tool_completed",
        "step_cancelled", "request_cancelled",
    ]


# ── 7: Failed step — taxonomy preserved, no retry, no replan ─────────────────

def test_failed_step_preserves_taxonomy_and_never_retries(monkeypatch):
    plan = _plan(_step(1, "knowledge", tool="search_knowledge_base", description="docs"))
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _failed_gate_result("knowledge base unreachable")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps)

    result = _run(plan, ctx)

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 failed"
    assert result.execution.status == "failed"
    sr = result.execution.step_results[0]
    assert sr.status == "failed"
    assert sr.tool_result.error_code == "TOOL_FAILED"
    assert "knowledge base unreachable" in sr.error
    # No retry, no replan: exactly one gate call, one iteration.
    assert calls == [("search_knowledge_base", {"query": "q"})]
    # Trace: tool_failed carries the stable code.
    tool_failed = [e for e in _events(ctx) if e.event == "tool_failed"]
    assert len(tool_failed) == 1
    assert tool_failed[0].metadata.get("error_code") == "TOOL_FAILED"
    # V3.13 single-use authorization semantics intact (pending stays blocked).
    ctx2 = _ctx(plan.steps, ledger=IdempotencyLedger())

    def _pending(tool, args):
        return _pending_gate_result()

    _patch_gate(monkeypatch, _pending)
    result2 = Executor().execute_one(
        plan.steps[0], context=ctx2,
        capability_selections=[_cap(1)],
        tool_selections=[_tsel(1, tool="search_knowledge_base", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )
    assert result2.status == "blocked"
    assert result2.error == "AUTHORIZATION_REQUIRED: Tool execution requires operator approval."


# ── 8: Partial recovery — independent steps continue ─────────────────────────

def test_independent_steps_continue_after_failure(monkeypatch):
    plan = _plan(
        _step(1, "knowledge", tool="search_knowledge_base", description="docs"),
        _step(2, "memory", tool="remember_user_fact", description="Keep Python"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        if tool == "search_knowledge_base":
            return _failed_gate_result("kb down")
        return _gate_result(f"result-for-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps)

    result = _run(plan, ctx, tsel=_memory_tsel(plan.steps))

    assert result.completed is False
    assert result.iterations == 2  # the independent step still ran
    assert result.stopped_reason == "step 1 failed"
    assert result.execution.status == "partial"
    by_id = {r.step_id: r for r in result.execution.step_results}
    assert by_id[1].status == "failed"
    assert by_id[2].status == "completed"
    assert by_id[2].output == "result-for-remember_user_fact"
    assert calls == [
        ("search_knowledge_base", {"query": "q"}),
        ("remember_user_fact", {"fact": "x"}),
    ]
    assert [s.status for s in ctx.agent_state.steps] == ["failed", "completed"]


# ── 9: Partial recovery — dependent steps blocked, never executed ────────────

def test_dependent_steps_blocked_after_failure(monkeypatch):
    plan = _plan(
        _step(1, "knowledge", tool="search_knowledge_base", description="docs"),
        _step(2, "direct_answer", deps=[1], description="synthesize"),
    )
    calls = []
    llm = MagicMock()

    def _gate(tool, args):
        calls.append((tool, args))
        return _failed_gate_result("kb down")

    _patch_gate(monkeypatch, _gate)
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", lambda **kw: llm)
    ctx = _ctx(plan.steps)

    result = _run(plan, ctx)

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 failed"
    assert result.execution.status == "failed"
    by_id = {r.step_id: r for r in result.execution.step_results}
    assert by_id[1].status == "failed"
    assert by_id[2].status == "blocked"
    assert "dependency step(s) [1]" in by_id[2].error
    assert calls == [("search_knowledge_base", {"query": "q"})]
    assert llm.invoke.call_count == 0  # dependent never executed
    assert ctx.agent_state.steps[1].status == "blocked"
    assert any(e.step_id == 2 and e.event == "step_blocked" for e in _events(ctx))


# ── 10: Idempotent terminal replay ───────────────────────────────────────────

def test_idempotent_replay_never_duplicates_execution(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search"))
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("search results")

    _patch_gate(monkeypatch, _gate)
    ledger = IdempotencyLedger()
    ctx = _ctx(plan.steps, ledger=ledger)
    executor = Executor()

    kwargs = dict(
        context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )
    first = executor.execute_one(plan.steps[0], **kwargs)
    second = executor.execute_one(plan.steps[0], **kwargs)

    # Same terminal result, handler ran exactly ONCE.
    assert first.status == "completed"
    assert first.output == "search results"
    assert second.status == "completed"
    assert second.output == "search results"
    assert calls == [("web_search", {"query": "q"})]

    # A different execution_id executes again (ledger keys per execution).
    ctx2 = _ctx(plan.steps, ledger=ledger, execution_id="exec-2")
    third = Executor().execute_one(
        plan.steps[0], context=ctx2,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )
    assert third.status == "completed"
    assert calls == [
        ("web_search", {"query": "q"}),
        ("web_search", {"query": "q"}),
    ]


def test_replay_never_bypasses_policy_gates(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search"))
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("out")

    _patch_gate(monkeypatch, _gate)
    ctx = _ctx(plan.steps, ledger=IdempotencyLedger())
    executor = Executor()
    kwargs = dict(
        context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )
    assert executor.execute_one(plan.steps[0], **kwargs).status == "completed"

    # Denied selections still block BEFORE replay — policy is authoritative.
    denied = Executor().execute_one(
        plan.steps[0], context=ctx,
        capability_selections=[_cap(1, allowed=False, reason="no web")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
        step_status={}, step_outputs={},
    )
    assert denied.status == "blocked"
    assert "no web" in denied.error
    assert calls == [("web_search", {"query": "q"})]


# ── 11: Trace/state consistency on cancellation (already asserted above) ─────

def test_cancellation_state_and_trace_consistent(monkeypatch):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "knowledge", tool="search_knowledge_base", description="docs"),
        _step(3, "web_search", tool="web_search", description="news"),
    )
    calls = []
    ctx = _ctx(plan.steps)

    def _gate(tool, args):
        calls.append((tool, args))
        # The operator cancels while step 1 is executing.
        ctx.cancel_requested = True
        return _gate_result("stored")

    _patch_gate(monkeypatch, _gate)
    result = _run(plan, ctx)

    # Step 1 completed; steps 2 and 3 were settled blocked by the loop's
    # cancellation pass (never executed, never left running/pending).
    assert [r.step_id for r in result.execution.step_results] == [1, 2, 3]
    assert [r.status for r in result.execution.step_results] == [
        "completed", "blocked", "blocked",
    ]
    assert result.iterations == 1
    assert result.stopped_reason == "request cancelled"
    assert all(
        r.error == REASON_REQUEST_CANCELLED
        for r in result.execution.step_results[1:]
    )
    # Every step has a consistent terminal state; nothing running/pending.
    assert [s.status for s in ctx.agent_state.steps] == ["completed", "blocked", "blocked"]
    assert ctx.agent_state.cancelled is True
    # Both unsettled steps got per-step events; one request-level event.
    names = _event_names(ctx)
    assert names.count("step_cancelled") == 2
    assert names.count("request_cancelled") == 1
    assert all(e.step_id in (2, 3) for e in _events(ctx) if e.event == "step_cancelled")
    assert len(calls) == 1  # only step 1 executed; steps 2/3 never ran


# ── 12: No retry / no replan on failure or cancellation ──────────────────────

def test_no_retry_after_failure(monkeypatch):
    plan = _plan(_step(1, "direct_answer", description="explain"))
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("llm exploded")
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", lambda **kw: llm)
    ctx = _ctx(plan.steps)

    result = _run(plan, ctx)

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 failed"
    assert result.execution.status == "failed"
    assert llm.invoke.call_count == 1  # exactly ONE call, never retried
