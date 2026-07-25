from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.evaluation.loader import BenchmarkDataset
from app.evaluation.reporters.html_reporter import generate_html_report
from app.evaluation.reproducibility import collect_metadata

logger = logging.getLogger(__name__)


def generate_report(results: list, dataset_name: str, output_dir: str = "reports") -> str:
    from app.evaluation.loader import load_dataset
    successful = [r for r in results if r.get("status") == "success"]
    latencies = [r.get("latency_ms", 0) for r in successful]
    summary = {
        "dataset": dataset_name,
        "display_name": dataset_name,
        "total": len(results),
        "successful": len(successful),
        "failed": len(results) - len(successful),
        "timestamp": datetime.utcnow().isoformat(),
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "ragas_scores": {},
    }
    dataset = load_dataset(dataset_name) if dataset_name else None
    generator = ReportGenerator(output_dir)
    return generator.generate(summary, results, dataset or BenchmarkDataset(name=dataset_name, display_name=dataset_name, description=""))


class ReportGenerator:
    def __init__(self, report_dir: str = "reports"):
        self._base_dir = Path(report_dir)

    def generate(
        self,
        summary: dict,
        results: list[dict],
        dataset: BenchmarkDataset,
    ) -> str:
        dataset_name = summary["dataset"]
        timestamp = datetime.fromisoformat(summary["timestamp"])
        run_dir = self._base_dir / dataset_name / timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_summary(summary, run_dir)
        self._write_results_json(results, run_dir)
        self._write_results_csv(results, run_dir)
        self._write_failures(results, run_dir)
        generate_html_report(summary, results, dataset, run_dir)
        self._write_metadata(summary, run_dir)

        logger.info("Report generated at %s", run_dir)
        return str(run_dir)

    def _write_summary(self, summary: dict, run_dir: Path):
        with open(run_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)

    def _write_results_json(self, results: list[dict], run_dir: Path):
        with open(run_dir / "results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

    def _write_results_csv(self, results: list[dict], run_dir: Path):
        if not results:
            return
        fieldnames = [
            "id", "category", "difficulty", "status", "question",
            "latency_ms", "missing_claims", "hallucinated_terms", "error",
        ]
        with open(run_dir / "results.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)

    def _write_failures(self, results: list[dict], run_dir: Path):
        failures = [r for r in results if r["status"] != "success"]
        for r in results:
            if r.get("missing_claims") or r.get("hallucinated_terms"):
                failures.append(r)
        if not failures:
            return
        failures_dir = run_dir / "failures"
        failures_dir.mkdir(exist_ok=True)
        for f_result in failures:
            safe_id = f_result.get("id", "unknown").replace("/", "_").replace("\\", "_")
            artifact = {
                "id": f_result.get("id"),
                "question": f_result.get("question"),
                "expected_claims": f_result.get("expected_claims", []),
                "must_not_contain": f_result.get("must_not_contain", []),
                "missing_claims": f_result.get("missing_claims", []),
                "hallucinated_terms": f_result.get("hallucinated_terms", []),
                "answer": f_result.get("answer", ""),
                "context_text": f_result.get("context_text", ""),
                "retrieved_chunks": f_result.get("retrieved_chunks", []),
                "ranked_chunks": f_result.get("ranked_chunks", []),
                "chunks_by_source": f_result.get("chunks_by_source", {}),
                "latency_ms": f_result.get("latency_ms"),
                "error": f_result.get("error"),
            }
            with open(failures_dir / f"{safe_id}.json", "w", encoding="utf-8") as f:
                json.dump(artifact, f, indent=2, default=str, ensure_ascii=False)



    def _write_metadata(self, summary: dict, run_dir: Path):
        metadata = collect_metadata(
            dataset_name=summary.get("dataset", ""),
            retriever_mode=summary.get("retriever", "default"),
            extra={
                "timestamp": summary["timestamp"],
                "category": summary.get("category", "all"),
            },
        )
        with open(run_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
