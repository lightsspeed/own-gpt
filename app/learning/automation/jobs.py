"""Job implementations — each job orchestrates existing platform modules."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ..analytics.engine import AnalyticsEngine
from ..evidence.engine import EvidenceEngine
from ..experiments.models import ExperimentDefinition
from .models import AutomationRun, JobType, JobStatus, EvaluationSnapshot
from .state import SnapshotStore
from .health import compute_all

logger = logging.getLogger(__name__)


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


def run_benchmark_regression() -> AutomationRun:
    """Check benchmarks for regressions. Stub — full benchmark integration is future work."""
    run = AutomationRun(job_type=JobType.BENCHMARK_REGRESSION, status=JobStatus.RUNNING)
    start = time.time()

    try:
        # TODO: Run benchmark datasets and compare against stored baselines
        run.status = JobStatus.SKIPPED
        run.duration_ms = (time.time() - start) * 1000
        run.error = "Benchmark integration not yet configured"
    except Exception as e:
        run.status = JobStatus.FAILED
        run.error = str(e)

    return run
