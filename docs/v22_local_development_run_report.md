# V2.2 Local Development Run Report

Date: 2026-08-16
Environment: Windows host + Docker Desktop (WSL2), CPU-only (no GPU)
Repo: own_gpt @ `be04257` (branch `feature/frontend-redesign`)

---

## 1. What is running (all `docker compose` services)

| Service   | Image / Command                    | Port             | Status |
|-----------|------------------------------------|------------------|--------|
| db        | ankane/pgvector (PostgreSQL 15.4)  | 5432 (host)      | up     |
| redis     | redis:7-alpine                     | 6379 (host)      | up     |
| ollama    | ollama/ollama:latest               | internal only    | up (healthy) |
| web       | build `.` + `uvicorn --reload`     | 8000             | up     |
| worker    | build `.` + arq `WorkerSettings`   | —                | up     |
| frontend  | vite dev server (HMR)              | 5173             | up     |
| prometheus| prom/prometheus:v3.13.2 (opt-in)   | 9090             | up     |
| grafana   | grafana/grafana:13.1.3 (opt-in)    | 3000             | up     |

Canonical start command (dev): `docker compose up -d`
Monitoring (opt-in, never started by the plain command):
`$env:GRAFANA_ADMIN_USER=...; $env:GRAFANA_ADMIN_PASSWORD=...; docker compose --profile monitoring up -d prometheus grafana`

## 2. URLs

- Frontend (browser): http://localhost:5173
- Backend API + Swagger: http://localhost:8000/docs, health http://localhost:8000/health
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090  |  Grafana: http://localhost:3000
- Runtime facts: model allowlist served by backend at runtime (client may only pick `llama-3.3-70b-versatile`); auth = `AUTH_ALLOW_SINGLE_USER_FALLBACK=true` (no login needed; exactly 1 user exists).

## 3. Smoke test results (API level, real app)

| Check | Result |
|---|---|
| `GET /health` | ok |
| `GET /api/v1/system/status` | ok — postgres, pgvector (382 chunks), Whoosh BM25 (382 docs), ollama reachable (nomic-embed-text + qwen3:8b) |
| Auth (no header, single-user fallback) | works — all smoke requests reached the pipeline |
| `POST /api/v1/chat/stream` (Groq, general chat) | **200, SSE streamed ~4.5 KB**, tokens visible; assistant message persisted `status=completed`; `GET /chat/{id}/history` returns both messages |
| Extraction scheduling | `owngpt_memory_extraction_scheduled_total = 1` after the turn; `owngpt_memory_extraction_info{enabled="1"} = 1` |
| `GET /metrics` | 200, counters present |
| Prometheus targets | owngpt-web: up, prometheus: up; `sum(owngpt_http_requests_total) = 2` |
| Grafana | login (Basic auth on API) ok with container env creds; datasource `Prometheus` + dashboard `OwnGPT Memory Extraction` provisioned |
| Frontend | 200; served `ChatLayout` module contains the baked `VITE_DEFAULT_MODEL` (= `llama-3.3-70b-versatile`) |
| **Grounded KB chat** (after embeddings fix, §4.6) | **200, SSE 29 KB, 9.9 s** — `stage=retrieval retrieved=20 top_score=0.6216 latency_ms=8333.4`, hybrid RRF `bm25=20`, confidence 1.0 → answer; both messages persisted `completed` |

Cleanup: all `smoke-*` conversations, messages, and LangGraph checkpoints deleted after testing.

## 4. Local-run blockers found + fixes applied (working tree, NOT committed)

1. **`app/agent/pipeline/rewrite.py` — UnboundLocalError → every knowledge question 500.**
   The `except` path referenced `elapsed`, which is only assigned inside `try` after the
   LLM call. When the rewrite LLM failed (e.g. provider/model mismatch), the exception
   handler itself crashed. Fixed: compute latency in the except path from `start`.
   (Same signature as the 2 pre-existing suite failures' secondary symptom.)
2. **`pipeline_config.yaml` — OpenAI-only model names under the Ollama/Groq provider.**
   `intent_model/rewrite_model/validation_model` were `gpt-4o-mini`; with
   `LLM_PROVIDER=ollama|groq` every build_llm call requested a model that does not exist
   (Ollama 404 / Groq 404). Now `""` with an explanatory comment — empty resolves the
   provider default via `build_llm` (LLM_MODEL / GROQ_MODEL). Provider-agnostic config.
3. **`docker-compose.yml` (ollama) — 8B model could never load on this CPU box.**
   Default Ollama load timeout (5 min) is far below the ~15 min this machine needs
   (883 s measured for llama-server start). Added `OLLAMA_LOAD_TIMEOUT=30m` +
   `OLLAMA_KEEP_ALIVE=10m`.
4. **New `groq` LLM provider (user-approved, part of this run's unblocking).**
   - `app/core/config.py`: `GROQ_API_KEY`, `GROQ_BASE_URL`, `GROQ_MODEL` (default
     `llama-3.3-70b-versatile`).
   - `app/core/llm_provider.py`: `_build_groq` — ChatOpenAI against the OpenAI-compatible
     Groq base URL; fails clearly without `GROQ_API_KEY`; no fallback (provider boundary
     invariants preserved). Module docstring updated.
   - `app/core/model_config.py`: allowlist/DEFAULT_MODEL for `LLM_PROVIDER=groq`
     (`[GROQ_MODEL]`), mirroring the Ollama pattern.
   - `tests/core/test_llm_provider.py`: 4 new groq cases (selection/base_url/model
     passthrough/max_tokens/missing-key refusal) — all pass (`pytest exit 0` on
     llm_provider + model_config files).
   - Local `.env` (gitignored, never committed): `LLM_PROVIDER=groq`,
     `GROQ_MODEL=llama-3.3-70b-versatile`, `GROQ_API_KEY=<user-supplied>`.
5. **Frontend hardcoded `model: 'gpt-4o-mini'`** (ChatLayout, DocumentChat, OwnGPTPage,
   SettingsModal). The server allowlist rejects it under groq → 400. Made the default
   env-driven: `import.meta.env.VITE_DEFAULT_MODEL || 'gpt-4o-mini'`; SettingsModal
   prepends a "Default model" entry. `frontend/.env.local` (gitignored) sets
   `VITE_DEFAULT_MODEL=llama-3.3-70b-versatile`.
6. **KB retrieval embeddings → local Ollama (was OpenAI, zero credits → 429 → 500).**
   `app/services/vector_store.py` switched `OpenAIEmbeddings` to
   `OllamaEmbeddings(model=settings.OLLAMA_EMBEDDING_MODEL)` (`nomic-embed-text`,
   768-dim). Migration: deleted the 763 OpenAI rows (`langchain_pg_embedding` +
   `langchain_pg_collection`), re-uploaded the 4 corpus PDFs → worker re-embedded to
   **382 chunks** (`40 + 96 + 107 + 139`; pgvector == whoosh == 382). Old worker image
   (2 weeks old) lacked `langchain_ollama` → rebuilt with `docker compose build worker`.
   No schema migration needed: `embedding` column is untyped `vector`.
7. **Memory extraction silently failed under Groq** — `extractor.py` hardcoded
   `gpt-4o-mini` unless provider == ollama → Groq 404 → extraction errors every turn.
   Now provider-aware: `LLM_MODEL` (ollama) / `GROQ_MODEL` (groq) / `gpt-4o-mini`
   (openai fallback). Remaining `gpt-4o-mini` references are comments, OpenAI
   allowlists, or pricing constants — no active runtime hardcodes.

## 5. Known limitations (reported, NOT fixed — out of local-run scope)

- **Groq tool calls are intermittent.** llama-3.3-70b-versatile occasionally emits a
  malformed tool call → Groq `failed_generation` → streamed 500 (observed twice,
  e.g. on a pure "give me questions only from the docs" request). Retrying the same
  question succeeds (verified). The graph always binds tools (`graph.py:208`); a
  retry wrapper there is a design decision, deliberately not added in this run.
- **Session titles fall back to message prefix.** `_generate_session_title` passes
  `settings.DEFAULT_MODEL` (`gpt-4o-mini`) into `build_llm`; Groq/Ollama reject the
  name → caught → `message[:30] + "..."`. Cosmetic only.
- **Generations are uncapped** on the graph LLM (no max_tokens) — fine on Groq
  (~20-60 s), was the reason Ollama turns appeared to hang (multi-thousand-token
  qwen3 thinking blocks at ~3-8 tok/s CPU).
- 2 pre-existing suite failures (quota pair, OpenAI 429 in `rewrite.py` path) —
  unchanged, documented previously; unrelated to this run.

## 6. Performance facts (evidence)

- Ollama qwen3:8b on this machine: llama-server start **884 s**; first generation
  attempt timed out at 314 s with default timeout.
- Groq: `/chat/completions` 200 in **~190 ms** (HTTP round-trip); full streamed turn
  with persistence in well under a minute.

## 7. Manual browser checklist (left running for the user)

1. Open http://localhost:5173 — Chat page loads; session list empty.
2. Send "Hello! What can you help me with?" → streamed answer from Groq in seconds;
   conversation appears in the sidebar with a title.
3. Open http://localhost:3000 (Grafana) and log in — dashboard "OwnGPT Memory
   Extraction": extraction scheduled / completed counters tick after 1-2 chat turns
   (worker + Groq extractions run async).
4. Open http://localhost:9090 — Prometheus: select
   `owngpt_http_requests_total`, `owngpt_memory_extraction_*`.
5. Settings modal: model selector shows "Default model" first (works) — do not pick
   the OpenAI entries (server rejects them under groq).
6. Knowledge-base questions now work (see §3 grounded row). First embedding query
   takes ~8 s on CPU (nomic model cold-load) — subsequent ones are faster.
7. If a chat turn returns a 500 ("Failed to call a function"), just resend — Groq
   tool-call error is intermittent (§5).

## 8. Git status (nothing committed)

17 modified + 5 untracked. P2.2 observability changes (of which
`app/core/metrics.py`, `observability.py`, `executor.py`, `main.py`,
`tests/learning/test_extraction_observability.py`, `docs/…implementation.md`,
`docker-compose.yml` monitoring additions, `ops/`, `tests/ops/`,
`verify_p2_2_observability.ps1`, audit doc) remain staged-for-review from the last
checkpoint (commit still awaiting approval). This local-run session added:
`rewrite.py`, `pipeline_config.yaml`, `llm_provider.py`, `config.py`,
`model_config.py`, `vector_store.py`, `docker-compose.yml` (ollama env block),
`frontend/*` (4 files), `tests/core/test_llm_provider.py` (groq tests),
`app/learning/extraction/extractor.py` (provider-aware extraction model).
No secrets in the tree: `.env*` are gitignored (`.gitignore` covers `.env`);
`frontend/.env.local` matches `*.local` in `frontend/.gitignore`.