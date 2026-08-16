# V2.2 P2 MEMORY OBSERVABILITY AUDIT

Audit-only deliverable. No code, tests, config, schema, Docker, or dashboard
changes. Checkpoint: `8eeca8a` (V2.2 P1 hardening committed). Git tree clean.

Question this audit answers:

> If memory extraction is running in production, can an engineer understand
> what happened to every extraction attempt, where time was spent, why it
> failed/skipped, and whether the system is healthy?

Answer in one line: **partially** — every skip/failure is logged with reason,
but there is no metrics, no traces, no duration data, no correlation id, no
token/cost data, and the memory-write outcome is invisible. All evidence
below is file:line verified against the committed tree.

Every section distinguishes:

- **CURRENT BEHAVIOR** — what exists today (with file:line evidence)
- **RECOMMENDED P2 DESIGN** — what P2 should add (design only, not implemented)

---

## 1. Executive Summary

| Dimension | Verdict | Evidence |
|---|---|---|
| Structured logs | PARTIAL — kv-pair style, but no config, no JSON, no correlation id, some silent drops | §3, §7 |
| Metrics | NONE — no Prometheus/OTEL dependency, no counters/gauges/histograms anywhere | §3, §5 |
| Distributed traces | PARTIAL — LangSmith auto-tracing + Redis `PipelineTrace` exist for the RAG path; extraction is invisible to both | §3, §8 |
| Error classification | PARTIAL — log-message naming, no taxonomy, no counters, Gate 3 non-secret drops are silent | §3, §9 |
| Duration measurement | NONE in extraction (only request-level) | §3, §5 |
| Correlation / request id | BROKEN — `request_id` exists per request but is never propagated to extraction; extraction has no own id | §4 |
| Session id / user id / message id | PARTIAL — session + turn id in extraction logs; user id only in 2 lines; never together | §4 |
| Model / provider | PARTIAL — model constant `EXTRACTION_MODEL`, provider never logged | §3, §11 |
| Memory outcome | PARTIAL — MemoryEvent rows persist outcomes (STORED/CONFLICT/SUPERSEDED) but dedupe is silent and nothing is logged | §3, §9 |
| Retry information | PARTIAL — LLM retry attempt logged on final failure only | §3 |

**Strengths (preserve):**

1. Every scheduling decision and every gate skip is logged with a distinct
   machine-readable event name (`memory_extraction_skipped_*`,
   `memory_extraction_redis_unavailable op=...`).
2. The execution path **never logs message content** — no prompt/user text
   is emitted today (verified §13).
3. Coordination is fully instrumentable: `claim_turn` / `release_turn` /
   `throttle_allowed` are single choke points (`coordinator.py:118,138,153`)
   where P2 counters + latency hooks land with minimal surface.
4. `BoundedDaemonExecutor.queue_size` already exists as a property
   (`executor.py:89-91`) — the queue-depth gauge has a ready source.
5. `MemoryEntity.metadata_` (JSON) and `MemoryEvent.metadata_` (JSON) already
   exist on the persistence layer (`models/memory.py:119,143`) — correlation
   ids can be persisted as lineage without a schema migration.

**Major gaps (fix in P2):**

1. No metrics subsystem at all (§5).
2. No extraction duration anywhere; no in-flight counter; queue depth is
   never exposed (§3, §5).
3. Correlation is lost at four seams: middleware request_id is never read by
   chat/extraction (§4), stream path schedules from a threadpool thread
   (`chat.py:767,899,967`), Redis claim value is only `pid-<n>` (no id),
   and `MemoryEntity` stores `source_conversation_id` but never the
   `chat_messages.id` of the turn (§4).
4. Gate 3 non-secret rejections and LLM double-failure are silent
   (`extractor.py:265-266`); memory-service dedupe is silent
   (`memory.py:284-285`).
5. No logging configuration at all (level/format depend on the launcher;
   INFO events like `memory_extraction_scheduled` may be lost) (§7).
6. Extraction token usage is never read (`extractor.py:149-159` ignores
   `response_metadata`); no cost observability (§11).
7. Background thread breaks LangSmith context propagation — the extraction
   LLM call is a detached root run, not a child of the chat request (§8).

---

## 2. Current Extraction Architecture

```
User message
  → chat_persistence.persist_user_message        chat_persistence.py:155-182
      (returns user_msg; id = ChatMessage PK)    models/chat.py:44
  → response completes (sync / stream)
  → schedule_extraction(session_id, user_id,     chat.py:419-420 (sync)
                          project_id, user_msg.id) chat.py:898-899 (stream)
  → coordinator.claim_turn (Redis SET NX EX)     extractor.py:327; coordinator.py:118-136
      fail → skipped_duplicate (INFO)            extractor.py:328-332
      in-process fallback                        coordinator.py:131-136
  → extraction_executor.submit (bounded queue)   extractor.py:333; executor.py:71-82
      fail → release + skipped_concurrency (WARN) extractor.py:334-339
  → worker thread task (_run_task)               extractor.py:296-308
  → run_extraction (own DB session)              extractor.py:204-293
      turn resolution (_turn_pair)               extractor.py:103-117, 232
      Gate 1  _is_eligible (no LLM)              extractor.py:86-100, 245
      Gate 1b coordinator.throttle_allowed (Lua) coordinator.py:153-173; extractor.py:251
      Gate 2  _extract_with_llm (1 retry)        extractor.py:120-165, 263
      Gate 3  _validate_candidates (no LLM)      extractor.py:168-201, 264
      create_memory (idempotent, dedupe)         memory.py:241-358
        dedupe → return existing                 memory.py:274-285
        conflict → pending + CONFLICT event      memory.py:330-340, 353-354
        supersede → SUPERSEDED event             memory.py:345-349
        STORED event                             memory.py:351
      release_turn (best-effort; TTL is safety)  coordinator.py:138-149; extractor.py:308
```

Fail-open invariants (P1, preserved): Redis down → in-process fallback
(`coordinator.py:95-109,131-136,148-149,168-173`); queue full → skip with
WARNING (`extractor.py:333-339`); any exception → `memory_extraction_failed`
ERROR and return 0 (`extractor.py:288-293`); shutdown abandons queued work
(`executor.py:93-114`).

---

## 3. Observability Coverage Matrix

Legend: ✔ present · ✖ absent · ◐ partial. Evidence per cell.

