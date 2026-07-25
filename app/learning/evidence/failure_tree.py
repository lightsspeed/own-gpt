"""
Retrieval Failure Tree — walks a decision tree for every failed/weak query
to classify the failure mode and produce actionable Findings.

Every failed query walks this tree:

Low confidence?
├── Yes
│   ├── Retrieved documents?
│   │   ├── No → Knowledge Gap (no KB coverage)
│   │   └── Yes
│   │       ├── Reranker score > threshold?
│   │       │   ├── No → Low Reranker (poor relevance ranking)
│   │       │   └── Yes → Weak Chunks (retrieved but not helpful)
│   └── (routing check)
│       ├── Correct intent?
│       │   ├── No → Routing Issue
│       │   └── Yes → Evaluation Issue
└── High confidence → (no failure, skip)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..storage.sqlite import LearningStore
from .models import (
    Evidence, EvidenceStrength, RootCause, RootCauseCategory,
    Finding, FindingCategory,
)

logger = logging.getLogger(__name__)

RERANKER_THRESHOLD = 0.35
MIN_CONFIDENCE_FAILURE = 0.50  # confidence below this = "low confidence"


@dataclass
class FailureClassification:
    category: FindingCategory
    root_cause: RootCauseCategory
    severity: str
    explanation: str
    recommendation: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "category": self.category.value if hasattr(self.category, 'value') else self.category,
            "root_cause": self.root_cause.value if hasattr(self.root_cause, 'value') else self.root_cause,
            "severity": self.severity,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class FailureTreeReport:
    total_failed: int = 0
    classifications: dict = field(default_factory=dict)   # category → count
    by_root_cause: dict = field(default_factory=dict)      # root_cause → count
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_failed": self.total_failed,
            "classifications": self.classifications,
            "by_root_cause": self.by_root_cause,
            "findings": [f.to_dict() for f in self.findings],
        }


class RetrievalFailureTree:
    """Classify every failed/weak query into a failure mode."""

    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> FailureTreeReport:
        # Fetch records that indicate failure: low confidence, not accepted, or regenerated
        rows = self._store.query_sql("""
            SELECT record_id, question_hash, question, normalized_question,
                   confidence, accepted, intent, matched_rule,
                   documents, chunks, answer_mode, retriever,
                   reranker_scores, failure_reason
            FROM learning_records
            WHERE confidence < ? OR accepted = 0
            ORDER BY confidence ASC
            LIMIT 500
        """, [MIN_CONFIDENCE_FAILURE])

        if not rows:
            return FailureTreeReport()

        classifications: dict[str, int] = {}
        by_cause: dict[str, int] = {}
        aggregated: dict[str, list[dict]] = {}  # qhash → [classifications]

        for r in rows:
            classification = self._classify(r)
            key = classification.category.value if hasattr(classification.category, 'value') else str(classification.category)
            classifications[key] = classifications.get(key, 0) + 1
            cause_key = classification.root_cause.value if hasattr(classification.root_cause, 'value') else str(classification.root_cause)
            by_cause[cause_key] = by_cause.get(cause_key, 0) + 1

            qhash = r.get("question_hash", "unknown")
            if qhash not in aggregated:
                aggregated[qhash] = []
            aggregated[qhash].append(classification)

        # Generate findings for the most common failure patterns
        findings = self._generate_findings(classifications, by_cause, aggregated)

        return FailureTreeReport(
            total_failed=len(rows),
            classifications=classifications,
            by_root_cause=by_cause,
            findings=findings,
        )

    def _classify(self, record: dict) -> FailureClassification:
        """Walk the decision tree for a single record."""
        confidence = record.get("confidence", 0) or 0
        accepted = bool(record.get("accepted", 1))
        documents_raw = record.get("documents", "")
        chunks_raw = record.get("chunks", "")
        answer_mode = record.get("answer_mode", "")
        intent = record.get("intent", "")
        matched_rule = record.get("matched_rule", "")
        failure_reason = record.get("failure_reason", "")

        has_documents = self._has_content(documents_raw)
        has_chunks = self._has_content(chunks_raw)

        avg_reranker = self._parse_reranker_scores(record.get("reranker_scores", ""))

        # Decision tree
        if failure_reason:
            return FailureClassification(
                category=FindingCategory.KNOWLEDGE_GAP,
                root_cause=RootCauseCategory.UNKNOWN,
                severity="medium",
                explanation=f"Explicit failure: {failure_reason[:100]}",
                recommendation="Review the specific failure reason and address accordingly.",
                confidence=0.90,
            )

        if not has_documents:
            return FailureClassification(
                category=FindingCategory.KNOWLEDGE_GAP,
                root_cause=RootCauseCategory.NO_DOCUMENTS,
                severity="critical" if confidence < 0.3 else "high",
                explanation="No documents retrieved. The knowledge base lacks coverage for this query.",
                recommendation="Add documentation covering this topic.",
                confidence=min(0.7 + (1.0 - confidence) * 0.3, 0.95),
            )

        if not has_chunks:
            return FailureClassification(
                category=FindingCategory.KNOWLEDGE_GAP,
                root_cause=RootCauseCategory.INSUFFICIENT_COVERAGE,
                severity="high",
                explanation="Documents retrieved but no usable chunks extracted. Chunk pipeline may have failed.",
                recommendation="Review chunk extraction for this document set.",
                confidence=0.80,
            )

        if avg_reranker is not None and avg_reranker < RERANKER_THRESHOLD:
            return FailureClassification(
                category=FindingCategory.LOW_RERANKER,
                root_cause=RootCauseCategory.POOR_RERANKER,
                severity="high" if avg_reranker < 0.2 else "medium",
                explanation=f"Documents and chunks exist but reranker score is low ({avg_reranker:.2f}). "
                           f"Retrieved content is not precisely relevant.",
                recommendation="Review chunk quality. Consider re-chunking or adding more specific content.",
                confidence=min(0.6 + (RERANKER_THRESHOLD - avg_reranker) * 1.5, 0.92),
            )

        if answer_mode == "synthesis":
            return FailureClassification(
                category=FindingCategory.WEAK_CHUNK,
                root_cause=RootCauseCategory.INSUFFICIENT_COVERAGE,
                severity="medium",
                explanation="Answer was synthesized (no direct chunk match). Partial coverage exists.",
                recommendation="Add a chunk targeting this specific query.",
                confidence=0.70,
            )

        if intent not in ("knowledge", "KNOWLEDGE", ""):
            return FailureClassification(
                category=FindingCategory.ROUTING_ISSUE,
                root_cause=RootCauseCategory.BAD_ROUTING,
                severity="medium",
                explanation=f"Query routed to '{intent}' instead of KNOWLEDGE. May be misclassified.",
                recommendation="Review routing rules for this query pattern.",
                confidence=0.75,
            )

        # Default: retrieved but not helpful
        return FailureClassification(
            category=FindingCategory.WEAK_CHUNK,
            root_cause=RootCauseCategory.UNKNOWN,
            severity="medium",
            explanation="Query retrieved documents and chunks but still failed. Chunks may be low quality.",
            recommendation="Review chunk quality and relevance for this query pattern.",
            confidence=0.50,
        )

    def _generate_findings(
        self, classifications: dict, by_cause: dict, aggregated: dict[str, list]
    ) -> list[Finding]:
        findings = []
        total = sum(classifications.values()) or 1

        # Generate one Finding per dominant failure category
        dominant = sorted(classifications.items(), key=lambda x: -x[1])
        for cat, count in dominant[:3]:
            pct = count / total * 100
            sample_qhash = None
            for qhash, classes in aggregated.items():
                matching = [c for c in classes if (c.category.value if hasattr(c.category, 'value') else str(c.category)) == cat]
                if matching:
                    sample_qhash = qhash
                    break

            severity = "critical" if pct > 40 else "high" if pct > 20 else "medium"
            evidence = Evidence(
                category="failure_tree",
                strength=EvidenceStrength(
                    sample_size=count,
                    agreement=count / total,
                    trend="stable" if count >= 20 else "insufficient",
                    consistency="stable" if count >= 10 else "insufficient",
                    confidence=min(0.5 + count * 0.01, 0.95),
                ),
                observations=[
                    f"{count} failures ({pct:.0f}% of all failures)",
                    f"Category: {cat}",
                    f"Sample question hash: {sample_qhash or 'N/A'}",
                ],
            )

            root_cause_cat = RootCauseCategory.UNKNOWN
            for cause, cause_count in sorted(by_cause.items(), key=lambda x: -x[1]):
                root_cause_cat = RootCauseCategory(cause) if cause in [e.value for e in RootCauseCategory] else RootCauseCategory.UNKNOWN
                break

            findings.append(Finding(
                category=FindingCategory(cat) if cat in [e.value for e in FindingCategory] else FindingCategory.KNOWLEDGE_GAP,
                severity=severity,
                title=f"Failure Pattern: {cat} ({count} queries, {pct:.0f}%)",
                description=f"{count} of {total} failures ({pct:.0f}%) are classified as {cat}.",
                root_cause=RootCause(
                    category=root_cause_cat,
                    explanation=f"{cat} is the dominant failure pattern, accounting for {pct:.0f}% of all failures.",
                    confidence=evidence.strength.confidence,
                    evidence=evidence,
                ),
                evidence=evidence,
                recommendation_text=f"Address the {cat} failure pattern. Review the specific root causes and apply targeted fixes.",
            ))

        return findings

    def _has_content(self, raw) -> bool:
        if not raw:
            return False
        if isinstance(raw, str) and raw in ("", "[]", "{}"):
            return False
        return True

    def _parse_reranker_scores(self, raw) -> Optional[float]:
        if not raw or raw == "[]" or raw == "":
            return None
        try:
            scores = json.loads(raw) if isinstance(raw, str) else raw
            if scores:
                return sum(scores) / len(scores)
        except (json.JSONDecodeError, TypeError, ZeroDivisionError):
            pass
        return None
