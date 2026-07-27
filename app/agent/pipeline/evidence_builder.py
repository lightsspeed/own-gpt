"""
Evidence Builder: Produces evidence items from chunks that were ACTUALLY CITED
in the final response, not from all retrieved chunks.

Phase 1: N-gram overlap matching (deterministic, zero cost)
Phase 2: (Future) LLM-based citation verification

Design principle:
  Never cite what was retrieved. Only cite what was actually used.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.langsmith import traceable
from app.models.evidence import EvidenceItem, ConfidenceLabel, RetrievalMethod, confidence_from_score
from .reranker import RankedChunk
from .source_policy import SourcePolicy, SourcePolicyResult

logger = logging.getLogger(__name__)


@dataclass
class EvidenceBuilderResult:
    evidence: list[EvidenceItem] = field(default_factory=list)
    source_policy: Optional[SourcePolicy] = None
    total_candidates: int = 0
    total_cited: int = 0


def _extract_ngrams(text: str, n: int = 5) -> set[str]:
    """Extract character n-grams from normalized text for overlap matching."""
    cleaned = re.sub(r'\s+', ' ', text.lower().strip())
    if len(cleaned) < n:
        return {cleaned}
    return {cleaned[i:i+n] for i in range(len(cleaned) - n + 1)}


def _compute_overlap(response_text: str, chunk_text: str, threshold: float = 0.15) -> float:
    """Compute character n-gram overlap between response and chunk."""
    response_ngrams = _extract_ngrams(response_text)
    chunk_ngrams = _extract_ngrams(chunk_text)
    if not chunk_ngrams:
        return 0.0
    intersection = response_ngrams & chunk_ngrams
    return len(intersection) / len(chunk_ngrams)


def _find_cited_chunks(
    response_text: str,
    ranked_chunks: list[RankedChunk],
    min_overlap: float = 0.15,
) -> list[tuple[RankedChunk, float]]:
    """Return chunks whose content overlaps significantly with the response."""
    cited: list[tuple[RankedChunk, float]] = []
    for rc in ranked_chunks:
        chunk_text = rc.chunk.document.page_content
        overlap = _compute_overlap(response_text, chunk_text, min_overlap)
        if overlap >= min_overlap:
            cited.append((rc, overlap))
    return cited


class EvidenceBuilder:
    """
    Builds evidence from chunks that were actually cited in the LLM response.
    Uses n-gram overlap matching to determine citation.
    """

    def __init__(self, min_overlap: float = 0.15) -> None:
        self._min_overlap = min_overlap

    @traceable(name="evidence_builder", metadata={"stage": "evidence_builder"})
    def build(
        self,
        response_text: str,
        ranked_chunks: list[RankedChunk],
        source_policy: SourcePolicyResult,
        answer_mode: str = "grounded",
        answer_mode_metadata: dict | None = None,
    ) -> EvidenceBuilderResult:
        meta = answer_mode_metadata or {}

        if source_policy.policy == SourcePolicy.NONE:
            logger.info("stage=evidence_builder policy=none — no evidence")
            return EvidenceBuilderResult(
                evidence=[],
                source_policy=source_policy.policy,
                total_candidates=0,
                total_cited=0,
            )

        candidates = ranked_chunks
        total_candidates = len(candidates)

        cited = _find_cited_chunks(response_text, candidates, self._min_overlap)
        total_cited = len(cited)

        method = RetrievalMethod(meta.get("retrieval_method", "hybrid")) \
            if meta.get("retrieval_method") in ("vector", "bm25", "hybrid") \
            else RetrievalMethod.hybrid

        evidence_items: list[EvidenceItem] = []
        seen_doc_ids: set[str] = set()

        confidence = meta.get("confidence", 0.0)
        confidence_label = confidence_from_score(confidence)

        for rc, overlap in cited:
            chunk = rc.chunk
            doc_id = getattr(chunk, "chunk_id", None) or f"cited-{len(evidence_items)}"
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)

            src = getattr(chunk, "source", None) or getattr(chunk, "filename", None) or "unknown"

            evidence_items.append(EvidenceItem(
                id=doc_id,
                title=src,
                source_type="knowledge",
                chunk=chunk.document.page_content[:300] if hasattr(chunk, "document") else "",
                confidence_label=confidence_label,
                retrieval_method=method,
                chunk_index=rc.reranked_rank if hasattr(rc, "reranked_rank") else None,
                total_chunks=total_cited,
                document_id=src,
                raw_score=chunk.score if hasattr(chunk, "score") else None,
                reranker_score=getattr(rc, "reranker_score", None),
            ))

        logger.info(
            "stage=evidence_builder policy=%s candidates=%d cited=%d evidence=%d",
            source_policy.policy.value,
            total_candidates,
            total_cited,
            len(evidence_items),
        )

        return EvidenceBuilderResult(
            evidence=evidence_items,
            source_policy=source_policy.policy,
            total_candidates=total_candidates,
            total_cited=total_cited,
        )