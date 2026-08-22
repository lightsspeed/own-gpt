# V2.2 P1 MEMORY EXTRACTION HARDENING REPORT

Date: 2026-08-15
Scope: Production hardening of memory-extraction EXECUTION only (audit P1 items
Y1/Y2/Y3/Y9 + requirements 1–12). No memory redesign, no P2/P3/P4, no schema
change, no new infrastructure dependency.

---

## 1. PREVIOUS ARCHITECTURE

- `schedule_extraction()` (chat.py:420 sync, :899 stream) created **one unbounded
  daemon thread per completed turn** (`extractor.py` old `schedule_extraction`).
- Throttle: in-process dict `session -> last extracted user-message sequence`,
  interval 3 turns, **per-process only** (`_throttle`/`_throttle_lock`).
- `run_extraction` resolved the extraction input as the **last** user +
  **last** assistant message in the conversation (walk over `list_messages`).
- No single-flight protection; no cross-worker coordination; no shutdown
  control; daemon threads died with the process.
- Extractors never failed the chat request (outer try/except, fire-and-forget).

## 2. PROBLEMS FOUND

1. **Unbounded thread creation** under chat bursts / slow providers (Y3).
2. **Throttle not shared across workers** — multi-worker deployments extract up
   to N× more often (Y1).
3. **No duplicate suppression** — two workers (or two rapid requests) could
   extract the same turn independently; correctness relied solely on
   `create_memory` dedupe (wasted LLM calls).
4. **Turn-boundary race (Y9)** — `run_extraction` read "last pair"; a
   concurrently-persisted next turn could be mixed with the previous assistant
   reply, extracting a mismatched pair.
5. **Shutdown nondeterminism** — daemon threads could be killed mid-write
   (writes were already transactional-safe, but execution state was unclear).
6. **Queue saturation / resource exhaustion** — no bound at all on pending work.

## 3. CHOSEN ARCHITECTURE

```
chat request thread                     extraction worker pool (per process)
─────────────────────                   ─────────────────────────────────────
chat.py: persist user msg (user_msg.id)
        ... generation, persist assistant
        schedule_extraction(session, user, project, user_msg.id)
              │
              ├─ coordinator.claim_turn(session, user_msg_id)   [Redis SET NX EX]
              │     └─ Redis down → in-process claim set (fail-open)
              │
              ├─ extraction_executor.submit(_run_task, ...)     [bounded pool]
              │     └─ queue full / stopped → release claim, log skip
              │
              └─ log scheduled / skipped_duplicate / skipped_concurrency

worker: _run_task → run_extraction(session, user, project, user_msg_id)
              │  turn = _turn_pair(messages, user_msg_id)   ← completed turn ONLY
              │  Gate 1 eligibility → coordinator.throttle_allowed(session, seq)
              │     [Redis Lua read-compare-set; down → in-process dict]
              │  Gate 2 LLM → Gate 3 validation → create_memory (pending/extracted)
              └─ finally: coordinator.release_turn(...)      ← best-effort
shutdown: executor.shutdown()  (main.py teardown; idempotent, never blocks)
```

Components:
- `app/learning/extraction/executor.py` — `BoundedDaemonExecutor`: N daemon
  worker threads (N = `MEMORY_EXTRACTION_MAX_CONCURRENCY`, default 2) + bounded
  queue (`MEMORY_EXTRACTION_MAX_QUEUE`, default 200). `submit()` never raises;
  `shutdown()` idempotent (stop accepting → drop queued → sentinels).
- `app/learning/extraction/coordinator.py` — `ExecutionCoordinator`: lazy Redis
  client (existing `redis==5.0.4`, same pattern as pipeline tracing) + Lua
  throttle script + in-process fallbacks. All ops fail open.
- `extractor.py` — turn-targeted `run_extraction(user_msg_id)`; `schedule_extraction`
  = claim → submit → release-on-failure.

## 4. WHY THIS ARCHITECTURE WAS SELECTED

- **Redis already exists in production** (compose `redis:7-alpine`, `redis==5.0.4`
  used by arq ingestion worker and pipeline tracing, `REDIS_URL` wired to web
  and worker). Requirement #3: "Do NOT introduce a new infrastructure dependency
  if an existing production dependency can safely provide the capability."
  A durable queue (Celery/RabbitMQ/Kafka/arq-for-extraction) was **not** justified:
  extraction is a best-effort side effect with idempotent writes — it needs
  coordination (dedupe, throttle), not delivery guarantees. Adding a durable
  queue would have added ops burden without correctness value.
