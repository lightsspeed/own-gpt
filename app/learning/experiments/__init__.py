"""
Experimentation Framework — offline optimization environment.

Consumes:
  - Learning Ledger records (via ReplayRunner)
  - Benchmarks (future)
  - Evidence Engine Findings (via recommendation_id)

Produces:
  - ExperimentResult (metrics + deltas)
  - ComparisonReport (wins / losses / verdict)
  - DecisionCandidate (system proposal for human review)
"""

from .models import (
    ExperimentDefinition, ExperimentResult, ExperimentStatus,
    ParameterChange, ParameterDomain,
    DecisionCandidate, Decision, DecisionStatus,
)
from .runner import ReplayRunner
from .comparator import Comparator, ComparisonReport, build_decision_candidate

__all__ = [
    "ExperimentDefinition", "ExperimentResult", "ExperimentStatus",
    "ParameterChange", "ParameterDomain",
    "DecisionCandidate", "Decision", "DecisionStatus",
    "ReplayRunner",
    "Comparator", "ComparisonReport", "build_decision_candidate",
]
