# V2.2 MEMORY EXTRACTION ARCHITECTURE AUDIT

Audit date: 2026-08-15
Scope: How a conversation turn becomes a durable `MemoryEntity` in the current
codebase (V2.2 memory intelligence). Inspection only — no files modified.
Comparator: `docs/v22_memory_intelligence_spec.md` §9/§10.

Verified commits: `e708845` (V2.2), `8c9bb71` (Ollama provider). Working tree clean.

---

## 1. EXECUTIVE SUMMARY

V2.2 memory extraction is **implemented and architecturally sound**. The
pipeline matches the spec: three deterministic gates — eligibility (no LLM),
LLM extraction (temp 0, one retry), batch-atomic validation (no LLM) — write
candidates through the existing V2.1 `MemoryService.create_memory` as
`pending` / `extracted` / confidence 0.65. **Nothing is ever auto-approved**;
humans promote via the V2.1 lifecycle.

Execution is correctly isolated: extraction runs **after** the response is
complete, on a detached daemon thread with its own `SyncSessionLocal`, and can
never block, fail, or corrupt the chat path. In the streaming path it is
scheduled after the assistant message is persisted and runs concurrently with
`[DONE]` delivery without blocking it. In the sync path it runs after persist.

Candidates never enter LangGraph state — the graph carries only transient
`memory_context`; all extraction artifacts travel through the database. No
orphan artifacts: every written entity carries `user_id`, `source`,
`source_conversation_id`, `content_hash`, `authority`, `status`.

**Verdict: GREEN** — with YELLOW operational items (in-memory throttle,
per-entity write commits, silent gate-3 drops, unbounded daemon threads,
no exchange length guard) and **no RED items**. All items are operational
hardening, not architectural flaws. Section 12 lists every item with evidence;
section 13 gives recommendations only.

---

## 2. ARCHITECTURE DIAGRAM

```
POST /api/v1/chat[/stream]                     app/api/endpoints/chat.py
  │  auth, idempotency, persist user message (store.persist_user_message)
  ▼
LangGraph  ── StateGraph(AgentState)           app/agent/graph.py:266
  retrieve_memory ─► agent (call_model) ─?──► action (tools) ─► agent
       │               │                      └──► END
       │               └─ build_model → build_llm (provider factory)
       ▼
  graph.stream(stream_mode=["messages","updates"]) ─► SSE content chunks
  │
  │  (response complete: grounding, validation, trace)
  ▼
persist_assistant(COMPLETED) ─► record_id ─► [DONE]          chat.py:895/899/964
  │
  ▼  schedule_extraction() ──► daemon thread (own SyncSessionLocal)
run_extraction                                  app/learning/extraction/extractor.py:194
  │  Gate 1  _is_eligible + _throttle_allowed      (deterministic, no LLM)
  │  Gate 2  _extract_with_llm  (build_llm(EXTRACTION_MODEL), temp 0, retry once)
  │  Gate 3  _validate_candidates (batch-atomic, SECRET_PATTERNS)
  ▼
MemoryService.create_memory(source=extracted, status=pending, 0.65, embed)
  │  dedupe → check_potential_conflicts → supersede | pending+conflicts_with_id
  ▼
memory_entities  (+ memory_events, m004 vector(1536))
  ▲
  │  read paths (V2.1, unchanged):
  │    retrieve_memory node (search_memories k=5)
  │    explicit memory tools (remember/forget, AUTO_TOOLS)
  │    episodic recall (transcripts → summaries)
```

Dependencies flow downward only: chat → extraction → memory service → store.
Extraction depends on nothing above it; the chat layer depends on extraction
only through a fire-and-forget schedule call.

---

## 3. END-TO-END TRACE

Example: user sends **"I prefer detailed technical explanations with real-world examples."** (streaming).

1. **Request** — `chat_stream_endpoint` (`app/api/endpoints/chat.py:661`): auth
   via `get_current_user`; conversation loaded/created; idempotency by
   `request_id`; user message persisted (`persist_user_message`).
