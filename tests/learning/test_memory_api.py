"""Memory V2 API tests — thin-router behavior over app.services.memory.

Hermetic: in-memory sqlite engine with get_sync_db and
get_embedding_provider overridden. No agent infrastructure is involved.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_sync_db
from app.core.config import settings
from app.api.deps import get_embedding_provider

# Register all tables (chat_sessions.project_id / memory_entities.project_id
# FK resolve lazily; Project/ChatSession must be in metadata before create_all).
from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401
from app.models import user as _user_model  # noqa: F401

DIM = settings.MEMORY_EMBEDDING_DIMENSION


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class FakeEmbeddingProvider:
    """Deterministic keyword-coded vectors: 'alice' -> dim0, 'sky' -> dim1."""

    model_name = "fake-text-embedding"
    dimension = DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * DIM
            if "alice" in t:
                v[0] = 1.0
            if "sky" in t:
                v[1] = 1.0
            out.append(v)
        return out


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
def session_factory(test_engine):
    from sqlalchemy.orm import Session

    return sessionmaker(bind=test_engine, class_=Session, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def user(db):
    from app.services import auth as auth_svc

    return auth_svc.create_user(db, "alice", "password123")


@pytest.fixture
def second_user(db):
    from app.services import auth as auth_svc

    return auth_svc.create_user(db, "bob", "password123")


@pytest.fixture
def alice_token(db, user) -> str:
    from app.services import auth as auth_svc

    return auth_svc.issue_token(db, user.id)


@pytest.fixture
def bob_token(db, second_user) -> str:
    from app.services import auth as auth_svc

    return auth_svc.issue_token(db, second_user.id)


def _build_client(test_engine, provider):
    from app.api.endpoints import memory as mem_ep
    from app.api.endpoints import projects as proj_ep

    TestingSessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_db():
        with TestingSessionLocal() as s:
            yield s

    app = FastAPI()
    app.include_router(mem_ep.router, prefix="/api/v1/memory")
    app.include_router(proj_ep.router, prefix="/api/v1/projects")

    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    @app.exception_handler(HTTPException)
    async def _handle(request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            body = {"error": {"code": "error", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    app.dependency_overrides[get_sync_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    return TestClient(app)


@pytest.fixture
def client(test_engine):
    return _build_client(test_engine, FakeEmbeddingProvider())


@pytest.fixture
def client_no_provider(test_engine):
    return _build_client(test_engine, None)


# ---------------------------------------------------------------------------
# Auth / ownership
# ---------------------------------------------------------------------------

def test_memory_routes_require_auth(client):
    r = client.post("/api/v1/memory", json={"statement": "x", "domain": "semantic"})
    assert r.status_code == 401
    r = client.get("/api/v1/memory", headers=_bearer("not-a-token"))
    assert r.status_code == 401
    r = client.get("/api/v1/projects", headers=_bearer("not-a-token"))
    assert r.status_code == 401


def test_memory_isolation_across_users(client, alice_token, bob_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 201
    mem_id = r.json()["id"]

    r = client.get(f"/api/v1/memory/{mem_id}", headers=_bearer(bob_token))
    assert r.status_code == 404

    r = client.get("/api/v1/memory", headers=_bearer(bob_token))
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------

def test_create_and_get_memory(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"].startswith("mem-")
    assert body["status"] == "active"
    assert body["domain"] == "semantic"
    assert body["user_id"] != "" and body["version"] == 1

    r = client.get(f"/api/v1/memory/{body['id']}", headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["statement"] == "user's name is alice"


def test_create_memory_invalid_domain_400(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "x", "domain": "bogus"},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 422


def test_create_memory_foreign_project_rejected(client, alice_token, bob_token):
    r = client.post(
        "/api/v1/projects", json={"name": "bob-project"}, headers=_bearer(bob_token)
    )
    bob_project_id = r.json()["id"]

    r = client.post(
        "/api/v1/memory",
        json={"statement": "sneaky", "domain": "semantic", "project_id": bob_project_id},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"

    # Missing and foreign are indistinguishable — no existence oracle.
    r = client.post(
        "/api/v1/memory",
        json={"statement": "sneaky", "domain": "semantic", "project_id": "no-such-project"},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_create_memory_with_own_project(client, alice_token):
    r = client.post(
        "/api/v1/projects", json={"name": "alice-project"}, headers=_bearer(alice_token)
    )
    project_id = r.json()["id"]

    r = client.post(
        "/api/v1/memory",
        json={"statement": "alice works on python", "domain": "semantic", "project_id": project_id},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 201
    assert r.json()["project_id"] == project_id


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_returns_top_hits_and_backfills(client, alice_token, db):
    from app.models.memory import MemoryEntity

    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    alice_id = r.json()["id"]
    client.post(
        "/api/v1/memory",
        json={"statement": "the sky is green", "domain": "semantic"},
        headers=_bearer(alice_token),
    )

    r = client.post(
        "/api/v1/memory/search",
        json={"query": "alice", "k": 5},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert len(hits) >= 1
    assert hits[0]["statement"] == "user's name is alice"
    assert hits[0]["score"] > hits[-1]["score"] if len(hits) > 1 else True

    entity = db.get(MemoryEntity, alice_id)
    assert entity is not None and entity.embedding is not None


def test_search_empty_query_400(client, alice_token):
    r = client.post(
        "/api/v1/memory/search",
        json={"query": "   "},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "empty_query"


def test_search_requires_embedding_provider(client_no_provider, alice_token):
    client_no_provider.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    r = client_no_provider.post(
        "/api/v1/memory/search",
        json={"query": "alice"},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "embedding_provider_disabled"


def test_search_project_context_includes_project_memory(client, alice_token):
    r = client.post(
        "/api/v1/projects", json={"name": "p1"}, headers=_bearer(alice_token)
    )
    project_id = r.json()["id"]
    client.post(
        "/api/v1/memory",
        json={"statement": "alice owns the p1 codebase", "domain": "semantic", "project_id": project_id},
        headers=_bearer(alice_token),
    )
    r = client.post(
        "/api/v1/memory/search",
        json={"query": "alice", "project_id": project_id},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 200
    assert any(h["statement"] == "alice owns the p1 codebase" for h in r.json()["hits"])


def test_search_project_ownership_enforced(client, alice_token, bob_token):
    r = client.post(
        "/api/v1/projects", json={"name": "bob-p"}, headers=_bearer(bob_token)
    )
    bob_project_id = r.json()["id"]

    for project_id in (bob_project_id, "no-such-project"):
        r = client.post(
            "/api/v1/memory/search",
            json={"query": "alice", "project_id": project_id},
            headers=_bearer(alice_token),
        )
        assert r.status_code == 404, project_id
        assert r.json()["error"]["code"] == "project_not_found", project_id


# ---------------------------------------------------------------------------
# PATCH immutability
# ---------------------------------------------------------------------------

def test_patch_immutable_fields_400(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    mem_id = r.json()["id"]

    for field in ("statement", "domain", "status"):
        payload = {field: "changed"}
        if field == "status":
            payload[field] = "archived"
        r = client.patch(
            f"/api/v1/memory/{mem_id}", json=payload, headers=_bearer(alice_token)
        )
        assert r.status_code == 400, field
        assert r.json()["error"]["code"] == "immutable_field", field


def test_patch_attributes_ok(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    mem_id = r.json()["id"]

    r = client.patch(
        f"/api/v1/memory/{mem_id}",
        json={"importance": 0.9, "metadata": {"source": "manual"}},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["importance"] == 0.9
    assert body["metadata"] == {"source": "manual"}


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def test_promote_active_rejected_400(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    mem_id = r.json()["id"]
    r = client.post(f"/api/v1/memory/{mem_id}/promote", json={}, headers=_bearer(alice_token))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_transition"


def test_supersede_and_archive_and_delete_lifecycle(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    mem_id = r.json()["id"]

    r = client.post(f"/api/v1/memory/{mem_id}/supersede", json={"note": "outdated"}, headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["status"] == "superseded"

    r = client.post(f"/api/v1/memory/{mem_id}/archive", json={}, headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["status"] == "archived"

    r = client.delete(f"/api/v1/memory/{mem_id}", headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json() == {"status": "deleted"}

    r = client.get(f"/api/v1/memory/{mem_id}", headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"

    r = client.delete(f"/api/v1/memory/{mem_id}", headers=_bearer(alice_token))
    assert r.status_code == 400


def test_restore_conflict_refused_409(client, alice_token):
    r = client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    active_id = r.json()["id"]
    client.post(
        "/api/v1/memory/search",
        json={"query": "alice"},
        headers=_bearer(alice_token),
    )

    r = client.post(
        "/api/v1/memory",
        json={"statement": "alice likes blue", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    archived_id = r.json()["id"]
    r = client.post(f"/api/v1/memory/{archived_id}/archive", json={}, headers=_bearer(alice_token))
    assert r.status_code == 200

    r = client.post(f"/api/v1/memory/{archived_id}/restore", json={}, headers=_bearer(alice_token))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "conflict_refused"
    assert active_id in err["candidate_ids"]

    r = client.get(f"/api/v1/memory/{archived_id}", headers=_bearer(alice_token))
    assert r.json()["status"] == "archived"


def test_restore_ok_without_conflict(client, alice_token):
    client.post(
        "/api/v1/memory",
        json={"statement": "user's name is alice", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    client.post(
        "/api/v1/memory/search",
        json={"query": "alice"},
        headers=_bearer(alice_token),
    )
    r = client.post(
        "/api/v1/memory",
        json={"statement": "the sky is green", "domain": "semantic"},
        headers=_bearer(alice_token),
    )
    mem_id = r.json()["id"]
    client.post(f"/api/v1/memory/{mem_id}/archive", json={}, headers=_bearer(alice_token))

    r = client.post(f"/api/v1/memory/{mem_id}/restore", json={}, headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["status"] == "active"


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def test_project_crud_flow(client, alice_token):
    r = client.post(
        "/api/v1/projects", json={"name": "alpha", "description": "first"}, headers=_bearer(alice_token)
    )
    assert r.status_code == 201
    project_id = r.json()["id"]
    assert r.json()["owner_id"]

    r = client.get("/api/v1/projects", headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "beta", "description": "renamed"},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "beta"

    r = client.delete(f"/api/v1/projects/{project_id}", headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json() == {"status": "deleted"}

    r = client.delete(f"/api/v1/projects/{project_id}", headers=_bearer(alice_token))
    assert r.status_code == 404


def test_project_delete_in_use_409(client, alice_token):
    r = client.post(
        "/api/v1/projects", json={"name": "in-use"}, headers=_bearer(alice_token)
    )
    project_id = r.json()["id"]
    client.post(
        "/api/v1/memory",
        json={"statement": "alice works on python", "domain": "semantic", "project_id": project_id},
        headers=_bearer(alice_token),
    )

    r = client.delete(f"/api/v1/projects/{project_id}", headers=_bearer(alice_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "project_in_use"


def test_project_isolation_across_users(client, alice_token, bob_token):
    r = client.post(
        "/api/v1/projects", json={"name": "alice-only"}, headers=_bearer(alice_token)
    )
    project_id = r.json()["id"]

    r = client.patch(f"/api/v1/projects/{project_id}", json={"name": "hacked"}, headers=_bearer(bob_token))
    assert r.status_code == 404

    r = client.delete(f"/api/v1/projects/{project_id}", headers=_bearer(bob_token))
    assert r.status_code == 404

    r = client.get("/api/v1/projects", headers=_bearer(bob_token))
    assert r.status_code == 200
    assert r.json()["total"] == 0