- **Bounded daemon pool** is the smallest production-grade mechanism compatible
  with the synchronous FastAPI architecture (streaming already uses thread
  executors; `learning_collector` sets the fire-and-forget precedent). It
  preserves the existing daemon-thread exit semantics while bounding resources.
- **Lua script** gives atomic read-compare-set for the throttle — no TOCTOU
  window between GET and SET that two workers could slip through.
- **Claim at schedule time** (not run time) prevents duplicate enqueueing and
  queue-slot waste; release-on-completion + TTL covers crash cases.
- **Turn identity = `chat_messages.id`** (immutable integer PK of the user
  message that starts the turn) — requirement #2's "existing immutable
  identifier" — never a timestamp; survives renames/retries; unique per session.

### Tradeoffs (documented)
- Redis down → **fail-open to in-process state**: cross-worker duplicates are
  possible but end-state-safe (dedupe) and logged; availability is preserved.
- Single-flight TTL (300s) is a safety net, not a lock: an extraction running
  longer than TTL can be re-claimed by a duplicate schedule — idempotent writes
  keep this harmless.
- Queue is in-memory per process: worker restart abandons queued work (by
  design, see §8); no redelivery (not needed — idempotent + best-effort).
- Throttle marker persistence: a session idle for >24h (throttle TTL) resumes
  extraction on its next turn — intended crash-safety behavior.

## 5. DISTRIBUTED COORDINATION MECHANISM

Redis keys (namespace `memory:extraction:`):

| Purpose | Key | Value | Op | TTL |
|---|---|---|---|---|
| Single-flight claim | `memory:extraction:sf:{session_id}:{user_message_id}` | owner (`pid-<pid>`) | `SET NX EX` | `MEMORY_EXTRACTION_SINGLE_FLIGHT_TTL_SECONDS` (default 300) |
| Distributed throttle | `memory:extraction:throttle:{session_id}` | last extracted user-message sequence | Lua GET→compare→SET | `MEMORY_EXTRACTION_THROTTLE_TTL_SECONDS` (default 86400) |

Throttle Lua semantics (atomic):
```
last = GET key
if last == nil:  SET key seq EX ttl; return ALLOW
if seq - last >= interval: SET key seq EX ttl; return ALLOW
return DENY
```
- **Atomic**: single Lua script — no interleaving window.
- **TTL protected**: both keys expire; a crashed worker's claim/marker cannot
  block a session forever.
- **Worker crash**: claim expires after 300s; throttle marker after 24h.
- **Exception during extraction**: claim released in `finally`; writes already
  committed by `create_memory` remain (idempotent).
- **Process restart**: Redis state persists (correct — cross-worker truth);
  in-process fallback state resets (claims/throttle are per-process only when
  Redis is absent).

## 6. CONCURRENCY MODEL

- Per-process bounded pool: `MEMORY_EXTRACTION_MAX_CONCURRENCY` (2) daemon
  workers; `MEMORY_EXTRACTION_MAX_QUEUE` (200) pending tasks. Horizontal scale =
  N processes × pool size; Redis claims are global so the same turn is never
  extracted twice even across processes.
- Queue-full or stopped pool → `submit()` returns False → claim released, turn
  skipped with a log (extraction is best-effort; the turn is simply not
  extracted — chat unaffected).
- All shared state is lock-protected; `submit()`/`claim_turn`/`throttle_allowed`
  are safe from any calling thread (FastAPI request threads, stream threads).

## 7. SINGLE-FLIGHT / IDEMPOTENCY MODEL

- **Identity**: `(session_id, chat_messages.id of the turn's user message)` —
  immutable, never a timestamp. Extracts exactly the turn starting at that
  message plus its first completed assistant reply (`_turn_pair`).
- **Cross-worker**: Redis `SET NX EX` — only the first claimant enqueues.
- **Same-process (Redis down)**: in-process claim set under lock.
- **Re-execution safety**: `MemoryService.create_memory` content-hash dedupe
  (unchanged), authority/conflict/lineage/event-ledger rules untouched —
  re-running extraction for an already-extracted turn writes nothing new.
- **Failed extraction**: claim released; nothing reschedules automatically —
  the turn's facts are lost for that run (logged), matching the old semantics.

## 8. SHUTDOWN BEHAVIOR

Decision: **B — abandon safely, never block** (documented in executor.py and
main.py):

- `main.py` lifespan teardown calls `extraction_executor.shutdown()`:
  idempotent; stops accepting new work; **drops queued** tasks; wakes workers
  with sentinels (they exit); **in-flight extraction continues** on its daemon
  worker only while the process stays alive.
- Workers are daemon threads: a slow/offline LLM provider can never hang
  application shutdown.
