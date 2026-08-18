# OWNGPT V2.2 P2.2 OBSERVABILITY ARCHITECTURE AUDIT

- Checkpoint baseline: commit `be04257da09d7d7970f593f9c1bd805d085068db` (`feat(platform): harden memory extraction observability`)
- Audit type: READ-ONLY — no source, test, or configuration changes were made
- Output of this audit: this single document only
- Prior audit: `docs/v22_p2_observability_audit.md` (P2.1, committed) — left untouched

---

## 1. Executive Summary

P2.1 delivered a complete, correct, well-tested **in-process metrics and structured-logging
surface** for memory extraction: 20 bounded-label metrics, a strict privacy policy, a
fail-open state machine, and a 37-test observability suite. The gap this audit examined
is not *emission* — it is **visibility**: nothing in the current deployment scrapes or
displays the metrics, nothing alerts on them, and two operational blind spots remain
(executor shutdown is silent; request-level trace context does not reach extraction).

After inspecting the full observability surface (metrics, logs, HTTP middleware, the
stage-9 pipeline trace store, and the existing LangSmith scaffolding), the audit verdict is:

- **Do NOT wire extraction into LangSmith** (Option A): the infrastructure exists but is
  dormant by default, moves prompts/statements off-box when enabled, and provides little
  value for a local 1–2 instance deployment.
- **Do NOT adopt OpenTelemetry now** (Option B): it is not a dependency, has no
  consumer in this topology, and its benefits (cross-service, vendor-neutral tracing)
  do not yet pay for its complexity.
- **ADOPT Option C for P2.2**: Prometheus + Grafana + a minimal alert set on the
  **existing** `/metrics` endpoint, provisioned as versioned code under `ops/`, enabled
  via a docker-compose profile, plus one small tracked code change (executor shutdown
  abandoned-count event). This maximizes operational value with minimum added
  complexity, keeps vendor neutrality, and preserves every P2.1 privacy guarantee.

Tracing in any form (LangSmith extraction trees, OTel/OTLP) is **not justified yet**;
explicit triggers that would change that answer are recorded in §19.

---

## 2. Current P2.1 State

Baseline verified at `be04257` (15 files, +2914/−91):

| Area | State |
|---|---|
| Metrics registry | `app/core/metrics.py` — `owngpt_memory_extraction_*` namespace, 4 counters + 4 memory-outcome counters + 5 coordination/LLM counters + 2 histograms + 3 gauges = **20 metrics** |
| Label policy | Finite enums ONLY (`REASONS` 15-taxonomy, `GATES {1,1b,2,3}`, `OPERATIONS`, `KINDS`, `PROVIDERS`, `STATUSES`); `model` bounded by config allowlist + `"other"` |
| Forbidden labels | user_id, user_hash, session_id, conversation_id, message_id, request_id, extraction_run_id, memory_id, raw errors, prompts, statements — never in metrics |
| Structured logging | `app/core/logging_config.py` JSON formatter + `ALLOWED_EXTRA_FIELDS` whitelist; `log_event()` taxonomy in `app/learning/extraction/observability.py` |
| Fail-open contract | All `safe_*` emitters swallow exceptions; tests `test_broken_metrics_never_fail_extraction`, `test_broken_logging_never_fails_extraction` |
| Coordination | Redis single-flight claim (`pid-<pid>:<run_id>`), distributed throttle, in-process fallback; `redis_fallback_total{operation}` counted once per failure |
| Executor | Bounded daemon pool `BoundedDaemonExecutor`; inflight gauge owned **solely** by the executor; queue_depth/queue_capacity gauges |
| Endpoints | `GET /health` (static `{"status": "ok"}`), `GET /metrics` (Prometheus text exposition, unauthenticated) |
| Tests | 37 observability tests (`tests/learning/test_extraction_observability.py`); full suite 308 passed / 2 failed (pre-existing OpenAI quota pair) |

---

