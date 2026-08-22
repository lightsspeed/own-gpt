# V2.2 Provider Compatibility & Reliability Audit

Date: 2026-08-16
Scope: multi-provider (OpenAI / Groq / Ollama) compatibility, Groq 500 root cause, error contract, embedding architecture, observability, security.
Status: **AUDIT ONLY** — no code, migration, schema, reindex, or commit changes were made.

---

## 1. Executive Summary

OwnGPT's **provider factory boundary is clean** (`app/core/llm_provider.py` `build_llm`, 3 providers, no cross-provider fallback, clear construction errors), but the **application is provider-agnostic by accident, not by design**:

- **The Groq 500 is a model-side tool-call failure, surfaced raw by OwnGPT.** The agent graph binds 5 tools unconditionally (`graph.py:208`) and has **no retry and no error classification** (`chat.py:949-964`). llama-3.3-70b-versatile intermittently emits a tool call that fails Groq's strict parser → Groq HTTP 400 `tool_use_failed` ("failed_generation") → langchain `APIError` → SSE `error` event with the raw provider text (reproduced, evidence in §4). Pure "generation without tools" is stable (verified 200 back-to-back; direct API probes 8/8).
- The HTTP 500s the browser reported pre-date the embedding fix: OpenAI embedding 429s during retrieval raised **pre-stream** at `chat.py:986-988` → true HTTP 500. That path is fixed (KB embeddings now local), but the failure currently being seen is the mid-stream provider-error path → **HTTP 200 + SSE error event** (log-verified: `req_id=f11948d4` status=200).
- **Three provider-specific leaks remain**: `settings.DEFAULT_MODEL` is passed raw to the provider in session-title generation (`chat.py:171`) and episodic consolidation (`episodic.py:123`) — under Groq/Ollama this requests `gpt-4o-mini` (silently falls back / fails); RAG embeddings and memory embeddings use **two different abstractions** (KB = concrete `OllamaEmbeddings` module singleton; memory = `EmbeddingProvider` protocol, OpenAI 1536 pinned); chat LLM calls are **unobservable** (Prometheus metrics cover only memory extraction).
- **Verdict: YELLOW.** The boundary architecture is sound and fixable with bounded, staged changes; it is NOT yet production-safe for multi-provider (raw provider errors to clients, no retry, no capability registry, unauthenticated information-endpoints). See §13-16.

---

## 2. Current Provider Architecture

| Layer | Location | Notes |
|---|---|---|
| Config | `app/core/config.py:48` `LLM_PROVIDER` (default `ollama`); `:96-100` embedding/memory settings; `:72-74` `SUPPORTED_MODELS`, `DEFAULT_MODEL` (`gpt-4o-mini`) | `.env` (gitignored) currently `LLM_PROVIDER=groq`, `GROQ_MODEL=llama-3.3-70b-versatile` |
| LLM factory | `app/core/llm_provider.py:98-120` `build_llm` → `_build_openai` :41-58 / `_build_ollama` :61-74 / `_build_groq` :77-95 | No fallback (invariant, :10-19), errors name the env var only (:44-48, :80-84) |
| Model policy | `app/core/model_config.py:35-48` allowlists + `DEFAULT_MODEL` per provider; `resolve_model` :55-63; `validate_temperature` :66-75 | Static name lists — **no capability metadata** |
| Agent | `app/agent/graph.py:208` `bind_tools(tools)` always; :210 `invoke(payload)` | 5 tools (`app/agent/tools.py:60`) |
| Pipeline LLMs | intent `intent.py:166-167`, rewrite `rewrite.py:71-72`, validation `validation.py:75-76` — all degrade to safe defaults on failure (:209-218, :106-116, :119-121) | `pipeline_config.yaml` model keys `""` → provider default |
| Extraction | `extractor.py:62-66` provider-aware `EXTRACTION_MODEL`; :174 build; :190-228 one retry; Gate 3 deterministic batch-atomic :231-270 | The only LLM site that is provider-correct by construction |
| Title/Episodic | `chat.py:171`, `episodic.py:123` — `settings.DEFAULT_MODEL` raw | ⚠️ provider-mismatch leak (§6-A) |
| Embeddings | KB: `vector_store.py:17-20` module-level `OllamaEmbeddings` (768). Memory: `embeddings.py:34-96` `EmbeddingProvider` protocol, OpenAI 1536 (`models/memory.py:118` `vector(1536)`) | Two stacks, one leak (§7) |

