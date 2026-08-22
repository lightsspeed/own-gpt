# OwnGPT Memory Contract v0.2

**Status:** Frozen (2026-08-14)

**Scope:** This document is the contract between the OwnGPT platform and its memory subsystem. It governs memory storage, ownership, provenance, lifecycle, and retrieval semantics. It is not an implementation specification. Implementation is specified per milestone (V2.1, V2.2, ...).

Amendments to a frozen contract require a new version (v0.3, ...).

> **v0.2.1 amendment (2026-08-14) — Restore transition:** adds `archived → active`
> (operator restore) with an explicit `restored` lifecycle event. Restore is
> operator-initiated and **must pass conflict validation** (§7): an archived memory
> is never blindly activated if doing so would create contradictory ACTIVE
> memories — on conflict, follow the authority/conflict policy instead of
> silently restoring. Details in §18.

---

## 1. Definitions

- **MemoryEntity** — a durable, scoped, curated representation of a single claim or event that the system has sufficient evidence to retain for future retrieval.
- **Memory ≠ transcript.** A memory is curated and canonicalized. Raw messages and conversation transcripts are chat persistence artifacts, not memory.
- **Memory ≠ context.** The Memory subsystem defines storage, governance, and retrieval semantics. It never decides prompt injection. A future Context Engine consumes retrieval results and decides what enters the context window.
- **Authority ≠ confidence.** Authority is the evidential weight of the claim's origin (human vs. machine). Confidence is a numerical estimate of correctness. Conflict resolution weighs authority and confidence jointly — never confidence alone.
- **Extraction boundary.** The extraction LLM never writes `memory_entities` directly. It produces candidates that pass policy validation, dedup, and conflict resolution before persistence (see §11).

---

## 2. Core artifact: `MemoryEntity`

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | immutable |
| `user_id` | uuid | **required** — owner |
| `project_id` | uuid \| null | null = user-wide (see §4) |
| `domain` | enum | `semantic \| episodic \| preference \| procedural` |
| `statement` | text | canonical, single-claim natural language |
| `source` | enum | `user_declared \| extracted \| consolidated \| migrated` |
| `authority` | enum | `explicit_user \| operator \| extracted \| consolidated \| migrated` (see §5) |
| `confidence` | float 0..1 | see §5 |
| `importance` | float 0..1 | relevance to future work; decayable |
| `source_conversation_id` | uuid \| null | required when evidence originates from a conversation; nullable for operator/system-created memories |
| `content_hash` | text | canonicalized-statement hash; drives dedupe |
| `status` | enum | `pending \| active \| superseded \| archived \| deleted` |
| `version` | int | increments on supersede |
| `supersedes_id` | uuid \| null | lineage — the mandatory parent link |
| `conflicts_with_id` | uuid \| null | unresolved contradiction (see §8) |
| `expires_at` | timestamptz \| null | retention policy field; null = durable |
| `created_at` | timestamptz | tz-aware UTC |
| `updated_at` | timestamptz | tz-aware UTC |
| `last_accessed_at` | timestamptz \| null | for decay / eviction decisions |
| `deleted_at` | timestamptz \| null | set on logical deletion (see §9) |
| `embedding` | vector(N) | computed projection, not the artifact; N deployment-pinned (see §12) |
| `metadata` | jsonb | extraction pipeline version, model, tags |

Other transition timestamps (`superseded_at`, `archived_at`) are recorded as lifecycle events; only `deleted_at` is a column.

---

## 3. Memory domains

| Domain | Meaning | Retention default |
|---|---|---|
| `semantic` | Stable truths about the user or project ("Project uses FastAPI + pgvector") | No expiry |
| `episodic` | What happened, temporally anchored ("On 2026-08-14, archived 24 legacy conversations") | 90 days, overridable |
| `preference` | How the user likes things ("User wants concise chat responses") | No expiry |
| `procedural` | How things are done ("To run tests: `pytest`") | No expiry |

**Retention is a policy, not an intrinsic property of the domain.** `episodic` defaults to a 90-day TTL, but any entity — including episodic — may carry `expires_at = NULL` when its importance/retention policy marks it durable (e.g., a major decision). No domain hard-forces expiry; no domain forbids it.

---

## 4. Ownership & scoping

- `user_id` is always set. `project_id` is nullable; null = user-wide memory.
- **Project model (introduced now):** `projects` table (`id`, `user_id`, `name`, `description`, `metadata`) and `ChatSession.project_id`. UI for projects may come later; the schema ships in V2.1.
- **Visibility rule:** retrieval returns memories where `project_id IS NULL` (user-wide, floats into all projects) OR `project_id = current project`. Project-specific memories never leak into other projects — contamination is forbidden.

```
User-wide memory
   ├── project A
   ├── project B
   └── project C

Project A memory: FastAPI, LangGraph, PostgreSQL, pgvector
Project B memory: React, AWS, DynamoDB, S3
```

