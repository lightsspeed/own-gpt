"""V3.8 Memory-Aware Agent Learning — hermetic tests.

Covers the 12 required cases:
  1.  Explicit memory request → stored
  2.  Ordinary question → not stored
  3.  Greeting → not stored
  4.  User correction → stored
  5.  Duplicate memory → skipped
  6.  Unsafe/sensitive value → skipped
  7.  Failed validation → prevents learning
  8.  Memory service failure → never breaks the answer
  9.  User isolation propagated
  10. Project isolation propagated
  11. Structured LearningResult
  12. Learner never directly executes tools

No live LLM / API / database testing. SQLite in-memory only.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from app.agent.pipeline.learning import AgentLearner, LearningResult
from app.core.database import Base
from app.models.memory import (
    DOMAIN_PREFERENCE,
    DOMAIN_SEMANTIC,
    SOURCE_USER_DECLARED,
    STATUS_ACTIVE,
    MemoryEntity,
)
from app.models.project import Project
from app.services import auth


# ── Fixtures / helpers ───────────────────────────────────────────────────────

@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def user(session_factory):
    with session_factory() as db:
        return auth.create_user(db, "alice", "password123")


@pytest.fixture
def project(session_factory, user) -> Project:
    with session_factory() as db:
        p = Project(owner_id=user.id, name="Test Project")
        db.add(p)
        db.commit()
        return p


FAKE_EMBED = lambda texts: [[0.1] * 1536 for _ in texts]


def _learner(session_factory, embed=FAKE_EMBED) -> AgentLearner:
    return AgentLearner(session_factory=session_factory, embed=embed)


def _context(user_id=None, project_id=None, session_id="sess-1"):
    return SimpleNamespace(
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
    )


class _Valid:
    valid = True


class _Invalid:
    valid = False


class _Execution:
    status = "completed"


def _stores(session_factory, question, learner=None, user_id="", project_id=None, validation=None):
    learner = learner or _learner(session_factory)
    return learner.learn(
        question=question,
        answer="answer text",
        intent=None,
        execution=_Execution(),
        validation=validation or _Valid(),
        context=_context(user_id=user_id, project_id=project_id),
    )


def _entities(session_factory) -> list[MemoryEntity]:
    with session_factory() as db:
        return list(db.execute(select(MemoryEntity)).scalars().all())


# ── 1: Explicit memory request ───────────────────────────────────────────────

def test_explicit_memory_gets_stored(session_factory, user):
    result = _stores(
        session_factory,
        "Remember that my favorite DevOps tool is Kubernetes.",
        user_id=user.id,
    )

    assert result.memories_created == 1
    assert result.memories_updated == 0
    assert result.memories_skipped == 0
    assert result.reason == "stored via Memory V2"

    mems = _entities(session_factory)
    assert len(mems) == 1
    assert mems[0].user_id == user.id
    assert mems[0].domain == DOMAIN_PREFERENCE
    assert mems[0].source == SOURCE_USER_DECLARED
    assert mems[0].status == STATUS_ACTIVE
    assert "kubernetes" in mems[0].statement


# ── 2: Ordinary question ─────────────────────────────────────────────────────

def test_ordinary_question_not_stored(session_factory, user):
    result = _stores(session_factory, "What is Kubernetes?", user_id=user.id)

    assert result.memories_created == 0
    assert result.memories_updated == 0
    assert result.memories_skipped == 1
    assert "durable" in result.reason
    assert _entities(session_factory) == []


# ── 3: Greeting ──────────────────────────────────────────────────────────────

def test_greeting_not_stored(session_factory, user):
    for greeting in ("Hello!", "Hi there", "Good morning!", "Thanks!"):
        result = _stores(session_factory, greeting, user_id=user.id)
        assert result.memories_created == 0
        assert result.memories_skipped == 1

    assert _entities(session_factory) == []


# ── 4: User correction ───────────────────────────────────────────────────────

def test_user_correction_stored(session_factory, user):
    result = _stores(
        session_factory,
        "Actually, my name is Alex, not Bob.",
        user_id=user.id,
    )

    assert result.memories_created == 1
    assert result.memories_updated == 0
    assert result.memories_skipped == 0

    mems = _entities(session_factory)
    assert len(mems) == 1
    assert mems[0].domain == DOMAIN_SEMANTIC
    assert mems[0].statement == "my name is alex"


# ── 5: Duplicate memory ──────────────────────────────────────────────────────

def test_duplicate_memory_skipped(session_factory, user):
    question = "Remember that my favorite DevOps tool is Kubernetes."
    first = _stores(session_factory, question, user_id=user.id)
    second = _stores(session_factory, question, user_id=user.id)

    assert first.memories_created == 1
    assert second.memories_created == 0
    assert second.memories_updated == 0
    assert second.memories_skipped == 1
    assert "duplicate" in second.reason
    assert len(_entities(session_factory)) == 1


# ── 6: Unsafe / sensitive value ──────────────────────────────────────────────

def test_unsafe_sensitive_value_skipped(session_factory, user):
    result = _stores(
        session_factory,
        "Remember that my favorite API key is sk-abc123xyz",
        user_id=user.id,
    )

    assert result.memories_created == 0
    assert result.memories_skipped == 1
    assert "sensitive" in result.reason
    assert _entities(session_factory) == []

    result = _stores(
        session_factory,
        "My favorite password is hunter2",
        user_id=user.id,
    )
    assert result.memories_created == 0
    assert result.memories_skipped == 1
    assert _entities(session_factory) == []


# ── 7: Failed validation prevents learning ───────────────────────────────────

def test_failed_validation_prevents_learning(session_factory, user):
    result = _stores(
        session_factory,
        "Remember that my favorite DevOps tool is Kubernetes.",
        user_id=user.id,
        validation=_Invalid(),
    )

    assert result.memories_created == 0
    assert result.memories_updated == 0
    assert result.memories_skipped == 1
    assert "validation" in result.reason
    assert _entities(session_factory) == []


# ── 8: Memory service failure never breaks the answer ────────────────────────

def test_memory_service_failure_does_not_break_answer(
    session_factory, user, monkeypatch
):
    def _explode(*args, **kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr("app.services.memory.create_memory", _explode)

    result = _stores(
        session_factory,
        "Remember that my favorite DevOps tool is Kubernetes.",
        user_id=user.id,
    )

    assert result.memories_created == 0
    assert result.memories_skipped == 1
    assert "unaffected" in result.reason
    assert _entities(session_factory) == []


# ── 9: User isolation ────────────────────────────────────────────────────────

def test_user_isolation_propagated(session_factory, user):
    with session_factory() as db:
        bob = auth.create_user(db, "bob", "password123")

    question = "My favorite language is Python."
    alice_result = _stores(session_factory, question, user_id=user.id)
    bob_result = _stores(session_factory, question, user_id=bob.id)

    assert alice_result.memories_created == 1
    assert bob_result.memories_created == 1

    mems = _entities(session_factory)
    assert {m.user_id for m in mems} == {user.id, bob.id}

    with session_factory() as db:
        from app.services.memory import find_memory_by_statement
        alice_hit = find_memory_by_statement(db, user.id, "my favorite language is python")
        bob_hit = find_memory_by_statement(db, bob.id, "my favorite language is python")
        assert alice_hit is not None and alice_hit.user_id == user.id
        assert bob_hit is not None and bob_hit.user_id == bob.id


# ── 10: Project isolation ────────────────────────────────────────────────────

def test_project_isolation_propagated(session_factory, user, project):
    with session_factory() as db:
        other = Project(owner_id=user.id, name="Other Project")
        db.add(other)
        db.commit()

    question = "Remember that I use Terraform for infrastructure."
    first = _stores(session_factory, question, user_id=user.id, project_id=project.id)
    second = _stores(session_factory, question, user_id=user.id, project_id=other.id)

    assert first.memories_created == 1
    assert second.memories_created == 1

    mems = _entities(session_factory)
    assert {m.project_id for m in mems} == {project.id, other.id}
    by_id = {m.project_id: m for m in mems}
    assert by_id[project.id].user_id == user.id
    assert by_id[other.id].user_id == user.id


# ── 11: Structured LearningResult ────────────────────────────────────────────

def test_learning_result_is_structured(session_factory, user):
    empty = LearningResult()
    assert empty.memories_created == 0
    assert empty.memories_updated == 0
    assert empty.memories_skipped == 0
    assert empty.reason == ""

    result = _stores(
        session_factory,
        "Remember that my favorite DevOps tool is Kubernetes.",
        user_id=user.id,
    )
    assert isinstance(result, LearningResult)
    assert isinstance(result.memories_created, int)
    assert isinstance(result.memories_updated, int)
    assert isinstance(result.memories_skipped, int)
    assert isinstance(result.reason, str)
    assert result.memories_created >= 0
    assert result.memories_updated >= 0
    assert result.memories_skipped >= 0


# ── 12: Learner never directly executes tools ────────────────────────────────

def test_learner_never_executes_tools(session_factory, user, monkeypatch):
    calls: list = []

    def _explode(tool, args):
        calls.append((tool, args))
        raise AssertionError("learner must never execute tools")

    monkeypatch.setattr("app.agent.tool_gate.request_tool_execution", _explode)

    result = _stores(
        session_factory,
        "Remember that my favorite DevOps tool is Kubernetes.",
        user_id=user.id,
    )

    assert result.memories_created == 1
    assert calls == []
    assert len(_entities(session_factory)) == 1