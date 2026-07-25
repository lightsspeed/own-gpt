"""EvaluationEngine — single orchestration layer for the entire evaluation pipeline.

Usage:
    config = EvaluationConfig(dataset="thinking_fast_and_slow")
    engine = EvaluationEngine(config)
    ctx = engine.run()
    # ctx.summary, ctx.results, ctx.gate_result, etc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.evaluation.benchmark import run_benchmark
from app.evaluation.loader import BenchmarkDataset, list_datasets, load_dataset
from app.evaluation.analytics import (
    generate_analytics_report,
    generate_coverage_report,
    generate_effectiveness_report,
    compute_weighted_scores,
)
from app.evaluation.regression import RegressionDetector
from app.evaluation.report import ReportGenerator
from app.evaluation.reporters.comparison_reporter import generate_comparison_report, find_baseline_run
from app.evaluation.trends import write_trend_report
from app.evaluation.reproducibility import collect_metadata

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    dataset: str
    category: Optional[str] = None
    report_dir: str = "reports"
    max_workers: int = 3
    base_url: str = "http://localhost:8000"
    retriever: Optional[str] = None
    compare: Optional[str] = None
    ci: bool = False
    pr_summary: bool = False
    top_failures: int = 0
    export_csv: bool = False


@dataclass
class BenchmarkContext:
    """Holds all state produced by the evaluation pipeline."""
    config: EvaluationConfig
    summary: dict = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)
    dataset_meta: Optional[BenchmarkDataset] = None
    gate_result: Optional[dict] = None
    baseline_summary: Optional[dict] = None
    error: Optional[str] = None


class EvaluationEngine:
    """Orchestrates the complete evaluation pipeline.

    Pipeline stages (in order):
      1. validate    — dataset & retriever validation
      2. benchmark   — run questions against backend
      3. analytics   — retrieval metrics, coverage, effectiveness, weighted scores
      4. reports     — write summary.json, results.json, CSV, HTML, metadata
      5. comparison  — diff vs baseline run (optional)
      6. gates       — regression threshold check
      7. trends      — update historical trend dashboard
      8. bundle      — index README at report root
    """

    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.ctx = BenchmarkContext(config=config)

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self) -> BenchmarkContext:
        if self.ctx.error:
            return self.ctx
        try:
            self._validate()
            if self.ctx.error:
                return self.ctx
            self._run_benchmark()
            self._generate_reports()        # must run before analytics (sets report_path)
            self._compute_analytics()        # enriches summary in-memory
            self._write_summary()            # persist enriched summary back to disk
            self._generate_comparison()
            self._check_gates()
            self._update_trends()
            self._write_bundle_readme()
        except Exception as e:
            logger.exception("Evaluation pipeline failed")
            self.ctx.error = str(e)
        return self.ctx

    # ── Stage 1: Validation ─────────────────────────────────────────────────

    def _validate(self):
        available = list_datasets()
        if self.config.dataset not in available:
            self.ctx.error = f"Dataset '{self.config.dataset}' not found. Available: {available}"
            return
        r = self.config.retriever
        if r and r not in ("hybrid", "vector", "bm25"):
            self.ctx.error = f"Invalid retriever '{r}'. Use: hybrid, vector, bm25"
            return
        self.ctx.dataset_meta = load_dataset(self.config.dataset)

    # ── Stage 2: Benchmark ──────────────────────────────────────────────────

    def _run_benchmark(self):
        if self.ctx.error:
            return
        result = run_benchmark(
            dataset_name=self.config.dataset,
            base_url=self.config.base_url,
            category=self.config.category,
            max_workers=self.config.max_workers,
            report_dir=self.config.report_dir,
            retriever=self.config.retriever,
        )
        self.ctx.summary = result["summary"]
        self.ctx.results = result["results"]

    # ── Stage 3: Analytics — coverage, effectiveness, weighted scores ────────

    def _compute_analytics(self):
        summary = self.ctx.summary
        results = self.ctx.results
        report_path = summary.get("report_path")
        if not report_path:
            return
        analytics_dir = Path(report_path) / "analytics"

        generate_analytics_report(results, analytics_dir)

        # Fetch corpus manifest for true coverage
        corpus_chunks = None
        try:
            import requests
            resp = requests.get(f"{self.config.base_url}/api/v1/index/corpus", timeout=10)
            if resp.status_code == 200:
                corpus_chunks = resp.json().get("chunks", [])
        except Exception:
            pass

        cov_path = generate_coverage_report(results, analytics_dir, corpus_chunks=corpus_chunks)
        eff_path = generate_effectiveness_report(results, analytics_dir)

        summary["coverage_path"] = str(cov_path)
        summary["effectiveness_path"] = str(eff_path)
        with open(cov_path) as f:
            summary["coverage"] = json.load(f)
        with open(eff_path) as f:
            summary["effectiveness"] = json.load(f)
        summary["weighted_scores"] = compute_weighted_scores(results)

    # ── Stage 4: Reports ────────────────────────────────────────────────────

    def _generate_reports(self):
        summary = self.ctx.summary
        results = self.ctx.results
        dataset = self.ctx.dataset_meta
        report_dir = self.config.report_dir
        if not report_dir or not dataset:
            return
        generator = ReportGenerator(report_dir)
        path = generator.generate(summary, results, dataset)
        summary["report_path"] = path

    # ── Write enriched summary back to disk ─────────────────────────────────

    def _write_summary(self):
        rp = self.ctx.summary.get("report_path")
        if rp:
            import json
            (Path(rp) / "summary.json").write_text(json.dumps(self.ctx.summary, indent=2, default=str))

    # ── Stage 5: Comparison vs baseline ─────────────────────────────────────

    def _generate_comparison(self):
        compare = self.config.compare
        summary = self.ctx.summary
        results = self.ctx.results
        if not compare or not summary.get("report_path"):
            return
        report_dir = Path(summary["report_path"])
        try:
            baseline = find_baseline_run(
                self.config.dataset,
                summary.get("retriever", "default"),
                Path(self.config.report_dir),
                compare,
                summary.get("timestamp", ""),
            )
            if baseline:
                self.ctx.baseline_summary = baseline
                base_dir = None
                if compare == "latest":
                    ds_dir = Path(self.config.report_dir) / self.config.dataset
                    if ds_dir.exists():
                        for run_dir in sorted(ds_dir.iterdir(), reverse=True):
                            sf = run_dir / "summary.json"
                            if sf.exists():
                                bs = json.loads(sf.read_text())
                                if bs.get("timestamp", "") < summary.get("timestamp", ""):
                                    base_dir = run_dir
                                    break
                else:
                    found = list(Path(self.config.report_dir).rglob(f"{compare}/summary.json"))
                    if found:
                        base_dir = found[0].parent
                if base_dir and (base_dir / "results.json").exists():
                    generate_comparison_report(
                        summary,
                        results,
                        baseline,
                        json.loads((base_dir / "results.json").read_text()),
                        report_dir,
                    )
        except Exception as e:
            logger.warning("Comparison skipped: %s", e)

    # ── Stage 6: Regression gates ───────────────────────────────────────────

    def _check_gates(self):
        detector = RegressionDetector(baseline_dir=self.config.report_dir)
        self.ctx.gate_result = detector.check_gates(self.ctx.summary)

    # ── Stage 7: Trends ────────────────────────────────────────────────────

    def _update_trends(self):
        try:
            write_trend_report(
                self.config.dataset,
                self.config.report_dir,
                self.ctx.summary.get("report_path"),
            )
        except Exception as e:
            logger.warning("Trend update skipped: %s", e)

    # ── Stage 8: Bundle README ──────────────────────────────────────────────

    def _write_bundle_readme(self):
        report_path = self.ctx.summary.get("report_path")
        if not report_path:
            return
        lines = [
            "# Benchmark Artifact Bundle",
            "",
            f"**Dataset:** {self.config.dataset}",
            f"**Retriever:** {self.ctx.summary.get('retriever', 'default')}",
            f"**Timestamp:** {self.ctx.summary.get('timestamp', '')[:19]}",
            f"**Gates:** {(self.ctx.gate_result or {}).get('status', 'N/A').upper()}",
            "",
            "## Contents",
            "",
            "| File | Description |",
            "|------|-------------|",
            "| `summary.json` | Run summary with scores, latencies, metadata |",
            "| `results.json` | Per-question results with claims, chunks, scores |",
            "| `results.csv` | Tabular per-question results |",
            "| `report.html` | Full HTML report with visualizations |",
            "| `metadata.json` | Environment and configuration metadata |",
            "| `analytics/retrieval_analytics.json` | Method distribution, average scores |",
            "| `analytics/retrieval_coverage.json` | Per-document chunk coverage statistics |",
            "| `analytics/method_effectiveness.json` | Vector-only vs BM25-only vs hybrid |",
            "| `comparison/comparison.json` | Machine-readable metric deltas vs baseline |",
            "| `comparison/comparison.csv` | Tabular metric comparison |",
            "| `comparison/comparison.html` | Visual comparison report |",
            "| `trends.html` | Historical trend charts |",
            "",
            "## Quick Stats",
            "",
            f"- Questions: {self.ctx.summary.get('total', '?')}",
            f"- Passed: {self.ctx.summary.get('successful', '?')}",
            f"- Failed: {self.ctx.summary.get('failed', '?')}",
            f"- Avg Latency: {self.ctx.summary.get('avg_latency_ms', 0):.0f}ms",
        ]
        s = self.ctx.summary
        if s.get("total"):
            lines.append(f"- Pass Rate: {s['successful'] / s['total'] * 100:.1f}%")
        (Path(report_path) / "README.md").write_text("\n".join(lines) + "\n")
