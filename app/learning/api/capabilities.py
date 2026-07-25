"""Capability Registry API — introspect platform capabilities."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..architecture.capabilities import to_dict, list_all, list_by_owner, list_by_stage, get

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("", response_model=dict)
async def all_capabilities():
    return to_dict()


@router.get("/{capability_id}", response_model=dict)
async def get_capability(capability_id: str):
    cap = get(capability_id)
    if not cap:
        return {"error": f"Unknown capability: {capability_id}"}
    return {
        "id": cap.id,
        "name": cap.name,
        "description": cap.description,
        "owner": cap.owner,
        "dependencies": list(cap.dependencies),
        "lifecycle_stage": cap.lifecycle_stage,
        "maturity": cap.maturity.value,
        "artifacts": list(cap.artifacts),
        "api_prefix": cap.api_prefix,
    }


@router.get("/filter/owner/{owner}", response_model=dict)
async def capabilities_by_owner(owner: str):
    caps = list_by_owner(owner)
    return {"count": len(caps), "capabilities": {c.id: c.name for c in caps}}


@router.get("/filter/stage/{stage}", response_model=dict)
async def capabilities_by_stage(stage: str):
    caps = list_by_stage(stage)
    return {"count": len(caps), "capabilities": {c.id: c.name for c in caps}}