2. **Pipeline** — intent classification, query rewrite, retrieval (KB) build
   `ctx`; intent for this message resolves to `general` via rules
   (`app/agent/pipeline/intent.py:71-129` — no rule matches; falls through to
   LLM classifier).
3. **Graph invoke** — `graph.stream(..., stream_mode=["messages","updates"])`
   (`chat.py:783`):
   - `retrieve_memory` node (`graph.py:214`): query = last user message;
     `search_memories` k=5 (provider openai@1536 in prod config); result
     injected into `memory_context`; failures degrade to empty string.
   - `agent` / `call_model` (`graph.py:130`): prompt assembly, `memory_context`
     appended to the system prompt; `build_model(model, temperature)` →
     `build_llm` (`app/core/llm_provider.py`); `.bind_tools(tools)` +
     `.invoke`; answer streamed token-by-token via SSE `content` events.
4. **Post-stream** — grounding, validation, trace emit; assistant message
   persisted COMPLETED (`chat.py:895`); `record_id` SSE event (`chat.py:906`).
5. **Extraction schedule** — `schedule_extraction(request.session_id, user.id,
   conv.project_id)` (`chat.py:899`) starts the daemon thread; `[DONE]` queued
   in `finally` (`chat.py:964`) — never blocked by extraction.
6. **Extraction thread** (`extractor.py:194`):
   - Own `SyncSessionLocal`; load conversation + messages.
   - Walk messages (latest user with `status != "failed"`, latest assistant
     with content) → `last_user` / `last_assistant` (`extractor.py:222-228`).
   - **Gate 1** `_is_eligible` (`extractor.py:82`): not `eval-*`; substantive
     (≥3 chars, not punctuation-only); not a command/recall turn (pattern
     list `extractor.py:48-57`); rule-classified intent is **not** `general`
     (`extractor.py:93-95`). For this example: substantive ✓, no command ✓ —
     but rule intent is `general` (no rule fired → rule_classify returns the
     GENERAL catch-all? — see Section 4 note) → **turn skipped**.
   - If eligible: **Gate 1b** `_throttle_allowed` (1 extraction per 3 user
     turns per session, `extractor.py:99`).
   - **Gate 2** `_extract_with_llm(exchange)` (`extractor.py:110`): exchange =
     `"User: {last_user}\n\nAssistant: {last_assistant}"` (only the last pair,
     `extractor.py:235`); `build_llm(EXTRACTION_MODEL, temperature=0.0)`; plain
     JSON parse with ONE retry; malformed twice → `[]` (batch dropped, logged).
   - **Gate 3** `_validate_candidates` (`extractor.py:158`): batch-atomic —
     any violation (count >3, non-dict, empty/oversized statement, unknown
     domain, importance out of [0,1], secret pattern hit) drops the **whole**
     batch.
   - **Write** — per candidate `create_memory(..., source=extracted,
     importance=c["importance"], project_id, source_conversation_id=session_id,
     embed=provider.embed)` (`extractor.py:243-254`).
7. **Store** (`app/services/memory.py:241`): normalize → content_hash →
   dedupe (same user+scope+hash, active/pending) → status `pending` (not
   user-declared/operator) → `check_potential_conflicts` (cosine ≥ 0.85 among
   active, `memory.py:518/547`): higher-authority + ≥ confidence supersedes
   (`status=superseded`, `supersedes_id`), else the new entity stays `pending`
   with `conflicts_with_id`; embedding written when provider present
   (`memory.py:342-343`); events `stored` / `conflict_recorded` appended.
8. **Result** — memory is `pending`; it becomes retrievable only after a human
   promotes it (`promote_memory`, operator API). Nothing auto-applies.

---

## 4. EXTRACTION IMPLEMENTATION

File: `app/learning/extraction/extractor.py` (285 lines).

- **Model** (`extractor.py:40`): `EXTRACTION_MODEL = settings.LLM_MODEL` when
  provider is `ollama` (qwen3:8b), else `gpt-4o-mini`. Provider-agnostic via
  `build_llm` factory.
