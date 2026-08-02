"""
Answer Quality API — admin review of citation and grounding validation.

Intended for admins only. The platform has no auth yet; when auth is added,
gate these endpoints behind an admin role check.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..storage.sqlite import LearningStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quality", tags=["quality"])


def get_store() -> LearningStore:
    return LearningStore()


@router.get("/reports", response_model=dict)
async def list_quality_reports(
    limit: int = Query(50, ge=1, le=500),
    store: LearningStore = Depends(get_store),
):
    reports = store.list_quality_reports(limit=limit)
    return {"count": len(reports), "reports": reports}


@router.get("/reports/{record_id}", response_model=dict)
async def get_quality_report(record_id: str, store: LearningStore = Depends(get_store)):
    report = store.get_quality_report(record_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Quality report not found")
    return report