Deployment: Groq primary (CPU-only box, Ollama qwen3:8b too slow); Ollama serves embeddings (nomic-embed-text 768).

---

## 3. LLM Capability Matrix

Every LLM call site (all facts verified at the cited lines):

| # | Pipeline stage | File:line | Model source | Temp | max_tokens | Streaming | Tool calling | Structured output / JSON | Retry | Fallback | Failure behavior | Provider-specific assumptions |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Agent `call_model` | `graph.py:210` (build :71, bind :208) | request → `resolve_model` allowlist (`chat.py:229-236`) | 0.4 (`graph.py:205-207`) | none | no (sync invoke; streaming via `graph.stream` chunk forwarding in `chat.py:783-795`) | **yes — 5 tools, always bound** | none — plain text | **none** | **none** | raw exception → `chat.py:949` handler | OpenAI-style tool_calls assumed (Groq model emits them unreliably — §4) |
| 2 | Session title | `chat.py:168-180` (build :171) | **`settings.DEFAULT_MODEL` = "gpt-4o-mini"** | 0 | none | no | no | prompt-instructed only | none | `message[:30]…` (:178-180) | degrades silently | ⚠️ raw OpenAI name against Groq/Ollama → 404, swallowed |
| 3 | Intent classification | `intent.py:166-167,196` | `pipeline_config["intent_model"]` (`""` → provider default, `pipeline.py:137-139`) | 0 | 64 | no | no | prompt JSON, `json.loads` (:200) | none | rule-fallback → UNKNOWN/0.4 (:209-218) | degrades | none (docstring claims gpt-4o-mini — stale) |
| 4 | Query rewrite | `rewrite.py:71-72,93` | `rewrite_model` (`""` → default, `pipeline.py:142-144`) | 0 | 256 | no | no | prompt JSON (:98) | none | no-op rewrite (:106-116) | degrades | none |
| 5 | Response validation | `validation.py:75-76,113` | `validation_model` (`""` → default, `pipeline.py:177-179`) | 0 | 64 | no | no | prompt JSON (:117) | none | rule Tier-1 only (:136-139); else invalid-flagged | degrades (never raises) | none (docstring stale: "gpt-4o-mini") |
| 6 | Confidence | `confidence.py:61-65` | n/a | — | — | — | — | — | — | — | rule-based, no LLM | — |
| 7 | Retrieval / RAG | `retriever.py:106`, `hybrid.py:103-190`, `reranker.py:74` | n/a (embeddings + FlashRank) | — | — | — | — | — | — | — | **raises** → bubbles (`pipeline.py` process() has no try/except) | embedding provider, §7 |
| 8 | Memory extraction Gate 2 | `extractor.py:174,196` | `EXTRACTION_MODEL` provider-aware (:62-66) | 0.0 | none | no | no | prompt JSON (`json.loads` :211) | **1 retry per batch** (:190) | Gate 3 validators drop batch (:231-270) | never raises (:349-356 → failed) | token_usage reading OpenAI-style, Ollama-conditional (:135-158) |
| 9 | Episodic recall summarization | `episodic.py:123,133` | **`settings.DEFAULT_MODEL` (gpt-4o-mini)** | 0.0 | none | no | no | prompt-instructed | none | `""` summary skipped (:137-139) | degrades | same leak as #2 |
| 10 | Graph `invoke` (non-stream) | `chat.py:343` | same as #1 | same | none | no | yes | no | none | none | caught → generic 500 (`chat.py:431-433`) | same as #1 |
| 11 | Graph `invoke` (evaluate) | `chat.py:1048-1052` | `resolve_model(None)` | `TEMPERATURE_DEFAULT` | none | no | yes | no | none | none | same as #1 | same as #1 |

Notes:
- `with_structured_output` / JSON-mode: **zero occurrences** in the repo. All structured output is prompt-instructed + `json.loads`. Tool binding: exactly one occurrence (`graph.py:208`).
- Retry exists only in extraction (once) and ingestion/embedding jobs (`jobs.py:67`, `processor.py:40-41`) — **never on chat-model calls**.
- Streaming: the graph streams via LangGraph `stream_mode=["messages","updates"]`; the underlying `invoke` is non-streaming per node — token chunks are forwarded (`chat.py:788-795`), so provider streaming is thrice-translated, but works.

