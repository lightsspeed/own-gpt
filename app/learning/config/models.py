"""Configuration snapshot model — immutable point-in-time captures of pipeline parameters."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from enum import Enum
from typing import Any, Optional

from ..architecture.artifacts import ArtifactType, Lineage


class ConfigDomain(str, Enum):
    RETRIEVER = "retriever"
    GENERATION = "generation"
    EVALUATION = "evaluation"
    ROUTING = "routing"
    EMBEDDING = "embedding"
    RERANKER = "reranker"
    CHUNKING = "chunking"
    PROMPT = "prompt"
    SYSTEM = "system"


@dataclass
class ConfigurationSnapshot:
    """Immutable snapshot of pipeline configuration at a point in time."""
    id: str = ""
    version: int = 1
    parent_id: Optional[str] = None
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    domains: list[ConfigDomain] = field(default_factory=list)
    git_commit: str = ""
    created_from_decision_id: Optional[str] = None
    created_from_experiment_id: Optional[str] = None
    is_current: bool = False
    created_at: str = ""
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"cfg-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.created_from_decision_id,
                parent_type=ArtifactType.DECISION if self.created_from_decision_id else None,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "parent_id": self.parent_id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "domains": [d.value if isinstance(d, Enum) else d for d in self.domains],
            "git_commit": self.git_commit,
            "created_from_decision_id": self.created_from_decision_id,
            "created_from_experiment_id": self.created_from_experiment_id,
            "is_current": self.is_current,
            "created_at": self.created_at,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConfigurationSnapshot:
        """Reconstruct from a dict (handles nested Lineage)."""
        kwargs = dict(data)
        lineage_data = kwargs.pop("lineage", None)
        if lineage_data and isinstance(lineage_data, dict):
            kwargs["lineage"] = Lineage(**lineage_data)
        return cls(**kwargs)


@dataclass
class ConfigDiff:
    """Structured diff between two configuration snapshots."""
    snapshot_a_id: str = ""
    snapshot_b_id: str = ""
    a_name: str = ""
    b_name: str = ""
    added: dict[str, Any] = field(default_factory=dict)
    removed: dict[str, Any] = field(default_factory=dict)
    changed: dict[str, dict] = field(default_factory=dict)
    unchanged_count: int = 0

    def to_dict(self) -> dict:
        return {
            "snapshot_a_id": self.snapshot_a_id,
            "snapshot_b_id": self.snapshot_b_id,
            "a_name": self.a_name,
            "b_name": self.b_name,
            "added": self.added,
            "removed": self.removed,
            "changed": {k: {"from": v["from"], "to": v["to"]} for k, v in self.changed.items()},
            "unchanged_count": self.unchanged_count,
        }