- **Gate 1 — eligibility** (`extractor.py:65-96`), deterministic:
  - `eval-*` sessions never extract (`:84`).
  - Non-substantive turns (empty, punctuation-only) skipped (`_substantive`).
  - Explicit command/recall turns skipped — they are already handled by the
    explicit tool path (`_COMMAND_PATTERNS`, `:48-57`) → no double-write.
  - **Rule-based intent check**: `IntentClassifier().rule_classify(last_user)`
    — if a rule fires with intent `general`, the turn is skipped (`:93-95`).
    NOTE: `rule_classify` returning `None` (no rule matched) passes the gate —
    LLM intent classification is never consulted. Deterministic by design, but
    see Section 12 (Y5).
- **Gate 1b — throttle** (`extractor.py:99-107`): at most one extraction per
  `EXTRACTION_TURN_INTERVAL = 3` user turns per session. **In-memory dict +
  lock** — resets on restart, per-process only (Y1).
- **Gate 2 — LLM** (`extractor.py:110-155`): system prompt fixed; domains
  allowlisted from `DOMAINS`; output contract `{"candidates":
  [{"statement", "domain", "importance"}]}`; `temperature=0.0`; one retry on
  any exception; content list (multi-block) flattened; malformed twice →
  `[]` logged `extraction_llm_failed`. No structured-output/JSON-mode pinning —
  relies on prompt + Gate 3.
- **Gate 3 — validation** (`extractor.py:158-191`): batch-atomic as documented
  (`:159-160`); secret scan reuses `guardrail.SECRET_PATTERNS` (deterministic,
  stdlib); on secret hit logs `extraction_gate3_secret_dropped`.
- **run_extraction** (`extractor.py:194-266`): guarded by
  `settings.MEMORY_V2_GRAPH` (`:205`); never raises (outer try/except logs
  `memory_extraction_failed`, returns 0). Writes via one `create_memory` call
  **per candidate** — each call commits its own transaction (Y2: batch write
  is not atomic even though Gate 3 validation is).
- **schedule_extraction** (`extractor.py:269-285`): daemon thread per call,
  named, own `SyncSessionLocal`. No pool/semaphore — one thread per eligible
  completion (Y3).

NOT IMPLEMENTED vs spec §9/§10: none — eligibility, throttle, extraction,
validation, and the pending-write execution model are all present. Cross-session
consolidation belongs to V2.3 (out of scope, as per spec).

---

## 5. CANDIDATE CONTRACT

- **Transient shape**: plain `dict` — `{"statement": str (≤500 chars), "domain":
  str ∈ DOMAINS, "importance": float ∈ [0,1]}`. Produced by Gate 2 JSON parse
  (`extractor.py:145-149`), normalized/re-validated by Gate 3
  (`extractor.py:188-190`), consumed positionally by `create_memory`
  (`extractor.py:244-254`).
- **No dataclass/Pydantic model** for the candidate envelope. The Constitution
  prefers dataclasses/Pydantic for *persisted artifacts*; candidates are
  transient and never persisted — but the envelope is the only artifact-shaped
  data in the pipeline without a model (Y4, mild).
- **Persisted artifact**: `MemoryEntity` (`app/models/memory.py:87-114`) —
  full artifact fields: `id`, `created_at/updated_at`, lineage
  (`source_conversation_id`, `supersedes_id`, `conflicts_with_id`,
  `content_hash`), `version`, `status`, `authority`, `confidence`,
  `importance`, `expires_at`, `embedding vector(1536)` (pgvector).
- **Derived values on write**: `authority = extracted` (rank 1),
  `confidence = 0.65` (`DEFAULT_CONFIDENCE`, `models/memory.py:58-63`),
  `status = pending` (`memory.py:305-309`), `importance` forwarded from the
  candidate as-is (no floor — Gate 3 accepts 0.0, which would enter pending
  with importance 0; see Section 12, Y6).
- **Dedupe key**: `content_hash` of normalized statement scoped to
  (user, project) with status active|pending (`memory.py:271-285`) — idempotent
  writes, so throttle/thread races cannot create duplicates.

---

## 6. GATES TABLE

