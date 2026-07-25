"""
EvidenceEngine — orchestrates all evidence modules and produces Findings.

Sits between Analytics (what happened) and Recommendations (what to do).
Answers: why did it happen, how confident are we, what would improve it?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..storage.sqlite import LearningStore
from ..analytics.queries import QueryIntelligenceReport
from .calibration import ConfidenceCalibration, CalibrationReport
from .knowledge_gap import KnowledgeGapDiagnosis, KnowledgeGapDiagnosisReport
from .failure_tree import RetrievalFailureTree, FailureTreeReport
from .models import Finding

logger = logging.getLogger(__name__)


@dataclass
class EvidenceReport:
    generated_at: str = ""
    calibration: Optional[CalibrationReport] = None
    knowledge_gaps: Optional[KnowledgeGapDiagnosisReport] = None
    failure_tree: Optional[FailureTreeReport] = None
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"generated_at": self.generated_at, "total_findings": len(self.findings)}
        if self.calibration:
            d["calibration"] = self.calibration.to_dict()
        if self.knowledge_gaps:
            d["knowledge_gaps"] = self.knowledge_gaps.to_dict()
        if self.failure_tree:
            d["failure_tree"] = self.failure_tree.to_dict()
        d["findings"] = [f.to_dict() for f in self.findings]
        return d


class EvidenceEngine:
    """Orchestrates all evidence modules. Produces Findings."""

    def __init__(self, store: Optional[LearningStore] = None):
        self._store = store or LearningStore()
        self._calibration = ConfidenceCalibration(self._store)
        self._knowledge_gap = KnowledgeGapDiagnosis(self._store)
        self._failure_tree = RetrievalFailureTree(self._store)

    def analyze(
        self,
        query_report: Optional[QueryIntelligenceReport] = None,
        retrieval_report: Optional[RetrievalIntelligenceReport] = None,
        routing_report: Optional[RoutingAnalyticsReport] = None,
    ) -> EvidenceReport:
        """Run all evidence modules. Takes optional analytics reports to avoid re-computation."""
        calibration = self._calibration.analyze()
        knowledge_gaps = self._knowledge_gap.analyze(query_report=query_report)
        failure_tree = self._failure_tree.analyze()

        # Collect all findings
        all_findings: list[Finding] = []
        all_findings.extend(calibration.findings)
        all_findings.extend(knowledge_gaps.diagnoses)
        all_findings.extend(failure_tree.findings)

        return EvidenceReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            calibration=calibration,
            knowledge_gaps=knowledge_gaps,
            failure_tree=failure_tree,
            findings=all_findings,
        )