| Stage (entry point) | Struct. logs | Metrics | Traces | Error class | Duration | Corr/req id | Session id | User id | Msg/turn id | Model/provider | Outcome | Retry |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HTTP request (sync) `chat.py:271-433` | ✔ `observability.py:36-42` | ✖ | ◐ LangSmith pipeline runs `pipeline.py:205,440` | ✖ | ✔ middleware `observability.py:33` | ✔ request_id `observability.py:25` | ◐ body-level, not logged | ◐ auth dep, not logged | ✖ | ✖ | ✖ | ✖ |
| HTTP request (stream) `chat.py:660-987` | ✔ same middleware | ✖ | ◐ same | ✖ | ✔ | ✔ | ◐ | ◐ | ✖ | ✖ | ✖ | ✖ |
| schedule_extraction `extractor.py:311-344` | ✔ `:328,335,340` | ✖ | ✖ | ◐ reason-in-name | ✖ | ✖ (no id) | ✔ `:329,337,341` | ✖ | ✔ `:329,337,341` | ✖ | ◐ True/False only | ✖ |
| Redis claim `coordinator.py:118-136` | ✔ warn `:130` | ✖ | ✖ | ◐ op label | ✖ | ✖ | ✔ (in key) | ✖ | ✔ (in key) | ✖ | ◐ bool | ✖ |
| Redis throttle `coordinator.py:153-173` | ✔ warn `:167` | ✖ | ✖ | ◐ | ✖ | ✖ | ✔ (in key) | ✖ | ✖ | ✖ | ◐ bool | ✖ |
| Executor queue `executor.py:71-82` | ✔ error `:69`; skip warn `extractor.py:335` | ✖ (queue_size property only `:90-91`) | ✖ | ◐ | ✖ (queue wait) | ✖ | ◐ via task args | ◐ | ◐ | ✖ | ◐ | ✖ |
| run_extraction `extractor.py:204-293` | ✔ `:234,246,252,258,283,289` | ✖ | ✖ | ◐ | ✖ | ✖ | ✔ | ◐ `:284,291` | ✔ | ✖ | ◐ written count `:285` | ✖ |
| Turn resolution `_turn_pair` `:103-117` | ✔ incomplete `:234` | ✖ | ✖ | ◐ | ✖ | ✖ | ✔ | ✖ | ✔ | ✖ | ◐ | ✖ |
| Gate 1 eligibility `:86-100,245` | ✔ `:246` | ✖ | ✖ | ◐ reason-in-name | ✖ | ✖ | ✔ | ✖ | ✔ | ✖ | ◐ | ✖ |
| Gate 1b throttle `:251` | ✔ `:252` | ✖ | ✖ | ◐ | ✖ | ✖ | ✔ | ✖ | ✔ | ✖ | ◐ | ✖ |
| Gate 2 LLM `:120-165` | ✔ warn `:161-164` | ✖ | ◐ LangChain auto-run only, detached (§8) | ◐ retry attempt | ✖ | ✖ | ◐ "session_batch_dropped" `:162` | ✖ | ✖ | ✖ (model const `:51`) | ◐ [] | ◐ attempt in log `:162` |
| Gate 3 validation `:168-201` | ◐ only secret-drop `:196`; non-secret drop SILENT `:265-266` | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ (even secret-drop lacks session) `:196` | ✖ | ✖ | ✖ | ✖ | ✖ |
| create_memory `memory.py:241-358` | ✖ (logger defined `:55`, never used) | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ `source_conversation_id` `:279` | ✔ param | ✖ (no msg id) | ✖ | ◐ entity/status `:305-309,339`; events `:348,351,353` | ✖ |
| Dedupe `memory.py:274-285` | ✖ silent `:284-285` | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ (returns existing) | ✖ |
| Conflict/supersede `memory.py:329-354` | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ MemoryEvent rows `:348,353` | ✖ |
| MemoryEntity/MemoryEvent persist `models/memory.py:87-143` | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✔ column `:99-101` | ✔ column `:91` | ✖ | ✖ | ✔ status/event rows (artifact of record) | ✖ |
| Completion/failure `extractor.py:283-293` | ✔ `:283,289` | ✖ | ✖ | ◐ | ✖ | ✖ | ✔ | ✔ `:284,291` | ✔ | ✖ | ◐ written count | ✖ |
| Shutdown `executor.py:93-114` | ✖ (no abandoned-count log) | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ none | ✖ |
| Ollama provider `llm_provider.py:57-70` | ✖ | ✖ | ◐ via LangChain | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ model from settings `:63` | ✖ | ✖ |
| OpenAI provider `llm_provider.py:37-54` | ✖ | ✖ | ◐ via LangChain | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ◐ model arg | ✖ | ✖ |

Global facts:

- **No metrics dependency**: `requirements*.txt` contain no
  prometheus/opentelemetry/sentry/otel package (grep verified).
- **No logging configuration**: no `basicConfig`/`LOG_LEVEL`/loguru in app
  runtime; only CLI scripts (`app/services/memory_legacy_import.py:192`,
  `app/evaluation/cli.py:23`, `app/evaluation/intent_accuracy.py:152`).
  INFO logs (e.g. `memory_extraction_scheduled`, `extractor.py:340-343`) are
  only emitted if the launcher configures INFO — which the app never does
  itself.
- **No contextvars / context propagation** anywhere in `app/` (grep
  verified) — background threads cannot inherit request tracing context.
- **memory.py contains zero log statements** — the entire memory service
  (create/dedupe/conflict/supersede/promote/restore, 752 lines) is silent.
  The only observability is the MemoryEvent artifact rows.

---

## 4. Correlation / Traceability Analysis

### 4.1 Can one extraction attempt be correlated across the chain today?

