"""
Memory V2 service — scoped, governed memory with authority-aware conflict
resolution, append-only lifecycle events, and deterministic vector retrieval.

Conventions mirror `chat_persistence.py`: module-level functions taking
`(db, ...)`, ownership enforced in every query (user_id is ALWAYS the
authenticated identity — never client-supplied), business logic here, thin
routes elsewhere. All lifecycle events are appended to memory_events; the
statement of a memory is never mutated.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import safe_count
from app.models.memory import (
    AUTHORITY_CONSOLIDATED,
    AUTHORITY_EXTRACTED,
    AUTHORITY_MIGRATED,
    AUTHORITY_OPERATOR,
    AUTHORITY_RANK,
    DEFAULT_AUTHORITY,
    DEFAULT_CONFIDENCE,
    DOMAIN_EPISODIC,
    DOMAINS,
    EVENT_ARCHIVED,
    EVENT_CONFLICT,
    EVENT_DELETED,
    EVENT_EXPIRED,
    EVENT_PROMOTED,
    EVENT_RESTORED,
    EVENT_STORED,
    EVENT_SUPERSEDED,
    OPERATOR_CONFIDENCE,
    SOURCE_USER_DECLARED,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_DELETED,
    STATUS_PENDING,
    STATUS_SUPERSEDED,
    MemoryEntity,
    MemoryEvent,
)
from app.models.project import Project

logger = logging.getLogger(__name__)

# A batch-style embedder callable: texts -> vectors (provider contract).
Embed = Callable[[list[str]], list[list[float]]]

_UNSET = object()  # distinguishes "not provided" from explicit None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryConflictError(Exception):
    """Restore refused: a potential conflict candidate exists in the same
    scope. Carries the candidate ids; the entity was NOT activated."""

    def __init__(self, message: str, candidate_ids: list[str]) -> None:
        super().__init__(message)
        self.message = message
        self.candidate_ids = candidate_ids


class ProjectNotFoundError(ValueError):
    """Project reference is missing or not owned. Subclasses ValueError so
    existing callers mapping ValueError to an error still behave, while API
    layers can map this specifically to 404 (indistinguishable foreign vs
    missing — never an existence oracle)."""


@dataclass(frozen=True)
class MemoryHit:
    entity: MemoryEntity
    score: float


def _normalize(statement: str) -> str:
    """Same normalization semantics as the legacy store: lowercase, collapse
    whitespace. Empty after normalization → ValueError at creation."""
    return " ".join(statement.strip().lower().split())


def _content_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    # pgvector rows yield numpy.float32 elements — coerce to plain float.
    return float(dot / (na * nb))


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _dialect(db: Session) -> str:
    return db.get_bind().dialect.name


def _append_event(
    db: Session,
    entity: MemoryEntity,
    event_type: str,
    actor: str | None,
    note: str = "",
    metadata: Optional[dict] = None,
) -> None:
    db.add(
        MemoryEvent(
            entity_id=entity.id,
            event_type=event_type,
            actor=actor,
            note=note or None,
            metadata_=metadata or {},
        )
    )


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

def resolve_owned_project(db: Session, project_id: str, user_id: str) -> Project:
    """Resolve a project reference with ownership verification.

    The FK proves existence, never ownership — a foreign or missing project
    is indistinguishable to the caller (ProjectNotFoundError → 404 at the
    API layer).
    """
    if not project_id:
        raise ValueError("project_id is required")
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user_id:
        raise ProjectNotFoundError("project not found or not owned")
    return project


def _get_owned(db: Session, memory_id: str, user_id: str) -> MemoryEntity | None:
    return db.execute(
        select(MemoryEntity).where(
            MemoryEntity.id == memory_id,
            MemoryEntity.user_id == user_id,
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_memory(db: Session, memory_id: str, user_id: str) -> MemoryEntity | None:
    return _get_owned(db, memory_id, user_id)


def find_memory_by_statement(
    db: Session,
    user_id: str,
    statement: str,
    *,
    project_id: Optional[str] = None,
    statuses: tuple[str, ...] = (STATUS_ACTIVE,),
) -> MemoryEntity | None:
    """Exact normalized-statement match within the user's scope.

    Scope mirrors retrieval: a project context sees project memories plus
    user-wide memories; without a project, only user-wide memories. Returns
    the first deterministic match (created_at asc, id asc) or None.
    """
    normalized = _normalize(statement)
    if not normalized:
        return None
    q = select(MemoryEntity).where(
        MemoryEntity.user_id == user_id,
        MemoryEntity.status.in_(statuses),
    )
    if project_id is None:
        q = q.where(MemoryEntity.project_id.is_(None))
    else:
        q = q.where(or_(MemoryEntity.project_id == project_id, MemoryEntity.project_id.is_(None)))
    matches = [
        e
        for e in db.execute(q).scalars().all()
        if _normalize(e.statement) == normalized
    ]
    matches.sort(key=lambda e: (e.created_at if e.created_at is not None else datetime.min.replace(tzinfo=timezone.utc), e.id))
    return matches[0] if matches else None


def list_memories(
    db: Session,
    user_id: str,
    *,
    project_id: Optional[str] = None,
    domain: Optional[str] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[MemoryEntity]:
    q = select(MemoryEntity).where(MemoryEntity.user_id == user_id)
    if not include_deleted:
        q = q.where(MemoryEntity.status != STATUS_DELETED)
    if status is not None:
        q = q.where(MemoryEntity.status == status)
    if domain is not None:
        q = q.where(MemoryEntity.domain == domain)
    if project_id is not None:
        q = q.where(MemoryEntity.project_id == project_id)
    q = q.order_by(MemoryEntity.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(q).scalars().all())


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def create_memory(
    db: Session,
    *,
    user_id: str,
    statement: str,
    domain: str,
    source: str = SOURCE_USER_DECLARED,
    authority: Optional[str] = None,
    confidence: Optional[float] = None,
    importance: float = 0.5,
    project_id: Optional[str] = None,
    source_conversation_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    apply_domain_ttl: bool = True,
    metadata: Optional[dict] = None,
    now: Callable[[], datetime] = utc_now,
    embed: Optional[Embed] = None,
    extraction_run_id: Optional[str] = None,
) -> MemoryEntity:
    """Create a memory. Idempotent on identical (user, scope, statement);
    authority-aware potential-conflict handling per contract §5/§7.

    Observability (P2.1): when extraction_run_id is provided it is written
    into the entity metadata_ and the MemoryEvent metadata_ of this
    write's events, giving the full lineage
    extraction attempt -> entity -> events without a schema change.
    Outcome counters (memory_created/deduplicated/conflict/superseded)
    reflect ALL create_memory writes — the single chokepoint — and are
    documented in docs/v22_p2_observability_implementation.md."""
    normalized = _normalize(statement)
    if not normalized:
        raise ValueError("statement is required")
    if domain not in DOMAINS:
        raise ValueError(f"invalid domain: {domain!r}")

    # Ownership chain: project reference must belong to the user.
    if project_id is not None:
        resolve_owned_project(db, project_id, user_id)

    content_hash = _content_hash(normalized)

    # Dedupe: identical (user, scope, normalized) active/pending memory.
    dedupe_q = select(MemoryEntity).where(
        MemoryEntity.user_id == user_id,
        MemoryEntity.content_hash == content_hash,
        MemoryEntity.status.in_((STATUS_ACTIVE, STATUS_PENDING)),
    )
    if project_id is None:
        dedupe_q = dedupe_q.where(MemoryEntity.project_id.is_(None))
    else:
        dedupe_q = dedupe_q.where(MemoryEntity.project_id == project_id)
    existing = db.execute(dedupe_q).scalars().all()
    if existing:
        safe_count("memory_deduplicated_total")
        if extraction_run_id:
            logger.info(
                "memory_extraction_deduplicated",
                extra={
                    "event": "memory_extraction_deduplicated",
                    "run_id": extraction_run_id,
                    "entity": str(existing[0].id),
                    "status": existing[0].status,
                },
            )
        return existing[0]

    if authority is None:
        authority = DEFAULT_AUTHORITY[source]
    if authority not in AUTHORITY_RANK:
        raise ValueError(f"invalid authority: {authority!r}")
    if confidence is None:
        confidence = (
            OPERATOR_CONFIDENCE
            if authority == AUTHORITY_OPERATOR
            else DEFAULT_CONFIDENCE[source]
        )
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be within [0, 1]")
    if not 0.0 <= importance <= 1.0:
        raise ValueError("importance must be within [0, 1]")

    if apply_domain_ttl and expires_at is None and domain == DOMAIN_EPISODIC:
        expires_at = now() + timedelta(days=settings.MEMORY_EPISODIC_TTL_DAYS)

    entry_status = (
        STATUS_ACTIVE
        if source == SOURCE_USER_DECLARED or authority == AUTHORITY_OPERATOR
        else STATUS_PENDING
    )

    if extraction_run_id:
        metadata = {**(metadata or {}), "extraction_run_id": extraction_run_id}

    entity = MemoryEntity(
        user_id=user_id,
        project_id=project_id,
        domain=domain,
        statement=normalized,
        source=source,
        authority=authority,
        confidence=confidence,
        importance=importance,
        source_conversation_id=source_conversation_id,
        content_hash=content_hash,
        status=entry_status,
        expires_at=expires_at,
        metadata_=metadata or {},
    )
    db.add(entity)
    db.flush()

    supersede_target: MemoryEntity | None = None
    candidates = check_potential_conflicts(db, user_id, normalized, project_id=project_id, embed=embed)
    if candidates:
        first = candidates[0]
        if (
            AUTHORITY_RANK[authority] < AUTHORITY_RANK[first.authority]
            and confidence >= first.confidence
        ):
            supersede_target = first
        else:
            entity.status = STATUS_PENDING
            entity.conflicts_with_id = first.id

    if embed is not None:
        entity.embedding = embed([normalized])[0]

    event_metadata = {"extraction_run_id": extraction_run_id} if extraction_run_id else None

    if supersede_target is not None:
        supersede_target.status = STATUS_SUPERSEDED
        entity.supersedes_id = supersede_target.id
        _append_event(db, supersede_target, EVENT_SUPERSEDED, actor=user_id,
                      note=f"superseded by {entity.id}", metadata=event_metadata)
        safe_count("memory_superseded_total")

    _append_event(db, entity, EVENT_STORED, actor=user_id, metadata=event_metadata)
    if candidates and supersede_target is None:
        _append_event(db, entity, EVENT_CONFLICT, actor=user_id,
                      note=f"potential conflict candidate: {candidates[0].id}",
                      metadata=event_metadata)
        safe_count("memory_conflict_total")

    db.commit()
    db.refresh(entity)
    safe_count("memory_created_total", status=entry_status)
    return entity


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def promote_memory(
    db: Session,
    memory_id: str,
    user_id: str,
    actor: str,
    note: str = "",
) -> MemoryEntity:
    entity = _get_owned(db, memory_id, user_id)
    if entity is None:
        raise ValueError("memory not found or not owned")
    if entity.status != STATUS_PENDING:
        raise ValueError(f"invalid transition: {entity.status} -> active")
    entity.status = STATUS_ACTIVE
    _append_event(db, entity, EVENT_PROMOTED, actor=actor, note=note)
    db.commit()
    db.refresh(entity)
    return entity


def supersede_memory(
    db: Session,
    memory_id: str,
    user_id: str,
    actor: str,
    note: str = "",
) -> MemoryEntity:
    """Manual operator override: active -> superseded. Content preserved;
    no successor is created (supersedes_id/version untouched)."""
    entity = _get_owned(db, memory_id, user_id)
    if entity is None:
        raise ValueError("memory not found or not owned")
    if entity.status != STATUS_ACTIVE:
        raise ValueError(f"invalid transition: {entity.status} -> superseded")
    entity.status = STATUS_SUPERSEDED
    _append_event(db, entity, EVENT_SUPERSEDED, actor=actor, note=note)
    db.commit()
    db.refresh(entity)
    return entity


def archive_memory(
    db: Session,
    memory_id: str,
    user_id: str,
    actor: str,
    note: str = "",
) -> MemoryEntity:
    entity = _get_owned(db, memory_id, user_id)
    if entity is None:
        raise ValueError("memory not found or not owned")
    if entity.status not in (STATUS_ACTIVE, STATUS_SUPERSEDED):
        raise ValueError(f"invalid transition: {entity.status} -> archived")
    entity.status = STATUS_ARCHIVED
    _append_event(db, entity, EVENT_ARCHIVED, actor=actor, note=note)
    db.commit()
    db.refresh(entity)
    return entity


def delete_memory(
    db: Session,
    memory_id: str,
    user_id: str,
    actor: str,
    note: str = "",
    now: Callable[[], datetime] = utc_now,
) -> MemoryEntity:
    """Logical delete only: status=deleted + deleted_at. Row and events
    remain for audit; no physical purge in V2.1."""
    entity = _get_owned(db, memory_id, user_id)
    if entity is None:
        raise ValueError("memory not found or not owned")
    if entity.status == STATUS_DELETED:
        raise ValueError("invalid transition: deleted -> deleted")
    entity.status = STATUS_DELETED
    entity.deleted_at = now()
    _append_event(db, entity, EVENT_DELETED, actor=actor, note=note)
    db.commit()
    db.refresh(entity)
    return entity


def restore_memory(
    db: Session,
    memory_id: str,
    user_id: str,
    actor: str,
    note: str = "",
    embed: Optional[Embed] = None,
) -> MemoryEntity:
    """archived -> active (contract v0.2.1 §18). Operator-initiated only.

    Conflict-validated: a potential conflict candidate in the same scope
    REFUSES the restore (entity stays archived, MemoryConflictError, and a
    conflict_recorded event is appended). Never a conflicting pair of ACTIVE
    memories. expires_at is NOT cleared — an expired memory must have its
    expiry extended explicitly, or the retention sweeper re-archives it.
    """
    entity = _get_owned(db, memory_id, user_id)
    if entity is None:
        raise ValueError("memory not found or not owned")
    if entity.status != STATUS_ARCHIVED:
        raise ValueError(f"invalid transition: {entity.status} -> active")

    candidates = check_potential_conflicts(db, user_id, entity.statement,
                                           project_id=entity.project_id, embed=embed)
    if candidates:
        ids = [c.id for c in candidates]
        _append_event(db, entity, EVENT_CONFLICT, actor=actor,
                      note=f"restore refused, potential conflict candidates: {', '.join(ids)}")
        db.commit()
        raise MemoryConflictError(
            "restore refused: potential conflict candidates exist", candidate_ids=ids
        )

    entity.status = STATUS_ACTIVE
    _append_event(db, entity, EVENT_RESTORED, actor=actor, note=note)
    db.commit()
    db.refresh(entity)
    return entity


def update_memory_attributes(
    db: Session,
    memory_id: str,
    user_id: str,
    *,
    importance=_UNSET,
    expires_at=_UNSET,
    metadata=_UNSET,
) -> MemoryEntity:
    """Attribute-only updates. Never accepts statement/domain/status —
    those require supersede/transitions."""
    entity = _get_owned(db, memory_id, user_id)
    if entity is None:
        raise ValueError("memory not found or not owned")
    if importance is not _UNSET:
        if not 0.0 <= importance <= 1.0:
            raise ValueError("importance must be within [0, 1]")
        entity.importance = importance
    if expires_at is not _UNSET:
        entity.expires_at = expires_at  # explicit None clears the expiry
    if metadata is not _UNSET:
        entity.metadata_ = metadata or {}
    db.commit()
    db.refresh(entity)
    return entity


# ---------------------------------------------------------------------------
# Potential conflict candidates
# ---------------------------------------------------------------------------

def check_potential_conflicts(
    db: Session,
    user_id: str,
    statement: str,
    *,
    project_id: Optional[str] = None,
    embed: Optional[Embed] = None,
) -> list[MemoryEntity]:
    """ACTIVE memories in the same scope with cosine >= threshold.

    Candidates are semantically similar — NEVER proven contradictions
    (contradiction judgment is V2.2). Scope mirrors retrieval: a project
    context sees its project memories plus user-wide memories; without a
    project, only user-wide memories are in scope.
    """
    normalized = _normalize(statement)
    if not normalized or embed is None:
        return []

    q = select(MemoryEntity).where(
        MemoryEntity.user_id == user_id,
        MemoryEntity.status == STATUS_ACTIVE,
    )
    if project_id is None:
        q = q.where(MemoryEntity.project_id.is_(None))
    else:
        q = q.where(or_(MemoryEntity.project_id == project_id, MemoryEntity.project_id.is_(None)))

    query_vec = embed([normalized])[0]
    threshold = settings.MEMORY_CONFLICT_COSINE_THRESHOLD
    hits = []
    for entity in db.execute(q).scalars().all():
        if entity.embedding is None:
            continue
        similarity = _cosine(list(query_vec), list(entity.embedding))
        if similarity >= threshold:
            hits.append(entity)
    # Deterministic "first candidate" ordering.
    hits.sort(key=lambda e: (e.created_at if e.created_at is not None else datetime.min.replace(tzinfo=timezone.utc), e.id))
    return hits


# ---------------------------------------------------------------------------
# Search (vector-only; spec §8.3)
# ---------------------------------------------------------------------------

def _rank_score(cos: float, importance: float, created_at: datetime | None, now: datetime) -> float:
    half_life_days = settings.MEMORY_RECENCY_HALF_LIFE_DAYS
    if created_at is None:
        recency = 0.5
    else:
        days = max(0.0, (now - _as_utc(created_at)).total_seconds() / 86400.0)
        recency = 0.5 ** (days / half_life_days)
    return (
        settings.MEMORY_RANK_W_COSINE * cos
        + settings.MEMORY_RANK_W_IMPORTANCE * importance
        + settings.MEMORY_RANK_W_RECENCY * recency
    )


def search_memories(
    db: Session,
    user_id: str,
    query: str,
    *,
    project_id: Optional[str] = None,
    domains: Optional[list[str]] = None,
    k: int = 5,
    min_score: float = 0.0,
    max_tokens: Optional[int] = None,
    now: Callable[[], datetime] = utc_now,
    embed: Optional[Embed] = None,
) -> list[MemoryHit]:
    """Deterministic ranked retrieval. With provider 'none' (embed=None)
    search degrades to no candidates. A provided project_id must be owned
    by the user (ProjectNotFoundError otherwise — same posture as create)."""
    if project_id is not None:
        resolve_owned_project(db, project_id, user_id)
    if not query.strip() or embed is None:
        return []

    now_dt = now()
    filters = [
        MemoryEntity.user_id == user_id,
        MemoryEntity.status == STATUS_ACTIVE,
        or_(MemoryEntity.expires_at.is_(None), MemoryEntity.expires_at > now_dt),
    ]
    if project_id is None:
        filters.append(MemoryEntity.project_id.is_(None))
    else:
        filters.append(or_(MemoryEntity.project_id == project_id, MemoryEntity.project_id.is_(None)))
    if domains:
        filters.append(MemoryEntity.domain.in_(domains))

    filtered = lambda stmt: stmt.where(*filters)

    # 1. Embedding ensure: backfill candidate rows missing embeddings.
    batch = settings.MEMORY_EMBEDDING_BATCH_SIZE
    while True:
        missing = list(
            db.execute(
                filtered(select(MemoryEntity.id))
                .where(MemoryEntity.embedding.is_(None))
                .limit(batch)
            ).scalars().all()
        )
        if not missing:
            break
        rows = list(
            db.execute(
                filtered(select(MemoryEntity.id, MemoryEntity.statement))
                .where(MemoryEntity.id.in_(missing))
            ).all()
        )
        vectors = embed([r.statement for r in rows])
        for row, vec in zip(rows, vectors):
            db.execute(
                update(MemoryEntity).where(MemoryEntity.id == row.id).values(embedding=vec)
            )
        db.commit()

    cand_cap = max(50, k * 5)
    cols = (
        MemoryEntity.id,
        MemoryEntity.statement,
        MemoryEntity.embedding,
        MemoryEntity.importance,
        MemoryEntity.created_at,
        MemoryEntity.last_accessed_at,
    )
    query_vec = embed([query.strip()])[0]

    if _dialect(db) == "postgresql":
        dist_col = MemoryEntity.embedding.cosine_distance(query_vec).label("distance")
        stmt = (
            filtered(select(*cols, dist_col))
            .order_by(dist_col)
            .limit(cand_cap)
        )
        scored: list[tuple[float, MemoryEntity]] = []
        for row in db.execute(stmt).all():
            cos = max(0.0, 1.0 - float(row.distance))
            scored.append((cos, row))
    else:
        rows = db.execute(filtered(select(*cols))).all()
        scored = []
        for row in rows:
            # pgvector reads embeddings back as numpy arrays.
            embedding = list(row.embedding) if row.embedding is not None else []
            cos = _cosine(query_vec, embedding)
            scored.append((cos, row))

    ranked = sorted(
        (
            (
                _rank_score(cos, float(row.importance), row.created_at, now_dt),
                row,
            )
            for cos, row in scored
        ),
        # Deterministic: score desc, then created_at asc, then id asc.
        key=lambda pair: (
            -pair[0],
            pair[1].created_at if pair[1].created_at is not None else datetime.min.replace(tzinfo=timezone.utc),
            pair[1].id,
        ),
    )

    winners = [(score, row) for score, row in ranked if score >= min_score][:k]

    if max_tokens is not None:
        budget = max_tokens
        trimmed: list[tuple[float, object]] = []
        for score, row in winners:
            estimate = max(1, len(row.statement) // 4)
            if estimate > budget:
                break
            budget -= estimate
            trimmed.append((score, row))
        winners = trimmed

    ids = [row.id for _, row in winners]
    if not ids:
        return []

    # Throttled access tracking: only NULL or stale last_accessed_at, batched.
    threshold = timedelta(seconds=settings.MEMORY_ACCESS_UPDATE_THROTTLE_SECONDS)
    stale_ids = []
    for _, row in winners:
        last = _as_utc(row.last_accessed_at)
        if last is None or (now_dt - last) > threshold:
            stale_ids.append(row.id)
    if stale_ids:
        db.execute(
            update(MemoryEntity).where(MemoryEntity.id.in_(stale_ids)).values(last_accessed_at=now_dt)
        )
        db.commit()

    entities = {
        e.id: e
        for e in db.execute(select(MemoryEntity).where(MemoryEntity.id.in_(ids))).scalars().all()
    }
    return [MemoryHit(entity=entities[row.id], score=score) for score, row in winners if row.id in entities]


# ---------------------------------------------------------------------------
# Governance helpers
# ---------------------------------------------------------------------------

def archive_expired_memories(
    db: Session,
    *,
    now: Callable[[], datetime] = utc_now,
    limit: int = 1000,
) -> int:
    """Retention sweep: active + past expires_at -> archived + expired event.
    Never deletes."""
    now_dt = now()
    rows = list(
        db.execute(
            select(MemoryEntity)
            .where(
                MemoryEntity.status == STATUS_ACTIVE,
                MemoryEntity.expires_at.is_not(None),
                MemoryEntity.expires_at <= now_dt,
            )
            .limit(limit)
        ).scalars().all()
    )
    for entity in rows:
        entity.status = STATUS_ARCHIVED
        _append_event(db, entity, EVENT_EXPIRED, actor="system", note="expires_at reached")
    if rows:
        db.commit()
    return len(rows)