---

## 4. Groq Failure Root Cause

### Observed symptom (exact user-visible text)
`Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details.`

### Reproduction (this audit, live app)
POST `/api/v1/chat/stream` with `"remember that my favorite color is electric blue"`:
- **First attempt → reproduced exactly**: SSE `{"type":"error","message":"Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details."}`. Server log: `11:59:44Z ERROR Stream thread error: Failed to call a function… error_class=APIError req_id=f11948d4`; the HTTP request logged `status=200 duration_ms=7203.7`.
- Follow-up: 5/5 identical in-app requests succeeded; 8/8 direct Groq API probes (same model, same tool schema, same message) returned 200 with a valid `tool_calls` payload.

### Full trace
```
Frontend browser (POST /api/v1/chat/stream)
 → chat.py:666-694 pre-stream (idempotency, persist user msg)
 → chat.py:694   _run_pipeline (intent → rewrite → retrieval → rerank → confidence) [OK]
 → chat.py:783   graph.stream (worker thread)
 → graph.py:210  model_with_tools.invoke(payload)
                 (model_with_tools = build_llm(...).bind_tools(tools) at graph.py:208)
 → langchain_openai ChatOpenAI → Groq POST /chat/completions (tools bound)
 → Groq responds HTTP 400:
     {"error": {"message": "Failed to call a function. Please adjust your prompt.
       See 'failed_generation' for more details.",
       "type": "invalid_request_error", "code": "tool_use_failed"}}
 → langchain_openai raises APIError   (verified: error_class=APIError in server log)
 → propagates through graph.stream generator
 → caught at chat.py:949 → SSE error event emitted at chat.py:957 (raw str()) → [DONE] (:963-964)
 → HTTP 200 (response already committed)
```

### Mechanistic root cause (multi-source evidence)
- Groq's `tool_use_failed` / `failed_generation` error code means **the model produced a tool call that Groq's strict OpenAI-style tool-call parser rejected** (Groq error class `invalid_request_error`, HTTP 400).
- The same error string is extensively documented against **llama-3.3-70b-versatile specifically** in LangChain/LangGraph, AutoGen, smolagents, and litellm projects: the model intermittently emits a non-native tool-call fragment (`<function=name{...}</function>` XML, or malformed/truncated `tool_calls` JSON) instead of valid OpenAI `tool_calls`, and Groq rejects it. It is a **model-side nondeterministic emission failure**, not an OwnGPT schema bug — we verified the tool schemas are accepted (direct probe 8/8).
- Why OwnGPT makes it user-visible: `graph.py:208` binds tools **on every turn regardless of provider or model capability**; there is **no retry** at `call_model`, the provider layer, or the endpoint; and the exception text is sent verbatim to the client (`chat.py:957`).
- Whether it is "the" 500: **in-stream it is an SSE error event (HTTP 200), not a 500.** Genuine HTTP 500s observed in the browser occurred pre-stream from the OpenAI embedding 429 (`credit_balance_exhausted`) during retrieval, caught by the outer handler at `chat.py:986-988` → `500 internal_error`. That failure mode is resolved since KB embeddings moved to Ollama (retrieval verified: `retrieved=20 top_score=0.6216`).

### Classification answer
Cause = **model capability limitation** (llama-3.3-70b-versatile tool-call reliability on Groq) × **missing retry** × **un-classified error surfacing**. Not: malformed OwnGPT tool schema (probed clean), not with_structured_output (unused), not JSON parsing, not streaming/tool interaction (fails identically in non-streaming invoke), not provider adapter construction (base_url/model correct).

---

## 5. HTTP/SSE Failure Analysis

Endpoint: `chat.py:660-988`. Two failure surfaces exist:

**A. Pre-stream** (`chat.py:667-988` outer try): auth 401, ownership 404, idempotency 409, model-config 400 via `api_error`; anything else → `chat.py:986-988` **generic 500 `internal_error`** (details only in logs). Includes the entire pipeline (`_run_pipeline` `chat.py:694` — which has no internal try/except at `pipeline.py:process()`), so a retrieval/embedding failure becomes a raw HTTP 500.
→ This is where the observed browser-visible `POST ... 500` came from (embedding 429 era). Current risk: Ollama embedding outage/timeout, DB outage.

