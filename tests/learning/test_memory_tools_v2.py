"""Memory tool rewiring (V2.2) tests — tools write via MemoryService.

The impls open their own SyncSessionLocal inside the function body, so tests
monkeypatch app.core.database.SyncSessionLocal to the sqlite test sessionmaker.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import tool_impls
from app.core.database import Base
from app.models.memory import (
    AUTHORITY_EXPLICIT_USER,
    EVENT_DELETED,
    SOURCE_USER_DECLARED,
    STATUS_ACTIVE,
    STATUS_DELETED,
    MemoryEntity,
    MemoryEvent,
)
from app.models.project import Project
from app.services import auth

from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401


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


@pytest.fixture(autouse=True)
def _bind_sessions(monkeypatch, session_factory):
    monkeypatch.setattr("app.core.database.SyncSessionLocal", session_factory)


@pytest.fixture
def user(session_factory):
    with session_factory() as db:
        u = auth.create_user(db, "alice", "password123")
        return u


@pytest.fixture
def project(session_factory, user) -> Project:
    with session_factory() as db:
        p = Project(owner_id=user.id, name="Test Project")
        db.add(p)
        db.commit()
        return p


def test_remember_user_fact_creates_active_explicit_memory(session_factory, user, project):
    result = tool_impls.remember_user_fact_impl(
        "the user prefers kotlin", user_id=user.id, project_id=project.id
    )
    assert "Successfully saved fact" in result

    with session_factory() as db:
        entity = db.execute(select(MemoryEntity)).scalars().one()
        assert entity.status == STATUS_ACTIVE
        assert entity.source == SOURCE_USER_DECLARED
        assert entity.authority == AUTHORITY_EXPLICIT_USER
        assert entity.confidence == 0.95
        assert entity.project_id == project.id


def test_remember_user_fact_requires_user_context():
    result = tool_impls.remember_user_fact_impl("some fact")
    assert "no authenticated user context" in result


def test_remember_session_fact_links_conversation(session_factory, user, project):
    result = tool_impls.remember_session_fact_impl(
        "we decided to use fastapi",
        session_id="sess-1",
        user_id=user.id,
        project_id=project.id,
    )
    assert "Successfully saved fact" in result

    with session_factory() as db:
        entity = db.execute(select(MemoryEntity)).scalars().one()
        assert entity.source_conversation_id == "sess-1"
        assert entity.status == STATUS_ACTIVE


def test_forget_user_fact_logically_deletes(session_factory, user, project):
    with session_factory() as db:
        from app.services import memory as mem

        mem.create_memory(
            db,
            user_id=user.id,
            statement="the user prefers kotlin",
            domain="preference",
            project_id=project.id,
        )

    result = tool_impls.forget_user_fact_impl(
        "the user prefers kotlin", user_id=user.id, project_id=project.id
    )
    assert "Successfully forgotten" in result

    with session_factory() as db:
        entity = db.execute(select(MemoryEntity)).scalars().one()
        assert entity.status == STATUS_DELETED
        events = list(
            db.execute(
                select(MemoryEvent.event_type).where(MemoryEvent.entity_id == entity.id)
            ).scalars()
        )
        assert EVENT_DELETED in events


def test_forget_user_fact_matches_user_wide_fallback(session_factory, user, project):
    with session_factory() as db:
        from app.services import memory as mem

        mem.create_memory(
            db, user_id=user.id, statement="the user works at acme", domain="semantic"
        )

    result = tool_impls.forget_user_fact_impl(
        "the user works at acme", user_id=user.id, project_id=project.id
    )
    assert "Successfully forgotten" in result

    with session_factory() as db:
        entity = db.execute(select(MemoryEntity)).scalars().one()
        assert entity.status == STATUS_DELETED


def test_forget_user_fact_not_found(session_factory, user):
    result = tool_impls.forget_user_fact_impl("nothing stored here", user_id=user.id)
    assert "No matching memory found" in result
