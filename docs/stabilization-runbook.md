# OwnGPT — 7-Day Real-World Stabilization Runbook

Architecture is FROZEN. This period is for OBSERVATION, not feature development.
No V5. No new architecture. No refactors of working subsystems. No premature
optimization.

- Commit under test: `9d1347f` (`feat(platform): complete agent platform and observability`)
- Branch: `feature/frontend-redesign`
- Pre-flight: GO — blockers 0 — 7-day test ready

---

## Environment

### Start the backend (option A — local dev)

```powershell
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Start the backend + monitoring (option B — docker compose, recommended)

```powershell
docker compose --profile monitoring up
```

This starts web, worker, db, redis, ollama, prometheus, grafana, frontend.
A plain `docker compose up` never starts the monitoring services.

### Start the frontend (local dev, if not using compose)

```powershell
cd frontend
npm run dev
```

Frontend: http://localhost:5173 (backend API base is hardcoded to
`http://localhost:8000/api/v1` in `frontend/src/features/chat/services/chatApi.ts`).

### Authentication requirement

`AUTH_ALLOW_SINGLE_USER_FALLBACK` (default **false**, `app/core/config.py`)
controls whether unauthenticated requests are accepted.

Testers must EITHER:

- authenticate normally (sign up / log in via `/auth/signup`, `/auth/login`,
  send the returned bearer token, or store it), OR
- intentionally configure the fallback for the local single-user environment:

```
# .env (local test only — never in production)
AUTH_ALLOW_SINGLE_USER_FALLBACK=true
```

The fallback only applies when exactly one user exists in the database; with
zero or multiple users unauthenticated requests get 401.

### Environment variables

Required in `.env` (or environment):

- `OPENAI_API_KEY` (chat default model; `VITE_DEFAULT_MODEL` on the frontend)
- `TAVILY_API_KEY` (web search tool)
- `LANGCHAIN_API_KEY` + tracing settings after `setup_langsmith()` — optional
- `AUTH_ALLOW_SINGLE_USER_FALLBACK=true` (see above)
- Monitoring profile only: `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`
  (weak values rejected by design; do not use `admin/password`)

### Prometheus / Grafana access (compose monitoring profile)

- Prometheus: http://127.0.0.1:9090 (scrapes `web:8000/metrics` every 15s, 15d retention)
- Grafana: http://127.0.0.1:3000 (use the configured admin credentials)

Dashboards auto-provisioned from `ops/grafana/dashboards/`:

- `owngpt-agent` (uid `owngpt-agent`) — agent requests, latency, tokens, cost,
  tool calls/failures/blocks
- `owngpt-extraction` — memory extraction observability

Bounded labels only: no user/session/message/run IDs ever appear in Prometheus.

---

## Daily Testing Areas

Each day exercises real application usage, not synthetic smoke tests.

### Day 1 — Core Chat

- normal questions, conversation history, new chat
- streaming, stop (Stop button must stop the stream immediately)
- error handling (bad model name, provider outage message)

### Day 2 — Projects + Isolation

- create project, switch project (switch must open a NEW session per project)
- create chat inside a project, upload project documents
- retrieval scoped to the project
- **verify Project A cannot see Project B content** (documents, retrieval, history)

### Day 3 — Knowledge + Citations

- PDF / TXT / MD upload, ingestion, retrieval
- citations rendering, source inspection, missing-evidence behavior
- grounded vs ungrounded answers (claim validation events)

### Day 4 — Web + Agent

- web search mode, multi-step questions, tool selection
- blocked tools (deny-list / unregistered), failed tools, partial execution

### Day 5 — Reliability + Security

- timeout, cancellation, provider/tool failure, malformed inputs
- prompt-injection attempts, secret-like content, PII-like content
- verify nothing sensitive appears in: UI, logs, AgentTrace, SSE, Prometheus,
  Grafana (pay attention to `owngpt_*` metric labels and log files)

### Day 6 — Observability + Cost

- from Grafana/Prometheus verify: requests, latency, tool calls, failures,
  blocked calls, tokens, cost, model usage — cross-check against actual
  requests you made that day (single accounting source duty)

### Day 7 — Full End-to-End

- use OwnGPT as a real product with mixed workflows:

```
Project → document → retrieval → web → multi-step agent → citations → memory → follow-up
```

- record anything unexpected

---

## Bug Classification

| Class | Meaning | Action |
|---|---|---|
| P0 | Security breach, data leakage, corruption, catastrophic failure | investigate immediately |
| P1 | Core functionality broken or unreliable | investigate immediately |
| P2 | Usability/reliability issue, product still valid | record, continue unless it materially affects the test |
| P3 | Cosmetic, cleanup, enhancement, debt | record, continue |

On any bug: reproduce → capture evidence → classify → determine if it is an
architecture flaw or an isolated bug → fix only if necessary → add regression
coverage → re-run affected tests → resume testing.

Never immediately redesign architecture because a bug was found.

---

## Daily Bug Log

Keep a per-day log (file `reports/stabilization-day-N.md` or equivalent) with:

- date, area, repro steps, evidence (trace/metrics/log excerpts), classification,
  fix-or-deferred decision, regression test added (if any)

---

## Known Technical Debt (do NOT fix automatically)

1. 55 pre-existing frontend TypeScript errors in untouched legacy/demo files
   (`npm run build`'s `tsc -b` step fails; `vite` dev/runtime unaffected).
2. 66 lint warnings (0 errors).
3. No server-side cooperative cancellation of the LangGraph worker — client
   disconnect leaves the background thread to complete and persist the response.
4. Single-user auth fallback must be intentionally configured for local testing.
5. `/chat/evaluate` uses `project_id=""` (eval runs are not conversations).
6. Other non-blocking legacy/demo UI issues.

These belong to future stabilization/V5 planning unless testing proves otherwise.