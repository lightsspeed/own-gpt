"""
Analytics Engine — turns the Learning Ledger into operational intelligence.

Read-only computations over LearningRecords and UserEvents.
Generates evidence-backed Recommendations for human review.
"""

from .engine import AnalyticsEngine
from .queries import QueryIntelligence
from .retrieval import RetrievalIntelligence
from .routing import RoutingAnalytics
from .behavior import UserBehavior
from .trends import TrendAnalytics
from .recommendations import RecommendationGenerator

__all__ = [
    "AnalyticsEngine",
    "QueryIntelligence",
    "RetrievalIntelligence",
    "RoutingAnalytics",
    "UserBehavior",
    "TrendAnalytics",
    "RecommendationGenerator",
]