- Re-execution is safe because: single-flight TTL lets a later legitimate
  schedule re-run the turn; `create_memory` is idempotent; writes are
  transactional per entity.
- No durable queue was introduced — a shutdown-lost extraction is an accepted,
  logged, best-effort miss (matching pre-existing fire-and-forget semantics).

## 9. FAILURE BEHAVIOR

| Failure | Behavior |
|---|---|
| Redis unavailable (claim/throttle/release) | log `memory_extraction_redis_unavailable`, fall back to in-process state — extraction proceeds |
| Claim lost to another worker | log `memory_extraction_skipped_duplicate`, return False — no work |
| Queue full / executor stopped | release claim, log `memory_extraction_skipped_concurrency`, return False |
| `run_extraction` raises | caught, logged `memory_extraction_failed`; claim released in `finally` |
| LLM provider fails | Gate 2 retry once → batch dropped (pre-existing) |
| `create_memory` fails | caught by `run_extraction`; already-committed entities remain (idempotent) |
| Turn not complete / unknown | log `memory_extraction_skipped_incomplete`, return 0 — never extracts partial content |
| Extraction LLM/queue path breaks | **chat response is already fully streamed + persisted + `[DONE]` delivered** — scheduling is off the critical path (verified by test I + live smoke) |

Chat can never fail because of extraction; extraction can never corrupt chat or
memory state.

## 10. CONFIGURATION (all `app/core/config.py`, env-driven)

| Setting | Default | Meaning |
|---|---|---|
| `MEMORY_EXTRACTION_MAX_CONCURRENCY` | 2 | concurrent extractions per worker process |
| `MEMORY_EXTRACTION_MAX_QUEUE` | 200 | pending extractions per worker process |
| `MEMORY_EXTRACTION_SINGLE_FLIGHT_TTL_SECONDS` | 300 | turn-claim lifetime (crash safety net) |
| `MEMORY_EXTRACTION_TURN_INTERVAL` | 3 | user turns between extractions, per session |
| `MEMORY_EXTRACTION_THROTTLE_TTL_SECONDS` | 86400 | throttle marker lifetime (crash safety net) |

Safe defaults for a single-worker docker-compose deployment (2 concurrent × 200
queued is ample; extraction is throttled to 1 per 3 turns per session). No
hard-coded deployment values.

## 11. FILES CHANGED

Modified:
- `app/core/config.py` — +5 settings (above)
- `app/learning/extraction/extractor.py` — turn-targeted `run_extraction`,
  `schedule_extraction` (claim→submit→release), `_turn_pair`, coordinator/
  executor wiring, structured skip/start logs; removed in-process-only throttle
- `app/api/endpoints/chat.py` — capture `persist_user_message()` result; pass
  `user_msg.id` at both schedule sites (sync :420, stream :899)
- `app/main.py` — `extraction_executor.shutdown()` in teardown
- `tests/learning/test_extraction.py` — updated to new signatures + coordinator
- `tests/chat/test_endpoints.py` — +1 streaming `[DONE]` test with real
  scheduling wired

New:
- `app/learning/extraction/executor.py` — `BoundedDaemonExecutor` + singleton
- `app/learning/extraction/coordinator.py` — `ExecutionCoordinator` (Redis +
  Lua + fallbacks) + singleton
- `tests/learning/test_extraction_execution.py` — 18 tests

Unchanged (verified via `git status`/`git diff`): `app/services/memory.py`,
`app/models/memory.py`, migrations, embeddings (dimension 1536), authority/
conflict/restore semantics, retrieval ranking, Ollama provider, chat streaming
protocol, API contracts, docker-compose, requirements.

## 12. TESTS ADDED

`tests/learning/test_extraction_execution.py` (18, all deterministic, sqlite,
FakeRedis mirroring the Lua script, no network/LLM):
- A bounded concurrency: max 2 running while 5 submitted (event-conditioned)
- queue-full → `submit` False; submit after `shutdown` → False
- B duplicate scheduling of the same turn → second skipped
- C concurrent duplicate scheduling (2 threads, barrier) → exactly 1 run
- claim/release semantics (in-process)
- D Redis claim atomic across two coordinators; TTL recorded; throttle
  interval + TTL on FakeRedis; Redis-down fails open to in-process state
- E single-flight TTL expiry → re-claim allowed; throttle TTL expiry → allowed
- F process-restart semantics (fresh coordinator = fresh in-process state)
- G extraction raising → schedule never raises, claim released
- H executor shutdown → schedule returns False, never raises
- J turn-targeted: extracts ONLY its own turn (later turn never leaks into the
  exchange); skips turns with no reply; skips turns with `failed` assistant
  reply (partial content never extracted); unknown turn id → no-op

