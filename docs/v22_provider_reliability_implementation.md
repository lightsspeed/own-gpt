# V2.2 Provider Reliability Implementation (Audit Items 1–3)

Date: 2026-08-16
Predecessor: `docs/v22_provider_compatibility_audit.md` (audit — unchanged).
Scope: audit remediation items 1–3 ONLY. No router/V7/capability-registry/embedding/metrics-architecture work.

---

## 1. Problem

- Groq `llama-3.3-70b-versatile` intermittently emits a tool call that Groq's strict
  parser rejects → HTTP 400 `tool_use_failed` ("failed_generation") → the raw provider
  error text was returned to the frontend verbatim (SSE `error` event), with no retry.
- Provider failures were indistinguishable from application failures (no error taxonomy).
- `settings.DEFAULT_MODEL` (= `gpt-4o-mini`) was passed raw to non-OpenAI providers in
  session-title generation and episodic consolidation → guaranteed provider 404s.

## 2. Root Cause

Traced + reproduced in the audit and re-verified during implementation:
`chat.py` stream → `graph.py:210` `bind_tools(...).invoke()` → Groq 400
`tool_use_failed` → langchain `APIError` → `chat.py:949` raw `str(exc)` in SSE error event.
Model-side nondeterminism (verified: same schema+message direct-probe 8/8 200);
OwnGPT had no retry and no error classification.

## 3. Error Taxonomy

Added at the provider boundary (`app/core/llm_provider.py`):

| Code | Retryable | Client message |
|---|---|---|
| `PROVIDER_UNAVAILABLE` | yes (auth/config sub-cases: no) | "The AI provider is temporarily unavailable. Please try again." |
| `MODEL_GENERATION_FAILED` | no | "The model could not generate a response. Please try again." |
| `TOOL_CALL_FAILED` | yes | "The model could not complete the requested tool operation. Please try again." |
| `STRUCTURED_OUTPUT_FAILED` | no | "The model returned an invalid structured response. Please try again." |
| `RETRIEVAL_FAILED` | no | "Knowledge retrieval failed. Please try again." |
| `EMBEDDING_PROVIDER_FAILED` | no | "The embedding service is unavailable. Please try again." |
| `APPLICATION_ERROR` | no | "An internal error occurred." |

`classify_provider_error(exc, provider=None) -> ProviderErrorInfo{code, retryable, safe_message}`:
- OpenAI-compatible (OpenAI + Groq via ChatOpenAI): Authentication/Permission → PROVIDER_UNAVAILABLE (not retryable);
  RateLimit/APIConnection/APITimeout/InternalServer → PROVIDER_UNAVAILABLE (retryable);
  BadRequest with `tool_use_failed`/`failed_generation` → TOOL_CALL_FAILED (retryable);
  BadRequest with `response_format`/`json` → STRUCTURED_OUTPUT_FAILED; other 400 → MODEL_GENERATION_FAILED;
  NotFound → MODEL_GENERATION_FAILED.
- Ollama: `ollama.ResponseError` status-mapped (400/422 tool-text → TOOL_CALL_FAILED; 429/5xx → retryable
  unavailable; 401/403 → unavailable; 404 → generation failed); transport errors via httpx/requests.
- Unknown → APPLICATION_ERROR. Raw provider text is NEVER placed in `safe_message` (tests assert this);
  it remains in structured server logs (existing sanitizer/redaction applies).

## 4. Retry Policy

`invoke_model_with_retry(model, payload, provider=None)` in `llm_provider.py`:
- **At most one retry — maximum 2 attempts total** (asserted by tests).
- Retry ONLY errors classified retryable: `PROVIDER_UNAVAILABLE` (transient) + `TOOL_CALL_FAILED`.
- No retry for auth/config, 4xx-generic, structured-output, retrieval, embedding, application errors.
- Retry reuses the SAME model instance — never a fallback to another provider (invariant preserved).
- Wired into the agent graph's only generation step: `graph.py` `call_model` now calls
  `invoke_model_with_retry(model_with_tools, payload, provider=settings.LLM_PROVIDER)`.
  (All graph invocations — stream, non-stream, evaluate — pass through `call_model`.)

## 5. Why Retry Is Safe (Tool Execution)

