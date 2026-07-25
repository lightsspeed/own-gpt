"""Operations Control Plane — aggregation endpoints for the five workspaces.

Transforms backend intelligence into actionable operator workflows.
Each workspace provides: Overview, Evidence, Lineage, Metrics, Related, Actions.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..analytics.engine import AnalyticsEngine
from ..evidence.engine import EvidenceEngine
from ..evidence.models import EvidenceStrengthLabel
from ..experiments.runner import ReplayRunner
from ..experiments.comparator import Comparator, build_decision_candidate
from ..experiments.models import ExperimentDefinition, DecisionCandidate, DecisionStatus
from ..config.manager import ConfigManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/operations", tags=["operations"])


# ── Helpers ────────────────────────────────────────────────────────────

SEVERITY_WEIGHTS = {"critical": 100, "high": 75, "medium": 50, "low": 25}
STRENGTH_WEIGHTS = {"high": 1.0, "medium": 0.6, "low": 0.3, "insufficient": 0.1}


def compute_priority(severity: str, strength_label: str, frequency: int, trend: str) -> int:
    """Priority score: severity × evidence_strength × frequency × trend."""
    sev = SEVERITY_WEIGHTS.get(severity.lower(), 25)
    strength = STRENGTH_WEIGHTS.get(strength_label.lower(), 0.1)
    freq_factor = min(frequency / 10, 2.0)
    trend_factor = 1.5 if trend == "increasing" else 1.0 if trend == "stable" else 0.7
    return int(sev * strength * freq_factor * trend_factor)


def get_evidence_strength_label(finding) -> str:
    """Extract evidence strength label from a finding."""
    try:
        return finding.evidence.strength.overall.value
    except AttributeError:
        return "insufficient"


def get_frequency(finding) -> int:
    """Extract frequency/sample_size from a finding."""
    try:
        return finding.evidence.strength.sample_size
    except AttributeError:
        return 1


def get_trend(finding) -> str:
    """Extract trend from a finding."""
    try:
        return finding.evidence.strength.trend
    except AttributeError:
        return "stable"


# ── Workspace 1: Findings ──────────────────────────────────────────────


@router.get("/findings", response_model=dict)
async def findings_workspace(
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    min_priority: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Prioritized findings inbox. Filters available for the operator."""
    ee = EvidenceEngine()
    report = ee.analyze()

    findings = []
    for f in report.findings:
        sev = f.severity.lower()
        cat = f.category.value if hasattr(f.category, "value") else str(f.category)
        strength = get_evidence_strength_label(f)
        freq = get_frequency(f)
        trend = get_trend(f)
        priority = compute_priority(sev, strength, freq, trend)

        if category and cat != category:
            continue
        if severity and sev != severity:
            continue
        if priority < min_priority:
            continue
        if strength == "insufficient" and priority < 30:
            continue

        findings.append({
            "priority": priority,
            "id": f.id,
            "category": cat,
            "severity": sev,
            "title": f.title,
            "description": f.description[:120],
            "evidence_strength": strength,
            "evidence_confidence": round(f.evidence.strength.confidence, 2),
            "sample_size": freq,
            "trend": trend,
            "root_cause": f.root_cause.category.value if hasattr(f.root_cause.category, "value") else str(f.root_cause.category),
            "recommendation_text": f.recommendation_text[:120],
            "created_at": f.created_at,
            "lineage": f.lineage.to_dict() if f.lineage else None,
        })

    findings.sort(key=lambda x: -x["priority"])

    return {
        "workspace": "findings",
        "total": len(findings),
        "priority_filters": {"severity": ["critical", "high", "medium", "low"],
                             "strength": ["high", "medium", "low", "insufficient"]},
        "findings": findings[:limit],
    }


# ── Workspace 2: Recommendations ──────────────────────────────────────


@router.get("/recommendations", response_model=dict)
async def recommendations_workspace(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Recommendation review workspace — PR-style with full lineage."""
    ae = AnalyticsEngine()
    ee = EvidenceEngine()

    query_report = ae.query.analyze()
    retrieval_report = ae.retrieval.analyze()
    routing_report = ae.routing.analyze()
    evidence_report = ee.analyze(
        query_report=query_report,
        retrieval_report=retrieval_report,
        routing_report=routing_report,
    )

    recs = ae.recommendations.from_findings(evidence_report.findings)
    results = []
    for r in recs.all:
        rtype = r.type.value if hasattr(r.type, "value") else str(r.type)
        rstatus = r.status.value if hasattr(r.status, "value") else str(r.status)
        if status and rstatus != status:
            continue
        results.append({
            "id": r.id,
            "type": rtype,
            "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
            "title": r.title,
            "description": r.description,
            "status": rstatus,
            "finding_id": r.finding_id,
            "evidence": r.evidence if isinstance(r.evidence, dict) else {"note": "See linked finding"},
            "lineage": r.lineage.to_dict() if r.lineage else None,
        })

    return {
        "workspace": "recommendations",
        "total": len(results),
        "recommendations": results[:limit],
    }


@router.get("/recommendations/{rec_id}", response_model=dict)
async def recommendation_detail(rec_id: str):
    """Full detail for a single recommendation — with trace to finding and evidence."""
    ae = AnalyticsEngine()
    ee = EvidenceEngine()
    query_report = ae.query.analyze()
    retrieval_report = ae.retrieval.analyze()
    routing_report = ae.routing.analyze()
    evidence_report = ee.analyze(
        query_report=query_report,
        retrieval_report=retrieval_report,
        routing_report=routing_report,
    )
    recs = ae.recommendations.from_findings(evidence_report.findings)

    for r in recs.all:
        if r.id == rec_id:
            # Find the linked finding
            linked_finding = None
            for f in evidence_report.findings:
                if f.id == r.finding_id:
                    linked_finding = f
                    break
            return {
                "recommendation": r.to_dict(),
                "finding": linked_finding.to_dict() if linked_finding else None,
                "actions": ["create_experiment", "dismiss", "approve"],
            }

    raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")


# ── Workspace 3: Experiments ──────────────────────────────────────────


@router.get("/experiments", response_model=dict)
async def experiments_workspace(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Experiment history with lifecycle states."""
    # For now, experiments are not persisted (future: SQLite store).
    # This endpoint returns the stored snapshots as experiment records.
    cm = ConfigManager()
    snapshots = cm.list_snapshots(limit=limit)
    experiments = []
    for s in snapshots:
        if status and status != "completed":
            continue
        experiments.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "status": "completed" if s.is_current else "archived",
            "config_version": s.version,
            "decision_id": s.created_from_decision_id,
            "parameter_count": len(s.parameters),
            "created_at": s.created_at,
            "lineage": s.lineage.to_dict() if s.lineage else None,
        })

    return {
        "workspace": "experiments",
        "total": len(experiments),
        "statuses": ["draft", "running", "completed", "reviewed", "archived"],
        "experiments": experiments[:limit],
    }


