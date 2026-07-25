"""
Stage 6: Confidence Evaluation

Purpose: Combine multiple scoring signals into a single confidence score
         that drives the routing decision (answer / web_search / clarification).

This is the key decision-maker for a production RAG system.
A single retrieval score is never sufficient.

Signal weights:
  retrieval_score   (0.35) — average cosine similarity of top-3 chunks
  reranker_score    (0.40) — average cross-encoder score of top-3 (normalized)
  intent_confidence (0.15) — how certain the intent classifier was
  source_agreement  (0.10) — are answers coming from multiple independent sources?

Decision thresholds (configurable in pipeline_config.yaml):
  overall >= high_threshold  → "answer"        (serve response directly)
  overall >= medium_threshold → "web_search"   (augment with web results)
  overall <  medium_threshold → "clarification" (ask user to rephrase)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from app.core.langsmith import traceable
from .intent import IntentResult
from .reranker import RankedChunk

logger = logging.getLogger(__name__)

# FlashRank score range is approximately -10 to +10.
# We normalize to [0, 1] using: (score + 10) / 20
_RERANKER_MIN = -10.0
_RERANKER_MAX = 10.0

# Signal weights — must sum to 1.0
_W_RETRIEVAL  = 0.35
_W_RERANKER   = 0.40
_W_INTENT     = 0.15
_W_AGREEMENT  = 0.10


@dataclass
class ConfidenceResult:
    overall: float            # composite score [0.0, 1.0]
    retrieval_score: float
    reranker_score: float     # normalized to [0, 1]
    intent_confidence: float
    source_agreement: float
    decision: str             # "answer" | "web_search" | "clarification"


def _normalize_reranker(raw: float) -> float:
    """Convert FlashRank score to [0, 1]."""
    return max(0.0, min(1.0, (raw - _RERANKER_MIN) / (_RERANKER_MAX - _RERANKER_MIN)))


class ConfidenceEvaluator:
    """
    Produces a composite confidence score from multiple retrieval signals.
    No LLM calls — entirely rule-based computation.
    """

    def __init__(
        self,
        high_threshold: float = 0.70,
        medium_threshold: float = 0.45,
    ) -> None:
        self._high = high_threshold
        self._medium = medium_threshold

    @traceable(name="confidence_evaluator", metadata={"stage": 6})
    def evaluate(
        self,
        ranked_chunks: List[RankedChunk],
        intent: IntentResult,
    ) -> ConfidenceResult:
        """
        Compute confidence and make a routing decision.
        Returns a ConfidenceResult with overall score and decision.
        """
        if not ranked_chunks:
            result = ConfidenceResult(
                overall=0.0,
                retrieval_score=0.0,
                reranker_score=0.0,
                intent_confidence=round(intent.confidence, 4),
                source_agreement=0.0,
                decision="clarification",
            )
            logger.info(
                "stage=confidence_evaluation overall=0.0 decision=clarification (no chunks)",
            )
            return result

        top3 = ranked_chunks[:3]

        # Signal 1: Average retrieval score of top-3
        retrieval_score = round(
            sum(c.chunk.score for c in top3) / len(top3), 4
        )

        # Signal 2: Average normalized reranker score of top-3
        reranker_score = round(
            sum(_normalize_reranker(c.reranker_score) for c in top3) / len(top3), 4
        )

        # Signal 3: Intent confidence (already in [0, 1])
        intent_confidence = round(intent.confidence, 4)

        # Signal 4: Source diversity — more unique sources = higher agreement
        unique_sources = len({c.chunk.source for c in ranked_chunks})
        source_agreement = round(min(1.0, unique_sources / 3.0), 4)

        # Weighted composite
        overall = round(
            retrieval_score   * _W_RETRIEVAL +
            reranker_score    * _W_RERANKER  +
            intent_confidence * _W_INTENT    +
            source_agreement  * _W_AGREEMENT,
            4,
        )
        overall = min(1.0, max(0.0, overall))

        # Route decision
        if overall >= self._high:
            decision = "answer"
        elif overall >= self._medium:
            decision = "web_search"
        else:
            decision = "clarification"

        result = ConfidenceResult(
            overall=overall,
            retrieval_score=retrieval_score,
            reranker_score=reranker_score,
            intent_confidence=intent_confidence,
            source_agreement=source_agreement,
            decision=decision,
        )

        logger.info(
            "stage=confidence_evaluation overall=%.4f retrieval=%.4f "
            "reranker=%.4f intent=%.4f agreement=%.4f decision=%s",
            overall,
            retrieval_score,
            reranker_score,
            intent_confidence,
            source_agreement,
            decision,
        )
        return result