| Hop | Correlated today? | Evidence |
|---|---|---|
| chat request → message | ◐ | `request_id` per request (`observability.py:25`) is never joined to `ChatMessage.request_id` (`models/chat.py:51`, set at `chat_persistence.py:155-182`). The request thread's id and the message row are linked only by the middleware log line (path+status) and the client's own `request_id`. |
| message → extraction job | ✔ | `schedule_extraction(..., user_msg.id)` (`chat.py:420,899`) — the `ChatMessage` PK is the extraction turn id (`extractor.py:325-327`). |
| extraction job → Redis claim | ✔ | claim key embeds `session_id` + `user_msg_id` (`coordinator.py:62-63`); value is `pid-<n>` (`extractor.py:327`) — id present, but no request/trace id. |
| Redis claim → LLM call | ✖ | no id crosses into `_extract_with_llm` (`extractor.py:120-165`); LangChain run gets no parent context (detached thread, §8). |
| LLM call → memory creation | ✖ | `create_memory` receives only statement/domain/importance/session (`extractor.py:271-281`); no turn id, no extraction id, no tokens. |
| memory creation → MemoryEntity | ◐ | `source_conversation_id = session_id` (`extractor.py:279`; `models/memory.py:99-101`) — session level only, never the `chat_messages.id`. |
| MemoryEntity → MemoryEvent | ✔ | `_append_event` links `entity_id` (`memory.py:124-140`; `models/memory.py:130-143`). |
| HTTP request → any of the above | ✖ | `request.state.request_id` is read nowhere else (`observability.py:27` is the only setter; no other file reads it). Stream path schedules from a threadpool thread (`chat.py:767,899,967`) — even thread-local access would fail. |

### 4.2 Where correlation is lost (the four seams)

1. **Seam A — middleware → endpoint**: `request_id` stays in
   `request.state` (`observability.py:27`); chat endpoints never log it
   (all chat logs at `chat.py:179-1073` carry no req_id).
2. **Seam B — request thread → background executor**: `schedule_extraction`
   runs synchronously on the request path (sync `chat.py:420`) or in the
   stream threadpool thread (`chat.py:899` inside `stream_in_thread`
   `:767`, launched `run_in_executor` `:967`). No id is generated at
   schedule time; nothing is handed to the worker besides
   session/user/project/msg id (`extractor.py:333`).
3. **Seam C — executor thread → Redis/LLM/DB**: `run_extraction` has no
   context object; LangSmith context vars die at the thread boundary
   (no `contextvars` usage, grep verified).
4. **Seam D — memory write**: `create_memory` never receives the turn id;
   `MemoryEntity.metadata_` (`models/memory.py:119`) is written as `{}` by
   the extraction call (no `metadata=` passed, `extractor.py:271-281`).

### 4.3 RECOMMENDED P2 DESIGN — correlation model

Introduce one stable identifier and propagate it everywhere:

- **`extraction_run_id`** — `uuid4` string generated in
  `schedule_extraction` (the only place that runs on a thread that still
  has the request context), carried as a parameter into
  `_run_task` / `run_extraction` / `_extract_with_llm`.
- Written into:
  - Redis claim value (`coordinator.py:125-127`) alongside owner
    (`claim_turn(..., owner=f"pid-{os.getpid()}:{extraction_run_id}")`),
  - every extraction log line (`req_id`/`run_id` field),
  - `MemoryEvent.metadata_` (`memory.py:124-140`) and/or
    `MemoryEntity.metadata_` (`models/memory.py:119`) at
    `extractor.py:271-281` via the existing `metadata=` parameter
    (`memory.py:255,324`),
  - the LangSmith run metadata dict if/when extraction is traced (§8).
- **Request-level link**: the middleware id (`observability.py:25`) should
  be passed into `schedule_extraction` as `request_id` and included in the
  `extraction_run_id` metadata — or, simpler and cheaper, the middleware
  should be widened to also attach `X-Request-ID` on the request side
  (it currently only sets the response header, `:35`).
- **Persistence-level link**: store `turn_message_id` (the
  `chat_messages.id`) in `MemoryEntity.metadata_` — closes Seam D without a
  schema change (the platform constitution allows `metadata_` as a
  documented artifact field; no migration required).

**Privacy constraint (applies to the whole design)**: `session_id` and
`user_id` may be sensitive. Recommended treatment:
- logs: keep `session_id` (operationally necessary, already the convention)
  but **stop logging raw `user_id`**; emit a short hash
  (`sha256(user_id)[:8]`) where user identity must appear;
- metrics: never as labels (§6);
- Redis claim keys already embed session + msg id (necessary for
  single-flight) — leave as-is (short TTL, 300 s, `config.py:113`), but
  never echo their contents into metrics or dashboards.

---

## 5. Metrics Design

### 5.1 CURRENT BEHAVIOR

No runtime metrics exist. The only counters in the repo are offline
evaluation scripts (`app/evaluation/analytics.py:14-22`) and learning-ledger
dashboards (`app/learning/api/telemetry.py:67-110`) — none touch extraction.
The single ready-made signal is `BoundedDaemonExecutor.queue_size`
(`executor.py:90-91`), which nothing reads.

### 5.2 RECOMMENDED P2 DESIGN — exact metric set

Namespace: `owngpt_memory_extraction_*`. Instrumentation points are single
chokepoints, so surface stays small.

**Scheduling (Counter) — instrumented at `extractor.py:311-344`:**
- `extraction_scheduled_total` — after `submit` True (`:340`)
- `extraction_skipped_total{reason=...}` — bounded reason set: `duplicate`
  (`:328`), `concurrency`/queue-full (`:335`), `disabled`/no-turn-id (`:325`)
- `extraction_claim_failed_total{reason=redis_error|inprocess_dup}` — from
  `claim_turn` (`coordinator.py:123-136`)

**Coordination (Counter + Histogram) — `coordinator.py`:**
- `extraction_coordination_redis_unavailable_total{op=claim|release|throttle}`
  (`:130,147,167`)
- `extraction_coordination_redis_latency_seconds{op=...}` (histogram around
  the Redis calls `:125-127,145,160-164`)

**Execution (Counter/Gauge/Histogram) — `extractor.py:204-293`:**
- `extraction_started_total` (`:258`)
- `extraction_completed_total` (`:283`)
- `extraction_failed_total{reason=exception}` — bounded reason extraction
  from the catch block (`:288-293`)
- `extraction_duration_seconds` (histogram: claim→done, i.e. covering queue
  wait + LLM + persistence)
- `extraction_inflight` (gauge: inc `:258`, dec in `finally` of `_run_task`
  `:305-308`)
- `extraction_turn_incomplete_total` (`:234`), `extraction_eligibility_rejected_total` (`:246`), `extraction_throttled_total` (`:252`)

**Gates (Counter):**
- `extraction_gate3_rejected_total{reason=format|domain|importance|count|secret}`
  — replaces the current silent return (`:265-266`) and the secret-only log
  (`:196`)
- Gate 2 failure is covered by `extraction_llm_errors_total` below.

**LLM (Counter/Histogram) — `extractor.py:120-165`:**
- `extraction_llm_calls_total{provider,model}`
- `extraction_llm_errors_total{provider,model,attempt=1|2}` (both failures
  `:160-164`)
