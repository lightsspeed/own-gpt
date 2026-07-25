"""
Comparator — computes objective differences between baseline and candidate metrics.

No opinions, no recommendations. Only measurements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .models import ExperimentResult

logger = logging.getLogger(__name__)


@dataclass
class ComparisonReport:
    """Structured comparison between baseline and candidate."""
    experiment_id: str = ""
    metrics: dict = field(default_factory=dict)
    wins: list[str] = field(default_factory=list)     # metrics where candidate improved
    losses: list[str] = field(default_factory=list)    # metrics where candidate regressed
    unchanged: list[str] = field(default_factory=list) # metrics where candidate tied
    overall_verdict: str = ""    # "improvement", "regression", "mixed", "inconclusive"

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "metrics": self.metrics,
            "wins": self.wins,
            "losses": self.losses,
            "unchanged": self.unchanged,
            "overall_verdict": self.overall_verdict,
        }


class Comparator:
    """Compare baseline to candidate and produce objective measurements."""

    IMPROVEMENT_METRICS = frozenset({
        "avg_confidence", "accept_rate", "avg_reranker_score",
        "faithfulness", "context_precision", "context_recall",
    })
    REGRESSION_METRICS = frozenset({
        "avg_latency_ms", "avg_tokens_out",
    })

    def compare(self, result: ExperimentResult) -> ComparisonReport:
        """Produce a structured comparison from experiment results."""
        deltas = result.deltas
        wins, losses, unchanged = [], [], []

        for key, delta in deltas.items():
            if not isinstance(delta, dict) or "absolute" not in delta:
                continue
            abs_val = delta.get("absolute", 0)
            if abs_val == 0:
                unchanged.append(key)
            elif key in self.IMPROVEMENT_METRICS:
                if abs_val > 0:
                    wins.append(key)
                else:
                    losses.append(key)
            elif key in self.REGRESSION_METRICS:
                if abs_val < 0:
                    wins.append(key)
                else:
                    losses.append(key)
            else:
                # Unknown metric — positive delta is a win, negative is a loss
                if abs_val > 0:
                    wins.append(key)
                elif abs_val < 0:
                    losses.append(key)

        # Overall verdict
        win_count = len(wins)
        loss_count = len(losses)
        if win_count > 0 and loss_count == 0:
            verdict = "improvement"
        elif loss_count > 0 and win_count == 0:
            verdict = "regression"
        elif win_count > loss_count:
            verdict = "mixed_positive"
        elif loss_count > win_count:
            verdict = "mixed_negative"
        elif win_count == 0 and loss_count == 0:
            verdict = "inconclusive"
        else:
            verdict = "mixed"

        return ComparisonReport(
            experiment_id=result.experiment_id,
            metrics=deltas,
            wins=wins,
            losses=losses,
            unchanged=unchanged,
            overall_verdict=verdict,
        )


def build_decision_candidate(
    experiment_id: str,
    comparison: ComparisonReport,
    recommendation_id: Optional[str] = None,
) -> "DecisionCandidate":
    """Auto-generate a DecisionCandidate from experiment results."""
    from .models import DecisionCandidate

    if comparison.overall_verdict in ("improvement", "mixed_positive"):
        decision = "adopt"
        rationale = f"Experiment {experiment_id} shows improvement in {len(comparison.wins)} metrics"
        risks = []
        if comparison.losses:
            risks.append(f"Regression in: {', '.join(comparison.losses)}")
    elif comparison.overall_verdict in ("regression", "mixed_negative"):
        decision = "reject"
        rationale = f"Experiment {experiment_id} shows regression in {len(comparison.losses)} metrics"
        risks = [f"Would degrade: {', '.join(comparison.losses)}"]
    else:
        decision = "modify"
        rationale = f"Experiment {experiment_id} results are inconclusive — further tuning needed"
        risks = ["Insufficient evidence for clear decision"]

    return DecisionCandidate(
        experiment_id=experiment_id,
        recommendation_id=recommendation_id,
        decision=decision,
        rationale=rationale,
        supporting_metrics=comparison.metrics,
        risks=risks,
    )
