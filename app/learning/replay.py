"""
Replay support — load historical records to replay queries against a new pipeline.

Usage:
    from app.learning.replay import load_records_for_replay
    records = load_records_for_replay(intent="knowledge", limit=10)
    for r in records:
        ctx = pipeline.process(question=r.question, session_id=f"replay-{r.record_id}")
        # compare ctx.answer_mode, ctx.confidence, etc. with r.answer_mode, r.confidence
"""

from __future__ import annotations

from typing import Optional

from .models import LearningRecord
from .storage.sqlite import LearningStore


def load_records_for_replay(
    intent: Optional[str] = None,
    answer_mode: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 100,
) -> list[LearningRecord]:
    """
    Load LearningRecords suitable for replaying against a new pipeline version.

    Filters by optional criteria. Returns records with sufficient metadata
    to reconstruct the original query context.
    """
    store = LearningStore()
    filters = {}
    if intent:
        filters["intent"] = intent
    if answer_mode:
        filters["answer_mode"] = answer_mode

    records = store.query_records(**filters)

    if min_confidence is not None:
        records = [r for r in records if r.confidence >= min_confidence]

    return records[:limit]
