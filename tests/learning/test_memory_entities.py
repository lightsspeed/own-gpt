"""Memory V2 service-level tests (deterministic, sqlite, no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.memory import (
    AUTHORITY_EXPLICIT_USER,
    AUTHORITY_MIGRATED,
    DOMAIN_EPISODIC,
    DOMAIN_SEMANTIC,
    EVENT_ARCHIVED,
    EVENT_CONFLICT,
    EVENT_DELETED,
    EVENT_PROMOTED,
    EVENT_RESTORED,
    EVENT_STORED,
    EVENT_SUPERSEDED,
    SOURCE_CONSOLIDATED,
    SOURCE_EXTRACTED,
    SOURCE_MIGRATED,
    SOURCE_USER_DECLARED,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_SUPERSEDED,
    MemoryEntity,
    MemoryEvent,
)
from app.models.project import Project
from app.services import auth, memory as mem

FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def utc_now_fixed() -> datetime:
    return FIXED_NOW


def fake_embedder(texts):
    """Deterministic bag-of-words embeddings — shared tokens → high cosine.

    Zero-padded to MEMORY_EMBEDDING_DIMENSION because the pgvector column
    validates the bound dimension; padding does not change cosine values.
    """
    vocab = ("user", "name", "alice", "prefers", "postgresql", "uses", "python",
             "project", "concise", "answers", "today", "gpt4o", "met", "work", "on")
    dim = 1536  # = settings.MEMORY_EMBEDDING_DIMENSION (test default)
    vectors = []
    for text in texts:
        active = [1.0 if token in text.lower() else 0.0 for token in vocab]
        norm = sum(x * x for x in active) ** 0.5 or 1.0
        normalized = [x / norm for x in active]
        vectors.append(normalized + [0.0] * (dim - len(normalized)))
    return vectors


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
def other_user(db):
    return auth.create_user(db, "bob", "password123")


def _as_utc_naive(dt) -> datetime:
    """Normalize sqlite's naive DATETIME back to an aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _events(db, entity_id: str) -> list[str]:
    return list(
        db.execute(
            select(MemoryEvent.event_type)
            .where(MemoryEvent.entity_id == entity_id)
            .order_by(MemoryEvent.id.asc())
        ).scalars()
    )


# ── 1. Create defaults ──────────────────────────────────────────────────

def test_create_user_declared_defaults(db, user):
    entity = mem.create_memory(
        db, user_id=user.id, statement="User prefers concise answers", domain=DOMAIN_SEMANTIC,
        now=utc_now_fixed, embed=fake_embedder,
    )
    assert entity.status == STATUS_ACTIVE
    assert entity.authority == AUTHORITY_EXPLICIT_USER
    assert entity.confidence == 0.95
    assert entity.version == 1
    assert entity.source == SOURCE_USER_DECLARED
    assert entity.importance == 0.5
    assert _events(db, entity.id) == [EVENT_STORED]


# ── 2/3. Dedupe + normalization ─────────────────────────────────────────

def test_dedupe_and_normalization(db, user):
    e1 = mem.create_memory(db, user_id=user.id, statement="  User   prefers Concise answers ",
                           domain=DOMAIN_SEMANTIC)
    e2 = mem.create_memory(db, user_id=user.id, statement="user prefers concise answers",
                           domain=DOMAIN_SEMANTIC)
    assert e1.id == e2.id
    assert e1.statement == "user prefers concise answers"
    rows = db.execute(select(MemoryEntity)).scalars().all()
    assert len(rows) == 1


def test_empty_statement_rejected(db, user):
    with pytest.raises(ValueError):
        mem.create_memory(db, user_id=user.id, statement="   ", domain=DOMAIN_SEMANTIC)


# ── 4. Scoping ──────────────────────────────────────────────────────────

