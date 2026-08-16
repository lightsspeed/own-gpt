"""V2.2 P1 memory-extraction execution control tests — deterministic, sqlite,
no network, no real Redis/LLM (FakeRedis mirrors the throttle Lua script)."""

from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.learning.extraction import extractor as ex
from app.learning.extraction.coordinator import ExecutionCoordinator
from app.learning.extraction.executor import BoundedDaemonExecutor
from app.models.memory import MemoryEntity
from app.models.project import Project
from app.services import auth

# Every table referenced by the ownership chain + extraction input.
from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401


# ---------------------------------------------------------------------------
# FakeRedis — in-memory Redis double implementing EX/NX/TTL semantics plus a
# Python interpreter of the exact coordinator throttle Lua script.
# ---------------------------------------------------------------------------

class FakeRedis:
    def __init__(self):
        self._data: dict[str, tuple[object, float | None]] = {}  # key -> (value, expires_at)
        self._now = 0.0
        self.broken = False

    def _check(self):
        if self.broken:
            raise ConnectionError("redis down")

    def _purge(self, key: str) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return False
        _value, expires_at = entry
        if expires_at is not None and self._now >= expires_at:
            del self._data[key]
            return False
        return True

    def set(self, name: str, value: object, ex=None, nx=False) -> bool:
        self._check()
        if nx and self._purge(name):  # NX: fail when the key already exists
            return False
        self._data[name] = (value, self._now + ex if ex is not None else None)
        return True

    def get(self, name: str):
        self._check()
        if not self._purge(name):
            return None
        return self._data[name][0]

    def delete(self, *names) -> int:
        self._check()
        removed = 0
        for name in names:
            if self._data.pop(name, None) is not None:
                removed += 1
        return removed

    def register_script(self, script):
        return _FakeScript(self, script)

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def ttl(self, name: str) -> float | None:
        entry = self._data.get(name)
        if entry is None:
            return None
        _value, expires_at = entry
        if expires_at is None:
            return None
        return max(0.0, expires_at - self._now)


class _FakeScript:
    """Executes the coordinator throttle script semantics in Python.
    MUST stay in sync with the Lua in app/learning/extraction/coordinator.py."""

    def __init__(self, redis: FakeRedis, script: str):
        self._r = redis
        self._script = script

    def __call__(self, keys, args):
        r = self._r
        r._check()
        key = keys[0]
        seq = int(args[0])
        ttl = float(args[1])
        interval = int(args[2])
        raw = r.get(key)
        if raw is None:
            r.set(key, str(seq), ex=ttl)
            return 1
        if (seq - int(raw)) >= interval:
            r.set(key, str(seq), ex=ttl)
            return 1
        return 0


