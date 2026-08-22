"""
Artifact types and generic Lineage mixin for the entire optimization pipeline.

Every artifact in the pipeline traces back to its parent through Lineage,
forming an auditable chain:

    LearningRecord → AnalyticsReport → Evidence → Finding → Recommendation
    → Experiment → DecisionCandidate → Decision → ConfigurationChange
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


ARCHITECTURE_VERSION = 1


class ArtifactType(str, Enum):
    LEARNING_RECORD = "learning_record"
    ANALYTICS_REPORT = "analytics_report"
    EVIDENCE = "evidence"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    EXPERIMENT = "experiment"
    DECISION_CANDIDATE = "decision_candidate"
    DECISION = "decision"
    CONFIGURATION_CHANGE = "configuration_change"
    # V3.13: one-time checkout token that authorizes experiment execution.
    # Deliberately NOT part of _ANCESTOR_CHAIN: it does not transform
    # information, it gates execution. Its lineage points at the EXPERIMENT.
    AUTHORIZATION_CODE = "authorization_code"


@dataclass
class Lineage:
    """
    Generic lineage for any artifact in the optimization pipeline.

    Every artifact carries its own id and optionally references its parent,
    forming a traceable chain from telemetry to production change.
    """
    artifact_id: str = ""
    parent_artifact_id: Optional[str] = None
    parent_type: Optional[ArtifactType] = None
    created_at: str = ""

    def __post_init__(self):
        if not self.artifact_id:
            self.artifact_id = uuid.uuid4().hex[:16]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = {"artifact_id": self.artifact_id, "created_at": self.created_at}
        if self.parent_artifact_id:
            d["parent_artifact_id"] = self.parent_artifact_id
        if self.parent_type:
            d["parent_type"] = self.parent_type.value if isinstance(self.parent_type, Enum) else self.parent_type
        return d


# ── Parent/child relationships (ordered) ─────────────────────────────────

_ANCESTOR_CHAIN: list[ArtifactType] = [
    ArtifactType.LEARNING_RECORD,
    ArtifactType.ANALYTICS_REPORT,
    ArtifactType.EVIDENCE,
    ArtifactType.FINDING,
    ArtifactType.RECOMMENDATION,
    ArtifactType.EXPERIMENT,
    ArtifactType.DECISION_CANDIDATE,
    ArtifactType.DECISION,
    ArtifactType.CONFIGURATION_CHANGE,
]

_STAGE_MAP: dict[ArtifactType, str] = {
    ArtifactType.LEARNING_RECORD: "observe",
    ArtifactType.ANALYTICS_REPORT: "measure",
    ArtifactType.EVIDENCE: "explain",
    ArtifactType.FINDING: "explain",
    ArtifactType.RECOMMENDATION: "propose",
    ArtifactType.EXPERIMENT: "validate",
    ArtifactType.DECISION_CANDIDATE: "apply",
    ArtifactType.DECISION: "apply",
    ArtifactType.CONFIGURATION_CHANGE: "apply",
    ArtifactType.AUTHORIZATION_CODE: "validate",
}


class ArtifactRegistry:
    """Central registry of all known artifact types and their lifecycle relationships."""

    @classmethod
    def stage_for(cls, artifact_type: ArtifactType) -> str:
        return _STAGE_MAP.get(artifact_type, "unknown")

    @classmethod
    def expected_parent(cls, artifact_type: ArtifactType) -> Optional[ArtifactType]:
        """Return the expected parent type for a given artifact type."""
        try:
            idx = _ANCESTOR_CHAIN.index(artifact_type)
            if idx == 0:
                return None
            return _ANCESTOR_CHAIN[idx - 1]
        except ValueError:
            return None

    @classmethod
    def parent(cls, artifact_type: ArtifactType) -> Optional[ArtifactType]:
        """Alias for expected_parent (more readable in traversal contexts)."""
        return cls.expected_parent(artifact_type)

    @classmethod
    def children(cls, artifact_type: ArtifactType) -> list[ArtifactType]:
        """Return the list of artifact types that can directly follow this one."""
        children = []
        for i, at in enumerate(_ANCESTOR_CHAIN[:-1]):
            if at == artifact_type:
                children.append(_ANCESTOR_CHAIN[i + 1])
        return children

    @classmethod
    def path(cls, from_type: ArtifactType, to_type: ArtifactType) -> list[ArtifactType]:
        """Return the ordered list of artifact types between from_type and to_type (inclusive)."""
        try:
            start = _ANCESTOR_CHAIN.index(from_type)
            end = _ANCESTOR_CHAIN.index(to_type)
            if start <= end:
                return _ANCESTOR_CHAIN[start:end + 1]
            return list(reversed(_ANCESTOR_CHAIN[end:start + 1]))
        except ValueError:
            return []

    @classmethod
    def all_types(cls) -> list[ArtifactType]:
        return list(_ANCESTOR_CHAIN)
