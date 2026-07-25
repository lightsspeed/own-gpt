# ADR-0005: Evaluation Engine Orchestrator

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

The benchmark pipeline grew from a single script to multiple stages: validation, benchmark execution, report generation, analytics, gate checking, trend updates, and README generation. These stages were initially mixed together in the CLI and benchmark modules, creating hidden dependencies (e.g., reports must run before analytics writes the report path). Without a clear orchestration layer, it became difficult to add new stages, reorder them, or share the pipeline across CLI, API, and scheduled jobs.

## Decision

Introduce `EvaluationEngine` as the central orchestrator. The engine owns a fixed pipeline of 9 stages, each implemented as a private method:

1. `_validate` — dataset exists, backend reachable
2. `_run_benchmark` — execute parallel HTTP benchmark
3. `_generate_reports` — HTML and comparison reports
4. `_compute_analytics` — method distribution, coverage, effectiveness
5. `_write_summary` — enriched summary.json with analytics
6. `_generate_comparison` — vs baseline if available
7. `_check_gates` — regression threshold checks
8. `_update_trends` — trend dashboard update
9. `_write_bundle_readme` — bundle-level README

The CLI becomes a thin presentation layer that calls `engine.run()` and formats the result.

## Consequences

- **Positive**: Single execution path — CLI, future REST API, and scheduled jobs share the same pipeline
- **Positive**: Explicit stage ordering eliminates hidden dependencies
- **Positive**: Each stage can fail independently without crashing the pipeline (errors collected in `BenchmarkContext`)
- **Negative**: Fixed pipeline order is inflexible — adding a stage between existing stages requires modifying the engine
- **Negative**: Another abstraction layer — developers must understand the engine, not just the CLI

## Alternatives Considered

- **Keep logic in CLI**: Simplest but makes it impossible to reuse the pipeline programmatically. Rejected.
- **Async event-driven pipeline**: Each stage publishes events that downstream stages subscribe to. More flexible but significantly more complex. Unjustified for current scale.
- **Make stages independent scripts**: Worst of both worlds — no orchestration, no shared context. Rejected.
