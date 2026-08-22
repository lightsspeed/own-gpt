"""Hermetic unit tests for V3.3 Plan Executor (app/agent/pipeline/executor.py).

All tests are fully mocked — zero live API, DB, or LLM calls.

Test coverage:
  1.  Simple direct_answer plan completes
  2.  Memory step dispatches through mock tool_gate
  3.  Web search step dispatches through mock tool_gate
  4.  Knowledge step dispatches through mock tool_gate
  5.  Multi-step dependency ordering (step 3 waits for 1 and 2)
  6.  Dependency failure → BLOCKED (step 3 blocked when step 2 fails)
  7.  Unknown action → FAILED
  8.  Tool handler raises exception → StepResult.status == "failed"
  9.  Dependency outputs passed into subsequent steps
  10. Planner remains pure (planner itself never invokes a tool)
  11. Backward compatibility: Planner.plan(intent, route) -> AnswerMode still works
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from app.agent.pipeline.executor import Executor, ExecutionResult, StepResult
from app.agent.pipeline.planner import Plan, PlanStep, Planner
from app.agent.pipeline.intent import Intent, IntentResult
from app.agent.pipeline.router import RequestRouter, RouterResult, RouteDecision
from app.agent.pipeline.source_policy import AnswerMode, SourcePolicy


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def simple_general_plan():
    return Plan(
        goal="Answer greeting",
        steps=[
            PlanStep(step_id=1, description="Say hello", action="direct_answer",
                     dependencies=[], expected_output="greeting text"),
        ],
        requires_tools=False,
        estimated_complexity="simple",
    )


@pytest.fixture
def memory_plan():
    return Plan(
        goal="Store user memory",
        steps=[
            PlanStep(step_id=1, description="Remember favorite color is blue",
                     action="memory", tool="remember_user_fact",
                     dependencies=[], expected_output="Memory stored"),
        ],
        requires_tools=True,
        estimated_complexity="simple",
    )


@pytest.fixture
def web_plan():
    return Plan(
        goal="Search web for latest Kubernetes release",
        steps=[
            PlanStep(step_id=1, description="Search for latest Kubernetes release",
                     action="web_search", tool="tavily_search",
                     dependencies=[], expected_output="Search results"),
        ],
        requires_tools=True,
        estimated_complexity="medium",
    )


@pytest.fixture
def knowledge_plan():
    return Plan(
        goal="Search knowledge base",
        steps=[
            PlanStep(step_id=1, description="Find RBAC info in knowledge base",
                     action="knowledge", tool=None,
                     dependencies=[], expected_output="KB results"),
        ],
        requires_tools=False,
        estimated_complexity="simple",
    )


@pytest.fixture
def multi_step_plan():
    """Steps 1 and 2 are independent; step 3 depends on both."""
    return Plan(
        goal="Multi-step plan",
        steps=[
            PlanStep(step_id=1, description="Step 1: Memory store",
                     action="memory", tool="remember_user_fact",
                     dependencies=[], expected_output="Memory stored"),
            PlanStep(step_id=2, description="Step 2: Web search",
                     action="web_search", tool="tavily_search",
                     dependencies=[], expected_output="Search results"),
            PlanStep(step_id=3, description="Step 3: Synthesize answer",
                     action="direct_answer",
                     dependencies=[1, 2], expected_output="Final answer"),
        ],
        requires_tools=True,
        estimated_complexity="complex",
    )


# ── Test 1: Simple direct_answer plan completes ───────────────────────────────

class TestSimpleDirectAnswer:
    def test_simple_plan_completes(self, executor, simple_general_plan, monkeypatch):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Hello! How can I help you today?"
        mock_llm.invoke.return_value = mock_response

        with patch("app.agent.pipeline.executor.build_llm", return_value=mock_llm):
            result = executor.execute(simple_general_plan, context=None)

        assert result.status == "completed"
        assert len(result.step_results) == 1
        assert result.step_results[0].status == "completed"
        assert result.final_output == "Hello! How can I help you today?"
        assert 1 in result.outputs


# ── Test 2: Memory step dispatches through mock tool_gate ─────────────────────

class TestMemoryStep:
    def test_memory_step_dispatches_to_tool_gate(self, executor, memory_plan):
        mock_execution = MagicMock()
        mock_execution.status = "executed"
        mock_execution.result = "Successfully saved fact to long-term memory (abc123): 'favorite color is blue'"

        with patch("app.agent.pipeline.executor.request_tool_execution",
                   return_value=mock_execution) as mock_gate:
            result = executor.execute(memory_plan, context=None)

        assert result.status == "completed"
        assert result.step_results[0].status == "completed"
        # Gate was called with memory tool name
        call_args = mock_gate.call_args
        assert call_args[0][0] == "remember_user_fact"


# ── Test 3: Web search step dispatches through mock tool_gate ─────────────────

class TestWebSearchStep:
    def test_web_search_step_dispatches_to_tool_gate(self, executor, web_plan):
        mock_execution = MagicMock()
        mock_execution.status = "executed"
        mock_execution.result = "Web Search Results for 'latest Kubernetes':\n\n[1] Kubernetes v1.32 released..."

        with patch("app.agent.pipeline.executor.request_tool_execution",
                   return_value=mock_execution) as mock_gate:
            result = executor.execute(web_plan, context=None)

        assert result.status == "completed"
        assert result.step_results[0].status == "completed"
        call_args = mock_gate.call_args
        assert call_args[0][0] == "web_search"
        assert "query" in call_args[0][1]


# ── Test 4: Knowledge step dispatches through mock tool_gate ──────────────────

class TestKnowledgeStep:
    def test_knowledge_step_dispatches_to_tool_gate(self, executor, knowledge_plan):
        mock_execution = MagicMock()
        mock_execution.status = "executed"
        mock_execution.result = "Found information about RBAC in the knowledge base."

        with patch("app.agent.pipeline.executor.request_tool_execution",
                   return_value=mock_execution) as mock_gate:
            result = executor.execute(knowledge_plan, context=None)

        assert result.status == "completed"
        call_args = mock_gate.call_args
        assert call_args[0][0] == "search_knowledge_base"


# ── Test 5: Multi-step dependency ordering ────────────────────────────────────

class TestMultiStepOrdering:
    def test_step3_executes_after_1_and_2(self, executor, multi_step_plan):
        """Step 3 must only execute after steps 1 and 2 have completed."""
        execution_order = []

        mock_execution = MagicMock()
        mock_execution.status = "executed"
        mock_execution.result = "tool result"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Final synthesized answer"
        mock_llm.invoke.return_value = mock_response

        def mock_gate(tool_name, args):
            execution_order.append(tool_name)
            return mock_execution

        with patch("app.agent.pipeline.executor.request_tool_execution", side_effect=mock_gate), \
             patch("app.agent.pipeline.executor.build_llm", return_value=mock_llm):
            result = executor.execute(multi_step_plan, context=None)

        # All 3 steps must complete
        assert result.status == "completed"
        assert len(result.step_results) == 3
        assert all(r.status == "completed" for r in result.step_results)

        # Step 1 (memory) and Step 2 (web_search) ran through tool_gate.
        # The tool_gate impl name for web is "web_search", not "tavily_search".
        assert "remember_user_fact" in execution_order
        assert "web_search" in execution_order

        # Step 3's result is available in outputs
        assert 3 in result.outputs


# ── Test 6: Dependency failure → BLOCKED ─────────────────────────────────────

class TestDependencyFailureBlocking:
    def test_step3_blocked_when_step2_fails(self, executor, multi_step_plan):
        """When step 2 fails, step 3 must be BLOCKED (not executed)."""
        call_count = {"count": 0}

        mock_fail_execution = MagicMock()
        mock_fail_execution.status = "failed"
        mock_fail_execution.result = ""
        mock_fail_execution.error = "Tavily API unavailable"

        mock_ok_execution = MagicMock()
        mock_ok_execution.status = "executed"
        mock_ok_execution.result = "Memory stored successfully"

        def mock_gate(tool_name, args):
            call_count["count"] += 1
            if tool_name == "web_search":
                # Return an execution whose status is "failed" to trigger raise in handler
                return mock_fail_execution
            return mock_ok_execution

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Should not appear"
        mock_llm.invoke.return_value = mock_response

        with patch("app.agent.pipeline.executor.request_tool_execution", side_effect=mock_gate), \
             patch("app.agent.pipeline.executor.build_llm", return_value=mock_llm):
            result = executor.execute(multi_step_plan, context=None)

        # Overall status must be partial (step 1 succeeded, step 2 failed, step 3 blocked)
        assert result.status == "partial"

        step_map = {r.step_id: r for r in result.step_results}
        assert step_map[1].status == "completed"
        assert step_map[2].status == "failed"
        assert step_map[3].status == "blocked"

        # Step 3 must not appear in outputs (was never executed)
        assert 3 not in result.outputs


# ── Test 7: Unknown action → FAILED ──────────────────────────────────────────

class TestUnknownAction:
    def test_unknown_action_fails_step(self, executor):
        plan = Plan(
            goal="Test unknown action",
            steps=[
                PlanStep(step_id=1, description="Do something invalid",
                         action="something_totally_invalid",
                         dependencies=[], expected_output="never"),
            ],
            requires_tools=False,
            estimated_complexity="simple",
        )

        result = executor.execute(plan, context=None)

        assert result.step_results[0].status == "failed"
        assert "Unknown action" in result.step_results[0].error


# ── Test 8: Tool handler exception → step failed ─────────────────────────────

class TestToolHandlerException:
    def test_tool_exception_marks_step_failed(self, executor, web_plan):
        def mock_gate_raises(tool_name, args):
            raise RuntimeError("Tavily connection refused")

        with patch("app.agent.pipeline.executor.request_tool_execution",
                   side_effect=mock_gate_raises):
            result = executor.execute(web_plan, context=None)

        assert result.step_results[0].status == "failed"
        assert "Tavily connection refused" in result.step_results[0].error
        assert result.status == "failed"


# ── Test 9: Dependency outputs passed into subsequent steps ───────────────────

class TestDependencyOutputPropagation:
    def test_step3_receives_dependency_outputs(self, executor, multi_step_plan):
        """Verify step 3 receives outputs from steps 1 and 2 as its context."""
        received_calls = []

        mock_execution = MagicMock()
        mock_execution.status = "executed"
        mock_execution.result = "dependency output content"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Final answer with context"
        mock_llm.invoke.return_value = mock_response

        def capture_llm_invoke(messages):
            # Capture the system message to verify dep context was passed
            for m in messages:
                received_calls.append(m.content)
            return mock_response

        mock_llm.invoke.side_effect = capture_llm_invoke

        with patch("app.agent.pipeline.executor.request_tool_execution",
                   return_value=mock_execution), \
             patch("app.agent.pipeline.executor.build_llm", return_value=mock_llm):
            result = executor.execute(multi_step_plan, context=None)

        # Step 3 must have received the outputs from steps 1 and 2
        # The LLM system prompt for step 3 must include dependency context
        combined = " ".join(received_calls)
        assert "[Step 1]" in combined or "dependency output content" in combined
        assert result.status == "completed"


# ── Test 10: Planner remains pure — never invokes tools ───────────────────────

class TestPlannerPurity:
    def test_planner_create_plan_does_not_call_tool_gate(self):
        """Planner.create_plan must never call tool_gate or tool_impls."""
        planner = Planner()
        intent_res = IntentResult(
            intent=Intent.MULTI_INTENT,
            confidence=0.95,
            matched_rule="MULTI_INTENT_COMBINED",
            candidate_tools=["tavily_search", "remember_user_fact"],
            requires_tool=True,
        )
        router = RequestRouter()
        route_res = router.route(intent_res)

        with patch("app.agent.pipeline.executor.request_tool_execution") as mock_gate:
            plan = planner.create_plan(
                "remember my preference and search the web", intent_res, route_res
            )

        # Tool gate must NOT have been called by the planner
        mock_gate.assert_not_called()

        # Plan must have been created with steps
        assert plan is not None
        assert len(plan.steps) > 0


# ── Test 11: Backward compatibility ──────────────────────────────────────────

class TestBackwardCompatibility:
    def test_planner_plan_still_returns_answermode(self):
        """Planner.plan(intent, route) must still return AnswerMode."""
        planner = Planner()
        router = RequestRouter()

        intent_res = IntentResult(intent=Intent.KNOWLEDGE, confidence=0.95)
        route_res = router.route(intent_res)

        mode = planner.plan(intent_res, route_res)

        assert isinstance(mode, AnswerMode)
        assert mode.policy == SourcePolicy.KB
        assert mode.contract.requires_evidence is True

    def test_empty_plan_returns_completed(self):
        """Executing an empty plan should complete safely."""
        executor = Executor()
        empty_plan = Plan(goal="Empty plan", steps=[], requires_tools=False)

        result = executor.execute(empty_plan, context=None)

        assert result.status == "completed"
        assert result.final_output == "No steps to execute."
        assert result.step_results == []
