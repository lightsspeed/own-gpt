"""Trigger engine — detects meaningful changes and generates operator alerts."""

from __future__ import annotations

import logging
from typing import Optional

from .models import Trigger, EvaluationSnapshot, DailyBrief
from .state import SnapshotStore

logger = logging.getLogger(__name__)


class TriggerEngine:
    """Evaluates snapshots and generates Triggers when meaningful changes are detected.

    Never notifies because a job completed. Only notifies because state changed.
    """

    def __init__(self, store: Optional[SnapshotStore] = None):
        self._store = store or SnapshotStore()

    def evaluate(self, snapshot: Optional[EvaluationSnapshot] = None) -> list[Trigger]:
        """Evaluate a snapshot and return any triggers."""
        triggers: list[Trigger] = []
        snap = snapshot or self._store.latest()
        if not snap:
            return triggers

        previous = None
        if snap.previous_snapshot_id:
            previous = self._store.load(snap.previous_snapshot_id)

        # 1. Confidence drop
        if snap.confidence_delta is not None and snap.confidence_delta < -0.05:
            triggers.append(Trigger(
                title="Confidence dropped significantly",
                description=f"Average confidence decreased by {abs(snap.confidence_delta):.1%}",
                severity="critical" if snap.confidence_delta < -0.10 else "high",
                domain="calibration",
                metric_name="avg_confidence",
                metric_value=snap.avg_confidence or 0,
                threshold=snap.confidence_delta,
                direction="below",
                snapshot_id=snap.id,
            ))

        # 2. ECE increase
        if snap.ece_change_pct is not None and snap.ece_change_pct > 2.0:
            triggers.append(Trigger(
                title="Calibration error increasing",
                description=f"ECE increased by {snap.ece_change_pct:.1f}% (now {snap.ece:.4f})",
                severity="high" if snap.ece_change_pct > 5.0 else "medium",
                domain="calibration",
                metric_name="ece",
                metric_value=snap.ece or 0,
                threshold=snap.ece_change_pct,
                direction="above",
                snapshot_id=snap.id,
            ))

        # 3. New critical findings
        if snap.critical_findings and (previous is None or snap.critical_findings > (previous.critical_findings or 0)):
            delta = snap.critical_findings - (previous.critical_findings or 0) if previous else snap.critical_findings
            if delta > 0:
                triggers.append(Trigger(
                    title=f"{delta} new critical finding(s)",
                    description=f"Critical findings increased from {(previous.critical_findings or 0) if previous else 0} to {snap.critical_findings}",
                    severity="critical",
                    domain="overall",
                    metric_name="critical_findings",
                    metric_value=float(snap.critical_findings),
                    threshold=float(previous.critical_findings or 0) if previous else 0,
                    direction="above",
                    snapshot_id=snap.id,
                ))

        # 4. Knowledge gap surge
        if snap.knowledge_gap_count and (previous is None or snap.knowledge_gap_count > (previous.knowledge_gap_count or 0) * 1.5):
            triggers.append(Trigger(
                title="Knowledge gap surge detected",
                description=f"Knowledge gaps increased to {snap.knowledge_gap_count} ({(previous.knowledge_gap_count or 0) if previous else 0} → {snap.knowledge_gap_count})",
                severity="high",
                domain="knowledge",
                metric_name="knowledge_gap_count",
                metric_value=float(snap.knowledge_gap_count),
                threshold=float(previous.knowledge_gap_count or 0) if previous else 0,
                direction="above",
                snapshot_id=snap.id,
            ))

        # 5. Weak chunk increase
        if snap.weak_chunk_count and (previous is None or snap.weak_chunk_count > (previous.weak_chunk_count or 0) * 1.5):
            triggers.append(Trigger(
                title="Weak chunk count increasing",
                description=f"Weak chunks grew to {snap.weak_chunk_count}",
                severity="medium",
                domain="retrieval",
                metric_name="weak_chunk_count",
                metric_value=float(snap.weak_chunk_count),
                threshold=float(previous.weak_chunk_count or 0) if previous else 0,
                direction="above",
                snapshot_id=snap.id,
            ))

        # 6. Total findings surge
        if snap.findings_count and (previous is None or snap.findings_count > (previous.findings_count or 0) * 2):
            if previous and snap.findings_delta and snap.findings_delta > 0:
                triggers.append(Trigger(
                    title="Finding count doubled",
                    description=f"Total findings: {(previous.findings_count or 0)} → {snap.findings_count}",
                    severity="medium",
                    domain="overall",
                    metric_name="findings_count",
                    metric_value=float(snap.findings_count),
                    threshold=float(previous.findings_count or 0),
                    direction="above",
                    snapshot_id=snap.id,
                ))

        return triggers