def _owned_project(db, owner_id: str, name: str = "proj") -> Project:
    p = Project(owner_id=owner_id, name=name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_user_and_project_isolation(db, user, other_user):
    proj_a = _owned_project(db, user.id, "a")
    proj_b = _owned_project(db, user.id, "b")
    mem.create_memory(db, user_id=user.id, statement="user's name is alice", domain=DOMAIN_SEMANTIC,
                      project_id=proj_a.id)
    mem.create_memory(db, user_id=user.id, statement="works on python project", domain=DOMAIN_SEMANTIC,
                      project_id=proj_b.id)
    mem.create_memory(db, user_id=user.id, statement="prefers postgresql", domain=DOMAIN_SEMANTIC)

    # User isolation
    assert mem.list_memories(db, other_user.id) == []
    assert mem.get_memory(db, list(mem.list_memories(db, user.id))[0].id, other_user.id) is None

    # Project isolation: project memory invisible outside its project.
    proj_a_ids = {e.id for e in mem.list_memories(db, user.id, project_id=proj_a.id)}
    assert "user's name is alice" in {e.statement for e in mem.list_memories(db, user.id, project_id=proj_a.id)}
    assert all(e.statement == "user's name is alice" or e.project_id is None
               for e in mem.list_memories(db, user.id, project_id=proj_a.id))


def test_user_wide_visible_in_project_context(db, user):
    proj = _owned_project(db, user.id)
    mem.create_memory(db, user_id=user.id, statement="user's name is alice", domain=DOMAIN_SEMANTIC)
    mem.create_memory(db, user_id=user.id, statement="works on python project", domain=DOMAIN_SEMANTIC,
                      project_id=proj.id)
    hits = mem.search_memories(db, user.id, "alice", project_id=proj.id, k=10, embed=fake_embedder)
    statements = {h.entity.statement for h in hits}
    assert "user's name is alice" in statements          # user-wide visible in project context
    assert "works on python project" in statements       # project memory visible in its context
    in_context = mem.search_memories(db, user.id, "python project", project_id=proj.id,
                                     k=10, embed=fake_embedder)
    assert "works on python project" in {h.entity.statement for h in in_context}
    outside = mem.search_memories(db, user.id, "python project", k=10, embed=fake_embedder)
    # Project memory must NOT be visible user-wide.
    assert all(h.entity.statement != "works on python project" for h in outside)


# ── 5. Authority defaults per source ────────────────────────────────────

def test_authority_defaults_per_source(db, user):
    cases = {
        SOURCE_USER_DECLARED: (AUTHORITY_EXPLICIT_USER, 0.95),
        SOURCE_EXTRACTED: ("extracted", 0.65),
        SOURCE_CONSOLIDATED: ("consolidated", 0.5),
        SOURCE_MIGRATED: (AUTHORITY_MIGRATED, 0.5),
    }
    for source, (authority, confidence) in cases.items():
        e = mem.create_memory(db, user_id=user.id, statement=f"fact from {source} source",
                              domain=DOMAIN_SEMANTIC, source=source, now=utc_now_fixed)
        assert e.authority == authority, source
        assert e.confidence == confidence, source


def test_operator_authority_default_confidence(db, user):
    e = mem.create_memory(db, user_id=user.id, statement="operator fact", domain=DOMAIN_SEMANTIC,
                          source=SOURCE_USER_DECLARED, authority="operator", now=utc_now_fixed)
    assert e.confidence == 1.0
    assert e.status == STATUS_ACTIVE


def test_extracted_source_enters_pending(db, user):
    e = mem.create_memory(db, user_id=user.id, statement="extracted claim", domain=DOMAIN_SEMANTIC,
                          source=SOURCE_EXTRACTED, now=utc_now_fixed)
    assert e.status == "pending"


# ── 6. Potential conflict ladder ────────────────────────────────────────

def test_conflict_weaker_authority_becomes_pending(db, user):
    mem.create_memory(db, user_id=user.id, statement="user's name is alice", domain=DOMAIN_SEMANTIC,
                      now=utc_now_fixed, embed=fake_embedder)
    new = mem.create_memory(db, user_id=user.id, statement="user's full name is alice smith",
                            domain=DOMAIN_SEMANTIC, source=SOURCE_EXTRACTED,
                            now=utc_now_fixed, embed=fake_embedder)
    assert new.status == "pending"
    assert new.conflicts_with_id is not None
    assert EVENT_CONFLICT in _events(db, new.id)


def test_conflict_equal_authority_becomes_pending(db, user):
    first = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                              domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    second = mem.create_memory(db, user_id=user.id, statement="user's full name is alice smith",
                               domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    assert second.status == "pending"
    assert second.conflicts_with_id == first.id
    assert first.status == STATUS_ACTIVE


def test_conflict_higher_authority_supersedes(db, user):
    old = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                            domain=DOMAIN_SEMANTIC, source=SOURCE_EXTRACTED,
                            now=utc_now_fixed, embed=fake_embedder)
    old = mem.promote_memory(db, old.id, user.id, actor=user.id)
    assert old.status == STATUS_ACTIVE

    new = mem.create_memory(db, user_id=user.id, statement="user's full name is alice smith",
                            domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    assert new.status == STATUS_ACTIVE
    assert new.supersedes_id == old.id
    fresh_old = mem.get_memory(db, old.id, user.id)
    assert fresh_old.status == STATUS_SUPERSEDED
    assert EVENT_SUPERSEDED in _events(db, old.id)
    assert EVENT_STORED in _events(db, new.id)


def test_conflict_weaker_confidence_pending(db, user):
    strong = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                               domain=DOMAIN_SEMANTIC, source=SOURCE_EXTRACTED,
                               now=utc_now_fixed, embed=fake_embedder)
    mem.promote_memory(db, strong.id, user.id, actor=user.id)
    weak = mem.create_memory(db, user_id=user.id, statement="user's full name is alice smith",
                             domain=DOMAIN_SEMANTIC, source=SOURCE_EXTRACTED, confidence=0.3,
                             now=utc_now_fixed, embed=fake_embedder)
    assert weak.status == "pending"
    assert weak.conflicts_with_id == strong.id


def test_high_cosine_is_candidate_not_contradiction(db, user):
    # 'daily' is not in the vocabulary so both statements share every token
    # (cosine 1.0) while asserting no contradiction between them.
    mem.create_memory(db, user_id=user.id, statement="user uses postgresql",
                      domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    candidates = mem.check_potential_conflicts(
        db, user.id, "user uses postgresql daily", embed=fake_embedder
    )
    # High similarity — returned as a *candidate*, never claimed contradictory.
    assert len(candidates) == 1
    assert candidates[0].statement == "user uses postgresql"


# ── 7. Transitions ──────────────────────────────────────────────────────

def test_promote_only_from_pending(db, user):
    e = mem.create_memory(db, user_id=user.id, statement="promotable claim",
                          domain=DOMAIN_SEMANTIC, source=SOURCE_EXTRACTED)
    e = mem.promote_memory(db, e.id, user.id, actor=user.id, note="approved")
    assert e.status == STATUS_ACTIVE
    assert EVENT_PROMOTED in _events(db, e.id)
    with pytest.raises(ValueError):
        mem.promote_memory(db, e.id, user.id, actor=user.id)


def test_manual_supersede_preserves_content(db, user):
    e = mem.create_memory(db, user_id=user.id, statement="user's name is alice", domain=DOMAIN_SEMANTIC)
    version_before = e.version
    statement_before = e.statement
    e = mem.supersede_memory(db, e.id, user.id, actor=user.id)
    assert e.status == STATUS_SUPERSEDED
    assert e.statement == statement_before
    assert e.version == version_before  # manual supersede has no successor
    assert EVENT_SUPERSEDED in _events(db, e.id)


def test_archive_and_delete_require_owned(db, user, other_user):
    e = mem.create_memory(db, user_id=user.id, statement="user's name is alice", domain=DOMAIN_SEMANTIC)
    with pytest.raises(ValueError):
        mem.archive_memory(db, e.id, other_user.id, actor=other_user.id)
    e = mem.archive_memory(db, e.id, user.id, actor=user.id)
    assert e.status == STATUS_ARCHIVED
    assert EVENT_ARCHIVED in _events(db, e.id)
    e = mem.delete_memory(db, e.id, user.id, actor=user.id, now=utc_now_fixed)
    assert e.status == "deleted"
    # sqlite strips tzinfo on DATETIME columns — normalize before comparing.
    assert _as_utc_naive(e.deleted_at) == FIXED_NOW
    assert EVENT_DELETED in _events(db, e.id)


def test_restore_ok_and_conflict_refused(db, user):
    target = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                               domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    mem.archive_memory(db, target.id, user.id, actor=user.id)

    # Activate a similar statement first so the restore has an ACTIVE candidate.
    mem.create_memory(db, user_id=user.id, statement="user's full name is alice smith",
                      domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)

    with pytest.raises(mem.MemoryConflictError) as excinfo:
        mem.restore_memory(db, target.id, user.id, actor=user.id, embed=fake_embedder)
    assert len(excinfo.value.candidate_ids) == 1
    still = mem.get_memory(db, target.id, user.id)
    assert still.status == STATUS_ARCHIVED  # never blind activation
    assert EVENT_CONFLICT in _events(db, target.id)

    # Remove the only candidate (delete user-wide memory B) → restore succeeds.
    blocker = mem.search_memories(db, user.id, "alice", k=10, now=utc_now_fixed, embed=fake_embedder)
    assert len(blocker) == 1
    mem.delete_memory(db, blocker[0].entity.id, user.id, actor=user.id)
    restored = mem.restore_memory(db, target.id, user.id, actor=user.id, embed=fake_embedder)
    assert restored.status == STATUS_ACTIVE
    assert EVENT_RESTORED in _events(db, target.id)


def test_logical_delete_removes_from_list_and_search(db, user):
    e = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                          domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    mem.delete_memory(db, e.id, user.id, actor=user.id, now=utc_now_fixed)
    assert mem.list_memories(db, user.id) == []
    assert mem.search_memories(db, user.id, "alice", k=10, now=utc_now_fixed, embed=fake_embedder) == []
    # Row + events remain for audit (logical deletion).
    assert db.get(MemoryEntity, e.id) is not None


# ── 8. Episodic TTL ─────────────────────────────────────────────────────

def test_episodic_ttl_default(db, user):
    episodic = mem.create_memory(db, user_id=user.id, statement="met gpt4o today",
                                 domain=DOMAIN_EPISODIC, now=utc_now_fixed)
    assert _as_utc_naive(episodic.expires_at) == FIXED_NOW + timedelta(days=90)
    durable = mem.create_memory(db, user_id=user.id, statement="met gpt4o yesterday",
                                domain=DOMAIN_EPISODIC, apply_domain_ttl=False, now=utc_now_fixed)
    assert durable.expires_at is None
    semantic = mem.create_memory(db, user_id=user.id, statement="works on python project",
                                 domain=DOMAIN_SEMANTIC, now=utc_now_fixed)
    assert semantic.expires_at is None


# ── 9. Expiry sweeper ───────────────────────────────────────────────────

def test_expiry_sweeper_archives_and_keeps_durable(db, user):
    expired = mem.create_memory(db, user_id=user.id, statement="episodic old memory",
                                domain=DOMAIN_EPISODIC, now=utc_now_fixed)
    durable = mem.create_memory(db, user_id=user.id, statement="works on python project",
                                domain=DOMAIN_SEMANTIC)
    archived = mem.archive_expired_memories(
        db, now=lambda: FIXED_NOW + timedelta(days=91)
    )
    assert archived == 1
    fresh = mem.get_memory(db, expired.id, user.id)
    assert fresh.status == STATUS_ARCHIVED
    assert "expired" in _events(db, expired.id)
    assert mem.get_memory(db, durable.id, user.id).status == STATUS_ACTIVE


# ── 10/11. Search pipeline ──────────────────────────────────────────────

def test_search_ranking_and_filters(db, user):
    names = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                              domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    mem.create_memory(db, user_id=user.id, statement="works on a python project",
                      domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    stale = mem.create_memory(db, user_id=user.id, statement="user's name is alice when young",
                              domain=DOMAIN_SEMANTIC, source=SOURCE_EXTRACTED,
                              now=utc_now_fixed, embed=fake_embedder)
    mem.promote_memory(db, stale.id, user.id, actor=user.id)  # pending -> active first
    mem.archive_memory(db, stale.id, user.id, actor=user.id)

    hits = mem.search_memories(db, user.id, "what is the user's name?",
                               k=5, now=utc_now_fixed, embed=fake_embedder)
    assert hits[0].entity.id == names.id                      # top hit first
    assert names.statement in {h.entity.statement for h in hits}
    assert all(h.entity.status == STATUS_ACTIVE for h in hits)  # archived excluded
    assert len(hits) >= 1

    hits = mem.search_memories(db, user.id, "alice", k=5, min_score=0.9,
                               now=utc_now_fixed, embed=fake_embedder)
    for h in hits:
        assert h.score >= 0.9

    domain_hits = mem.search_memories(db, user.id, "alice", k=5, domains=[DOMAIN_EPISODIC],
                                      now=utc_now_fixed, embed=fake_embedder)
    assert domain_hits == []


def test_search_k_cap_and_max_tokens(db, user):
    stmt_a = " ".join(["aaa"] * 40)   # 160 chars -> ~40 tokens
    stmt_b = " ".join(["bbb"] * 40)
    mem.create_memory(db, user_id=user.id, statement=stmt_a, domain=DOMAIN_SEMANTIC,
                      now=utc_now_fixed)
    mem.create_memory(db, user_id=user.id, statement=stmt_b, domain=DOMAIN_SEMANTIC,
                      now=utc_now_fixed)

    all_hits = mem.search_memories(db, user.id, "anything", k=10,
                                   now=utc_now_fixed, embed=fake_embedder)
    assert len(all_hits) == 2

    capped = mem.search_memories(db, user.id, "anything", k=1,
                                 now=utc_now_fixed, embed=fake_embedder)
    assert len(capped) == 1

    token_limited = mem.search_memories(db, user.id, "anything", k=10, max_tokens=40,
                                        now=utc_now_fixed, embed=fake_embedder)
    assert len(token_limited) == 1


def test_search_lazy_embedding_backfill(db, user):
    mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                      domain=DOMAIN_SEMANTIC, now=utc_now_fixed)  # no embed at creation
    calls: list[list[str]] = []

    def counting_embedder(texts):
        calls.append(list(texts))
        return fake_embedder(texts)

    hits = mem.search_memories(db, user.id, "alice", k=5, now=utc_now_fixed, embed=counting_embedder)
    assert len(hits) == 1
    assert any("user's name is alice" in batch for batch in calls)  # backfilled via embedder
    row = db.get(MemoryEntity, hits[0].entity.id)
    assert row.embedding is not None


def test_search_access_tracking_throttled_and_batched(db, user):
    m1 = mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                           domain=DOMAIN_SEMANTIC, now=utc_now_fixed, embed=fake_embedder)
    t0 = FIXED_NOW
    mem.search_memories(db, user.id, "alice", k=5, now=lambda: t0, embed=fake_embedder)
    assert db.get(MemoryEntity, m1.id).last_accessed_at == t0

    # Within the throttle window (30 min < 3600s) -> NOT updated.
    mem.search_memories(db, user.id, "alice", k=5,
                        now=lambda: t0 + timedelta(minutes=30), embed=fake_embedder)
    assert db.get(MemoryEntity, m1.id).last_accessed_at == t0

    # Past the window -> updated.
    later = t0 + timedelta(hours=2)
    mem.search_memories(db, user.id, "alice", k=5, now=lambda: later, embed=fake_embedder)
    assert db.get(MemoryEntity, m1.id).last_accessed_at == later

    # Provider 'none': embed=None degrades to no candidates.
    assert mem.search_memories(db, user.id, "alice", k=5, now=utc_now_fixed, embed=None) == []


# ── 12. Attribute update ────────────────────────────────────────────────

def test_attribute_update_only(db, user):
    e = mem.create_memory(db, user_id=user.id, statement="works on python project",
                          domain=DOMAIN_SEMANTIC, now=utc_now_fixed)
    e = mem.update_memory_attributes(db, e.id, user.id, importance=0.9,
                                     expires_at=None, metadata={"note": "x"})
    assert e.importance == 0.9
    assert e.expires_at is None          # explicit None clears expiry
    assert e.metadata_ == {"note": "x"}
    assert e.statement == "works on python project"  # content untouched

    with pytest.raises(ValueError):
        mem.update_memory_attributes(db, e.id, user.id, importance=1.5)
    with pytest.raises(TypeError):
        mem.update_memory_attributes(db, e.id, user.id, statement="hacked")  # no such param


def test_project_ownership_enforced(db, user, other_user):
    proj = _owned_project(db, other_user.id, "bobs")
    with pytest.raises(mem.ProjectNotFoundError):
        mem.create_memory(db, user_id=user.id, statement="user's name is alice",
                          domain=DOMAIN_SEMANTIC, project_id=proj.id)
    with pytest.raises(mem.ProjectNotFoundError):
        mem.resolve_owned_project(db, "missing-project", user.id)
    with pytest.raises(mem.ProjectNotFoundError):
        mem.search_memories(db, user.id, "alice", project_id=proj.id, embed=fake_embedder)
    with pytest.raises(mem.ProjectNotFoundError):
        mem.search_memories(db, user.id, "alice", project_id="missing-project", embed=fake_embedder)