**B. Mid-stream** (worker thread, `chat.py:782-963`): any graph/provider error → SSE `{"type":"error","message":str(thread_err)}` (`chat.py:957`) with **raw provider exception text**, then `[DONE]` (`:963-964`). Partial accumulated tokens are persisted as `MESSAGE_STATUS_FAILED` with `error[:2000]` (`:958-961`); no output → no fabricated assistant row. HTTP status stays 200.

Failure-mode matrix (as-implemented):

| Failure | When | HTTP | Client receives | Persisted |
|---|---|---|---|---|
| Model fails pre-token (in graph) | any turn | **200** | SSE error event (raw text) + [DONE] | partial → failed, none → nothing |
| Model fails after tokens streamed | any turn | 200 | content events + SSE error event + [DONE] | partial text, status failed |
| Tool call fails (Groq `tool_use_failed`) | tool turns | **200** | SSE error event (raw provider text) | (usually nothing — no tokens) |
| Structured output fails | pipeline stages | n/a (degrade) | n/a | n/a |
| Provider timeout | graph invoke | 200 (mid) / 500 (pre-stream road) | raw text / internal_error | as above |
| Retrieval/embedding failure | pre-stream | **500** | generic JSON | (user msg persisted only) |
| Malformed output (bad JSON) | pipeline stages | n/a (degrade/validate) | n/a | n/a |

**Contract verdict:** the mid-stream SSE contract is *mechanically* valid (error event always precedes `[DONE]`) but **semantically insufficient**: raw provider text leaks out (§11), error is not typed/retryable-flagged, and pre-stream provider failures are indistinguishable from application bugs (both `500`). A client cannot distinguish "retryable provider hiccup" from "OwnGPT bug".

**Recommended taxonomy (design only — not implemented):**

| Code | Meaning | HTTP (pre-stream) | SSE (mid-stream) |
|---|---|---|---|
| `PROVIDER_UNAVAILABLE` | provider unreachable/auth | 503 (or 502) | `{"type":"error","code":"PROVIDER_UNAVAILABLE","retryable":true}` |
| `MODEL_GENERATION_FAILED` | generation failed (non-tool) | 502 | retryable: true |
| `TOOL_CALL_FAILED` | provider rejected tool emission | 502 | retryable: true |
| `STRUCTURED_OUTPUT_FAILED` | JSON/structured validation failed | 502 | retryable: true (for deterministic stages: degrade instead) |
| `RETRIEVAL_FAILED` | RAG/embedding failure | 503 | retryable: true |
| `EMBEDDING_PROVIDER_FAILED` | embedding provider failure | 503 | retryable: true |
| `APPLICATION_ERROR` | OwnGPT internal bug | 500 | retryable: false |

Where classification belongs (recommendation): **one boundary function in `app/core/llm_provider.py`** (map exception classes → taxonomy code + retryable flag), used by (a) pre-stream outer catch `chat.py:986-988` (map before raising `api_error`) and (b) mid-stream `chat.py:949-957`. Logs keep full text; clients get codes only.

---

## 6. Provider-Specific Coupling

### A. Model-name leaks (active bugs)
1. `chat.py:171` — `_generate_session_title` passes `settings.DEFAULT_MODEL` (= `gpt-4o-mini` under any provider) into `build_llm`. Groq/Ollama reject → per-turn 404, swallowed → title fallback `chat.py:178-180`.
2. `episodic.py:123` — same pattern for episodic recall summarization.
Recommendation: pass `None` or `model_config.DEFAULT_MODEL` (provider-resolved, `model_config.py:39/44/48`) — the same one-liner extraction uses (`extractor.py:62-66`).

### B. OpenAI-shaped assumptions (benign today, fragile tomorrow)
- Tool metadata: `bind_tools` with `@tool` signature-derived schemas (`tools.py:12-56`) — OpenAI-compatible JSON Schema; Groq accepts it (probed), Ollama accepts subset. Gated by model, not capability (§14-1).
- Token usage parsing: `extractor.py:135-158` reads `response_metadata.token_usage` (OpenAI shape), conditionalized for Ollama — fine.
- `max_tokens` mapped per provider (`llm_provider.py:56-57,73,93-94`) — correct pattern.
- Error construction: OpenAI/Groq share `ChatOpenAI`; errors surface as langchain OpenAI-compatible `APIError` regardless of actual provider — the taxonomy mapper (§5) must read `provider` from settings, not from exception class.

