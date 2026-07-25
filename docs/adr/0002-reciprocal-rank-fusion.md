# ADR-0002: Reciprocal Rank Fusion

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

The pipeline retrieves chunks from two independent systems: vector similarity search (pgvector) and BM25 keyword search (Whoosh). A fusion strategy was needed to combine these result sets into a single ranked list. The strategy must handle differently scaled scores (cosine similarity vs BM25 scores) and be simple to tune.

## Decision

Use Reciprocal Rank Fusion (RRF) with a constant `k=60`. Each document's RRF score is `1 / (k + rank_in_vector_results) + 1 / (k + rank_in_bm25_results)`, where `rank` starts at 1. Documents appearing in only one result set receive `0` for the missing rank.

## Consequences

- **Positive**: Score-scale independent — RRF works on ranks, not raw scores, so vector and BM25 scores don't need normalization
- **Positive**: No tuning required beyond picking `k` (60 is a widely-used default)
- **Positive**: Robust across heterogeneous retrievers — works even if one retriever's score distribution changes
- **Negative**: Rank-based fusion loses information about score magnitude — a near-perfect vector match and a marginal one are treated similarly if ranked close

## Alternatives Considered

- **Weighted averaging**: Requires score normalization and per-dataset weight tuning. Rejected for complexity.
- **Borda count**: Similar complexity to RRF but less widely studied. Rejected for lack of proven defaults.
- **Learning-to-rank**: Requires labeled training data and ongoing maintenance. Unjustified for current scale.
