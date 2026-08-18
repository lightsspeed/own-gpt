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

---

# Part 2 — P2.2: Prometheus + Grafana operational observability

Status: IMPLEMENTED · Date: 2026-08-16 · Audit: `docs/v22_p2_observability_audit_p22.md`
(uncommitted working tree; no commits made for P2.2)

## P2.2-1. Scope (Option C of the P2.2 audit)

Self-hosted Prometheus + Grafana behind a compose `monitoring` profile, 5
alert rules over the existing `owngpt_memory_extraction_*` metrics, one Grafana
dashboard, plus the smallest app additions required by the amendment-reviewed
stalled-extraction alert. Everything is validation-as-code: hermetic pytest
suites (no Prometheus/Grafana needed) + promtool rule tests + a verification
runbook. No committed credentials anywhere.

## P2.2-2. Amendments incorporated

1. **ExtractionSilentlyStopped must be chat-activity-aware.** `schedule_extraction`
   runs per completed chat turn and increments `scheduled_total` every time
   unless disabled / claim-conflict / queue-full (both of the latter have their
   own alerts). Therefore "chat traffic but zero scheduling for 12h" is a real
   break; "zero traffic at all" is healthy silence and must never fire. No
   Prometheus-visible activity metric existed (LearningCollector writes to the
   DB only), so the smallest addition was chosen: bounded HTTP counter
   `owngpt_http_requests_total{endpoint∈{chat,other}}` incremented in
   `RequestLoggingMiddleware` for every request except `/metrics` (scrape noise
   excluded). Alert 5 gates on chat traffic AND zero scheduled AND the info
   gauge enabled=1 → WARN for 10m.
2. **Grafana credentials come from the environment only.** `${GRAFANA_ADMIN_USER:-}` /
   `${GRAFANA_ADMIN_PASSWORD:-}` with an entrypoint guard that exits 1 (FATAL)
   on missing or weak values (admin/password/password123/grafana/changeme/secret),
   then `exec /run.sh`. Empty-safe interpolation means plain `docker compose up`
   (no monitoring profile) is unaffected.

## P2.2-3. Files changed

| File | Change |
|---|---|
| `app/core/metrics.py` | `ENABLE_STATES`; `extraction_info` gauge (registered as `Gauge("owngpt_memory_extraction_info", registry=registry)`); `API_REGISTRY`, `_api_http_requests_total` counter (namespace-less, bounded via `safe_count_http(endpoint)` with endpoints ∈ {chat, other}); `record_extraction_enabled()` (reads `settings.MEMORY_V2_GRAPH`); `registered_metric_names()` (counters → `_total`, histograms → `_bucket/_sum/_count`, gauges bare); `render_metrics()` now concatenates extraction registry + API registry |
| `app/main.py` | lifespan: `record_extraction_enabled()` after `setup_logging` |
| `app/core/observability.py` | `request_endpoint(path)` classifier (`/api/v1/chat*` → chat, else other); middleware increments the counter when `path != "/metrics"` |
| `app/learning/extraction/executor.py` | `shutdown()`: counts abandoned queue tasks, sets `queue_depth` to 0, posts sentinels, emits structured event `extraction_executor_shutdown` (`dropped`, `queue_depth`); does NOT reset `inflight` (workers own it — documentation-only log `extraction_executor_shutdown_detached`) |
| `ops/prometheus/prometheus.yml` | NEW — scrape 15s, eval 30s, `rule_files`, jobs `owngpt-web` (static `web:8000`, path `/metrics`) + `prometheus` self-scrape |
| `ops/prometheus/rules/extraction.yml` | NEW — the 5 approved alerts (P2.2-6) |
| `ops/prometheus/tests/extraction_test.yml` | NEW — 12 promtool rule unit tests (P2.2-10) |
| `ops/grafana/provisioning/{datasources/prometheus.yml, dashboards/providers.yml}` | NEW — datasource `owngpt_prometheus` → `http://prometheus:9090` (isDefault, editable false); providers (file-based, `allowUiUpdates: false`) |
| `ops/grafana/dashboards/owngpt-extraction.json` | NEW — uid `owngpt-extraction`, 9 panels, editable false, no templating |
| `docker-compose.yml` | monitoring profile: `prometheus` + `grafana` services (P2.2-7); named volumes `prometheus_data`, `grafana_data`; removed obsolete `version: '3.8'` |
| `scripts/verify_p2_2_observability.ps1` | NEW — verification runbook: promtool check + test rules (pinned `prom/prometheus:v3.13.2` container, `--entrypoint promtool`, dev-only), compose profile gating, full config validity, dashboard JSON check |
| `tests/ops/_promql.py` | NEW — helpers: `known_metric_names()` (from `registered_metric_names()` + `up`), unknown-metric ref scan, forbidden-identifier scan (user_id, user_hash, session_id, conversation_id, message_id, request_id, run_id, extraction_run_id, memory_id), series-spec validity |
| `tests/ops/test_prometheus_config.py` | NEW — 6 tests |
| `tests/ops/test_prometheus_rules.py` | NEW — 7 tests |
| `tests/ops/test_grafana_dashboard.py` | NEW — 8 tests |
| `tests/ops/test_compose_profile.py` | NEW — 10 tests |
| `tests/learning/test_extraction_observability.py` | P2.2 section: info gauge (enabled/disabled/bounded/non-ID labels), shutdown drain/idempotency, queue capacity, http counter render/bounded/classification |

## P2.2-4. Pinned images (searched 2026-08)

`prom/prometheus:v3.13.2` (latest stable 2026-07-29), `grafana/grafana:13.1.3`
(2026-08-07). No new Python dependencies.

## P2.2-5. Metric additions (bounded)

- `owngpt_memory_extraction_info{enabled∈{1,0}}` — gauge, 1.0 when
  `MEMORY_V2_GRAPH` is enabled. Exists so rules can reference "extraction is
  deliberately off" (alert 5 suppression) via a metric instead of a config leak.
- `owngpt_http_requests_total{endpoint∈{chat,other}}` — app-traffic activity
  counter for the stalled-extraction amendment; `/metrics` requests excluded.
  Bounded fail-open (`safe_count_http`).

## P2.2-6. Final alert rules (group `extraction_operations`)

| Alert | severity | expr | for | semantics |
|---|---|---|---|---|
| `ExtractionFailureRateHigh` | warning | `increase(owngpt_memory_extraction_failed_total[15m]) / clamp_min(increase(owngpt_memory_extraction_scheduled_total[15m]), 1) > 0.5` | 10m | majority of attempts failing — systemic (provider/DB/bad config) |
| `ExtractionInflightStuck` | critical | `owngpt_memory_extraction_inflight > 0 and on() rate(owngpt_memory_extraction_completed_total[30m]) == 0` | 30m | extraction dead while system believes it runs |
| `ExtractionQueueBacklog` | warning | `owngpt_memory_extraction_queue_depth / owngpt_memory_extraction_queue_capacity >= 0.9` | 5m | sustained saturation vs burst |
| `RedisCoordinationDegraded` | warning | `rate(owngpt_memory_extraction_redis_fallback_total[15m]) > 0` | 10m | fail-open but coordination lost (duplicate/parallel risk) |
| `ExtractionSilentlyStopped` | warning | `sum(increase(owngpt_http_requests_total{endpoint="chat"}[12h])) > 0 and on() (increase(owngpt_memory_extraction_scheduled_total[12h]) == 0 or on() absent(owngpt_memory_extraction_scheduled_total) == 1) and on() (owngpt_memory_extraction_info{enabled="1"} == 1)` | 10m | amendment 1 |

## P2.2-7. Compose and security

- Services `prometheus` (9090) and `grafana` (3000) with `profiles: ["monitoring"]`:
  plain `docker compose up` starts neither; `--profile monitoring` starts both.
- Host binds loopback-only (`127.0.0.1:9090:9090`, `127.0.0.1:3000:3000`);
  `prometheus` depends on `web`, `grafana` depends on `prometheus`; app services
  never depend on monitoring.
