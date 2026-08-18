"""V2.2 P2.1 extraction observability tests — hermetic, sqlite, no network.

Covers: JSON logging structure, LOG_LEVEL, extraction_run_id generation +
propagation + MemoryEvent metadata linkage, metric increments (scheduled /
skipped / failed / completed / duration / inflight / queue), bounded label
policy (no user/session/run ids as labels), gate reason taxonomy, token
capture (present / absent / Ollama-style), exception sanitization, and
fail-open (broken metrics/logging never break extraction).

No real OpenAI/Redis calls — fake providers, FakeRedis, sqlite.
"""

from __future__ import annotations

import json
import logging
import threading
import time

import pytest
from prometheus_client import CollectorRegistry
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core import metrics as core_metrics
from app.core.logging_config import (
    JsonFormatter,
    classify_exception,
    sanitize_exception_message,
    setup_logging,
)
from app.learning.extraction import extractor as ex
from app.learning.extraction import observability
from app.learning.extraction.coordinator import ExecutionCoordinator
from app.learning.extraction.executor import BoundedDaemonExecutor
from app.models.memory import MemoryEntity, MemoryEvent
from app.services import auth

# Every table referenced by the ownership chain + extraction input.
from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401

_FORBIDDEN_LABELS = {
    "user_id", "user_hash", "session_id", "session", "conversation_id",
    "message_id", "turn", "request_id", "run_id", "extraction_run_id",
    "memory_id", "entity", "error", "error_message",
}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Minimal Redis double for claim keys (set nx/ex, get, delete)."""

    def __init__(self):
        self._data: dict[str, object] = {}
        self.broken = False

    def _check(self):
        if self.broken:
            raise ConnectionError("redis down")

    def set(self, name: str, value: object, ex=None, nx=False) -> bool:
        self._check()
        if nx and name in self._data:
            return False
        self._data[name] = value
        return True

    def get(self, name: str):
        self._check()
        return self._data.get(name)

    def delete(self, *names) -> int:
        self._check()
        removed = 0
        for name in names:
            if self._data.pop(name, None) is not None:
                removed += 1
        return removed

    def register_script(self, script):
        raise AssertionError("throttle script should not run in these tests")


class _StubExecutor:
    def __init__(self):
        self.submitted: list[tuple] = []

    def submit(self, fn, *args) -> bool:
        self.submitted.append((fn, args))
        return True

    def shutdown(self) -> None:
        pass


class _FakeReply:
    def __init__(self, content: str, metadata: dict | None = None):
        self.content = content
        self.response_metadata = metadata or {}


class _FakeModel:
    def __init__(self, reply):
        self._reply = reply

    def invoke(self, payload):
        return self._reply


def _wait_until(cond, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _conv(db, user, session_id: str, rows: list[tuple[str, str, str]]):
    """Create a conversation with (role, content, status) rows in sequence."""
    from app.models.chat import ChatMessage
    from app.services import chat_persistence as store

    conv = store.create_conversation(db, user, session_id, title="T")
    msgs = []
    for i, (role, content, status) in enumerate(rows, start=1):
        m = ChatMessage(session_id=conv.id, role=role, content=content, status=status, sequence=i)
        db.add(m)
        msgs.append(m)
    db.commit()
    return msgs


def _full_run_fixture(engine, user, monkeypatch, session_id="sess-ob", rows=None):
    """Wire SyncSessionLocal + fake embeddings + fake LLM + a fresh in-process
    coordinator (no Redis) for run_extraction. The fresh coordinator keeps the
    single-flight/throttle state hermetic per test — the process-wide singleton
    would leak throttle markers across tests."""
    from sqlalchemy.orm import Session as SA_Session

    S = sessionmaker(bind=engine, class_=SA_Session, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, session_id, rows or [
            ("user", "I prefer kotlin for side projects", "completed"),
            ("assistant", "Good to know!", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))

    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.embeddings.build_embedding_provider",
        lambda: SimpleNamespace(embed=lambda texts: [[0.0] * 1536 for _ in texts]),
    )

    def fake_llm(exchange, run_id=None):
        return [{"statement": "durable fact", "domain": "semantic", "importance": 0.5}]

    monkeypatch.setattr(ex, "_extract_with_llm", fake_llm)
    return msgs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
def user(db):
    return auth.create_user(db, "alice", "password123")


@pytest.fixture
def mreg(monkeypatch):
    """Fresh metrics registry wired into every instrumentation consumer.
    safe_count/safe_observe/... in app.core.metrics close over the module
    global `metrics`, so rebinding it covers all call sites."""
    fresh = core_metrics.ExtractionMetrics(CollectorRegistry())
    monkeypatch.setattr(core_metrics, "metrics", fresh)
    return fresh


@pytest.fixture
def json_logs():
    """Capture JSON-formatted records from the extraction loggers."""
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.setFormatter(JsonFormatter())

    def _emit(record):
        records.append(record)

    handler.emit = _emit
    targets = [
        logging.getLogger("app.extraction"),
        logging.getLogger("app.memory"),
        logging.getLogger("app.services.memory"),
    ]
    for lg in targets:
        lg.addHandler(handler)
        lg.setLevel(logging.DEBUG)
    yield records
    for lg in targets:
        lg.removeHandler(handler)
        lg.setLevel(logging.NOTSET)


def _formatted(records, index=-1) -> dict:
    handler = logging.Handler()
    handler.setFormatter(JsonFormatter())
    return json.loads(handler.format(records[index]))


def _counter(metric, labels=None):
    child = metric.labels(**labels) if labels else metric
    return child._value.get()


def _hist_sum(hist):
    return hist._sum.get()


def _hist_count(hist):
    # prometheus-client >= 0.26: _buckets is a list of per-bucket value
    # objects (non-cumulative); the histogram count is their sum.
    return sum(b.get() for b in hist._buckets)


# ---------------------------------------------------------------------------
# 1. Structured JSON logging + LOG_LEVEL
# ---------------------------------------------------------------------------

def test_json_logger_emits_structured_fields(json_logs):
    observability.log_event(
        logging.INFO, "memory_extraction_scheduled",
        session="s1", turn=7, run_id="RUN-1",
    )
    payload = _formatted(json_logs)
    assert payload["event"] == "memory_extraction_scheduled"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.extraction"
    assert payload["session"] == "s1"
    assert payload["turn"] == 7
    assert payload["run_id"] == "RUN-1"
    assert "ts" in payload
    assert "message" in payload


def test_json_logger_drops_non_whitelisted_fields(json_logs):
    observability.log_event(
        logging.INFO, "memory_extraction_started",
        session="s1", user_id="u-secret", prompt="SHOULD NOT APPEAR", run_id="RUN-1",
    )
    payload = _formatted(json_logs)
    assert payload["session"] == "s1"
    assert "user_id" not in payload
    assert "prompt" not in payload
    assert "SHOULD NOT APPEAR" not in json.dumps(payload)


def test_json_formatter_sanitizes_exc_info():
    formatter = JsonFormatter()
    logger = logging.getLogger("app.extraction")
    record = logger.makeRecord(
        logger.name, logging.ERROR, __file__, 1,
        "memory_extraction_failed", None, None,
    )
    try:
        raise RuntimeError("boom sk-1234567890abcdefghij")
    except RuntimeError:
        logger.exception = None  # noqa: B010
        record.exc_info = __import__("sys").exc_info()
    payload = json.loads(formatter.format(record))
    assert payload["error_class"] == "RuntimeError"
    assert "sk-[REDACTED]" in payload["error_message"]
    assert "sk-1234567890abcdefghij" not in payload["error_message"]


def test_setup_logging_respects_level():
    root = setup_logging("DEBUG")
    assert root.level == logging.DEBUG
    root = setup_logging("WARNING")
    assert root.level == logging.WARNING
    root = setup_logging("not-a-level")
    assert root.level == logging.INFO
    setup_logging("INFO")


def test_log_level_setting_default():
    from app.core.config import settings

    assert settings.LOG_LEVEL == "INFO"


# ---------------------------------------------------------------------------
# 3. extraction_run_id
# ---------------------------------------------------------------------------

def test_new_run_id_is_uuid4_unique():
    a = observability.new_run_id()
    b = observability.new_run_id()
    assert a != b
    assert len(a) == 36


def test_user_hash_is_short_and_stable():
    h1 = observability.user_hash("user-1")
    h2 = observability.user_hash("user-1")
    assert h1 == h2
    assert len(h1) == 8
    assert observability.user_hash("user-1") != observability.user_hash("user-2")


def test_schedule_generates_and_propagates_run_id(mreg, monkeypatch):
    fake = _FakeRedis()
    coord = ExecutionCoordinator(client=fake)
    monkeypatch.setattr(ex, "coordinator", coord)
    stub = _StubExecutor()
    monkeypatch.setattr(ex, "extraction_executor", stub)

    assert ex.schedule_extraction("s1", "u1", None, 7) is True

    assert len(stub.submitted) == 1
    _fn, args = stub.submitted[0]
    run_id = args[4]
    assert run_id == observability.new_run_id().__class__(run_id)  # str check below
    assert isinstance(run_id, str) and len(run_id) == 36
    # claim value embeds the run id (coordination correlation)
    claim_value = fake.get(f"memory:extraction:sf:s1:7")
    assert isinstance(claim_value, str) and run_id in claim_value
    assert _counter(mreg.scheduled_total) == 1
    assert _counter(mreg.redis_claim_success_total) == 1


def test_run_id_in_memoryevent_metadata(engine, user, monkeypatch):
    msgs = _full_run_fixture(engine, user, monkeypatch)

    written = ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="RUN-TEST-1")
    assert written == 1

    from sqlalchemy.orm import Session as SA_Session

    S = sessionmaker(bind=engine, class_=SA_Session, expire_on_commit=False)
    with S() as db:
        entities = list(db.execute(select(MemoryEntity)).scalars())
        assert len(entities) == 1
        assert entities[0].metadata_.get("extraction_run_id") == "RUN-TEST-1"
        events = list(db.execute(select(MemoryEvent)).scalars())
        assert len(events) == 1
        assert events[0].metadata_.get("extraction_run_id") == "RUN-TEST-1"


def test_run_generates_run_id_when_absent(engine, user, monkeypatch, json_logs):
    msgs = _full_run_fixture(engine, user, monkeypatch)
    assert ex.run_extraction("sess-ob", user.id, None, msgs[0].id) == 1
    payload = _formatted(json_logs, -1)
    assert payload["event"] == "memory_extraction_completed"
    assert payload["run_id"] and len(payload["run_id"]) == 36


# ---------------------------------------------------------------------------
# 4. Metric increments
# ---------------------------------------------------------------------------

def test_skipped_metric_claim_conflict(mreg, monkeypatch):
    coord = ExecutionCoordinator(redis_url=None)
    monkeypatch.setattr(ex, "coordinator", coord)
    monkeypatch.setattr(ex, "extraction_executor", _StubExecutor())

    assert ex.schedule_extraction("s1", "u1", None, 7) is True
    assert ex.schedule_extraction("s1", "u1", None, 7) is False

    assert _counter(mreg.skipped_total, {"reason": "CLAIM_CONFLICT"}) == 1
    assert _counter(mreg.scheduled_total) == 1
    assert _counter(mreg.redis_claim_conflict_total) == 1


def test_skipped_metric_queue_full(mreg, monkeypatch):
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))

    class FullExecutor:
        def submit(self, fn, *args) -> bool:
            return False

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(ex, "extraction_executor", FullExecutor())
    assert ex.schedule_extraction("s1", "u1", None, 7) is False
    assert _counter(mreg.skipped_total, {"reason": "QUEUE_FULL"}) == 1


def test_release_turn_redis_failure_carries_run_id(mreg, json_logs, monkeypatch):
    """Y4: a Redis failure at claim-release time is correlated with the run_id
    that was threaded through release_turn; omitting run_id stays backward
    compatible (event without run_id)."""
    fake = _FakeRedis()
    fake.broken = True
    coord = ExecutionCoordinator(client=fake)
    monkeypatch.setattr(ex, "coordinator", coord)

    coord.release_turn("sess-rel", 7, run_id="RUN-Y4")
    payload = _formatted(json_logs, -1)
    assert payload["event"] == "memory_extraction_redis_unavailable"
    assert payload["op"] == "release"
    assert payload["run_id"] == "RUN-Y4"
    assert _counter(mreg.redis_fallback_total, {"operation": "release"}) == 1

    coord.release_turn("sess-rel", 8)
    payload = _formatted(json_logs, -1)
    assert payload["op"] == "release"
    assert "run_id" not in payload
    assert _counter(mreg.redis_fallback_total, {"operation": "release"}) == 2


def test_failed_metric_db_error(mreg, engine, user, monkeypatch):
    import sqlalchemy.exc

    msgs = _full_run_fixture(engine, user, monkeypatch)

    class BrokenDB:
        def __enter__(self):
            raise sqlalchemy.exc.OperationalError("stmt", {}, Exception("db down"))

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("app.core.database.SyncSessionLocal", BrokenDB)
    assert ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="R") == 0
    assert _counter(mreg.failed_total, {"reason": "DB_ERROR"}) == 1
    assert _counter(mreg.started_total) == 1


def test_completed_metric_and_created_counter(mreg, engine, user, monkeypatch):
    msgs = _full_run_fixture(engine, user, monkeypatch)
    assert ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="R") == 1
    assert _counter(mreg.completed_total) == 1
    assert _counter(mreg.started_total) == 1
    assert _counter(mreg.memory_created_total, {"status": "pending"}) == 1


def test_duration_histogram_recorded(mreg, engine, user, monkeypatch):
    msgs = _full_run_fixture(engine, user, monkeypatch)
    ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="R")
    assert _hist_count(mreg.duration_seconds) == 1
    assert _hist_sum(mreg.duration_seconds) > 0


def test_inflight_gauge_through_real_production_nesting(mreg, engine, user, monkeypatch):
    """R1 regression: the real production nesting
    schedule_extraction -> executor -> _run_task -> run_extraction must
    show inflight == 1 for ONE running extraction. The executor is the sole
    owner of the inflight gauge; run_extraction never touches it (before the
    fix both layers incremented the same gauge -> 2.0)."""
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-nest", [
            ("user", "I prefer kotlin for side projects", "completed"),
            ("assistant", "Good to know!", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.embeddings.build_embedding_provider",
        lambda: SimpleNamespace(embed=lambda texts: [[0.0] * 1536 for _ in texts]),
    )

    llm_started = threading.Event()
    release = threading.Event()

    def blocking_llm(exchange, run_id=None):
        llm_started.set()
        release.wait(5)
        return [{"statement": "durable fact", "domain": "semantic", "importance": 0.5}]

    monkeypatch.setattr(ex, "_extract_with_llm", blocking_llm)

    pool = BoundedDaemonExecutor(max_workers=1, max_queue=4)
    monkeypatch.setattr(ex, "extraction_executor", pool)
    try:
        assert ex.schedule_extraction("sess-nest", user.id, None, msgs[0].id) is True
        assert llm_started.wait(5)
        assert mreg.inflight._value.get() == 1.0
        assert mreg.queue_depth._value.get() == 0.0
        release.set()
        assert _wait_until(lambda: mreg.inflight._value.get() == 0.0)
        assert mreg.queue_depth._value.get() == 0.0
        assert _counter(mreg.completed_total) == 1
        assert _counter(mreg.scheduled_total) == 1
    finally:
        release.set()
        pool.shutdown()


def test_queue_depth_and_capacity_gauges(mreg):
    pool = BoundedDaemonExecutor(max_workers=1, max_queue=4)
    release = threading.Event()

    def block():
        release.wait(5)

    try:
        assert pool.submit(block) is True
        assert pool.submit(block) is True
        assert _wait_until(lambda: mreg.queue_depth._value.get() == 1.0)
        assert mreg.queue_capacity._value.get() == 4.0
        assert mreg.inflight._value.get() == 1.0
    finally:
        release.set()
        pool.shutdown()
    assert mreg.queue_depth._value.get() == 0.0


# ---------------------------------------------------------------------------
# 6. Label / cardinality policy
# ---------------------------------------------------------------------------

def test_bounded_labels_validate():
    m = core_metrics.ExtractionMetrics(CollectorRegistry())
    assert m.validate("reason", "THROTTLED") == "THROTTLED"
    assert m.validate("gate", "3") == "3"
    assert m.validate("operation", "claim") == "claim"
    assert m.validate("kind", "input") == "input"
    assert m.validate("status", "pending") == "pending"
    assert m.validate("provider", "ollama") == "ollama"
    with pytest.raises(ValueError):
        m.validate("reason", "USER_SPECIFIC_REASON")
    with pytest.raises(ValueError):
        m.validate("gate", "42")
    with pytest.raises(ValueError):
        m.validate("operation", "explode")
    with pytest.raises(ValueError):
        m.validate("kind", "tokens")
    with pytest.raises(ValueError):
        m.validate("status", "archived")
    with pytest.raises(ValueError):
        m.validate("provider", "claude")
    assert m.validate("model", "weird-free-model") == "other"


def test_no_forbidden_ids_in_metric_labels():
    fresh = core_metrics.ExtractionMetrics(CollectorRegistry())
    seen: set[str] = set()
    for group in (fresh._counters, fresh._histograms, fresh._gauges):
        for metric in group.values():
            seen.update(getattr(metric, "_labelnames", ()))
    assert not (seen & _FORBIDDEN_LABELS)
    assert seen <= {"reason", "gate", "operation", "kind", "provider", "model", "status", "enabled"}


def test_metrics_render_has_no_content(engine, user, monkeypatch):
    msgs = _full_run_fixture(engine, user, monkeypatch)
    ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="R")
    body = core_metrics.render_metrics().decode()
    assert "owngpt_memory_extraction_scheduled_total" in body
    assert "owngpt_memory_extraction_duration_seconds" in body
    assert "durable fact" not in body
    assert "sess-ob" not in body


# ---------------------------------------------------------------------------
# 7. Gate reason taxonomy
# ---------------------------------------------------------------------------

def test_gate1_ineligible_reason(mreg, engine, user, monkeypatch):
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-g1", [
            ("user", "thanks!", "completed"),
            ("assistant", "You're welcome", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))

    assert ex.run_extraction("sess-g1", user.id, None, msgs[0].id, run_id="R") == 0
    assert _counter(mreg.skipped_total, {"reason": "INELIGIBLE"}) == 1
    assert _counter(mreg.gate_rejections_total, {"gate": "1", "reason": "INELIGIBLE"}) == 1


def test_gate1b_throttled_reason(mreg, engine, user, monkeypatch):
    coord = ExecutionCoordinator(redis_url=None, interval=3)
    monkeypatch.setattr(ex, "coordinator", coord)
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-g1b", [
            ("user", "I like python", "completed"),
            ("assistant", "ok", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "_extract_with_llm", lambda exchange, run_id=None: [])

    assert coord.throttle_allowed("sess-g1b", 1)  # mark the previous turn
    assert ex.run_extraction("sess-g1b", user.id, None, msgs[0].id, run_id="R") == 0
    assert _counter(mreg.skipped_total, {"reason": "THROTTLED"}) == 1
    assert _counter(mreg.gate_rejections_total, {"gate": "1b", "reason": "THROTTLED"}) == 1


def test_gate3_invalid_candidate_reason(mreg, engine, user, monkeypatch):
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-g3", [
            ("user", "I use kotlin", "completed"),
            ("assistant", "ok", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))
    monkeypatch.setattr(
        ex, "_extract_with_llm",
        lambda exchange, run_id=None: [{"statement": "x" * 600, "domain": "semantic", "importance": 0.5}],
    )
    assert ex.run_extraction("sess-g3", user.id, None, msgs[0].id, run_id="R") == 0
    assert _counter(mreg.skipped_total, {"reason": "INVALID_CANDIDATE"}) == 1
    assert _counter(mreg.gate_rejections_total, {"gate": "3", "reason": "INVALID_CANDIDATE"}) == 1


def test_gate3_secret_detected_reason(mreg, engine, user, monkeypatch):
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-secret", [
            ("user", "I use kotlin", "completed"),
            ("assistant", "ok", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))
    monkeypatch.setattr(
        ex, "_extract_with_llm",
        lambda exchange, run_id=None: [
            {"statement": "the api key is sk-1234567890abcdefghij", "domain": "semantic", "importance": 0.5}
        ],
    )
    assert ex.run_extraction("sess-secret", user.id, None, msgs[0].id, run_id="R") == 0
    assert _counter(mreg.skipped_total, {"reason": "SECRET_DETECTED"}) == 1
    assert _counter(mreg.gate_rejections_total, {"gate": "3", "reason": "SECRET_DETECTED"}) == 1


def test_secret_detected_emits_exactly_one_terminal_event(mreg, engine, user, monkeypatch, json_logs):
    """Y2: one terminal skip event per attempt — the SECRET_DETECTED decision
    is made in _validate_candidates but the single event/metric is emitted by
    the caller, never twice."""
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-secret1", [
            ("user", "I use kotlin", "completed"),
            ("assistant", "ok", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))
    monkeypatch.setattr(
        ex, "_extract_with_llm",
        lambda exchange, run_id=None: [
            {"statement": "the api key is sk-1234567890abcdefghij", "domain": "semantic", "importance": 0.5}
        ],
    )
    assert ex.run_extraction("sess-secret1", user.id, None, msgs[0].id, run_id="R") == 0
    payloads = [_formatted(json_logs, i) for i in range(len(json_logs))]
    skips = [p for p in payloads if p.get("event") == "memory_extraction_skipped"]
    assert len(skips) == 1
    assert skips[0]["reason"] == "SECRET_DETECTED"
    assert skips[0]["gate"] == "3"
    assert _counter(mreg.skipped_total, {"reason": "SECRET_DETECTED"}) == 1
    assert _counter(mreg.gate_rejections_total, {"gate": "3", "reason": "SECRET_DETECTED"}) == 1


def test_llm_error_is_failure_not_skip(mreg, monkeypatch):
    monkeypatch.setattr(
        "app.core.llm_provider.build_llm",
        lambda **kw: _FakeModel(_FakeReply("not json at all")),
    )
    assert ex._extract_with_llm("exchange", run_id="R") is None
    assert _counter(mreg.llm_calls_total, {"provider": "openai", "model": "gpt-4o-mini"}) == 2
    assert _counter(mreg.llm_errors_total, {"provider": "openai", "model": "gpt-4o-mini"}) == 2


# ---------------------------------------------------------------------------
# 8. Token observability
# ---------------------------------------------------------------------------

def test_token_metadata_present(mreg, monkeypatch):
    monkeypatch.setattr(
        "app.core.llm_provider.build_llm",
        lambda **kw: _FakeModel(_FakeReply(
            '{"candidates": []}',
            {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        )),
    )
    assert ex._extract_with_llm("exchange", run_id="R") == []
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "input"}) == 10
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "output"}) == 5
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "total"}) == 15


def test_token_metadata_absent_is_graceful(mreg, monkeypatch):
    monkeypatch.setattr(
        "app.core.llm_provider.build_llm",
        lambda **kw: _FakeModel(_FakeReply('{"candidates": []}')),
    )
    assert ex._extract_with_llm("exchange", run_id="R") == []
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "input"}) == 0
    assert _counter(mreg.llm_calls_total, {"provider": "openai", "model": "gpt-4o-mini"}) == 1


def test_ollama_style_token_fields(mreg, monkeypatch):
    monkeypatch.setattr(
        "app.core.llm_provider.build_llm",
        lambda **kw: _FakeModel(_FakeReply(
            '{"candidates": []}',
            {"usage": {"prompt_eval_count": 100, "eval_count": 20}},
        )),
    )
    assert ex._extract_with_llm("exchange", run_id="R") == []
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "input"}) == 100
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "output"}) == 20
    assert _counter(mreg.llm_tokens_total, {"provider": "openai", "model": "gpt-4o-mini", "kind": "total"}) == 0


def test_llm_duration_histogram(mreg, monkeypatch):
    monkeypatch.setattr(
        "app.core.llm_provider.build_llm",
        lambda **kw: _FakeModel(_FakeReply('{"candidates": []}')),
    )
    ex._extract_with_llm("exchange", run_id="R")
    hist = mreg.llm_duration_seconds.labels(provider="openai", model="gpt-4o-mini")
    assert _hist_count(hist) == 1
    assert hist._sum.get() >= 0


# ---------------------------------------------------------------------------
# 9. Sanitization / classification
# ---------------------------------------------------------------------------

def test_sanitize_exception_message():
    assert sanitize_exception_message("key sk-1234567890abcdefghij leaked") == "key sk-[REDACTED] leaked"
    assert "AKIA1234567890ABCDEF" not in sanitize_exception_message("ak AKIA1234567890ABCDEF")
    assert "Bearer abcdefghijklmnopqrstuvwxyz" not in sanitize_exception_message("h Bearer abcdefghijklmnopqrstuvwxyz")
    assert sanitize_exception_message("plain error") == "plain error"
    assert len(sanitize_exception_message("x" * 5000)) == 500


def test_classify_exception_taxonomy():
    import sqlalchemy.exc

    assert classify_exception(sqlalchemy.exc.OperationalError("s", {}, Exception("db"))) == "DB_ERROR"
    assert classify_exception(ConnectionError("provider down")) == "PROVIDER_UNAVAILABLE"

    class FakeOpenAIError(Exception):
        pass

    FakeOpenAIError.__module__ = "openai.api_error"
    assert classify_exception(FakeOpenAIError("quota")) == "PROVIDER_UNAVAILABLE"
    assert classify_exception(RuntimeError("boom")) == "UNKNOWN_ERROR"


def test_reason_taxonomy_expected_set():
    assert {
        "DISABLED", "CLAIM_CONFLICT", "QUEUE_FULL", "CONVERSATION_MISSING",
        "NO_TURN", "INELIGIBLE", "THROTTLED", "NO_CANDIDATES",
        "INVALID_CANDIDATE", "SECRET_DETECTED", "LLM_ERROR", "DB_ERROR",
        "PROVIDER_UNAVAILABLE", "WORKER_ERROR", "UNKNOWN_ERROR",
    } <= core_metrics.REASONS


# ---------------------------------------------------------------------------
# 10. Failure isolation
# ---------------------------------------------------------------------------

def test_broken_metrics_never_fail_extraction(engine, user, monkeypatch):
    msgs = _full_run_fixture(engine, user, monkeypatch)

    class BrokenMetrics:
        def count(self, *a, **k):
            raise RuntimeError("metrics exploded")

        def observe(self, *a, **k):
            raise RuntimeError("metrics exploded")

        def set(self, *a, **k):
            raise RuntimeError("metrics exploded")

        def gauge_inc(self, *a, **k):
            raise RuntimeError("metrics exploded")

        def gauge_dec(self, *a, **k):
            raise RuntimeError("metrics exploded")

    import app.core.metrics as core_metrics_mod

    monkeypatch.setattr(core_metrics_mod, "metrics", BrokenMetrics())

    assert ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="R") == 1
    assert ex.schedule_extraction("sess-ob", user.id, None, msgs[0].id) in (True, False)


def test_broken_logging_never_fails_extraction(engine, user, monkeypatch):
    msgs = _full_run_fixture(engine, user, monkeypatch)

    class ExplodingHandler(logging.Handler):
        def emit(self, record):
            raise RuntimeError("log exploded")

    handler = ExplodingHandler()
    lg = logging.getLogger("app.extraction")
    lg.addHandler(handler)
    try:
        assert ex.run_extraction("sess-ob", user.id, None, msgs[0].id, run_id="R") == 1
    finally:
        lg.removeHandler(handler)


def test_logs_never_contain_conversation_content(engine, user, monkeypatch, json_logs):
    marker = "SENSITIVECONTENTMARKER42"
    S = _full_run_fixture.__globals__["sessionmaker"](bind=engine, expire_on_commit=False)
    with S() as db:
        msgs = _conv(db, user, "sess-content", [
            ("user", marker, "completed"),
            ("assistant", "Good to know!", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.embeddings.build_embedding_provider",
        lambda: SimpleNamespace(embed=lambda texts: [[0.0] * 1536 for _ in texts]),
    )
    monkeypatch.setattr(
        ex, "_extract_with_llm",
        lambda exchange, run_id=None: [{"statement": marker, "domain": "semantic", "importance": 0.5}],
    )
    assert ex.run_extraction("sess-content", user.id, None, msgs[0].id, run_id="R") == 1
    joined = " ".join(json.dumps(_formatted(json_logs, i)) for i in range(len(json_logs)))
    assert marker not in joined
    assert "password123" not in joined


# ---------------------------------------------------------------------------
# 8. V2.2 P2.2: extraction_info gauge, executor shutdown, HTTP traffic counter
# ---------------------------------------------------------------------------

def test_extraction_info_gauge_reflects_config_enabled(mreg, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", True)
    core_metrics.record_extraction_enabled()
    assert mreg.extraction_info.labels(enabled="1")._value.get() == 1.0
    assert mreg.extraction_info.labels(enabled="0")._value.get() == 0.0


def test_extraction_info_gauge_reflects_config_disabled(mreg, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", False)
    core_metrics.record_extraction_enabled()
    assert mreg.extraction_info.labels(enabled="0")._value.get() == 1.0
    assert mreg.extraction_info.labels(enabled="1")._value.get() == 0.0


def test_extraction_info_label_is_bounded(mreg):
    assert mreg.validate("enabled", "1") == "1"
    assert mreg.validate("enabled", "0") == "0"
    with pytest.raises(ValueError):
        mreg.validate("enabled", "2")
    with pytest.raises(ValueError):
        mreg.validate("enabled", "yes")


def test_extraction_info_gauge_labels_are_finite_and_never_ids():
    fresh = core_metrics.ExtractionMetrics(CollectorRegistry())
    assert tuple(fresh.extraction_info._labelnames) == ("enabled",)
    assert not (set(fresh.extraction_info._labelnames) & _FORBIDDEN_LABELS)


def test_executor_shutdown_abandons_only_queued_tasks(json_logs, mreg):
    """Shutdown drains the queue (dropped=N) and never counts in-flight work;
    inflight stays owned by the worker until the task finishes."""
    gate = threading.Event()

    def _blocking():
        gate.wait(timeout=3.0)

    pool = BoundedDaemonExecutor(max_workers=1, max_queue=10)
    try:
        for _ in range(5):
            assert pool.submit(_blocking)
        assert _wait_until(lambda: pool.queue_size == 4)  # 1 running, 4 queued
        assert pool.running

        pool.shutdown()

        assert not pool.running
        payload = _formatted(json_logs)
        assert payload["event"] == "extraction_executor_shutdown"
        assert payload["dropped"] == 4
        assert payload["queue_depth"] == 0
        assert core_metrics.metrics.queue_depth._value.get() == 0.0
        # The in-flight task was NOT counted as abandoned; inflight returns
        # to zero only when the daemon worker finishes (executor-owned gauge).
        assert core_metrics.metrics.inflight._value.get() == 1.0
        gate.set()
        assert _wait_until(lambda: core_metrics.metrics.inflight._value.get() == 0.0)
    finally:
        gate.set()
        pool.shutdown()


def test_executor_shutdown_is_idempotent_and_quiet_when_empty(json_logs):
    pool = BoundedDaemonExecutor(max_workers=1, max_queue=5)
    pool.shutdown()
    pool.shutdown()  # second call must not emit a duplicate event
    events = [r for r in json_logs if getattr(r, "event", None) == "extraction_executor_shutdown"]
    assert len(events) == 1
    assert _formatted(json_logs, json_logs.index(events[0]))["dropped"] == 0


def test_executor_shutdown_queue_capacity_gauge_is_preserved(mreg):
    pool = BoundedDaemonExecutor(max_workers=1, max_queue=10)
    pool.shutdown()
    assert core_metrics.metrics.queue_capacity._value.get() == 10.0


def test_http_traffic_counter_renders_and_is_bounded():
    core_metrics.safe_count_http("chat")
    core_metrics.safe_count_http("other")
    body = core_metrics.render_metrics().decode()
    assert 'owngpt_http_requests_total{endpoint="chat"}' in body
    assert 'owngpt_http_requests_total{endpoint="other"}' in body


def test_http_traffic_counter_rejects_unbounded_endpoints_without_raising():
    core_metrics.safe_count_http("admin-panel")  # fail-open contract
    body = core_metrics.render_metrics().decode()
    assert 'endpoint="admin-panel"' not in body


def test_request_endpoint_classification_is_bounded():
    from app.core.observability import request_endpoint
    assert request_endpoint("/api/v1/chat") == "chat"
    assert request_endpoint("/api/v1/chat/stream?q=1") == "chat"
    assert request_endpoint("/health") == "other"
    assert request_endpoint("/metrics") == "other"