### C. Absence of capability routing
- No site checks `supports_tools`/`supports_structured_output` — capability assumptions are implicit in call-site design (graph binds tools; extraction requests JSON by prompt). If a future provider lacks tools, the graph breaks at runtime, mid-stream (§4 mechanism, other models).

---

## 7. Embedding Architecture

Two stacks, intentionally split, **one leak**:

| | KB / RAG | Memory (V2.1) |
|---|---|---|
| Provider | module-level `OllamaEmbeddings` singleton `vector_store.py:17-20` (nomic-embed-text, 768) | `EmbeddingProvider` protocol `embeddings.py:34-96` (Default: OpenAI text-embedding-3-small, `MEMORY_EMBEDDING_DIMENSION` 1536 `config.py:100`) |
| Consumers | `processor.py:161-170` (batch 100, retry 4×), `retriever.py:106` (k=20), `chat.py:49` → `pipeline.py:184-186` (GroundingValidator zero-fallback `[0.0]*1536`) | `deps.py:60-62` (DI), `graph.py:238` (recall), `extractor.py:314,368` (write), `endpoints/memory.py:160,276` |
| Storage | `langchain_pg_embedding` — **untyped `vector`** column (no dimension), collection `own_gpt_docs` | `memory_entities.embedding = Column(Vector(1536))` `models/memory.py:118`; migration `migrations.py:122`; HNSW index :140-142 |

OpenAI-specific / bypasses / risks:
1. **`MemoryEmbeddingIndex` hardcode** — `operations/memory.py:285-291` `OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)` (default embed path for legacy file-store MemoryFact + episodic `operations/episodic.py:196-201`); failure swallowed at `memory.py:302-303`. Not config-gated, not lazy.
2. `vector_store.py` concrete singleton bypasses the `EmbeddingProvider` protocol entirely (KB never had one).
3. RAG vs memory **do not share an abstraction** (protocol exists but covers memory only) — the audit brief's "same abstraction?" answer: no.
4. 429 `credit_balance_exhausted` origin = memory provider default `openai` (recall degrades gracefully per `graph.py:235-251`) and, until this run's fix, KB OpenAI embeddings (which 500'd).
5. Dimensions: KB 768 (untyped column — no migration needed, current corpus 382 chunks); memory frozen at 1536. Changing memory dims would violate the frozen V2.1 schema — **do not**.

Safest production architecture (recommendation, not implemented):
- Make the existing `EmbeddingProvider` protocol the **only** embedding entry point: route KB through it too (`build_embedding_provider()` gains provider config; `vector_store.py` accepts an injected embedder, keeping the module-level singleton only as the KB default), delete the `MemoryEmbeddingIndex` OpenAI hardcode, and record `{provider, model, dimension}` in collection metadata for future migration detection.
- Keep memory = OpenAI 1536 now (schema-frozen). Local embeddings may enter the **KB stack only** (768 in untyped column). For memory, introduce local 1536-dimension embeddings **only via a new collection/table + explicit schema migration** (never in-place `ALTER` of `vector(1536)`), or defer until V2.1 schema owners approve a v2.2 schema artifact. Documented option: wait for a local 1536-dim model (e.g., MTEB-class) and migrate via new artifact per the Architecture Constitution.

---

## 8. Ollama Architecture

LLM `qwen3:8b` (CPU, ~884 s cold load, ~3-8 tok/s) vs embeddings `nomic-embed-text` (768).
- Compose: `OLLAMA_LOAD_TIMEOUT=30m`, `OLLAMA_KEEP_ALIVE=10m` (docker-compose.yml, ollama env block).
- Model allowlist: `model_config.py:35-40` → `[settings.LLM_MODEL]`.
- Tool calling: Ollama supports tool schema subset; llama-family won't emit the Groq-style failure mode, but structured reliability differs (why Gate 3 is provider-agnostic, `extractor.py:231-270`).
- Embeddings: KB uses nomic 768 — dimension mismatch vs memory 1536 is safe because KB column is untyped (verified: current status pgvector=382, whoosh=382).
- Recommendation: at DI level, "encapsulate Ollama as one more adapter" — everything above already flows through `build_llm`/`build_embedding_provider`; no architecture change needed, only the KB-side protocol alignment (§7).

---

## 9. Quality vs Reliability

OwnGPT should treat these as orthogonal:

- **Quality** = per-model answer quality on a task (reasoning, grounding, tone). OpenAI historically better for this app; Groq lower latency; Ollama privacy/cost — these are *model-selection* inputs, never *code-shape* inputs.
- **Reliability** = system behavior under provider/model failure: classified errors, retries, contract-preserving SSE, observability. Today's gaps (no retry, raw text, untyped failures) are reliability gaps, independent of which provider scores best.

The application layer must stay provider-agnostic; **selection policy belongs in configuration/routing** (§13). Measurement (recommended, not built):
- Answer quality: keep deterministic `SourceValidator` (`chat.py:841-856`) + `GroundingValidator` claim checks (`chat.py:860-886`); add offline eval harness on a locked dataset (already available: `app/evaluation/benchmark.py` drives `/chat/evaluate`).
- Tool-call success / structured-output success / failure rate / latency / tokens / cost: per-provider Prometheus counters/histograms with bounded labels (§10) + opt-in live benchmark runs per provider; never user/session IDs in labels (existing cardinality policy, `metrics.py:8-16`).

---

## 10. Observability

Existing (all memory-extraction scoped, `app/core/metrics.py`; chart in §“metric inventory” of prior report not repeated — key facts):
- `llm_calls_total{provider,model}` `metrics.py:169-171`, `llm_errors_total` :172-174, `llm_duration_seconds` :175-178, `llm_tokens_total{kind}` :179-182 — **incremented only by extraction observability** (`observability.py:128,148,171`).
- HTTP: `owngpt_http_requests_total{endpoint}` :332-337.
- No user/session/run labels anywhere (policy :8-16) — compliant.

Gaps vs the brief's target:
- The **chat/graph LLM path emits zero LLM metrics** (429/`failed_generation` invisible to Prometheus; only logs + SSE text).
- No llm_retries_total, llm_tool_call_failures_total, llm_structured_output_failures_total, latency per stage/model.

Recommended additions (bounded; not implemented):
`llm_requests_total{provider,model,stage}`, `llm_failures_total{provider,model,stage,error_code}` (error_code from §5 taxonomy, bounded), `llm_retries_total{provider,model,stage}`, `llm_tool_call_failures_total{provider,model}`, `llm_structured_output_failures_total{provider,model,stage}`, `llm_duration_seconds{provider,model,stage}` histogram. Stage ∈ small enum {agent,title,intent,rewrite,validation,extraction,episodic}. Wire in `metrics.py` (namespace `owngpt_llm`) and the new failure mapper (§5) — a provider comparison dashboard then falls out of existing Grafana provisioning (`ops/grafana/`).

---

## 11. Security

Positive:
- `build_llm` errors name env vars, never values (`llm_provider.py:44-48,80-84`); sanitizer scrubs key-shaped strings from logs (`logging_config.py:68-90`); startup logs avoid env values; `.env*` gitignored; `/health` minimal (`main.py:152-154`).

Findings (file:line → risk):
1. `chat.py:957` — **raw provider exception text to client** (prompts are not leaked; but provider internals/URLs and possibly error bodies are).
2. `system.py:24-92` — status endpoint exposes `LLM_PROVIDER`, `OLLAMA_BASE_URL`, full Ollama model list, and raw `str(e)` DB/provider errors (:38,:51,:67,:88-90).
3. `documents.py:42,93,140,178` + `index.py:84,95` — `HTTPException(detail=str(e))` raw DB exception text.
4. `main.py:110-116` — CORS `allow_origins=["*"]` + `allow_credentials=True` (invalid per fetch spec; backend effectively trusts any origin).
5. **Unauthenticated**: `documents.py`, `index.py`, `ingestion.py`, `system.py` have no `Depends(get_current_user)` — document content/download, corpus manifest, ingestion triggers, and infra status are public in the network.
6. `main.py:135-140` — validation errors echo submitted body back (self-echo only).
7. Groq/OpenAI keys: read only via pydantic settings; the only non-factory read is `operations/memory.py:290` (hardcoded `api_key=`).

