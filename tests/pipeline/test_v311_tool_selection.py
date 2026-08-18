"""V3.11 Tool Selection & Argument Construction — hermetic tests.

Covers the 12 required cases:
  1.  Memory tool selection
  2.  Web tool + query construction
  3.  Knowledge tool + project ID
  4.  Document tool
  5.  Direct-answer / no-tool
  6.  Denied capability → denied tool
  7.  Unknown tool
  8.  Missing required argument
  9.  Malformed arguments
  10. Multi-step selection
  11. Executor receives selected arguments
  12. Tool selector never executes tools

Zero live API / DB / LLM calls.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.executor import Executor
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.tool_selection import ToolSelector, ToolSelection


# ── Helpers ─────────────────────────────────────────────────────────────────

@pytest.fixture
def executor():
    return Executor()


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


def _ctx(question="", user_id="u1", project_id="p1", session_id="s1") -> SimpleNamespace:
    return SimpleNamespace(
        question=question,
        final_query="",
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
    )


def _select(plan, ctx=None, caps=None) -> list[ToolSelection]:
    return ToolSelector().select(plan, context=ctx, capability_selections=caps)


# ── 1: Memory tool selection ─────────────────────────────────────────────────

def test_memory_tool_selection():
    plan = _plan(_step(1, "memory", description="Remember that I like blue"))
    caps = [_cap(1)]

    tsel = _select(plan, _ctx(), caps)[0]

    assert tsel.step_id == 1
    assert tsel.allowed is True
    assert tsel.tool == "remember_user_fact"
    assert tsel.arguments["fact"] == "Remember that I like blue"
    assert tsel.arguments["user_id"] == "u1"
    assert tsel.arguments["project_id"] == "p1"

    # remember_session_fact is honored when the plan requests it.
    plan = _plan(_step(1, "memory", tool="remember_session_fact",
                       description="Remember that I like blue"))
    tsel = _select(plan, _ctx(), [_cap(1)])[0]
    assert tsel.tool == "remember_session_fact"
    assert tsel.arguments["session_id"] == "s1"


# ── 2: Web tool + query construction ─────────────────────────────────────────

def test_web_tool_query_construction():
    plan = _plan(_step(1, "web_search", tool="tavily_search",
                       description="latest Kubernetes release"))
    caps = [_cap(1, tool="web_search")]

    tsel = _select(plan, _ctx(), caps)[0]

    assert tsel.allowed is True
    assert tsel.tool == "web_search"  # alias tavily_search → web_search
    assert tsel.arguments == {"query": "latest Kubernetes release"}

    # Rewritten query takes precedence when present.
    ctx = _ctx()
    ctx.final_query = "rewritten query"
    tsel = _select(plan, ctx, caps)[0]
    assert tsel.arguments == {"query": "rewritten query"}


# ── 3: Knowledge tool + project ID ───────────────────────────────────────────

def test_knowledge_tool_project_id():
    plan = _plan(_step(1, "knowledge", description="What is RBAC?"))
    caps = [_cap(1)]

    tsel = _select(plan, _ctx(project_id="proj-42"), caps)[0]

    assert tsel.allowed is True
    assert tsel.tool == "search_knowledge_base"
    assert tsel.arguments == {"query": "What is RBAC?", "project_id": "proj-42"}

    # No project → empty project_id (matches the executor contract).
    tsel = _select(plan, _ctx(project_id=None), caps)[0]
    assert tsel.arguments == {"query": "What is RBAC?", "project_id": ""}


# ── 4: Document tool ─────────────────────────────────────────────────────────

def test_document_tool():
    plan = _plan(_step(1, "document", description="Summarize the PDF"))
    caps = [_cap(1)]

    tsel = _select(plan, _ctx(), caps)[0]

    assert tsel.allowed is True
    assert tsel.tool == "search_knowledge_base"
    assert tsel.arguments["query"] == "Summarize the PDF"
    assert tsel.arguments["project_id"] == "p1"


# ── 5: Direct-answer / no-tool ───────────────────────────────────────────────

def test_direct_answer_no_tool():
    plan = _plan(
        _step(1, "direct_answer"),
        _step(2, "reasoning"),
        _step(3, "coding"),
    )
    caps = [_cap(1), _cap(2), _cap(3)]

    selections = _select(plan, _ctx(), caps)

    for tsel in selections:
        assert tsel.allowed is True
        assert tsel.tool is None
        assert tsel.arguments == {}

    # No-tool actions reject requests for tools.
    plan = _plan(_step(1, "direct_answer", tool="remember_user_fact"))
    tsel = _select(plan, _ctx(), [_cap(1)])[0]
    assert tsel.allowed is False
    assert "does not use a tool" in tsel.reason


# ── 6: Denied capability → denied tool ───────────────────────────────────────

def test_denied_capability_denied_tool():
    plan = _plan(_step(1, "web_search", tool="tavily_search"))
    caps = [_cap(1, allowed=False, reason="web search violates source policy kb")]

    tsel = _select(plan, _ctx(), caps)[0]

    assert tsel.allowed is False
    assert tsel.tool is None
    assert tsel.arguments == {}
    assert tsel.reason == "capability denied: web search violates source policy kb"

    # Missing capability selection also fails closed.
    tsel = _select(plan, _ctx(), caps=[])[0]
    assert tsel.allowed is False
    assert "no capability selection" in tsel.reason


# ── 7: Unknown tool ──────────────────────────────────────────────────────────

def test_unknown_tool():
    plan = _plan(_step(1, "memory", tool="some_nonexistent_tool"))
    caps = [_cap(1)]

    tsel = _select(plan, _ctx(), caps)[0]

    assert tsel.allowed is False
    assert tsel.reason == "tool 'some_nonexistent_tool' is not registered"

    # A registered tool on the wrong action is rejected as well.
    plan = _plan(_step(1, "knowledge", tool="web_search"))
    tsel = _select(plan, _ctx(), [_cap(1)])[0]
    assert tsel.allowed is False
    assert "not valid for action 'knowledge'" in tsel.reason


# ── 8: Missing required argument ─────────────────────────────────────────────

def test_missing_required_argument():
    plan = _plan(_step(1, "memory", tool="remember_session_fact",
                       description="Remember that I like blue"))
    ctx = _ctx(session_id=None)

    tsel = _select(plan, ctx, [_cap(1)])[0]

    assert tsel.allowed is False
    assert tsel.reason == "missing required argument 'session_id'"

    # Empty context → fact cannot be constructed.
    plan = _plan(_step(1, "memory", description=""))
    tsel = _select(plan, _ctx(question=""), [_cap(1)])[0]
    assert tsel.allowed is False
    assert tsel.reason == "missing required argument 'fact'"


# ── 9: Malformed arguments ───────────────────────────────────────────────────

def test_malformed_arguments():
    plan = _plan(_step(1, "web_search", tool="tavily_search"))

    # Non-string question cannot produce a valid query.
    tsel = _select(plan, _ctx(question=12345), [_cap(1)])[0]
    assert tsel.allowed is False
    assert tsel.reason == "invalid argument 'query': must be a string"

    # Whitespace-only query is rejected (empty after strip).
    tsel = _select(plan, _ctx(question="   "), [_cap(1)])[0]
    assert tsel.allowed is False
    assert tsel.reason == "missing required argument 'query'"


# ── 10: Multi-step selection ─────────────────────────────────────────────────

def test_multi_step_selection():
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "web_search", tool="tavily_search", description="latest release", deps=[1]),
        _step(3, "direct_answer", deps=[1, 2]),
    )
    caps = [_cap(1), _cap(2), _cap(3)]

    selections = _select(plan, _ctx(), caps)

    assert [s.step_id for s in selections] == [1, 2, 3]
    assert [s.tool for s in selections] == ["remember_user_fact", "web_search", None]
    assert all(s.allowed for s in selections)
    assert selections[0].arguments["fact"] == "Keep Python"
    assert selections[1].arguments["query"] == "latest release"
    assert selections[2].arguments == {}


# ── 11: Executor receives selected arguments ─────────────────────────────────

def test_executor_receives_selected_arguments(executor):
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "web_search", tool="tavily_search", description="latest release"),
    )
    ctx = _ctx()
    caps = [_cap(1), _cap(2)]
    tool_selections = ToolSelector().select(plan, context=ctx, capability_selections=caps)

    calls: list = []

    def _gate(tool, args):
        calls.append((tool, args))
        mock = MagicMock()
        mock.status = "executed"
        mock.result = "tool result"
        return mock

    with patch("app.agent.pipeline.executor.request_tool_execution", side_effect=_gate):
        result = executor.execute(
            plan,
            context=ctx,
            capability_selections=caps,
            tool_selections=tool_selections,
        )

    assert result.status == "completed"
    assert all(s.status == "completed" for s in result.step_results)

    # The gate received EXACTLY the validated selections, in step order.
    assert calls[0][0] == tool_selections[0].tool == "remember_user_fact"
    assert calls[0][1] == tool_selections[0].arguments
    assert calls[1][0] == tool_selections[1].tool == "web_search"
    assert calls[1][1] == tool_selections[1].arguments

    # A tool-denied step never reaches the gate.
    denied_plan = _plan(_step(1, "web_search", tool="tavily_search"))
    denied_tsel = ToolSelector().select(
        denied_plan, context=_ctx(), capability_selections=[_cap(1, allowed=False, reason="nope")]
    )
    assert denied_tsel[0].allowed is False
    calls.clear()
    with patch("app.agent.pipeline.executor.request_tool_execution", side_effect=_gate):
        result = executor.execute(
            denied_plan,
            context=_ctx(),
            capability_selections=[_cap(1, allowed=False, reason="nope")],
            tool_selections=denied_tsel,
        )
    assert result.step_results[0].status == "blocked"
    assert calls == []


# ── 12: Tool selector never executes tools ───────────────────────────────────

def test_tool_selector_never_executes_tools(monkeypatch):
    calls: list = []

    def _explode(tool, args):
        calls.append((tool, args))
        raise AssertionError("tool selector must never execute tools")

    monkeypatch.setattr("app.agent.pipeline.executor.request_tool_execution", _explode)
    monkeypatch.setattr("app.agent.tool_gate.request_tool_execution", _explode)

    plan = _plan(
        _step(1, "memory", tool="remember_user_fact", description="Keep Python"),
        _step(2, "web_search", tool="tavily_search", description="latest release"),
    )
    caps = [_cap(1), _cap(2)]

    selections = _select(plan, _ctx(), caps)

    assert calls == []
    assert all(s.allowed for s in selections)

    # Empty plans select nothing and still never execute.
    assert _select(_plan(), _ctx(), caps=[]) == []