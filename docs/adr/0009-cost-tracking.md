# ADR-0009: Cost Tracking via Tiktoken + OpenAI Pricing

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

The platform needed visibility into the operational cost of each benchmark run. Without cost tracking, there is no way to detect cost regressions (e.g., a pipeline change that doubles token usage), compare cost across retrieval strategies, or budget for CI usage. The challenge is that OpenAI API responses include token usage in their response, but the LangGraph pipeline abstracts away raw API calls.

## Decision

Track cost at the endpoint level rather than intercepting API responses. The evaluate endpoint counts tokens using `tiktoken` with the `gpt-4o-mini` encoding (`chat.py:48-51`), which matches the model's actual tokenizer. Two token types are counted:

- **prompt_tokens**: `tiktoken.encode(question)` on the user query
- **completion_tokens**: `tiktoken.encode(response)` on the generated answer

Embedding tokens are estimated in `benchmark.py:65-66` as `sum(len(t.split()) * 1.3 for t in contexts)`.

Cost is estimated using OpenAI's published pricing for `gpt-4o-mini` ($0.15/M input, $0.60/M output) and `text-embedding-3-small` ($0.02/M), stored as constants in `benchmark.py`.

## Consequences

- **Positive**: No API dependency — cost works even if OpenAI's response format changes or usage metadata is missing
- **Positive**: Tiktoken counts match the model's actual tokenization (not a rough word-count approximation)
- **Positive**: Cost is computed at benchmark time and aggregated in the summary, available to all downstream consumers
- **Negative**: Token counts are estimates — they don't include system prompts, conversation history, or tool call tokens
- **Negative**: Pricing is hardcoded — if OpenAI changes prices, the constants must be updated manually

## Alternatives Considered

- **Intercept OpenAI API responses**: Parse `usage` field from API response for exact token counts. More accurate but requires hooking into LangGraph's internal API calls. Unreliable across library versions.
- **Use LangSmith token counting**: Available but adds a third-party dependency and requires LangSmith to be configured. Rejected for reproducibility.
- **Skip cost tracking**: Simpler but provides no operational visibility. Rejected as a gap for a production benchmarking platform.
