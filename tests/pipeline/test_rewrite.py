"""Tests for Stage 3: Query Rewrite"""
import pytest
from app.agent.pipeline.rewrite import QueryRewriter
from app.agent.pipeline.intent import Intent, IntentResult


class TestQueryRewriter:
    @pytest.fixture
    def rewriter(self):
        return QueryRewriter()

    def _intent(self, intent: Intent):
        return IntentResult(intent=intent, confidence=0.95, reason="test",
                            latency_ms=0.0, used_llm=False)

    def test_rewrite_returns_noop_for_general_intent(self, rewriter):
        result = rewriter.rewrite("hello", self._intent(Intent.GENERAL))
        assert result.was_rewritten is False
        assert result.rewritten == "hello"

    def test_rewrite_returns_noop_for_coding_intent(self, rewriter):
        result = rewriter.rewrite("write code", self._intent(Intent.CODING))
        assert result.was_rewritten is False
        assert result.rewritten == "write code"

    def test_rewrite_preserves_original(self, rewriter):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(rewriter, "_get_llm", lambda: _mock_llm())
            result = rewriter.rewrite("test query", self._intent(Intent.KNOWLEDGE))
            assert result.original == "test query"

    def test_rewrite_sets_latency_on_rag(self, rewriter):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(rewriter, "_get_llm", lambda: _mock_llm())
            result = rewriter.rewrite("test query", self._intent(Intent.KNOWLEDGE))
            assert result.latency_ms >= 0


def _mock_llm():
    class MockResponse:
        content = '{"rewritten": "optimized query", "expanded": ["alt1", "alt2"]}'
    class MockLLM:
        def invoke(self, msgs):
            return MockResponse()
    return MockLLM()
