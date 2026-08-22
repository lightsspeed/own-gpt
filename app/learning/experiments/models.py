"""
Experiment data models — defines what an experiment is, and the candidate decision that follows.

Experiment: an immutable description of a test (what parameter changed, over what data, to test what hypothesis).
DecisionCandidate: a system-generated recommendation to adopt or reject an experiment's result.
Decision: a human-approved (or dismissed) decision based on a candidate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ..architecture.artifacts import ArtifactType, Lineage


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DecisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ParameterDomain(str, Enum):
    CHUNK_SIZE = "chunk_size"
    RETRIEVER_TOP_K = "retriever_top_k"
    BM25_WEIGHT = "bm25_weight"
    RERANKER_MODEL = "reranker_model"
    EMBEDDING_MODEL = "embedding_model"
    PROMPT_VERSION = "prompt_version"
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    RERANKER_THRESHOLD = "reranker_threshold"
    CUSTOM = "custom"


@dataclass
class ParameterChange:
    """A single parameter change to test in an experiment."""
    domain: ParameterDomain = ParameterDomain.CUSTOM
    parameter: str = ""
    baseline: Any = None
    candidate: Any = None
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "domain": self.domain.value if isinstance(self.domain, Enum) else self.domain,
            "parameter": self.parameter,
            "baseline": str(self.baseline) if self.baseline is not None else None,
            "candidate": str(self.candidate) if self.candidate is not None else None,
            "description": self.description,
        }


@dataclass
class ExperimentDefinition:
    """
    Immutable description of what is being tested and why.
    Each experiment is linked back to the Recommendation that motivated it.
    """
    id: str = ""
    name: str = ""
    hypothesis: str = ""
    parameter_changes: list[ParameterChange] = field(default_factory=list)
    dataset_size: int = 0
    dataset_description: str = ""
    metrics: list[str] = field(default_factory=lambda: [
        "confidence", "accept_rate", "faithfulness", "context_precision",
        "context_recall", "latency_ms", "tokens_out",
    ])
    status: ExperimentStatus = ExperimentStatus.DRAFT
    recommendation_id: Optional[str] = None
    created_at: str = ""
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"exp-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.recommendation_id,
                parent_type=ArtifactType.RECOMMENDATION,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hypothesis": self.hypothesis,
            "parameter_changes": [p.to_dict() for p in self.parameter_changes],
            "dataset_size": self.dataset_size,
            "dataset_description": self.dataset_description,
            "metrics": self.metrics,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "recommendation_id": self.recommendation_id,
            "created_at": self.created_at,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


@dataclass
class ExperimentResult:
    """
    The complete outcome of one AUTHORIZED experiment execution (V3.14).

    Every result is an immutable artifact:
      - execution_id (unique per execution), status, timestamps
      - authorization code reference (raw code kept internal, NEVER serialized)
      - lineage: parent is the AuthorizationCode that authorized it
    """
    experiment_id: str = ""
    execution_id: str = ""
    status: str = "completed"        # completed | failed | blocked
    baseline_metrics: dict = field(default_factory=dict)
    candidate_metrics: dict = field(default_factory=dict)
    deltas: dict = field(default_factory=dict)
    summary: str = ""
    records_processed: int = 0
    duration_ms: float = 0.0
    started_at: str = ""
    finished_at: str = ""
    completed_at: str = ""           # legacy alias of finished_at
    authorization_code: str = ""     # INTERNAL — the raw code, redacted on serialize
    authorization_code_id: str = ""  # non-secret artifact reference
    error: str = ""
    lineage: Optional[Lineage] = None

    def to_dict(self) -> dict:
        # Secret redaction: the raw authorization_code is NEVER serialized.
        return {
            "experiment_id": self.experiment_id,
            "execution_id": self.execution_id,
            "status": self.status,
            "baseline_metrics": self.baseline_metrics,
            "candidate_metrics": self.candidate_metrics,
            "deltas": self.deltas,
            "summary": self.summary,
            "records_processed": self.records_processed,
            "duration_ms": round(self.duration_ms, 1),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "completed_at": self.completed_at,
            "authorization_code_id": self.authorization_code_id,
            "error": self.error,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


@dataclass
class DecisionCandidate:
    """
    A system-generated proposal based on experiment results.
    Not a Decision — requires human review before becoming one.
    """
    id: str = ""
    experiment_id: str = ""
    recommendation_id: Optional[str] = None
    decision: str = ""              # "adopt", "reject", "modify"
    rationale: str = ""
    supporting_metrics: dict = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: str = ""
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"dc-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.experiment_id,
                parent_type=ArtifactType.EXPERIMENT,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "recommendation_id": self.recommendation_id,
            "decision": self.decision,
            "rationale": self.rationale,
            "supporting_metrics": self.supporting_metrics,
            "risks": self.risks,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "created_at": self.created_at,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


@dataclass
class Decision:
    """
    A human-approved (or dismissed) decision.
    The last step before a configuration change.
    """
    id: str = ""
    decision_candidate_id: str = ""
    experiment_id: str = ""
    approved: bool = False
    reviewer_notes: str = ""
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: str = ""
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"dec-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.decision_candidate_id,
                parent_type=ArtifactType.DECISION_CANDIDATE,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "decision_candidate_id": self.decision_candidate_id,
            "experiment_id": self.experiment_id,
            "approved": self.approved,
            "reviewer_notes": self.reviewer_notes,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "created_at": self.created_at,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }
