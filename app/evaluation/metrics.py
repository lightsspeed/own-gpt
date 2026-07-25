from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    overall: float = 0.0
    retrieval_precision: float = 0.0
    retrieval_recall: float = 0.0
    retrieval_mrr: float = 0.0
    latency_ms: float = 0.0
    total_tokens: int = 0

    @classmethod
    def from_ragas(cls, scores: dict) -> EvaluationMetrics:
        metrics = cls()
        metrics.faithfulness = scores.get("faithfulness", 0.0) or 0.0
        metrics.answer_relevancy = scores.get("answer_relevancy", 0.0) or 0.0
        metrics.context_precision = scores.get("context_precision", 0.0) or 0.0
        metrics.context_recall = scores.get("context_recall", 0.0) or 0.0
        scores_list = [v for v in [metrics.faithfulness, metrics.answer_relevancy, metrics.context_precision, metrics.context_recall] if v > 0]
        metrics.overall = sum(scores_list) / len(scores_list) if scores_list else 0.0
        return metrics

    def to_dict(self) -> dict:
        return {
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevancy": round(self.answer_relevancy, 4),
            "context_precision": round(self.context_precision, 4),
            "context_recall": round(self.context_recall, 4),
            "overall": round(self.overall, 4),
            "retrieval_precision": round(self.retrieval_precision, 4),
            "retrieval_recall": round(self.retrieval_recall, 4),
            "retrieval_mrr": round(self.retrieval_mrr, 4),
            "latency_ms": round(self.latency_ms, 2),
            "total_tokens": self.total_tokens,
        }


def compute_retrieval_metrics(
    retrieved_chunk_ids: list[str],
    expected_source_ids: list[str],
) -> dict:
    if not expected_source_ids:
        return {"precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0}

    relevant_retrieved = [c for c in retrieved_chunk_ids if c in expected_source_ids]
    precision = len(relevant_retrieved) / len(retrieved_chunk_ids) if retrieved_chunk_ids else 0.0
    recall = len(relevant_retrieved) / len(expected_source_ids) if expected_source_ids else 0.0

    mrr = 0.0
    for rank, c in enumerate(retrieved_chunk_ids, 1):
        if c in expected_source_ids:
            mrr = 1.0 / rank
            break

    hit = 1.0 if relevant_retrieved else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "mrr": round(mrr, 4),
        "hit_rate": hit,
    }