`tests/chat/test_endpoints.py` (+1): streaming still delivers `[DONE]` when the
real scheduling path runs; schedule receives the immutable user-message id.

K (dedupe) and L (lifecycle) are covered by the unchanged existing suites:
`test_memory_entities.py` (25+) and `test_memory_api.py` — both green.

## 13. TEST RESULTS

- Targeted: `tests/learning/test_extraction.py` + `test_extraction_execution.py`
  → **30 passed**
- Chat: `tests/chat` → **48 passed** (incl. new `[DONE]` test)
- Full suite: **271 passed / 2 failed** — the 2 failures are the pre-existing
  OpenAI `credit_balance_exhausted` (429) quota tests in
  `tests/pipeline/test_pipeline.py`, byte-identical to the pre-change baseline
  (252/2 → 271/2, +19 tests). No lint/typecheck is configured (pyproject has
  pytest only); `python -m compileall` clean on all touched modules.

## 14. LIVE VERIFICATION (docker compose, real Redis)

Ran `smoke_p1.py` inside the `web` container (source mounted live via `.:/app`):
```
claim1=True claim_dup=False claim_next=True claim_after_release=True
throttle_10=True throttle_11=False throttle_13=True
executor_submit=True ran=[1] waited=True submit_after_shutdown=False
sched1=True dup=False after=True runs=[('smoke-e2e', 7), ('smoke-e2e', 7)]
SMOKE OK
```
Verified directly in Redis:
- `memory:extraction:sf:smoke-e2e:7` = `pid-184` (owner label), TTL 292s
  (300s default)
- `memory:extraction:throttle:smoke-p1` = `13` (last extracted sequence),
  TTL 86390s (86400 default)
All smoke keys deleted afterwards; no `memory:extraction:*` residue. The full
schedule path (claim → bounded enqueue → worker run → release → re-schedule
allowed) works end-to-end in the real deployment.

## 15. GREEN / YELLOW / RED ASSESSMENT

GREEN:
- Bounded concurrency + bounded queue, config-driven
- Single-flight across workers keyed on an immutable identifier
- Distributed throttle, atomic (Lua), TTL-protected, crash-safe
- Fail-open everywhere — chat can never fail because of extraction
- Turn-boundary safety: extraction input is exactly one completed persisted
  turn (partial/failed content excluded)
- Shutdown: deterministic, non-blocking, safe re-execution
- Idempotency/lifecycle/authority/conflict/lineage untouched (frozen)
- No schema change; no new infrastructure dependency
- Structured logs for every outcome:
  `memory_extraction_scheduled` / `_skipped_duplicate` / `_skipped_concurrency` /
  `_skipped_eligibility` / `_skipped_throttle` / `_skipped_incomplete` /
  `_started` / `_done` / `_failed` / `memory_extraction_redis_unavailable`

YELLOW (documented, accepted):
- Redis-down window: cross-worker duplicates possible until Redis recovers —
  fail-open by requirement; harmless via dedupe; logged
- Single-flight TTL shorter than a pathological extraction allows a later
  duplicate re-claim — safe via idempotent writes
- Queue is per-process/in-memory — restarts abandon queued extractions (by
  design, §8)

RED: none.

## 16. REMAINING P1 CONCERNS

1. No circuit breaker / backoff on the extraction LLM call itself (pre-existing;
   belongs to P2 observability scope per the audit, not P1 execution control).
2. Extraction LLM cost under Redis-down multi-worker duplicate runs — bounded,
   logged; mitigate later if it becomes a measured cost problem.
3. Throttle interval remains turn-based (unchanged semantics); a time-based
   variant would be a behavior change requiring product sign-off.

---

## STATUS

- **P1 COMPLETE** — all 12 requirements implemented, tested, and live-verified.
- **P2 should NOT begin yet** — P1 is the only authorized work; start P2 only on
  explicit instruction.
- **Architectural decisions requiring approval:**
  1. **Redis as the extraction coordination layer** — chosen per requirement #3
     (existing production dependency; no new infrastructure). Alternative would
     be a durable job queue (rejected: no delivery guarantees needed, idempotent
     writes make it unnecessary).
  2. **Shutdown choice B** — queued extraction abandoned on shutdown; in-flight
     work finishes only if the process stays alive (daemon workers); safe
     re-execution via TTL + dedupe. No durable retry queue.
  3. **TTL-based claims (not durable claims)** — crash safety comes from key
     expiry, not from a persistent job record; a duplicate re-claim after TTL
     expiry is possible and safe (idempotent writes).
