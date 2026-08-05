"""Tests for Stage 2: Request Router"""
import pytest
from app.agent.pipeline.router import RequestRouter, RouteDecision
from app.agent.pipeline.intent import Intent, IntentResult


class TestRequestRouter:
    @pytest.fixture
    def router(self):
        return RequestRouter()

    def _result(self, intent: Intent, confidence: float = 0.95, matched_rule: str = ""):
        return IntentResult(intent=intent, confidence=confidence, reason="test",
                            latency_ms=0.0, used_llm=False, matched_rule=matched_rule)

    def test_rag_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.KNOWLEDGE))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval


    def test_memory_routes_to_memory(self, router):
        result = router.route(self._result(Intent.MEMORY))
        assert result.decision == RouteDecision.MEMORY
        assert result.skip_retrieval

    def test_general_chitchat_rule_routes_to_direct_llm(self, router):
        result = router.route(self._result(Intent.GENERAL, matched_rule="GENERAL_CHAT"))
        assert result.decision == RouteDecision.DIRECT_LLM
        assert result.skip_retrieval

    def test_general_llm_classified_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.GENERAL))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval

    def test_coding_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.CODING))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval

    def test_reasoning_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.REASONING))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval

    def test_tool_routes_to_direct_llm(self, router):
        result = router.route(self._result(Intent.TOOL))
        assert result.decision == RouteDecision.DIRECT_LLM
        assert result.skip_retrieval

    def test_unknown_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.UNKNOWN))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval
