"""
AnalyticsEngine — orchestrates all analytics modules and returns a composite result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..storage.sqlite import LearningStore
from .queries import QueryIntelligence, QueryIntelligenceReport
from .retrieval import RetrievalIntelligence, RetrievalIntelligenceReport
from .routing import RoutingAnalytics, RoutingAnalyticsReport
from .behavior import UserBehavior, UserBehaviorReport
from .trends import TrendAnalytics, TrendAnalyticsReport
from .recommendations import RecommendationGenerator, RecommendationList

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsReport:
    generated_at: str = ""
    total_records: int = 0
    total_events: int = 0
    query: Optional[QueryIntelligenceReport] = None
    retrieval: Optional[RetrievalIntelligenceReport] = None
    routing: Optional[RoutingAnalyticsReport] = None
    behavior: Optional[UserBehaviorReport] = None
    trends: Optional[TrendAnalyticsReport] = None
    recommendations: Optional[RecommendationList] = None

    def to_dict(self) -> dict:
        d = {"generated_at": self.generated_at, "total_records": self.total_records, "total_events": self.total_events}
        for k in ("query", "retrieval", "routing", "behavior", "trends", "recommendations"):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = v.to_dict() if hasattr(v, "to_dict") else v
        return d


class AnalyticsEngine:
    """Orchestrates all analytics modules. Pure computation, no side effects."""

    def __init__(self, store: Optional[LearningStore] = None):
        self._store = store or LearningStore()
        self.query = QueryIntelligence(self._store)
        self.retrieval = RetrievalIntelligence(self._store)
        self.routing = RoutingAnalytics(self._store)
        self.behavior = UserBehavior(self._store)
        self.trends = TrendAnalytics(self._store)
        self.recommendations = RecommendationGenerator(self._store)

    @property
    def store(self) -> LearningStore:
        return self._store

    def run_all(self) -> AnalyticsReport:
        """Run all analytics modules and return a composite report."""
        qr = self.query.analyze()
        rr = self.retrieval.analyze()
        return AnalyticsReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_records=self._store.count_records(),
            total_events=self._store.count_events(),
            query=qr,
            retrieval=rr,
            routing=self.routing.analyze(),
            behavior=self.behavior.analyze(),
            trends=self.trends.analyze(),
            recommendations=self.recommendations.generate(
                query_report=qr,
                retrieval_report=rr,
                routing_report=self.routing.analyze(),
            ),
        )
