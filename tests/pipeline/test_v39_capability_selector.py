"""V3.9 Tool Selection & Capability Matching — hermetic tests.

Covers the 12 required cases:
  1.  Memory step → memory_v2 capability
  2.  Web step → sandboxing capability (alias + config availability)
  3.  Knowledge step → hybrid_retrieval capability
  4.  Document step → hybrid_retrieval capability
  5.  Coding step → sandboxing capability
  6.  Reasoning step → answer_generation capability
  7.  Direct answer step → answer_generation capability
  8.  Unsupported tool → rejected cleanly ("Capability is unavailable")
  9.  Unavailable capability → rejected cleanly ("Capability is unavailable")
  10. Source-policy restriction enforced (KB forbids web search)
  11. Multi-step plan selected step by step
  12. Selector never executes tools

No live LLM / API / database testing. Pure decision layer.
"""

from types import SimpleNamespace

from app.agent.pipeline.capabilities import CapabilitySelector, CapabilitySelection
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.source_policy import SourcePolicy, AnswerMode


# ── Helpers ─────────────────────────────────────────────────────────────────

WEB_AVAILABLE = {"web_search": True}


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


def _ctx(policy=None):
    return SimpleNamespace(source_policy=policy)


def _policy(policy: SourcePolicy) -> AnswerMode:
    return AnswerMode.from_policy(policy)


def _select(plan, ctx=None, availability=None) -> list[CapabilitySelection]:
    return CapabilitySelector().select(plan, context=ctx, tool_availability=availability)


# ── 1: Memory step ───────────────────────────────────────────────────────────

def test_memory_step_maps_to_memory_capability():
    plan = _plan(_step(1, "memory", tool="remember_user_fact"))

    selections = _select(plan, _ctx())

    assert len(selections) == 1
    sel = selections[0]
    assert sel.step_id == 1
    assert sel.capability == "memory_v2"
    assert sel.tool == "remember_user_fact"
    assert sel.allowed is True
    assert "memory_v2" in sel.reason


# ── 2: Web step ──────────────────────────────────────────────────────────────

def test_web_step_maps_to_sandboxing_capability():
    plan = _plan(_step(1, "web_search", tool="tavily_search"))

    selections = _select(plan, _ctx(), availability=WEB_AVAILABLE)

    assert len(selections) == 1
    sel = selections[0]
    assert sel.capability == "tool_sandboxing"
    assert sel.tool == "web_search"  # alias tavily_search → web_search
    assert sel.allowed is True

    # Without configuration the same step is rejected, not executed.
    unavailable = _select(
        plan,
        _ctx(),
        availability={"web_search": False},
    )
    assert unavailable[0].allowed is False
    assert "unavailable" in unavailable[0].reason


# ── 3: Knowledge step ────────────────────────────────────────────────────────

def test_knowledge_step_maps_to_hybrid_retrieval_capability():
    plan = _plan(_step(1, "knowledge"))

    sel = _select(plan, _ctx())[0]

    assert sel.capability == "hybrid_retrieval"
    assert sel.tool is None
    assert sel.allowed is True


# ── 4: Document step ─────────────────────────────────────────────────────────

def test_document_step_maps_to_hybrid_retrieval_capability():
    plan = _plan(_step(1, "document"))

    sel = _select(plan, _ctx())[0]

    assert sel.capability == "hybrid_retrieval"
    assert sel.tool is None
    assert sel.allowed is True


# ── 5: Coding step ───────────────────────────────────────────────────────────

def test_coding_step_maps_to_sandboxing_capability():
    plan = _plan(_step(1, "coding"))

    sel = _select(plan, _ctx())[0]

    assert sel.capability == "tool_sandboxing"
    assert sel.allowed is True

    # "python_interpreter" is advertised by the intent/planner but is NOT
    # registered in the tool gate — the selector must not trust the planner.
    rejected = _select(_plan(_step(1, "coding", tool="python_interpreter")), _ctx())[0]
    assert rejected.allowed is False
    assert rejected.reason == "Capability is unavailable"


