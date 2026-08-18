"""V3.12 Controlled Agent Execution Loop — hermetic tests.

Covers the 15 required cases:
   1.  Single-step execution
   2.  Sequential multi-step execution
   3.  Dependency ordering (outputs flow as context)
   4.  Blocked dependency -> dependent never executes
   5.  Failed dependency -> run stops, dependent never executes
   6.  Capability denial (V3.10) blocks even with an approved tool
   7.  Tool-selection denial (V3.11) blocks before the gate
   8.  Plan exceeding MAX_STEPS is rejected outright
   9.  MAX_ITERATIONS hard cap stops the loop
  10.  Empty / None plan terminates immediately
  11.  All steps completed -> clean stop reason
  12.  AgentState transitions (pending -> running -> completed)
  13.  No parallel execution (one gate call per iteration)
  14.  No retry / no replan after a step failure
  15.  Executor receives only approved selections

Zero live API / DB / LLM calls.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.executor import Executor
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.tool_selection import ToolSelection
from app.agent.pipeline.loop import AgentExecutionLoop
from app.agent.pipeline.state import AgentState, StepExecutionState


# ── Helpers ─────────────────────────────────────────────────────────────────

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
        step_id=step_id,
        capability="capability-x",
        tool=tool,
        allowed=allowed,
        reason=reason,
    )


def _tsel(step_id, tool=None, arguments=None, allowed=True, reason="") -> ToolSelection:
    return ToolSelection(
        step_id=step_id,
        tool=tool,
        arguments=dict(arguments or {}),
        allowed=allowed,
        reason=reason,
    )


def _gate_result(text: str) -> MagicMock:
    mock = MagicMock()
    mock.status = "executed"
    mock.result = text
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


def _agent_ctx(steps, question="q") -> SimpleNamespace:
    state = AgentState(request_id="req-v312", question=question, plan_steps=len(steps))
    state.steps = [StepExecutionState(step_id=s.step_id) for s in steps]
    return SimpleNamespace(
        question=question,
        final_query="",
        user_id="u1",
        project_id="p1",
        session_id="s1",
        context=SimpleNamespace(
            knowledge_context=None,
            document_context=None,
            web_context=None,
        ),
        agent_state=state,
    )


# ── 1: Single-step execution ─────────────────────────────────────────────────

def test_single_step_execution(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search", description="latest release"))
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("search results")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1, tool="web_search")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "latest release"})],
    )

    assert result.completed is True
    assert result.iterations == 1
    assert result.stopped_reason == "all steps completed"
    assert result.execution.status == "completed"
    assert result.execution.final_output == "search results"
    assert calls == [("web_search", {"query": "latest release"})]


# ── 2: Sequential multi-step execution ───────────────────────────────────────

def test_sequential_multi_step_execution(monkeypatch):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "knowledge", tool="search_knowledge_base", description="What is RBAC?"),
        _step(3, "web_search", tool="web_search", description="latest Kubernetes release"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result(f"result-for-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)
    caps = [_cap(1, tool="remember_user_fact"), _cap(2, tool="search_knowledge_base"),
            _cap(3, tool="web_search")]
    tsel = [
        _tsel(1, tool="remember_user_fact", arguments={"fact": "Keep Python"}),
        _tsel(2, tool="search_knowledge_base", arguments={"query": "What is RBAC?"}),
        _tsel(3, tool="web_search", arguments={"query": "kubernetes"}),
    ]

    result = AgentExecutionLoop(executor=Executor()).run(
        plan, context=ctx, capability_selections=caps, tool_selections=tsel,
    )

    assert result.completed is True
    assert result.iterations == 3
    assert result.stopped_reason == "all steps completed"
    assert result.execution.status == "completed"
    assert [r.step_id for r in result.execution.step_results] == [1, 2, 3]
    assert all(r.status == "completed" for r in result.execution.step_results)
    assert result.execution.outputs[1] == "result-for-remember_user_fact"
    assert result.execution.outputs[3] == "result-for-web_search"
    assert result.execution.final_output == "result-for-web_search"
    assert len(calls) == 3


# ── 3: Dependency ordering (outputs flow as context) ─────────────────────────

def test_dependency_ordering(monkeypatch):
    plan = _plan(
        _step(1, "knowledge", tool="search_knowledge_base", description="What is RBAC?"),
        _step(2, "direct_answer", deps=[1], description="Explain RBAC"),
    )
    order: list = []
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        order.append("gate:1")
        return _gate_result("kb-out")

    _patch_gate(monkeypatch, _gate)

    captured = {}

    def _invoke(messages):
        order.append("llm:2")
        captured["system"] = str(messages[0].content) if messages else ""
        return SimpleNamespace(content="final answer")

    llm = MagicMock()
    llm.invoke.side_effect = _invoke
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", lambda **kw: llm)

    ctx = _agent_ctx(plan.steps)
    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1), _cap(2)],
        tool_selections=[
            _tsel(1, tool="search_knowledge_base", arguments={"query": "RBAC?"}),
            _tsel(2, tool=None, arguments={}),
        ],
    )

    assert result.completed is True
    assert result.iterations == 2
    # Step 1 ran before step 2 (dependency first, single thread).
    assert order == ["gate:1", "llm:2"]
    # Step 1's output was passed as dependency context to step 2.
    assert "[Step 1]" in captured["system"]
    assert "kb-out" in captured["system"]
    assert result.execution.final_output == "final answer"


# ── 4: Blocked dependency -> dependent never executes ────────────────────────

def test_blocked_dependency_stops_run(monkeypatch):
    plan = _plan(
        _step(1, "web_search", tool="web_search", description="research"),
        _step(2, "direct_answer", deps=[1], description="synthesize"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("results")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1, allowed=False, reason="web search denied by policy")],
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"})],
    )

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 blocked"
    assert result.execution.status == "blocked"
    assert result.execution.step_results[0].status == "blocked"
    assert "web search denied by policy" in result.execution.step_results[0].error
    # The dependent step never executed.
    assert len(calls) == 0


# ── 5: Failed dependency -> run stops, dependent never executes ──────────────

def test_failed_step_stops_run(monkeypatch):
    plan = _plan(
        _step(1, "knowledge", tool="search_knowledge_base", description="query docs"),
        _step(2, "direct_answer", deps=[1], description="synthesize"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _failed_gate_result("knowledge base unreachable")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1), _cap(2)],
        tool_selections=[
            _tsel(1, tool="search_knowledge_base", arguments={"query": "q"}),
            _tsel(2, tool=None, arguments={}),
        ],
    )

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 failed"
    assert result.execution.status == "failed"
    assert result.execution.step_results[0].status == "failed"
    # The dependent step never executed.
    assert len(calls) == 1


# ── 6: Capability denial (V3.10) blocks even with an approved tool ──────────

def test_capability_denial_blocks_despite_approved_tool(monkeypatch):
    plan = _plan(_step(1, "web_search", tool="web_search", description="research"))
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("results")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1, allowed=False, reason="source policy blocks web")],
        # Tool selection is ALLOWED — capability denial still wins (fail closed).
        tool_selections=[_tsel(1, tool="web_search", arguments={"query": "q"}, allowed=True)],
    )

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 blocked"
    assert result.execution.status == "blocked"
    assert result.execution.step_results[0].status == "blocked"
    assert "source policy blocks web" in result.execution.step_results[0].error
    assert calls == []


# ── 7: Tool-selection denial (V3.11) blocks before the gate ──────────────────

def test_tool_selection_denial_blocks_before_gate(monkeypatch):
    plan = _plan(_step(1, "memory", tool="remember_user_fact", description="Keep Python"))
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result("stored")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1)],
        tool_selections=[_tsel(1, tool="remember_user_fact",
                               arguments={"fact": "x"}, allowed=False,
                               reason="tool policy: memory writes not allowed")],
    )

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 blocked"
    assert result.execution.step_results[0].status == "blocked"
    assert "tool policy: memory writes not allowed" in result.execution.step_results[0].error
    assert calls == []


# ── 8: Plan exceeding MAX_STEPS is rejected outright ─────────────────────────

def test_plan_exceeding_max_steps_rejected(monkeypatch):
    steps = [_step(i, "direct_answer") for i in range(1, 12)]  # 11 > MAX_STEPS=10
    plan = _plan(*steps)
    _patch_gate(monkeypatch, _explode_gate)
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", _explode_llm)
    ctx = _agent_ctx(steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(i) for i in range(1, 12)],
        tool_selections=[_tsel(i) for i in range(1, 12)],
    )

    assert result.completed is False
    assert result.iterations == 0
    assert result.stopped_reason == "plan exceeds max steps (10)"
    assert result.execution.status == "completed"  # empty aggregate
    assert result.execution.final_output == "No steps to execute."
    assert result.execution.step_results == []


# ── 9: MAX_ITERATIONS hard cap stops the loop ────────────────────────────────

def test_max_iterations_hard_cap(monkeypatch):
    plan = _plan(
        _step(1, "web_search", tool="web_search", description="a"),
        _step(2, "knowledge", tool="search_knowledge_base", description="b"),
        _step(3, "memory", tool="remember_user_fact", description="c"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result(f"out-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)
    caps = [_cap(i) for i in range(1, 4)]
    tsel = [
        _tsel(1, tool="web_search", arguments={"query": "a"}),
        _tsel(2, tool="search_knowledge_base", arguments={"query": "b"}),
        _tsel(3, tool="remember_user_fact", arguments={"fact": "c"}),
    ]

    result = AgentExecutionLoop(executor=Executor(), max_iterations=2).run(
        plan, context=ctx, capability_selections=caps, tool_selections=tsel,
    )

    assert result.completed is False
    assert result.iterations == 2
    assert result.stopped_reason == "max iterations reached"
    assert [r.step_id for r in result.execution.step_results] == [1, 2]
    assert all(r.status == "completed" for r in result.execution.step_results)
    assert len(calls) == 2  # step 3 never ran


# ── 10: Empty / None plan terminates immediately ─────────────────────────────

def test_empty_and_none_plan(monkeypatch):
    _patch_gate(monkeypatch, _explode_gate)
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", _explode_llm)

    loop = AgentExecutionLoop(executor=Executor())

    for plan in (None, _plan()):
        result = loop.run(plan, context=None, capability_selections=[], tool_selections=[])
        assert result.completed is True
        assert result.iterations == 0
        assert result.stopped_reason == "empty plan"
        assert result.execution.status == "completed"
        assert result.execution.final_output == "No steps to execute."
        assert result.execution.step_results == []


# ── 11: All steps completed -> clean stop reason ─────────────────────────────

def test_all_steps_completed(monkeypatch):
    plan = _plan(
        _step(1, "knowledge", tool="search_knowledge_base", description="a"),
        _step(2, "web_search", tool="web_search", description="b"),
    )

    def _gate(tool, args):
        return _gate_result(f"out-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)
    caps = [_cap(1), _cap(2)]
    tsel = [
        _tsel(1, tool="search_knowledge_base", arguments={"query": "a"}),
        _tsel(2, tool="web_search", arguments={"query": "b"}),
    ]

    result = AgentExecutionLoop(executor=Executor()).run(
        plan, context=ctx, capability_selections=caps, tool_selections=tsel,
    )

    assert result.completed is True
    assert result.iterations == 2
    assert result.stopped_reason == "all steps completed"
    assert result.execution.status == "completed"
    assert result.execution.final_output == "out-web_search"


# ── 12: AgentState transitions (pending -> running -> completed) ─────────────

def test_agent_state_transitions(monkeypatch):
    import app.agent.pipeline.executor as executor_module

    plan = _plan(
        _step(1, "web_search", tool="web_search", description="a"),
        _step(2, "knowledge", tool="search_knowledge_base", description="b"),
    )

    def _gate(tool, args):
        return _gate_result(f"out-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)
    state = ctx.agent_state

    observed = []
    real_started = executor_module.mark_step_started

    def _wrap_started(st, step_id, tool=None):
        real_started(st, step_id, tool)
        step = next(s for s in st.steps if s.step_id == step_id)
        observed.append((step_id, step.status))

    monkeypatch.setattr(executor_module, "mark_step_started", _wrap_started)

    caps = [_cap(1), _cap(2)]
    tsel = [
        _tsel(1, tool="web_search", arguments={"query": "a"}),
        _tsel(2, tool="search_knowledge_base", arguments={"query": "b"}),
    ]

    result = AgentExecutionLoop(executor=Executor()).run(
        plan, context=ctx, capability_selections=caps, tool_selections=tsel,
    )

    assert result.completed is True
    # Each step went pending -> running exactly once, in step order.
    assert observed == [(1, "running"), (2, "running")]
    assert [s.status for s in state.steps] == ["completed", "completed"]
    assert state.steps[0].output == "out-web_search"
    assert state.current_step == 2
    assert state.steps[0].tool == "web_search"


# ── 13: No parallel execution (one gate call per iteration) ─────────────────

def test_no_parallel_execution(monkeypatch):
    plan = _plan(
        _step(1, "web_search", tool="web_search", description="a"),
        _step(2, "knowledge", tool="search_knowledge_base", description="b"),
        _step(3, "memory", tool="remember_user_fact", description="c"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result(f"out-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)
    caps = [_cap(i) for i in range(1, 4)]
    tsel = [
        _tsel(1, tool="web_search", arguments={"query": "a"}),
        _tsel(2, tool="search_knowledge_base", arguments={"query": "b"}),
        _tsel(3, tool="remember_user_fact", arguments={"fact": "c"}),
    ]

    result = AgentExecutionLoop(executor=Executor()).run(
        plan, context=ctx, capability_selections=caps, tool_selections=tsel,
    )

    assert result.completed is True
    assert result.iterations == 3
    # Exactly one gate call per step, no duplicates, no fan-out.
    assert calls == [
        ("web_search", {"query": "a"}),
        ("search_knowledge_base", {"query": "b"}),
        ("remember_user_fact", {"fact": "c"}),
    ]


# ── 14: No retry / no replan after a step failure ────────────────────────────

def test_no_retry_no_replan(monkeypatch):
    plan = _plan(_step(1, "direct_answer", description="explain"))

    def _boom(**kw):
        raise RuntimeError("llm exploded")

    llm = MagicMock()
    llm.invoke.side_effect = _boom
    monkeypatch.setattr("app.agent.pipeline.executor.build_llm", lambda **kw: llm)
    ctx = _agent_ctx(plan.steps)

    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1)],
        tool_selections=[_tsel(1, tool=None, arguments={})],
    )

    assert result.completed is False
    assert result.iterations == 1
    assert result.stopped_reason == "step 1 failed"
    assert result.execution.status == "failed"
    # Exactly ONE LLM call: the failed step was NOT retried.
    assert llm.invoke.call_count == 1
    # No replan: the runner returned a bounded LoopResult, no recursion.
    assert hasattr(result, "execution")
    assert [r.step_id for r in result.execution.step_results] == [1]


# ── 15: Executor receives only approved selections ───────────────────────────

def test_executor_receives_only_approved_selections(monkeypatch):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "web_search", tool="web_search", description="latest release"),
    )
    calls = []

    def _gate(tool, args):
        calls.append((tool, args))
        return _gate_result(f"out-{tool}")

    _patch_gate(monkeypatch, _gate)
    ctx = _agent_ctx(plan.steps)
    args1 = {"fact": "Keep Python", "user_id": "u1", "project_id": "p1"}
    args2 = {"query": "latest release"}

    # Full approval: both selections reach the gate, in step order.
    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1), _cap(2)],
        tool_selections=[_tsel(1, tool="remember_user_fact", arguments=args1),
                         _tsel(2, tool="web_search", arguments=args2)],
    )
    assert result.completed is True
    assert calls == [("remember_user_fact", args1), ("web_search", args2)]

    # Step 2's capability denied: only step 1's approved selection reaches the
    # gate; the denied step is blocked before any handler runs.
    calls.clear()
    result = AgentExecutionLoop(executor=Executor()).run(
        plan,
        context=ctx,
        capability_selections=[_cap(1), _cap(2, allowed=False, reason="no web")],
        tool_selections=[_tsel(1, tool="remember_user_fact", arguments=args1),
                         _tsel(2, tool="web_search", arguments=args2)],
    )
    assert result.completed is False
    assert result.stopped_reason == "step 2 blocked"
    assert calls == [("remember_user_fact", args1)]