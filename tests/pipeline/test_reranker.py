"""Tests for Stage 5: Cross-Encoder Reranking"""
import pytest
from app.agent.pipeline.reranker import CrossEncoderReranker


class TestCrossEncoderReranker:
    def test_rerank_returns_top_k(self, sample_retrieved_chunks):
        reranker = CrossEncoderReranker(top_k=3)
        ranked = reranker.rerank("test", sample_retrieved_chunks)
        assert len(ranked) == min(3, len(sample_retrieved_chunks))

    def test_rerank_empty_input_returns_empty(self,):
        reranker = CrossEncoderReranker()
        ranked = reranker.rerank("test", [])
        assert ranked == []

    def test_rerank_lazy_loads_model(self, sample_retrieved_chunks):
        reranker = CrossEncoderReranker(top_k=2)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(reranker, "_get_ranker", lambda: _MockRanker())
            ranked = reranker.rerank("test", sample_retrieved_chunks)
            assert len(ranked) <= 2

    def test_reranker_sets_reranker_score(self, sample_retrieved_chunks):
        reranker = CrossEncoderReranker(top_k=2)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(reranker, "_get_ranker", lambda: _MockRanker())
            ranked = reranker.rerank("test", sample_retrieved_chunks)
            for r in ranked:
                assert r.reranker_score is not None


class _MockRanker:
    def rerank(self, request):
        passages = request.passages
        return [
            {"id": p["id"], "text": p["text"], "score": 10.0 - i, "meta": p.get("meta", {})}
            for i, p in enumerate(passages)
        ]