# ── 6: Reasoning step ────────────────────────────────────────────────────────

def test_reasoning_step_maps_to_answer_generation_capability():
    plan = _plan(_step(1, "reasoning"))

    sel = _select(plan, _ctx())[0]

    assert sel.capability == "answer_generation"
    assert sel.tool is None
    assert sel.allowed is True


# ── 7: Direct answer step ────────────────────────────────────────────────────

def test_direct_answer_step_maps_to_answer_generation_capability():
    plan = _plan(_step(1, "direct_answer"))

    sel = _select(plan, _ctx())[0]

    assert sel.capability == "answer_generation"
    assert sel.allowed is True


# ── 8: Unsupported tool ──────────────────────────────────────────────────────

def test_unsupported_tool_rejected_cleanly():
    plan = _plan(_step(1, "memory", tool="some_nonexistent_tool"))

    sel = _select(plan, _ctx())[0]

    assert sel.allowed is False
    assert sel.reason == "Capability is unavailable"
    assert sel.capability == "memory_v2"


# ── 9: Unavailable capability (registry verify) ──────────────────────────────

def test_unavailable_capability_rejected_when_not_in_registry(monkeypatch):
    monkeypatch.setattr(
        "app.learning.architecture.capabilities.get",
        lambda cap_id: None,
    )
    plan = _plan(_step(1, "memory", tool="remember_user_fact"))

    sel = _select(plan, _ctx())[0]

    assert sel.allowed is False
    assert sel.reason == "Capability is unavailable"
    assert sel.capability == "memory_v2"


# ── 10: Source-policy restriction ────────────────────────────────────────────

def test_source_policy_restriction_enforced():
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact"),
        _step(2, "web_search", tool="tavily_search"),
        _step(3, "direct_answer"),
    )

    selections = _select(plan, _ctx(policy=_policy(SourcePolicy.KB)), availability=WEB_AVAILABLE)

    assert len(selections) == 3
    memory, web, direct = selections
    assert memory.allowed is True
    assert direct.allowed is True
    assert web.allowed is False
    assert "violates source policy" in web.reason
    assert web.capability == "tool_sandboxing"

    # Memory policy also forbids knowledge retrieval.
    kb_like = _select(
        _plan(_step(1, "knowledge")),
        _ctx(policy=_policy(SourcePolicy.MEMORY)),
    )[0]
    assert kb_like.allowed is False
    assert "violates source policy" in kb_like.reason

    # No policy / NONE policy impose no restriction.
    unrestricted = _select(
        plan,
        _ctx(policy=_policy(SourcePolicy.NONE)),
        availability=WEB_AVAILABLE,
    )
    assert all(s.allowed for s in unrestricted)


# ── 11: Multi-step plan selection ────────────────────────────────────────────

def test_multi_step_plan_selected_step_by_step():
    plan = _plan(
        _step(1, "memory", tool="remember_user_fact"),
        _step(2, "web_search", tool="tavily_search", deps=[1]),
        _step(3, "direct_answer", deps=[1, 2]),
    )

    selections = _select(plan, _ctx(), availability=WEB_AVAILABLE)

    assert [s.step_id for s in selections] == [1, 2, 3]
    assert [s.capability for s in selections] == [
        "memory_v2",
        "tool_sandboxing",
        "answer_generation",
    ]
    assert all(s.allowed for s in selections)


# ── 12: Selector never executes tools ────────────────────────────────────────

def test_selector_never_executes_tools(monkeypatch):
    calls: list = []

    def _explode(tool, args):
        calls.append((tool, args))
        raise AssertionError("selector must never execute tools")

    monkeypatch.setattr("app.agent.tool_gate.request_tool_execution", _explode)

    plan = _plan(
        _step(1, "memory", tool="remember_user_fact"),
        _step(2, "web_search", tool="tavily_search"),
    )
    selections = _select(plan, _ctx(), availability=WEB_AVAILABLE)

    assert calls == []
    assert all(s.allowed for s in selections)

    # Empty plans select nothing and still never execute.
    assert _select(_plan(), _ctx()) == []