## 3. Existing Telemetry Surface (Inventory)

| # | Telemetry | Owner | State | Consumed by |
|---|---|---|---|---|
| 1 | `RequestLoggingMiddleware` — per-HTTP-request `req_id` (uuid4), `X-Request-ID` header, method/path/status/duration log (`app/core/observability.py`) | core | ✅ lives | logs only |
| 2 | JSON structured logs (`app.request`, `app.extraction`, ...) with whitelisted extras | core | ✅ lives | logs only |
| 3 | `owngpt_memory_extraction_*` Prometheus metrics | P2.1 | ✅ lives | **nothing scrapes them** |
| 4 | `GET /metrics` text exposition | P2.1 | ✅ lives | **nothing scrapes it** |
| 5 | `GET /health` | core | ✅ trivial | compose `depends_on` only (no healthcheck wired for web) |
| 6 | `PipelineTrace` + `TracingService` (stage 9): per-pipeline-run trace with per-stage latency, tokens, decisions; stored in Redis `trace:{session}:{trace_id}` + `traces:{session}`, 7-day TTL | V1-era | ✅ lives | Redis only; no UI |
| 7 | LangSmith scaffolding: `setup_langsmith()`, `@traceable` on 11 pipeline stages, `create_trace()` RunTree helper, auto env tracing | V1-era | ⚠️ dormant by default (`LANGCHAIN_API_KEY=""`) | cloud SaaS if enabled |
| 8 | arq ingestion worker (separate process) | V1-era | ✅ lives | no metrics surface |
| 9 | Automation scheduler + learning subsystem REST APIs | platform | ✅ lives | out of scope here |

**Gaps identified by this audit:**

- G1 — No Prometheus scraper, no Grafana, no dashboard: the P2.1 metric registry is invisible in operation.
- G2 — No alerting: failures, queue backlog, stuck inflight, Redis fallback are all undetected until a human reads logs.
- G3 — Executor shutdown is silent: queued work is dropped without a log event; `inflight` may linger >0 during teardown (daemon workers still running) with no explanation.
- G4 — No correlation between HTTP `req_id` and extraction `run_id` (see §4).
- G5 — `/health` reports only process liveness — no dependency health (acceptable scope: coordination is fail-open by design; noted, not changed).

---

## 4. Correlation Model

Four independent identifiers exist today:

| ID | Generated at | Scope | Carried by | Linkable |
|---|---|---|---|---|
| HTTP `req_id` (middleware uuid4) | request entry | one HTTP request | log extras; `X-Request-ID` response header | not persisted |
| Client `request_id` (idempotency key) | client | one logical user message | `chat_messages.request_id` column; 409 on retry | user-scoped, optional |
| `PipelineTrace.trace_id` (uuid4) | pipeline run | one RAG pipeline execution | Redis `trace:{session}:{trace_id}` | per-session list |
| Extraction `run_id` (uuid4) | `schedule_extraction` | one extraction attempt | Redis claim value `pid-<pid>:<run_id>`; `MemoryEvent.metadata_`; every extraction log event | **not linked to the other three** |

Assessment: extraction debugging is **self-sufficient** — a run_id log line can be
joined with `MemoryEvent.metadata_` (DB) and bounded metrics (no ids). HTTP-level joins
are a support-ticket convenience, not an operational need at this scale.

**Decision (P2.2):** do not build ambient request→run correlation. The explicit
parameter pattern already in place (`run_id` threaded through schedule → claim →
executor → run → MemoryEvent) is the correct minimal mechanism; ambient context
propagation (contextvars/threadlocals) through daemon threads would be more complex,
fragile at the thread boundary, and is explicitly deferred (trigger in §19). If a join
is ever needed, the cheapest future step is logging `req_id` at the two
`schedule_extraction(...)` call sites in `app/api/endpoints/chat.py`.

---

## 5. Executor Thread Boundary

Facts verified in `app/learning/extraction/executor.py`:

- Workers are **daemon threads** (`memory-extraction-worker-{i}`), started at import.
- Submission crosses `submit(fn, *args)` on a bounded `queue.Queue(maxsize=200)`.
- The `inflight` gauge is incremented/decremented **exclusively** inside the worker loop
  (P2.1 corrective fix R1); `run_extraction` never touches it.
- `queue_depth` is updated on submit and on task dequeue; `queue_capacity` is static.
- No tracing/context mechanism exists at this boundary today — and none is needed:
  correlation is a **data field** (`run_id`), not ambient context.

Implication for any future tracing: contextvars set on the requesting thread (FastAPI
request thread or streaming worker thread) will **not** propagate into daemon executor
threads automatically. Any OTel/LangChain span parentage for extraction would require an
explicit `parent_context` (or callback-manager) argument to `run_extraction` — a
deliberate, testable design choice, currently deferred (§19). The P2.1 integrated test
`test_inflight_gauge_through_real_production_nesting` already pins the nesting
`schedule_extraction → executor → _run_task → run_extraction` behavior at the boundary,
which is the seam where any future trace handoff would be inserted and tested.

---

## 6. LangSmith Assessment (Option A — rejected)

Current state (`app/core/langsmith.py`): `get_client()`, `@traceable(name=...)` decorator,
`create_trace()` RunTree helper, `setup_langsmith()` called in `lifespan`. The RAG
pipeline stages (intent, router, rewrite, retriever, reranker, confidence, planner,
source_validator, evidence_builder, validation, rag_pipeline) carry `@traceable`.
`LANGCHAIN_TRACING_V2=true` env auto-tracing is set **only** when an API key is present
(default `LANGCHAIN_API_KEY=""` → setup exits early, zero traffic leaves the box —
a privacy-positive property).

Assessment for extraction:

| Criterion | Score | Note |
|---|---|---|
| Operational value here | Low | 1 instance, local compose; logs + MetricsEvent are sufficient |
| Privacy | **Negative** | LangSmith auto-capture includes prompts/outputs; extraction prompts contain memory statements — would require explicit input sanitization before any wiring |
| Vendor neutrality | Negative | SaaS dependency + data egress |
| Complexity | Low to add, high to sanitize | decorator is trivial; safe inputs are not |
| Failure mode | Silent (fail-open exists) | compatible, but not a differentiator |

**Decision:** extraction stays **off** LangSmith. The existing RAG-pipeline LangSmith
support remains an operator opt-in for pipeline debugging only. Do not extend the
`@traceable` pattern to the extraction path. Trigger to revisit: §19.

---

## 7. OpenTelemetry Assessment (Option B — rejected for now)

Facts: `opentelemetry-*` is **not** a dependency; `requirements.txt` has none. There is
no OTLP endpoint, no collector, no trace consumer in the deployment.

Assessment:

| Criterion | Score | Note |
|---|---|---|
| Operational value here | Low | Single process, in-process metrics already exist; no cross-service query need |
| Vendor neutrality | Positive | the one clear advantage |
| Complexity | High | SDK + exporter + collector routing + span propagation across the daemon-thread boundary (LangChain callback manager plumbing) + cardinality guard |
| Failure mode | Must remain fail-open | needs new mechanism (current fail-open is metric/log specific) |
| Maturity in stack | Untested | no code, no tests, no config |

**Decision:** defer. The P2.1 metric/log surface answers today's questions (is extraction
failing? skipped? slow? how many tokens?). OTel only pays for itself when deployments
grow beyond one instance or when cross-service trace queries are actually asked (trigger
in §19).

---

## 8. Options Comparison (A / B / C / D)

Scored on the audit mandate: minimum necessary complexity + maximum operational value +
vendor neutrality + privacy + reliability.

