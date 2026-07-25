from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class RagasRunner:
    """Evaluate RAG answers using ragas metrics (faithfulness, relevancy, precision, recall)."""

    def __init__(self, llm: Optional[str] = None, embeddings: Optional[str] = None):
        self._llm = llm
        self._embeddings = embeddings

    def evaluate(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: Optional[list[str]] = None,
    ) -> dict:
        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            from datasets import Dataset
        except ImportError:
            logger.error("ragas or datasets not installed. Run: pip install ragas")
            return {"error": "ragas not installed"}

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        if ground_truths:
            data["ground_truth"] = ground_truths

        dataset = Dataset.from_dict(data)

        metrics = [faithfulness, answer_relevancy]
        if all(len(c) > 0 for c in contexts):
            metrics.extend([context_precision, context_recall])

        try:
            result = evaluate(dataset, metrics=metrics)
            scores = {}
            for metric in metrics:
                key = metric.name
                values = result[key]
                scores[key] = sum(values) / len(values) if values else 0.0
            logger.info("Ragas evaluation complete: %s", scores)
            return scores
        except Exception as exc:
            logger.error("Ragas evaluation failed: %s", exc)
            return {"error": str(exc)}


def run_ragas_evaluation(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: Optional[list[str]] = None,
) -> dict:
    runner = RagasRunner()
    return runner.evaluate(questions, answers, contexts, ground_truths)
