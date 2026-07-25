from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.agent.pipeline.intent import IntentClassifier, Intent

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).resolve().parents[2] / "tests" / "rag" / "datasets" / "intent_accuracy"


@dataclass
class IntentAccuracyResult:
    overall: float
    by_intent: dict[str, float]
    by_rule: dict[str, float]
    total: int
    correct: int
    details: list[dict]


def load_intent_dataset(path: Optional[Path] = None) -> list[dict]:
    path = path or DATASET_PATH / "questions.jsonl"
    questions = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def evaluate_intent_accuracy(classifier: IntentClassifier | None = None) -> IntentAccuracyResult:
    questions = load_intent_dataset()
    if not questions:
        logger.warning("intent_accuracy_dataset_empty path=%s", DATASET_PATH)
        return IntentAccuracyResult(0.0, {}, {}, 0, 0, [])

    if classifier is None:
        classifier = IntentClassifier()

    correct = 0
    per_intent: dict[str, dict] = {}
    per_rule: dict[str, dict] = {}
    details = []

    for q in questions:
        query = q["query"]
        expected = q["expected_intent"]

        start = time.monotonic()
        result = classifier.classify(query)
        latency = round((time.monotonic() - start) * 1000, 1)

        is_correct = result.intent.value == expected
        if is_correct:
            correct += 1

        # Per-intent tracking
        if expected not in per_intent:
            per_intent[expected] = {"total": 0, "correct": 0, "latency_ms": []}
        per_intent[expected]["total"] += 1
        per_intent[expected]["latency_ms"].append(latency)
        if is_correct:
            per_intent[expected]["correct"] += 1

        # Per-rule tracking
        rule = result.matched_rule if result.matched_rule else "NO_RULE"
        if rule not in per_rule:
            per_rule[rule] = {"total": 0, "correct": 0}
        per_rule[rule]["total"] += 1
        if is_correct:
            per_rule[rule]["correct"] += 1

        details.append({
            "id": q["id"],
            "query": query,
            "expected": expected,
            "actual": result.intent.value,
            "correct": is_correct,
            "confidence": round(result.confidence, 2),
            "latency_ms": latency,
            "matched_rule": result.matched_rule,
            "used_llm": result.used_llm,
        })

    total = len(questions)
    overall = round(correct / total * 100, 1) if total else 0.0

    by_intent = {
        intent: round(stats["correct"] / stats["total"] * 100, 1)
        for intent, stats in sorted(per_intent.items())
    }

    by_rule = {
        rule: round(stats["correct"] / stats["total"] * 100, 1)
        for rule, stats in sorted(per_rule.items())
    }

    # Log per-intent latency
    logger.info(
        "intent_accuracy latency_ms avg=%.1f",
        sum(d["latency_ms"] for d in details) / len(details),
    )

    return IntentAccuracyResult(
        overall=overall,
        by_intent=by_intent,
        by_rule=by_rule,
        total=total,
        correct=correct,
        details=details,
    )


def print_intent_accuracy_report(result: IntentAccuracyResult) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  Intent Accuracy Report")
    lines.append("=" * 60)
    lines.append(f"  Overall:  {result.overall}%  ({result.correct}/{result.total})")
    lines.append("")
    lines.append("  By Intent:")
    for intent, pct in sorted(result.by_intent.items()):
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        lines.append(f"    {intent:15s} {pct:5.1f}% {bar}")
    lines.append("")
    lines.append("  By Rule:")
    for rule, pct in sorted(result.by_rule.items()):
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        lines.append(f"    {rule:25s} {pct:5.1f}% {bar}")
    lines.append("")
    lines.append("  Failures:")
    failures = [d for d in result.details if not d["correct"]]
    if failures:
        for d in failures[:10]:
            lines.append(f"    {d['id']:15s} expected={d['expected']:12s} actual={d['actual']:12s}  query=\"{d['query']}\"")
        if len(failures) > 10:
            lines.append(f"    ... and {len(failures) - 10} more")
    else:
        lines.append("    None")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = evaluate_intent_accuracy()
    print(print_intent_accuracy_report(result))
