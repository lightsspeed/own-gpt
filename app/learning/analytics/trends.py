"""
TrendAnalytics — time-series analysis of learning data.

Provides daily/weekly/monthly aggregations of volume, confidence, and behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..storage.sqlite import LearningStore

logger = logging.getLogger(__name__)


@dataclass
class TrendAnalyticsReport:
    daily_volume: list[dict] = field(default_factory=list)
    daily_confidence: list[dict] = field(default_factory=list)
    weekly_growth: dict = field(default_factory=dict)
    top_days: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "daily_volume": self.daily_volume,
            "daily_confidence": self.daily_confidence,
            "weekly_growth": self.weekly_growth,
            "top_days": self.top_days[:10],
        }


class TrendAnalytics:
    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> TrendAnalyticsReport:
        return TrendAnalyticsReport(
            daily_volume=self._daily_volume(),
            daily_confidence=self._daily_confidence(),
            weekly_growth=self._weekly_growth(),
            top_days=self._top_days(),
        )

    def _daily_volume(self, limit: int = 90) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT DATE(timestamp) AS day,
                   COUNT(*) AS queries,
                   COUNT(DISTINCT question_hash) AS unique_questions,
                   ROUND(COUNT(DISTINCT question_hash) * 1.0 / MAX(COUNT(*), 1), 3) AS novelty_rate
            FROM learning_records
            WHERE timestamp IS NOT NULL
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
        """, [limit])
        return list(reversed(rows))

    def _daily_confidence(self, limit: int = 90) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT DATE(timestamp) AS day,
                   ROUND(AVG(confidence), 3) AS avg_confidence,
                   ROUND(AVG(CASE WHEN accepted = 1 THEN 1.0 ELSE 0.0 END), 3) AS avg_accept,
                   COUNT(*) AS queries
            FROM learning_records
            WHERE timestamp IS NOT NULL AND confidence > 0
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
        """, [limit])
        return list(reversed(rows))

    def _weekly_growth(self) -> dict:
        """Compare the most recent full week to the prior week."""
        rows = self._store.query_sql("""
            WITH weeks AS (
              SELECT
                STRFTIME('%Y-%W', timestamp) AS week,
                COUNT(*) AS queries,
                ROUND(AVG(confidence), 3) AS avg_confidence
              FROM learning_records
              WHERE timestamp IS NOT NULL
              GROUP BY week
            )
            SELECT * FROM weeks ORDER BY week DESC LIMIT 2
        """)
        if len(rows) < 2:
            return {"note": "Need at least 2 weeks of data"}
        current, previous = rows[0], rows[1]
        growth = ((current["queries"] - previous["queries"]) / max(previous["queries"], 1)) * 100
        conf_change = ((current["avg_confidence"] or 0) - (previous["avg_confidence"] or 0)) * 100
        return {
            "current_week": current["week"],
            "previous_week": previous["week"],
            "current_queries": current["queries"],
            "previous_queries": previous["queries"],
            "query_growth_pct": round(growth, 1),
            "current_avg_confidence": current["avg_confidence"],
            "confidence_change_pct": round(conf_change, 1),
        }

    def _top_days(self, limit: int = 10) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT DATE(timestamp) AS day,
                   COUNT(*) AS queries,
                   ROUND(AVG(confidence), 3) AS avg_confidence
            FROM learning_records
            WHERE timestamp IS NOT NULL
            GROUP BY day
            ORDER BY queries DESC
            LIMIT ?
        """, [limit])
        return rows
