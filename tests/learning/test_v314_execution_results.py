"""V3.14 Experiment Execution Results & Audit Trail — hermetic tests.

Covers the required cases:
   1.  Completed result artifact fields (execution_id, status, timestamps,
       authorization reference, lineage)
   2.  Secret redaction — raw authorization code / value never serialized
   3.  Failed execution -> immutable failed result, code terminal
   4.  Blocked execution (no approval) -> blocked result, runner untouched
   5.  Authorization binding -> blocked result, code not spent
   6.  Replay / idempotency -> same cached result, single stored entry
   7.  Result store: first-write-wins, immutable, defensive copies
   8.  Audit chain: issued -> approved -> consumed -> result with actors,
       experiment_id, execution_id; append-only
   9.  GET 404 for unknown execution
  10.  GET completed result (redacted) after a real lane exchange
  11.  GET failed result (status + error retrievable)
  12.  GET blocked result retrievable
  13.  No secret anywhere in serialized artifacts
  14.  Results visible across lane instances sharing a store

Zero live API / DB / LLM calls.
"""

import json
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.learning.architecture.artifacts import ArtifactType, Lineage
from app.learning.experiments.authorization import (
    AuthorizationError,
    AuthorizationStatus,
    CheckoutLane,
    ExecutionResultStore,
)
from app.learning.experiments.api import router as experiments_router
from app.learning.experiments.models import ExperimentDefinition, ExperimentResult


# ── Helpers ─────────────────────────────────────────────────────────────────

class FakeRunner:
    """Hermetic stand-in for ReplayRunner.run."""

    def __init__(self, error: Exception | None = None):
        self.calls = 0
        self.error = error

    def __call__(self, experiment, limit=200):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ExperimentResult(
            experiment_id=experiment.id,
            summary=f"ran #{self.calls}",
            records_processed=3,
            baseline_metrics={"count": 3},
        )


def _experiment(exp_id="exp-1") -> ExperimentDefinition:
    return ExperimentDefinition(id=exp_id, name="reranker test", hypothesis="h")


def _approved(lane: CheckoutLane, exp_id="exp-1", code=None, reviewer="alice") -> str:
    c = lane.issue(exp_id, code=code, key="reranker-threshold", value="0.85")
    lane.approve(c.code, reviewer=reviewer)
    return c.code


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(experiments_router)
    return app


# ── 1: Completed result artifact fields ─────────────────────────────────────

def test_completed_result_artifact_fields():
    runner = FakeRunner()
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=runner, results_store=store)
    code = _approved(lane)
    record = lane._get(code)

    result = lane.exchange(code, _experiment())

    assert result.execution_id.startswith("exr-")
    assert store.get("exp-1", result.execution_id) is result
    assert result.status == "completed"
    assert result.started_at and result.finished_at
    assert result.completed_at == result.finished_at
    # Authorization reference: non-secret artifact id + internal raw code.
    assert result.authorization_code_id == record.id
    assert result.authorization_code == code
    # Lineage: result descends from the authorization code.
    assert result.lineage.artifact_id == result.execution_id
    assert result.lineage.parent_artifact_id == record.id
    assert result.lineage.parent_type == ArtifactType.AUTHORIZATION_CODE


# ── 2: Secret redaction ─────────────────────────────────────────────────────

def test_secrets_redacted_in_serialization():
    runner = FakeRunner()
    lane = CheckoutLane(runner=runner)
    code = _approved(lane, code="chk-topsecret")

    result = lane.exchange(code, _experiment())

    body = json.dumps(result.to_dict())
    assert "chk-topsecret" not in body       # raw code never serialized
    assert "0.85" not in body                # code value never serialized
    assert result.authorization_code_id      # non-secret ref IS present


# ── 3: Failed execution -> immutable failed result, code terminal ───────────

def test_failed_execution_records_failed_result():
    runner = FakeRunner(error=RuntimeError("replay exploded"))
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=runner, results_store=store)
    code = _approved(lane, code="chk-fail")

    with pytest.raises(AuthorizationError, match="execution failed"):
        lane.exchange(code, _experiment())

    # The failed result was recorded and is inspectable.
    results = store.all()
    assert len(results) == 1
    failed = results[0]
    assert failed.status == "failed"
    # Capped stable diagnostic: exception TYPE, never raw exception text
    # (V4 review: artifact errors must not leak internal exception details).
    assert "replay exploded" not in failed.error
    assert failed.error.startswith("experiment execution failed: RuntimeError")
    assert failed.authorization_code_id == lane._get(code).id
    assert lane.status_of(code) == AuthorizationStatus.FAILED
    # Terminal: retry is blocked, no re-execution. The denial is recorded.
    with pytest.raises(AuthorizationError):
        lane.exchange(code, _experiment())
    assert runner.calls == 1
    assert store.count() == 2
    assert store.all()[-1].status == "blocked"


# ── 4: Blocked execution (no approval) -> blocked result ────────────────────

def test_blocked_execution_records_blocked_result():
    runner = FakeRunner()
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=runner, results_store=store)
    code = lane.issue("exp-1")

    with pytest.raises(AuthorizationError, match="not approved"):
        lane.exchange(code.code, _experiment())

    assert runner.calls == 0  # never executed
    blocked = store.all()[0]
    assert blocked.status == "blocked"
    assert "not approved" in blocked.error
    assert blocked.execution_id.startswith("exr-")
    assert lane.status_of(code.code) == AuthorizationStatus.ISSUED


# ── 5: Authorization binding -> blocked result, code not spent ──────────────

