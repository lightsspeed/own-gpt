# ADR-0006: True Corpus Coverage

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

Retrieval coverage was initially computed only against the set of chunks that were actually retrieved during a benchmark run. This showed which chunks were used but not which chunks were *never* retrieved — making it impossible to distinguish "well-covered" from "lucky coverage" (where the benchmark only asked questions about a narrow subset of the corpus). A true coverage metric needed access to the full corpus chunk manifest.

## Decision

Add `GET /api/v1/index/corpus` that returns every chunk in the pgvector index with its `chunk_id`, `source`, `page`, and `chapter`. The benchmark calls this endpoint once per run and compares the universe of retrieved chunk IDs against the full manifest to compute per-document and overall true coverage percentages.

Chunks uploaded before this feature do not have `chunk_id` in their metadata. Use `COALESCE(cmetadata->>'chunk_id', id::text)` to generate stable identifiers for legacy chunks.

## Consequences

- **Positive**: Coverage now measures against the actual corpus, not just the retrieved subset
- **Positive**: Identifies blind spots — documents whose chunks are never retrieved across the benchmark
- **Positive**: Single endpoint serves both coverage analytics and chunk inventory (1945 chunks across 5 sources)
- **Negative**: Requires the backend to be running during benchmark execution (already required for evaluation)
- **Negative**: Legacy chunks without `chunk_id` use the pgvector row ID, which is not stable across re-indexing

## Alternatives Considered

- **Track coverage during indexing**: Tag each chunk when it's first retrieved. Would miss chunks that are never retrieved. Rejected for the exact problem we needed to solve.
- **Static manifest file**: Maintain a JSON manifest of all chunks alongside the dataset. Would drift from the actual index. Rejected for reliability.
- **Skip coverage**: Simpler but provides no signal about corpus-level blind spots. Rejected as insufficient.
