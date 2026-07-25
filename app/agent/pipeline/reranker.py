"""
Stage 5: Cross-Encoder Reranking

Purpose: Reorder the top-20 retrieved chunks using a cross-encoder model
         that scores query-document relevance more precisely than vector similarity.

Model: ms-marco-MiniLM-L-12-v2 (FlashRank)
  - Runs locally on CPU, no API key required
  - ~85MB model, downloaded automatically on first use
  - Typical latency: <200ms for 20 chunks
  - Model cached at /app/.cache/flashrank (persisted via Docker volume)

Input:  Top-20 retrieved chunks from the Retriever
Output: Top-5 reranked chunks (configurable via top_k)

Each RankedChunk stores:
  chunk          — the original RetrievedChunk with its retrieval score
  reranker_score — cross-encoder relevance score (used in confidence evaluation)
  original_rank  — position before reranking
  reranked_rank  — position after reranking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List

from app.core.langsmith import traceable
from .retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class RankedChunk:
    chunk: RetrievedChunk
    reranker_score: float   # raw cross-encoder score
    original_rank: int      # 0-indexed rank before reranking
    reranked_rank: int      # 0-indexed rank after reranking


class CrossEncoderReranker:
    """
    Uses FlashRank's cross-encoder to rerank retrieved chunks.
    Lazy-loads the model on first use to avoid blocking application startup.
    """

    DEFAULT_MODEL = "ms-marco-MiniLM-L-12-v2"
    DEFAULT_CACHE = "/app/.cache/flashrank"

    def __init__(
        self,
        top_k: int = 5,
        model_name: str = DEFAULT_MODEL,
        cache_dir: str = DEFAULT_CACHE,
    ) -> None:
        self._top_k = top_k
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._ranker = None  # lazy init

    def _get_ranker(self):
        """Lazy-load FlashRank ranker on first call."""
        if self._ranker is None:
            from flashrank import Ranker
            logger.info(
                "stage=reranker loading model=%s cache=%s",
                self._model_name,
                self._cache_dir,
            )
            self._ranker = Ranker(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )
            logger.info("stage=reranker model loaded")
        return self._ranker

    @traceable(name="reranker", metadata={"stage": 5})
    def rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RankedChunk]:
        """
        Rerank chunks using cross-encoder. Returns top_k ranked results.
        If chunks is empty, returns empty list immediately.
        """
        if not chunks:
            return []

        start = time.monotonic()
        from flashrank import RerankRequest

        # Build passages for FlashRank
        passages = [
            {
                "id": i,
                "text": chunk.document.page_content,
                "meta": {
                    "source": chunk.source,
                    "score": chunk.score,
                },
            }
            for i, chunk in enumerate(chunks)
        ]

        request = RerankRequest(query=query, passages=passages)
        results = self._get_ranker().rerank(request)
        elapsed = round((time.monotonic() - start) * 1000, 2)

        ranked: List[RankedChunk] = []
        for new_rank, result in enumerate(results[: self._top_k]):
            orig_idx = result["id"]
            reranker_score = round(float(result["score"]), 4)
            # Set reranker provenance on the underlying chunk
            chunks[orig_idx].provenance["reranker_score"] = reranker_score
            chunks[orig_idx].provenance["reranker_rank"] = new_rank + 1
            ranked.append(
                RankedChunk(
                    chunk=chunks[orig_idx],
                    reranker_score=reranker_score,
                    original_rank=orig_idx,
                    reranked_rank=new_rank,
                )
            )

        logger.info(
            "stage=reranking input=%d output=%d top_reranker_score=%.4f latency_ms=%.1f",
            len(chunks),
            len(ranked),
            ranked[0].reranker_score if ranked else 0.0,
            elapsed,
        )
        return ranked