| Gate | Stage | Deterministic? | Where | Fails when | Failure result |
|---|---|---|---|---|---|
| 1 | Eligibility | Yes (no LLM) | `extractor.py:82` | `eval-*` session; filler/emoji turn; explicit command/recall turn; rule-intent == general | skip, return 0 (silent) |
| 1b | Throttle | Yes | `extractor.py:99` | < 3 user turns since last extraction in this session (in-memory) | skip, return 0 (silent) |
| 2 | LLM extraction | No (qwen3:8b / gpt-4o-mini, temp 0) | `extractor.py:110` | malformed JSON / exception | 1 retry, then batch dropped + warning log |
| 3 | Validation | Yes (no LLM) | `extractor.py:158` | count > 3; non-dict candidate; empty/oversized statement; domain ∉ DOMAINS; importance out of [0,1]; secret pattern | **whole batch dropped**, silent except secret case (warning) |
| — | Persistence | Yes | `memory.py:241` | invalid domain/statement; ownership check `resolve_owned_project` | raise → caught in `run_extraction` → log, return 0 |

Observations: gates are correctly ordered (cheap deterministic filters before
the only paid LLM call); Gate 2 is the only non-deterministic stage; Gate 3 is
strictly stronger than Gate 2's output contract (defense in depth). Gate 3
failure visibility is poor (Y7).

---

## 7. LANGGRAPH STATE

`AgentState` (TypedDict, `app/agent/state.py:6-20`), 14 fields:
`messages` (Annotated operator.add), `system_prompt`, `answer_mode_directive`,
`intent`, `rewritten_query`, `pipeline_context`, `answer_mode`, `session_id`,
`user_id`, `project_id`, `memory_context`, `model`, `temperature`.

- **Extraction candidates do not travel through graph state** — none of the
  14 fields carries them. The graph is entirely read-path for memory.
- `memory_context` is transient retrieval context (k=5 ranked facts), injected
  into the prompt by `call_model`; it IS part of checkpointed state values
  (PostgresSaver persists full state per node, `graph.py:287`), so each turn's
  checkpoint stores it — no schema migration needed (JSONB), but it is
  duplicated per checkpoint (Section 12, Y8, mild).
- Checkpointer: `PostgresSaver` — state transitions are checkpointed, not
  mutated in place; message history per thread is append-only via the reducer.
- Graph wiring (`graph.py:266-289`): `retrieve_memory` → `agent` →
  (`should_continue` → `action` | END) → `agent` loop.

---

## 8. STREAMING + MEMORY

Sequence in `chat_stream_endpoint` (verified `chat.py:880-972`):
1. Streaming loop consumes `graph.stream` chunks → SSE `content` events (chunks
   are never gated on memory work — memory only read pre-generation).
2. Post-loop: grounding, validation, trace, `record_id`.
3. `persist_assistant(COMPLETED)` (`:895`) — committed before extraction starts.
4. `schedule_extraction(...)` (`:899`) — thread starts here.
5. `[DONE]` queued in `finally` (`:964`) — extraction thread runs concurrently
   with `[DONE]` delivery; **never blocks** it (own thread, own session,
   separate engine path).

Sync path (`chat.py:416-420`): persist then `schedule_extraction` — identical
ordering guarantee.

Races analyzed:
- **Turn-boundary race**: if the user submits the next message before the
  previous extraction thread finishes, the thread may read the new user message
  with the old assistant message (its `list_messages` snapshot happens after
  the new message is persisted). Impact: extraction of a mismatched pair →
  spurious/duplicate candidates only. Mitigated by Gate 1 (new turn must pass
  eligibility), throttle (sequence-based), and dedupe. Chat correctness
  unaffected. Window is small; severity low (Y9).
- **Concurrent extractions in one session** (two threads): both read last pair,
  both call `create_memory` → dedupe makes writes idempotent; extra LLM cost
  only.
- **Throttle concurrency**: guarded by `_throttle_lock`; safe in-process; not
  coordinated across workers (Y1).

---

## 9. FAILURE ISOLATION MATRIX

