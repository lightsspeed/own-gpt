"""Memory extraction (V2.2) tests — deterministic, sqlite, no network."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.learning.extraction import extractor as ex
from app.models.memory import (
    AUTHORITY_EXTRACTED,
    SOURCE_EXTRACTED,
    STATUS_PENDING,
    MemoryEntity,
)
from app.models.project import Project
from app.services import auth

# Every table referenced by the ownership chain + extraction input.
from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401


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


# ── Gate 1: eligibility ──────────────────────────────────────────────────

def test_eval_sessions_never_extract():
    assert not ex._is_eligible("eval-123", "I use Python", "Great!")


def test_empty_or_filler_turns_never_extract():
    assert not ex._is_eligible("sess-1", "ok", "Alright.")
    assert not ex._is_eligible("sess-1", "!!", "Alright.")
    assert not ex._is_eligible("sess-1", "I use Python", "")


def test_explicit_command_turns_never_extract():
    assert ex._command_or_recall_turn("remember that I like kotlin")
    assert ex._command_or_recall_turn("my name is Alice")
    assert not ex._command_or_recall_turn("I prefer kotlin for side projects")


def test_general_chat_never_extracts():
    assert not ex._is_eligible("sess-1", "thanks!", "You're welcome")


def test_substantive_turn_is_eligible():
    assert ex._is_eligible("sess-1", "I prefer kotlin for side projects", "Good to know")


def test_throttle_one_per_interval():
    ex._throttle.clear()
    assert ex._throttle_allowed("sess-1", 10)
    assert not ex._throttle_allowed("sess-1", 11)   # 1 < interval
    assert not ex._throttle_allowed("sess-1", 12)   # 2 < interval
    assert ex._throttle_allowed("sess-1", 13)       # 3 == interval
    assert ex._throttle_allowed("sess-2", 1)        # other session independent
    ex._throttle.clear()


# ── Gate 3: validation (batch-atomic) ────────────────────────────────────

def test_valid_candidates_pass_gate3():
    got = ex._validate_candidates([
        {"statement": "the user prefers kotlin", "domain": "preference", "importance": 0.8},
    ])
    assert len(got) == 1
    assert got[0]["domain"] == "preference"


def test_gate3_drops_whole_batch_on_any_violation():
    good = {"statement": "valid fact", "domain": "semantic", "importance": 0.5}
    assert ex._validate_candidates([good]) == [good]
    assert ex._validate_candidates([good, {"statement": "x" * 501, "domain": "semantic", "importance": 0.5}]) == []
    assert ex._validate_candidates([good, {"statement": "bad", "domain": "astrology", "importance": 0.5}]) == []
    assert ex._validate_candidates([good, {"statement": "bad", "domain": "semantic", "importance": 9}]) == []
    assert ex._validate_candidates("not a list") == []
    assert ex._validate_candidates([good] * 4) == []


def test_gate3_drops_batch_containing_secret_material():
    got = ex._validate_candidates([
        {"statement": "the api key is sk-1234567890abcdefghij", "domain": "semantic", "importance": 0.5},
    ])
    assert got == []


# ── End-to-end run_extraction ────────────────────────────────────────────

def test_run_extraction_writes_pending_memories(engine, user, project, monkeypatch):
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with S() as db:
        from app.models.chat import ChatMessage, ChatSession
        from app.services import chat_persistence as store

        conv = store.create_conversation(db, user, "sess-1", title="T")
        db.add(ChatMessage(session_id=conv.id, role="user", content="I prefer kotlin for side projects and I work at Acme", status="completed", sequence=1))
        db.add(ChatMessage(session_id=conv.id, role="assistant", content="Good to know!", status="completed", sequence=2))
        db.commit()

    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    from types import SimpleNamespace

    dim = 1536  # = settings.MEMORY_EMBEDDING_DIMENSION (test default)

    def pad(texts):
        return [[0.0] * dim for _ in texts]

    fake_provider = SimpleNamespace(embed=pad)
    monkeypatch.setattr(
        "app.services.embeddings.build_embedding_provider", lambda: fake_provider
    )

    def fake_llm(exchange):
        return [
            {"statement": "the user prefers kotlin", "domain": "preference", "importance": 0.8},
            {"statement": "the user works at acme", "domain": "semantic", "importance": 0.6},
        ]

    monkeypatch.setattr(ex, "_extract_with_llm", fake_llm)
    ex._throttle.clear()

    written = ex.run_extraction("sess-1", user.id, project.id)

    assert written == 2
    with S() as db:
        entities = list(db.execute(select(MemoryEntity).order_by(MemoryEntity.statement)).scalars())
        assert len(entities) == 2
        for e in entities:
            assert e.status == STATUS_PENDING
            assert e.source == SOURCE_EXTRACTED
            assert e.authority == AUTHORITY_EXTRACTED
            assert e.confidence == 0.65
            assert e.project_id == project.id
            assert e.source_conversation_id == "sess-1"
    ex._throttle.clear()


def test_run_extraction_skips_eval_sessions(engine, user, monkeypatch):
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "_extract_with_llm", lambda exchange: [])

    assert ex.run_extraction("eval-9", user.id) == 0


def test_run_extraction_malformed_llm_output_writes_nothing(engine, user, monkeypatch):
    from sqlalchemy.orm import Session

    S = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with S() as db:
        from app.models.chat import ChatMessage
        from app.services import chat_persistence as store

        conv = store.create_conversation(db, user, "sess-2", title="T")
        db.add(ChatMessage(session_id=conv.id, role="user", content="I prefer kotlin for side projects", status="completed", sequence=1))
        db.add(ChatMessage(session_id=conv.id, role="assistant", content="Good to know!", status="completed", sequence=2))
        db.commit()

    monkeypatch.setattr("app.core.database.SyncSessionLocal", S)
    monkeypatch.setattr(ex, "_extract_with_llm", lambda exchange: [{"statement": "x" * 600, "domain": "semantic", "importance": 0.5}])
    ex._throttle.clear()

    assert ex.run_extraction("sess-2", user.id) == 0

    with S() as db:
        assert db.execute(select(MemoryEntity)).scalars().all() == []
    ex._throttle.clear()
