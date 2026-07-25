# ADR-0007: Reproducibility Metadata at Benchmark Time

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

Benchmark results are meaningless if they cannot be reproduced. The platform needed a way to capture the exact environment of each run so that future comparisons account for changes in code, dependencies, datasets, and models. The challenge is that some metadata is known at config-time and some is only known at runtime — using config-declared values risks inaccuracy if configs change between runs.

## Decision

Capture reproducibility metadata at benchmark execution time using `collect_metadata()`. This function reads:

- **Git state**: commit hash, branch name, dirty flag
- **Environment**: Python version, benchmark version
- **Dependencies**: dataset hash (SHA-256 of JSONL), requirements lock hash
- **Models**: embedding model name and dimensions, reranker model, LLM name
- **Config**: chunk size, retriever mode, timestamp

The metadata block is written to three locations: `summary.json`, `metadata.json`, and CI output JSON.

## Consequences

- **Positive**: Metadata reflects the actual run state — even if configs changed between runs
- **Positive**: Dataset hashing catches unannounced dataset modifications
- **Positive**: Three write locations ensure metadata is accessible regardless of how results are consumed
- **Negative**: Git metadata is meaningless in CI (shallow clone, detached HEAD) — those fields are context-dependent
- **Negative**: Runtime capture is slower than config-declared values (negligible — milliseconds)

## Alternatives Considered

- **Config-declared metadata**: Read values from pipeline_config.yaml at the start of a run. Rejected — would miss dirty repos and uncommitted changes.
- **Post-hoc metadata**: Capture after the run completes. Rejected — timestamp and git state could change.
- **Minimal metadata**: Just capture commit hash and version. Rejected — insufficient for diagnosing cross-environment differences.
