"""Configuration Management API — snapshots, current pointer, diffs, rollback."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from .manager import ConfigManager
from .models import ConfigurationSnapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["config"])


def get_manager() -> ConfigManager:
    return ConfigManager()


@router.get("/snapshots", response_model=list[dict])
async def list_snapshots(manager: ConfigManager = Depends(get_manager)):
    return [s.to_dict() for s in manager.list_snapshots()]


@router.get("/snapshots/{snapshot_id}", response_model=dict)
async def get_snapshot(snapshot_id: str, manager: ConfigManager = Depends(get_manager)):
    snap = manager.load_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snap.to_dict()


@router.post("/snapshots", response_model=dict)
async def create_snapshot(
    name: str = "",
    description: str = "",
    decision_id: str | None = None,
    experiment_id: str | None = None,
    manager: ConfigManager = Depends(get_manager),
):
    # Read current pipeline config. For now, capture default params.
    # In production this would read from the live pipeline config.
    params = {
        "retriever_top_k": 10,
        "bm25_weight": 0.5,
        "reranker_threshold": 0.35,
        "confidence_threshold": 0.3,
        "chunk_size": 512,
        "chunk_overlap": 64,
        "embedding_model": "default",
        "reranker_model": "default",
        "prompt_version": "default",
    }
    snap = manager.create_from_dict(
        params=params,
        name=name or f"Config v{(manager.get_current().version + 1) if manager.get_current() else 1}",
        description=description,
        decision_id=decision_id,
        experiment_id=experiment_id,
    )
    return snap.to_dict()


@router.get("/current", response_model=dict)
async def get_current(manager: ConfigManager = Depends(get_manager)):
    current = manager.get_current()
    if not current:
        return {"note": "No current configuration set"}
    return current.to_dict()


@router.post("/current/{snapshot_id}", response_model=dict)
async def set_current(snapshot_id: str, manager: ConfigManager = Depends(get_manager)):
    ok = manager.set_current(snapshot_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return manager.get_current().to_dict()


@router.get("/diff", response_model=dict)
async def diff_snapshots(snapshot_a: str, snapshot_b: str, manager: ConfigManager = Depends(get_manager)):
    diff = manager.diff(snapshot_a, snapshot_b)
    if not diff:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")
    return diff.to_dict()


@router.get("/diff/current/{snapshot_id}", response_model=dict)
async def diff_against_current(snapshot_id: str, manager: ConfigManager = Depends(get_manager)):
    diff = manager.diff_current(snapshot_id)
    if not diff:
        raise HTTPException(status_code=404, detail="Snapshot or current config not found")
    return diff.to_dict()


@router.post("/rollback/{snapshot_id}", response_model=dict)
async def rollback(snapshot_id: str, manager: ConfigManager = Depends(get_manager)):
    snap = manager.rollback(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Cannot rollback: snapshot {snapshot_id} not found")
    return snap.to_dict()
