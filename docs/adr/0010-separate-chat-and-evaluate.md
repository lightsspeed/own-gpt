# ADR-0010: Separate `/chat` and `/chat/evaluate` Endpoints

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

The initial design shared a single `/chat` endpoint for both user-facing chat and programmatic evaluation. This created tension: evaluation requires verbose structured output (provenance, trace, latencies, confidence) that degrades the chat UX, while chat requires low latency and minimal payload overhead that conflicts with evaluation's instrumentation needs.

## Decision

Split into two endpoints:

- **`POST /api/v1/chat`**: User-facing chat. Returns only the answer string. Minimal instrumentation. Optimized for latency.
- **`POST /api/v1/chat/evaluate`**: Programmatic evaluation. Returns full `EvaluationResult` with answer, retrieved/reranked chunks with provenance, pipeline trace, per-stage latencies, and confidence scores.

Both endpoints run the same retrieval pipeline and LLM call — they differ only in how much context they return.

## Consequences

- **Positive**: Each endpoint has a clear SLA — chat prioritizes speed, evaluate prioritizes completeness
- **Positive**: Evaluate endpoint serves as the single source of truth for benchmarks and CI without affecting chat UX
- **Positive**: Easy to add future evaluation-only features (e.g., deeper instrumentation, multiple LLM comparisons) without touching chat
- **Negative**: Two endpoints to maintain and test — changes to the pipeline must be validated against both

## Alternatives Considered

- **Query parameter on `/chat`**: `?mode=evaluate` to switch output format. Simpler but couples chat's evolution to evaluation's requirements. Rejected for separation of concerns.
- **Single endpoint, always verbose**: Simplest implementation. Rejected because the verbose payload (provenance, trace) adds latency overhead and exposes internal structure to chat clients.
- **Separate service**: Full microservice for evaluation. Unjustified — the two endpoints share the same pipeline and data store.
