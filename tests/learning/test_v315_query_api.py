"""V3.15 Experiment Result Query & Audit API — hermetic tests.

Covers the required cases:
   1.  Store lists results by experiment, newest-first, isolated
   2.  Store list and all() are defensive copies
   3.  Store returns [] for unknown experiments
   4.  AuditLog: newest-first per experiment, defensive all()
   5.  Audit serialization never exposes code/key/value
   6.  Lane mirrors every event into the shared AuditLog
   7.  GET /experiments/{id}/results -> 200 newest-first, secrets redacted
   8.  GET results list for unknown experiment -> 404
   9.  GET /experiments/{id}/audit -> 200 with transitions + execution ids
  10.  GET audit for unknown experiment -> 404
  11.  Audit trail includes blocked denials
  12.  Existing single-result endpoint intact (200 / 404)
  13.  Query API is read-only (no mutation, no replay)
  14.  Newest-first ordering across two real executions

Zero live API / DB / LLM calls.
"""

import json
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.learning.experiments.authorization import (
    AuditLog,
    AuthorizationError,
    AuthorizationEvent,
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


def _result(exp_id, execution_id, finished_at) -> ExperimentResult:
    return ExperimentResult(
        experiment_id=exp_id, execution_id=execution_id, status="completed",
        summary=f"run-{execution_id}", records_processed=1,
        finished_at=finished_at, started_at=finished_at,
        authorization_code="chk-secret-value", authorization_code_id="authz-1",
    )


# ── 1: Store lists results by experiment, newest-first, isolated ────────────

def test_store_lists_results_newest_first():
    store = ExecutionResultStore()
    store.put(_result("exp-1", "exr-1", "2026-01-01T00:00:01+00:00"))
    store.put(_result("exp-1", "exr-2", "2026-01-01T00:00:03+00:00"))
    store.put(_result("exp-1", "exr-3", "2026-01-01T00:00:02+00:00"))
    store.put(_result("exp-2", "exr-9", "2026-01-01T00:00:09+00:00"))

    listed = store.list_by_experiment("exp-1")

    assert [r.execution_id for r in listed] == ["exr-2", "exr-3", "exr-1"]
    assert all(r.experiment_id == "exp-1" for r in listed)
    assert store.count() == 4  # exp-2 result untouched


# ── 2: Defensive copies ─────────────────────────────────────────────────────

def test_store_defensive_copies():
    store = ExecutionResultStore()
    store.put(_result("exp-1", "exr-1", "2026-01-01T00:00:01+00:00"))

    listed = store.list_by_experiment("exp-1")
    listed.clear()

    assert store.list_by_experiment("exp-1")  # unaffected
    assert store.count() == 1
    store.all().clear()
    assert store.count() == 1


# ── 3: Unknown experiments list as empty ────────────────────────────────────

def test_store_unknown_experiment_empty():
    store = ExecutionResultStore()
    assert store.list_by_experiment("exp-nope") == []


# ── 4: AuditLog newest-first per experiment, defensive all() ────────────────

def test_audit_log_listing_and_copies():
    log = AuditLog()
    e1 = AuthorizationEvent(code="c1", from_status=None, to_status="issued",
                            experiment_id="exp-1")
    e2 = AuthorizationEvent(code="c2", from_status=None, to_status="issued",
                            experiment_id="exp-1")
    e3 = AuthorizationEvent(code="c3", from_status=None, to_status="issued",
                            experiment_id="exp-2")
    log.append(e1), log.append(e2), log.append(e3)

    assert log.list_by_experiment("exp-1") == [e2, e1]  # reverse append order
    assert log.list_by_experiment("exp-2") == [e3]
    assert log.list_by_experiment("exp-nope") == []
    assert log.count() == 3
    log.all().clear()
    assert log.count() == 3  # defensive copy


# ── 5: Audit serialization never exposes code/key/value ─────────────────────

def test_audit_serialization_redacts_secrets():
    log = AuditLog()
    log.append(AuthorizationEvent(
        code="chk-topsecret", from_status=None, to_status="issued",
        actor="system", experiment_id="exp-1",
    ))

    body = json.dumps({"events": [e.to_dict() for e in log.all()]})

    assert "chk-topsecret" not in body
    assert '"***"' in body          # redacted placeholder
    assert '"key"' not in body      # never carried
    assert '"value"' not in body    # never carried


# ── 6: Lane mirrors every event into the shared audit log ───────────────────

def test_lane_mirrors_events_to_shared_log():
    log = AuditLog()
    lane = CheckoutLane(runner=FakeRunner(), audit_log=log)
    code = _approved(lane, code="chk-shared")
    result = lane.exchange(code, _experiment())

    # Unauthorized attempt also lands in the shared log.
    denied = lane.issue("exp-1", code="chk-denied")
    with pytest.raises(AuthorizationError):
        lane.exchange(denied.code, _experiment())

    events = log.list_by_experiment("exp-1")
    assert [(e.from_status, e.to_status) for e in events] == [
        ("issued", "blocked"),          # denial, newest first
        (None, "issued"),               # the denied code's issue
        ("approved", "consumed"),       # successful execution
        ("issued", "approved"),
        (None, "issued"),
    ]
    assert events[2].execution_id == result.execution_id
    assert log.count() == len(lane.history())


# ── 7-10: API endpoints ─────────────────────────────────────────────────────

def test_api_list_results_after_real_exchange(monkeypatch):
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=FakeRunner(), results_store=store)
    code = _approved(lane, code="chk-ok")
    executed = lane.exchange(code, _experiment())

    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-1/results")

    assert resp.status_code == 200
    body = resp.json()
    assert body["experiment_id"] == "exp-1"
    assert body["total"] == 1
    assert body["results"][0]["execution_id"] == executed.execution_id
    assert body["results"][0]["status"] == "completed"
    assert "chk-ok" not in json.dumps(body)  # secret redacted


