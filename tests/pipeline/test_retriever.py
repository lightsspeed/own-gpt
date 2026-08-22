"""Tests for Stage 4: Knowledge Retrieval"""
import pytest
from langchain_core.documents import Document
from app.agent.pipeline.retriever import Retriever


class TestRetriever:
    def test_retrieve_returns_chunks(self):
        store = _MockVectorStore()
        retriever = Retriever(vector_store=store, k=3)
        chunks, timings = retriever.retrieve("test query")
        assert len(chunks) == 3
        assert all(c.score >= 0 for c in chunks)
        assert all(c.score <= 1 for c in chunks)

    def test_retrieve_sorted_by_score_descending(self):
        store = _MockVectorStore()
        retriever = Retriever(vector_store=store, k=5)
        chunks, timings = retriever.retrieve("test")
        scores = [c.score for c in chunks]
        assert scores == sorted(scores, reverse=True)

    def test_retrieve_sets_source_from_metadata(self):
        store = _MockVectorStore()
        retriever = Retriever(vector_store=store, k=1)
        chunks, timings = retriever.retrieve("test")
        assert chunks[0].source is not None

    def test_retrieve_empty_when_no_results(self):
        store = _MockVectorStore(results=[])
        retriever = Retriever(vector_store=store, k=3)
        chunks, timings = retriever.retrieve("test")
        assert len(chunks) == 0


class _MockVectorStore:
    def __init__(self, results=None):
        self._results = results

    def similarity_search_with_score(self, query, k, filter=None):
        if self._results is not None:
            return self._results
        return [
            (Document(page_content=f"doc {i}", metadata={"filename": f"f{i}.pdf", "source": f"f{i}.pdf"}), round(i * 0.3, 2))
            for i in range(k)
        ]
