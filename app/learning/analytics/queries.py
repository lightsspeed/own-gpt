"""
QueryIntelligence — analyzes what users are asking and identifies knowledge gaps.

Reports:
  - Top N repeated questions (by question_hash)
  - Lowest confidence questions
  - Most failed (low confidence, thumbs down, regenerated)
  - Knowledge gaps (repeated low-confidence queries on similar topics)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..storage.sqlite import LearningStore

logger = logging.getLogger(__name__)


@dataclass
class QueryIntelligenceReport:
    top_queries: list[dict] = field(default_factory=list)
    lowest_confidence: list[dict] = field(default_factory=list)
    most_failed: list[dict] = field(default_factory=list)
    most_regenerated: list[dict] = field(default_factory=list)
    highest_copy_rate: list[dict] = field(default_factory=list)
    knowledge_gaps: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "top_queries": self.top_queries[:20],
            "lowest_confidence": self.lowest_confidence[:20],
            "most_failed": self.most_failed[:20],
            "most_regenerated": self.most_regenerated[:10],
            "highest_copy_rate": self.highest_copy_rate[:10],
            "knowledge_gaps": self.knowledge_gaps[:20],
        }


class QueryIntelligence:
    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> QueryIntelligenceReport:
        return QueryIntelligenceReport(
            top_queries=self._top_queries(),
            lowest_confidence=self._lowest_confidence(),
            most_failed=self._most_failed(),
            most_regenerated=self._most_regenerated(),
            highest_copy_rate=self._highest_copy_rate(),
            knowledge_gaps=self._knowledge_gaps(),
        )

    def _top_queries(self, limit: int = 100) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT question_hash,
                   MAX(SUBSTR(normalized_question, 1, 120)) AS sample,
                   COUNT(*) AS count,
                   ROUND(AVG(confidence), 3) AS avg_confidence,
                   ROUND(AVG(CASE WHEN accepted = 1 THEN 1.0 ELSE 0.0 END), 3) AS accept_rate
            FROM learning_records
            WHERE question_hash IS NOT NULL AND question_hash != ''
            GROUP BY question_hash
            ORDER BY count DESC
            LIMIT ?
        """, [limit])
        return rows

    def _lowest_confidence(self, limit: int = 20) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT question_hash,
                   MAX(SUBSTR(normalized_question, 1, 120)) AS sample,
                   COUNT(*) AS count,
                   ROUND(AVG(confidence), 3) AS avg_confidence,
                   answer_mode,
                   MAX(timestamp) AS last_seen
            FROM learning_records
            WHERE confidence > 0 AND confidence IS NOT NULL
            GROUP BY question_hash
            HAVING count >= 2
            ORDER BY avg_confidence ASC
            LIMIT ?
        """, [limit])
        return rows

    def _most_failed(self, limit: int = 20) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT question_hash,
                   MAX(SUBSTR(normalized_question, 1, 120)) AS sample,
                   COUNT(*) AS total,
                   SUM(CASE WHEN accepted = 0 THEN 1 ELSE 0 END) AS failures,
                   ROUND(AVG(CASE WHEN accepted = 0 THEN 1.0 ELSE 0.0 END), 3) AS fail_rate,
                   MAX(failure_reason) AS common_reason
            FROM learning_records
            WHERE question_hash IS NOT NULL AND question_hash != ''
            GROUP BY question_hash
            HAVING failures > 0
            ORDER BY failures DESC
            LIMIT ?
        """, [limit])
        return rows

    def _most_regenerated(self, limit: int = 10) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT lr.question_hash,
                   MAX(SUBSTR(lr.normalized_question, 1, 120)) AS sample,
                   COUNT(*) AS total_queries,
                   COUNT(ue.event_id) AS regens
            FROM learning_records lr
            LEFT JOIN user_events ue ON ue.record_id = lr.record_id AND ue.type = 'regenerate'
            WHERE lr.question_hash IS NOT NULL AND lr.question_hash != ''
            GROUP BY lr.question_hash
            HAVING regens > 0
            ORDER BY regens DESC
            LIMIT ?
        """, [limit])
        return rows

    def _highest_copy_rate(self, limit: int = 10) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT lr.question_hash,
                   MAX(SUBSTR(lr.normalized_question, 1, 120)) AS sample,
                   COUNT(DISTINCT lr.record_id) AS total,
                   COUNT(DISTINCT ue.event_id) AS copies,
                   ROUND(CAST(COUNT(DISTINCT ue.event_id) AS REAL) / MAX(COUNT(DISTINCT lr.record_id), 1), 3) AS copy_rate
            FROM learning_records lr
            LEFT JOIN user_events ue ON ue.record_id = lr.record_id AND ue.type = 'copy'
            WHERE lr.question_hash IS NOT NULL AND lr.question_hash != ''
            GROUP BY lr.question_hash
            HAVING total >= 3
            ORDER BY copy_rate DESC
            LIMIT ?
        """, [limit])
        return rows

    def _knowledge_gaps(self, limit: int = 20) -> list[dict]:
        """
        Detect knowledge gaps: repeated queries with low confidence,
        high synthesis rate, or high thumbs-down rate.
        These suggest topics users expect the KB to cover but don't.
        """
        rows = self._store.query_sql("""
            SELECT lr.question_hash,
                   MAX(SUBSTR(lr.normalized_question, 1, 120)) AS sample,
                   COUNT(*) AS count,
                   ROUND(AVG(lr.confidence), 3) AS avg_confidence,
                   ROUND(SUM(CASE WHEN lr.answer_mode = 'synthesis' THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3) AS synthesis_rate,
                   COUNT(ue_thumb.event_id) AS thumbs_down
            FROM learning_records lr
            LEFT JOIN user_events ue_thumb ON ue_thumb.record_id = lr.record_id AND ue_thumb.type = 'thumb_down'
            WHERE lr.question_hash IS NOT NULL AND lr.question_hash != ''
            GROUP BY lr.question_hash
            HAVING count >= 2 AND (avg_confidence < 0.50 OR synthesis_rate > 0.50 OR thumbs_down >= 2)
            ORDER BY (avg_confidence * (1.0 - synthesis_rate)) ASC
            LIMIT ?
        """, [limit])
        return rows