def test_binding_mismatch_records_blocked_result():
    runner = FakeRunner()
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=runner, results_store=store)
    code = _approved(lane, exp_id="exp-1")

    with pytest.raises(AuthorizationError, match="bound to experiment 'exp-1'"):
        lane.exchange(code, _experiment("exp-2"))

    assert runner.calls == 0
    blocked = store.all()[0]
    assert blocked.status == "blocked"
    assert blocked.experiment_id == "exp-2"
    assert lane.status_of(code) == AuthorizationStatus.APPROVED  # not spent


# ── 6: Replay / idempotency ─────────────────────────────────────────────────

def test_replay_returns_same_result_single_store_entry():
    runner = FakeRunner()
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=runner, results_store=store)
    code = _approved(lane)

    first = lane.exchange(code, _experiment())
    second = lane.exchange(code, _experiment())

    assert second is first
    assert runner.calls == 1
    assert store.count() == 1
    assert store.get("exp-1", first.execution_id) is first


# ── 7: Result store: first-write-wins, immutable, defensive ─────────────────

def test_result_store_semantics():
    store = ExecutionResultStore()
    r1 = ExperimentResult(experiment_id="exp-1", execution_id="exr-7",
                          status="completed", summary="one")
    r2 = ExperimentResult(experiment_id="exp-1", execution_id="exr-7",
                          status="failed", summary="two")

    assert store.put(r1) is r1
    assert store.put(r2) is r1  # first write wins
    assert store.count() == 1
    assert store.get("exp-1", "exr-7") is r1
    assert store.get("exp-1", "exr-missing") is None
    all_results = store.all()
    all_results.clear()
    assert store.count() == 1  # defensive copy


# ── 8: Audit chain ──────────────────────────────────────────────────────────

def test_audit_chain_with_execution_context():
    runner = FakeRunner()
    lane = CheckoutLane(runner=runner)
    code = _approved(lane, code="chk-audit")
    result = lane.exchange(code, _experiment())

    events = lane.history()

    assert [(e.from_status, e.to_status, e.actor) for e in events] == [
        (None, "issued", "system"),
        ("issued", "approved", "alice"),
        ("approved", "consumed", "system"),
    ]
    assert all(e.code == "chk-audit" for e in events)
    assert all(e.experiment_id == "exp-1" for e in events)
    assert events[2].execution_id == result.execution_id  # result linked
    # Append-only: external mutation cannot touch history.
    events.clear()
    assert len(lane.history()) == 3


# ── 9-12: GET results endpoint ──────────────────────────────────────────────

def _stored(store, exp_id="exp-1", execution_id="exr-9", status="completed",
            error=""):
    r = ExperimentResult(
        experiment_id=exp_id, execution_id=execution_id, status=status,
        summary="done", records_processed=4, error=error,
        authorization_code="chk-secret-value", authorization_code_id="authz-1",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        lineage=Lineage(artifact_id=execution_id, parent_artifact_id="authz-1",
                        parent_type=ArtifactType.AUTHORIZATION_CODE),
    )
    store.put(r)
    return r


def test_get_result_unknown_execution(monkeypatch):
    store = ExecutionResultStore()
    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-1/results/exr-nope")

    assert resp.status_code == 404


def test_get_completed_result_after_real_exchange(monkeypatch):
    runner = FakeRunner()
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=runner, results_store=store)
    code = _approved(lane, code="chk-ok")
    executed = lane.exchange(code, _experiment())

    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    resp = client.get(f"/experiments/exp-1/results/{executed.execution_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["execution_id"] == executed.execution_id
    assert body["experiment_id"] == "exp-1"
    assert "chk-ok" not in json.dumps(body)          # secret redacted
    assert body["authorization_code_id"] == executed.authorization_code_id


def test_get_failed_result(monkeypatch):
    store = ExecutionResultStore()
    _stored(store, execution_id="exr-f", status="failed", error="boom")
    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-1/results/exr-f")

    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["error"] == "boom"


def test_get_blocked_result(monkeypatch):
    store = ExecutionResultStore()
    _stored(store, execution_id="exr-b", status="blocked", error="not approved")
    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-1/results/exr-b")

    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


# ── 13: No secret anywhere in serialized artifacts ──────────────────────────

def test_no_secret_in_any_serialized_artifact():
    runner = FakeRunner()
    lane = CheckoutLane(runner=runner)
    code = _approved(lane, code="chk-s3cr3t", reviewer="alice")

    result = lane.exchange(code, _experiment())
    allowed = lane.history()
    denied_lane = CheckoutLane(runner=runner)
    denied = denied_lane.issue("exp-1", code="chk-denied")
    denied_lane.approve(denied.code, reviewer="bob")
    denied_lane.revoke(denied.code, actor="bob")

    serialized = json.dumps({
        "result": result.to_dict(),
        "events": [e.to_dict() for e in allowed],
    })
    assert "chk-s3cr3t" not in serialized
    assert "0.85" not in serialized
    # Denied path artifacts equally leak nothing.
    assert "chk-denied" not in json.dumps([e.to_dict() for e in denied_lane.history()])


# ── 14: Results visible across lane instances sharing a store ───────────────

def test_results_shared_across_lanes():
    store = ExecutionResultStore()
    lane_a = CheckoutLane(runner=FakeRunner(), results_store=store)
    code = _approved(lane_a)
    result = lane_a.exchange(code, _experiment())

    lane_b = CheckoutLane(runner=FakeRunner(), results_store=store)  # fresh lane

    assert lane_b._results_store.get("exp-1", result.execution_id) is result
    assert lane_b._results_store.count() == 1
    assert result in lane_b._results_store.all()