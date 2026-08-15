"""
Authentication service — the minimum production-appropriate identity
foundation: password hashing (PBKDF2-HMAC-SHA256, stdlib), opaque bearer
tokens stored as SHA-256 hashes.

Deliberately small: no OAuth, no JWT, no session framework. Username +
password + hashed bearer token fits the existing application architecture.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import AuthToken, User

_PBKDF2_ITERATIONS = 260_000
_ALGO = "pbkdf2_sha256"


class AuthError(Exception):
    """Raised on invalid credentials or token."""


def hash_password(password: str) -> str:
    """Hash a password with a per-user random salt. Format:
    pbkdf2_sha256$iterations$salt_hex$hash_hex"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    ).hex()
    return f"{_ALGO}${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def create_user(db: Session, username: str, password: str) -> User:
    """Create a user; raises AuthError if the username is taken."""
    if not username or not username.strip():
        raise AuthError("username is required")
    if len(password) < 8:
        raise AuthError("password must be at least 8 characters")
    username = username.strip()
    existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing:
        raise AuthError("username is already taken")
    user = User(id=str(uuid.uuid4()), username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.execute(select(User).where(User.username == username.strip())).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("invalid username or password")
    return user


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(db: Session, user_id: str) -> str:
    """Create a bearer token for a user; returns the raw token (store only the hash)."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.AUTH_TOKEN_EXPIRE_DAYS)
    db.add(AuthToken(token_hash=hash_token(token), user_id=user_id, expires_at=expires_at))
    db.commit()
    return token


def revoke_token(db: Session, token: str) -> None:
    row = db.get(AuthToken, hash_token(token))
    if row:
        db.delete(row)
        db.commit()


def get_user_by_token(db: Session, token: str) -> User | None:
    """Resolve a bearer token to a user; None when invalid or expired."""
    row = db.get(AuthToken, hash_token(token))
    if row is None:
        return None
    if row.expires_at is not None:
        expires = row.expires_at
        now = datetime.now(timezone.utc)
        if expires.tzinfo is None:
            now = now.replace(tzinfo=None)
        if expires < now:
            db.delete(row)
            db.commit()
            return None
    return db.get(User, row.user_id)


def single_fallback_user(db: Session) -> User | None:
    """When single-user fallback is enabled and exactly one user exists,
    return that user. Used so unauthenticated legacy clients keep working
    on single-user deployments."""
    if not settings.AUTH_ALLOW_SINGLE_USER_FALLBACK:
        return None
    users = db.execute(select(User)).scalars().all()
    if len(users) == 1:
        return users[0]
    return None