from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from app.agent.pipeline.claim_extractor import Claim
from .claim_extractor import Claim
from .reranker import RankedChunk


@dataclass
class ClaimValidation:
    claim: Claim
    supported: bool
    best_chunk_idx: int
    best_chunk_text: str
    best_score: float
    document_name: str
    threshold: float


@dataclass
class GroundingResult:
    validations: List[ClaimValidation] = field(default_factory=list)
    all_supported: bool = True
    unsupported_count: int = 0
    total_count: int = 0


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(av * bv for av, bv in zip(a, b))
    na = math.sqrt(sum(av * av for av in a))
    nb = math.sqrt(sum(bv * bv for bv in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class GroundingValidator:
    """
    Deterministic claim-level grounding validator.

    For each claim extracted from the LLM response, computes embedding similarity
    against every retrieved chunk. If the best similarity is below threshold,
    the claim is flagged as unsupported.
    """

    # Embedding similarity threshold — claims scoring below this are unsupported
    STRICT_THRESHOLD = 0.55
    HYBRID_THRESHOLD = 0.45

    def __init__(self, embed_fn):
        self._embed_fn = embed_fn

    def validate(
        self,
        claims: List[Claim],
        chunks: List[RankedChunk],
        threshold: Optional[float] = None,
        strict: bool = True,
    ) -> GroundingResult:
        if not claims or not chunks:
            return GroundingResult()

        if threshold is None:
            threshold = self.STRICT_THRESHOLD if strict else self.HYBRID_THRESHOLD

        chunk_texts = [c.chunk.document.page_content for c in chunks]

        # Batch-embed all claims and all chunks (2 API calls total)
        claim_embeddings = self._embed_fn([c.text for c in claims])
        chunk_embeddings = self._embed_fn(chunk_texts)

        validations: List[ClaimValidation] = []
        unsupported_count = 0

        for i, claim in enumerate(claims):
            best_score = 0.0
            best_j = -1
            for j, chunk_emb in enumerate(chunk_embeddings):
                score = _cosine_similarity(claim_embeddings[i], chunk_emb)
                if score > best_score:
                    best_score = score
                    best_j = j

            supported = best_score >= threshold
            if not supported:
                unsupported_count += 1

            doc_name = ""
            if best_j >= 0:
                md = chunks[best_j].chunk.document.metadata or {}
                doc_name = md.get("source", md.get("filename", md.get("title", "")))

            validations.append(ClaimValidation(
                claim=claim,
                supported=supported,
                best_chunk_idx=best_j,
                best_chunk_text=chunk_texts[best_j] if best_j >= 0 else "",
                best_score=round(best_score, 4),
                document_name=doc_name,
                threshold=threshold,
            ))

        return GroundingResult(
            validations=validations,
            all_supported=unsupported_count == 0,
            unsupported_count=unsupported_count,
            total_count=len(claims),
        )