| # | Failure | Layer | Chat impact | Memory impact | Handling |
|---|---|---|---|---|---|
| F1 | Extraction LLM fails (provider down / quota) | Gate 2 | **None** | None written | retry once → batch dropped, logged (`extractor.py:150-154`) |
| F2 | Malformed LLM output | Gate 2/3 | **None** | None written | retry once → Gate 3 drop |
| F3 | Any exception in extraction thread | run_extraction | **None** (thread never raises; `extractor.py:261-266`) | None written (or partial, see F4) | caught, `memory_extraction_failed` error log, return 0 |
| F4 | `create_memory` fails mid-batch (e.g., ownership violation) | Store | **None** | Earlier candidates of the batch already committed (per-entity commits, `memory.py:356`) — partial batch possible | exception propagates to F3 handler |
| F5 | Main LLM fails mid-stream | Graph | Error SSE event + failed assistant message persisted (`chat.py:949-962`) | Extraction NOT scheduled (only on success path `:895-899`) — correct fail-closed for memory | graceful |
| F6 | Retrieval/embedding failure (memory read) | Graph node | Degrades to empty `memory_context` | n/a | try/except, fail-open (`test_retrieve_memory_node.py:102` covers) |
| F7 | Embedding provider missing on write | Store | **None** | Entity written without embedding (`memory.py:342` — `embed is None` skips); conflict detection silently disabled (`check_potential_conflicts` cosine path needs embed) | documented degradation; search backfills lazily |
| F8 | Config flag off (`MEMORY_V2_GRAPH=false`) | run_extraction | **None** | Nothing | early return (`extractor.py:205`) |
| F9 | Ollama unavailable for chat AND extraction | Gate 2 + chat | Chat fails with its own error path | Extraction never reached (F5 ordering) | per-layer isolation holds |

Overall: chat can never fail because of extraction; extraction can never fail
because of chat; every failure is logged with structured keys
(`extraction_llm_failed`, `extraction_gate3_secret_dropped`,
`memory_extraction_done`, `memory_extraction_failed`).

---

## 10. COST & PERFORMANCE

- **Per-turn LLM cost** (worst case): 1 main generation + (extraction LLM call
  when eligible). Eligibility passes for most substantive turns, but the
  throttle caps at 1 extraction per 3 turns per session.
- **Extraction model**: gpt-4o-mini on OpenAI (matches chat default); on Ollama
  the extraction model IS the chat model (qwen3:8b) — no separate small model,
  so extraction competes for the same Ollama inference slot (Y10). Temp 0.
- **Token bound**: the exchange is exactly the last user + last assistant
  message (`extractor.py:235`); statements capped at 500 chars by Gate 3, but
  **the exchange itself has no length guard** — a very long turn is sent
  in full (Y11, mild; bounded by chat context limits anyway).
- **Embedding cost**: 1 embed per written candidate (only on pending writes);
  1 embed per retrieval query; lazy backfill on search. With `openai` provider:
  trivial. With `none` provider: embeddings skipped entirely (F7).
- **Threading**: 1 daemon thread per eligible turn; thread holds a DB session
  for the duration of the LLM call (minutes when Ollama is slow/down) →
  unbounded thread + session accumulation under chat load (Y3).
- **No batching**: candidates are written one by one (N commits per run, Y2);
  no queue/batch across sessions; no circuit breaker around the provider
  (Y12).
- **Retry economics**: only 1 retry, only for malformed output — no runaway
  cost. `MAX_CANDIDATES=3` bounds output. Deterministic gates (1, 3) cost
  nothing.

---

## 11. TEST COVERAGE

Full suite: **252 passed / 2 failed** (the 2 failures are pre-existing
live-OpenAI quota tests, unrelated to V2.2). `tests/conftest.py` pins
`LLM_PROVIDER=openai`; `tests_live/` (5 Ollama tests) excluded from testpaths.

