# OwnGPT Memory V2.1 — Implementation Specification

**Status:** Finalized (2026-08-14, post pre-flight amendments). Storage wiring superseded by V2.2 (agent recall node + tools + extraction route through the V2.1 `MemoryService`; see `docs/v22_memory_intelligence_spec.md`). This document remains normative for the store itself: schema, lifecycle, retrieval.

**Normative reference:** `docs/memory_contract.md` — Memory Contract v0.2 (frozen). Where this spec and the contract disagree, **the contract wins**; surface the conflict instead of improvising.

**Scope:** V2.1 = memory storage + governance. Schema, projects, lifecycle, CRUD, retrieval primitives. NO extraction pipeline (V2.2), NO hybrid retrieval (V2.5), NO Context Engine, NO UI.

---

## 1. Mission

Build the durable, governed memory store: Postgres tables + pgvector embeddings, user/project scoping, authority-aware conflict resolution, append-only lifecycle events, logical-delete semantics, vector retrieval with deterministic ranking, thin operator API, and a legacy JSON-store import path. Everything is service-layer; API routes stay thin; nothing in V1.1 behavior changes.

---

## 2. Pre-flight inspection checklist (read before writing code)

| File | What to absorb |
|---|---|
| `app/core/database.py` | `Base`, `get_sync_db()`, `SyncSessionLocal` — sync sessions everywhere for memory |
| `app/core/migrations.py` | `_MIGRATIONS: list[(name, [sql...])]` pattern; idempotent `IF NOT EXISTS`; appends new migrations, never edits applied ones |
| `app/models/chat.py` | Column-based declarative style; VARCHAR string ids (`uuid4` hex), not UUID columns; `DateTime(timezone=True)` |
| `app/models/user.py` | FK pattern with `ondelete="CASCADE"` |
| `app/services/chat_persistence.py` | Service conventions: module-level functions taking `(db, ...)`, ownership enforced in the SQL WHERE clause, module-level status constants |
| `app/api/deps.py` | `get_current_user`, `api_error(status, code, message)` |
| `app/api/endpoints/chat.py` | Thin-route pattern, `{"error": {"code", "message"}}` envelope, `except HTTPException: raise` |
| `app/core/config.py` | `Settings(BaseSettings)` with defaults; env-driven |
| `app/learning/operations/memory.py` | Legacy store semantics to mirror: `_normalize` (lowercase + whitespace collapse), idempotent dedupe, append-only events, supersede-without-rewrite |
| `app/learning/automation/models.py`, `scheduler.py` | `JobType` enum, `ScheduleDef`/`DEFAULT_SCHEDULES` for the retention job |
| `app/learning/architecture/capabilities.py` | `register(Capability(...))` pattern |
| `app/main.py` | Router wiring + `lifespan` (migrations already run there) |
| `tests/chat/conftest.py` | sqlite `test_engine` (StaticPool) + `Base.metadata.create_all`; `client` fixture with `get_sync_db` override; hermetic fake pattern |
| `tests/learning/test_memory.py` | Deterministic fake embedder pattern (bag-of-words) — reuse it |

---

## 3. Architecture invariants (must preserve)

1. Artifacts immutable, append-only. Never UPDATE statement/content of a memory; transitions append events and flip status.
2. Ownership enforced in SQL: every memory/project query filters `user_id`; never trust client ids alone.
3. Business logic in services; routes thin; persistence isolated (no ORM in endpoints).
4. No direct LLM writes to `memory_entities` (extraction is V2.2; the only writers are the service API and operator endpoints).
5. Deterministic tests: inject clocks (`now` callable) and embedders; no `datetime.now()` in services without injection, no sleep-based tests.
6. Logs are operational, not the system of record — lifecycle truth lives in `memory_events`.
7. Ownership chain invariant: `Project.owner_id == ChatSession.owner_id == MemoryEntity.user_id`. Every `project_id` reference is resolved and ownership-verified before use — never rely on the FK alone, and never trust a client-supplied `user_id` (identity always comes from `get_current_user`).

---

## 4. New settings (`app/core/config.py`)

```python
# Memory V2
MEMORY_EMBEDDING_PROVIDER: str = "openai"     # "openai" | "none"
MEMORY_EMBEDDING_MODEL: str = "text-embedding-3-small"
MEMORY_EMBEDDING_DIMENSION: int = 1536        # deployment-pinned; change = new migration
MEMORY_EPISODIC_TTL_DAYS: int = 90
MEMORY_CONFLICT_COSINE_THRESHOLD: float = 0.85
MEMORY_RANK_W_COSINE: float = 0.6
MEMORY_RANK_W_IMPORTANCE: float = 0.25
MEMORY_RANK_W_RECENCY: float = 0.15
MEMORY_RECENCY_HALF_LIFE_DAYS: float = 30.0
MEMORY_EMBEDDING_BATCH_SIZE: int = 64
MEMORY_ACCESS_UPDATE_THROTTLE_SECONDS: int = 3600
```

Note: `MEMORY_EMBEDDING_DIMENSION` is consumed by both the model column and migration m004. Changing it after deployment is an embedding re-index migration (new migration number), not a config tweak — document this in a comment next to the setting.

---

## 5. New models

### 5.1 `app/models/project.py` — `Project`

```python
class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, index=True)          # uuid4 hex
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)  # SQLAlchemy reserves `metadata`
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### 5.2 `app/models/memory.py` — `MemoryEntity` + `MemoryEvent` + constants

Constants live here (mirror `chat_persistence` convention of module-level constants):

```python
DOMAIN_SEMANTIC, DOMAIN_EPISODIC, DOMAIN_PREFERENCE, DOMAIN_PROCEDURAL = "semantic", "episodic", "preference", "procedural"
SOURCE_USER_DECLARED, SOURCE_EXTRACTED, SOURCE_CONSOLIDATED, SOURCE_MIGRATED = "user_declared", "extracted", "consolidated", "migrated"
AUTHORITY_EXPLICIT_USER, AUTHORITY_OPERATOR, AUTHORITY_EXTRACTED, AUTHORITY_CONSOLIDATED, AUTHORITY_MIGRATED = "explicit_user", "operator", "extracted", "consolidated", "migrated"
AUTHORITY_RANK = {"explicit_user": 0, "operator": 0, "extracted": 1, "consolidated": 2, "migrated": 3}
STATUS_PENDING, STATUS_ACTIVE, STATUS_SUPERSEDED, STATUS_ARCHIVED, STATUS_DELETED = "pending", "active", "superseded", "archived", "deleted"
RETRIEVABLE_STATUSES = (STATUS_ACTIVE,)
EVENT_STORED, EVENT_SUPERSEDED, EVENT_PROMOTED, EVENT_ARCHIVED, EVENT_DELETED, EVENT_EXPIRED, EVENT_CONFLICT, EVENT_RESTORED = "stored", "superseded", "promoted", "archived", "deleted", "expired", "conflict_recorded", "restored"
```

```python
class MemoryEntity(Base):
    __tablename__ = "memory_entities"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    domain = Column(String, nullable=False)
    statement = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    authority = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)                # 0..1
    importance = Column(Float, nullable=False, default=0.5)   # 0..1
    source_conversation_id = Column(String, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)
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
    embedding = Column(Vector(settings.MEMORY_EMBEDDING_DIMENSION).with_variant(JSON, "sqlite"), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
```

`Vector` comes from `pgvector.sqlalchemy`. The `with_variant(JSON, "sqlite")` keeps `Base.metadata.create_all` working on the sqlite test engine. **SQLite via `with_variant` is test persistence compatibility only — SQLite is NOT a production memory backend** (production is Postgres + pgvector). If `Vector.with_variant` misbehaves with SQLAlchemy 2.0.30 in practice, fall back to a plain `JSON` column + dialect branching in the service, and note it in the PR.

```python
class MemoryEvent(Base):
    """Append-only lifecycle audit trail. Insert-only; never updated."""
    __tablename__ = "memory_events"
    id = Column(Integer, primary_key=True, index=True)  # autoincrement, matches chat_messages style
    entity_id = Column(String, ForeignKey("memory_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=True)               # operator id / "system" / "legacy_import"
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
```

---

## 6. Migrations (`app/core/migrations.py` — append, never edit m001–m003)

**Schema-evolution reality (verified in pre-flight):** the repository has no Alembic installation (`alembic.ini` and `alembic/` do not exist). Current mechanism = `Base.metadata.create_all` at startup (handles brand-new tables, `app/main.py` lifespan) followed by the idempotent `run_migrations` runner. V2.1 does NOT introduce Alembic and does NOT add create_all behavior — new models are created empty by the existing startup `create_all` on fresh DBs, then evolved by idempotent migrations (same as m001–m003). **Migration to Alembic-owned schema evolution is tracked separately and is out of V2.1 scope.**

**m004_memory_v2** (idempotent, Postgres-only):

```sql
CREATE EXTENSION IF NOT EXISTS vector

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR PRIMARY KEY,
    owner_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    description TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
)
CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects (owner_id)

CREATE TABLE IF NOT EXISTS memory_entities (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id VARCHAR REFERENCES projects(id) ON DELETE CASCADE,
    domain VARCHAR NOT NULL,
    statement TEXT NOT NULL,
    source VARCHAR NOT NULL,
    authority VARCHAR NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    importance DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    source_conversation_id VARCHAR REFERENCES chat_sessions(id) ON DELETE SET NULL,
    content_hash VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending',
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id VARCHAR,
    conflicts_with_id VARCHAR,
    expires_at TIMESTAMPTZ,
    last_accessed_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    embedding vector({settings.MEMORY_EMBEDDING_DIMENSION}),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
)
CREATE INDEX IF NOT EXISTS ix_memory_entities_user_status ON memory_entities (user_id, status)
CREATE INDEX IF NOT EXISTS ix_memory_entities_project ON memory_entities (project_id)
CREATE INDEX IF NOT EXISTS ix_memory_entities_expires ON memory_entities (expires_at)
CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_entities_dedupe
    ON memory_entities (user_id, COALESCE(project_id, ''), content_hash)
    WHERE status IN ('active', 'pending')
CREATE INDEX IF NOT EXISTS ix_memory_entities_embedding
    ON memory_entities USING hnsw (embedding vector_cosine_ops)

CREATE TABLE IF NOT EXISTS memory_events (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR NOT NULL REFERENCES memory_entities(id) ON DELETE CASCADE,
    event_type VARCHAR NOT NULL,
    actor VARCHAR,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
)
CREATE INDEX IF NOT EXISTS ix_memory_events_entity ON memory_events (entity_id)
```

The `vector({...})` dimension is f-string interpolated from `settings.MEMORY_EMBEDDING_DIMENSION` at migration-definition time (same value the model column uses — keep them in lockstep).

**m005_chat_session_project**:

```sql
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS project_id VARCHAR REFERENCES projects(id) ON DELETE SET NULL
CREATE INDEX IF NOT EXISTS ix_chat_sessions_project_id ON chat_sessions (project_id)
```

`ON DELETE SET NULL` — deleting a project never deletes conversations; deleting a user's project may cascade *memories* only if the operator explicitly deletes the project.

---

## 7. Embedding provider (`app/services/embeddings.py`)

```python
class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class OpenAIEmbeddingProvider:
    """Wraps langchain_openai.OpenAIEmbeddings(model=settings.MEMORY_EMBEDDING_MODEL)."""

def get_embedding_provider() -> EmbeddingProvider | None:
    """None when MEMORY_EMBEDDING_PROVIDER == 'none' (search degrades to no candidates)."""
```

- Never hard-wire `OpenAIEmbeddings` inside the memory repository — only through this interface.
- No other providers in V2.1; the registry pattern (`openai | none`) is the extension point.
- Expose it as a FastAPI dependency (`app/api/deps.py` addition) so endpoints can override it in tests.

---

## 8. Memory service (`app/services/memory.py`)

Function-based, mirroring `chat_persistence.py`. Ownership enforced in every query.

**Definitions (contract §2/§5):** `confidence` = likelihood that the memory claim is true; `importance` = usefulness/relevance of the memory for future retrieval. They are independent — a confident claim ("I like Python", confidence 0.95) can be less important than a confident project fact ("OwnGPT production uses PostgreSQL + pgvector", importance 0.98).

```python
def create_memory(db, *, user_id, statement, domain, source=SOURCE_USER_DECLARED,
                  authority=None, confidence=None, importance=0.5,
                  project_id=None, source_conversation_id=None,
                  expires_at=None, apply_domain_ttl=True, metadata=None,
                  now=utc_now, embed=None) -> MemoryEntity
def get_memory(db, memory_id, user_id) -> MemoryEntity | None            # owner-filtered
def list_memories(db, user_id, *, project_id=None, domain=None, status=None,
                  include_deleted=False, limit=100, offset=0) -> list[MemoryEntity]
def promote_memory(db, memory_id, user_id, actor, note="") -> MemoryEntity        # pending -> active
def supersede_memory(db, memory_id, user_id, actor, note="") -> MemoryEntity      # active -> superseded (manual)
def archive_memory(db, memory_id, user_id, actor, note="") -> MemoryEntity        # active|superseded -> archived
def delete_memory(db, memory_id, user_id, actor, note="", now=utc_now) -> MemoryEntity  # LOGICAL only
def resolve_owned_project(db, project_id, user_id) -> Project
    # raises ValueError when the project is missing OR project.owner_id != user_id;
    # never rely on the FK alone (FK proves existence, not ownership)
def update_memory_attributes(db, memory_id, user_id, *, importance=None, expires_at=None, metadata=None) -> MemoryEntity
    # NEVER accepts statement/domain/status changes — those require supersede/transitions
def search_memories(db, user_id, query, *, project_id=None, domains=None, k=5,
                    min_score=0.0, max_tokens=None, now=utc_now, embed=None) -> list[MemoryHit]
def restore_memory(db, memory_id, user_id, actor, note="", embed=None) -> MemoryEntity
    # archived -> active; conflict-validated; raises MemoryConflictError when refused (see 8.2)
def archive_expired_memories(db, *, now=utc_now, limit=1000) -> int      # used by the retention job
def backfill_embeddings(db, *, limit=100, embed=None) -> int             # lazy embedding fill
def check_potential_conflicts(db, user_id, statement, *, project_id=None, embed=None) -> list[MemoryEntity]
    # ACTIVE entities with cosine >= MEMORY_CONFLICT_COSINE_THRESHOLD — potential conflict
    # candidates only, NOT contradictions (contradiction judgment is V2.2)
```

`MemoryHit` is a frozen dataclass: `@dataclass(frozen=True) class MemoryHit: entity: MemoryEntity; score: float` — never return raw dicts.

### 8.1 Creation rules (contract §2, §5, §7)

1. Normalize statement: `" ".join(stmt.strip().lower().split())` (reuse legacy `_normalize` semantics). Empty → `ValueError`.
2. `content_hash = sha256(normalized).hexdigest()`.
3. **Dedupe:** if an `active`/`pending` entity with the same `(user_id, COALESCE(project_id,''), content_hash)` exists → return it unchanged (idempotent), do not bump version.
4. **Authority default:** `authority = authority or source` (maps `user_declared → explicit_user`, etc.); `confidence` default: user_declared 0.95, operator 1.0, extracted 0.65, consolidated 0.5, migrated 0.5.
5. **Status entry:** `user_declared`/`operator`-sourced → `active`; everything else → `pending`. (V2.1 has no extraction callers, so pending only arises from conflict rules below or migrated imports with conflicting hashes.)
6. **Potential conflict candidate check:** `check_potential_conflicts(...)` on ACTIVE entities. **Cosine similarity ≥ `MEMORY_CONFLICT_COSINE_THRESHOLD` does NOT mean contradiction** — it only identifies semantically similar candidates worth evaluating; actual contradiction judgment is V2.2. Canonical counterexample: "User prefers PostgreSQL." vs "User uses PostgreSQL." — high similarity, no contradiction.
   - No candidate → store, event `stored`.
   - Candidate + `AUTHORITY_RANK[new] < AUTHORITY_RANK[old]` + `new_confidence >= old_confidence` → supersede the old entity (status→superseded, `supersedes_id` set on the new entity, events `superseded` on old, `stored` on new), then store new as `active`.
   - Otherwise → store new as `pending` with `conflicts_with_id` = first candidate id; append `conflict_recorded` event on the new entity (note names the candidate id).
7. **Expiry:** if `apply_domain_ttl` and `expires_at is None` and `domain == episodic` → `expires_at = now() + timedelta(days=settings.MEMORY_EPISODIC_TTL_DAYS)`. Durable episodic (explicit override) passes `apply_domain_ttl=False`.
8. **Embedding:** when `embed` is provided, set `entity.embedding = embed([normalized])[0]` at creation; otherwise leave NULL (lazy backfill).
9. **Project ownership:** `user_id` is always the authenticated identity (never client-supplied). When `project_id` is provided, resolve it via `resolve_owned_project(db, project_id, user_id)` and raise `ValueError` when missing or not owned — never rely on the FK alone.

### 8.2 Transition rules

- `promote_memory`: only `pending → active`. Appends `promoted` event. Does not auto-clear `conflicts_with_id` — the operator resolves explicitly (extra service call `clear_conflicts` or via `update_memory_attributes` note).
- `supersede_memory`: only `active → superseded` (manual operator override, contract §6). Appends `superseded` event. Content preserved; version untouched (manual supersede does not create a successor).
- `archive_memory`: from `active` or `superseded`; appends `archived`.
- `restore_memory`: only `archived → active` (contract v0.2.1, §18). Operator-initiated only; explicitly logged with a `restored` event (actor, note). **Restore is conflict-validated:** run `check_potential_conflicts` on the statement against other ACTIVE entities in the same scope; when a candidate exists the restore is REFUSED — entity stays archived, raise `MemoryConflictError` carrying the candidate ids, append a `conflict_recorded` note event. Never blind activation, and never a conflicting pair of ACTIVE memories. Restore does not clear `expires_at`; if the memory was expired, the operator must extend/clear it explicitly via `update_memory_attributes`, otherwise the retention sweeper re-archives it.
- `delete_memory`: from any non-deleted status → `status=deleted`, `deleted_at=now()`. Appends `deleted` event. **Immediately excluded from search/list.** No physical purge in V2.1 (retention job policy comes later) — the row and events remain for audit.

### 8.3 Search pipeline (contract §13, vector-only)

1. **Candidate SQL filter** (always): `user_id = :uid`, `status = 'active'`, `expires_at IS NULL OR expires_at > :now`, plus `project_id = :pid OR project_id IS NULL` when `project_id` given, plus domain filter.
2. **Embedding ensure:** `backfill_embeddings` for candidate rows missing embeddings (batches of `MEMORY_EMBEDDING_BATCH_SIZE`), or embed the query.
3. **Similarity:** Postgres dialect → `ORDER BY embedding <=> :qvec LIMIT :cand` (candidate cap = `max(50, k*5)`); sqlite dialect → Python cosine over JSON lists (reuse the legacy `cosine_similarity` math).
4. **Rank:** `score = w_cosine * cos + w_importance * importance + w_recency * 0.5**(days_since_created / half_life)`. Weights from settings; deterministic ordering (tie-break `created_at asc, id asc`).
5. **Post-filters:** `score >= min_score`; truncate to `k`; `max_tokens` → trim list until summed token estimate (`len//4` fallback, mirroring `_count_tokens`) fits.
6. **Throttled access tracking:** update `last_accessed_at` only for returned ids where it is NULL or older than `MEMORY_ACCESS_UPDATE_THROTTLE_SECONDS` (default 3600); one batched `UPDATE ... WHERE id = ANY(...)`. Retrieval must never become a write-per-request workload.
7. Return `list[MemoryHit]`.

---

## 9. API endpoints (thin; `app/api/endpoints/memory.py`, `projects.py`)

All routes: `user: User = Depends(get_current_user)`, sync `db`, `api_error(...)` envelope, `except HTTPException: raise`, no engine details leaked.

### `app/api/endpoints/memory.py` (prefix `/api/v1/memory`)

| Method/Path | Body/Params | Behavior |
|---|---|---|
| `POST /api/v1/memory` | `{statement, domain, project_id?, importance?, expires_at?, source_conversation_id?, metadata?}` | Create (user_declared, authority explicit_user). `user_id` is NEVER accepted from the client — identity comes from `get_current_user`. `project_id` resolved + ownership-verified (404 when missing/foreign — never rely on the FK alone). `expires_at` applied only if key present (use `exclude_unset`); absent + episodic → domain TTL. 201 + entity. Conflicts resolved per §8.1 |
| `GET /api/v1/memory` | `project_id?, domain?, status?, limit, offset` | Owner-scoped list; `deleted` excluded by default |
| `GET /api/v1/memory/{id}` | — | Owner-scoped; 404 if missing/foreign (never reveal existence) |
| `POST /api/v1/memory/search` | `{query, project_id?, domains?, k?, min_score?, max_tokens?}` | Search pipeline; returns `{query, hits: [{id, statement, domain, score}]}`; 400 on empty query or when provider is `none` |
| `PATCH /api/v1/memory/{id}` | `{importance?, expires_at?, metadata?}` | Attribute-only updates; content/status changes rejected (400) |
| `POST /api/v1/memory/{id}/promote` | `{note?}` | pending → active (operator action) |
| `POST /api/v1/memory/{id}/supersede` | `{note?}` | active → superseded |
| `POST /api/v1/memory/{id}/archive` | `{note?}` | → archived |
| `POST /api/v1/memory/{id}/restore` | `{note?}` | archived → active (contract v0.2.1). Conflict-validated: 409 `conflict_refused` with candidate ids when potential conflict candidates exist; otherwise active + `restored` event |
| `DELETE /api/v1/memory/{id}` | — | Logical delete; returns `{"status": "deleted"}` |

The search endpoint depends on `get_embedding_provider` (overridable). Endpoints must import only: `app.api.deps`, `app.core.database`, `app.models.*`, `app.services.memory` — **never** `vector_store`, `graph`, or chat pipeline modules, so endpoint tests stay hermetic without sys.modules fakes.

### `app/api/endpoints/projects.py` (prefix `/api/v1/projects`)

Every project route follows **authenticate → load project → verify `project.owner_id == current_user.id` → operate**; a missing OR foreign project is 404 (never reveal existence). `user_id` is never accepted from the client.

| Method/Path | Behavior |
|---|---|
| `POST /api/v1/projects` | `{name, description?}` → 201; owner = current user from `get_current_user`, not the body |
| `GET /api/v1/projects` | owner's projects |
| `PATCH /api/v1/projects/{id}` | `{name?, description?}` owner-verified |
| `DELETE /api/v1/projects/{id}` | owner-verified; 409 `project_in_use` when any `memory_entities` row references it; else delete |

**Ownership chain invariant:** `Project.owner_id == ChatSession.owner_id == MemoryEntity.user_id`. Violations are impossible by construction — every `project_id` the platform stores was ownership-verified at write time.

### Optional but recommended: `PATCH /api/v1/chat/sessions/{session_id}`

Extend `SessionUpdateRequest` (app/api/endpoints/chat.py:111) with `project_id: Optional[str] = None`; when provided, resolve + ownership-verify via `resolve_owned_project` (404 otherwise — never rely on the FK alone) and set it via a new `store.update_conversation(db, conv, project_id=...)` param (app/services/chat_persistence.py:97). Ownership-validated; touches nothing else.

### Wiring (`app/main.py`)

Add to the existing import/include block: `memory.router` and `projects.router` under `/api/v1`.

---

## 10. Legacy import (operator CLI: `app/services/memory_legacy_import.py`)

`python -m app.services.memory_legacy_import --memory-dir memory_facts [--user-id <id>] [--dry-run]`

- Reads legacy `MemoryFact` JSON files (skip `.memory_index.json` dotfiles).
- Target user: `--user-id` or, when unset, the single fallback user (error if multi-user and no id).
- Mapping: `scope == "global"` → `project_id=None` (user-wide).
- `scope == "session:<id>"` → may be migrated ONLY when ALL of: the referenced session row exists; `session.owner_id` is set; `session.owner_id` matches the import target user. Otherwise **SKIP + REPORT** (warning with the rationale). Never infer ownership and never guess a project mapping — the previously deleted legacy sessions deterministically skip.
- Entities: `domain=semantic`, `source=migrated`, `authority=migrated`, `confidence=0.5`, `importance=0.5`, `status` = legacy status (superseded stays superseded), `metadata={"legacy_fact_id": <id>, "legacy_scope": <scope>}`.
- Idempotency guard: skip files whose `legacy_fact_id` already appears in `metadata` (query `metadata_->>'legacy_fact_id'`).
- `--dry-run` prints the plan, writes nothing.
- Does NOT import embeddings; the search-time backfill covers them.
- Legacy module `app/learning/operations/memory.py` and `memory_facts/` stay untouched and continue working; they are superseded operationally, not deleted.

---

## 11. Retention job (governance)

- `JobType.MEMORY_RETENTION = "memory_retention"` (app/learning/automation/models.py:14).
- `run_memory_retention()` in `app/learning/automation/jobs.py` → calls `memory.archive_expired_memories(session)` in its own sync session; returns counts; failure is logged, never fatal.
- `DEFAULT_SCHEDULES` (scheduler.py:59): add `ScheduleDef(job_type=MEMORY_RETENTION, cadence=DAILY, timeout_minutes=10)`.
- `archive_expired_memories`: `status='active' AND expires_at <= now` → `status='archived'`, event `expired` (actor `system`). Never deletes.

---

## 12. Capability Registry (AGENTS.md obligation)

Register in `app/learning/architecture/capabilities.py` (additive):

```python
register(Capability(
    id="memory_v2", name="Memory V2 — Governed Memory Store",
    description="Durable, scoped, curated memories with authority-aware conflict resolution, lifecycle events, and vector retrieval",
    owner="services.memory", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("architecture_governance", "agent_memory"),
    artifacts=("MemoryEntity", "MemoryEvent"),
    api_prefix="/api/v1/memory",
))
```

---

## 13. Tests to write (deterministic; sqlite; no network)

Reuse the sqlite `test_engine` pattern from `tests/chat/conftest.py:254` (StaticPool, `Base.metadata.create_all`). Provide a `fake_embedder` bag-of-words embedder (extend the one in `tests/learning/test_memory.py:156` with a broader vocab) and a fixed `now` callable. No `sys.modules` fakes needed — memory modules must not import chat infra (enforced by design, §9).

### `tests/learning/test_memory_entities.py` (service level)
1. Create: user_declared → active, defaults (confidence 0.95, authority explicit_user, version 1), event `stored` appended.
2. Dedupe: same normalized statement + scope → same id, no duplicate row (and unique-index backstop behaves).
3. Normalization: case/whitespace collapse.
4. Scoping: user A vs user B isolation; project A vs project B isolation; user-wide memory visible in every project context; project memory invisible outside its project.
5. Authority defaults per source (table-driven).
6. Potential conflict candidate ladder: extracted (0.65) vs existing explicit_user → new is `pending`, `conflicts_with_id` set, `conflict_recorded` event; explicit_user vs explicit_user (equal rank) → pending + conflict; explicit_user vs extracted → supersede (old→superseded, new→active, `supersedes_id` set); extracted with lower confidence than existing extracted → pending. High-cosine pairs that are NOT contradictory (e.g. "prefers PostgreSQL" vs "uses PostgreSQL") are returned as *candidates* — never described as proven contradictions.
7. Transitions: promote (pending→active only; invalid transitions raise), manual supersede (content preserved), archive, restore (archived→active with `restored` event; refused with `MemoryConflictError` when candidates exist and entity stays archived), logical delete (excluded from list/search; `deleted_at` set; rows/events still present).
8. Episodic TTL: default applies 90d; `apply_domain_ttl=False` → None; semantic → None.
9. Expiry sweeper: active + past `expires_at` → archived + `expired` event; durable (NULL) untouched.
10. Search: relevance ranking with fake embedder (top hit first), min_score filter, domain filter, scope filter, k cap, max_tokens truncation, deleted/archived/pending excluded; `last_accessed_at` updated ONLY when NULL or older than the throttle window, batched — never per-request.
11. Lazy embedding backfill: entities with NULL embedding get embedded on search (counting embedder asserts call pattern — mirror `test_index_persists_across_instances`).
12. Attribute update: importance/expires_at/metadata only; statement/status changes rejected.

### `tests/learning/test_memory_api.py` (endpoint level)
Build a `client` fixture like `tests/chat/conftest.py:308` — override `get_sync_db` + `get_embedding_provider`; create users via `auth.create_user`; token via `auth.issue_token`.
1. POST /memory 201 + fields; unauthenticated 401; foreign-user list empty; GET /memory/{id} 404 for foreign id; POST /memory with a foreign `project_id` → 404.
2. POST /memory/search returns ranked hits; empty query 400; provider `none` → 400/empty semantics.
3. Lifecycle endpoints: promote/supersede/archive/restore/delete each require ownership; restore returns 409 `conflict_refused` with candidate ids when candidates exist; PATCH rejects statement changes (400).
4. Projects: create/list/patch/delete; 409 on delete with memories; ownership enforced (foreign project_id on memory create → 404; chat session PATCH with foreign project → 404).

### `tests/learning/test_memory_legacy_import.py`
tmp dir with 2–3 fact JSON files (global + session-scoped); import; assert mapping, `source=migrated`, idempotent re-run, dry-run writes nothing, and session-scoped SKIP+REPORT paths: missing session row, session with NULL `owner_id`, session owned by a different user.

### `tests/chat/test_chat_persistence.py` (additive)
`create_conversation(project_id=...)` persists; `update_conversation(project_id=...)` updates; foreign project id rejected at the service boundary (raise `ValueError`).

### `tests/chat/test_endpoints.py` (additive)
PATCH session with a valid project_id persists; with a foreign project → 404.

No Postgres-specific test is required; m004/m005 are verified manually (below).

---

## 14. Must-not-touch list

- `app/learning/operations/memory.py`, `tests/learning/test_memory.py`, `app/learning/operations/router.py` (existing `/operations/memories` workspace) — legacy store stays live until import ships; no behavior changes.
- `app/services/vector_store.py`, `app/core/whoosh_manager.py`, `app/retrievers/*` — document RAG retrieval; memory has its own store.
- `app/agent/*`, `app/core/langsmith.py`, `app/core/observability.py` — untouched.
- `app/api/endpoints/chat.py` — only the single optional PATCH `project_id` extension; no other edits.
- `app/services/auth.py`, `app/models/user.py`, auth flows — untouched.
- `docker-compose.yml`, frontend, `.env` — untouched (memory settings are defaults; nothing must be added to `.env`).
- Existing migrations m001–m003, `schema_migrations` rows — never edited.
- `data/learning.db` (telemetry) — memory lives in Postgres, not SQLite; no telemetry writes added in V2.1.

---

## 15. Definition of done + verification

1. `pytest -q` — all suites green: 154 existing + the new files above.
2. With `docker compose up -d db redis`: app startup applies m004/m005; verify via psql: `\d memory_entities` (vector column present), `\d projects`, `SELECT name FROM schema_migrations;` (5 rows: m001–m005).
3. Smoke test against the running API: login → POST project → POST user-declared memory (active) → POST conflicting extracted-style memory via the service (pending+conflict) → POST /memory/search returns the active one → archive then restore (active, `restored` event) → DELETE → search excludes it.
4. `python -m app.services.memory_legacy_import --dry-run` prints a sane plan against the live `memory_facts/` dir; run for real once, re-run is a no-op.
5. Capability Registry: `GET /api/v1/capabilities` includes `memory_v2`.
6. AGENTS.md "Definition of Done" checklist satisfied: architecture consistent, registry updated, lineage preserved (events + supersedes), APIs documented, tests added, invariants preserved.

**Do not commit anything unless explicitly asked.**