- **Migration rule (V2.1):** legacy `memory_facts/` JSON facts import with `source = migrated`. Global facts become user-wide; `session:<id>` facts map best-effort to their project; the legacy JSON store and its embedding sidecar are superseded — no dual-write.

---

## 5. Authority & confidence

**Authority ladder (total order for conflict resolution):**

```
explicit_user = operator   (human; highest weight)
        │
   extracted
        │
   consolidated
        │
     migrated
```

- `explicit_user` — the end-user states the claim directly.
- `operator` — a platform operator creates or overrides a memory.
- `extracted` — inferred by the extraction pipeline from conversation evidence.
- `consolidated` — derived from existing memories by a consolidation process.
- `migrated` — imported from the legacy store.

**Confidence defaults** (operator overrides recorded as events):

| Source | Default confidence |
|---|---|
| user_declared | 0.95 |
| extracted | 0.6–0.7 (pipeline-set) |
| consolidated | 0.5 |
| operator-created | 1.0 |

**Promotion rule:** `user_declared` memories enter `active` directly. `extracted` memories enter `pending`. Promotion from `pending` is operator-gated; confidence informs the decision but is **never the sole promotion mechanism**. Policy may assist (e.g., explicit user re-confirmation), but no bare `confidence >= 0.7` auto-promotion.

---

## 6. Lifecycle

```
         (explicit user declaration)
            ────────────────►
pending ──(operator approval)──► active ──(expires_at passed, sweeper)──► archived
                                    │                                        │
                                    │  superseded                            │  operator
                                    ▼                                        ▼
                               superseded ◄─────────────── archived ────────► deleted
```

`archived ──(operator restore, NEW in v0.2.1)──► active` — see §18.

**Rules:**

- Transitions are explicit, logged events (append-only audit trail). History is never rewritten.
- `pending → active` requires operator approval or an approved policy (see §5). Auto-promotion by confidence alone is forbidden.
- `active → superseded` follows the conflict resolution rules (§7).
- `active → archived` also occurs when `expires_at` passes (retention sweeper).
- `archived → deleted` is always operator-initiated (see §9).
- `archived → active` (restore, v0.2.1) is operator-initiated, explicitly logged with a `restored` event, and conflict-validated (see §18) — never a blind activation.
- Superseded entities retain their content, lineage, and events.

---

## 7. Conflict resolution

**Decision tree (on extraction/insert):**

```
NEW CLAIM
   │
   ▼
Potential contradiction?
   │
   ├── NO ────────────────► normal dedupe / store
   │
   ▼ YES
Compare authority (then confidence)
   │
   ├── higher ────────────► supersede old (logged)
   │
   ├── equal ─────────────► pending + conflict record
   │
   └── lower ─────────────► pending + conflict record
```

- When authority is strictly higher AND confidence is not inferior, the new claim supersedes the old.
- Otherwise the new claim enters `pending` with `conflicts_with_id` set; the operator resolves.

**Worked example:**

1. User explicitly: "I use PostgreSQL." → `active`, `explicit_user`.
2. LLM infers: "User prefers MongoDB." → contradicts; authority lower → `pending`, `conflicts_with_id = PostgreSQL memory`.
3. User later explicitly: "I've switched from PostgreSQL to MongoDB." → authority strictly higher → MongoDB supersedes PostgreSQL (lineage recorded).

> Memory systems should be evidence-driven, not model-confidence-driven. The LLM may never silently rewrite reality.

---

## 8. Relationships

- `supersedes_id` — lineage for resolved contradictions (mandatory parent link).
- `conflicts_with_id` — records unresolved contradictions (nullable).
- A dedicated `memory_relationships` table (`source_memory_id`, `target_memory_id`, `relationship_type` ∈ `supersedes | contradicts | supports | derived_from`, `created_at`, `metadata`) is a **future** evolution for the memory graph (V2.4+). **Not built in V2.1.** `supersedes_id + conflicts_with_id` is sufficient for the first production-quality implementation.

---

## 9. Deletion semantics

Deletion is two-phase:

- **Logical deletion** — `status = deleted`, `deleted_at` set. The entity is excluded from retrieval immediately.
- **Physical purge** — rows/vectors removed per retention policy; executed by a retention job, not by the delete request itself.

The deletion audit event (who, when, why, entity id) is retained without retaining the unnecessary sensitive content. Operator-triggered "forget" requests ("Forget that I prefer MongoDB") result in immediate logical deletion; physical purge follows policy.

---

## 10. Provenance

- Every extracted/consolidated memory must be traceable to its evidence: `source`, `source_conversation_id` (when the evidence originated in a conversation), extraction pipeline version, and model, all recorded in `metadata`.
- `source_conversation_id` is required when evidence originates from a conversation (including `user_declared` memories stated in chat, e.g. "Remember that I prefer Python"); nullable for operator/system-created memories.
- No orphan artifacts. Every entity has a lineage path to its parent or evidence.

---

## 11. Extraction boundary (contract-level; implementation in V2.2)

```
Conversation
   │
   ▼
Extraction            (LLM)
   │
   ▼
Memory candidates
   │
   ▼
Validation            (policy: PII, scope, single-claim, retention)
   │
   ▼
Dedup / conflict      (§7)
   │
   ▼
MemoryEntity
```

The LLM produces **candidates only**. Persistence happens through the validated pipeline. This is a security and governance boundary: no direct LLM writes to `memory_entities`.

---

## 12. Embeddings

- **Configuration-driven, deployment-pinned:** `MEMORY_EMBEDDING_PROVIDER`, `MEMORY_EMBEDDING_MODEL`, `MEMORY_EMBEDDING_DIMENSION`.
- The storage layer depends on an `EmbeddingProvider` interface (OpenAI, local model, future providers); OpenAI is not hard-wired into the repository.
- The database column is `vector(N)` where N is pinned by configuration at migration time.
- Changing the embedding dimension is **not a normal config change** — it requires an embedding re-index/migration strategy (versioned, deployment-gated).

---

## 13. Retrieval contract

- **Input:** `(user_id, project_id | null, query, domain filter*, k, min_score)`
- **Pipeline (V2.1):** vector-only.
  1. Candidate generation — pgvector similarity (cosine) on `embedding`
  2. Hard filters — `status = active`, scope rule (§4), domain filter, `expires_at > now`
  3. Ranking — `score = w1·cosine + w2·importance + w3·exponential half-life decay (0.5 ** (days / MEMORY_RECENCY_HALF_LIFE_DAYS))`
- **Output:** ranked `MemoryHit {entity, score}` list, capped by a caller-supplied token budget. No raw dicts.
- **Explicitly deferred:** hybrid keyword+vector retrieval and reranking (BM25/RRF per ADR-0008 precedent). V2.3+ introduces them as a measured experiment — start vector-only, then measure whether hybrid improves recall.

---

## 14. Storage

- Postgres table `memory_entities` with a `vector(N)` column (pgvector; the `db` service already runs it).
- `memory_events`-style append-only audit events for lifecycle transitions.
- The legacy JSON `memory_facts/` store and `.memory_index.json` sidecar are superseded by migration; no dual-write.

---

## 15. Out of scope for V2.1

- Context Engine / prompt injection (future)
- Extraction pipeline (V2.2 — contract boundary defined in §11)
- Hybrid retrieval, BM25, RRF, rerankers (V2.5, measured)
- Automated consolidation
- `memory_relationships` table / memory graph (V2.4+)
- Projects UI, memory management UI (schema ships in V2.1)
- Collaborative multi-user memory

---

## 16. Roadmap

```
V2.1  Memory storage + governance      (schema, projects, lifecycle, CRUD, retrieval primitives)
V2.2  Memory extraction                (extraction → candidates → validation → persist)
V2.3  Memory retrieval                 (vector retrieval, ranking, budgeted injection interfaces)
V2.4  Cross-session context            (session-to-session recall, memory graph groundwork)
V2.5  Hybrid retrieval / reranking     (measured experiment vs. vector-only baseline)
V2.6  Memory evaluation + optimization (precision/recall, false-memory rate, token savings)
```

---

## 17. Frozen decisions (summary)

1. `pending` status kept; extracted low-confidence memories enter `pending`; explicit user declarations go straight to `active`. Promotion is operator-gated — never confidence alone.
2. Authority-aware conflict resolution: auto-supersede only on strictly higher authority; equal/lower authority → `pending` + conflict record.
3. Project model introduced now: `projects` table + `ChatSession.project_id`; UI later.
4. Embeddings config-driven, deployment-pinned; `EmbeddingProvider` interface; dimension change = re-index migration.
5. Episodic default TTL 90 days, configurable, overridable per entity; retention is a policy, not an intrinsic domain property.
6. Explicit deletion semantics: immediate logical delete + policy-driven physical purge; audit event retained.
7. Extraction → candidates → validation → persist; the LLM never writes `memory_entities` directly.
8. Provenance preserved for every entity; `source_conversation_id` required when evidence originates in a conversation.
9. v0.2.1: restore transition `archived → active` with explicit `restored` event; operator-initiated, conflict-validated (§18).

---

## 18. Amendment v0.2.1 — Restore transition

**Date:** 2026-08-14 — applied to the frozen contract as a versioned amendment note; the baseline contract remains v0.2.

**Change:** adds a lifecycle transition `archived → active` and a `restored` MemoryEvent.

**Rules:**

- Restore is operator-initiated; it is never automatic.
- Restore must be explicitly logged with a `restored` event (actor, note, timestamp).
- Restore must run conflict validation (§7): an archived memory must NOT be blindly restored if doing so would create contradictory ACTIVE memories.
- When a potential conflict exists, follow the existing authority/conflict policy instead of silently activating the archived memory — the memory stays archived, or enters `pending` with `conflicts_with_id` per that policy.
- Restore does not clear `expires_at`: if the memory was expired, the operator must extend or clear `expires_at` explicitly, otherwise the retention sweeper re-archives it.
