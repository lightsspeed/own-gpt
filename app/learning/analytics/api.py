"""
Analytics API endpoints — read-only dashboards for analytics data.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from .engine import AnalyticsEngine, AnalyticsReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_engine() -> AnalyticsEngine:
    return AnalyticsEngine()


@router.get("/overview", response_model=dict)
async def overview(engine: AnalyticsEngine = Depends(get_engine)):
    report = engine.run_all()
    return report.to_dict()


@router.get("/query", response_model=dict)
async def query_analytics(
    top_n: int = Query(20, ge=1, le=100),
    engine: AnalyticsEngine = Depends(get_engine),
):
    report = engine.query.analyze()
    return report.to_dict()


@router.get("/retrieval", response_model=dict)
async def retrieval_analytics(engine: AnalyticsEngine = Depends(get_engine)):
    report = engine.retrieval.analyze()
    return report.to_dict()


@router.get("/routing", response_model=dict)
async def routing_analytics(engine: AnalyticsEngine = Depends(get_engine)):
    report = engine.routing.analyze()
    return report.to_dict()


@router.get("/behavior", response_model=dict)
async def behavior_analytics(engine: AnalyticsEngine = Depends(get_engine)):
    report = engine.behavior.analyze()
    return report.to_dict()


@router.get("/trends", response_model=dict)
async def trends_analytics(engine: AnalyticsEngine = Depends(get_engine)):
    report = engine.trends.analyze()
    return report.to_dict()


@router.get("/recommendations", response_model=dict)
async def recommendations_analytics(engine: AnalyticsEngine = Depends(get_engine)):
    qr = engine.query.analyze()
    rr = engine.retrieval.analyze()
    ror = engine.routing.analyze()
    result = engine.recommendations.generate(query_report=qr, retrieval_report=rr, routing_report=ror)
    return result.to_dict()
