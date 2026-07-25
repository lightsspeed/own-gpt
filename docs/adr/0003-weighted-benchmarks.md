# ADR-0003: Weighted Benchmarks

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

Not all benchmark questions are equally important. A question about memory safety may be more critical than one about formatting conventions, but a simple pass/fail count treats them identically. The platform needed a way to reflect question priority in benchmark scores without complicating the scoring model.

## Decision

Assign each question an integer weight (1–4) in its JSONL entry. The weighted pass rate replaces the simple pass rate in regression gate evaluation. Weights are static per dataset version — they are part of the dataset definition, not configurable at runtime.

The weighted pass rate is computed as `sum(passed_weight) / sum(total_weight)` where a question is counted at its full weight if it passes and zero if it fails.

## Consequences

- **Positive**: Reflects real-world priority — high-weight questions dominate the score
- **Positive**: Minimal complexity — weight is a single integer field, scoring is a simple ratio
- **Positive**: Dataset authors can encode domain expertise (which topics matter most)
- **Negative**: Weights are subjective and can be gamed — requires dataset review discipline
- **Negative**: Comparison across dataset versions with different weights is not meaningful

## Alternatives Considered

- **Multi-metric aggregation**: Combine pass/fail with latency, faithfulness, etc. into a composite score. Rejected as opaque — hard to explain why a benchmark got score X.
- **Tiered pass/fail**: Questions in tier 1 must all pass, tier 2 can have some failures. Rejected as too rigid — doesn't allow partial credit.
- **Unweighted**: Simpler but equates a trivial formatting question with a critical security question. Rejected for not reflecting real priorities.