def _wait_until(cond, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


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
def project(db, user) -> Project:
    p = Project(owner_id=user.id, name="Test Project")
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def executor():
    pool = BoundedDaemonExecutor(max_workers=2, max_queue=10)
    yield pool
    pool.shutdown()


@pytest.fixture
def coord(monkeypatch):
    """Fresh in-process coordinator (no Redis) — isolates throttle/claim
    state between tests and keeps the suite free of network access."""
    c = ExecutionCoordinator(redis_url=None)
    monkeypatch.setattr(ex, "coordinator", c)
    return c


# ---------------------------------------------------------------------------
# A. Bounded concurrency
# ---------------------------------------------------------------------------

def test_bounded_concurrency_limits_running_tasks():
    pool = BoundedDaemonExecutor(max_workers=2, max_queue=8)
    cond = threading.Condition()
    running: list[int] = []
    release = threading.Event()

    def task(i: int):
        with cond:
            running.append(i)
            cond.notify_all()
        release.wait(5)

    for i in range(5):
        assert pool.submit(task, i) is True

    with cond:
        started_two = cond.wait_for(lambda: len(running) >= 2, timeout=5)
    assert started_two
    with cond:
        assert len(running) == 2  # the other 3 wait in the queue
    release.set()
    with cond:
        all_done = cond.wait_for(lambda: len(running) == 5, timeout=5)
    assert all_done
    pool.shutdown()


def test_executor_queue_full_reports_false():
    pool = BoundedDaemonExecutor(max_workers=1, max_queue=2)
    release = threading.Event()

    def block():
        release.wait(5)

    assert pool.submit(block) is True    # occupies the single worker
    assert pool.submit(block) is True    # queued
    assert pool.submit(block) is False   # queue full — never raises
    release.set()
    pool.shutdown()


def test_executor_rejects_after_shutdown():
    pool = BoundedDaemonExecutor(max_workers=1, max_queue=4)
    pool.shutdown()
    assert pool.submit(lambda: None) is False
    assert pool.running is False


# ---------------------------------------------------------------------------
# B/C. Single-flight — duplicate and concurrent scheduling
# ---------------------------------------------------------------------------

def test_schedule_duplicate_turn_second_is_skipped(executor, monkeypatch):
    coord = ExecutionCoordinator(redis_url=None)
    monkeypatch.setattr(ex, "coordinator", coord)
    monkeypatch.setattr(ex, "extraction_executor", executor)

    calls: list[object] = []
    started = threading.Event()
    release = threading.Event()

    def fake_run(_session_id, _user_id, _project_id, user_msg_id, *args, **kwargs):
        calls.append(user_msg_id)
        started.set()
        release.wait(5)

    monkeypatch.setattr(ex, "run_extraction", fake_run)

    assert ex.schedule_extraction("s1", "u1", None, 7) is True
    started.wait(5)
    assert ex.schedule_extraction("s1", "u1", None, 7) is False  # duplicate
    assert ex.schedule_extraction("s1", "u1", None, 8) is True   # next turn ok
    release.set()
    assert _wait_until(lambda: len(calls) == 2)
    assert calls == [7, 8]
    assert _wait_until(lambda: coord.claim_turn("s1", 7))


def test_concurrent_duplicate_scheduling_runs_once(executor, monkeypatch):
    coord = ExecutionCoordinator(redis_url=None)
    monkeypatch.setattr(ex, "coordinator", coord)
    monkeypatch.setattr(ex, "extraction_executor", executor)

    calls: list[object] = []
    started = threading.Event()
    release = threading.Event()

    def fake_run(_session_id, _user_id, _project_id, user_msg_id, *args, **kwargs):
        calls.append(user_msg_id)
        started.set()
        release.wait(5)

    monkeypatch.setattr(ex, "run_extraction", fake_run)

    results: list[bool] = []
    barrier = threading.Barrier(2)

    def sched():
        barrier.wait()
        results.append(ex.schedule_extraction("s1", "u1", None, 7))

    t1 = threading.Thread(target=sched)
    t2 = threading.Thread(target=sched)
    t1.start()
    t2.start()
    assert started.wait(5)
    t1.join(5)
    t2.join(5)
    release.set()
    assert sorted(results) == [False, True]
    assert len(calls) == 1


def test_claim_release_semantics_in_process():
    coord = ExecutionCoordinator(redis_url=None)
    assert coord.claim_turn("s1", 7) is True
    assert coord.claim_turn("s1", 7) is False
    assert coord.claim_turn("s1", 8) is True      # different turn unaffected
    coord.release_turn("s1", 7)
    assert coord.claim_turn("s1", 7) is True      # released → claimable again


# ---------------------------------------------------------------------------
# D. Redis behavior
# ---------------------------------------------------------------------------

def test_redis_claim_atomic_across_coordinators():
    fake = FakeRedis()
    c1 = ExecutionCoordinator(client=fake, sf_ttl=300)
    c2 = ExecutionCoordinator(client=fake, sf_ttl=300)
    assert c1.claim_turn("s1", 7, owner="a") is True
    assert c2.claim_turn("s1", 7, owner="b") is False   # cross-worker exclusion
    assert c1.claim_turn("s1", 8) is True               # different turn ok
    assert fake.ttl("memory:extraction:sf:s1:7") == 300  # TTL documented
    c1.release_turn("s1", 7)
    assert c2.claim_turn("s1", 7) is True               # released → claimable


def test_redis_throttle_interval_and_ttl():
    fake = FakeRedis()
    coord = ExecutionCoordinator(client=fake, interval=3, throttle_ttl=3600)
    assert coord.throttle_allowed("s1", 10)
    assert not coord.throttle_allowed("s1", 11)
    assert not coord.throttle_allowed("s1", 12)
    assert coord.throttle_allowed("s1", 13)            # 3 == interval
    assert coord.throttle_allowed("s2", 1)             # other session independent
    assert fake.ttl("memory:extraction:throttle:s1") == 3600
    assert fake.get("memory:extraction:throttle:s1") == "13"


def test_redis_claim_fails_open_to_in_process_state():
    fake = FakeRedis()
    fake.broken = True
    coord = ExecutionCoordinator(client=fake)
    assert coord.claim_turn("s1", 7) is True
    assert coord.claim_turn("s1", 7) is False
    coord.release_turn("s1", 7)
    assert coord.claim_turn("s1", 7) is True
    assert coord.throttle_allowed("s1", 10) is True
    assert coord.throttle_allowed("s1", 11) is False


# ---------------------------------------------------------------------------
# E. TTL expiration (crash safety)
# ---------------------------------------------------------------------------

def test_single_flight_ttl_expiry_allows_retry():
    fake = FakeRedis()
    coord = ExecutionCoordinator(client=fake, sf_ttl=300)
    assert coord.claim_turn("s1", 7)
    fake.advance(301)                     # claiming worker died, TTL elapsed
    assert coord.claim_turn("s1", 7)


def test_throttle_ttl_expiry_allows_extraction_again():
    fake = FakeRedis()
    coord = ExecutionCoordinator(client=fake, interval=3, throttle_ttl=3600)
    assert coord.throttle_allowed("s1", 10)
    fake.advance(3601)                    # orphaned marker expired
    assert coord.throttle_allowed("s1", 11)


# ---------------------------------------------------------------------------
# F. Process restart semantics
# ---------------------------------------------------------------------------

def test_in_process_state_resets_on_restart():
    c1 = ExecutionCoordinator(redis_url=None)
    assert c1.claim_turn("s1", 7)
    assert not c1.claim_turn("s1", 7)
    assert c1.throttle_allowed("s1", 10)
    assert not c1.throttle_allowed("s1", 11)

    c2 = ExecutionCoordinator(redis_url=None)  # simulated process restart
    assert c2.claim_turn("s1", 7) is True       # claims are not durable
    assert c2.throttle_allowed("s1", 11) is True


# ---------------------------------------------------------------------------
# G/H. Fail-open scheduling
# ---------------------------------------------------------------------------

def test_schedule_with_failing_extraction_never_raises(executor, monkeypatch):
    coord = ExecutionCoordinator(redis_url=None)
    monkeypatch.setattr(ex, "coordinator", coord)
    monkeypatch.setattr(ex, "extraction_executor", executor)

    def boom(*_a, **_k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(ex, "run_extraction", boom)
    assert ex.schedule_extraction("s1", "u1", None, 7) is True
    # worker ran the task, absorbed the failure, released the claim
    assert _wait_until(lambda: coord.claim_turn("s1", 7))


def test_schedule_after_executor_shutdown_never_raises(monkeypatch):
    pool = BoundedDaemonExecutor(max_workers=1, max_queue=1)
    pool.shutdown()
    monkeypatch.setattr(ex, "coordinator", ExecutionCoordinator(redis_url=None))
    monkeypatch.setattr(ex, "extraction_executor", pool)
    assert ex.schedule_extraction("s1", "u1", None, 7) is False


# ---------------------------------------------------------------------------
# J. Turn-boundary safety — extraction input is exactly one completed turn
# ---------------------------------------------------------------------------

def _conv_with(db, user, session_id: str, rows: list[tuple[str, str, str]]):
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


def test_run_extraction_extracts_only_its_own_turn(engine, user, coord, monkeypatch):
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with S() as db:
        msgs = _conv_with(db, user, "sess-t", [
            ("user", "turn one fact: I like kotlin", "completed"),
            ("assistant", "ok one", "completed"),
            ("user", "turn two fact: I like go", "completed"),
            ("assistant", "ok two", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)

    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.embeddings.build_embedding_provider",
        lambda: SimpleNamespace(embed=lambda texts: [[0.0] * 1536 for _ in texts]),
    )

    exchange_seen: list[str] = []

    def fake_llm(exchange, run_id=None):
        exchange_seen.append(exchange)
        return [{"statement": "durable fact", "domain": "semantic", "importance": 0.5}]

    monkeypatch.setattr(ex, "_extract_with_llm", fake_llm)

    assert ex.run_extraction("sess-t", user.id, None, msgs[0].id) == 1
    assert "I like kotlin" in exchange_seen[0]
    assert "I like go" not in exchange_seen[0]   # later turn never leaks in

    with S() as db:
        entities = list(db.execute(select(MemoryEntity)).scalars())
        assert len(entities) == 1
        assert entities[0].statement == "durable fact"


def test_run_extraction_skips_turn_without_completed_reply(engine, user, coord, monkeypatch):
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with S() as db:
        msgs = _conv_with(db, user, "sess-inc", [
            ("user", "fact without reply", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "_extract_with_llm", lambda exchange, **kwargs: [])

    assert ex.run_extraction("sess-inc", user.id, None, msgs[0].id) == 0


def test_run_extraction_skips_turn_with_failed_reply(engine, user, coord, monkeypatch):
    """Partially-written assistant content (status=failed) is never extracted."""
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with S() as db:
        msgs = _conv_with(db, user, "sess-fail", [
            ("user", "fact with failed reply", "completed"),
            ("assistant", "Partial", "failed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "_extract_with_llm", lambda exchange, **kwargs: [])

    assert ex.run_extraction("sess-fail", user.id, None, msgs[0].id) == 0


def test_run_extraction_unknown_turn_is_noop(engine, user, coord, monkeypatch):
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with S() as db:
        msgs = _conv_with(db, user, "sess-u", [
            ("user", "real fact", "completed"),
            ("assistant", "ok", "completed"),
        ])
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "_extract_with_llm", lambda exchange, **kwargs: [])

    assert ex.run_extraction("sess-u", user.id, None, 999999) == 0   # no such message
