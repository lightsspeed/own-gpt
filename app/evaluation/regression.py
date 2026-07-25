from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLDS = {
    "faithfulness": 0.05,
    "answer_relevancy": 0.05,
    "context_precision": 0.05,
    "context_recall": 0.05,
    "overall": 0.03,
    "avg_latency_ms": 0.15,
}

_DEFAULT_MINIMUM_THRESHOLDS = {
    "minimum_faithfulness": 0.93,
    "minimum_answer_relevancy": 0.92,
    "minimum_context_precision": 0.90,
    "minimum_context_recall": 0.90,
    "maximum_latency_ms": 2500,
}


def _load_evaluation_config(config_path: Optional[str] = None) -> dict:
    """Load evaluation thresholds from YAML config."""
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg.get("evaluation", {})
    # Fallback: check common locations
    for candidate in ["pipeline_config.yaml", "../pipeline_config.yaml"]:
        if Path(candidate).exists():
            with open(candidate) as f:
                cfg = yaml.safe_load(f)
            return cfg.get("evaluation", {})
    return {}


class RegressionDetector:
    def __init__(self, baseline_dir: Optional[str] = None, config_path: Optional[str] = None):
        self._baseline_dir = Path(baseline_dir) if baseline_dir else None
        eval_cfg = _load_evaluation_config(config_path)
        self._min_thresholds = {
            "minimum_faithfulness": eval_cfg.get("minimum_faithfulness", _DEFAULT_MINIMUM_THRESHOLDS["minimum_faithfulness"]),
            "minimum_answer_relevancy": eval_cfg.get("minimum_answer_relevancy", _DEFAULT_MINIMUM_THRESHOLDS["minimum_answer_relevancy"]),
            "minimum_context_precision": eval_cfg.get("minimum_context_precision", _DEFAULT_MINIMUM_THRESHOLDS["minimum_context_precision"]),
            "minimum_context_recall": eval_cfg.get("minimum_context_recall", _DEFAULT_MINIMUM_THRESHOLDS["minimum_context_recall"]),
            "maximum_latency_ms": eval_cfg.get("maximum_latency_ms", _DEFAULT_MINIMUM_THRESHOLDS["maximum_latency_ms"]),
        }
        # Warning zone: within this fraction of the threshold triggers WARNING instead of PASS
        self._warning_zone = eval_cfg.get("warning_zone", 0.02)

    def _load_latest_baseline(self, dataset_name: str) -> Optional[dict]:
        if not self._baseline_dir or not self._baseline_dir.exists():
            return None
        dataset_dir = self._baseline_dir / dataset_name
        if not dataset_dir.exists():
            return None
        runs = sorted(dataset_dir.iterdir(), reverse=True)
        if not runs:
            return None
        latest = runs[0]
        summary_file = latest / "summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                return json.load(f)
        return None

    def check_gates(self, current_summary: dict) -> dict:
        """Check absolute minimum quality thresholds. Returns PASS/WARNING/FAIL with three levels."""
        scores = current_summary.get("ragas_scores", {})
        failures = []
        warnings = []
        passes = []

        metric_map = {
            "faithfulness": "minimum_faithfulness",
            "answer_relevancy": "minimum_answer_relevancy",
            "context_precision": "minimum_context_precision",
            "context_recall": "minimum_context_recall",
        }

        for metric, threshold_key in metric_map.items():
            min_val = self._min_thresholds.get(threshold_key, 0.0)
            actual = scores.get(metric, 0) or 0
            if min_val == 0:
                passes.append({"gate": threshold_key, "metric": metric, "status": "skipped"})
                continue
            # FAIL if below minimum
            if actual < min_val:
                failures.append({
                    "gate": threshold_key,
                    "metric": metric,
                    "minimum": min_val,
                    "actual": round(actual, 4),
                    "delta": round(actual - min_val, 4),
                    "status": "fail",
                })
            # WARNING if within warning zone
            elif actual < min_val * (1 + self._warning_zone):
                warnings.append({
                    "gate": threshold_key,
                    "metric": metric,
                    "minimum": min_val,
                    "actual": round(actual, 4),
                    "delta": round(actual - min_val, 4),
                    "status": "warning",
                })
            else:
                passes.append({
                    "gate": threshold_key,
                    "metric": metric,
                    "minimum": min_val,
                    "actual": round(actual, 4),
                    "status": "pass",
                })

        max_latency = self._min_thresholds.get("maximum_latency_ms", 99999)
        actual_latency = current_summary.get("avg_latency_ms", 0)
        if max_latency < 99999:
            if actual_latency > max_latency:
                failures.append({
                    "gate": "maximum_latency_ms",
                    "metric": "avg_latency_ms",
                    "minimum": max_latency,
                    "actual": round(actual_latency, 2),
                    "delta": round(actual_latency - max_latency, 2),
                    "status": "fail",
                })
            elif actual_latency > max_latency * (1 - self._warning_zone):
                warnings.append({
                    "gate": "maximum_latency_ms",
                    "metric": "avg_latency_ms",
                    "minimum": max_latency,
                    "actual": round(actual_latency, 2),
                    "delta": round(actual_latency - max_latency, 2),
                    "status": "warning",
                })
            else:
                passes.append({
                    "gate": "maximum_latency_ms",
                    "metric": "avg_latency_ms",
                    "minimum": max_latency,
                    "actual": round(actual_latency, 2),
                    "status": "pass",
                })

        if failures:
            overall_status = "fail"
        elif warnings:
            overall_status = "warning"
        else:
            overall_status = "pass"

        return {
            "status": overall_status,
            "gates_passed": len(passes),
            "gates_warned": len(warnings),
            "gates_failed": len(failures),
            "passes": passes,
            "warnings": warnings,
            "failures": failures,
            "ci_exit_code": 1 if overall_status == "fail" else 0,
        }

    def detect(
        self,
        current_summary: dict,
        dataset_name: str,
        thresholds: Optional[dict] = None,
    ) -> dict:
        baseline = self._load_latest_baseline(dataset_name)
        if not baseline:
            return {"status": "no_baseline", "regressions": []}

        t = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}
        regressions = []
        metrics_to_check = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]

        current_scores = current_summary.get("ragas_scores", {})
        baseline_scores = baseline.get("ragas_scores", {})

        for metric in metrics_to_check:
            curr = current_scores.get(metric, 0) or 0
            base = baseline_scores.get(metric, 0) or 0
            threshold = t.get(metric, 0.05)
            if base > 0 and (curr - base) < -threshold:
                regressions.append({
                    "metric": metric,
                    "baseline": round(base, 4),
                    "current": round(curr, 4),
                    "delta": round(curr - base, 4),
                    "threshold": threshold,
                })

        curr_latency = current_summary.get("avg_latency_ms", 0)
        base_latency = baseline.get("avg_latency_ms", 0)
        latency_threshold = t.get("avg_latency_ms", 0.15)
        if base_latency > 0 and curr_latency > base_latency * (1 + latency_threshold):
            regressions.append({
                "metric": "avg_latency_ms",
                "baseline": round(base_latency, 2),
                "current": round(curr_latency, 2),
                "delta": round(curr_latency - base_latency, 2),
                "threshold": f"{latency_threshold*100:.0f}%",
            })

        status = "regression" if regressions else "pass"
        return {
            "status": status,
            "regressions": regressions,
            "baseline_run": baseline.get("timestamp", "unknown"),
            "current_run": current_summary.get("timestamp", ""),
        }
