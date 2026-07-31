"""Tests for Stage 6: Confidence Evaluation"""
import pytest
from app.agent.pipeline.confidence import ConfidenceEvaluator
from app.agent.pipeline.intent import Intent, IntentResult


class TestConfidenceEvaluator:
    @pytest.fixture
    def evaluator(self):
        return ConfidenceEvaluator(high_threshold=0.70, medium_threshold=0.45)

    def _intent(self, confidence=0.95):
        return IntentResult(intent=Intent.KNOWLEDGE, confidence=confidence, reason="test",
                            latency_ms=0.0, used_llm=False)

    def test_no_chunks_returns_clarification(self, evaluator):
        result = evaluator.evaluate([], self._intent())
        assert result.decision == "clarification"
        assert result.overall == 0.0

    def test_high_confidence_returns_answer(self, evaluator, sample_ranked_chunks):
        result = evaluator.evaluate(sample_ranked_chunks, self._intent(0.95))
        assert result.decision == "answer"
        assert result.overall >= 0.70

    def test_medium_confidence_returns_clarification(self, evaluator, sample_ranked_chunks):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.agent.pipeline.confidence._W_RETRIEVAL", 0.0)
            mp.setattr("app.agent.pipeline.confidence._W_RERANKER", 0.0)
            mp.setattr("app.agent.pipeline.confidence._W_INTENT", 1.0)
            mp.setattr("app.agent.pipeline.confidence._W_AGREEMENT", 0.0)
            result = evaluator.evaluate(sample_ranked_chunks, self._intent(0.50))
            assert result.decision == "clarification"

    def test_overall_score_bounded(self, evaluator, sample_ranked_chunks):
        result = evaluator.evaluate(sample_ranked_chunks, self._intent(0.95))
        assert 0.0 <= result.overall <= 1.0

    def test_source_agreement_increases_with_unique_sources(self, evaluator):
        from app.agent.pipeline.retriever import RetrievedChunk
        from app.agent.pipeline.reranker import RankedChunk
        from langchain_core.documents import Document

        chunks = [
            RankedChunk(
                chunk=RetrievedChunk(
                    document=Document(page_content=f"c{i}", metadata={"source": f"src{i}.pdf"}),
                    score=0.95, source=f"src{i}.pdf", collection="test",
                ),
                reranker_score=9.0, original_rank=i, reranked_rank=i,
            )
            for i in range(3)
        ]
        result = evaluator.evaluate(chunks, self._intent(0.95))
        assert result.source_agreement >= 0.33