| Option | Complexity | Value | Neutrality | Privacy | Reliability | Verdict |
|---|---|---|---|---|---|---|
| A — LangSmith extraction trace tree | Low (decorator) / high (sanitize) | Low | Bad (SaaS) | **Bad** (off-box prompts/statements) | fail-open, silent | REJECTED |
| B — OpenTelemetry + OTLP | High | Low now | Good | Good (self-hosted) | needs new guards | DEFERRED (P2.3 trigger) |
| **C — Prometheus + Grafana + alerts on existing /metrics** | **Low** | **High** (visibility + warnings) | **Good** (OSS, self-hosted) | **Good** (bounded labels only, localhost binds) | app-independent sidecars | **ADOPTED for P2.2** |
| D — In-process improvements only | Low | Low (still invisible) | Good | Good | Good | PARTIAL (only the shutdown event from D is adopted) |

Also rejected in C's favor: pushing logs into a log-aggregator (Loki etc.) — structured
JSON logs are already the debugging record; adding Loki now violates minimum complexity.

---

## 9. Grafana Dashboard (P2.2, part of Option C)

Deliverable: dashboard-as-code, no manual click-ops.

- `ops/grafana/provisioning/datasources/` — Prometheus datasource (auto-provisioned).
- `ops/grafana/dashboards/owngpt-extraction.json` — dashboard, versioned, validated
  by tests (parse + panel/label assertions).
- Enabled via docker-compose profile `observability` (see §10, §17).

Panels (all feed on existing metrics; **no new metrics invented**):

| Tab | Panels |
|---|---|
| Overview | `scheduled_total` rate; `skipped_total{reason}` breakdown; `failed_total{reason}` breakdown; `completed_total` rate; success ratio `(completed/scheduled)` |
| Gates | `gate_rejections_total{gate,reason}` stacked bars (gates 1/1b/3) |
| Execution | `inflight` (with `queue_capacity` reference line), `queue_depth` vs `queue_capacity`, `duration_seconds` histogram_quantile p50/p90/p95 |
| LLM | `llm_calls_total`/`llm_errors_total` by `{provider,model}`, `llm_duration_seconds` quantiles, `llm_tokens_total{kind}` stacked |
| Redis | `redis_claim_success_total` vs `redis_claim_conflict_total`, `redis_fallback_total{operation}` |
| Memory | `memory_created_total{status}`, `memory_deduplicated_total`, `memory_conflict_total`, `memory_superseded_total` |
| Process | `up{job="owngpt-web"}`, `prometheus_target_scrape_duration_seconds` (scrape health) |

Privacy rule enforced by tests: dashboard JSON contains no user/session/message labels
and no variable that could inject ids into PromQL.

---

## 10. Alerting Rules (P2.2, minimal set — exactly 5)

Rules live in `ops/prometheus/rules/extraction.yml`, evaluated by Prometheus itself;
delivery via Grafana alerting (no Alertmanager component unless email/webhooks are
required — an optional profile flag, documented, not implemented by default).

Config-drift-free design: no rule hardcodes `MEMORY_EXTRACTION_MAX_CONCURRENCY`; ratio
and activity-based expressions instead.

| Rule | Expression (draft) | Condition | Severity | Rationale |
|---|---|---|---|---|
| ExtractionFailureRateHigh | `rate(owngpt_memory_extraction_failed_total[15m]) / clamp_min(rate(owngpt_memory_extraction_scheduled_total[15m]), 1)` | > 0.5 for 10m | warn | LLM/DB/provider degradation |
| ExtractionNoProgressDisabled | `sum(rate(owngpt_memory_extraction_scheduled_total[30m])) == 0` for 4h | AND `memory_v2_graph_enabled` (`owngpt_memory_extraction_info` if added — see note) | warn | extraction silently off (config drift) |
| InflightStuck | `owngpt_memory_extraction_inflight > 0 and rate(owngpt_memory_extraction_completed_total[30m]) == 0` | for 30m | critical | dead workers / hung LLM call |
| QueueBacklog | `owngpt_memory_extraction_queue_depth / owngpt_memory_extraction_queue_capacity` | >= 0.9 for 5m | warn | scheduler outpacing workers |
| RedisCoordinationDegraded | `rate(owngpt_memory_extraction_redis_fallback_total[15m])` | > 0 for 10m | warn | fail-open working, but single-flight/throttle lost |

