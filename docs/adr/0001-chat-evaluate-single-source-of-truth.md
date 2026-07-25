# ADR-0001: `/chat/evaluate` as Single Source of Truth

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

The platform needed a single, deterministic evaluation endpoint that all consumers — benchmarks, CI/CD, debugging, and ad-hoc analysis — could rely on. Without this, each consumer would implement its own evaluation logic, leading to drift between what CI measures and what local benchmarking measures.

## Decision

Route all evaluation through `POST /api/v1/chat/evaluate`. This endpoint returns a structured `EvaluationResult` containing the answer, retrieved/reranked chunks with full provenance, pipeline trace, latencies, confidence, and context. Benchmarks call this endpoint via HTTP; CI calls it via the same benchmark path.

## Consequences

- **Positive**: Zero drift — all evaluations use the same LLM, retrieval pipeline, and scoring logic
- **Positive**: Single optimization target — improving the endpoint improves every downstream consumer
- **Positive**: Easy to test — a single endpoint covers the entire pipeline
- **Negative**: The endpoint is a coupling point — changes to it affect all consumers

## Alternatives Considered

- **Embedded evaluation in benchmark CLI**: Would mean the benchmark duplicates pipeline logic. Rejected for drift risk.
- **Shared library function**: Better, but still requires version synchronization. HTTP boundary forces explicit contracts.
