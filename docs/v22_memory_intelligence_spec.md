# OwnGPT Memory V2.2 — Memory Intelligence Implementation Specification

**Status:** Implemented (2026-08-15)

**Normative references:** `docs/memory_contract.md` v0.2 (frozen) · `docs/v21_memory_implementation_spec.md` (storage layer) · `AGENTS.md` (architecture constitution)

**Scope:** V2.2 integrates the V2.1 governed memory store into the agent runtime: graph recall node, tool rewiring, detached three-gate extraction, tenant-isolation hardening. NO new tables, NO new infrastructure, NO UI, NO contradiction judge, NO consolidation job, NO hybrid retrieval.

---

## 1. Design decisions

| # | Decision |
|---|---|
| D1 | Three-gate extraction: deterministic eligibility → LLM structured JSON → deterministic validation |
| D2 | `MemoryService.create_memory` is the single write authority |
| D3 | No LLM contradiction judge — conflict rule = cosine ≥ `MEMORY_CONFLICT_COSINE_THRESHOLD` vs active |
| D4 | No consolidation, no reranker, no BM25/RRF |
| D5 | Domains stay the existing four: `semantic`, `episodic`, `preference`, `procedural` |
| D6 | Explicit commands → `explicit_user` authority, rank 0, confidence 0.95, status active |
| D7 | Extraction → `extracted` authority, rank 1, confidence 0.65, status pending (never self-approved) |
| D8 | Cross-session recall: `search_memories(user_id, project_id, k=5, max_tokens=400)` — project scope + user-wide floats |
| D9 | Memory ≠ conversation ≠ LangGraph state — only `memory_context` text enters the system prompt |
| D10 | Streaming never depends on memory; extraction runs detached after `[DONE]` |
| D11 | Tenant isolation is invariant on every read path |
| D12 | Staged legacy retirement (stop writes → switch reads → verify → remove) |

## 2. Recall node (`retrieve_memory`)

- New LangGraph node before the first `call_model`; entry point of the graph.
- Inputs from `AgentState`: `user_id`, `project_id`, last `HumanMessage` as query.
- Calls `search_memories` through the configured embedding provider; degrades to no context on any failure (memory is context, not truth).
- Output `memory_context` is appended to the system prompt by `call_model`.
- Gated by `MEMORY_V2_GRAPH` (default True). OFF = no memory context injected (deprecation window only).

## 3. Tool rewiring

- `remember_user_fact` / `remember_session_fact` → `create_memory(source=user_declared)` → active, explicit_user, 0.95.
- `forget_user_fact` → exact normalized-statement match (`find_memory_by_statement`, project scope + user-wide fallback) → logical `delete_memory`.
- The graph injects `user_id`/`project_id` into memory-tool args from the request tenant context.
- Guardrails unchanged: all three remain in `AUTO_TOOLS`, `MAX_FACT_LENGTH=500`, `SECRET_PATTERNS`; every call recorded as a `ToolExecution` artifact.

## 4. Extraction pipeline (`app/learning/extraction/extractor.py`)

- **Gate 1 (deterministic):** skip `eval-*` sessions, explicit command / recall turns, non-substantive turns (incl. `general` rule intent), and per-session throttle (1 per `EXTRACTION_TURN_INTERVAL`=3 user turns, in-memory operational bookkeeping).
- **Gate 2 (LLM):** `gpt-4o-mini`, temperature 0, structured JSON `{candidates: [{statement, domain, importance}]}`, retried ONCE per batch.
- **Gate 3 (deterministic, batch-atomic):** any violation drops the WHOLE batch — malformed JSON, statement > 500 chars, domain not in the four, candidates > 3, importance outside [0,1], or `SECRET_PATTERNS` match.
- Writes: `create_memory(source=extracted)` → status pending, authority extracted, confidence 0.65, lineage to the conversation.
- Execution: `schedule_extraction` spawns a daemon thread with its own `SyncSessionLocal`, called after the response is persisted — never on the request/stream path, never raises.

## 5. Tenant isolation (D4)

- `default_session_loader` now filters `ChatSession.owner_id == user_id` when a user is provided; `EpisodicRecallService.recall(..., user_id=...)` threads the tenant through. Cross-tenant transcript leakage is impossible.

## 6. Configuration

- `MEMORY_V2_GRAPH` (bool, default True) — V2.2 master gate for recall + extraction.
- All other settings from V2.1 (`MEMORY_*` block in `app/core/config.py`) unchanged.

## 7. Legacy retirement status

- Stage 1 done (V2.1 MUST-FIX): dead `backfill_embeddings` removed.
- Stage 2 done (V2.2): graph reads and tools route exclusively through V2.1; legacy JSON store (`memory_facts/`, `episodic_summaries/`) no longer read by the agent.
- Stage 3 (import) / Stage 4 (remove): pending operator sign-off — run `python -m app.services.memory_legacy_import --memory-dir memory_facts [--user-id <id>] [--dry-run]` first.

## 8. Definition of done

- [x] `retrieve_memory` node + `memory_context` prompt injection
- [x] Tools rewired to V2.1 with tenant injection
- [x] Extraction pipeline (3 gates) + detached scheduling
- [x] D4 episodic loader owner filter + regression test
- [x] Capability Registry updated (`memory_v2`, `memory_extraction`)
- [x] Contract wording aligned (exponential half-life decay ranking)
- [x] Tests: gates, node, tools, D4; full suite green
