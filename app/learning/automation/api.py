"""Continuous Evaluation API — run jobs, view snapshots, health, and briefs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from .scheduler import run_job, get_run_history, get_schedules
from .state import SnapshotStore
from .reports import generate_daily_brief
from .jobs import run_daily_evaluation
from .models import JobType, AutomationRun

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/automation", tags=["automation"])


def get_store() -> SnapshotStore:
    return SnapshotStore()


# ── Jobs ───────────────────────────────────────────────────────────────


@router.post("/run/daily-evaluation", response_model=dict)
async def run_daily_evaluation_endpoint():
    """Run a full daily evaluation immediately."""
    run = run_daily_evaluation()
    return run.to_dict()


@router.post("/run/{job_type}", response_model=dict)
async def run_job_endpoint(job_type: str):
    """Execute a job immediately."""
    try:
        jt = JobType(job_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown job type: {job_type}")
    run = run_job(jt)
    return run.to_dict()


@router.get("/history", response_model=list[dict])
async def run_history(limit: int = Query(50, ge=1, le=200)):
    """Recent automation run history."""
    return [r.to_dict() for r in get_run_history(limit=limit)]


@router.get("/schedules", response_model=list[dict])
async def schedules():
    """Current schedule definitions."""
    return [{
        "job_type": s.job_type.value,
        "cadence": s.cadence.value,
        "enabled": s.enabled,
        "description": s.description,
        "timeout_minutes": s.timeout_minutes,
    } for s in get_schedules()]


# ── Snapshots ──────────────────────────────────────────────────────────


@router.get("/snapshots", response_model=list[dict])
async def list_snapshots(limit: int = Query(50, ge=1, le=200), store: SnapshotStore = Depends(get_store)):
    return [s.to_dict() for s in store.list_all(limit=limit)]


@router.get("/snapshots/{snapshot_id}", response_model=dict)
async def get_snapshot(snapshot_id: str, store: SnapshotStore = Depends(get_store)):
    snap = store.load(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snap.to_dict()


@router.get("/snapshots/{snapshot_id}/diff", response_model=dict)
async def diff_snapshot(snapshot_id: str, store: SnapshotStore = Depends(get_store)):
    snap = store.load(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    if not snap.previous_snapshot_id:
        return {"note": "No previous snapshot for comparison", "snapshot": snap.to_dict()}
    diffed = store.diff(snapshot_id, snap.previous_snapshot_id)
    if not diffed:
        return {"note": "Could not compute diff", "snapshot": snap.to_dict()}
    return diffed.to_dict()


# ── Health ─────────────────────────────────────────────────────────────


@router.get("/health", response_model=dict)
async def current_health(store: SnapshotStore = Depends(get_store)):
    """Current health scores from the latest snapshot."""
    latest = store.latest()
    if not latest:
        return {"overall_health": None, "domains": {}, "note": "No evaluation snapshots yet"}
    return {
        "overall_health": latest.health_scores.get("overall"),
        "domains": {k: v for k, v in latest.health_scores.items() if k != "overall"},
        "snapshot_id": latest.id,
        "timestamp": latest.timestamp,
    }


# ── Daily Brief ────────────────────────────────────────────────────────


@router.get("/brief", response_model=dict)
async def daily_brief(snapshot_id: Optional[str] = Query(None)):
    """Generate the daily operator brief. Optionally from a specific snapshot."""
    brief = generate_daily_brief(snapshot_id=snapshot_id)
    return brief.to_dict()


@router.get("/brief/latest", response_model=dict)
async def latest_brief(store: SnapshotStore = Depends(get_store)):
    """Generate a brief from the latest snapshot (without re-running evaluation)."""
    latest = store.latest()
    if not latest:
        return {"note": "No evaluation data available yet. Run daily evaluation first."}
    brief = generate_daily_brief(snapshot_id=latest.id)
    return brief.to_dict()


# ── Triggers ───────────────────────────────────────────────────────────


@router.get("/triggers", response_model=list[dict])
async def current_triggers(store: SnapshotStore = Depends(get_store)):
    """Evaluate the latest snapshot and return active triggers."""
    from .triggers import TriggerEngine
    te = TriggerEngine(store)
    triggers = te.evaluate()
    return [t.to_dict() for t in triggers]
