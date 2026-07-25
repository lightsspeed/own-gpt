"""
Experimentation Framework API — create experiments, run replays, review decisions.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .models import ExperimentDefinition, ParameterChange, DecisionCandidate
from .runner import ReplayRunner
from .comparator import Comparator, build_decision_candidate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("/define", response_model=dict)
async def define_experiment(experiment: ExperimentDefinition):
    """Define a new experiment (immutable definition, not executed yet)."""
    return experiment.to_dict()


@router.post("/run", response_model=dict)
async def run_experiment(
    experiment: ExperimentDefinition,
    limit: int = Query(200, ge=1, le=2000),
):
    """Define and run an experiment immediately."""
    runner = ReplayRunner()
    result = runner.run(experiment, limit=limit)
    return result.to_dict()


@router.post("/compare", response_model=dict)
async def compare_experiment(
    experiment: ExperimentDefinition,
    limit: int = Query(200, ge=1, le=2000),
):
    """Run an experiment and produce a comparison report."""
    runner = ReplayRunner()
    result = runner.run(experiment, limit=limit)
    comparator = Comparator()
    report = comparator.compare(result)
    return report.to_dict()


@router.post("/evaluate", response_model=dict)
async def evaluate_experiment(
    experiment: ExperimentDefinition,
    limit: int = Query(200, ge=1, le=2000),
):
    """Run an experiment and produce a DecisionCandidate."""
    runner = ReplayRunner()
    result = runner.run(experiment, limit=limit)
    comparator = Comparator()
    report = comparator.compare(result)
    candidate = build_decision_candidate(
        experiment_id=experiment.id,
        comparison=report,
        recommendation_id=experiment.recommendation_id,
    )
    return {
        "experiment": experiment.to_dict(),
        "result": result.to_dict(),
        "comparison": report.to_dict(),
        "decision_candidate": candidate.to_dict(),
    }
