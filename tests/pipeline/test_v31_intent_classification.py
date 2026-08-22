"""Hermetic unit tests for V3.1 Intent & Request Classification (app/agent/pipeline/intent.py).

Covers all 8 supported intents:
- general
- memory
- knowledge
- web
- document
- coding
- reasoning
- multi_intent

Also tests:
- IntentResult fields: intent, confidence, reasoning, requires_tool, candidate_tools
- Router integration for V3.1 intents
- Mocked LLM fallback classification
"""

import pytest
from unittest.mock import MagicMock
from app.agent.pipeline.intent import IntentClassifier, Intent, IntentResult
from app.agent.pipeline.router import RequestRouter, RouteDecision


@pytest.fixture
def classifier():
    return IntentClassifier()


@pytest.fixture
def router():
    return RequestRouter()


class TestV31IntentRuleClassification:
    def test_general_intent_rule(self, classifier):
        res = classifier.rule_classify("hello good morning")
        assert res is not None
        assert res.intent == Intent.GENERAL
        assert res.requires_tool is False
        assert res.candidate_tools == []
        assert res.reasoning != ""

    def test_memory_intent_rule(self, classifier):
        res = classifier.rule_classify("remember that my favorite color is electric blue")
        assert res is not None
        assert res.intent == Intent.MEMORY
        assert res.requires_tool is False
        assert "remember_user_fact" in res.candidate_tools
        assert res.confidence == 0.95

    def test_web_intent_rule(self, classifier):
        res = classifier.rule_classify("what is the latest news on AI today?")
        assert res is not None
        assert res.intent == Intent.WEB
        assert res.requires_tool is True
        assert "tavily_search" in res.candidate_tools

    def test_document_intent_rule(self, classifier):
        res = classifier.rule_classify("according to the uploaded pdf document, what is the policy?")
        assert res is not None
        assert res.intent == Intent.DOCUMENT
        assert res.requires_tool is False

    def test_coding_intent_rule(self, classifier):
        res = classifier.rule_classify("write a python script to parse json files")
        assert res is not None
        assert res.intent == Intent.CODING
        assert res.requires_tool is True
        assert "python_interpreter" in res.candidate_tools

    def test_reasoning_intent_rule(self, classifier):
        res = classifier.rule_classify("prove that the sum of two even integers is even step by step")
        assert res is not None
        assert res.intent == Intent.REASONING
        assert res.requires_tool is False

    def test_multi_intent_rule(self, classifier):
        res = classifier.rule_classify("remember my preference and search the web for Kubernetes releases")
        assert res is not None
        assert res.intent == Intent.MULTI_INTENT
        assert res.requires_tool is True
        assert "tavily_search" in res.candidate_tools
        assert "remember_user_fact" in res.candidate_tools

    def test_knowledge_intent_rule(self, classifier):
        res = classifier.rule_classify("what is Kubernetes RBAC?")
        assert res is not None
        assert res.intent == Intent.KNOWLEDGE
        assert res.requires_tool is False


class TestV31IntentResultFields:
    def test_intent_result_fields_compatibility(self):
        res = IntentResult(
            intent=Intent.WEB,
            confidence=0.9,
            reason="Fresh news request",
            latency_ms=1.5,
            used_llm=False,
            matched_rule="WEB_SEARCH",
            requires_tool=True,
            candidate_tools=["tavily_search"],
        )
        assert res.intent == Intent.WEB
        assert res.confidence == 0.9
        assert res.reason == "Fresh news request"
        assert res.reasoning == "Fresh news request"  # post-init sync
        assert res.requires_tool is True
        assert res.candidate_tools == ["tavily_search"]


class TestV31RouterIntegration:
    def test_router_web_intent(self, router):
        intent_res = IntentResult(
            intent=Intent.WEB,
            confidence=0.95,
            reason="Rule match",
            latency_ms=0.0,
            used_llm=False,
            requires_tool=True,
            candidate_tools=["tavily_search"],
        )
        route_res = router.route(intent_res)
        assert route_res.decision == RouteDecision.DIRECT_LLM
        assert route_res.skip_retrieval is True

    def test_router_document_intent(self, router):
        intent_res = IntentResult(
            intent=Intent.DOCUMENT,
            confidence=0.95,
            reason="Rule match",
            latency_ms=0.0,
            used_llm=False,
        )
        route_res = router.route(intent_res)
        assert route_res.decision == RouteDecision.RETRIEVAL
        assert route_res.skip_retrieval is False

    def test_router_multi_intent(self, router):
        intent_res = IntentResult(
            intent=Intent.MULTI_INTENT,
            confidence=0.95,
            reason="Rule match",
            latency_ms=0.0,
            used_llm=False,
            requires_tool=True,
            candidate_tools=["tavily_search", "remember_user_fact"],
        )
        route_res = router.route(intent_res)
        assert route_res.decision == RouteDecision.RETRIEVAL
        assert route_res.skip_retrieval is False


class TestMockedLLMFallbackClassification:
    def test_llm_classification_fallback(self, monkeypatch):
        classifier = IntentClassifier()

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"intent": "web", "confidence": 0.88, "reasoning": "Live web query", "requires_tool": true, "candidate_tools": ["tavily_search"]}'
        mock_llm.invoke.return_value = mock_response

        monkeypatch.setattr(classifier, "_get_llm", lambda: mock_llm)

        # Unmatched query triggers LLM fallback
        res = classifier.classify("should I wear a winter jacket in Tokyo tomorrow evening?")
        assert res.intent == Intent.WEB
        assert res.confidence == 0.88
        assert res.requires_tool is True
        assert res.candidate_tools == ["tavily_search"]
        assert res.used_llm is True
