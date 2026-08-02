"""Job implementations — each job orchestrates existing platform modules."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ..analytics.engine import AnalyticsEngine
from ..evidence.engine import EvidenceEngine
from ..experiments.models import ExperimentDefinition
from .models import AutomationRun, JobType, JobStatus, EvaluationSnapshot, BenchmarkBaseline
from .state import SnapshotStore, BaselineStore
from .health import compute_all

logger = logging.getLogger(__name__)

# Benchmark regression job defaults
DEFAULT_BENCHMARK_DATASET = "intent_accuracy"
DEFAULT_SAMPLE_SIZE = 10          # bounded subset for a light weekly check
DEFAULT_BASE_URL = "http://localhost:8000"
REGRESSION_THRESHOLD = 0.05       # success-rate drop >= 5 points = regression
LATENCY_REGRESSION_PCT = 1.5      # avg latency > 1.5x baseline = regression


def run_daily_evaluation(limit: int = 500) -> AutomationRun:
    """Full evaluation: Analytics → Evidence → Health → Snapshot → Diff.

    This is the primary job. It orchestrates the entire pipeline and
    produces an EvaluationSnapshot with change data.
    """
    run = AutomationRun(job_type=JobType.DAILY_EVALUATION, status=JobStatus.RUNNING)
    start = time.time()
    store = SnapshotStore()

    try:
        # 1. Run analytics
        ae = AnalyticsEngine()
        ar = ae.run_all()

        # 2. Run evidence engine
        ee = EvidenceEngine()
        er = ee.analyze(query_report=ar.query, retrieval_report=ar.retrieval, routing_report=ar.routing)

        # 3. Compute health scores
        health_scores_list = compute_all(evidence_report=er)
        health_scores_dict = {hs.domain.value: hs.score for hs in health_scores_list}

        # 4. Load calibration ECE
        ece = None
        if er.calibration and er.calibration.buckets:
            ece = round(er.calibration.ece, 4)

        # 5. Build snapshot
        snapshot = EvaluationSnapshot(
            record_count=ar.total_records,
            event_count=ar.total_events,
            avg_confidence=ar.query.top_queries[0].get("avg_confidence") if ar.query and ar.query.top_queries else None,
            accept_rate=None,
            ece=ece,
            findings_count=len(er.findings),
            critical_findings=sum(1 for f in er.findings if f.severity == "critical"),
            high_findings=sum(1 for f in er.findings if f.severity == "high"),
            medium_findings=sum(1 for f in er.findings if f.severity == "medium"),
            low_findings=sum(1 for f in er.findings if f.severity == "low"),
            knowledge_gap_count=len(er.knowledge_gaps.diagnoses) if er.knowledge_gaps else 0,
            weak_chunk_count=len(er.failure_tree.classifications) if er.failure_tree else 0,
            calibration_drift_count=len(er.calibration.findings) if er.calibration else 0,
            health_scores=health_scores_dict,
            intent_distribution=ar.routing.intent_distribution if ar.routing else {},
            analytics_report={"total_records": ar.total_records, "total_events": ar.total_events},
            evidence_report={"total_findings": len(er.findings)},
        )

        # 6. Diff against previous snapshot
        previous = store.latest()
        if previous:
            snapshot.previous_snapshot_id = previous.id
            snapshot.findings_delta = snapshot.findings_count - (previous.findings_count or 0)
            if snapshot.avg_confidence is not None and previous.avg_confidence is not None:
                snapshot.confidence_delta = round(snapshot.avg_confidence - previous.avg_confidence, 3)
            if ece is not None and previous.ece is not None and previous.ece > 0:
                snapshot.ece_change_pct = round(((ece - previous.ece) / previous.ece) * 100, 1)

        # 7. Persist
        store.save(snapshot)

        run.status = JobStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc).isoformat()
        run.duration_ms = (time.time() - start) * 1000
        run.records_processed = ar.total_records
        run.findings_generated = len(er.findings)
        run.snapshot_id = snapshot.id

    except Exception as e:
        logger.exception("Daily evaluation failed")
        run.status = JobStatus.FAILED
        run.completed_at = str(time.time())
        run.error = str(e)

    return run


def run_calibration_check() -> AutomationRun:
    """Focused calibration check — lighter than full evaluation."""
    run = AutomationRun(job_type=JobType.CALIBRATION_CHECK, status=JobStatus.RUNNING)
    start = time.time()

    try:
        ee = EvidenceEngine()
        cal = ee._calibration.analyze()
        run.status = JobStatus.COMPLETED
        run.duration_ms = (time.time() - start) * 1000
        run.findings_generated = len(cal.findings)
        run.records_processed = cal.total_records_analyzed
    except Exception as e:
        run.status = JobStatus.FAILED
        run.error = str(e)

    return run


def run_benchmark_regression(
    dataset: str = DEFAULT_BENCHMARK_DATASET,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    base_url: str = DEFAULT_BASE_URL,
) -> AutomationRun:
    """Run a bounded benchmark subset and detect regressions vs the latest baseline.

    Orchestrates existing benchmark modules (app.evaluation) — no business logic
    is duplicated here. Intent datasets run offline through the classifier; RAG
    datasets run against the chat API. A new BenchmarkBaseline artifact is
    written on every run; the previous baseline is never mutated.
    """
    run = AutomationRun(job_type=JobType.BENCHMARK_REGRESSION, status=JobStatus.RUNNING)
    start = time.time()
    store = BaselineStore()

    try:
        if dataset == "intent_accuracy":
            from app.evaluation.intent_accuracy import evaluate_intent_accuracy
            result = evaluate_intent_accuracy()
            total = result.total
            successful_count = result.correct
            avg_latency = (
                sum(d["latency_ms"] for d in result.details) / len(result.details)
                if result.details else 0.0
            )
            metrics = {
                "by_intent": result.by_intent,
                "by_rule": result.by_rule,
                "sample_size": total,
            }
            display_name = "Intent Accuracy"
        else:
            from app.evaluation.loader import load_dataset
            from app.evaluation.benchmark import run_benchmark_subset

            ds = load_dataset(dataset)
            if not ds.questions:
                run.status = JobStatus.SKIPPED
                run.duration_ms = (time.time() - start) * 1000
                run.error = f"Dataset '{dataset}' has no questions"
                return run

            subset = ds.questions[:sample_size]
            results = run_benchmark_subset(subset, base_url=base_url)
            successful = [r for r in results if r["status"] == "success"]
            successful_count = len(successful)
            total = len(results)
            avg_latency = (
                sum(r.get("latency_ms", 0) for r in successful) / successful_count
                if successful_count else 0.0
            )
            metrics = {
                "sample_size": total,
                "missing_claims": sum(len(r.get("missing_claims", [])) for r in successful),
                "hallucinated_terms": sum(len(r.get("hallucinated_terms", [])) for r in successful),
                "errors": [r.get("error") for r in results if r.get("error")][:10],
            }
            display_name = ds.display_name

        success_rate = successful_count / total if total else 0.0

        previous = store.latest(dataset)
        baseline = BenchmarkBaseline(
            dataset=dataset,
            display_name=display_name,
            total=total,
            successful=successful_count,
            failed=total - successful_count,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            metrics=metrics,
            previous_baseline_id=previous.id if previous else None,
        )
        store.save(baseline)

        # Regression detection
        regressions = []
        if previous:
            prev_rate = previous.success_rate
            if success_rate < prev_rate - REGRESSION_THRESHOLD:
                regressions.append(
                    f"success_rate {success_rate:.1%} vs baseline {prev_rate:.1%}"
                )
            if previous.avg_latency_ms and avg_latency > previous.avg_latency_ms * LATENCY_REGRESSION_PCT:
                regressions.append(
                    f"latency {avg_latency:.0f}ms vs baseline {previous.avg_latency_ms:.0f}ms"
                )

        run.status = JobStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc).isoformat()
        run.duration_ms = (time.time() - start) * 1000
        run.records_processed = total
        run.findings_generated = len(regressions)
        run.snapshot_id = baseline.id
        if regressions:
            run.error = f"Benchmark regression detected: {'; '.join(regressions)}"
        else:
            run.error = None

    except Exception as e:
        logger.exception("Benchmark regression failed")
        run.status = JobStatus.FAILED
        run.completed_at = str(time.time())
        run.error = str(e)

    return run
