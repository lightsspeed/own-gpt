"""
Knowledge Gap Diagnosis — goes beyond "what" to "why" for each knowledge gap.

For every detected knowledge gap (repeated low-confidence queries on a topic),
diagnose the root cause among:
  - No documents exist for this topic
  - Documents exist but retrieval fails
  - Retrieved documents are weak chunks (low reranker/citation)
  - The query was misrouted (wrong intent)
  - The reranker failed to surface relevant chunks

Produces Finding objects with root cause, evidence strength, and recommendation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..storage.sqlite import LearningStore
from ..analytics.queries import QueryIntelligenceReport
from .models import (
    Evidence, EvidenceStrength, RootCause, RootCauseCategory,
    Finding, FindingCategory,
)

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeGapDiagnosisReport:
    diagnoses: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"diagnoses": [f.to_dict() for f in self.diagnoses]}


class KnowledgeGapDiagnosis:
    """Diagnose why knowledge gaps exist."""

    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self, query_report: Optional[QueryIntelligenceReport] = None) -> KnowledgeGapDiagnosisReport:
        gaps = query_report.knowledge_gaps if (query_report and query_report.knowledge_gaps) else []
        if not gaps:
            return KnowledgeGapDiagnosisReport()
        findings = []
        for gap in gaps[:20]:
            finding = self._diagnose(gap)
            if finding:
                findings.append(finding)
        return KnowledgeGapDiagnosisReport(diagnoses=findings)

    def _diagnose(self, gap: dict) -> Optional[Finding]:
        qhash = gap.get("question_hash", "")
        sample = gap.get("sample", "Unknown topic")[:80]
        count = gap.get("count", 1)
        avg_conf = gap.get("avg_confidence", 0) or 0
        synthesis_rate = gap.get("synthesis_rate", 0) or 0
        thumbs_down = gap.get("thumbs_down", 0)

        # Fetch sample records for this question_hash to inspect retrieval
        records = self._store.query_sql("""
            SELECT retriever, documents, chunks, answer_mode, matched_rule, intent,
                   confidence, accepted, reranker_scores
            FROM learning_records
            WHERE question_hash = ?
            LIMIT 20
        """, [qhash])

        if not records:
            return None

        # Analyze retrieval characteristics
        has_docs = any(r.get("documents") and r["documents"] != "[]" for r in records)
        has_chunks = any(r.get("chunks") and r["chunks"] != "[]" for r in records)
        answer_modes = [r.get("answer_mode", "unknown") for r in records]
        intents = [r.get("intent", "unknown") for r in records]
        matched_rules = [r.get("matched_rule", "") for r in records]
        retriever_modes = [r.get("retriever", "") for r in records]

        # Parse reranker scores from stored JSON
        reranker_scores = []
        for r in records:
            raw = r.get("reranker_scores")
            if raw and raw != "[]":
                try:
                    scores = json.loads(raw) if isinstance(raw, str) else raw
                    reranker_scores.extend(scores)
                except (json.JSONDecodeError, TypeError):
                    pass

        avg_reranker = sum(reranker_scores) / len(reranker_scores) if reranker_scores else None

        is_synthesis = sum(1 for m in answer_modes if m == "synthesis") / max(len(answer_modes), 1)
        is_knowledge = sum(1 for i in intents if i in ("knowledge", "KNOWLEDGE")) / max(len(intents), 1)
        matched_rule_count = sum(1 for r in matched_rules if r and r != "")

        # Decision tree for root cause
        if not has_docs:
            cause = RootCauseCategory.NO_DOCUMENTS
            explanation = (
                f"No documents were retrieved for this topic across {len(records)} queries. "
                f"The knowledge base likely lacks coverage for \"{sample}\"."
            )
            rec = "Add documentation covering this topic. Consider ingesting relevant manuals, guides, or reference materials."
            sev = "critical" if count >= 5 else "high"
            conf = min(0.5 + count * 0.05, 0.95)
        elif not has_chunks:
            cause = RootCauseCategory.INSUFFICIENT_COVERAGE
            explanation = (
                f"Documents were retrieved but no usable chunks were extracted. "
                f"The {len(records)} queries on this topic all failed at chunk extraction."
            )
            rec = "Review chunk extraction pipeline for this document set."
            sev = "high"
            conf = 0.70
        elif avg_reranker is not None and avg_reranker < 0.3:
            cause = RootCauseCategory.POOR_RERANKER
            explanation = (
                f"Despite retrieving documents, the reranker assigned very low scores "
                f"(avg {avg_reranker:.2f}). The retrieved content may be topically related "
                f"but not precisely relevant to \"{sample}\"."
            )
            rec = "Review chunk quality for this topic. Consider re-chunking, improving embedding quality, or adding more specific content."
            sev = "high"
            conf = min(0.6 + (1.0 - avg_reranker) * 0.4, 0.93)
        elif is_synthesis > 0.5:
            cause = RootCauseCategory.INSUFFICIENT_COVERAGE
            explanation = (
                f"{is_synthesis:.0%} of answers were synthesized (no direct match). "
                f"The KB has partial coverage but no chunk directly answers \"{sample}\"."
            )
            rec = "Add a chunk that directly addresses this topic to reduce synthesis reliance."
            sev = "medium"
            conf = 0.75
        elif is_knowledge < 0.5:
            cause = RootCauseCategory.BAD_ROUTING
            explanation = (
                f"Only {is_knowledge:.0%} of queries were routed to KNOWLEDGE intent. "
                f"Routing misclassifies this topic, sending it to non-knowledge pipelines."
            )
            rec = "Review intent classification rules for this topic pattern. Consider adding a specific KNOWLEDGE rule."
            sev = "medium"
            conf = 0.80
        elif avg_conf < 0.3:
            cause = RootCauseCategory.LOW_CONFIDENCE
            explanation = (
                f"Even when routed correctly, confidence is very low (avg {avg_conf:.2f}). "
                f"Retrieved content may be poor quality or mismatched."
            )
            rec = "Review retrieved chunks for quality and relevance. Consider adding higher-quality sources."
            sev = "medium"
            conf = 0.65
        else:
            cause = RootCauseCategory.UNKNOWN
            explanation = (
                f"Topic \"{sample}\" shows repeated issues ({count}x, conf={avg_conf:.2f}) "
                f"but root cause is unclear from available signals."
            )
            rec = "Manually review sample queries to identify the issue."
            sev = "low"
            conf = 0.30

        evidence = Evidence(
            category="knowledge_gap",
            strength=EvidenceStrength(
                sample_size=len(records),
                agreement=conf,
                trend="stable" if count >= 5 else "insufficient",
                consistency="stable" if len(records) >= 5 else "insufficient",
                confidence=conf,
            ),
            observations=[
                f"{count} occurrences, avg confidence {avg_conf:.2f}, synthesis rate {synthesis_rate:.0%}",
                f"Retrieved documents: {'YES' if has_docs else 'NO'}",
                f"Retrieved chunks: {'YES' if has_chunks else 'NO'}",
                f"Avg reranker score: {avg_reranker:.3f}" if avg_reranker is not None else "Reranker data: N/A",
                f"Knowlege routing: {is_knowledge:.0%}",
                f"Answer modes: {', '.join(sorted(set(answer_modes)))[:60]}",
            ],
        )

        return Finding(
            category=FindingCategory.KNOWLEDGE_GAP,
            severity=sev,
            title=f"Knowledge Gap: \"{sample[:60]}\"",
            description=explanation,
            root_cause=RootCause(category=cause, explanation=explanation, confidence=conf, evidence=evidence),
            evidence=evidence,
            recommendation_text=rec,
            signature=f"knowledge_gap|{cause.value}|{sample}",
        )
