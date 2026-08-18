"""V3.10 Execution Policy & Enforcement — hermetic tests.

Covers the 10 required cases:
  1.  Allowed capability → executes
  2.  Denied capability → blocked
  3.  Denied web search → Tavily never called
  4.  Denied memory → memory tool never called
  5.  Unknown/missing selection → fail closed (blocked)
  6.  Blocked step propagates to dependent step
  7.  Allowed unrelated steps still execute
  8.  Existing execution behavior remains intact (no selections passed)
  9.  Selector reason appears in StepResult
  10. No tool execution occurs inside the policy layer

Zero live API / DB / LLM calls — tool gate and LLM are patched.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agent.pipeline.capabilities import CapabilitySelector, CapabilitySelection
from app.agent.pipeline.executor import Executor
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.source_policy import AnswerMode, SourcePolicy


# ── Helpers ─────────────────────────────────────────────────────────────────

WEB_AVAILABLE = {"web_search": True}


@pytest.fixture
def executor():
    return Executor()


def _step(step_id, action, tool=None, deps=None) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        description=f"step {step_id}",
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


def _sel(step_id, capability, tool=None, allowed=True, reason="") -> CapabilitySelection:
    return CapabilitySelection(
        step_id=step_id,
        capability=capability,
        tool=tool,
        allowed=allowed,
        reason=reason,
    )


def _ctx() -> SimpleNamespace:
    """Pipeline-like context; knowledge steps resolve hermetically."""
    return SimpleNamespace(
        question="q",
        final_query="q",
        user_id="u1",
        project_id=None,
        session_id="s1",
        context=SimpleNamespace(
            knowledge_context="KB CONTENT",
            document_context="",
            web_context="",
        ),
    )


def _gate_result(result="tool result"):
    mock = MagicMock()
    mock.status = "executed"
    mock.result = result
    return mock


def _fake_llm(content="fake answer"):
    mock = MagicMock()
    response = MagicMock()
    response.content = content
    mock.invoke.return_value = response
    return mock


# ── 1: Allowed capability → executes ─────────────────────────────────────────

def test_allowed_capability_executes(executor):
    plan = _plan(_step(1, "knowledge"))
    selections = [_sel(1, "hybrid_retrieval")]

    with patch("app.agent.pipeline.executor.request_tool_execution") as gate:
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert result.status == "completed"
    assert result.step_results[0].status == "completed"
    assert result.outputs[1] == "KB CONTENT"
    gate.assert_not_called()  # knowledge step resolved from context, not the gate


# ── 2: Denied capability → blocked ───────────────────────────────────────────

def test_denied_capability_blocked(executor):
    plan = _plan(_step(1, "memory", tool="remember_user_fact"))
    selections = [_sel(1, "memory_v2", tool="remember_user_fact",
                       allowed=False, reason="memory is unavailable under policy")]

    with patch("app.agent.pipeline.executor.request_tool_execution") as gate:
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert result.status == "blocked"
    step = result.step_results[0]
    assert step.status == "blocked"
    assert step.output == ""
    assert step.error == "memory is unavailable under policy"
    gate.assert_not_called()


# ── 3: Denied web search → Tavily never called ───────────────────────────────

def test_denied_web_search_tavily_never_called(executor, monkeypatch):
    plan = _plan(_step(1, "web_search", tool="tavily_search"))
    selections = [_sel(1, "tool_sandboxing", tool="web_search",
                       allowed=False, reason="web search violates source policy kb")]

    gate_calls: list = []
    tavily_calls: list = []

    def _gate(tool, args):
        gate_calls.append(tool)
        raise AssertionError("denied step must never reach the tool gate")

    monkeypatch.setattr("app.agent.pipeline.executor.request_tool_execution", _gate)
    monkeypatch.setattr(
        "app.agent.tool_impls.web_search_impl",
        lambda **kw: tavily_calls.append(kw),
    )

    result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert result.step_results[0].status == "blocked"
    assert gate_calls == []
    assert tavily_calls == []


# ── 4: Denied memory → memory tool never called ──────────────────────────────

def test_denied_memory_memory_tool_never_called(executor, monkeypatch):
    plan = _plan(_step(1, "memory", tool="remember_user_fact"))
    selections = [_sel(1, "memory_v2", tool="remember_user_fact",
                       allowed=False, reason="memory denied for test")]

    gate_calls: list = []
    impl_calls: list = []

    def _gate(tool, args):
        gate_calls.append(tool)
        raise AssertionError("denied step must never reach the tool gate")

    monkeypatch.setattr("app.agent.pipeline.executor.request_tool_execution", _gate)
    monkeypatch.setattr(
        "app.agent.tool_impls.remember_user_fact_impl",
        lambda **kw: impl_calls.append(kw),
    )

    result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert result.step_results[0].status == "blocked"
    assert gate_calls == []
    assert impl_calls == []


# ── 5: Unknown/missing selection → fail closed ───────────────────────────────

def test_missing_selection_fails_closed(executor):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact"),
        _step(2, "knowledge"),
    )
    # Only step 1 has a selection; step 2 is unselected → fail closed.
    selections = [_sel(1, "memory_v2", tool="remember_user_fact")]

    with patch("app.agent.pipeline.executor.request_tool_execution",
               return_value=_gate_result("saved")) as gate:
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert result.step_results[0].status == "completed"  # selected + allowed
    assert gate.call_args[0][0] == "remember_user_fact"

    blocked = result.step_results[1]
    assert blocked.status == "blocked"
    assert "no capability selection" in blocked.error

    # An entirely empty selection list blocks every step as well.
    result = executor.execute(plan, context=_ctx(), capability_selections=[])
    assert all(s.status == "blocked" for s in result.step_results)


# ── 6: Blocked step propagates to dependent step ─────────────────────────────

def test_blocked_step_propagates_to_dependent(executor):
    plan = _plan(
        _step(1, "web_search", tool="tavily_search"),
        _step(2, "direct_answer", deps=[1]),
    )
    selections = [
        _sel(1, "tool_sandboxing", tool="web_search", allowed=False,
             reason="web search violations denied at selection"),
        _sel(2, "answer_generation"),
    ]
    llm = _fake_llm()

    with patch("app.agent.pipeline.executor.build_llm", return_value=llm):
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert [s.status for s in result.step_results] == ["blocked", "blocked"]
    assert "web search violations denied at selection" in result.step_results[0].error
    assert "dependency" in result.step_results[1].error
    llm.invoke.assert_not_called()


# ── 7: Allowed unrelated steps still execute ─────────────────────────────────

def test_allowed_unrelated_steps_still_execute(executor):
    plan = _plan(
        _step(1, "knowledge"),
        _step(2, "web_search", tool="tavily_search"),
        _step(3, "direct_answer"),
    )
    selections = [
        _sel(1, "hybrid_retrieval"),
        _sel(2, "tool_sandboxing", tool="web_search", allowed=False,
             reason="denied step two"),
        _sel(3, "answer_generation"),
    ]
    llm = _fake_llm(content="final")

    with patch("app.agent.pipeline.executor.build_llm", return_value=llm):
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert result.status == "partial"
    assert [s.status for s in result.step_results] == ["completed", "blocked", "completed"]
    assert result.outputs[1] == "KB CONTENT"
    assert result.outputs[3] == "final"


# ── 8: Existing behavior intact without selections ───────────────────────────

def test_existing_behavior_remains_intact_without_selections(executor):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact"),
        _step(2, "direct_answer"),
    )
    llm = _fake_llm(content="synthesized")

    with patch("app.agent.pipeline.executor.request_tool_execution",
               return_value=_gate_result("saved")) as gate, \
         patch("app.agent.pipeline.executor.build_llm", return_value=llm):
        result = executor.execute(plan, context=_ctx())  # no selections → no enforcement

    assert result.status == "completed"
    assert [s.status for s in result.step_results] == ["completed", "completed"]
    gate.assert_called_once()
    assert gate.call_args[0][0] == "remember_user_fact"
    llm.invoke.assert_called_once()


# ── 9: Selector reason appears in StepResult ─────────────────────────────────

def test_selector_reason_appears_in_step_result(executor):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact"),
        _step(2, "web_search", tool="tavily_search"),
    )
    ctx = SimpleNamespace(
        source_policy=AnswerMode.from_policy(SourcePolicy.KB),
    )
    selections = CapabilitySelector().select(
        plan, context=ctx, tool_availability=WEB_AVAILABLE
    )

    assert selections[0].allowed is True
    assert selections[1].allowed is False

    with patch("app.agent.pipeline.executor.request_tool_execution",
               return_value=_gate_result("saved")):
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    blocked = result.step_results[1]
    assert blocked.status == "blocked"
    assert blocked.error == selections[1].reason
    assert "violates source policy" in blocked.error


# ── 10: No tool execution inside the policy layer ────────────────────────────

def test_no_tool_execution_inside_policy_layer(executor, monkeypatch):
    plan = _plan(
        _step(1, "web_search", tool="tavily_search"),
        _step(2, "knowledge"),
        _step(3, "direct_answer"),
    )
    ctx_policy = SimpleNamespace(
        source_policy=AnswerMode.from_policy(SourcePolicy.MEMORY),  # denies web + knowledge
    )
    gate_calls: list = []

    def _gate(tool, args):
        gate_calls.append(tool)
        raise AssertionError("policy layer must never execute tools")

    monkeypatch.setattr("app.agent.pipeline.executor.request_tool_execution", _gate)

    # Step 1: selection itself — pure, no I/O.
    selections = CapabilitySelector().select(plan, context=ctx_policy, tool_availability=WEB_AVAILABLE)
    assert gate_calls == []

    # Steps 2-3: enforcement — denied steps blocked before any handler runs.
    llm = _fake_llm(content="final")
    with patch("app.agent.pipeline.executor.build_llm", return_value=llm):
        result = executor.execute(plan, context=_ctx(), capability_selections=selections)

    assert [s.status for s in result.step_results] == ["blocked", "blocked", "completed"]
    assert gate_calls == []  # no tool reached the gate anywhere in the policy path