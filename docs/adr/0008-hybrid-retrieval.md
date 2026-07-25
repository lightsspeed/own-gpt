# ADR-0008: Hybrid Retrieval Architecture

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

The retrieval pipeline needed to serve diverse query types. Some queries are semantic ("explain the concept of attention") and benefit from vector search. Others are lexical ("what does the `max_connections` parameter do?") and benefit from keyword matching. Relying on a single retrieval method would miss relevant results for a significant fraction of queries.

## Decision

Implement a hybrid retrieval pipeline with three runtime-selectable modes:

- **vector** — pgvector cosine similarity search only
- **bm25** — Whoosh BM25 search only
- **hybrid** (default) — both searches run in parallel, results fused via RRF

The pipeline also supports optional FlashRank reranking on the fused results. The retriever mode is configurable per-request via the `retriever` parameter on `/chat/evaluate`.

## Consequences

- **Positive**: Semantic and lexical queries both served well — no "one size fits all" compromise
- **Positive**: Runtime mode switching enables comparative benchmarking — measure which mode performs best per dataset
- **Positive**: Parallel execution of vector and BM25 means hybrid latency is roughly `max(vector_time, bm25_time)`, not the sum
- **Negative**: Two indices to maintain (pgvector + Whoosh) — twice the infrastructure surface
- **Negative**: BM25 index must be rebuilt when documents change (or re-ingested)

## Alternatives Considered

- **Pure vector search**: Simplest infrastructure. Rejected — poor lexical matching for code, parameters, and proper nouns.
- **Pure BM25**: Simple and fast. Rejected — poor semantic matching for conceptual questions.
- **Ensemble with learned weighting**: Train a model to choose vector/BM25 per query. More accurate but requires labeled training data and model maintenance. Unjustified for current scale.
