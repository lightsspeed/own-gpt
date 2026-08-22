"""
Whoosh BM25 full-text search for hybrid retrieval.

Zero-infrastructure full-text search engine.
Index stored at data/whoosh/ — persistent across restarts.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional

from whoosh import index as whoosh_index
from whoosh.analysis import StandardAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import MultifieldParser, OrGroup

logger = logging.getLogger(__name__)

SCHEMA = Schema(
    chunk_id=ID(stored=True, unique=True),
    content=TEXT(stored=True, analyzer=StandardAnalyzer()),
    source=TEXT(stored=True),
    collection=TEXT(stored=True),
    project_id=TEXT(stored=True),
)


@dataclass
class BM25Result:
    chunk_id: str
    content: str
    source: str
    collection: str
    score: float  # BM25 score
    project_id: str = ""


class BM25Retriever:
    """Persistent Whoosh BM25 index manager."""

    def __init__(self, index_dir: str = "data/whoosh") -> None:
        self._index_dir = index_dir
        self._ix: Optional[whoosh_index.Index] = None
        self._open_or_create()

    def _open_or_create(self) -> None:
        os.makedirs(self._index_dir, exist_ok=True)
        if whoosh_index.exists_in(self._index_dir):
            self._ix = whoosh_index.open_dir(self._index_dir)
            logger.info("whoosh_index_loaded dir=%s", self._index_dir)
        else:
            self._ix = whoosh_index.create_in(self._index_dir, SCHEMA)
            logger.info("whoosh_index_created dir=%s", self._index_dir)

    # ── Index management ──────────────────────────────────────────────────────

    def add_document(self, chunk_id: str, content: str, source: str = "", collection: str = "", project_id: str = "") -> None:
        """Insert or update a single document in the Whoosh index."""
        writer = self._ix.writer()
        writer.update_document(
            chunk_id=chunk_id,
            content=content,
            source=source,
            collection=collection,
            project_id=project_id,
        )
        writer.commit()

    def add_documents(self, docs: List[dict]) -> None:
        """Batch insert documents. Each dict may have chunk_id, content, source, collection, project_id."""
        writer = self._ix.writer()
        for d in docs:
            writer.update_document(
                chunk_id=d["chunk_id"],
                content=d["content"],
                source=d.get("source", ""),
                collection=d.get("collection", "own_gpt_docs"),
                project_id=d.get("project_id", ""),
            )
        writer.commit()

    def remove_document(self, chunk_id: str) -> None:
        writer = self._ix.writer()
        writer.delete_by_term("chunk_id", chunk_id)
        writer.commit()

    def delete_by_source(self, source: str) -> int:
        """Delete all documents whose source field matches the given value. Returns count."""
        count = 0
        with self._ix.searcher() as searcher:
            results = searcher.search(
                MultifieldParser(["source"], schema=SCHEMA, group=OrGroup).parse(source),
                limit=None,
            )
            chunk_ids = [hit["chunk_id"] for hit in results]
        if chunk_ids:
            writer = self._ix.writer()
            for cid in chunk_ids:
                writer.delete_by_term("chunk_id", cid)
                count += 1
            writer.commit()
        logger.info("whoosh_delete_by_source source=%s count=%d", source, count)
        return count

    def clear(self) -> None:
        """Delete and recreate the index."""
        self._ix = whoosh_index.create_in(self._index_dir, SCHEMA)
        logger.info("whoosh_index_cleared dir=%s", self._index_dir)

    @property
    def doc_count(self) -> int:
        return self._ix.doc_count() if self._ix else 0

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 20, project_id: Optional[str] = None) -> List[BM25Result]:
        """
        BM25 full-text search. Returns top-k results sorted by BM25 score descending.
        Searches across 'content' and 'source' fields.
        If project_id is provided, filters results to only matching project_id.
        """
        if not self._ix:
            return []
        start = time.monotonic()
        results: List[BM25Result] = []
        try:
            with self._ix.searcher() as searcher:
                parser = MultifieldParser(["content", "source"], schema=SCHEMA, group=OrGroup)
                parsed = parser.parse(query)
                # If filtering by project, fetch up to k * 5 candidate hits to allow filtering
                fetch_limit = k * 5 if project_id else k
                hits = searcher.search(parsed, limit=fetch_limit)
                for hit in hits:
                    hit_pid = hit.get("project_id", "")
                    if project_id and hit_pid != project_id:
                        continue
                    results.append(BM25Result(
                        chunk_id=hit["chunk_id"],
                        content=hit["content"],
                        source=hit.get("source", ""),
                        collection=hit.get("collection", ""),
                        score=hit.score,
                        project_id=hit_pid,
                    ))
                    if len(results) >= k:
                        break
        except Exception as exc:
            logger.warning("whoosh_search_error query=%r error=%s", query[:60], exc)
        elapsed = round((time.monotonic() - start) * 1000, 2)
        logger.debug(
            "stage=bm25_search query=%r k=%d hits=%d latency_ms=%.1f project_id=%s",
            query[:60], k, len(results), elapsed, project_id,
        )
        return results