Recommendation: taxonomy-derived error codes to clients (keep full text server-side), sanitize/aggregate status+document endpoints, CORS tighten to explicit origins, and auth on the 4 endpoint groups. No keys/prompts/tool schemas currently reach clients; errors are the main leak class.

---

## 12. Test Strategy

Current: 348 pass / 2 pre-existing failures (quota pair); groq provider tests in `tests/core/test_llm_provider.py` (selection/base_url/model/max_tokens/missing-key). Principles: hermetic default (unit with mocked provider), integration against local services, live provider opt-in.

Recommended matrix (hermetic unless noted; not implemented):

| Feature | UNIT (mock provider) | INTEGRATION (docker Ollama local) | LIVE (opt-in env-gated) |
|---|---|---|---|
| Basic chat | graph happy path w/ FakeChat | chat vs Ollama | `-m live:groq`, `-m live:openai` |
| Streaming contract | SSE: pre-token failure → error event+[DONE]; post-token failure → content+error+[DONE]; no ambiguous stream | same vs real server | same |
| Structured output | extraction Gate 2 parse/validation; intent/rewrite/validation JSON degrade paths | Gate 3 batch-atomic | extraction JSON on each provider |
| Tool calling | bind_tools schema snapshot; tool-call -> ToolMessage roundtrip; Groq `tool_use_failed` simulation → retry/classification | Ollama tool call | llama-3.3 tool-call reliability probe |
| Intent / Rewrite / Validation | degrade-on-error paths (already exist) | re-run vs Ollama | periodic |
| Memory extraction | EXTRACTION_MODEL resolution per provider (exists) | vs Ollama | live |
| RAG | embedding provider injection; dimension bookkeeping test (768 vs 1536) | corpus → embed → retrieve | embedding parity |
| Failure handling | taxonomy mapper unit tests (each §5 code); retry-once tests; never-raw-text assertion (SSE + error mapper) | timeout/429 simulation (local proxy) | provider outage drill |

Do not gate CI on paid APIs: live suites run manually on schedule; hermetic tests mock the provider boundary exactly where `build_llm`/`embedding provider` are constructed.

---

## 13. Recommended Architecture

```
Application (chat / memory / extraction / agents)
        │  capability need (tools? structured? streaming? quality tier?)
        ▼
Capability-aware LLM interface  ←  extends build_llm (llm_provider.py)
   • capability registry (per provider × model): tools, structured_output,
     streaming, embeddings, context_window, quality tier, cost tier
   • build_llm(..., required_capabilities=[...]) — configured model must satisfy them
   • taxonomy mapper: exceptions → {code, retryable} (§5)
   • retry policy: bounded retries on retryable provider errors, same model
        ▼
Provider adapter (openai / groq / ollama / future)
        ▼
OpenAI  │  Groq  │  Ollama

separately:
RAG / Memory ─ Should flow through ONE EmbeddingProvider protocol (deps.py / embeddings.py)
        ▼           (KB currently bypasses it — §7-2)
Embedding interface → Embedding adapter (openai / ollama-local)
        ▼
vector stores: langchain_pg_embedding (untyped) | memory_entities vector(1536) [frozen]
```
Routing (future, V7, do not build now):
```
OwnGPT Request → Capability Need → Router { capability, quality, latency, cost, availability, context_window }
                                   → Provider+Model ≤ budget&capabilities → build_llm
```

---

## 14. Recommended Remediation Order

1. **Error contract + taxonomy** (smallest, highest value): mapper in `llm_provider.py`, use in pre-stream `chat.py:986-988` and mid-stream `chat.py:949-957`; SSE error events carry `code`+`retryable`; raw text to logs only. Fixes the user-visible symptom class (§4) and the §5 contract gap.
2. **One retry** on retryable provider errors (e.g. `tool_use_failed`, 429/5xx, timeouts) at the call boundary — a provider-layer wrapper, not per-stage logic; keeps the graph/architecture identical. Directly mitigates Groq intermittency.
3. **Model-name leak cleanup**: `chat.py:171` and `episodic.py:123` → provider-resolved default (`model_config.DEFAULT_MODEL` / `build_llm(None)`). One-line each (pattern proven at `extractor.py:62-66`).
4. **Embedding unification**: single `EmbeddingProvider` entry for KB+memory; kill `operations/memory.py:290` hardcode; collection metadata `{provider,model,dimension}`; KB stays 768/untyped, memory stays 1536/frozen. No dimension change, no migration, no reindex.
5. **Observability**: `owngpt_llm_*` metrics (per §10) wired at the same call boundary as (1)+(2), so provider comparison is measurable.
Then, later: capability registry + gated `bind_tools` (turns (2) from heuristics into policy), auth/endpoint hardening (§11.2-5), live-provider test harness (§12).

