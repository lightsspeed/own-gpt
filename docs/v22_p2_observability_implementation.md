# V2.2 P2.1 — Memory Extraction Observability: Implementation Record

Status: IMPLEMENTED · Date: 2026-08-15 · Head: `8eeca8a` (uncommitted working tree)

Companion document: `docs/v22_p2_observability_audit.md` (the P2 design record — this
file documents what was built and how it was verified; it does not repeat the audit).

## 1. Scope

Instrument the EXISTING memory extraction pipeline (`app/learning/extraction/`) with:

1. Structured JSON logging (`LOG_LEVEL` config, event names, whitelisted fields).
2. `extraction_run_id` — one uuid4 per extraction attempt, propagated through
   schedule → Redis claim → executor → run → memory write → MemoryEvent metadata → logs.
3. Prometheus metrics (`prometheus-client`, namespace `owngpt_memory_extraction_*`)
   with a bounded-label cardinality policy; exposed at `GET /metrics`.
4. Token capture (OpenAI + Ollama field shapes), duration/inflight/queue gauges.
5. Privacy-safe logging (no prompts, statements, keys, or raw user ids).
6. Structural failure isolation: observability can never break chat or extraction.

No extraction semantics changed. No schema change. No new dependencies beyond
`prometheus-client==0.26.0`.

## 2. Files

| File | Change |
|---|---|
| `app/core/config.py` | `LOG_LEVEL: str = "INFO"` |
| `app/core/logging_config.py` | NEW — `JsonFormatter`, `setup_logging()`, `sanitize_exception_message()`, `classify_exception()` |
| `app/core/metrics.py` | NEW — `ExtractionMetrics`, bounded-label enums, `safe_*` fail-open emitters, `render_metrics()` |
| `app/learning/extraction/observability.py` | NEW — `new_run_id()`, `user_hash()`, `log_event()`, `emit_*` taxonomy |
| `app/learning/extraction/extractor.py` | Instrumented: run_id flow, gate exit events, token capture, tuple `_validate_candidates` |
| `app/learning/extraction/coordinator.py` | Instrumented: claim/fallback counters, run_id params |
| `app/learning/extraction/executor.py` | Instrumented: queue/inflight gauges |
| `app/services/memory.py` | `extraction_run_id` metadata + outcome counters (single chokepoint) |
| `app/main.py` | `setup_logging(settings.LOG_LEVEL)` in lifespan; `GET /metrics` |
| `requirements.txt` | `prometheus-client==0.26.0` |
| `tests/learning/test_extraction_observability.py` | NEW — 35 tests |
| `tests/learning/test_extraction.py`, `test_extraction_execution.py` | Updated signatures |

## 3. Metrics catalog (namespace `owngpt_memory_extraction_`)

Counters:

- `scheduled_total` — attempts enqueued.
- `skipped_total{reason}` — deterministic exits; reasons in §5.
- `failed_total{reason}` — error exits (LLM_ERROR, DB_ERROR, PROVIDER_UNAVAILABLE, WORKER_ERROR, UNKNOWN_ERROR).
- `gate_rejections_total{gate,reason}` — slice of skipped_total (gates `1`, `1b`, `3`).
- `started_total`, `completed_total` — run-time invariant: started = completed + failed + run-time skips (CONVERSATION_MISSING, NO_TURN, INELIGIBLE, THROTTLED, NO_CANDIDATES, INVALID_CANDIDATE, SECRET_DETECTED). Schedule-time outcomes (DISABLED, CLAIM_CONFLICT, QUEUE_FULL) are emitted by `schedule_extraction` into `skipped_total` only and never increment `started_total`.
- `llm_calls_total{provider,model}`, `llm_errors_total{provider,model}`, `llm_tokens_total{provider,model,kind}` (`kind`: input|output|total). Failed LLM calls are counted by `llm_errors_total` and are NOT observed into `llm_duration_seconds` (duration histogram covers successful calls only — deferred, see §14).
- `memory_created_total{status}`, `memory_deduplicated_total`, `memory_conflict_total`, `memory_superseded_total` — all `create_memory` outcomes (documented chokepoint).
- `redis_claim_success_total`, `redis_claim_conflict_total`, `redis_fallback_total{operation}` (`operation`: claim|release|throttle).

Histograms (buckets 0.05…120s):

- `duration_seconds` — one extraction attempt.
- `llm_duration_seconds{provider,model}` — one LLM call.

Gauges:

- `inflight` — owned exclusively by the executor (executor.py `_run`): one
  increment per running extraction task, decremented when the task finishes.
  `run_extraction` never touches it. Invariant: N concurrently executing tasks
  → `inflight == N`; one scheduled extraction → running `1`, completed `0`.
- `queue_depth`, `queue_capacity` — executor pending queue gauges.

## 4. Label cardinality policy

- ALLOWED labels (finite enums): `provider` ∈ {openai, ollama, unknown} · `model`
  ∈ config allowlist ∪ {"other"} · `reason` ∈ §5 set · `gate` ∈ {1, 1b, 2, 3} ·
  `operation` ∈ {claim, release, throttle} · `kind` ∈ {input, output, total} ·
  `status` ∈ {pending, active}.
- FORBIDDEN (never metric labels; logs only where whitelisted): user_id,
  user_hash, session/conversation/message/run/request/memory ids, raw error
  text, prompts, statements.
- `validate(label, value)` is the strict path (raises on unbounded values except
  `model`, which collapses to `other`); every emission is validated before touch.
  Enforced by `tests/...::test_no_forbidden_ids_in_metric_labels` and
  `test_bounded_labels_validate`.

## 5. Reason taxonomy (terminal exits)

`DISABLED` · `CLAIM_CONFLICT` · `QUEUE_FULL` · `CONVERSATION_MISSING` · `NO_TURN` ·
`INELIGIBLE` (gate 1) · `THROTTLED` (gate 1b) · `NO_CANDIDATES` (gate 3) ·
`INVALID_CANDIDATE` (gate 3) · `SECRET_DETECTED` (gate 3) · `LLM_ERROR` ·
`DB_ERROR` · `PROVIDER_UNAVAILABLE` · `WORKER_ERROR` · `UNKNOWN_ERROR`.

Every terminal path emits exactly one `memory_extraction_skipped/failed/completed`
event and exactly one metric increment (tests assert this per path).

## 6. Structured logging

`JsonFormatter` emits `ts/level/logger/message` + whitelisted extras. `event` is
always present. Extras whitelist (`ALLOWED_EXTRA_FIELDS`): event, run_id,
request_id, session, turn, reason, gate, provider, model, attempt, written,
duration_ms, op/operation, status, outcome, kind, tokens_in/out, error_class,
error_message, user_hash, queue_depth, dropped, entity. Anything else is dropped
(test: `test_json_logger_drops_non_whitelisted_fields`).

Exception messages are sanitized (`sk-…`, `AKIA…`, `Bearer …`, PEM blocks,
500-char cap) and classified to a reason (DB_ERROR / PROVIDER_UNAVAILABLE /
UNKNOWN_ERROR). `setup_logging(level)` is idempotent; invalid level → INFO.

## 7. Correlation: extraction_run_id

```
schedule_extraction ──▶ new_run_id() ──▶ Redis claim value "pid-N:<run_id>"
      │                                   executor submit(_run_task, ..., run_id)
      ▼
run_extraction(run_id) ──▶ MemoryEntity.metadata_["extraction_run_id"]
      │                      MemoryEvent.metadata_["extraction_run_id"] (STORED/CONFLICT/SUPERSEDED)
      ▼
every structured log line for the attempt carries run_id
```

`run_id` is generated at schedule time and by `run_extraction` when absent
(called directly). MemoryEvent linkage is metadata-only — no schema change,
lineage preserved (extraction attempt → entity → events).

## 8. Failure isolation

- `ExtractionMetrics.count/observe/set/gauge_inc/gauge_dec` swallow all
  instrumentation exceptions.
- Module-level `safe_*` wrappers in `app/core/metrics.py` additionally guard
  against a broken/monkeypatched metrics object — EVERY production call site
  routes through them (extractor, coordinator, executor, observability,
  memory service).
- `log_event` swallows logging failures; `JsonFormatter` never raises;
  logging.Handler handles `emit` exceptions itself.
