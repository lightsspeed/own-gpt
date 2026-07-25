"""
RoutingAnalytics — analyzes intent classification and routing decisions.

Reports:
  - Intent distribution
  - matched_rule distribution (rule-based vs LLM)
  - Confidence by intent
  - Re-routing patterns (if available)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..storage.sqlite import LearningStore

logger = logging.getLogger(__name__)


@dataclass
class RoutingAnalyticsReport:
    intent_distribution: dict = field(default_factory=dict)
    rule_distribution: dict = field(default_factory=dict)
    confidence_by_intent: list[dict] = field(default_factory=list)
    rule_vs_llm_rate: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "intent_distribution": self.intent_distribution,
            "rule_distribution": self.rule_distribution,
            "confidence_by_intent": self.confidence_by_intent,
            "rule_vs_llm_rate": self.rule_vs_llm_rate,
        }


class RoutingAnalytics:
    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> RoutingAnalyticsReport:
        return RoutingAnalyticsReport(
            intent_distribution=self._intent_distribution(),
            rule_distribution=self._rule_distribution(),
            confidence_by_intent=self._confidence_by_intent(),
            rule_vs_llm_rate=self._rule_vs_llm(),
        )

    def _intent_distribution(self) -> dict:
        return self._store.count_records_by_intent()

    def _rule_distribution(self) -> dict:
        rows = self._store.query_sql("""
            SELECT matched_rule, COUNT(*) AS cnt
            FROM learning_records
            WHERE matched_rule IS NOT NULL AND matched_rule != ''
            GROUP BY matched_rule
            ORDER BY cnt DESC
        """)
        return {r["matched_rule"]: r["cnt"] for r in rows}

    def _confidence_by_intent(self) -> list[dict]:
        rows = self._store.query_sql("""
            SELECT intent,
                   COUNT(*) AS total,
                   ROUND(AVG(confidence), 3) AS avg_confidence,
                   ROUND(AVG(CASE WHEN accepted = 1 THEN 1.0 ELSE 0.0 END), 3) AS accept_rate,
                   ROUND(COUNT(DISTINCT matched_rule) * 1.0 / MAX(COUNT(*), 1), 3) AS rule_diversity
            FROM learning_records
            WHERE intent IS NOT NULL AND intent != ''
            GROUP BY intent
            ORDER BY total DESC
        """)
        return rows

    def _rule_vs_llm(self) -> dict:
        """Count how often intent was decided by a rule vs the LLM classifier."""
        rows = self._store.query_sql("""
            SELECT
              CASE
                WHEN matched_rule IS NULL OR matched_rule = '' OR matched_rule LIKE 'LLM_%' THEN 'llm'
                ELSE 'rule'
              END AS source,
              COUNT(*) AS cnt
            FROM learning_records
            GROUP BY source
        """)
        result = {r["source"]: r["cnt"] for r in rows}
        total = sum(result.values()) or 1
        result["rule_pct"] = round(result.get("rule", 0) * 100.0 / total, 1)
        result["llm_pct"] = round(result.get("llm", 0) * 100.0 / total, 1)
        return result
