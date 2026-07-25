"""
Validation guardrails — enforce architecture principles as code.

Provides:
  - EvidencePolicy: minimum thresholds for evidence strength
  - validate_lineage(): enforce parent-child relationships
  - validate_finding(): enforce evidence-backed findings
  - validate_recommendation(): enforce finding provenance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .artifacts import ArtifactType, ArtifactRegistry
from .principles import Principle, PRINCIPLES

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    passed: bool = True
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    principle_id: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity.value,
            "principle_id": self.principle_id,
        }


@dataclass
class ValidationReport:
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results if r.severity == ValidationSeverity.ERROR)

    @property
    def errors(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed and r.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed and r.severity == ValidationSeverity.WARNING]

    def add(self, passed: bool, message: str, severity: ValidationSeverity = ValidationSeverity.ERROR, principle_id: str = ""):
        self.results.append(ValidationResult(passed=passed, message=message, severity=severity, principle_id=principle_id))
        return self

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "total": len(self.results),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class EvidencePolicy:
    """Minimum thresholds for evidence to be actionable.

    Fields:
        minimum_strength: minimum EvidenceStrengthLabel ("high", "medium", "low", "insufficient")
        minimum_sample_size: minimum number of records supporting the conclusion
        minimum_confidence: minimum confidence score (0-1)
        minimum_observations: minimum number of discrete observations
        required_observation_types: observation substrings that must be present
        requires_trend: if True, evidence must have a non-"insufficient" trend
        requires_multiple_sources: if True, supporting records must span multiple sessions
        requires_human_review: if True, requires human approval before action
    """
    minimum_strength: str = "low"
    minimum_sample_size: int = 3
    minimum_confidence: float = 0.30
    minimum_observations: int = 1
    required_observation_types: list[str] = field(default_factory=list)
    requires_trend: bool = False
    requires_multiple_sources: bool = False
    requires_human_review: bool = True

    def meets_threshold(
        self,
        strength_label: str,
        sample_size: int,
        confidence: float,
        num_observations: int = 0,
        trend: str = "insufficient",
        num_sources: int = 1,
        observations: Optional[list[str]] = None,
    ) -> bool:
        strength_order = {"high": 3, "medium": 2, "low": 1, "insufficient": 0}
        min_strength = strength_order.get(self.minimum_strength, 0)
        actual_strength = strength_order.get(strength_label, 0)

        if actual_strength < min_strength:
            return False
        if sample_size < self.minimum_sample_size:
            return False
        if confidence < self.minimum_confidence:
            return False
        if num_observations < self.minimum_observations:
            return False
        if self.requires_trend and trend in ("insufficient", ""):
            return False
        if self.requires_multiple_sources and num_sources < 2:
            return False
        if self.required_observation_types and observations:
            obs_text = " ".join(observations).lower()
            for req in self.required_observation_types:
                if req.lower() not in obs_text:
                    return False
        return True

    def to_dict(self) -> dict:
        return {
            "minimum_strength": self.minimum_strength,
            "minimum_sample_size": self.minimum_sample_size,
            "minimum_confidence": self.minimum_confidence,
            "minimum_observations": self.minimum_observations,
            "required_observation_types": self.required_observation_types,
            "requires_trend": self.requires_trend,
            "requires_multiple_sources": self.requires_multiple_sources,
            "requires_human_review": self.requires_human_review,
        }


DEFAULT_EVIDENCE_POLICY = EvidencePolicy()


# ── Guardrail functions ──────────────────────────────────────────────────


def validate_lineage(
    artifact_type: ArtifactType,
    parent_artifact_id: Optional[str],
    parent_type: Optional[ArtifactType],
) -> ValidationResult:
    """Enforce PRINCIPLE_006: every artifact must have the expected parent type."""
    expected = ArtifactRegistry.expected_parent(artifact_type)

    if expected is None:
        # Root artifacts (LEARNING_RECORD, ANALYTICS_REPORT) have no required parent
        return ValidationResult(passed=True, severity=ValidationSeverity.INFO, message=f"No parent required for {artifact_type.value}")

    if parent_artifact_id is None or parent_type is None:
        return ValidationResult(
            passed=False,
            message=f"{artifact_type.value} requires parent of type {expected.value}, but no parent provided",
            principle_id="PRINCIPLE_006",
        )

    if parent_type != expected:
        return ValidationResult(
            passed=False,
            message=f"{artifact_type.value} expected parent type {expected.value}, got {parent_type.value}",
            principle_id="PRINCIPLE_006",
        )

    return ValidationResult(passed=True, severity=ValidationSeverity.INFO, message=f"Lineage valid for {artifact_type.value}")


def validate_finding(evidence) -> ValidationReport:
    """Enforce PRINCIPLE_002: a Finding must carry evidence with observations."""
    report = ValidationReport()
    if not evidence:
        report.add(False, "Finding has no evidence object", principle_id="PRINCIPLE_002")
        return report
    if not evidence.observations:
        report.add(False, "Evidence has no observations", principle_id="PRINCIPLE_002")
    else:
        report.add(True, f"Evidence has {len(evidence.observations)} observations", severity=ValidationSeverity.INFO, principle_id="PRINCIPLE_002")
    return report


def validate_recommendation(finding_id: Optional[str]) -> ValidationReport:
    """Enforce PRINCIPLE_003: every Recommendation must reference a Finding."""
    report = ValidationReport()
    if not finding_id:
        report.add(False, "Recommendation has no finding_id; each recommendation must derive from a Finding", principle_id="PRINCIPLE_003")
    else:
        report.add(True, f"Recommendation references Finding {finding_id}", severity=ValidationSeverity.INFO, principle_id="PRINCIPLE_003")
    return report


def validate_artifact(artifact_type: ArtifactType, **kwargs) -> ValidationReport:
    """Run all applicable guardrails for an artifact type."""
    report = ValidationReport()
    if artifact_type == ArtifactType.FINDING:
        ev = kwargs.get("evidence")
        if ev:
            report.results.extend(validate_finding(ev).results)
    elif artifact_type == ArtifactType.RECOMMENDATION:
        fid = kwargs.get("finding_id")
        if fid is not None:
            report.results.extend(validate_recommendation(fid).results)
    return report