- Enforced by `test_broken_metrics_never_fail_extraction` and
  `test_broken_logging_never_fails_extraction`.

## 9. Privacy

No conversation content, prompts, statements, tokens, keys, or raw user ids in
logs; session_id and turn stay (operational necessity, existing convention).
`user_hash` (sha256 prefix 8) available for identity-adjacent logs. Enforced by
`test_logs_never_contain_conversation_content` and `test_metrics_render_has_no_content`.

## 10. Configuration / API

- `LOG_LEVEL` (env, default INFO) → `setup_logging` at app startup.
- `GET /metrics` → `text/plain; version=0.0.4` Prometheus exposition of the
  extraction registry (fail-open: empty body on render failure).

## 11. Test strategy (all hermetic — sqlite StaticPool, FakeRedis, fake LLM)

35 new tests in `tests/learning/test_extraction_observability.py`: JSON
structure/whitelist/sanitization, LOG_LEVEL, run_id generation + propagation
(claim value contains run_id), MemoryEvent metadata linkage, per-reason gate
exits, metric increments (scheduled/skipped/failed/completed/duration/inflight/
queue), bounded-label enforcement incl. forbidden-id scan of `_labelnames`,
token capture (OpenAI / Ollama / absent), exception sanitize/classify, and both
fail-open guarantees.

Implementation notes discovered during test writing:

- prometheus-client 0.26.0 stores histogram bucket values as a list
  (`_buckets`) of per-bucket value objects; count = sum of bucket values
  (no `_count` attribute).
- `metric.labels()` on a label-less metric raises → `_labeled()` helper returns
  the metric itself when no labels are passed.
- Tests must inject a fresh `ExecutionCoordinator(redis_url=None)` per test —
  the process-wide singleton (real REDIS_URL) leaks claim/throttle state across
  tests and even into the local dev Redis (keys observed: `memory:extraction:
  throttle:sess-*`); cleaned up after the run.

Regression: full suite **306 passed / 2 failed** — the 2 failures are the
pre-existing OpenAI quota (429 `credit_balance_exhausted`) tests in
`tests/pipeline/test_pipeline.py`; unchanged from baseline (271 passed before
this change).

## 12. Live verification (docker compose stack)

Verified in the running stack (web container rebuilt with the new dependency):

- `GET /metrics` returns 200 with all `owngpt_memory_extraction_*` series.
- Real schedule flow: `memory_extraction_scheduled` → `started` → `llm_started`
  with `provider=ollama model=qwen3:8b` and a 36-char `run_id` in structured
  JSON, claim granted via real Redis.

Environment limitations (pre-existing, not P2.1 defects):

- The chat endpoint cannot complete turns: the RAG retriever embeddings are
  hardcoded to OpenAI (`app/services/vector_store.py`) and the OpenAI account
  has exhausted credits (429) — 500 on retrieval.
- `qwen3:8b` on this CPU-only machine takes minutes per generation and
  ultimately failed to load during warm-up, so the full LLM→write path could
  not complete live. It is fully covered by the hermetic suite.
- The write path additionally requires `MEMORY_EMBEDDING_PROVIDER` (OpenAI or
  none); with OpenAI credits exhausted, only the "none" process-level override
  allows a live write — not exercised here for that reason.

## 13. Operational usage

- Scrape: `curl http://localhost:8000/metrics`.
- Follow an attempt: grep logs for `"event":"memory_extraction_skipped|failed|
  completed"` with the same `run_id`, then query `memory_entities.metadata_`,
  `memory_events.metadata_` for `extraction_run_id`.
- Suggested future alerts (not implemented — P2.3): failed_total rate by reason
  (LLM_ERROR / DB_ERROR), redis_fallback_total rate, duration_seconds p95,
  llm_tokens_total per model for spend, inflight vs queue_capacity saturation.

## 14. Deferred (unchanged from the audit)

P2.2 (LangSmith tracing), P2.3 (Grafana/OTel/alerts), durable queues, LLM
timeouts, distributed dashboards — explicitly out of scope. Additionally:
failed LLM calls are not observed into `llm_duration_seconds` (they count in
`llm_errors_total` instead); recording their duration deliberately deferred
to avoid complicates the histogram's success semantics.
