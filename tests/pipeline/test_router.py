"""Tests for Stage 2: Request Router"""
import pytest
from app.agent.pipeline.router import RequestRouter, RouteDecision
from app.agent.pipeline.intent import Intent, IntentResult


class TestRequestRouter:
    @pytest.fixture
    def router(self):
        return RequestRouter()

    def _result(self, intent: Intent, confidence: float = 0.95):
        return IntentResult(intent=intent, confidence=confidence, reason="test",
                            latency_ms=0.0, used_llm=False)

    def test_rag_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.RAG))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval

    def test_web_routes_to_web_search(self, router):
        result = router.route(self._result(Intent.WEB))
        assert result.decision == RouteDecision.WEB_SEARCH
        assert result.skip_retrieval

    def test_memory_routes_to_memory(self, router):
        result = router.route(self._result(Intent.MEMORY))
        assert result.decision == RouteDecision.MEMORY
        assert result.skip_retrieval

    def test_general_routes_to_direct_llm(self, router):
        result = router.route(self._result(Intent.GENERAL))
        assert result.decision == RouteDecision.DIRECT_LLM
        assert result.skip_retrieval

    def test_coding_routes_to_direct_llm(self, router):
        result = router.route(self._result(Intent.CODING))
        assert result.decision == RouteDecision.DIRECT_LLM
        assert result.skip_retrieval

    def test_reasoning_routes_to_direct_llm(self, router):
        result = router.route(self._result(Intent.REASONING))
        assert result.decision == RouteDecision.DIRECT_LLM
        assert result.skip_retrieval

    def test_tool_routes_to_direct_llm(self, router):
        result = router.route(self._result(Intent.TOOL))
        assert result.decision == RouteDecision.DIRECT_LLM
        assert result.skip_retrieval

    def test_unknown_routes_to_retrieval(self, router):
        result = router.route(self._result(Intent.UNKNOWN))
        assert result.decision == RouteDecision.RETRIEVAL
        assert not result.skip_retrieval