# ── Workspace 4: Decisions ────────────────────────────────────────────


@router.get("/decisions", response_model=dict)
async def decisions_workspace(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Decision history — approved/rejected experiments with full trace."""
    cm = ConfigManager()
    snapshots = cm.list_snapshots(limit=limit)
    decisions = []
    for s in snapshots:
        if not s.created_from_decision_id:
            continue
        d_status = "approved" if s.is_current else "archived"
        if status and d_status != status:
            continue
        decisions.append({
            "id": s.created_from_decision_id,
            "experiment_id": s.created_from_experiment_id,
            "config_snapshot_id": s.id,
            "config_version": s.version,
            "status": d_status,
            "name": s.name,
            "description": s.description,
            "applied_at": s.created_at,
            "lineage": s.lineage.to_dict() if s.lineage else None,
        })

    decisions.sort(key=lambda x: x.get("config_version", 0), reverse=True)
    return {
        "workspace": "decisions",
        "total": len(decisions),
        "decisions": decisions[:limit],
    }


# ── Workspace 5: Configuration ────────────────────────────────────────


@router.get("/configurations", response_model=dict)
async def configurations_workspace(limit: int = Query(50, ge=1, le=200)):
    """Configuration workspace — snapshots, current pointer, rollback."""
    cm = ConfigManager()
    current = cm.get_current()
    snapshots = cm.list_snapshots(limit=limit)
    return {
        "workspace": "configurations",
        "current": current.to_dict() if current else None,
        "snapshots": [s.to_dict() for s in snapshots],
        "actions": ["create_snapshot", "rollback"],
    }


@router.post("/configurations/rollback/{snapshot_id}", response_model=dict)
async def rollback_configuration(snapshot_id: str):
    """Rollback current configuration to a previous snapshot."""
    cm = ConfigManager()
    snap = cm.rollback(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return {"status": "rolled_back", "snapshot": snap.to_dict()}


# ── Artifact Explorer ─────────────────────────────────────────────────


@router.get("/explore/{artifact_id}", response_model=dict)
async def explore_artifact(artifact_id: str):
    """Full lineage traversal: trace any artifact ID through the entire chain."""
    chain = []
    visited = set()
    current_id = artifact_id

    cm = ConfigManager()
    ee = EvidenceEngine()

    max_depth = 10
    while current_id and len(chain) < max_depth and current_id not in visited:
        visited.add(current_id)

        if current_id.startswith("cfg-"):
            snap = cm.load_snapshot(current_id)
            if snap:
                chain.append({"type": "configuration_snapshot", "data": snap.to_dict()})
                current_id = snap.created_from_decision_id
                continue

        if current_id.startswith("dec-"):
            chain.append({"type": "decision", "data": {"id": current_id, "note": "Decision record (stub)"}})
            break

        if current_id.startswith("dc-"):
            chain.append({"type": "decision_candidate", "data": {"id": current_id, "note": "Decision candidate (stub)"}})
            break

        if current_id.startswith("exp-"):
            chain.append({"type": "experiment", "data": {"id": current_id}})
            # Try to find parent recommendation via config manager lineage
            for snap in cm.list_snapshots():
                if snap.created_from_experiment_id == current_id:
                    if snap.lineage and snap.lineage.parent_artifact_id:
                        current_id = snap.lineage.parent_artifact_id
                        break
            else:
                current_id = None
            continue

        if current_id.startswith("rec-"):
            chain.append({"type": "recommendation", "data": {"id": current_id}})
            # Find the finding that produced this recommendation
            er = ee.analyze()
            for f in er.findings:
                if hasattr(f, 'id') and f.id and f.id.startswith("fi-"):
                    current_id = f.id
                    break
            else:
                current_id = None
            continue

        if current_id.startswith("fi-"):
            chain.append({"type": "finding", "data": {"id": current_id}})
            current_id = None
            continue

        if current_id.startswith("ev-"):
            chain.append({"type": "evidence", "data": {"id": current_id}})
            current_id = None
            continue

        # Unknown — stop
        chain.append({"type": "unknown", "data": {"id": current_id}})
        break

    return {
        "root_artifact_id": artifact_id,
        "chain": chain,
        "depth": len(chain),
    }
