"""
Evidence Engine models — the core abstraction between Analytics and Recommendations.

A Finding answers five questions:
  1. What happened?
  2. Why did it happen?
  3. How confident are we in that diagnosis?
  4. What evidence supports it?
  5. What would likely improve it?
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from ..architecture.artifacts import ArtifactType, Lineage


class EvidenceStrengthLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class FindingCategory(str, Enum):
    KNOWLEDGE_GAP = "knowledge_gap"
    WEAK_CHUNK = "weak_chunk"
    DEAD_CHUNK = "dead_chunk"
    CALIBRATION_DRIFT = "calibration_drift"
    ROUTING_ISSUE = "routing_issue"
    POOR_RETRIEVAL = "poor_retrieval"
    LOW_RERANKER = "low_reranker"
    BENCHMARK_CANDIDATE = "benchmark_candidate"
    PROMPT_ISSUE = "prompt_issue"
    EMBEDDING_ISSUE = "embedding_issue"


class RootCauseCategory(str, Enum):
    NO_DOCUMENTS = "no_documents"
    CHUNK_TOO_LARGE = "chunk_too_large"
    CHUNK_TOO_SMALL = "chunk_too_small"
    POOR_RERANKER = "poor_reranker"
    WEAK_EMBEDDING = "weak_embedding"
    BAD_ROUTING = "bad_routing"
    MISCLASSIFIED_INTENT = "misclassified_intent"
    LOW_CONFIDENCE = "low_confidence"
    OVERCONFIDENCE = "overconfidence"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"
    STALE_DOCUMENT = "stale_document"
    PROMPT_MISMATCH = "prompt_mismatch"
    UNKNOWN = "unknown"


@dataclass
class EvidenceStrength:
    """Multi-dimensional strength assessment for evidence."""
    sample_size: int = 0
    agreement: float = 0.0        # proportion of data consistent with conclusion
    trend: str = "stable"          # "increasing", "decreasing", "stable", "insufficient"
    consistency: str = "stable"    # "stable", "volatile", "insufficient"
    confidence: float = 0.0       # 0-1 score for this evidence

    @property
    def overall(self) -> EvidenceStrengthLabel:
        if self.sample_size < 5 or self.confidence < 0.3:
            return EvidenceStrengthLabel.INSUFFICIENT
        score = 0.0
        score += min(self.sample_size / 200, 1.0) * 0.25
        score += self.agreement * 0.30
        score += (1.0 if self.trend == "increasing" else 0.5 if self.trend == "stable" else 0.3) * 0.20
        score += (1.0 if self.consistency == "stable" else 0.3) * 0.10
        score += self.confidence * 0.15
        if score >= 0.75:
            return EvidenceStrengthLabel.HIGH
        elif score >= 0.50:
            return EvidenceStrengthLabel.MEDIUM
        elif score >= 0.25:
            return EvidenceStrengthLabel.LOW
        return EvidenceStrengthLabel.INSUFFICIENT

    def to_dict(self) -> dict:
        return {
            "sample_size": self.sample_size,
            "agreement": round(self.agreement, 3),
            "trend": self.trend,
            "consistency": self.consistency,
            "confidence": round(self.confidence, 3),
            "overall": self.overall.value,
        }


@dataclass
class Evidence:
    """A structured body of evidence supporting a single conclusion."""
    id: str = ""
    category: str = ""
    strength: EvidenceStrength = field(default_factory=EvidenceStrength)
    observations: list[str] = field(default_factory=list)
    supporting_record_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"ev-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(artifact_id=self.id, parent_type=ArtifactType.ANALYTICS_REPORT)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "strength": self.strength.to_dict(),
            "observations": self.observations,
            "supporting_record_ids": self.supporting_record_ids[:20],
            "created_at": self.created_at,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


@dataclass
class RootCause:
    """The diagnosed reason behind a Finding."""
    category: RootCauseCategory = RootCauseCategory.UNKNOWN
    explanation: str = ""
    confidence: float = 0.0
    evidence: Evidence = field(default_factory=Evidence)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value if isinstance(self.category, Enum) else self.category,
            "explanation": self.explanation,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence.to_dict(),
        }


@dataclass
class Finding:
    """
    A complete finding that answers all five questions.

    1. What happened?          → title, description
    2. Why did it happen?      → root_cause.explanation
    3. How confident?          → root_cause.confidence, evidence.strength.overall
    4. What evidence?          → evidence.observations, evidence.strength
    5. What would improve it?  → recommendation_text
    """
    id: str = ""
    category: FindingCategory = FindingCategory.KNOWLEDGE_GAP
    severity: str = "medium"       # "critical", "high", "medium", "low"
    title: str = ""
    description: str = ""
    root_cause: RootCause = field(default_factory=RootCause)
    evidence: Evidence = field(default_factory=Evidence)
    recommendation_text: str = ""
    created_at: str = ""
    signature: str = ""            # stable semantic identity seed for the id
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = self._stable_id()
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(artifact_id=self.id, parent_type=ArtifactType.ANALYTICS_REPORT)

    def _stable_id(self) -> str:
        """Deterministic content-addressed id.

        Findings describe *repeatable conditions* (a topic that lacks coverage,
        a calibration bucket that drifts). The same condition recur
        across recomputes, so the artifact id must be stable for review and
        lineage workflows to key on it. Generators set `signature` to a
        canonical seed (topic, bucket, class); if absent we fall back to the
        category + root cause (less granular but still deterministic).
        """
        if self.signature:
            seed = self.signature
        else:
            cat = self.category.value if isinstance(self.category, Enum) else str(self.category)
            rc = self.root_cause.category.value if hasattr(self.root_cause.category, "value") else str(self.root_cause.category)
            seed = f"{cat}|{rc}|{self.title}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        return f"fi-{digest}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value if isinstance(self.category, Enum) else self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "root_cause": self.root_cause.to_dict(),
            "evidence": self.evidence.to_dict(),
            "recommendation_text": self.recommendation_text,
            "created_at": self.created_at,
            "signature": self.signature,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }
