"""
Whoosh lifecycle manager: lazy persistent index with auto-refresh.

Strategy:
  - On startup: load existing index from data/whoosh/ (~200ms)
  - If missing: rebuild from all chunks in PGVector
  - On document upload: incremental update via add_documents()

Usage:
    from app.core.whoosh_manager import get_whoosh_retriever

    bm25 = get_whoosh_retriever()
    bm25.search("query")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from app.retrievers.bm25 import BM25Retriever

logger = logging.getLogger(__name__)

_INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "whoosh")

_bm25_instance: Optional[BM25Retriever] = None


def get_whoosh_retriever() -> BM25Retriever:
    """Return the singleton Whoosh BM25 retriever. Creates on first call."""
    global _bm25_instance
    if _bm25_instance is None:
        _bm25_instance = BM25Retriever(index_dir=_INDEX_DIR)
    return _bm25_instance


def rebuild_whoosh_index(vector_store, batch_size: int = 500) -> int:
    """
    Rebuild the entire Whoosh index from all chunks in PGVector.
    This is a fallback — normally the index persists across restarts.

    Returns number of documents indexed.
    """
    from app.retrievers.bm25 import BM25Retriever

    bm25 = BM25Retriever(index_dir=_INDEX_DIR)
    bm25.clear()

    count = 0
    # PGVector stores documents; we retrieve them via the collection
    try:
        results = vector_store.similarity_search_with_score("*", k=10000)
        if results:
            docs = []
            for doc, _ in results:
                chunk_id = doc.metadata.get("chunk_id", f"rebuild-{count}")
                docs.append({
                    "chunk_id": chunk_id,
                    "content": doc.page_content,
                    "source": doc.metadata.get("filename", doc.metadata.get("source", "unknown")),
                    "collection": doc.metadata.get("collection_name", "own_gpt_docs"),
                    "project_id": doc.metadata.get("project_id", ""),
                })
                count += 1
                if len(docs) >= batch_size:
                    bm25.add_documents(docs)
                    docs = []
            if docs:
                bm25.add_documents(docs)
        logger.info("whoosh_rebuild_complete total=%d", count)
    except Exception as exc:
        logger.warning("whoosh_rebuild_failed error=%s", exc)

    global _bm25_instance
    _bm25_instance = bm25
    return count


def add_to_whoosh_index(chunks: list) -> None:
    """Incrementally add newly chunked documents to the Whoosh index."""
    bm25 = get_whoosh_retriever()
    docs = []
    import uuid
    for chunk in chunks:
        doc_id = chunk.metadata.get("chunk_id", str(uuid.uuid4()))
        docs.append({
            "chunk_id": doc_id,
            "content": chunk.page_content,
            "source": chunk.metadata.get("filename", chunk.metadata.get("source", "unknown")),
            "collection": chunk.metadata.get("collection_name", "own_gpt_docs"),
            "project_id": chunk.metadata.get("project_id", ""),
        })
    if docs:
        bm25.add_documents(docs)
        logger.info("whoosh_incremental_add count=%d", len(docs))


def delete_from_whoosh_index(source: str) -> int:
    """
    Remove all Whoosh documents matching the given source filename.
    Returns number of documents deleted.
    """
    bm25 = get_whoosh_retriever()
    return bm25.delete_by_source(source)
