# Architecture Decision Records

This directory captures key architectural decisions made during the platform's evolution. Each ADR is a short, structured record of a significant decision, its context, alternatives considered, and consequences.

## Index

| ID | Title | Status |
|---|---|---|
| 0001 | `/chat/evaluate` as Single Source of Truth | Accepted |
| 0002 | Reciprocal Rank Fusion | Accepted |
| 0003 | Weighted Benchmarks | Accepted |
| 0004 | Three-Level Regression Gates | Accepted |
| 0005 | Evaluation Engine Orchestrator | Accepted |
| 0006 | True Corpus Coverage | Accepted |
| 0007 | Reproducibility Metadata at Benchmark Time | Accepted |
| 0008 | Hybrid Retrieval Architecture | Accepted |
| 0009 | Cost Tracking via Tiktoken + OpenAI Pricing | Accepted |
| 0010 | Separate `/chat` and `/chat/evaluate` Endpoints | Accepted |
| 0011 | Lockfile-based Dependency Pinning | Accepted |

## ADR Lifecycle

- **Proposed** — under discussion
- **Accepted** — agreed and implemented
- **Superseded** — replaced by a later ADR
- **Deprecated** — no longer applicable

## Template

```
# ADR-NNNN: Title

**Status:** [Proposed | Accepted | Superseded | Deprecated]

**Date:** YYYY-MM-DD

**Decision Makers:**
- Name

**Supersedes:**
- None

**Superseded By:**
- None

## Context

Why this decision was needed.

## Decision

What was decided.

## Consequences

What this means for the system (positive and negative).

## Alternatives Considered

Other approaches that were evaluated and why they were rejected.
```