| Area | File | Tests | Coverage of |
|---|---|---|---|
| Extraction gates | `tests/learning/test_extraction.py` | 12 | eval exclusion, filler, commands, general chat, substantive pass, throttle, Gate 3 valid/batch-atomic/secret, run_extraction integration (writes pending, skips eval, malformed → nothing) |
| Memory entity store | `tests/learning/test_memory_entities.py` | 25+ | create/dedupe, source→authority/confidence defaults, extracted→pending, conflict matrix (weaker/equal/higher authority, confidence), supersede, TTL, expiry sweeper, search ranking/backfill/k-cap, ownership |
| Explicit memory tools | `tests/learning/test_memory_tools_v2.py` | 6 | remember/fact/session, forget, ownership, user-wide fallback |
| Retrieve node | `tests/agent/test_retrieve_memory_node.py` | 5 | flag off, ranked injection, no identity, failure→empty, no matches |
| Episodic recall | `tests/learning/test_episodic.py` | 13 | transcript loading, consolidation, recall filtering, summarizer failure, ownership threading |
| Guardrail | `tests/agent/test_guardrail.py` | 10 | memory tools auto-allowed, secrets never remembered, empty/oversized facts, session_id bound |
| Chat endpoints | `tests/chat/` | — | **extraction neutralized**: `tests/chat/conftest.py:49,238` fakes `schedule_extraction` → no endpoint-level extraction test runs |
| Live Ollama | `tests_live/test_ollama_live.py` | 5 | skipped without reachable Ollama |

Gaps: no end-to-end test that schedules extraction through the chat endpoint
and asserts entities; no test for the turn-boundary race (Y9); no test for
partial-batch failure (F4). These are YELLOW, not RED — the gate-level unit
tests plus the real-store integration tests in `test_extraction.py` cover the
logic that matters.

---

## 12. GREEN / YELLOW / RED ASSESSMENT

### GREEN — verified strengths
1. **Human governance intact**: extraction writes only `pending`; promotion is
   exclusively human (`promote_memory`, operator API). No auto-apply anywhere
   (`extractor.py:12-14`, `memory.py:305-309`).
2. **Failure isolation**: detached daemon thread, own session, never raises,
   never on request path (`extractor.py:194-285`); chat/stream cannot be
   blocked by memory work; `[DONE]` ordering verified (`chat.py:895-964`).
3. **Deterministic-first design**: gates 1/1b/3 are LLM-free; the only paid
   stage is Gate 2 with temp 0 + single retry.
4. **Defense in depth**: Gate 3 re-validates the LLM contract independently
   (count, length, domain allowlist, importance range, secret patterns from
   the guardrail module).
5. **No orphan artifacts**: every entity has lineage
   (`source_conversation_id`, `supersedes_id`, `conflicts_with_id`,
   `content_hash`, `version`) and identity fields (`models/memory.py:87-111`).
6. **Idempotent writes**: content-hash dedupe makes concurrent/raced
   extraction runs safe.
7. **Authority-aware conflicts**: supersede only when strictly higher
   authority AND ≥ confidence; otherwise `pending` + `conflicts_with_id`
   (`memory.py:329-354`) — no silent overwrite of history.
8. **Config-guarded**: `MEMORY_V2_GRAPH` flag; provider abstraction via
   `build_llm` with no hidden fallback.
9. **Correct ordering guarantees**: extraction scheduled only after assistant
   message commit and only on successful generation (F5, `chat.py:895-899`);
   sync path identical (`chat.py:416-420`).
10. **Test discipline**: gates, store conflicts, tools, retrieval node, and
    episodic paths all unit-tested; live Ollama smoke kept out of testpaths.

### YELLOW — operational hardening needed
1. **Throttle is in-memory** (`extractor.py:61-62`): resets on restart;
   per-process only — multi-worker deployments can double-extract (idempotent,
   but wasted LLM calls).
2. **Non-atomic batch persistence**: Gate 3 is batch-atomic, but writes are
   per-entity commits (`memory.py:356`) — a mid-batch failure leaves a partial
   batch (F4). Not corrupt, but violates the spirit of "batch-atomic" and
   makes `written=` counts misleading.
