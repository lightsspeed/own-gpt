"""
UserBehavior — analyzes how users interact with answers.

Reports:
  - Thumb up/down counts and rates
  - Copy rate
  - Regenerate rate
  - Best/worst performing contexts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..storage.sqlite import LearningStore

logger = logging.getLogger(__name__)


@dataclass
class UserBehaviorReport:
    summary: dict = field(default_factory=dict)
    event_counts: dict = field(default_factory=dict)
    by_intent: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"summary": self.summary, "event_counts": self.event_counts, "by_intent": self.by_intent}


class UserBehavior:
    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> UserBehaviorReport:
        raw_counts = self._store.count_events_by_type()
        total_records = max(self._store.count_records(), 1)
        summary = {
            "total_records": self._store.count_records(),
            "total_events": self._store.count_events(),
            "events_per_record": round(self._store.count_events() / total_records, 2),
            "thumb_up": raw_counts.get("thumb_up", 0),
            "thumb_down": raw_counts.get("thumb_down", 0),
            "copy": raw_counts.get("copy", 0),
            "regenerate": raw_counts.get("regenerate", 0),
            "copy_rate": round(raw_counts.get("copy", 0) / total_records, 3),
            "regenerate_rate": round(raw_counts.get("regenerate", 0) / total_records, 3),
            "thumb_rate": round(
                (raw_counts.get("thumb_up", 0) + raw_counts.get("thumb_down", 0)) / total_records, 3
            ),
        }
        return UserBehaviorReport(summary=summary, event_counts=raw_counts, by_intent=self._behavior_by_intent())

    def _behavior_by_intent(self) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT lr.intent,
                   COUNT(DISTINCT lr.record_id) AS records,
                   COUNT(DISTINCT u_thumb.event_id) AS thumbs,
                   COUNT(DISTINCT u_copy.event_id) AS copies,
                   COUNT(DISTINCT u_regen.event_id) AS regens
            FROM learning_records lr
            LEFT JOIN user_events u_thumb ON u_thumb.record_id = lr.record_id AND u_thumb.type IN ('thumb_up', 'thumb_down')
            LEFT JOIN user_events u_copy ON u_copy.record_id = lr.record_id AND u_copy.type = 'copy'
            LEFT JOIN user_events u_regen ON u_regen.record_id = lr.record_id AND u_regen.type = 'regenerate'
            WHERE lr.intent IS NOT NULL AND lr.intent != ''
            GROUP BY lr.intent
            ORDER BY records DESC
        """)
        return rows
