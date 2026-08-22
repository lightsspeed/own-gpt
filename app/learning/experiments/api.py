"""
Experimentation Framework API — create experiments, run replays, review decisions.

V3.13: experiment EXECUTION (run/compare/evaluate) requires a checkout code
issued and operator-APPROVED through the Checkout Lane. No code, no approval,
wrong experiment, spent or revoked code → HTTP 403, nothing executes.
Definition (no execution) remains open.

V3.14: every authorized execution writes an immutable ExecutionResult into
the shared result store; GET /experiments/{experiment_id}/results/{execution_id}
exposes it read-only. Authorization secrets are NEVER serialized.

V3.15: read-only query surface — list results by experiment (newest-first)
and the append-only audit trail by experiment. Unknown experiment/execution
→ 404. The query API can never mutate, replay, or re-execute anything.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .authorization import (
    AuditLog,
    AuthorizationError,
    CheckoutLane,
    ExecutionResultStore,
)
from .models import ExperimentDefinition, ParameterChange, DecisionCandidate
from .runner import ReplayRunner
from .comparator import Comparator, build_decision_candidate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/experiments", tags=["experiments"])

# Process-wide registries (V3.14/3.15). Written by POST run/compare/evaluate
# and by the checkout lifecycle; read by the GET query endpoints. Results and
# audit events are immutable; these registries are the inspection surface,
# never mutation points.
_RESULT_STORE = ExecutionResultStore()
_AUDIT_LOG = AuditLog()


def _lane(runner=None) -> CheckoutLane:
    """Build the checkout lane writing into the shared registries."""
    return CheckoutLane(runner=runner, results_store=_RESULT_STORE,
                        audit_log=_AUDIT_LOG)


def _guarded(lane: CheckoutLane, code: str, experiment: ExperimentDefinition,
             limit: int):
    """Authorized experiment execution — fail closed on any checkout issue."""
    try:
        return lane.exchange(code, experiment, limit=limit)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/define", response_model=dict)
async def define_experiment(experiment: ExperimentDefinition):
    """Define a new experiment (immutable definition, not executed yet)."""
    return experiment.to_dict()


@router.post("/run", response_model=dict)
async def run_experiment(
    experiment: ExperimentDefinition,
    code: str = Query(..., min_length=1, description="Checkout code issued and approved via the Checkout Lane"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Run an experiment through the Checkout Lane (authorization required)."""
    result = _guarded(_lane(), code, experiment, limit)
    return result.to_dict()


@router.post("/compare", response_model=dict)
async def compare_experiment(
    experiment: ExperimentDefinition,
    code: str = Query(..., min_length=1, description="Checkout code issued and approved via the Checkout Lane"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Run an experiment (authorization required) and produce a comparison report."""
    result = _guarded(_lane(), code, experiment, limit)
    comparator = Comparator()
    report = comparator.compare(result)
    return report.to_dict()


@router.post("/evaluate", response_model=dict)
async def evaluate_experiment(
    experiment: ExperimentDefinition,
    code: str = Query(..., min_length=1, description="Checkout code issued and approved via the Checkout Lane"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Run an experiment (authorization required) and produce a DecisionCandidate."""
    result = _guarded(_lane(), code, experiment, limit)
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


@router.get("/{experiment_id}/results", response_model=dict)
async def list_execution_results(experiment_id: str):
    """
    Read-only: list execution results for one experiment, newest-first.

    Never exposes authorization secrets — ExperimentResult.to_dict() excludes
    the raw checkout code and its value.
    """
    results = _RESULT_STORE.list_by_experiment(experiment_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"no execution results for experiment '{experiment_id}'",
        )
    return {
        "experiment_id": experiment_id,
        "total": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.get("/{experiment_id}/results/{execution_id}", response_model=dict)
async def get_execution_result(experiment_id: str, execution_id: str):
    """
    Read-only: fetch one immutable execution result by its execution_id.

    Never exposes authorization secrets: the raw checkout code and its value
    are excluded from serialization by ExperimentResult.to_dict().
    """
    result = _RESULT_STORE.get(experiment_id, execution_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"no execution result for experiment '{experiment_id}' "
                   f"execution '{execution_id}'",
        )
    return result.to_dict()


@router.get("/{experiment_id}/audit", response_model=dict)
async def list_experiment_audit(experiment_id: str):
    """
    Read-only: append-only authorization history for one experiment,
    newest-first. Events include status transitions and execution ids but
    never the raw code, key, or value.
    """
    events = _AUDIT_LOG.list_by_experiment(experiment_id)
    if not events:
        raise HTTPException(
            status_code=404,
            detail=f"no audit trail for experiment '{experiment_id}'",
        )
    return {
        "experiment_id": experiment_id,
        "total": len(events),
        "events": [e.to_dict() for e in events],
    }