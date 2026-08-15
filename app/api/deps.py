"""FastAPI dependencies — authentication and standard error helpers."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_sync_db
from app.models.user import User
from app.services import auth
from app.services.embeddings import EmbeddingProvider, build_embedding_provider

logger = logging.getLogger(__name__)


def _unauthorized(message: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_sync_db),
) -> User:
    """Resolve the authenticated user for a request.

    - Authorization: Bearer <token>  → the token's owner (server-side lookup).
    - No header + single-user fallback enabled + exactly one user exists
      → that user (legacy single-user deployments keep working).
    - Otherwise → 401.
    """
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[len("Bearer ") :].strip()
        user = auth.get_user_by_token(db, token)
        if user is None:
            raise _unauthorized("Invalid or expired token")
        return user

    if settings.AUTH_ALLOW_SINGLE_USER_FALLBACK:
        user = auth.single_fallback_user(db)
        if user is not None:
            logger.info("auth_fallback_single_user user_id=%s", user.id)
            return user

    raise _unauthorized()


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Standard API error envelope: {"error": {"code", "message"}}."""
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


def get_embedding_provider() -> EmbeddingProvider | None:
    """Resolve the configured memory embedding provider (None = 'none')."""
    return build_embedding_provider()