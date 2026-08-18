"""V3.13 Checkout Lane / AuthorizationCode — hermetic tests.

Covers the 14 required cases:
   1.  Issue creates an ISSUED AuthorizationCode artifact
   2.  Codes are unique; duplicate explicit codes are rejected
   3.  Operator approval (ISSUED -> APPROVED) records reviewer
   4.  Approved code executes the experiment exactly once
   5.  No approval -> exchange blocked, runner never called
   6.  Unknown code -> blocked (issue/approve/status/exchange)
   7.  Reuse prevention + idempotent exchange (same result, one run)
   8.  Cached results are per-code (no cross-code replay)
   9.  Approval bound to experiment_id (mismatch -> blocked)
  10.  Revocation blocks execution (issued and approved codes)
  11.  Failed execution -> FAILED, never retried
  12.  Transition history is append-only with actors
  13.  Capability Registry + ArtifactType integration
  14.  API: run without/with code (422/403/200)

Zero live API / DB / LLM calls.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.learning.architecture.artifacts import ArtifactType, ArtifactRegistry
from app.learning.architecture.capabilities import get as get_capability
from app.learning.experiments.authorization import (
    AuthorizationCode,
    AuthorizationError,
    AuthorizationStatus,
    CheckoutLane,
)
from app.learning.experiments.models import ExperimentDefinition, ExperimentResult


# ── Helpers ─────────────────────────────────────────────────────────────────

class FakeRunner:
    """Hermetic stand-in for ReplayRunner.run."""

    def __init__(self, error: Exception | None = None):
        self.calls = 0
        self.experiments: list = []
        self.limits: list = []
        self.error = error

    def __call__(self, experiment, limit=200):
        self.calls += 1
        self.experiments.append(experiment)
        self.limits.append(limit)
        if self.error is not None:
            raise self.error
        return ExperimentResult(
            experiment_id=experiment.id,
            summary=f"ran #{self.calls}",
            records_processed=3,
        )


def _experiment(exp_id="exp-1") -> ExperimentDefinition:
    return ExperimentDefinition(id=exp_id, name="reranker test", hypothesis="h")


def _lane(runner=None) -> CheckoutLane:
    return CheckoutLane(runner=runner or FakeRunner())


def _approved(lane: CheckoutLane, exp_id="exp-1", code=None, reviewer="alice") -> str:
    """Issue + approve a code; returns the code string."""
    c = lane.issue(exp_id, code=code)
    lane.approve(c.code, reviewer=reviewer)
    return c.code


# ── 1: Issue creates an ISSUED AuthorizationCode artifact ───────────────────

def test_issue_creates_issued_code():
    lane = _lane()
    code = lane.issue("exp-777", code="chk-abc", key="reranker-threshold",
                      value="0.85", actor="pipeline")

    assert isinstance(code, AuthorizationCode)
    assert code.code == "chk-abc"
    assert code.key == "reranker-threshold"
    assert code.value == "0.85"
    assert code.experiment_id == "exp-777"
    assert code.status == AuthorizationStatus.ISSUED
    assert code.id.startswith("authz-")
    assert code.created_at  # timestamp present
    # Artifact lineage: parent is the experiment.
    assert code.lineage is not None
    assert code.lineage.parent_artifact_id == "exp-777"
    assert code.lineage.parent_type == ArtifactType.EXPERIMENT
    # Auto-generated codes are distinct and non-empty.
    assert lane.issue("exp-777").code != lane.issue("exp-777").code


# ── 2: Duplicate explicit codes are rejected ────────────────────────────────

def test_duplicate_code_rejected():
    lane = _lane()
    lane.issue("exp-1", code="chk-dup")

    with pytest.raises(AuthorizationError, match="already exists"):
        lane.issue("exp-2", code="chk-dup")


# ── 3: Operator approval records the reviewer ───────────────────────────────

def test_approve_records_reviewer():
    lane = _lane()
    code = lane.issue("exp-1")

    approved = lane.approve(code.code, reviewer="alice")

    assert approved.status == AuthorizationStatus.APPROVED
    assert approved.approved_by == "alice"
    assert approved.approved_at
    # Approval survives in the event history with the reviewer.
    events = lane.history()
    assert events[-1].from_status == "issued"
    assert events[-1].to_status == "approved"
    assert events[-1].actor == "alice"


# ── 4: Approved code executes the experiment exactly once ───────────────────

def test_approved_code_runs_experiment():
    runner = FakeRunner()
    lane = _lane(runner)
    code = _approved(lane)

    result = lane.exchange(code, _experiment(), limit=350)

    assert runner.calls == 1
    assert runner.experiments[0].id == "exp-1"
    assert runner.limits == [350]
    assert result.experiment_id == "exp-1"
    assert lane.status_of(code) == AuthorizationStatus.CONSUMED
    assert lane._get(code).consumed_at  # single-use marker set


# ── 5: No approval -> exchange blocked, runner never called ─────────────────

def test_unapproved_code_blocked():
    runner = FakeRunner()
    lane = _lane(runner)
    code = lane.issue("exp-1")

    with pytest.raises(AuthorizationError, match="not approved"):
        lane.exchange(code.code, _experiment())

    assert runner.calls == 0
    assert lane.status_of(code.code) == AuthorizationStatus.ISSUED


# ── 6: Unknown code -> blocked everywhere ───────────────────────────────────

def test_unknown_code_blocked():
    lane = _lane()

    with pytest.raises(AuthorizationError, match="unknown checkout code"):
        lane.status_of("chk-nope")
    with pytest.raises(AuthorizationError, match="unknown checkout code"):
        lane.approve("chk-nope")
    with pytest.raises(AuthorizationError, match="unknown checkout code"):
        lane.exchange("chk-nope", _experiment())


# ── 7: Reuse prevention + idempotent exchange ───────────────────────────────

def test_consumed_code_replays_same_result_without_rerun():
    runner = FakeRunner()
    lane = _lane(runner)
    code = _approved(lane)

    first = lane.exchange(code, _experiment())
    second = lane.exchange(code, _experiment())  # identical logical exchange

    assert runner.calls == 1  # single execution, never doubled
    assert second is first    # same cached result object
    assert second.summary == "ran #1"


# ── 8: Cached results are per-code ──────────────────────────────────────────

def test_cached_result_is_per_code():
    runner = FakeRunner()
    lane = _lane(runner)

    c1 = _approved(lane, exp_id="exp-1")
    c2 = _approved(lane, exp_id="exp-1")  # second independent code

    r1 = lane.exchange(c1, _experiment())
    r2 = lane.exchange(c2, _experiment())

    assert runner.calls == 2  # both codes executed (no shared cache)
    assert r1 is not r2
    # Replaying c1 still returns c1's own cached result.
    assert lane.exchange(c1, _experiment()) is r1
    assert runner.calls == 2


# ── 9: Approval bound to experiment_id (mismatch -> blocked) ────────────────

def test_experiment_binding_enforced():
    runner = FakeRunner()
    lane = _lane(runner)
    code = _approved(lane, exp_id="exp-1")

    with pytest.raises(AuthorizationError, match="bound to experiment 'exp-1'"):
        lane.exchange(code, _experiment("exp-2"))

    assert runner.calls == 0
    assert lane.status_of(code) == AuthorizationStatus.APPROVED  # not spent


# ── 10: Revocation blocks execution ─────────────────────────────────────────

def test_revoke_blocks_issued_and_approved():
    runner = FakeRunner()
    lane = _lane(runner)

    issued = lane.issue("exp-1")
    lane.revoke(issued.code, actor="bob")
    assert lane.status_of(issued.code) == AuthorizationStatus.REVOKED
    with pytest.raises(AuthorizationError, match="revoked"):
        lane.exchange(issued.code, _experiment())

    approved = _approved(lane, exp_id="exp-1", code="chk-rev")
    lane.revoke(approved, actor="bob")
    with pytest.raises(AuthorizationError, match="revoked"):
        lane.exchange(approved, _experiment())

    assert runner.calls == 0

    # Terminal states cannot be revoked.
    spent = _approved(lane, exp_id="exp-1", code="chk-spent")
    lane.exchange(spent, _experiment())
    with pytest.raises(AuthorizationError, match="invalid checkout transition"):
        lane.revoke(spent)


# ── 11: Failed execution -> FAILED, never retried ───────────────────────────

def test_failed_execution_is_terminal():
    runner = FakeRunner(error=RuntimeError("replay exploded"))
    lane = _lane(runner)
    code = _approved(lane)

    with pytest.raises(AuthorizationError, match="execution failed"):
        lane.exchange(code, _experiment())

    assert lane.status_of(code) == AuthorizationStatus.FAILED
    assert runner.calls == 1

    # Retry is blocked — no re-execution, the code is burned.
    with pytest.raises(AuthorizationError):
        lane.exchange(code, _experiment())
    assert runner.calls == 1


# ── 12: Transition history is append-only with actors ───────────────────────

def test_history_records_transitions():
    lane = _lane()
    code = lane.issue("exp-1", actor="pipeline")
    lane.approve(code.code, reviewer="alice")
    lane.exchange(code.code, _experiment(), actor="runner")

    history = lane.history()

    assert [(e.from_status, e.to_status, e.actor) for e in history] == [
        (None, "issued", "pipeline"),
        ("issued", "approved", "alice"),
        ("approved", "consumed", "runner"),
    ]
    assert all(e.code == code.code for e in history)
    # history() returns a defensive copy — no external mutation.
    history.clear()
    assert len(lane.history()) == 3


# ── 13: Capability Registry + ArtifactType integration ──────────────────────

def test_registry_and_artifact_type():
    cap = get_capability("experiment_checkout")
    assert cap is not None
    assert cap.lifecycle_stage == "validate"
    assert cap.dependencies == ("experimentation",)
    assert "AuthorizationCode" in cap.artifacts

    # Artifact type exists, maps to validate, but is NOT in the linear chain.
    assert ArtifactType.AUTHORIZATION_CODE == "authorization_code"
    assert ArtifactRegistry.stage_for(ArtifactType.AUTHORIZATION_CODE) == "validate"
    assert ArtifactRegistry.expected_parent(ArtifactType.AUTHORIZATION_CODE) is None
    assert ArtifactType.AUTHORIZATION_CODE not in ArtifactRegistry.all_types()


# ── 14: API authorization guard ─────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.learning.experiments.api import router as experiments_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(experiments_router)
    return app


def test_api_run_requires_checkout_code():
    client = TestClient(_make_app())

    resp = client.post("/experiments/run", json=_experiment().to_dict())

    assert resp.status_code == 422  # required `code` query param missing


def test_api_run_blocks_unknown_code(monkeypatch):
    class _FakeLane:
        def __init__(self, runner=None, results_store=None, audit_log=None):
            pass

        def exchange(self, code, experiment, limit=200):
            raise AuthorizationError(f"unknown checkout code '{code}'")

    monkeypatch.setattr("app.learning.experiments.api.CheckoutLane", _FakeLane)
    client = TestClient(_make_app())

    resp = client.post("/experiments/run?code=chk-x", json=_experiment().to_dict())

    assert resp.status_code == 403
    assert "unknown checkout code" in resp.json()["detail"]


def test_api_run_succeeds_with_approved_code(monkeypatch):
    class _FakeLane:
        def __init__(self, runner=None, results_store=None, audit_log=None):
            pass

        def exchange(self, code, experiment, limit=200):
            assert code == "chk-ok"
            assert limit == 50
            return ExperimentResult(
                experiment_id=experiment.id, summary="done", records_processed=5,
            )

    monkeypatch.setattr("app.learning.experiments.api.CheckoutLane", _FakeLane)
    client = TestClient(_make_app())

    resp = client.post(
        "/experiments/run?code=chk-ok&limit=50",
        json=_experiment("exp-1").to_dict(),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "done"
    assert body["experiment_id"] == "exp-1"