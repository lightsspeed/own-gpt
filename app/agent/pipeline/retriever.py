"""
Stage 4: Knowledge Retrieval

Purpose: Retrieve the top-K most semantically similar chunks from pgvector.

Upgrade from the original implementation:
  Before: similarity_search(query, k=3)       — no scores, only 3 results
  After:  similarity_search_with_score(q, k=20) — scores surfaced, top-20 for reranker

Score conversion:
  PGVector with cosine distance returns a distance value in [0, 2].
  We convert to similarity in [0, 1]:
    similarity = max(0.0, 1.0 - distance)
  For well-normalized OpenAI embeddings, this gives intuitive [0, 1] values.

Output per chunk:
  document   — LangChain Document object
  score      — cosine similarity [0.0, 1.0]
  source     — filename or source metadata field
  collection — pgvector collection name
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from app.core.langsmith import traceable

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    document: Document
    score: float      # cosine similarity [0.0, 1.0] — higher is better
    source: str
    collection: str
    provenance: Dict[str, Any] = field(default_factory=lambda: {
        "retrieval_method": "vector",
        "vector_rank": None,
        "vector_score": None,
        "bm25_rank": None,
        "bm25_score": None,
        "rrf_score": None,
        "rrf_rank": None,
        "reranker_score": None,
        "reranker_rank": None,
    })

    @property
    def chunk_id(self) -> str:
        return self.document.metadata.get("chunk_id", "")

    @property
    def page(self) -> Optional[int]:
        return self.document.metadata.get("page")

    @property
    def chapter(self) -> Optional[str]:
        return self.document.metadata.get("chapter")

    def metadata_dict(self) -> Dict[str, Any]:
        d = {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "score": self.score,
            "page": self.page,
            "chapter": self.chapter,
        }
        # Include provenance (filter out None values for cleaner output)
        prov = {k: v for k, v in self.provenance.items() if v is not None}
        if prov:
            d["provenance"] = prov
        return d


class Retriever:
    """
    Retrieves semantically similar document chunks from pgvector,
    surfacing similarity scores for the downstream confidence evaluator.
    """

    def __init__(self, vector_store, k: int = 20) -> None:
        self._store = vector_store
        self._k = k

    @traceable(name="retriever", metadata={"stage": 4})
    def retrieve(self, query: str) -> tuple[List[RetrievedChunk], dict]:
        """
        Retrieve top-K chunks with similarity scores.
        Returns (chunks, timing_dict) — chunks sorted by score descending.
        """
        start = time.monotonic()

        raw_results = self._store.similarity_search_with_score(query, k=self._k)

        chunks: List[RetrievedChunk] = []
        for _, (doc, distance) in enumerate(raw_results):
            similarity = round(max(0.0, 1.0 - distance), 4)
            chunk = RetrievedChunk(
                document=doc,
                score=similarity,
                source=doc.metadata.get("filename", doc.metadata.get("source", "unknown")),
                collection=doc.metadata.get("collection_name", "own_gpt_docs"),
            )
            chunks.append(chunk)

        chunks.sort(key=lambda c: c.score, reverse=True)
        for rank, chunk in enumerate(chunks):
            chunk.provenance["vector_rank"] = rank + 1
            chunk.provenance["vector_score"] = chunk.score

        elapsed = round((time.monotonic() - start) * 1000, 2)
        timings = {"vector_search_ms": elapsed}

        chunk_ids = [c.chunk_id for c in chunks]
        pages = [c.page for c in chunks if c.page is not None]
        chapters = [c.chapter for c in chunks if c.chapter is not None]
        logger.info(
            "stage=retrieval query=%r k=%d retrieved=%d top_score=%.4f latency_ms=%.1f "
            "chunk_ids=%s pages=%s chapters=%s",
            query[:60],
            self._k,
            len(chunks),
            chunks[0].score if chunks else 0.0,
            elapsed,
            chunk_ids[:5],
            pages[:5],
            chapters[:5],
        )
        return chunks, timings
