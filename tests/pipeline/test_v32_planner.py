"""Hermetic unit tests for V3.2 Agent Planner (app/agent/pipeline/planner.py).

Covers:
- Plan & PlanStep model definitions
- Simple requests (single step, simple complexity)
- Memory requests (memory action, candidate tools)
- Knowledge / Document requests (knowledge action)
- Web search requests (web_search action, tavily_search tool)
- Multi-intent requests (ordered multi-step plans with explicit dependencies)
- Step dependency graph ordering
- Defensive recovery from invalid / malformed LLM outputs
- Planner fallback to default safe plan
- 100% backward compatibility of Planner.plan(intent, route) -> AnswerMode
"""

import pytest
from unittest.mock import MagicMock
from app.agent.pipeline.planner import Planner, Plan, PlanStep
from app.agent.pipeline.intent import Intent, IntentResult
from app.agent.pipeline.router import RequestRouter, RouteDecision, RouterResult
from app.agent.pipeline.source_policy import AnswerMode, SourcePolicy


@pytest.fixture
def planner():
    return Planner()


@pytest.fixture
def router():
    return RequestRouter()


class TestV32PlannerSingleStepRequests:
    def test_simple_general_request_plan(self, planner, router):
        intent_res = IntentResult(
            intent=Intent.GENERAL, confidence=0.95, matched_rule="GENERAL_CHAT"
        )
        route_res = router.route(intent_res)
        plan = planner.create_plan("hello good morning", intent_res, route_res)

        assert plan.requires_tools is False
        assert plan.estimated_complexity == "simple"
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "direct_answer"
        assert plan.steps[0].dependencies == []

    def test_memory_request_plan(self, planner, router):
        intent_res = IntentResult(
            intent=Intent.MEMORY,
            confidence=0.95,
            matched_rule="MEMORY_FACTS",
            candidate_tools=["remember_user_fact"],
            requires_tool=False,
        )
        route_res = router.route(intent_res)
        plan = planner.create_plan("remember my favorite color is blue", intent_res, route_res)

        assert plan.estimated_complexity == "simple"
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "memory"
        assert plan.steps[0].tool == "remember_user_fact"

    def test_knowledge_request_plan(self, planner, router):
        intent_res = IntentResult(
            intent=Intent.KNOWLEDGE, confidence=0.95, matched_rule="KNOWLEDGE_EXPLAIN"
        )
        route_res = router.route(intent_res)
        plan = planner.create_plan("what is Kubernetes RBAC?", intent_res, route_res)

        assert plan.estimated_complexity == "simple"
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "knowledge"

    def test_web_request_plan(self, planner, router):
        intent_res = IntentResult(
            intent=Intent.WEB,
            confidence=0.95,
            matched_rule="WEB_SEARCH",
            candidate_tools=["tavily_search"],
            requires_tool=True,
        )
        route_res = router.route(intent_res)
        plan = planner.create_plan("what is the latest news on AI today?", intent_res, route_res)

        assert plan.requires_tools is True
        assert plan.estimated_complexity == "medium"
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "web_search"
        assert plan.steps[0].tool == "tavily_search"


class TestV32PlannerMultiIntentAndDependencies:
    def test_multi_intent_memory_and_web_plan(self, planner, router):
        intent_res = IntentResult(
            intent=Intent.MULTI_INTENT,
            confidence=0.95,
            matched_rule="MULTI_INTENT_COMBINED",
            candidate_tools=["tavily_search", "remember_user_fact"],
            requires_tool=True,
        )
        route_res = router.route(intent_res)
        plan = planner.create_plan(
            "remember my preference and search the web for latest Kubernetes releases",
            intent_res,
            route_res,
        )

        assert plan.requires_tools is True
        assert plan.estimated_complexity == "complex"
        assert len(plan.steps) == 3

        # Step 1: Memory store
        assert plan.steps[0].step_id == 1
        assert plan.steps[0].action == "memory"
        assert plan.steps[0].dependencies == []

        # Step 2: Web search (depends on step 1)
        assert plan.steps[1].step_id == 2
        assert plan.steps[1].action == "web_search"
        assert plan.steps[1].dependencies == [1]

        # Step 3: Synthesis (depends on steps 1 and 2)
        assert plan.steps[2].step_id == 3
        assert plan.steps[2].action == "direct_answer"
        assert plan.steps[2].dependencies == [1, 2]

    def test_multi_intent_document_and_coding_plan(self, planner, router):
        intent_res = IntentResult(
            intent=Intent.MULTI_INTENT,
            confidence=0.95,
            matched_rule="MULTI_INTENT_COMBINED",
            candidate_tools=["python_interpreter"],
            requires_tool=True,
        )
        route_res = router.route(intent_res)
        plan = planner.create_plan(
            "read the PDF document and write python code to parse it",
            intent_res,
            route_res,
        )

        assert plan.estimated_complexity == "complex"
        assert len(plan.steps) == 2
        assert plan.steps[0].action == "knowledge"
        assert plan.steps[1].action == "coding"
        assert plan.steps[1].dependencies == [1]


class TestV32PlannerLLMFallbackAndErrorRecovery:
    def test_llm_planner_valid_json(self, monkeypatch):
        planner = Planner()

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '''{
            "goal": "Complex query resolution",
            "estimated_complexity": "complex",
            "requires_tools": true,
            "steps": [
                {
                    "step_id": 1,
                    "description": "Custom step 1",
                    "action": "knowledge",
                    "dependencies": [],
                    "expected_output": "Context text",
                    "tool": null
                },
                {
                    "step_id": 2,
                    "description": "Custom step 2",
                    "action": "coding",
                    "dependencies": [1],
                    "expected_output": "Code result",
                    "tool": "python_interpreter"
                }
            ]
        }'''
        mock_llm.invoke.return_value = mock_response

        monkeypatch.setattr(planner, "_get_llm", lambda: mock_llm)

        intent_res = IntentResult(intent=Intent.UNKNOWN, confidence=0.4)
        route_res = RouterResult(decision=RouteDecision.RETRIEVAL, skip_retrieval=False, reason="test")

        plan = planner.create_plan("unmatched complex query", intent_res, route_res)

        assert plan.goal == "Complex query resolution"
        assert plan.estimated_complexity == "complex"
        assert len(plan.steps) == 2
        assert plan.steps[1].dependencies == [1]

    def test_llm_planner_malformed_json_fallback(self, monkeypatch):
        planner = Planner()

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "INVALID_JSON_OUTPUT_FROM_LLM"
        mock_llm.invoke.return_value = mock_response

        monkeypatch.setattr(planner, "_get_llm", lambda: mock_llm)

        intent_res = IntentResult(intent=Intent.UNKNOWN, confidence=0.4)
        route_res = RouterResult(decision=RouteDecision.RETRIEVAL, skip_retrieval=False, reason="test")

        # Must recover gracefully with safe default single-step plan
        plan = planner.create_plan("ambiguous query causing invalid JSON", intent_res, route_res)

        assert plan is not None
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "direct_answer"
        assert plan.estimated_complexity == "simple"


class TestV32BackwardCompatibility:
    def test_planner_plan_returns_answermode(self, planner, router):
        intent_res = IntentResult(intent=Intent.KNOWLEDGE, confidence=0.95)
        route_res = router.route(intent_res)

        mode = planner.plan(intent_res, route_res)

        assert isinstance(mode, AnswerMode)
        assert mode.policy == SourcePolicy.KB
        assert mode.contract.requires_evidence is True
