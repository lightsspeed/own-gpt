"""
Evidence Engine — explains why things happened and how confident we are.

Consumes AnalyticsReports, produces Findings.
Sits between Analytics and Recommendations.
"""

from .engine import EvidenceEngine, EvidenceReport
from .calibration import ConfidenceCalibration, CalibrationReport
from .knowledge_gap import KnowledgeGapDiagnosis, KnowledgeGapDiagnosisReport
from .failure_tree import RetrievalFailureTree, FailureTreeReport
from .models import (
    Finding, FindingCategory,
    Evidence, EvidenceStrength, EvidenceStrengthLabel,
    RootCause, RootCauseCategory,
)

__all__ = [
    "EvidenceEngine", "EvidenceReport",
    "ConfidenceCalibration", "CalibrationReport",
    "KnowledgeGapDiagnosis", "KnowledgeGapDiagnosisReport",
    "RetrievalFailureTree", "FailureTreeReport",
    "Finding", "FindingCategory",
    "Evidence", "EvidenceStrength", "EvidenceStrengthLabel",
    "RootCause", "RootCauseCategory",
]
