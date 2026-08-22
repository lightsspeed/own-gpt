"""Authentication API — the minimal identity foundation.

- POST /auth/signup   — create a user, returns a bearer token
- POST /auth/login    — authenticate, returns a bearer token
- POST /auth/logout   — revoke the current token
- GET  /auth/me       — current user (id, username, created_at)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import api_error, get_current_user
from app.core.database import get_sync_db
from app.models.user import User
from app.services import auth

logger = logging.getLogger(__name__)
router = APIRouter()


class CredentialsRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserResponse(BaseModel):
    id: str
    username: str
    created_at: str


@router.post("/auth/signup", response_model=AuthResponse)
def signup(request: CredentialsRequest, db: Session = Depends(get_sync_db)):
    try:
        user = auth.create_user(db, request.username, request.password)
    except auth.AuthError as e:
        raise api_error(400, "signup_failed", str(e))
    token = auth.issue_token(db, user.id)
    logger.info("user_signed_up user_id=%s username=%s", user.id, user.username)
    return AuthResponse(token=token, user={"id": user.id, "username": user.username})


@router.post("/auth/login", response_model=AuthResponse)
def login(request: CredentialsRequest, db: Session = Depends(get_sync_db)):
    try:
        user = auth.authenticate(db, request.username, request.password)
    except auth.AuthError as e:
        raise api_error(401, "invalid_credentials", str(e))
    token = auth.issue_token(db, user.id)
    return AuthResponse(token=token, user={"id": user.id, "username": user.username})


@router.post("/auth/logout")
def logout(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    # The dependency already resolved the token; revoke it by scanning the
    # request header again via a small helper is not possible here, so we
    # revoke all tokens for this user on logout (simple, safe).
    from sqlalchemy import delete

    from app.models.user import AuthToken

    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    db.commit()
    return {"status": "logged_out"}


@router.get("/auth/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )