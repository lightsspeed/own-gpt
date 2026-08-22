"""
Hybrid search: Reciprocal Rank Fusion of vector search + BM25 results.

RRF formula: score(d) = Σ 1 / (k + rank_i(d))
where rank_i(d) is the rank of document d in result set i.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

from app.agent.pipeline.retriever import RetrievedChunk
from .bm25 import BM25Retriever, BM25Result

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    vector_results: List[RetrievedChunk],
    bm25_results: List[BM25Result],
    k: int = 60,
    top_n: int = 20,
    vector_weight: float = 0.5,
    bm25_weight: float = 0.5,
) -> List[RetrievedChunk]:
    """
    Fuse vector and BM25 results using RRF.

    Sets provenance on each chunk:
      - retrieval_method: "vector" | "bm25" | "both"
      - vector_rank / vector_score
      - bm25_rank / bm25_score
      - rrf_score / rrf_rank

    Args:
        vector_results: retrieved chunks from vector search (pre-sorted by score desc)
        bm25_results: results from BM25 search (pre-sorted by score desc)
        k: RRF rank constant (default 60)
        top_n: number of results to return after fusion
        vector_weight: weight for vector rankings (default 0.5)
        bm25_weight: weight for BM25 rankings (default 0.5)

    Returns:
        fused results sorted by RRF score descending
    """
    scores: Dict[str, Tuple[float, RetrievedChunk]] = {}

    # Score vector results
    for rank, chunk in enumerate(vector_results):
        key = chunk.document.metadata.get("chunk_id", chunk.source + str(rank))
        rrf_score = vector_weight * (1.0 / (k + rank + 1))
        # Set vector provenance on the chunk (first pass — overwritten if BM25 also matches)
        chunk.provenance["retrieval_method"] = "vector"
        chunk.provenance["vector_rank"] = chunk.provenance.get("vector_rank", rank + 1)
        chunk.provenance["rrf_score"] = rrf_score
        scores[key] = (rrf_score, chunk)

    # Score BM25 results and merge
    for rank, bm25 in enumerate(bm25_results):
        key = bm25.chunk_id
        rrf_score = bm25_weight * (1.0 / (k + rank + 1))
        if key in scores:
            existing_score, existing_chunk = scores[key]
            # This chunk matched both vector AND BM25
            existing_chunk.provenance["retrieval_method"] = "both"
            existing_chunk.provenance["bm25_rank"] = rank + 1
            existing_chunk.provenance["bm25_score"] = bm25.score
            existing_chunk.provenance["rrf_score"] = existing_score + rrf_score
            scores[key] = (existing_score + rrf_score, existing_chunk)
        else:
            from langchain_core.documents import Document
            dummy = RetrievedChunk(
                document=Document(
                    page_content=bm25.content,
                    metadata={"chunk_id": bm25.chunk_id, "source": bm25.source, "collection_name": bm25.collection},
                ),
                score=bm25.score,
                source=bm25.source,
                collection=bm25.collection,
            )
            dummy.provenance["retrieval_method"] = "bm25"
            dummy.provenance["bm25_rank"] = rank + 1
            dummy.provenance["bm25_score"] = bm25.score
            dummy.provenance["rrf_score"] = rrf_score
            scores[key] = (rrf_score, dummy)

    # Sort by RRF score descending
    sorted_results = sorted(scores.values(), key=lambda x: x[0], reverse=True)

    # Attach RRF rank to each chunk
    fused: List[RetrievedChunk] = []
    for rrf_rank, (rrf_score, chunk) in enumerate(sorted_results[:top_n]):
        chunk.provenance["rrf_rank"] = rrf_rank + 1
        # Also keep legacy metadata field for backward compatibility
        chunk.document.metadata["rrf_score"] = round(rrf_score, 4)
        fused.append(chunk)

    return fused


class HybridRetriever:
    """
    Orchestrates vector + BM25 retrieval with RRF fusion.

    Usage:
        hybrid = HybridRetriever(vector_retriever, bm25_retriever)
        chunks = hybrid.retrieve(query, top_k=20)
    """

    def __init__(
        self,
        vector_retriever,
        bm25_retriever: BM25Retriever,
        top_k_vector: int = 20,
        top_k_bm25: int = 20,
        final_top_k: int = 20,
        rrf_k: int = 60,
        similarity_threshold: float = 0.72,
    ) -> None:
        self._vector = vector_retriever
        self._bm25 = bm25_retriever
        self._top_k_vector = top_k_vector
        self._top_k_bm25 = top_k_bm25
        self._final_top_k = final_top_k
        self._rrf_k = rrf_k
        self._similarity_threshold = similarity_threshold

    def retrieve(
        self,
        query: str,
        filename: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> tuple[List[RetrievedChunk], dict]:
        """
        Hybrid retrieval: vector search + BM25 → RRF fusion.
        Returns (chunks, timing_dict) with per-stage latency breakdown.

        Args:
            query: Search query.
            filename: If set, vector search is restricted to this document.
            project_id: If set, restrict retrieval to chunks from this project.
        """
        t_total = time.monotonic()

        # Stage 1: Vector search
        t_vs = time.monotonic()
        vector_chunks, _ = self._vector.retrieve(query, filename=filename, project_id=project_id)
        vector_ms = round((time.monotonic() - t_vs) * 1000, 2)

        logger.debug(
            "hybrid_vector_complete query=%r retrieved=%d top_score=%.4f latency_ms=%.1f project_id=%s",
            query[:60], len(vector_chunks), vector_chunks[0].score if vector_chunks else 0.0, vector_ms, project_id,
        )

        # Stage 2: BM25 search
        t_bm = time.monotonic()
        bm25_results = self._bm25.search(query, k=self._top_k_bm25, project_id=project_id)
        bm25_ms = round((time.monotonic() - t_bm) * 1000, 2)

        logger.debug(
            "hybrid_bm25_complete query=%r hits=%d top_score=%.2f latency_ms=%.1f",
            query[:60], len(bm25_results), bm25_results[0].score if bm25_results else 0.0, bm25_ms,
        )

        # Stage 3: RRF fusion
        t_rrf = time.monotonic()
        fused = reciprocal_rank_fusion(
            vector_results=vector_chunks,
            bm25_results=bm25_results,
            k=self._rrf_k,
            top_n=self._final_top_k,
        )
        rrf_ms = round((time.monotonic() - t_rrf) * 1000, 2)

        total_ms = round((time.monotonic() - t_total) * 1000, 2)

        timings = {
            "vector_search_ms": vector_ms,
            "bm25_ms": bm25_ms,
            "rrf_ms": rrf_ms,
            "total_retrieval_ms": total_ms,
        }

        logger.info(
            "stage=hybrid_retrieval query=%r vector=%d (%.1fms) bm25=%d (%.1fms) rrf=%.1fms fused=%d top_rrf=%.4f total=%.1fms",
            query[:60],
            len(vector_chunks), vector_ms,
            len(bm25_results), bm25_ms,
            rrf_ms,
            len(fused),
            fused[0].document.metadata.get("rrf_score", 0.0) if fused else 0.0,
            total_ms,
        )
        return fused, timings
