"""
Telemetry API — user action events and learning ledger queries.

POST /telemetry/events         — record a user action (thumb, copy, etc.)
POST /telemetry/thumb          — update thumb on a record
GET  /telemetry/dashboard      — basic counters for the learning dashboard
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..telemetry.collector import learning_collector

logger = logging.getLogger(__name__)
router = APIRouter()

# OpenAI pricing per 1K tokens (gpt-4o-mini) — mirrors app/evaluation/benchmark.py
COST_PER_1K_INPUT = 0.150
COST_PER_1K_OUTPUT = 0.600


class EventRequest(BaseModel):
    type: str
    record_id: str = ""
    session_id: str = ""
    metadata: dict = {}


class ThumbRequest(BaseModel):
    record_id: str
    thumb: str  # "up" | "down" | "none"


class EventResponse(BaseModel):
    status: str
    record_id: str


@router.post("/telemetry/events", response_model=EventResponse)
async def post_event(request: EventRequest):
    """Record a user action event. Supported types: thumb_up, thumb_down, copy, regenerate, retry, rename, share, bookmark, open_reference, feedback."""
    learning_collector.track_event(
        record_id=request.record_id,
        event_type=request.type,
        session_id=request.session_id,
        metadata=request.metadata,
    )
    return EventResponse(status="ok", record_id=request.record_id)


@router.post("/telemetry/thumb", response_model=EventResponse)
async def post_thumb(request: ThumbRequest):
    """Update the thumb (like/dislike) on a learning record."""
    learning_collector.update_thumb(request.record_id, request.thumb)
    learning_collector.track_event(
        record_id=request.record_id,
        event_type=f"thumb_{request.thumb}" if request.thumb != "none" else "thumb_none",
    )
    return EventResponse(status="ok", record_id=request.record_id)


@router.get("/telemetry/dashboard")
async def get_dashboard():
    """Return basic counters for the learning dashboard."""
    store = learning_collector.store
    records = store.count_records()
    events = store.count_events()
    by_type = store.count_events_by_type()
    by_intent = store.count_records_by_intent()

    thumbs_up = by_type.get("thumb_up", 0)
    thumbs_down = by_type.get("thumb_down", 0)
    total_thumbs = thumbs_up + thumbs_down
    thumb_rate = round(thumbs_up / total_thumbs * 100, 1) if total_thumbs else 0

    copies = by_type.get("copy", 0)
    regens = by_type.get("regenerate", 0)

    usage = store.usage_totals()
    total_tokens = usage["tokens_in"] + usage["tokens_out"]
    estimated_cost = (
        usage["tokens_in"] / 1000 * COST_PER_1K_INPUT
        + usage["tokens_out"] / 1000 * COST_PER_1K_OUTPUT
    )

    return {
        "learning_records": records,
        "user_events": events,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "thumb_approval_rate": thumb_rate,
        "copies": copies,
        "regenerations": regens,
        "events_by_type": by_type,
        "records_by_intent": by_intent,
        "usage": {
            "records": usage["records"],
            "tokens_in": usage["tokens_in"],
            "tokens_out": usage["tokens_out"],
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "cost_per_1k_input": COST_PER_1K_INPUT,
            "cost_per_1k_output": COST_PER_1K_OUTPUT,
        },
    }