- Tool side effects happen ONLY in the `action` node (`graph.py` `action_node` →
  `tool_gate.request_tool_execution`), which runs only after a **successful** AIMessage with
  `tool_calls` is produced.
- `invoke_model_with_retry` retries only when `model.invoke` RAISED — i.e., the model produced
  no tool call, so no tool side effect has occurred.
- Successful generations (including ones carrying tool_calls) are never retried
  (test: `test_success_is_never_retried`). Duplicate tool execution is impossible by construction.
- Extraction Gate 2's own single retry (unchanged, P1 semantics preserved) does not use this wrapper.

## 6. Provider Default Resolution

Fixed production call sites:
- `app/api/endpoints/chat.py` `_generate_session_title`: `build_llm(model=None, temperature=0)`
  (was `settings.DEFAULT_MODEL`).
- `app/learning/operations/episodic.py` `default_summarize`: `build_llm(model=None, temperature=0.0)`
  (removed now-unused `settings` import).
- `app/learning/telemetry/builder.py` `_default_model()`: now `model_config.DEFAULT_MODEL`
  (provider-resolved label, was raw `settings.DEFAULT_MODEL`).

Already correct (verified, unchanged): `llm_provider.py` openai default (provider-scoped),
`graph.py:204` + `chat_persistence.py:28` (import `model_config.DEFAULT_MODEL` — provider-resolved),
`extractor.py:62-66` (the pattern's source). Out of scope by audit decision: `evaluation/reproducibility.py`
(literal eval-artifact data), `reranker.py` (reranker model name), `metrics.py`/`config.py` (label/legacy domains).
Explicit user-selected models still flow through `resolve_model` allowlist → request state, unchanged.

## 7. Files Changed

- `app/core/llm_provider.py` — taxonomy constants, `ProviderErrorInfo`, `classify_provider_error`,
  `invoke_model_with_retry`.
- `app/agent/graph.py` — `call_model` uses `invoke_model_with_retry`.
- `app/api/endpoints/chat.py` — SSE error event now `{"type":"error","code":…,"retryable":…,"message":<safe>}`
  (raw text logged + stored server-side only); pre-stream outer catch classifies and maps retryable
  provider unavailability to HTTP 503 `provider_unavailable`; non-stream catch classifies in logs;
  title default resolved by provider.
- `app/learning/operations/episodic.py` — provider default.
- `app/learning/telemetry/builder.py` — provider-resolved label default.
- `tests/core/test_llm_provider.py` — TestErrorTaxonomy (12), TestBoundedRetry (7),
  TestProviderBoundaryCompatibility (3).
- `tests/chat/test_endpoints.py` — SSE contract tests updated to classified codes; added
  Groq `tool_use_failed` classified-code test.

## 8. Tests

- `tests/core/test_llm_provider.py`: A retry→success, B exhaustion→classified raise, C no retry
  (auth/generic), D exactly-one-retry (2 attempts), E success never retried + same-instance
  (no provider switch), taxonomy mapping incl. exact Groq error body, safe-message hijack assertions.
- `tests/chat/test_endpoints.py`: F valid SSE — error event has code/retryable/safe message,
  raw text absent, `[DONE]` last; partial-output persistence unchanged.
- Full suite: **377 passed / 0 failed** (baseline 348 passed / 2 failed; the named quota pair in
  `tests/pipeline/test_pipeline.py` now passes — they were not modified, hidden, or skipped;
  they no longer hit the exhausted-quota path).

## 9. Live Verification

Not yet re-verified live in this closure pass (the local stack still runs the pre-change image).
See §12. The retrieval + Groq streaming paths were verified during the audit (200 / grounded answers).

## 10. Known Limitations

- Retry covers the agent generation step only; title/episodic/pipeline stages degrade (fail-open)
  as before — by design.
- `MODEL_GENERATION_FAILED` is never retried (conservative: deterministic 4xx).
- The taxonomy mapper is heuristic on error bodies; provider error surfaces can change shape
  (safe-message layer protects clients regardless).

## 11. Deferred Work

Router / capability registry / V7 routing; embedding re-platforming; new provider fallbacks;
new metrics (none added — existing P2.2 infra used); link: audit §13–14.

## 12. Final Verdict

IMPLEMENTED (1–3 only) — TESTED (377/0) — NOT COMMITTED — P2.3 / V7 NOT STARTED.