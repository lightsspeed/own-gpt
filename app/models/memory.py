"""
Memory V2 models — MemoryEntity + append-only MemoryEvent audit trail.

Immutability: the statement/content of a MemoryEntity is never updated.
Lifecycle transitions append events and flip status. MemoryEvent rows are
insert-only — the audit trail of the memory lifecycle.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base

DOMAIN_SEMANTIC, DOMAIN_EPISODIC, DOMAIN_PREFERENCE, DOMAIN_PROCEDURAL = (
    "semantic",
    "episodic",
    "preference",
    "procedural",
)
DOMAINS = (DOMAIN_SEMANTIC, DOMAIN_EPISODIC, DOMAIN_PREFERENCE, DOMAIN_PROCEDURAL)
SOURCES = (
    "user_declared",
    "extracted",
    "consolidated",
    "migrated",
)
SOURCE_USER_DECLARED, SOURCE_EXTRACTED, SOURCE_CONSOLIDATED, SOURCE_MIGRATED = SOURCES

AUTHORITY_EXPLICIT_USER, AUTHORITY_OPERATOR, AUTHORITY_EXTRACTED, AUTHORITY_CONSOLIDATED, AUTHORITY_MIGRATED = (
    "explicit_user",
    "operator",
    "extracted",
    "consolidated",
    "migrated",
)
# Total order: lower rank wins conflicts. Humans (explicit_user == operator)
# strictly outrank machine authorities.
AUTHORITY_RANK = {
    AUTHORITY_EXPLICIT_USER: 0,
    AUTHORITY_OPERATOR: 0,
    AUTHORITY_EXTRACTED: 1,
    AUTHORITY_CONSOLIDATED: 2,
    AUTHORITY_MIGRATED: 3,
}
# Authority default when not provided: source maps to its authority.
DEFAULT_AUTHORITY = {
    SOURCE_USER_DECLARED: AUTHORITY_EXPLICIT_USER,
    SOURCE_EXTRACTED: AUTHORITY_EXTRACTED,
    SOURCE_CONSOLIDATED: AUTHORITY_CONSOLIDATED,
    SOURCE_MIGRATED: AUTHORITY_MIGRATED,
}
DEFAULT_CONFIDENCE = {
    SOURCE_USER_DECLARED: 0.95,
    SOURCE_EXTRACTED: 0.65,
    SOURCE_CONSOLIDATED: 0.5,
    SOURCE_MIGRATED: 0.5,
}
OPERATOR_CONFIDENCE = 1.0

STATUS_PENDING, STATUS_ACTIVE, STATUS_SUPERSEDED, STATUS_ARCHIVED, STATUS_DELETED = (
    "pending",
    "active",
    "superseded",
    "archived",
    "deleted",
)
RETRIEVABLE_STATUSES = (STATUS_ACTIVE,)

EVENT_STORED, EVENT_SUPERSEDED, EVENT_PROMOTED, EVENT_ARCHIVED, EVENT_DELETED, EVENT_EXPIRED, EVENT_CONFLICT, EVENT_RESTORED = (
    "stored",
    "superseded",
    "promoted",
    "archived",
    "deleted",
    "expired",
    "conflict_recorded",
    "restored",
)


class MemoryEntity(Base):
    __tablename__ = "memory_entities"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    domain = Column(String, nullable=False)
    statement = Column(Text, nullable=False)  # immutable once stored
    source = Column(String, nullable=False)
    authority = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)  # 0..1 — likelihood the claim is true
    importance = Column(Float, nullable=False, default=0.5)  # 0..1 — usefulness for future retrieval
    source_conversation_id = Column(
        String, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    content_hash = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default=STATUS_PENDING)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(String, nullable=True, index=True)
    conflicts_with_id = Column(String, nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # pgvector column. NOTE: `Vector.with_variant(JSON, "sqlite")` misbehaves
    # with SQLAlchemy 2.0.30 in practice (values bind as the literal string
    # "null"), so there is NO sqlite variant — the spec-sanctioned fallback:
    # tests rely on sqlite's lenient type names (VECTOR(n) columns store the
    # serialized vector as text; NULL-vs-value semantics stay correct) and
    # the service branches on dialect for cosine math instead.
    embedding = Column(Vector(settings.MEMORY_EMBEDDING_DIMENSION), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)

    def __init__(self, **kwargs):
        if not kwargs.get("id"):
            kwargs["id"] = f"mem-{uuid.uuid4().hex}"
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<MemoryEntity id={self.id} status={self.status} domain={self.domain}>"


class MemoryEvent(Base):
    """Append-only lifecycle audit trail. Insert-only; never updated."""

    __tablename__ = "memory_events"

    id = Column(Integer, primary_key=True, index=True)  # autoincrement, matches chat_messages style
    entity_id = Column(
        String, ForeignKey("memory_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=True)  # operator id / "system" / "legacy_import"
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)

    def __repr__(self) -> str:
        return f"<MemoryEvent id={self.id} entity={self.entity_id} type={self.event_type}>"