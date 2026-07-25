"""
ReplayRunner — re-executes historical Learning Records against candidate configurations.

This is the core of the offline experimentation framework. It does NOT call the
live inference pipeline. Instead, it uses stored data to simulate what would change,
computing counterfactual metrics from the Learning Ledger.

Supported parameter changes (extensible):
  - reranker_threshold: re-apply threshold to stored reranker_scores
  - confidence_threshold: re-compute filtered acceptance
  - retriever_top_k: simulate reduced top-k (can only decrease, not increase)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..storage.sqlite import LearningStore
from .models import (
    ExperimentDefinition, ExperimentResult, ParameterChange, ParameterDomain,
)

logger = logging.getLogger(__name__)


class ReplayRunner:
    """Replay historical records against a candidate configuration."""

    def __init__(self, store: Optional[LearningStore] = None):
        self._store = store or LearningStore()

    def run(self, experiment: ExperimentDefinition, limit: int = 500) -> ExperimentResult:
        """Execute an experiment against stored records."""
        start = time.time()
        records = self._store.query_sql("""
            SELECT * FROM learning_records
            ORDER BY timestamp DESC
            LIMIT ?
        """, [limit])

        baseline_metrics = self._compute_baseline(records)
        candidate_metrics = self._compute_candidate(records, experiment.parameter_changes)
        deltas = self._compute_deltas(baseline_metrics, candidate_metrics)

        duration = (time.time() - start) * 1000
        summary = self._build_summary(experiment, deltas, len(records))

        return ExperimentResult(
            experiment_id=experiment.id,
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            deltas=deltas,
            summary=summary,
            records_processed=len(records),
            duration_ms=duration,
            completed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        )

    def _compute_baseline(self, records: list[dict]) -> dict:
        """Compute metrics from actual stored values (the baseline config)."""
        if not records:
            return {}
        n = len(records)
        confs = [r.get("confidence", 0) or 0 for r in records]
        accepted = [1 if r.get("accepted") else 0 for r in records]
        reranker_scores = self._collect_reranker_scores(records)
        tokens_out = [r.get("tokens_out", 0) or 0 for r in records]
        latencies = [r.get("latency_ms", 0) or 0 for r in records]

        return {
            "count": n,
            "avg_confidence": round(sum(confs) / n, 3) if n else 0,
            "accept_rate": round(sum(accepted) / n, 3) if n else 0,
            "avg_reranker_score": round(sum(reranker_scores) / len(reranker_scores), 3) if reranker_scores else None,
            "avg_tokens_out": round(sum(tokens_out) / n, 1) if n else 0,
            "avg_latency_ms": round(sum(latencies) / n, 1) if n else 0,
        }

    def _compute_candidate(self, records: list[dict], changes: list[ParameterChange]) -> dict:
        """Compute metrics as-if the candidate parameter changes were applied."""
        if not records or not changes:
            return {}

        # Start with baseline values
        applied = dict(records[0]) if records else {}
        n = len(records)

        # Apply each parameter change
        confs = [r.get("confidence", 0) or 0 for r in records]
        accepted = [1 if r.get("accepted") else 0 for r in records]
        reranker_scores = self._collect_reranker_scores(records)
        tokens_out = [r.get("tokens_out", 0) or 0 for r in records]
        latencies = [r.get("latency_ms", 0) or 0 for r in records]

        for change in changes:
            if change.domain == ParameterDomain.RERANKER_THRESHOLD:
                # Simulate: records with reranker score below threshold would have been excluded
                threshold = float(change.candidate)
                if reranker_scores:
                    filtered_indices = []
                    for i, record in enumerate(records):
                        raw = record.get("reranker_scores", "[]")
                        try:
                            scores = json.loads(raw) if isinstance(raw, str) else (raw or [])
                            avg = sum(scores) / len(scores) if scores else 0
                            if avg >= threshold:
                                filtered_indices.append(i)
                        except (json.JSONDecodeError, TypeError, ZeroDivisionError):
                            filtered_indices.append(i)
                    if filtered_indices:
                        confs = [confs[i] for i in filtered_indices]
                        accepted = [accepted[i] for i in filtered_indices]
                        tokens_out = [tokens_out[i] for i in filtered_indices]
                        latencies = [latencies[i] for i in filtered_indices]
                        reranker_scores = [reranker_scores[i] for i in filtered_indices if i < len(reranker_scores)]

            elif change.domain == ParameterDomain.CONFIDENCE_THRESHOLD:
                # Simulate: only show answers above confidence threshold
                threshold = float(change.candidate)
                filtered = [(c, a, t, l, rs) for c, a, t, l, rs in
                           zip(confs, accepted, tokens_out, latencies, reranker_scores)
                           if c >= threshold]
                if filtered:
                    confs = [f[0] for f in filtered]
                    accepted = [f[1] for f in filtered]
                    tokens_out = [f[2] for f in filtered]
                    latencies = [f[3] for f in filtered]
                    reranker_scores = [f[4] for f in filtered]

            elif change.domain == ParameterDomain.RETRIEVER_TOP_K:
                # Simulate: reduce top-k (can only decrease what we can see)
                k = int(change.candidate)
                baseline_k = int(change.baseline) if change.baseline else 10
                if k < baseline_k and reranker_scores:
                    # Keep top-k scored records
                    scored = list(enumerate(reranker_scores))
                    scored.sort(key=lambda x: -x[1])
                    keep_indices = {idx for idx, _ in scored[:k]}
                    confs = [c for i, c in enumerate(confs) if i in keep_indices]
                    accepted = [a for i, a in enumerate(accepted) if i in keep_indices]
                    tokens_out = [t for i, t in enumerate(tokens_out) if i in keep_indices]
                    latencies = [l for i, l in enumerate(latencies) if i in keep_indices]
                    reranker_scores = [rs for i, rs in enumerate(reranker_scores) if i in keep_indices]

        n_candidate = len(confs)
        return {
            "count": n_candidate,
            "avg_confidence": round(sum(confs) / n_candidate, 3) if n_candidate else 0,
            "accept_rate": round(sum(accepted) / n_candidate, 3) if n_candidate else 0,
            "avg_reranker_score": round(sum(reranker_scores) / len(reranker_scores), 3) if reranker_scores else None,
            "avg_tokens_out": round(sum(tokens_out) / n_candidate, 1) if n_candidate else 0,
            "avg_latency_ms": round(sum(latencies) / n_candidate, 1) if n_candidate else 0,
        }

    def _compute_deltas(self, baseline: dict, candidate: dict) -> dict:
        """Compute difference between candidate and baseline metrics."""
        deltas = {}
        all_keys = set(baseline.keys()) | set(candidate.keys())
        for k in all_keys:
            b = baseline.get(k)
            c = candidate.get(k)
            if b is not None and c is not None and isinstance(b, (int, float)) and isinstance(c, (int, float)):
                abs_diff = round(c - b, 3)
                pct_diff = round(((c - b) / abs(b) * 100), 1) if b != 0 else None
                deltas[k] = {
                    "baseline": b,
                    "candidate": c,
                    "absolute": abs_diff,
                    "percent": pct_diff,
                }
            elif k == "count":
                deltas[k] = {"baseline": b, "candidate": c}
        return deltas

    def _collect_reranker_scores(self, records: list[dict]) -> list[float]:
        """Extract all stored reranker scores into a flat list."""
        scores = []
        for r in records:
            raw = r.get("reranker_scores", "[]")
            try:
                rec_scores = json.loads(raw) if isinstance(raw, str) else (raw or [])
                scores.extend(rec_scores)
            except (json.JSONDecodeError, TypeError):
                pass
        return scores

    def _build_summary(self, experiment: ExperimentDefinition, deltas: dict, n: int) -> str:
        """Generate a human-readable summary of the experiment results."""
        parts = [f"Experiment '{experiment.name}' over {n} records."]
        for param in experiment.parameter_changes:
            parts.append(f"Changed {param.parameter} from {param.baseline} to {param.candidate}.")
        for key, delta in deltas.items():
            if isinstance(delta, dict) and "percent" in delta and delta["percent"] is not None:
                arrow = "▲" if delta["absolute"] > 0 else "▼" if delta["absolute"] < 0 else "—"
                parts.append(f"{key}: {delta['candidate']} ({arrow} {delta['percent']:+.1f}%)")
        return " ".join(parts)