3. **Unbounded daemon threads**: one thread per eligible turn, held for the
   whole LLM call; no pool, semaphore, or queue (Y3). Under chat load with a
   slow Ollama, thread/session accumulation is possible.
4. **Candidate envelope has no model**: raw dicts (`extractor.py:188-190`)
   — mild Constitution friction (artifacts should be dataclasses/Pydantic);
   transient, not persisted, so low severity.
5. **Gate 1 ignores LLM intent results**: only `rule_classify` is consulted
   (`extractor.py:93-95`); misclassified intents pass or fail
   deterministically but sometimes wrongly (e.g., "I prefer X" is a durable
   preference that currently extracts — verified as eligible because no rule
   fires — but "tell me about X" preference statements may be skipped by
   KNOWLEDGE_EXPLAIN rules). Determinism is good; accuracy is unmeasured.
6. **No importance floor**: Gate 3 accepts `importance=0.0` → entities enter
   pending with 0 importance, possibly never retrieved after promotion.
7. **Silent gate-3 drops**: only the secret case logs (`extractor.py:186`);
   other batch drops return `[]` with no audit trail — bad observability for a
   "traceable" platform.
8. **memory_context duplicated in checkpoints**: transient retrieval context
   stored per node checkpoint (JSONB) — storage grows with turns; not
   evicted.
9. **Turn-boundary race** (Section 8): mismatched user/assistant pair possible
   on rapid consecutive requests; benign but wasteful.
10. **Extraction shares the chat model on Ollama** (`extractor.py:40`):
    qwen3:8b does both chat and extraction — latency contention and
    weaker structured-JSON reliability than gpt-4o-mini.
11. **No exchange length guard** (`extractor.py:235`): very long turns are
    extracted in full; token cost untracked.
12. **No circuit breaker / backoff** around the provider for the extraction
    path — a down Ollama causes every eligible turn to spawn a thread that
    burns connect-timeout twice.

### RED — none
No architectural violations found: lineage preserved, no in-place mutation of
artifacts, no orphan artifacts, no lifecycle skips (observe→measure→explain→
propose→validate→apply→operate all respected within V2.2 scope), no coupling
of UI to engines, no duplicate business logic, and no hidden state introduced
into persisted artifacts (throttle is explicitly operational, not a system of
record — `extractor.py:59-60`).

---

## 13. RECOMMENDATIONS (INSPECTION ONLY — NO CHANGES MADE)

**Priority 1 — reliability**
1. Move the throttle key out-of-process (DB/Redis row per session) so
   multi-worker deployments extract once per interval.
2. Bound extraction concurrency: a module-level semaphore (e.g., 2-4 slots)
   around `run_extraction`, dropping to `[]` when saturated.
3. Add a single-flight guard keyed by `session_id` to collapse concurrent
   extraction threads for the same session.

**Priority 2 — observability & correctness**
4. Log gate outcomes with structured keys for every rejection path (gate,
   reason, session) — not just secrets; make Gate 3 drops auditable.
5. Write candidates in a single transaction (batch write) so `written=N`
   is truthful and partial batches cannot occur.
6. Track and log extraction token/latency per run (`memory_extraction_done`
   with duration + exchange chars).

**Priority 3 — accuracy**
7. Consult the LLM intent result (not only rules) before declaring a turn
   ineligible; or explicitly document that rule-only classification is the
   product decision. Validate with a small golden-set eval.
8. Consider a separate small extraction model on Ollama
   (e.g., qwen2.5:3b-instruct or similar) to avoid contending with chat on
   qwen3:8b.
9. Add a token/length cap on the exchange before Gate 2.

**Priority 4 — hygiene**
10. Envelope candidates in a small dataclass/Pydantic model inside the
    extraction module (validated in Gate 3), keeping the raw-dict boundary
    inside `_extract_with_llm`.
11. Cap `memory_context` size before checkpointing (e.g., truncate
    retrieval context) to bound checkpoint growth.
12. Add tests: endpoint-level extraction scheduling (un-fake
    `schedule_extraction` in one integration test), turn-boundary race, and
    partial-batch failure (F4).

---
*End of audit — inspection only; no files were modified.*