---

## 15. Roadmap Impact

- Provider abstraction belongs in **V7 Platform (multi-model routing, observability, evaluation)** — §13/§14-6. Do not build the router now; the capability registry + taxonomy in this audit are its prerequisites.
- **V4 Agent** must adopt capability-gated tool binding when the registry lands; until then the recommended retry+taxonomy keeps llama-3.3/Groq tool turns reliable enough.
- **V2/V3 (memory, knowledge)** absorb §7 and §8 fixes via the existing `EmbeddingProvider` protocol — no schema or roadmap change; the 1536 V2.1 schema stays frozen.
- No lifecycle/lineage changes: taxonomy and metrics attach to existing observation points; retry is inside the Execute/Operate boundary, never approval-relevant.
- The architecture constitution's invariants (no fallback between providers at construction; artifacts immutable; capabilities registered) remain intact — each remediation attaches to existing packages and config surfaces.

---

## 16. GREEN / YELLOW / RED Assessment

| Axis | Grade | Evidence |
|---|---|---|
| Provider boundary (build_llm) | 🟢 GREEN | clean factory, no fallback, clear errors, per-provider param mapping (`llm_provider.py:10-19,41-120`) |
| Pipeline stages (intent/rewrite/validation/confidence/extraction) | 🟢 GREEN | provider-agnostic (config keys `""`), safe degradation, extraction model provider-aware, Gate-3 deterministic |
| Agent graph tool calling | 🟡 YELLOW | schema sound (probed), but unconditional `bind_tools` + no retry + raw error surfacing → user-visible Groq failures |
| HTTP/SSE error contract | 🔴 RED | raw provider text to clients; provider failure indistinguishable from application error; pre-stream 500 |
| Embedding architecture | 🟡 YELLOW | protocol exists for memory; KB bypasses it; one OpenAI hardcode; safe dims (768 untyped / 1536 frozen) |
| Observability | 🟡 YELLOW | extraction-only LLM metrics; chat LLM path invisible |
| Security | 🟡 YELLOW | keys/logs safe; error-text leakage, `*` CORS, unauthenticated info endpoints |
| Retrieval (post-fix) | 🟢 GREEN | 200 grounded answers, verified retrieval path (Ollama embeddings), consistent 382/382 corpus |
| Test coverage per provider | 🟡 YELLOW | hermetic unit coverage good; no live/integration provider suites, no error-contract tests |

**Overall: YELLOW** — the abstraction is genuinely provider-neutral at its core; the production gaps are concentrated in error handling, retry, capability policy, and observability, all addressable without architectural change.

---

## Appendix A — Reproduction evidence (this audit)

1. `POST /api/v1/chat/stream` `{"message":"remember that my favorite color is electric blue","model":"llama-3.3-70b-versatile"}` → SSE: `data: {"type": "error", "message": "Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details."}` + `data: [DONE]`; HTTP 200; server log `error_class=APIError`, `req_id=f11948d4`, `duration_ms=7203.7`.
2. Same request ×5 immediately after: all 200 with streamed answers (intermittency confirmed).
3. Direct Groq API (same schema + message, `llama-3.3-70b-versatile`, temp 0.4) ×8: all `200` with valid `tool_calls` (schema acceptance confirmed; e.g. `remember_user_fact` args `{"fact":"favorite color is electric blue"}`).
4. Independent ecosystem evidence (LangChain SO #79896070, AutoGen #3217, smolagents #1119, picoclaw #748, pydantic-ai #1233): same Groq error string, same model class (llama-3.3-70b-versatile / llama-3.x family), model emits non-native `<function=…>` or malformed tool-call JSON intermittently; "not reproducible" resolution in one track — model-side nondeterminism.
5. Grounded KB question (post-fix): `200`, `stage=retrieval retrieved=20 top_score=0.6216 latency_ms=8333.4`, confidence 1.0, 29 KB SSE — the earlier 500 class is gone.