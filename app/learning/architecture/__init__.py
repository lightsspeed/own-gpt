"""
Architecture governance — principles, lifecycle, lineage, and guardrails.

Establishes a common language and enforceable invariants across the
entire optimization pipeline.
"""

from .artifacts import ARCHITECTURE_VERSION, ArtifactType, Lineage, ArtifactRegistry
from .lifecycle import LifecycleStage
from .principles import Principle, PRINCIPLES, get_principle
from .validation import (
    ValidationSeverity, ValidationResult, ValidationReport,
    EvidencePolicy, DEFAULT_EVIDENCE_POLICY,
    validate_lineage, validate_finding, validate_recommendation, validate_artifact,
)
from .capabilities import (
    Capability, MaturityLevel,
    register, get, list_all, list_by_owner, list_by_stage, to_dict as capabilities_to_dict,
)

__all__ = [
    "ARCHITECTURE_VERSION", "ArtifactType", "Lineage", "ArtifactRegistry",
    "LifecycleStage",
    "Principle", "PRINCIPLES", "get_principle",
    "ValidationSeverity", "ValidationResult", "ValidationReport",
    "EvidencePolicy", "DEFAULT_EVIDENCE_POLICY",
    "validate_lineage", "validate_finding", "validate_recommendation", "validate_artifact",
    "Capability", "MaturityLevel",
    "register", "get", "list_all", "list_by_owner", "list_by_stage", "capabilities_to_dict",
]
