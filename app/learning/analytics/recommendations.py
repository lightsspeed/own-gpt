"""
RecommendationGenerator — now a thin formatting layer over Evidence Engine Findings.

Consumes Findings from the Evidence Engine and wraps them in Recommendation objects.
Keeps the existing RecommendationList API for backward compatibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..models import Recommendation, KnowledgeGap, WeakChunk, DeadChunk, RoutingIssue, BenchmarkCandidate
from ..storage.sqlite import LearningStore
from ..evidence.models import Finding, FindingCategory, RootCauseCategory
from ..analytics.queries import QueryIntelligenceReport
from ..analytics.retrieval import RetrievalIntelligenceReport
from ..analytics.routing import RoutingAnalyticsReport

logger = logging.getLogger(__name__)


@dataclass
class RecommendationList:
    knowledge_gaps: list[Recommendation] = field(default_factory=list)
    weak_chunks: list[Recommendation] = field(default_factory=list)
    dead_chunks: list[Recommendation] = field(default_factory=list)
    routing_issues: list[Recommendation] = field(default_factory=list)
    benchmark_candidates: list[Recommendation] = field(default_factory=list)

    @property
    def all(self) -> list[Recommendation]:
        result = []
        result.extend(self.knowledge_gaps)
        result.extend(self.weak_chunks)
        result.extend(self.dead_chunks)
        result.extend(self.routing_issues)
        result.extend(self.benchmark_candidates)
        return result

    @property
    def count(self) -> int:
        return len(self.all)

    def to_dict(self) -> dict:
        return {
            "total_recommendations": self.count,
            "knowledge_gaps": [r.to_dict() for r in self.knowledge_gaps],
            "weak_chunks": [r.to_dict() for r in self.weak_chunks],
            "dead_chunks": [r.to_dict() for r in self.dead_chunks],
            "routing_issues": [r.to_dict() for r in self.routing_issues],
            "benchmark_candidates": [r.to_dict() for r in self.benchmark_candidates],
        }


class RecommendationGenerator:
    """Formats Evidence Engine Findings into Recommendation objects."""

    def __init__(self, store: LearningStore):
        self._store = store

    def from_findings(self, findings: list[Finding]) -> RecommendationList:
        """Generate recommendations from Evidence Engine Findings (primary path)."""
        result = RecommendationList()
        for finding in findings:
            rec = self._finding_to_recommendation(finding)
            if rec is None:
                continue
            cat = finding.category.value if hasattr(finding.category, 'value') else str(finding.category)
            if cat in ("knowledge_gap",):
                result.knowledge_gaps.append(rec)
            elif cat in ("weak_chunk", "poor_retrieval", "low_reranker"):
                result.weak_chunks.append(rec)
            elif cat in ("dead_chunk",):
                result.dead_chunks.append(rec)
            elif cat in ("routing_issue",):
                result.routing_issues.append(rec)
            elif cat in ("benchmark_candidate",):
                result.benchmark_candidates.append(rec)
            else:
                result.knowledge_gaps.append(rec)
        return result

    def generate(
        self,
        query_report: Optional[QueryIntelligenceReport] = None,
        retrieval_report: Optional[RetrievalIntelligenceReport] = None,
        routing_report: Optional[RoutingAnalyticsReport] = None,
    ) -> RecommendationList:
        """
        Legacy path: generate directly from analytics reports.
        Delegates to the Evidence Engine for diagnosis, then formats results.
        """
        from ..evidence.engine import EvidenceEngine
        ee = EvidenceEngine(self._store)
        evidence_report = ee.analyze(
            query_report=query_report,
            retrieval_report=retrieval_report,
            routing_report=routing_report,
        )
        return self.from_findings(evidence_report.findings)

    def _finding_to_recommendation(self, finding: Finding) -> Optional[Recommendation]:
        cat = finding.category.value if hasattr(finding.category, 'value') else str(finding.category)
        rc = finding.root_cause.category.value if hasattr(finding.root_cause.category, 'value') else str(finding.root_cause.category)

        if cat == FindingCategory.KNOWLEDGE_GAP.value:
            return KnowledgeGap(
                id=finding.id,
                finding_id=finding.id,
                title=finding.title,
                description=finding.description,
                evidence={
                    "root_cause": rc,
                    "root_cause_explanation": finding.root_cause.explanation,
                    "evidence_strength": finding.evidence.strength.overall.value,
                    "observations": finding.evidence.observations[:5],
                },
                status=finding.severity,
                topic=finding.root_cause.explanation[:80],
                frequency=finding.evidence.strength.sample_size,
                avg_confidence=finding.root_cause.confidence,
            )

        if cat in (FindingCategory.WEAK_CHUNK.value, FindingCategory.POOR_RETRIEVAL.value, FindingCategory.LOW_RERANKER.value):
            return WeakChunk(
                id=finding.id,
                finding_id=finding.id,
                title=finding.title,
                description=finding.description,
                evidence={
                    "root_cause": rc,
                    "root_cause_explanation": finding.root_cause.explanation,
                    "evidence_strength": finding.evidence.strength.overall.value,
                    "observations": finding.evidence.observations[:5],
                },
                status=finding.severity,
                chunk_id=finding.title,
                source=rc,
                retrieved_count=finding.evidence.strength.sample_size,
                accept_rate=finding.evidence.strength.agreement,
            )

        if cat == FindingCategory.DEAD_CHUNK.value:
            return DeadChunk(
                id=finding.id,
                finding_id=finding.id,
                title=finding.title,
                description=finding.description,
                evidence={
                    "root_cause": rc,
                    "root_cause_explanation": finding.root_cause.explanation,
                    "evidence_strength": finding.evidence.strength.overall.value,
                },
                status=finding.severity,
                chunk_id=finding.title,
                source=rc,
                retrieved_count=finding.evidence.strength.sample_size,
                accept_rate=finding.evidence.strength.agreement,
            )

        if cat == FindingCategory.ROUTING_ISSUE.value:
            return RoutingIssue(
                id=finding.id,
                finding_id=finding.id,
                title=finding.title,
                description=finding.description,
                evidence={
                    "root_cause": rc,
                    "root_cause_explanation": finding.root_cause.explanation,
                    "evidence_strength": finding.evidence.strength.overall.value,
                },
                status=finding.severity,
                intent=rc,
                matched_rule="evidence_engine",
                misrouted_count=finding.evidence.strength.sample_size,
            )

        if cat == FindingCategory.BENCHMARK_CANDIDATE.value:
            return BenchmarkCandidate(
                id=finding.id,
                finding_id=finding.id,
                title=finding.title,
                description=finding.description,
                evidence={
                    "root_cause": rc,
                    "evidence_strength": finding.evidence.strength.overall.value,
                },
                status=finding.severity,
                topic=finding.root_cause.explanation[:80],
                frequency=finding.evidence.strength.sample_size,
            )

        return None
