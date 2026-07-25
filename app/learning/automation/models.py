"""Data models for the Continuous Evaluation subsystem."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ..architecture.artifacts import ArtifactType, Lineage


class JobType(str, Enum):
    DAILY_EVALUATION = "daily_evaluation"
    CALIBRATION_CHECK = "calibration_check"
    BENCHMARK_REGRESSION = "benchmark_regression"
    RECOMMENDATION_REFRESH = "recommendation_refresh"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class HealthDomain(str, Enum):
    RETRIEVAL = "retrieval"
    KNOWLEDGE = "knowledge"
    CALIBRATION = "calibration"
    ROUTING = "routing"
    EXPERIMENTS = "experiments"
    OVERALL = "overall"


@dataclass
class AutomationRun:
    """Record of a single automation execution."""
    id: str = ""
    job_type: JobType = JobType.DAILY_EVALUATION
    status: JobStatus = JobStatus.PENDING
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    records_processed: int = 0
    findings_generated: int = 0
    error: Optional[str] = None
    snapshot_id: Optional[str] = None
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"ar-{uuid.uuid4().hex[:12]}"
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(artifact_id=self.id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_type": self.job_type.value if isinstance(self.job_type, Enum) else self.job_type,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": round(self.duration_ms, 1),
            "records_processed": self.records_processed,
            "findings_generated": self.findings_generated,
            "error": self.error,
            "snapshot_id": self.snapshot_id,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


@dataclass
class EvaluationSnapshot:
    """Immutable point-in-time capture of all platform evaluation metrics.

    Stores aggregate analytics + evidence output so the platform can diff
    today against yesterday and detect meaningful changes.
    """
    id: str = ""
    previous_snapshot_id: Optional[str] = None
    timestamp: str = ""
    record_count: int = 0
    event_count: int = 0

    # Aggregate metrics (from Analytics)
    avg_confidence: Optional[float] = None
    accept_rate: Optional[float] = None
    ece: Optional[float] = None
    ece_change_pct: Optional[float] = None

    # Counts
    findings_count: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    knowledge_gap_count: int = 0
    weak_chunk_count: int = 0
    calibration_drift_count: int = 0

    # Health scores
    health_scores: dict[str, float] = field(default_factory=dict)

    # Intent distribution (routing)
    intent_distribution: dict = field(default_factory=dict)

    # Change summary (populated by diff engine)
    change_summary: dict = field(default_factory=dict)
    findings_delta: int = 0
    confidence_delta: Optional[float] = None

    # Raw reports (embedded for auditability)
    analytics_report: Optional[dict] = None
    evidence_report: Optional[dict] = None

    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"es-{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.previous_snapshot_id,
                parent_type=ArtifactType.ANALYTICS_REPORT,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "previous_snapshot_id": self.previous_snapshot_id,
            "timestamp": self.timestamp,
            "record_count": self.record_count,
            "event_count": self.event_count,
            "avg_confidence": self.avg_confidence,
            "accept_rate": self.accept_rate,
            "ece": self.ece,
            "ece_change_pct": self.ece_change_pct,
            "findings_count": self.findings_count,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "medium_findings": self.medium_findings,
            "low_findings": self.low_findings,
            "knowledge_gap_count": self.knowledge_gap_count,
            "weak_chunk_count": self.weak_chunk_count,
            "calibration_drift_count": self.calibration_drift_count,
            "health_scores": self.health_scores,
            "intent_distribution": self.intent_distribution,
            "change_summary": self.change_summary,
            "findings_delta": self.findings_delta,
            "confidence_delta": self.confidence_delta,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


@dataclass
class HealthDomainScore:
    """Score for a single health domain (0-100)."""
    domain: HealthDomain = HealthDomain.OVERALL
    score: float = 100.0
    previous_score: Optional[float] = None
    trend: str = "stable"
    finding_count: int = 0
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "domain": self.domain.value if isinstance(self.domain, Enum) else self.domain,
            "score": round(self.score, 1),
            "previous_score": round(self.previous_score, 1) if self.previous_score is not None else None,
            "trend": self.trend,
            "finding_count": self.finding_count,
            "weight": self.weight,
        }


@dataclass
class Trigger:
    """A condition that warrants operator attention."""
    id: str = ""
    title: str = ""
    description: str = ""
    severity: str = "info"
    domain: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    direction: str = "above"
    snapshot_id: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"tr-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "domain": self.domain,
            "metric_name": self.metric_name,
            "metric_value": round(self.metric_value, 3),
            "threshold": round(self.threshold, 3),
            "direction": self.direction,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
        }


@dataclass
class DailyBrief:
    """Concise daily summary for operators."""
    date: str = ""
    overall_health: float = 100.0
    health_change: Optional[float] = None
    health_domains: list[HealthDomainScore] = field(default_factory=list)
    new_critical_findings: int = 0
    new_high_findings: int = 0
    total_findings: int = 0
    findings_delta: int = 0
    triggers: list[Trigger] = field(default_factory=list)
    top_finding: Optional[str] = None
    calibration_note: str = ""
    retrieval_note: str = ""
    routing_note: str = ""
    recommendations_generated: int = 0
    experiments_awaiting: int = 0
    snapshot_id: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "overall_health": round(self.overall_health, 1),
            "health_change": round(self.health_change, 1) if self.health_change is not None else None,
            "health_domains": [d.to_dict() for d in self.health_domains],
            "new_critical_findings": self.new_critical_findings,
            "new_high_findings": self.new_high_findings,
            "total_findings": self.total_findings,
            "findings_delta": self.findings_delta,
            "triggers": [t.to_dict() for t in self.triggers[:10]],
            "top_finding": self.top_finding,
            "calibration_note": self.calibration_note,
            "retrieval_note": self.retrieval_note,
            "routing_note": self.routing_note,
            "recommendations_generated": self.recommendations_generated,
            "experiments_awaiting": self.experiments_awaiting,
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
        }