- `extraction_llm_duration_seconds{provider,model}` (histogram around
  `model.invoke` `:149`)
- `extraction_tokens_total{provider,model,kind=input|output}` from
  `reply.response_metadata` (§11)

**Memory outcome (Counter) — a thin, non-invasive wrapper:**
- Either instrument inside `create_memory` (preferred: it is the single
  chokepoint for all memory writes, `memory.py:241-358`) or have the
  extraction loop inspect the returned entity. Must distinguish:
  `memory_created_total{status=pending|active}` (`:311-327,339`),
  `memory_deduplicated_total` (`:284-285`),
  `memory_conflict_total` (`:339-340,353-354`),
  `memory_superseded_total` (`:345-349`),
  `memory_embedding_failed_total` (embedding exceptions in the loop,
  `extractor.py:270-281`).

**Queue (Gauge) — `executor.py`:**
- `extraction_queue_depth` — read `queue_size` (`:90-91`) on a cadence
  (e.g. a `/metrics` scrape-time gather or a light loop in the executor)
- `extraction_queue_capacity` — constant `settings.MEMORY_EXTRACTION_MAX_QUEUE`
  (`config.py:112`)
- `extraction_worker_utilization` — 1 if a worker is busy. Derive without
  new state: `utilization = inflight / max_workers` from the in-flight
  gauge + `config.py:111`.

### 5.3 Explicitly rejected from the proposed list (audit verdict)

- `extraction_claim_conflict_total` vs `redis_claim_*` — merged into
  `extraction_claim_failed_total{reason}` and the coordination counters;
  separate counters would double-count the same event.
- `redis_fallback_total` — same event as
  `extraction_coordination_redis_unavailable_total`; keep ONE counter with
  `op` label.
- `extraction_skipped_total` variants per gate — the gate counters above
  already carry the reason; a separate skip counter adds no information.
- `extraction_worker_utilization` as a dedicated tracked value — derive it;
  a new gauge requires state that can drift.
- Any per-stage duration histogram beyond coordination/LLM/total — three
  histograms are enough to answer "where was time spent" (queue wait is
  total − llm − persistence); more buckets = more surface for zero value.

### 5.4 Transport