Note on "ExtractionNoProgressDisabled": P2.1 has **no** info-metric for
`MEMORY_V2_GRAPH`/extraction-enabled config state. Adding a constant `Info` gauge
(`owngpt_memory_extraction_info{enabled="1"}`) is a **P2.2 tracked item** (one line in
`metrics.py` + one test) because an alert about "no scheduled extractions" is only
meaningful when we know whether extraction is *supposed* to run.

Testability: every rule ships with a `promtool test rules` unit-test YAML (`ops/prometheus/
tests/`) — deterministic time-series inputs, no wall-clock dependencies.

---

## 11. Redis Observability

Current state (P2.1): `redis_claim_success_total`, `redis_claim_conflict_total`
(covers in-process fallback too), `redis_fallback_total{operation ∈ {claim, release, throttle}}`
counted once per failure by `emit_redis_unavailable`.

Findings:

- Coordination failures are **fully visible** via the fallback counter + the
  `memory_extraction_redis_unavailable` log event (with `run_id`).
- Redis **latency** is deliberately not instrumented: Redis is in the same compose
  network, claims are sub-millisecond, and failures already surface through
  fallback counts. Adding latency histograms now would violate minimum complexity.
- No Redis metrics on the request path (chat never calls Redis for extraction —
  fail-open is end-to-end).

**Decision:** no new Redis metrics in P2.2. The dashboard Redis tab plus alert
`RedisCoordinationDegraded` covers the real operational questions. If evidence of
latency problems appears (slow claims, fallback spikes with healthy Redis), a
`redis_operation_duration_seconds{operation}` histogram is the P2.3 item (§19).

---

## 12. Shutdown Visibility

Current behavior (verified in code):

- `lifespan` teardown calls `execution_extractor.shutdown()` (`app/main.py`).
- `BoundedDaemonExecutor.shutdown()` stops accepting work, **silently drains** the
  queue, sets `queue_depth=0`, posts sentinels; workers exit when the queue empties.
- **No log event, no abandoned-count, no counter** indicates teardown happened or how
  much work was dropped. In-flight tasks keep running on daemon threads (by design,
  safe re-execution via claim TTL + idempotent writes), and `inflight` can read >0
  during the teardown window — a scrape could show a stuck gauge with no explanation.

**P2.2 tracked code change (the only one in the app):**

1. Emit `extraction_executor_shutdown` event with `abandoned=<n>` (count of tasks
   drained from the queue) — reuse the existing `log_event` machinery; no new fields.
2. After drain, reset `inflight`/`queue_depth` gauges to 0 with a clarifying log
   (`inflight` is process-scoped; surviving daemon in-flight tasks are detached).
3. Tests: deterministic — an executor preloaded with N queued tasks, `shutdown()`
   asserts the event carries `abandoned=N` and gauges read 0 afterward; idempotent
   second `shutdown()` emits nothing further.

This is the one piece of Option D adopted — it is 3 small lines plus tests and closes
the last real blind spot in the extraction lifecycle.

---

## 13. Tokens & Cost

Verified facts:

- Extraction: `llm_tokens_total{provider, model, kind ∈ {input, output, total}}` is
  counted when the provider reports usage (`_token_usage` in extractor.py handles
  OpenAI `response_metadata.token_usage` and Ollama-style fields; absent usage is
  graceful — `test_token_metadata_absent_is_graceful`, `test_ollama_style_token_fields`).