- Config mounts read-only; probing configs are development-only.
- Grafana: `GF_USERS_ALLOW_SIGN_UP=false`, `GF_AUTH_ANONYMOUS_ENABLED=false`,
  guard (amendment 2). The guard reads raw container env vars `GRAFANA_ADMIN_USER`
  / `GRAFANA_ADMIN_PASSWORD`, so the compose environment maps them in
  empty-safe interpolation alongside `GF_SECURITY_ADMIN_*`.
- Dashboard: uid `owngpt-extraction`, 9 panels (system health; extraction
  throughput; duration p50/p90/p95; failures by reason; inflight (workers
  busy); queue depth vs capacity; redis coordination; LLM calls/errors/tokens
  by provider/model; memories created and outcome counters), `editable: false`,
  no templating, refresh 30s, default range now-1h.

## P2.2-8. Test strategy (hermetic, no Prometheus/Grafana needed)

40 new tests: prometheus config structure + scrape wiring; rule semantics
(approved-five set, full annotations/severity/for-grammar, metric references
must resolve to registered names, no forbidden identifiers, fire/no-fire
coverage ≥1 per alert, eval_time grammar); Grafana dashboard (panels, PromQL
refs, datasource, no templating, provisioning); compose profile (gating,
depends_on, loopback, mounts, credential guard wording, no weak credentials
committed, volumes); app-side gauge/counter/shutdown tests. Registered-metric
derivation uses `registered_metric_names()` (counter `_total`, histogram
`_bucket/_sum/_count`, gauge bare name) — this caught the info-gauge
registration issue (factory `gauge()` used a differently-derived name).

## P2.2-9. Findings from verification (both found by the tools, both fixed)

1. **Per-second rate footgun (found by promtool test rules).** The first
   failure-rate rule used `rate(failed[15m]) / clamp_min(rate(scheduled[15m]), 1) > 0.5`.
   `rate()` returns events/second (~0.0167/s at 1 event/min), so the absolute
   clamp of `1` produced a ratio ≈ 0.017 that could NEVER exceed 0.5 — the
   alert was mathematically dead (confirmed empirically: `rate>0` fired,
   `rate>0.5` never even went pending). Fixed with windowed `increase()` counts,
   keeping the comparison materialized in events per 15m.
2. **Guard dead-code wiring (found by the live run).** The grafana guard checks
   container env `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`, but the compose
   `environment` block only mapped `GF_SECURITY_ADMIN_*` — the guard FATALed
   on every start regardless of credentials. Fixed by passing the raw vars
   through empty-safe interpolation. Verified live: no creds → FATAL + exit 1;
   with creds → healthy, datasource `owngpt_prometheus` provisioned, dashboard
   provisioned.

## P2.2-10. Live verification (docker compose, real stack)

- Full `scripts/verify_p2_2_observability.ps1` run: promtool `check rules`
  (5 rules) ✓, promtool `test rules` (12 cases, all firing/no-fire paths) ✓,
  plain config excludes prometheus/grafana ✓, `--profile monitoring` includes
  both ✓, `config -q` valid ✓, dashboard JSON valid ✓.
- Live: `--profile monitoring up` with creds → Prometheus healthy; targets
  `owngpt-web` (`web:8000/metrics`) and self-scrape both `up`; live query
  `owngpt_memory_extraction_info{enabled="1"} = 1` (real app, auto-reloaded);
  a real HTTP request produced `owngpt_http_requests_total{endpoint="other"} = 1`;
  Grafana healthy, datasource + dashboard provisioned. Restored the pre-existing
  dev stack afterwards (named volumes preserved).

## P2.2-11. Regression

Full suite **348 passed / 2 failed** (`reports/p2_2_junit.xml`) — the 2 are
the pre-existing OpenAI quota pair (`openai.RateLimitError` 429
`credit_balance_exhausted` in `tests/pipeline/test_pipeline.py`), identical to
baseline (308 passed). P2.2 added 40 tests (310 → 350 collected).

## P2.2-12. Deferred

Alertmanager/notification routing (email/webhook), long-term storage (thanos/
object storage), OTel tracing (P2.3), RBAC on 9090/3000 for exposed deployment,
Kubernetes-native service discovery. All five alerts assume the compose
deployment (single-instance `web` service target).