**CURRENT**: none. **RECOMMENDED P2 DESIGN**: `prometheus-client` +
a `/metrics` endpoint (FastAPI route, guarded) is the minimal viable
option (no new infra; matches "no new infrastructure unless strictly
required by observability"). OTLP/OTel is listed P2.2 and must be
introduced behind the same instrumented chokepoints so it is a transport
swap, not a re-instrumentation.

---

## 6. Cardinality Analysis

### 6.1 MUST NEVER become Prometheus labels (with reasons)

| Value | Source today | Why forbidden |
|---|---|---|
| `user_id` | `memory.py:91`; logged at `extractor.py:284,291` | Unbounded: grows with every user; identifies individuals (PII) and is personally addressable; breaks Prometheus memory/cardinality limits; dashboards would leak identity. |
| `session_id` (conversation id) | claim key `coordinator.py:63`; logs everywhere | Unbounded (one per conversation); embeds per-user activity; cardinality explosion at chat rates. |
| `message_id` / `turn_id` (user_msg.id) | claim key `coordinator.py:62`; logs | Unbounded (one per user message); the hottest dimension in the system. |
| `request_id` / `extraction_run_id` | proposed | One per attempt — by definition unbounded. Keep in logs/traces/Redis values, never labels. |
| `memory_id` | `MemoryEntity.id` `models/memory.py:90` | One per memory row; also unbounded and meaningless as an aggregation key. |
| arbitrary error messages / exception strings | `extractor.py:162,291` | Exception text is unbounded and noisy; would create new series per unique message. |
| raw prompts / memory statements | Gate 3 candidates `extractor.py:182-201` | Content leakage; unbounded; strictly prohibited by the constitution and this audit's privacy rules. |
| `domain` (memory domain) | `DOMAINS` | Not prohibited, but bounded ~10 values (`models/memory.py` DOMAINS); harmless as a label, yet adds no extraction insight — reject to keep the set small. |

### 6.2 RECOMMENDED P2 DESIGN — safe label set (all bounded)

- `provider` — `{"openai","ollama"}` (bounded, `llm_provider.py:86-90`)
- `model` — bounded by the model allowlist (`config.py:62-63`) + Ollama
  default (`config.py:39`); validate at instrumentation so free-text never
  reaches Prometheus
- `gate` — `{"1","1b","2","3"}`
- `reason` — fixed enum per counter (e.g. skip reasons:
  `duplicate|concurrency|disabled`; gate3: `format|domain|importance|count|secret`)
- `status` — `{"pending","active","superseded"}` (`models/memory.py:103`)
- `outcome` — `{"stored","deduplicated","conflict","superseded"}`
- `op` — `{"claim","release","throttle"}`
- `kind` — `{"input","output"}`
- `attempt` — `{"1","2"}`

Every label value set is declared in the metrics module as a frozen
`enum`/`frozenset`; the instrumentation **asserts membership** before
incrementing — high-cardinality drift fails tests, not production.

---

## 7. Structured Logging Design

### 7.1 CURRENT BEHAVIOR

- Format: hand-written kv-pairs, consistent naming
  (`memory_extraction_<event>`), which is searchable — but with no
  structured serializer, no JSON, no envelope (no `timestamp`/`level`
  guaranteed; stdlib adds them only per launcher config).
- No logging configuration anywhere in the app (§3 global facts) — level
  and format are whatever launches the process. `INFO` events like
  `memory_extraction_scheduled` (`extractor.py:340-343`) are dropped under
  default `WARNING` roots.
- Noise: `memory_extraction_skipped_*` INFO lines fire on every eligible
  skip — expected traffic, fine at INFO, but there is no way to rate-limit
  or sample them.
- Missing context:
  - `extraction_gate3_secret_dropped` (`extractor.py:196`) has NO
    session/turn — the only Gate-3 line and it cannot be traced to a turn.
  - `memory_extraction_done` has `session`, `user`, `turn`, `written`
    (`:283-286`) but no duration, no provider/model, no tokens.
  - `memory_extraction_failed` (`:288-293`) logs the raw exception and
    traceback but no attempt count, no stage ("where" it failed).
  - `memory_extraction_task_error` (`executor.py:69`) logs the exception
    but not which turn it belonged to — the worker loses task identity.
  - `executor.shutdown` (`executor.py:93-114`) drops queued tasks with no
    log of how many were abandoned.
- Sensitive data today: none of the message content is logged (§13); but
  `user_id` appears raw at `extractor.py:284,291`.

### 7.2 RECOMMENDED P2 DESIGN — field contract

One envelope: `{ts, level, logger, event, req_id?, run_id?, session, turn?,
user_hash?, duration_ms?, provider?, model?, reason?, ...}`. Fixed required
fields on every extraction event: `event`, `session`, `turn`,
`run_id` (after §4.3). Optional per event: `user_hash` (sha256 prefix —
never raw user id), `duration_ms`, `provider`, `model`, `reason`,
`attempt`, `written`.

Level assignment:

- **INFO**: `scheduled`, `started`, `done` (with duration + written),
  `skipped_*` (reason variants).
- **WARNING**: `redis_unavailable` (fail-open path taken), `skipped_concurrency`
  (queue full — capacity pressure), `llm_failed` attempt 1 (transient),
  `gate3_secret_dropped` (now with session/turn), `task_error` (now with
  turn + run_id).
- **ERROR**: `failed` (with stage + bounded `reason` enum, and
  `exc_info=True` only where traceback is useful), `llm_failed` after
  attempt 2 (retry exhausted), `memory_write_failed` (new — distinguishes
  DB failure from LLM failure, §9).

Fix-list (design, not code): JSON formatter + `LOG_LEVEL` setting in
`config.py`; attach session/turn to the Gate-3 secret line; add
abandoned-count to shutdown; add duration to `done`; carry run_id through
the executor task (removes the anonymous `task_error`).

---

## 8. Distributed Tracing Analysis

### 8.1 CURRENT BEHAVIOR — what tracing exists

Two independent, RAG-only mechanisms:

1. **LangSmith** (`app/core/langsmith.py`): client init `:22-35`,
   `traceable` decorator `:38-53`, manual `RunTree` helper `:56-92`;
   enabled only when `LANGCHAIN_API_KEY` is set (`:100-102`, env vars
   `:104-107`). Decorated stages: intent `intent.py:234`, rewrite
   `rewrite.py:75`, retriever `retriever.py:91`, reranker `reranker.py:80`,
   planner `planner.py:31`, confidence `confidence.py:75`, validation
   `validation.py:125`, router `router.py:62`, source validator
   `source_validator.py:36`, evidence builder `evidence_builder.py:60`,
   whole-pipeline `pipeline.py:205,440`.
2. **Redis PipelineTrace** (`app/agent/pipeline/tracing.py`): dataclass
   `:49-136` (trace_id, session_id, per-stage ms `:94-103`, tokens
   `:108-109`, model `:112`); stored per session with 7-day TTL `:146-175`,
   key `trace:{session}:{trace_id}` `:167`; stored at
   `chat.py:721-722` (`_pipeline.tracer.store(ctx.trace)`).

### 8.2 Where spans disappear for extraction

- `run_extraction` is **not** decorated with `traceable`; no RunTree, no
  OTel span exists anywhere in `app/learning/extraction/*` (grep
  verified).
- The extraction LLM call `model.invoke(payload)` (`extractor.py:149`)
  would auto-trace under LangSmith (it is a LangChain call) — but it runs
  on a **daemon worker thread** (`executor.py:53-58,67`) with no context
  propagation: LangSmith's context-var-based parent linkage is broken at
  the thread boundary (no `contextvars`/`copy_context` in the repo). The
  run becomes an **orphan root run**: exists, but cannot be joined to the
  chat request's run tree.
- Stream path: `schedule_extraction` itself executes on a threadpool
  thread (`chat.py:899` inside `stream_in_thread` `:767`, launched
  `run_in_executor` `:967`) — even the scheduler is off the async context.
- Redis coordination calls (`coordinator.py:125-127,145,160-164`) and DB
  writes (`memory.py:326-356`) are inside the same detached thread —
  nothing records their latency as spans.

### 8.3 RECOMMENDED P2 DESIGN — extraction trace tree

Preserve the no-new-infra rule: P2.1 does **not** add OTel; it wires
LangSmith's existing `traceable`/RunTree mechanism into extraction with
explicit parent context handoff:

```
extraction:<run_id>            (parent — wraps run_extraction)
 ├── coordination:<claim>      (Redis claim + throttle, coordinator.py)
 ├── queue:<wait_ms>           (from submit to worker start)
 ├── llm:<provider>/<model>    (extractor.py:149 — pass run as parent_run)
 ├── validation:<gate3>        (extractor.py:168-201)
 └── persist:<n_entities>      (create_memory loop, extractor.py:270-282)
```

Implementation sketch (design only): `schedule_extraction` captures the
current LangSmith run context when it runs on the request thread (or
generates `run_id` otherwise); the context object travels as a parameter
with `run_id`; `_run_task`/`run_extraction` create the parent run in the
worker thread with the captured parent linkage (LangSmith accepts
`parent_run` explicitly — `langsmith.py:58-61` already supports it).
Redis/DB work gets child spans only if their libraries participate; P2.2
may add an OTel bridge behind the same hook.

Fallback contract: tracing must never raise and must never block — the
existing `traceable`/`create_trace` silent-fallback pattern
(`langsmith.py:50-53,83-92`) is the model. When LangSmith is disabled,
`run_id` still propagates through logs + metadata (§4.3).

---

## 9. Failure & Error Classification

### 9.1 CURRENT BEHAVIOR

Error classes are implicit in log-message names; there is no taxonomy
code, no counter, and no machine-readable classification:

| Failure mode | What happens today | Observability today | P2 exposure | Severity |
|---|---|---|---|---|
| Redis unavailable | `claim`/`release`/`throttle` log `redis_unavailable` and fall back to in-process state (`coordinator.py:130,147,167`; fail-open `:27-33`) | WARNING logs; no counter; no latency | `extraction_coordination_redis_unavailable_total{op}`, latency histogram | P1 (fail-open protects chat; but cross-worker dedupe degrades) |
| Redis latency | no timing; request path not affected (only coordination) | none | `extraction_coordination_redis_latency_seconds` | P2 |
| Queue full | `submit` returns False (`executor.py:81-82`) → release + `skipped_concurrency` WARNING (`extractor.py:334-339`) | WARNING per event; no gauge | `extraction_queue_depth` gauge + saturation alert | P2 (capacity pressure; extraction silently degrades under load) |
| Executor worker failure | defensive catch logs `task_error` with traceback (`executor.py:68-69`) | ERROR, no turn identity | log run_id/turn; counter `extraction_failed_total{reason=worker}` | P1 |
| Extraction timeout | **none** — no timeout configured on `ChatOpenAI`/`ChatOllama` (`llm_provider.py:47-54,62-70`); a hung LLM occupies a worker indefinitely | none | histogram tail + `submit`-side watchdog counter in P2.3; prefer bounded per-call timeout | P1 (workers are scarce: 2, `config.py:111`) |
| Ollama unavailable | `model.invoke` raises → `extraction_llm_failed` WARNING (`extractor.py:160-164`), retry once, batch dropped silently (`:265-266`) | WARNING ×2 max, no counter | `extraction_llm_errors_total{provider=ollama}` | P1 |
| OpenAI unavailable / quota | same path; quota errors (e.g. 429 `credit_balance_exhausted` — seen in pipeline tests) | same WARNING; error text is the exception string | same counter + reason=quota subclass | P1 (cost control) |
| Invalid LLM output (malformed JSON twice) | `_extract_with_llm` returns `[]`; **silent** drop at `extractor.py:265-266` | none after the warnings | `extraction_gate3_rejected_total{reason=format}` | P1 (invisible today) |
| Gate 3 rejection (domain/importance/count) | `_validate_candidates` returns `[]`; **silent** (`:265-266`) | none | `extraction_gate3_rejected_total{reason=...}` | P1 |
| Database failure | caught at `extractor.py:288-293` → `memory_extraction_failed` ERROR with traceback | ERROR, no stage classification | `extraction_failed_total{reason=db}`; distinguish from LLM failures | P1 |
| Memory dedupe | returns existing entity silently (`memory.py:284-285`) | none | `memory_deduplicated_total` | P2 (informational) |
| Conflict | entity stays `pending` + CONFLICT event (`memory.py:339-340,353-354`) | MemoryEvent row only | `memory_conflict_total` | P2 (informational) |
| Process shutdown | queued tasks dropped; in-flight daemon work not guaranteed (`executor.py:93-114`, module docstring `:12-15`) | **no log of abandoned count** | log `shutdown dropped=<n> in_flight=<n>` | P2 (debugging aid) |

### 9.2 RECOMMENDED P2 DESIGN — taxonomy

Enum `ExtractionFailureReason`: `coordination_redis`, `queue_full`,
`worker_error`, `llm_error`, `llm_quota`, `llm_timeout`, `invalid_llm_output`,
`gate3_format`, `gate3_domain`, `gate3_importance`, `gate3_count`,
`gate3_secret`, `db_error`, `embedding_error`, `turn_missing`.
- Logs: add `reason=<enum>` field to every skip/failure line.
- Metrics: `extraction_failed_total{reason}`, `extraction_gate3_rejected_total{reason}`.
- The catch block at `extractor.py:288-293` becomes the classifier:
  exception → `reason` (db vs llm vs unknown), never the raw string as a
  label (§6).

---

## 10. SLO / SLI Recommendations

Context that shapes targets: chat availability > memory extraction;
extraction is fail-open; the subsystem is best-effort and detached; the
worker pool is small (2 workers, 200 queue — `config.py:111-112`).

| SLI | Definition (draft) | Initial SLO (window) | Rationale |
|---|---|---|---|
| Scheduling success | `scheduled / turns_with_msg_id` | ≥ 99.5% (28d) | Fail-open means skips are mostly benign, but a drift (e.g. Redis down for days) must surface |
| Extraction completion | `(done + terminal skip) / started` | ≥ 95% (28d) | LLM failures are the main loss; 5% headroom for provider flakiness on a free/offline stack |
| Coordination health | `redis_unavailable / claims` | < 1% (7d) | Above 1% = Redis degraded; chat unaffected but cross-worker dedupe weakened |
| Extraction latency | p95 of `extraction_duration_seconds` | < 30 s OpenAI / < 90 s Ollama (7d) | Local Ollama on 8B models is slower; do not alert on this alone |
| Queue saturation | `queue_depth / 200` p95 over 5 min | < 80% (7d) | Sustained saturation = extraction backlog under chat load |
| Memory write health | `memory_write_failures / starts` | < 1% (7d) | DB/embedding failures are the only errors that lose data |
| Pending-memory accumulation | `status=pending` growth rate | trend alert, no hard SLO | Pending is by design (human approval); only sustained growth with zero promotions warrants attention |

Alerting rules (initial, intentionally modest):

- **ERROR**: `redis_unavailable` rate > 1% over 1 h; `failed{reason=db}`
  > 0 over 15 min (2 consecutive); queue saturation > 80% for 30 min;
  scheduling success < 99% over 24 h.
- **WARNING**: p95 latency breach; LLM error rate > 10% over 1 h;
  `llm_quota` counter increment (cost control).
- **Never alert on**: gate rejections (expected), throttle skips
  (expected), individual latency spikes, pending-memory level alone.
- Chat-related errors remain out of extraction's SLO set entirely.

---

## 11. Cost Observability

### 11.1 CURRENT BEHAVIOR

- Extraction model: `EXTRACTION_MODEL = settings.LLM_MODEL` on Ollama,
  `gpt-4o-mini` otherwise (`extractor.py:51`); built via `build_llm`
  (`:129`; `llm_provider.py:73-93`).
- Token usage is **never read**: `_extract_with_llm` uses only
  `reply.content` (`extractor.py:149-159`); `response_metadata` is ignored.
- The only cost accounting in the platform is learning-record based:
  constants at `telemetry.py:22-24` and `usage_totals` at
  `telemetry.py:84-89` derive from `LearningRecord` rows built from RAG
  `PipelineTrace` tokens (`builder.py:57-58`). Extraction calls never
  create records → **invisible to cost tracking**.
- `ChatMessage.model` (`models/chat.py:48`) records the chat model, not
  the extraction model.
- No API calls were made during this audit.

### 11.2 RECOMMENDED P2 DESIGN

- Capture usage from the invocation result: OpenAI exposes usage in
  `reply.response_metadata["token_usage"]` (`extractor.py:149`); Ollama
  exposes prompt/eval counts in its metadata where available — fall back
  to `usage_metadata` absent.
- Counters: `extraction_tokens_total{provider,model,kind=input|output}` +
  `extraction_llm_calls_total` → derive per-day cost in a dashboard using
  the existing price constants (`telemetry.py:22-24` — keep them in ONE
  place, move/extend as `COST_PER_1K_*` map keyed by provider/model).
- Ollama volume: calls + tokens counters are the local-inference volume
  signal; no dollar conversion.
- Do not call OpenAI during measurement; instrumentation is passive.

---

## 12. Grafana Dashboard Design

Conceptual design only — not created. One dashboard, three rows.
"Useful" judgment per panel:

**Row 1 — Health (all useful):**
1. **Extraction success rate** — `(completed + terminal skips) / started`,
   stat panel. *Useful: the one-number health check.*
2. **Extraction duration p50/p95** — histogram quantiles. *Useful: catches
   queue buildup and provider slowness; do not alert on it alone (§10).*
3. **Queue depth + capacity** — gauge overlaid with 200 cap. *Useful: only
   panel that shows saturation pressure.*
4. **In-flight jobs** — `extraction_inflight`. *Useful: shows whether both
   workers (config.py:111) are saturated.*

**Row 2 — Behavior:**
5. **Gate rejection distribution** — stacked bars by `reason`.
   *Useful: distinguishes format/domain/secret issues; the secret bar is a
   security signal.*
6. **Memory creation vs dedupe vs conflict** — time series of the three
   counters. *Useful: dedupe/conflict trends indicate throttle effectiveness
   and semantic drift.*
7. **Provider/model usage** — calls breakdown by `provider`/`model`.
   *Useful: cost + Ollama-volume signal (§11).*
8. **Redis coordination failures** — `redis_unavailable_total{op}`.
   *Useful: the only cross-worker health signal; drives the <1% SLO.*

**Row 3 — Detail (moderately useful):**
9. **Pending-memory accumulation** — `status=pending` count over time
   (source: DB query or MemoryEvent metrics). *Useful but low-frequency;
   could be a weekly check instead of a live panel.*
10. **Recent extraction errors** — log panel filtered on
    `event=memory_extraction_failed` or `reason!=...`. *Useful during
    incident response; expensive as a permanent query — sample it.*

Least useful if space-constrained: pending-memory (slow-moving) and the
live error-log panel (replace with the error-rate panel).

---

## 13. Security & Privacy

### 13.1 CURRENT BEHAVIOR — exposure audit

| Asset | Logged today? | Verdict |
|---|---|---|
| Prompts / user text | No — `exchange` is built (`extractor.py:262`) but never logged; chat content not logged by middleware (`observability.py:36-42` logs path only) | SAFE |
| Memory statements | No — candidates are only validated (`extractor.py:179-201`); never logged | SAFE |
| User identifiers | `user_id` raw at `extractor.py:284,291` (done/failed) | RISK — raw user id in logs |
| Conversation id | `session_id` in every extraction log (`:234-341`) | ACCEPTED today (operational convention), but it is PII-adjacent; recommend hashing for non-essential lines |
| Message/turn id | `turn` in logs (`:329,337,341` etc.) | ACCEPTED — internal row id, no content |
| API keys / provider credentials | Never logged; `LLMProviderError` messages name env vars, not values (`llm_provider.py:41-44`); settings never dumped | SAFE — verify P2's exception scrubber keeps it that way |
| Exception strings | `error=%s` at `extractor.py:162,291`; `executor.py:69` | RISK-LOW — HTTP client exceptions can embed URLs/keys in pathological cases; scrub before logging |
| Redis trace payloads | `PipelineTrace.question` stores user query text in Redis 7d (`tracing.py:56,167-169`) | OUT OF SCOPE but adjacent — extraction adds nothing here today; P2 must not add prompts to traces |
| Request paths | middleware logs path (`observability.py:37-42`) — query strings excluded | SAFE |

### 13.2 RECOMMENDED P2 DESIGN — safe boundaries

1. Replace raw `user_id` in extraction logs with a stable short hash
   (`sha256(user_id)[:8]`) — enough for an engineer to pivot, not enough
   to identify.
2. `session_id` in logs: keep (needed to debug against
   `/chat/sessions`), but never in metrics (§6), never in dashboards.
3. `extraction_run_id` and `turn` ids: safe (opaque row ids).
4. Exception scrubber: strip `sk-...` tokens and URL-embedded secrets from
   `error=%s` values (reuse `guardrail.SECRET_PATTERNS`,
   `guardrail.py:54-67`) before logging.
5. Never log `exchange`, statements, or any candidate content — P2 tests
   must assert absence (§14).
6. LangSmith runs must not receive prompts as metadata (the LLM inputs are
   already recorded by LangSmith auto-tracing by design; do not duplicate
   into Redis/logs).

---

## 14. Test Coverage Gaps

### 14.1 CURRENT BEHAVIOR

- Behavior coverage is strong: `tests/learning/test_extraction_execution.py`
  (18 tests — FakeRedis Lua mirror, thread concurrency, TTL expiry,
  fail-open, turn-boundary safety), `tests/learning/test_extraction.py`
  (gates), `tests/chat/test_endpoints.py` (schedule wiring, incl. stream).
- Observability coverage: **zero** — no test in the repo uses
  `caplog`/`assertLogs`/`logs=` (grep verified); no metric assertions
  exist (no metrics to assert); no timing assertions; no redaction tests.

### 14.2 RECOMMENDED P2 DESIGN — observability tests (design only)

P2.1 (with instrumentation):
- Metric increments: scheduling, skip reasons, gates, LLM calls/errors,
  memory outcomes (dedupe/conflict/supersede), coordination fallback —
  assert exact counter deltas per scenario.
- Failure counters: queue-full → `skipped{reason=concurrency}`; Redis down
  → `redis_unavailable_total{op}`; Gate 3 format/domain/secret → per-reason
  counters.
- Timing: duration histogram recorded (deterministic clock injection —
  the constitution requires deterministic tests; avoid time-dependent
  assertions, use injected `time`/`perf_counter`).
- Label safety: instrumentation asserts label membership (§6.2) — a test
  that injects an out-of-set label must fail.
- Correlation: `run_id` present in claim value, in `MemoryEvent.metadata_`,
  and in every log record captured via `caplog`.
- Redaction: capture logs for a full success + failure path and assert no
  occurrence of the user text, statements, raw `user_id`, or `sk-` tokens.
- Shutdown: assert abandoned-count log emission.

P2.2 (tracing): fake/disabled LangSmith → extraction still completes and
logs (fail-open); parent-run linkage passed to the worker when context
available; spans named per §8.3.

---

## 15. P2.1 / P2.2 / P2.3 Priorities

### P2.1 — MUST HAVE (minimal viable observability)

1. Logging foundation: `LOG_LEVEL` setting + JSON-formatter config
   (single module, app-owned) — fixes "INFO events silently dropped".
2. Correlation: `extraction_run_id` at schedule time; propagate through
   claim value, logs, executor task, and `MemoryEvent.metadata_` /
   `MemoryEntity.metadata_` (§4.3) — no schema change.
3. Duration + in-flight: histograms around LLM call and total run;
   `extraction_inflight` gauge (inc/dec at `extractor.py:258` / `_run_task`
   `:305-308`); queue-depth gauge from `executor.queue_size` (`:90-91`).
4. Metrics module + `/metrics` endpoint (`prometheus-client`, no new
   infra), counters per §5.2, label set per §6.2 with membership
   enforcement.
5. Error taxonomy: `reason` enum on all skip/fail events; Gate 3
   per-reason counters (kills the silent drop at `extractor.py:265-266`).
6. Token capture (`extractor.py:149` response_metadata) →
   `extraction_tokens_total{provider,model,kind}`.
7. Redaction: `user_hash` instead of raw `user_id` in extraction logs;
   exception scrubber reusing `guardrail.py:54-67`.
8. Tests for all of the above (§14.2 P2.1 list).

### P2.2 — SHOULD HAVE

9. LangSmith extraction trace tree with explicit parent handoff into the
   worker thread (§8.3) — no OTel.
10. Grafana dashboard (conceptual §12) + initial alert rules (§10).
11. Shutdown accounting log (`executor.py:93-114` abandoned count);
    Redis latency histogram per op (`coordinator.py:125-127,145,160-164`).
12. Request-level link: pass middleware `request_id` (`observability.py:25`)
    into `schedule_extraction` so HTTP → extraction correlation closes
    Seam A (§4.2).
13. Trace-context tests (§14.2 P2.2).

### P2.3 — NICE TO HAVE

14. OTel/OTLP bridge behind the same chokepoints (transport swap only).
15. LLM-call timeout + watchdog on workers (`llm_provider.py:47-54,62-70`
    currently unset) — a correctness/availability improvement that
    observability surfaces first.
16. `extraction_run_id` linkage into `PipelineTrace` (`tracing.py:49-136`)
    so RAG and extraction traces join per session.
17. Cost dashboard panels (per-provider $, using one pricing map
    `telemetry.py:22-24`), pending-memory trend panel.

**Explicitly out of scope** (no creep): V2.3 consolidation, new memory
algorithms, reranking/hybrid retrieval, UI, durable queues, collaborative
memory, agent planning, any new infrastructure beyond
`prometheus-client`.

---

## 16. Recommended Implementation Plan

Phased; each phase keeps the suite green and the architecture intact
(capability = Observability; owner = platform; artifacts = metric/log
contracts; no lifecycle-stage changes; extraction stays fail-open).

1. **Foundation (P2.1)**: `app/core/logging_config.py` (JSON formatter,
   `LOG_LEVEL`) wired in `main.py` lifespan; baseline test asserting INFO
   emission.
2. **Correlation (P2.1)**: `extraction_run_id` in `schedule_extraction` →
   `_run_task` → `run_extraction` → `_extract_with_llm`; claim owner
   string; `metadata=` on `create_memory`; `MemoryEvent.metadata_` set via
   `_append_event` metadata param (`memory.py:124-140`).
3. **Metrics (P2.1)**: `app/core/metrics.py` (counters/gauges/histograms,
   label enums, `assert_membership`); `/metrics` route in `main.py`;
   instrument `coordinator.py` (3 ops), `extractor.py` (schedule/run/gates/
   LLM), `executor.py` (queue depth, in-flight), `memory.py` (outcomes —
   single chokepoint).
4. **Taxonomy + logging polish (P2.1)**: `reason` enum; Gate-3 counters;
   duration on `done`; user_hash; exception scrubber; shutdown count.
5. **Tests (P2.1)**: §14.2 list; deterministic via injected clocks/fakes.
6. **Tracing (P2.2)**: LangSmith parent-handoff wrapper around
   `_run_task`; silent fallback preserved (`langsmith.py:50-53,83-92`).
7. **Dashboards + alerts (P2.2)**: panels §12; rules §10.
8. **Optional (P2.3)**: OTel bridge, timeouts, PipelineTrace linkage,
   cost panels.

Definition of done for P2 (constitution): Capability Registry entry
(Observability capability: metrics/logging/tracing ownership, api_prefix
`/metrics`), artifacts documented, tests added, invariants preserved
(fail-open, no PII, no high-cardinality labels, no schema migration).

---

## 17. GREEN / YELLOW / RED Assessment

| Axis | Verdict | Basis |
|---|---|---|
| Logging | **YELLOW** | Distinct, searchable event names; but no configuration (INFO loss risk), no JSON, no correlation, mixed context gaps, two silent-drop points (`extractor.py:265-266`, `memory.py:284-285`) |
| Metrics | **RED** | None exist (no dependency, no counters, no gauges, no /metrics) |
| Tracing | **RED** | Extraction invisible to LangSmith trees (detached thread, `executor.py:53-58`) and to Redis `PipelineTrace` (RAG-only, `tracing.py:49-136`) |
| Error classification | **YELLOW** | Reason-in-message naming works for humans; no taxonomy, no counters, no structured reason field |
| Duration | **RED** | No timing anywhere in extraction |
| Correlation | **RED** | Four broken seams (§4.2); `request_id` dead after middleware |
| Artifact lineage (DB) | **GREEN** | MemoryEntity + MemoryEvent append-only chain is intact and queryable (`models/memory.py:87-143`); post-hoc reconstruction is possible via `source_conversation_id` + `content_hash` |
| Security/privacy posture | **GREEN** | No content logging today; risks are limited to raw `user_id` and unscrubbed exception strings |

**Overall: YELLOW** (leaning RED for real-time runtime observability).
The system is fully auditable *after the fact* through the artifact ledger
and logs, but an on-call engineer cannot today answer "where did the time
go / why did this specific turn fail / is extraction healthy right now"
without the P2.1 instrumentation. The four-strength base (chokepoint
design of coordinator/executor, no-content logging, ready-made
`queue_size`, existing `metadata_` fields) makes P2.1 a contained change
with no new infrastructure.