- Extraction: `llm_calls_total`/`llm_duration_seconds` give per-call cost input.
- Chat path: `_count_tokens()` uses tiktoken `cl100k_base` for title generation only.
- RAG embeddings: `build_embedding_provider()` — OpenAI provider is configured by
  default (`MEMORY_EMBEDDING_PROVIDER=openai`); embedding token counts are **not**
  recorded anywhere. Embeddings are the dominant paid-cost driver on the RAG path.
- `PipelineTrace` records `prompt_tokens`/`completion_tokens` per request (already).

**Decision:** P2.2 does not build a cost dashboard. The metric inputs for extraction
cost exist and are dashboarded (§9, LLM tab). End-to-end cost ($ estimate incl.
embeddings) is a P2.3 item with trigger "paid OpenAI/embedding usage resumed and a
billing question has actually been asked" (§19).

---

## 14. Privacy

P2.1 guarantees that P2.2 must preserve:

1. Metrics labels are validated finite enums; ids/content are structurally impossible
   (`test_no_forbidden_ids_in_metric_labels`).
2. Logs pass through the `ALLOWED_EXTRA_FIELDS` whitelist; extraction events never
   carry conversation content (`test_logs_never_contain_conversation_content`);
   user identity reduced to `user_hash` (sha256[:8]) for logs, never metrics.
3. Fail-open: observability failure can never break chat/extraction.

Additional privacy findings:

- `PipelineTrace` (stage 9) stores the **raw question** + retrieval scores in Redis
  with a 7-day TTL, keyed by session. This predates P2.1, is internal to the compose
  network, has no external consumer, and is out of scope for P2.2 — but it is recorded
  here as a known consideration: any future UI exposing traces must enforce per-owner
  access.
- LangSmith, when enabled, captures prompts/outputs to the SaaS — the reason extraction
  stays off it (§6).
- PromptScrape rule: **Grafana/Prometheus in the P2.2 profile bind to
  `127.0.0.1` only** (compose `ports: "127.0.0.1:3000:3000"` style), are not published
  to the host network beyond localhost, and consume only the bounded-label `/metrics`
  text. Scraping logs is explicitly forbidden; the dashboard contains no PII by test.

---

## 15. Failure Isolation

Extends the P2.1 contract to the new components:

| Component | Failure mode | Impact on app | Guarantee |
|---|---|---|---|
| Metrics emitter (`safe_*`) | any exception swallowed | none | tested (`test_broken_metrics_never_fail_extraction`) |
| Log formatter/emitter | swallowed | none | tested (`test_broken_logging_never_fails_extraction`) |
| TracingService (stage 9) | silent-fail | none | existing |
| LangSmith | silent-fail, opt-in only | none | existing |
| Prometheus sidecar (P2.2) | scrape error / container down | none | app never calls the sidecar; scrape is pull-only |
| Grafana sidecar (P2.2) | dashboard unavailable | none | depends_on prometheus only |
| Alert rules (P2.2) | rule error | none | `promtool check rules` in CI/verification; rules are data, not code |

Constitution-aligned rule enforced: the app process must never import, connect to, or
wait on Prometheus/Grafana. All observability infrastructure is **pull-side** and
containerized; the P2.1 in-process `prometheus-client` registry stays the only
in-app observability mechanism.

---

## 16. Test Strategy (P2.2)

Deterministic, no time-dependent assertions (AGENTS.md §Testing).

| Layer | Tests to add | Verification |
|---|---|---|
| Unit — shutdown event | shutdown drains N queued tasks → event `abandoned=N`; gauges 0; idempotent 2nd shutdown silent | pytest (extraction suite) |
| Unit — info metric | `owngpt_memory_extraction_info{enabled="1"}` present when extraction enabled; absent/wrong on config | pytest (observability suite) |
| Unit — dashboard | `ops/grafana/dashboards/owngpt-extraction.json` parses; contains no forbidden labels; every panel references a real metric name (from the metrics.py registry) | pytest (new `tests/ops/test_grafana_dashboard.py`)(*) |
| Unit — rules file | `ops/prometheus/rules/extraction.yml` parses; 5 rules present; expressions reference known metric names | pytest (new `tests/ops/test_prometheus_rules.py`) or `promtool check rules` |
| Deterministic rule behavior | `promtool test rules` YAML for all 5 rules (fixed series in, expected fires out) | `promtool test rules` in CI/verification step (**) |
| Live integration (compose profile) | `docker compose --profile observability up`; scrape `http://localhost:8000/metrics` via Prometheus target UP; `/metrics` still 200 + `application/octet-stream`-formatted text | manual verification step, documented in implementation record |

