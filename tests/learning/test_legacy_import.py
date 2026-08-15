"""Legacy memory import tests — deterministic, sqlite, injectable db."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base

# Register all tables before create_all (FKs resolve lazily).
from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401
from app.models import user as _user_model  # noqa: F401

from app.services import memory as mem
from app.services.memory_legacy_import import run_import


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def user(db):
    from app.services import auth as auth_svc

    return auth_svc.create_user(db, "alice", "password123")


@pytest.fixture
def second_user(db):
    from app.services import auth as auth_svc

    return auth_svc.create_user(db, "bob", "password123")


def _write_fact(tmp_path, name: str, payload: dict):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_global_fact_imported_as_migrated(db, user, tmp_path):
    _write_fact(
        tmp_path,
        "f1.json",
        {"id": "fact-1", "fact": "alice prefers python", "scope": "global", "status": "active"},
    )
    report = run_import(tmp_path, user.id, dry_run=False, db=db)

    assert [r["status"] for r in report["imported"]] == ["imported"]
    entity = mem.list_memories(db, user.id)[0]
    assert entity.statement == "alice prefers python"
    assert entity.source == "migrated"
    assert entity.authority == "migrated"
    assert entity.confidence == 0.5
    assert entity.project_id is None
    assert entity.metadata_["legacy_fact_id"] == "fact-1"
    assert entity.metadata_["legacy_scope"] == "global"


def test_import_is_idempotent_via_legacy_fact_id(db, user, tmp_path):
    _write_fact(
        tmp_path,
        "f1.json",
        {"id": "fact-1", "fact": "alice prefers python", "scope": "global", "status": "active"},
    )
    first = run_import(tmp_path, user.id, dry_run=False, db=db)
    second = run_import(tmp_path, user.id, dry_run=False, db=db)

    assert len(first["imported"]) == 1
    assert len(second["imported"]) == 0
    assert second["skipped"][0]["detail"] == "already imported (legacy_fact_id match)"
    assert len(mem.list_memories(db, user.id)) == 1


def test_session_scope_requires_owned_session(db, user, second_user, tmp_path):
    from app.models.chat import ChatSession

    owned = ChatSession(id="s-1", owner_id=user.id)
    foreign = ChatSession(id="s-2", owner_id=second_user.id)
    db.add_all([owned, foreign])
    db.commit()

    _write_fact(tmp_path, "owned.json", {"id": "f-a", "fact": "from owned session", "scope": "session:s-1", "status": "active"})
    _write_fact(tmp_path, "foreign.json", {"id": "f-b", "fact": "from foreign session", "scope": "session:s-2", "status": "active"})
    _write_fact(tmp_path, "missing.json", {"id": "f-c", "fact": "from gone session", "scope": "session:s-99", "status": "active"})

    report = run_import(tmp_path, user.id, dry_run=False, db=db)

    imported = {r["file"] for r in report["imported"]}
    skipped = {r["file"]: r["detail"] for r in report["skipped"]}
    assert imported == {"owned.json"}
    assert "missing.json" in skipped and "does not exist" in skipped["missing.json"]
    assert "foreign.json" in skipped and "owned by another user" in skipped["foreign.json"]

    entities = mem.list_memories(db, user.id)
    assert [e.statement for e in entities] == ["from owned session"]


def test_superseded_legacy_status_preserved(db, user, tmp_path):
    _write_fact(
        tmp_path,
        "f1.json",
        {"id": "fact-old", "fact": "old fact", "scope": "global", "status": "superseded"},
    )
    run_import(tmp_path, user.id, dry_run=False, db=db)
    entity = mem.list_memories(db, user.id)[0]
    assert entity.status == "superseded"


def test_dry_run_writes_nothing(db, user, tmp_path):
    _write_fact(
        tmp_path,
        "f1.json",
        {"id": "fact-1", "fact": "alice prefers python", "scope": "global", "status": "active"},
    )
    report = run_import(tmp_path, user.id, dry_run=True, db=db)

    assert report["dry_run"] is True
    assert report["imported"][0]["status"] == "plan"
    assert len(mem.list_memories(db, user.id)) == 0


def test_bad_json_skipped_with_error(db, user, tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    report = run_import(tmp_path, user.id, dry_run=False, db=db)
    assert len(report["imported"]) == 0
    assert report["skipped"][0]["status"] == "error"