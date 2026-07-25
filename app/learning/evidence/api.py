"""
Evidence Engine API endpoints — read-only findings and diagnostics.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from .engine import EvidenceEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evidence", tags=["evidence"])


def get_engine() -> EvidenceEngine:
    return EvidenceEngine()


@router.get("/findings", response_model=dict)
async def findings(engine: EvidenceEngine = Depends(get_engine)):
    """All findings across all evidence modules."""
    report = engine.analyze()
    return report.to_dict()


@router.get("/calibration", response_model=dict)
async def calibration(engine: EvidenceEngine = Depends(get_engine)):
    """Confidence calibration report (buckets, ECE, over/underconfidence)."""
    report = engine._calibration.analyze()
    return report.to_dict()


@router.get("/failure-tree", response_model=dict)
async def failure_tree(engine: EvidenceEngine = Depends(get_engine)):
    """Retrieval failure tree classification."""
    report = engine._failure_tree.analyze()
    return report.to_dict()
