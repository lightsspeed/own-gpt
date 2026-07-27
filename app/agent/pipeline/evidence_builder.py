from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.langsmith import traceable
from app.models.evidence import EvidenceItem, ConfidenceLabel, RetrievalMethod, confidence_from_score
from .reranker import RankedChunk
from .source_policy import SourcePolicy, AnswerMode

logger = logging.getLogger(__name__)


@dataclass
class EvidenceBuilderResult:
    evidence: list[EvidenceItem] = field(default_factory=list)
    source_policy: Optional[SourcePolicy] = None
    total_candidates: int = 0
    total_cited: int = 0
    total_validated: int = 0

    @property
    def debug_dict(self) -> dict:
        return {
            "total_candidates": self.total_candidates,
            "total_cited": self.total_cited,
            "total_validated": self.total_validated,
        }


_CHUNK_REF_RE = re.compile(r'\[Chunk\s+(\d+)\]', re.IGNORECASE)


def _parse_chunk_references(response_text: str) -> list[int]:
    """Parse explicit [Chunk N] references from the LLM response."""
    indices = set()
    for match in _CHUNK_REF_RE.finditer(response_text):
        try:
            idx = int(match.group(1))
            if idx >= 0:
                indices.add(idx)
        except ValueError:
            continue
    return sorted(indices)


class EvidenceBuilder:
    """
    Builds evidence from chunks explicitly referenced by the LLM via [Chunk N] notation.

    Phase 2: Explicit citation parsing (replaces n-gram overlap Phase 1).
    Fallback: If no explicit references found, falls back to overlap matching.
    """

    def __init__(self, min_overlap: float = 0.15) -> None:
        self._min_overlap = min_overlap

    @traceable(name="evidence_builder", metadata={"stage": "evidence_builder"})
    def build(
        self,
        response_text: str,
        ranked_chunks: list[RankedChunk],
        source_policy: AnswerMode,
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

        # Phase 2: Parse explicit [Chunk N] references
        ref_indices = _parse_chunk_references(response_text)
        total_explicit = len(ref_indices)

        if ref_indices:
            logger.info(
                "stage=evidence_builder found %d explicit chunk references: %s",
                total_explicit, ref_indices,
            )
            cited_chunks: list[tuple[RankedChunk, int]] = []
            seen: set[int] = set()
            for idx in ref_indices:
                if idx < len(candidates) and idx not in seen:
                    seen.add(idx)
                    cited_chunks.append((candidates[idx], idx))
            total_cited = len(cited_chunks)
        else:
            # Fallback: n-gram overlap matching
            logger.info("stage=evidence_builder no explicit references — falling back to n-gram overlap")
            cited_chunks = self._find_cited_chunks_overlap(response_text, candidates)
            total_cited = len(cited_chunks)

        method = RetrievalMethod(meta.get("retrieval_method", "hybrid")) \
            if meta.get("retrieval_method") in ("vector", "bm25", "hybrid") \
            else RetrievalMethod.hybrid

        evidence_items: list[EvidenceItem] = []
        seen_doc_ids: set[str] = set()

        confidence = meta.get("confidence", 0.0)
        confidence_label = confidence_from_score(confidence)

        for rc, _ in cited_chunks:
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
            "stage=evidence_builder policy=%s candidates=%d explicit=%d cited=%d evidence=%d",
            source_policy.policy.value,
            total_candidates,
            total_explicit,
            total_cited,
            len(evidence_items),
        )

        return EvidenceBuilderResult(
            evidence=evidence_items,
            source_policy=source_policy.policy,
            total_candidates=total_candidates,
            total_cited=total_cited,
        )

    # ── Fallback: n-gram overlap ──────────────────────────────────────────────

    def _extract_ngrams(self, text: str, n: int = 5) -> set[str]:
        cleaned = re.sub(r'\s+', ' ', text.lower().strip())
        if len(cleaned) < n:
            return {cleaned}
        return {cleaned[i:i+n] for i in range(len(cleaned) - n + 1)}

    def _compute_overlap(self, response_text: str, chunk_text: str, threshold: float = 0.15) -> float:
        response_ngrams = self._extract_ngrams(response_text)
        chunk_ngrams = self._extract_ngrams(chunk_text)
        if not chunk_ngrams:
            return 0.0
        intersection = response_ngrams & chunk_ngrams
        return len(intersection) / len(chunk_ngrams)

    def _find_cited_chunks_overlap(
        self,
        response_text: str,
        ranked_chunks: list[RankedChunk],
    ) -> list[tuple[RankedChunk, float]]:
        cited: list[tuple[RankedChunk, float]] = []
        for rc in ranked_chunks:
            # Skip chunks with negative reranker scores (FlashRank scores < 0 mean cross-encoder evaluated chunk as irrelevant)
            score = getattr(rc, "reranker_score", None)
            if score is not None and score < 0.0:
                logger.info(
                    "skipping_irrelevant_evidence_chunk score=%.4f source=%s",
                    score, getattr(rc.chunk, "source", "unknown"),
                )
                continue
            chunk_text = rc.chunk.document.page_content
            overlap = self._compute_overlap(response_text, chunk_text, self._min_overlap)
            if overlap >= self._min_overlap:
                cited.append((rc, overlap))
        return cited