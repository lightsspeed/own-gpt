"""Authentication service and API tests."""

from __future__ import annotations

import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import Base, get_sync_db
from app.services import auth as auth_svc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    from sqlalchemy.orm import Session

    with sessionmaker(bind=engine, class_=Session, expire_on_commit=False)() as s:
        yield s


def test_hash_verify_roundtrip():
    hashed = auth_svc.hash_password("s3cret-pass")
    assert hashed.startswith("pbkdf2_sha256$")
    assert auth_svc.verify_password("s3cret-pass", hashed)
    assert not auth_svc.verify_password("wrong", hashed)
    assert not auth_svc.verify_password("s3cret-pass", "garbage$1$2$3")


def test_hash_is_salted():
    assert auth_svc.hash_password("same") != auth_svc.hash_password("same")


def test_create_user_rejects_duplicate(db):
    auth_svc.create_user(db, "alice", "password123")
    with pytest.raises(auth_svc.AuthError):
        auth_svc.create_user(db, "alice", "password123")
    with pytest.raises(auth_svc.AuthError):
        auth_svc.create_user(db, "bob", "short")


def test_authenticate(db):
    auth_svc.create_user(db, "alice", "password123")
    user = auth_svc.authenticate(db, "alice", "password123")
    assert user.username == "alice"
    with pytest.raises(auth_svc.AuthError):
        auth_svc.authenticate(db, "alice", "nope")


def test_token_issue_verify_revoke(db):
    user = auth_svc.create_user(db, "alice", "password123")
    token = auth_svc.issue_token(db, user.id)
    assert auth_svc.get_user_by_token(db, token).id == user.id
    auth_svc.revoke_token(db, token)
    assert auth_svc.get_user_by_token(db, token) is None
    assert auth_svc.get_user_by_token(db, "totally-made-up") is None


def test_token_does_not_store_plaintext(db):
    user = auth_svc.create_user(db, "alice", "password123")
    token = auth_svc.issue_token(db, user.id)
    from sqlalchemy import select

    from app.models.user import AuthToken

    row = db.execute(select(AuthToken)).scalar_one()
    assert row.token_hash != token
    assert token not in row.token_hash


def test_single_user_fallback(db):
    assert auth_svc.single_fallback_user(db) is None  # zero users
    alice = auth_svc.create_user(db, "alice", "password123")
    assert auth_svc.single_fallback_user(db).id == alice.id
    auth_svc.create_user(db, "bob", "password123")
    assert auth_svc.single_fallback_user(db) is None  # two users → no fallback


# ---------------------------------------------------------------------------
# API-level tests (real signup → token → me flow)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(engine):
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    from app.api.endpoints import auth as auth_endpoints

    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with TestingSessionLocal() as s:
            yield s

    app = FastAPI()
    app.include_router(auth_endpoints.router)

    @app.exception_handler(HTTPException)
    async def _handle(request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            body = {"error": {"code": "error", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    app.dependency_overrides[get_sync_db] = override_db
    return TestClient(app)


def test_signup_login_me_logout_flow(client):
    r = client.post("/auth/signup", json={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    token = body["token"]

    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    login = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["token"]

    bad = client.post("/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"

    out = client.post("/auth/logout", headers=headers)
    assert out.status_code == 200
    me_after = client.get("/auth/me", headers=headers)
    assert me_after.status_code == 401


def test_signup_duplicate_username(client):
    client.post("/auth/signup", json={"username": "alice", "password": "password123"})
    r = client.post("/auth/signup", json={"username": "alice", "password": "password123"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "signup_failed"


def test_me_without_token_returns_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401