(*) `tests/ops/` is a new directory only if P2.2 is approved with Option C — test
counts and locations land in the P2.2 implementation record.
(**) `promtool` is used from the `prom/prometheus` container; it is a verification step,
not a new Python dependency.

No changes to existing suites are anticipated; current full-suite baseline is 310
collected / 308 passed / 2 failed (pre-existing OpenAI quota pair) and must stay 308/2.

---

## 17. P2.2 Scope (recommended implementation plan)

Scope when implementation starts (this audit is read-only):

**A. Infrastructure (new files, ops/):**
1. `ops/prometheus/prometheus.yml` — scrape config: `web:8000/metrics`
   (job name `owngpt-web`), 15s interval, localhost-only publish in compose profile.
2. `ops/prometheus/rules/extraction.yml` — the 5 rules from §10.
3. `ops/prometheus/tests/extraction_test.yml` — `promtool test rules` cases.
4. `ops/grafana/provisioning/datasources/prometheus.yml` —
   auto-provisioned Prometheus datasource.
5. `ops/grafana/dashboards/owngpt-extraction.json` — §9 dashboard.
6. `docker-compose.observability.yml` (or a `profile: ["observability"]` section in
   the existing compose) — services `prometheus`, `grafana`; host binds loopback-only;
   `grafana` depends_on `prometheus`; **profile is off by default** — devs never pay
   the cost unless they opt in.
7. Verification script/docs — exact commands incl. `promtool check rules`,
   `promtool test rules` (containerized), dashboard validation.

**B. Application (the only tracked code changes in P2.2):**
1. Executor shutdown event with `abandoned=<n>` + gauge reset (§12) — ~5 lines in
   `app/learning/extraction/executor.py` + tests.
2. `owngpt_memory_extraction_info{enabled="1"}` constant info gauge (§10 note) —
   ~3 lines in `app/core/metrics.py` + one test.

**C. Docs:** update `docs/v22_p2_observability_implementation.md` (P2.2 section) and
this audit's follow-up record. Capability Registry: no change — Grafana/Prometheus is
infrastructure, not a new subsystem; extraction capability `api_prefix`/artifacts
unchanged.

**D. Explicitly NOT in P2.2:** LangSmith extraction wiring, OTel/OTLP, request→run
correlation, cost dashboards, Redis latency metrics, log aggregation (Loki), healthcheck
hardening for `/health`.

---

## 18. P2.3 Deferred (with explicit triggers)

| Item | Trigger that justifies it |
|---|---|
| OpenTelemetry + OTLP (traces) | >1 app instance or a real cross-service trace query request; any deployment outside compose |
| LangSmith extraction trace tree | operator demand for multi-day extraction debugging UI in SaaS + acceptance of sanitized-input design (prompts/statements never leave the box until then) |
| request→run_id correlation (`req_id` at `schedule_extraction` call sites) | support tickets that actually require joining HTTP logs with extraction logs |
| Cost ($) dashboard incl. embeddings | paid OpenAI/embedding usage resumed AND a billing question asked |
| Redis latency histogram | evidence of slow claims/fallback spikes with healthy Redis |
| Trace-context tests / LangGraph parent spans | absorbed into the OTel item above |

Decision rule for all of the above: add complexity when the operational question exists
and none of the current telemetry answers it — never pre-emptively.

---

