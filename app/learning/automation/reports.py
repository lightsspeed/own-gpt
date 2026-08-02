"""Daily brief generator — synthesizes snapshots and triggers into operator-readable reports."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from ..analytics.engine import AnalyticsEngine
from ..evidence.engine import EvidenceEngine
from .models import DailyBrief, Trigger, EvaluationSnapshot
from .state import SnapshotStore
from .triggers import TriggerEngine
from .health import compute_all
from .jobs import run_daily_evaluation

logger = logging.getLogger(__name__)


def _knowledge_doc_count() -> int:
    """Count indexed knowledge documents from the Whoosh BM25 index."""
    try:
        from app.core.whoosh_manager import get_whoosh_retriever
        bm25 = get_whoosh_retriever()
        return int(getattr(bm25, "doc_count", 0) or 0)
    except Exception:
        return 0


def generate_daily_brief(snapshot_id: Optional[str] = None) -> DailyBrief:
    """Generate a daily brief from the latest evaluation snapshot.

    If no snapshot_id is provided, runs a fresh evaluation.
    """
    store = SnapshotStore()
    snapshot: Optional[EvaluationSnapshot] = None

    if snapshot_id:
        snapshot = store.load(snapshot_id)
    else:
        # Run a fresh evaluation
        logger.info("No snapshot provided — running daily evaluation")
        run = run_daily_evaluation()
        if run.snapshot_id:
            snapshot = store.load(run.snapshot_id)

    if not snapshot:
        return DailyBrief(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            overall_health=100.0,
            generated_at=datetime.now(timezone.utc).isoformat(),
            calibration_note="Insufficient data for evaluation",
            knowledge_docs=_knowledge_doc_count(),
        )

    # Compute health from snapshot data
    domains = []
    for domain_name, score in snapshot.health_scores.items():
        prev_score = None
        if snapshot.previous_snapshot_id:
            prev = store.load(snapshot.previous_snapshot_id)
            if prev:
                prev_score = prev.health_scores.get(domain_name)

        trend = "stable"
        if prev_score is not None:
            if score - prev_score > 1.0:
                trend = "improving"
            elif prev_score - score > 1.0:
                trend = "declining"

        from .models import HealthDomainScore
        domains.append(HealthDomainScore(
            domain=domain_name,
            score=score,
            previous_score=prev_score,
            trend=trend,
        ))

    # Evaluate triggers
    te = TriggerEngine(store)
    triggers = te.evaluate(snapshot)

    # Build top finding
    top_finding = None
    if snapshot.critical_findings and snapshot.critical_findings > 0:
        top_finding = f"{snapshot.critical_findings} critical finding(s) requiring attention"

    # Build per-domain notes
    calibration_note = f"ECE {snapshot.ece:.4f}" if snapshot.ece is not None else "Insufficient data"
    if snapshot.ece_change_pct is not None:
        arrow = "↑" if snapshot.ece_change_pct > 0 else "↓"
        calibration_note += f" ({arrow}{abs(snapshot.ece_change_pct):.1f}%)"

    retrieval_note = f"{snapshot.weak_chunk_count} weak chunks"
    if snapshot.findings_delta:
        retrieval_note += f" (Δ{snapshot.findings_delta:+.0f})"

    routing_note = "Stable"
    if snapshot.intent_distribution:
        top_intent = max(snapshot.intent_distribution, key=snapshot.intent_distribution.get)
        routing_note = f"Top intent: {top_intent}"

    return DailyBrief(
        date=snapshot.timestamp[:10] if snapshot.timestamp else datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        overall_health=snapshot.health_scores.get("overall", 100.0) if snapshot.health_scores else 100.0,
        health_change=None,
        health_domains=domains,
        new_critical_findings=snapshot.critical_findings or 0,
        new_high_findings=snapshot.high_findings or 0,
        total_findings=snapshot.findings_count or 0,
        findings_delta=snapshot.findings_delta or 0,
        triggers=triggers,
        top_finding=top_finding,
        calibration_note=calibration_note,
        retrieval_note=retrieval_note,
        routing_note=routing_note,
        recommendations_generated=0,
        experiments_awaiting=0,
        knowledge_docs=_knowledge_doc_count(),
        snapshot_id=snapshot.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
