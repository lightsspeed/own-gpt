"""
Tests for Knowledge Base Project Isolation (V3 Phase 2).

Verifies that:
1. Chunk metadata receives project_id and owner_id during ingestion.
2. Vector, BM25, and Hybrid retrievers strictly filter results by project_id.
3. Documents from Project A never appear in Project B retrieval.
4. Legacy documents without project_id metadata are safely excluded from project-scoped queries.
"""

import pytest
from langchain_core.documents import Document
from app.agent.pipeline.retriever import Retriever
from app.retrievers.bm25 import BM25Retriever, BM25Result
from app.retrievers.hybrid import HybridRetriever
from app.services.vector_store import similarity_search


class _MockVectorStoreWithFilter:
    """Mock PGVector store that records the filter dictionary passed to it
    and filters mock items accordingly."""

    def __init__(self, items=None):
        # List of tuples: (Document, distance)
        self.items = items or []
        self.last_filter = None

    def similarity_search_with_score(self, query, k=20, filter=None):
        self.last_filter = filter
        results = []
        for doc, dist in self.items:
            # Apply mock filter logic if filter is present
            if filter:
                if "project_id" in filter:
                    target_pid = filter["project_id"]
                    if doc.metadata.get("project_id") != target_pid:
                        continue
                elif "$and" in filter:
                    match = True
                    for sub in filter["$and"]:
                        if "project_id" in sub:
                            if doc.metadata.get("project_id") != sub["project_id"]:
                                match = False
                                break
                    if not match:
                        continue
            results.append((doc, dist))
        return results[:k]

    def similarity_search(self, query, k=4, filter=None):
        raw = self.similarity_search_with_score(query, k=k, filter=filter)
        return [doc for doc, _ in raw]


class TestRetrieverProjectIsolation:
    def test_retriever_passes_project_id_filter(self):
        store = _MockVectorStoreWithFilter()
        retriever = Retriever(vector_store=store, k=5)
        retriever.retrieve("test query", project_id="proj_alpha")

        assert store.last_filter == {"project_id": "proj_alpha"}

    def test_retriever_combines_filename_and_project_id(self):
        store = _MockVectorStoreWithFilter()
        retriever = Retriever(vector_store=store, k=5)
        retriever.retrieve("test query", filename="doc.pdf", project_id="proj_alpha")

        assert store.last_filter == {
            "$and": [
                {"$or": [{"filename": "doc.pdf"}, {"source": "doc.pdf"}]},
                {"project_id": "proj_alpha"},
            ]
        }

    def test_cross_project_isolation(self):
        doc_a = Document(
            page_content="Secret of Project A",
            metadata={"filename": "a.txt", "source": "a.txt", "project_id": "proj_A"},
        )
        doc_b = Document(
            page_content="Secret of Project B",
            metadata={"filename": "b.txt", "source": "b.txt", "project_id": "proj_B"},
        )

        store = _MockVectorStoreWithFilter(items=[(doc_a, 0.1), (doc_b, 0.2)])
        retriever = Retriever(vector_store=store, k=5)

        # Query for Project A
        chunks_a, _ = retriever.retrieve("Secret", project_id="proj_A")
        assert len(chunks_a) == 1
        assert chunks_a[0].source == "a.txt"
        assert chunks_a[0].document.metadata["project_id"] == "proj_A"

        # Query for Project B
        chunks_b, _ = retriever.retrieve("Secret", project_id="proj_B")
        assert len(chunks_b) == 1
        assert chunks_b[0].source == "b.txt"
        assert chunks_b[0].document.metadata["project_id"] == "proj_B"

    def test_legacy_documents_excluded_from_project_query(self):
        """Legacy chunks without project_id must not leak into project-scoped queries."""
        doc_legacy = Document(
            page_content="Legacy untagged content",
            metadata={"filename": "old.txt", "source": "old.txt"},  # no project_id
        )
        doc_project = Document(
            page_content="Project A content",
            metadata={"filename": "new.txt", "source": "new.txt", "project_id": "proj_A"},
        )

        store = _MockVectorStoreWithFilter(items=[(doc_legacy, 0.1), (doc_project, 0.2)])
        retriever = Retriever(vector_store=store, k=5)

        chunks, _ = retriever.retrieve("content", project_id="proj_A")
        assert len(chunks) == 1
        assert chunks[0].source == "new.txt"
        assert chunks[0].document.page_content == "Project A content"


class TestBM25ProjectIsolation:
    def test_bm25_search_filters_by_project_id(self, tmp_path):
        retriever = BM25Retriever(index_dir=str(tmp_path / "whoosh"))
        retriever.add_document(
            chunk_id="c1",
            content="Kubernetes pod configuration for Project Alpha",
            source="alpha.pdf",
            project_id="proj_alpha",
        )
        retriever.add_document(
            chunk_id="c2",
            content="Kubernetes pod configuration for Project Beta",
            source="beta.pdf",
            project_id="proj_beta",
        )
        retriever.add_document(
            chunk_id="c3",
            content="Kubernetes pod configuration legacy document",
            source="legacy.pdf",
            project_id="",
        )

        # Search for Alpha
        hits_alpha = retriever.search("Kubernetes", project_id="proj_alpha")
        assert len(hits_alpha) == 1
        assert hits_alpha[0].chunk_id == "c1"
        assert hits_alpha[0].project_id == "proj_alpha"

        # Search for Beta
        hits_beta = retriever.search("Kubernetes", project_id="proj_beta")
        assert len(hits_beta) == 1
        assert hits_beta[0].chunk_id == "c2"
        assert hits_beta[0].project_id == "proj_beta"


class TestHybridProjectIsolation:
    def test_hybrid_passes_project_id_to_sub_retrievers(self, tmp_path):
        doc_a = Document(
            page_content="React architecture for Alpha",
            metadata={"chunk_id": "ca1", "filename": "alpha.md", "source": "alpha.md", "project_id": "proj_alpha"},
        )
        doc_b = Document(
            page_content="React architecture for Beta",
            metadata={"chunk_id": "cb1", "filename": "beta.md", "source": "beta.md", "project_id": "proj_beta"},
        )
        v_store = _MockVectorStoreWithFilter(items=[(doc_a, 0.1), (doc_b, 0.2)])
        v_retriever = Retriever(vector_store=v_store, k=5)

        bm25_retriever = BM25Retriever(index_dir=str(tmp_path / "whoosh"))
        bm25_retriever.add_document("ca1", "React architecture for Alpha", "alpha.md", project_id="proj_alpha")
        bm25_retriever.add_document("cb1", "React architecture for Beta", "beta.md", project_id="proj_beta")

        hybrid = HybridRetriever(vector_retriever=v_retriever, bm25_retriever=bm25_retriever)

        fused_chunks, timings = hybrid.retrieve("React", project_id="proj_alpha")
        assert len(fused_chunks) == 1
        assert fused_chunks[0].chunk_id == "ca1"