## 19. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Unauthenticated `/metrics` | low (compose local) | loopback-only publish; internal network; documented; bounded labels make it PII-free |
| Dashboard/rules drift from code | medium | provisioning-as-code + versioned JSON + `tests/ops/` validation + `promtool check/test` step |
| Cardinality regression (someone adds an id label) | low | existing label-set validation + forbidden-label tests; extend the dashboard test to assert no id labels |
| Alert fatigue | medium | exactly 5 rules; sane `for` durations; `promtool test rules` pins behavior |
| Prometheus/Grafana down | medium | sidecars; app unaffected; rule `up` panel shows it; alert on `up{job="owngpt-web"} == 0` not on sidecar health |
| Inflight gauge stale during teardown | low | shutdown event + gauge reset (§12) documents and clears it |
| LangSmith/OTel premature adoption | n/a | rejected/deferred with triggers (§6, §7, §18) |
| PipelineTrace question content exposure (pre-existing) | low | internal Redis only; flagged; out of P2.2 scope; per-owner UI guard if ever exposed |

---

## 20. Final Architecture Decision

**ADOPT Option C for P2.2.**

One decision, stated without qualification:

> Keep the P2.1 in-process metric + structured-log surface as the single source of
> extraction telemetry. Make it visible — not more complex — by adding Prometheus and
> Grafana as loopback-only, opt-in docker-compose sidecars with dashboard-as-code and
> exactly five alert rules, plus the executor shutdown abandoned-count event and an
> extraction-enabled info gauge as the only application code changes. LangSmith
> (Option A) and OpenTelemetry (Option B) are rejected for P2.2; tracing in any form is
> not justified for this topology yet, and each deferred item has an explicit trigger in
> §18 before it may be re-opened.

This preserves every P2.1 invariant (bounded labels, fail-open, privacy, executor-owned
inflight), adds no new runtime dependency to the application process, and converts the
largest remaining defect — a metric registry nobody can see — into dashboards and
warnings with the minimum architectural surface.

---

## Appendix A — Files Inspected (this audit, at `be04257`)

Application:
- `app/core/config.py`, `app/core/logging_config.py`, `app/core/metrics.py`,
  `app/core/observability.py`, `app/core/langsmith.py`, `app/core/llm_provider.py`,
  `app/main.py`, `app/services/embeddings.py`
- `app/learning/extraction/observability.py`, `executor.py`, `coordinator.py`, `extractor.py`
- `app/agent/pipeline/tracing.py`, `app/agent/pipeline/pipeline.py` (tracer wiring),
  pipeline stage decorators (intent, router, rewrite, retriever, reranker, confidence,
  planner, source_validator, evidence_builder, validation)
- `app/api/endpoints/chat.py` (schedule_extraction call sites: lines 419–420, 898–899;
  request_id idempotency; token counting), `app/services/chat_persistence.py`
- `requirements.txt`, `docker-compose.yml`

Tests:
- `tests/learning/test_extraction_observability.py` (37 tests, enumerated),
  `tests/learning/test_extraction.py`, `tests/learning/test_extraction_execution.py`,
  `tests/pipeline/test_pipeline.py` (`trace_enabled: False` fixture surface)

Git history inspected:
- `1d04605` (V2.1), `e708845` (V2.2), `8c9bb71` (Ollama), `8eeca8a` (P1),
  `be04257` (P2.1 — `git show --stat`: 15 files, +2914/−91; LangSmith/tracing/stage-9
  infra predates P2.1 and was untouched by it)

## Appendix B — Audit Closure

- Files created by this audit: exactly one — `docs/v22_p2_observability_audit_p22.md`.
- Working tree contains **only** this untracked audit document.
- P2.2 implementation has **NOT** started. No code, test, config, or compose changes
  were made by this audit.
- P2.1 audit record (`docs/v22_p2_observability_audit.md`) and implementation record
  (`docs/v22_p2_observability_implementation.md`) exist in `be04257` and are untouched.