def test_api_list_results_unknown_experiment(monkeypatch):
    store = ExecutionResultStore()
    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-nope/results")

    assert resp.status_code == 404
    assert "no execution results" in resp.json()["detail"]


def test_api_audit_after_real_flow(monkeypatch):
    log = AuditLog()
    lane = CheckoutLane(runner=FakeRunner(), audit_log=log)
    code = _approved(lane, code="chk-ok", reviewer="alice")
    result = lane.exchange(code, _experiment())

    monkeypatch.setattr("app.learning.experiments.api._AUDIT_LOG", log)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-1/audit")

    assert resp.status_code == 200
    body = resp.json()
    assert body["experiment_id"] == "exp-1"
    assert body["total"] == 3
    transitions = [(e["from"], e["to"]) for e in body["events"]]
    assert transitions == [
        ("approved", "consumed"),
        ("issued", "approved"),
        (None, "issued"),
    ]
    assert body["events"][0]["execution_id"] == result.execution_id
    assert body["events"][0]["actor"] == "system"
    assert body["events"][1]["actor"] == "alice"
    assert "chk-ok" not in json.dumps(body)  # code redacted


def test_api_audit_unknown_experiment(monkeypatch):
    log = AuditLog()
    monkeypatch.setattr("app.learning.experiments.api._AUDIT_LOG", log)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-nope/audit")

    assert resp.status_code == 404
    assert "no audit trail" in resp.json()["detail"]


# ── 11: Audit trail includes blocked denials ────────────────────────────────

def test_audit_includes_blocked_denials(monkeypatch):
    log = AuditLog()
    lane = CheckoutLane(runner=FakeRunner(), audit_log=log)
    issued = lane.issue("exp-1", code="chk-denied")
    with pytest.raises(AuthorizationError):
        lane.exchange(issued.code, _experiment())

    monkeypatch.setattr("app.learning.experiments.api._AUDIT_LOG", log)
    client = TestClient(_make_app())

    resp = client.get("/experiments/exp-1/audit")

    assert resp.status_code == 200
    events = resp.json()["events"]
    assert events[0]["to"] == "blocked"          # denial recorded
    assert events[0]["from"] == "issued"
    assert events[0]["experiment_id"] == "exp-1"
    assert len(events) == 2                      # issued + blocked
    assert "chk-denied" not in json.dumps(resp.json())
    # The denial carries no serialized secret.
    assert '"code": "***"' in json.dumps(events)


# ── 12: Existing single-result endpoint intact ──────────────────────────────

def test_single_result_endpoint_intact(monkeypatch):
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=FakeRunner(), results_store=store)
    code = _approved(lane)
    executed = lane.exchange(code, _experiment())

    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    ok = client.get(f"/experiments/exp-1/results/{executed.execution_id}")
    assert ok.status_code == 200
    assert ok.json()["execution_id"] == executed.execution_id

    missing = client.get("/experiments/exp-1/results/exr-missing")
    assert missing.status_code == 404


# ── 13: Query API is read-only ──────────────────────────────────────────────

def test_query_api_is_read_only(monkeypatch):
    store = ExecutionResultStore()
    log = AuditLog()
    lane = CheckoutLane(runner=FakeRunner(), results_store=store, audit_log=log)
    code = _approved(lane)
    lane.exchange(code, _experiment())
    before_results = store.count()
    before_audit = log.count()

    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    monkeypatch.setattr("app.learning.experiments.api._AUDIT_LOG", log)
    client = TestClient(_make_app())

    client.get("/experiments/exp-1/results")
    client.get("/experiments/exp-1/results/missing")
    client.get("/experiments/exp-1/audit")

    assert store.count() == before_results   # no mutation
    assert log.count() == before_audit       # no new events


# ── 14: Newest-first across two real executions ─────────────────────────────

def test_api_results_newest_first_two_executions(monkeypatch):
    store = ExecutionResultStore()
    lane = CheckoutLane(runner=FakeRunner(), results_store=store)
    for code_suffix in ("a", "b"):
        c = _approved(lane, code=f"chk-{code_suffix}")
        lane.exchange(c, _experiment())

    monkeypatch.setattr("app.learning.experiments.api._RESULT_STORE", store)
    client = TestClient(_make_app())

    body = client.get("/experiments/exp-1/results").json()

    assert body["total"] == 2
    keys = [
        (r["finished_at"], r["execution_id"]) for r in body["results"]
    ]
    # Newest-first: keys are non-increasing.
    assert keys[0] >= keys[1]
    # Serials carry no secrets for either execution.
    assert "chk-" not in json.dumps(body)