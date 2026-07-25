"""Health domain scoring — transforms Findings into per-domain health scores (0-100)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..evidence.models import Finding, FindingCategory
from ..evidence.engine import EvidenceReport
from .models import HealthDomain, HealthDomainScore

logger = logging.getLogger(__name__)

# Domain → Finding category mapping
DOMAIN_CATEGORY_MAP: dict[HealthDomain, list[str]] = {
    HealthDomain.RETRIEVAL: ["weak_chunk", "dead_chunk", "poor_retrieval", "low_reranker"],
    HealthDomain.KNOWLEDGE: ["knowledge_gap", "benchmark_candidate"],
    HealthDomain.CALIBRATION: ["calibration_drift"],
    HealthDomain.ROUTING: ["routing_issue"],
    HealthDomain.EXPERIMENTS: [],  # computed from pending experiment count
}

SEVERITY_PENALTIES = {"critical": 30, "high": 15, "medium": 7, "low": 2}
STRENGTH_MULTIPLIERS = {"high": 1.0, "medium": 0.7, "low": 0.4, "insufficient": 0.2}


def compute_domain_score(domain: HealthDomain, findings: list[Finding],
                         total_findings: int = 0) -> HealthDomainScore:
    """Compute a 0-100 health score for a single domain.

    Starts at 100 and subtracts penalties for each finding in the domain.
    Penalties are weighted by severity × evidence strength × frequency.
    """
    score = 100.0
    cat_map = DOMAIN_CATEGORY_MAP.get(domain, [])
    domain_findings = [f for f in findings if _category(f) in cat_map]

    for f in domain_findings:
        severity = f.severity.lower()
        strength = _evidence_strength(f)
        freq = _frequency(f)
        penalty = SEVERITY_PENALTIES.get(severity, 5)
        multiplier = STRENGTH_MULTIPLIERS.get(strength, 0.5)
        freq_factor = min(freq / 5, 2.0)
        score -= penalty * multiplier * freq_factor

    score = max(0.0, min(100.0, round(score, 1)))

    return HealthDomainScore(
        domain=domain,
        score=score,
        finding_count=len(domain_findings),
    )


def compute_overall(domain_scores: list[HealthDomainScore],
                    total_findings: int = 0) -> HealthDomainScore:
    """Weighted average of all domain scores."""
    if not domain_scores:
        return HealthDomainScore(domain=HealthDomain.OVERALL, score=100.0)

    total_weight = sum(d.weight for d in domain_scores)
    if total_weight == 0:
        return HealthDomainScore(domain=HealthDomain.OVERALL, score=100.0)

    weighted = sum(d.score * d.weight for d in domain_scores)
    overall = round(weighted / total_weight, 1)

    return HealthDomainScore(
        domain=HealthDomain.OVERALL,
        score=overall,
        finding_count=total_findings,
    )


def compute_all(evidence_report: Optional[EvidenceReport] = None,
                pending_experiments: int = 0) -> list[HealthDomainScore]:
    """Compute all domain health scores from an EvidenceReport."""
    findings = evidence_report.findings if evidence_report and evidence_report.findings else []
    scores = []

    for domain in (HealthDomain.RETRIEVAL, HealthDomain.KNOWLEDGE,
                   HealthDomain.CALIBRATION, HealthDomain.ROUTING):
        ds = compute_domain_score(domain, findings)
        scores.append(ds)

    # Experiments domain — penalize for long-pending experiments
    exp_score = 100.0
    if pending_experiments > 5:
        exp_score = max(50.0, 100.0 - (pending_experiments * 5))
    elif pending_experiments > 2:
        exp_score = max(70.0, 100.0 - (pending_experiments * 8))
    scores.append(HealthDomainScore(
        domain=HealthDomain.EXPERIMENTS,
        score=exp_score,
        finding_count=pending_experiments,
    ))

    overall = compute_overall(scores, len(findings))
    scores.append(overall)
    return scores


def _category(finding) -> str:
    try:
        return finding.category.value if hasattr(finding.category, "value") else str(finding.category)
    except AttributeError:
        return "unknown"


def _evidence_strength(finding) -> str:
    try:
        return finding.evidence.strength.overall.value
    except AttributeError:
        return "insufficient"


def _frequency(finding) -> int:
    try:
        return finding.evidence.strength.sample_size
    except AttributeError:
        return 1
