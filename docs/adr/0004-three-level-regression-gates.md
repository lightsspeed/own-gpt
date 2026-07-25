# ADR-0004: Three-Level Regression Gates

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

Regression gates must allow for metric noise. Benchmarks have inherent variance — LLM outputs, network latency, and RAGAS scores fluctuate between runs. A binary pass/fail gate would produce false positives (blocking merges on spurious drops) and false negatives (missing real regressions within the noise floor).

## Decision

Implement three gate levels — PASS, WARNING, and FAIL — with a configurable `warning_zone` parameter (default 0.02, i.e. 2%):

- **FAIL**: Metric drops below the configured threshold.
- **WARNING**: Metric is above the threshold but within the warning zone below it (threshold - warning_zone < metric < threshold).
- **PASS**: Metric is at or above threshold.

Warnings are informational only — they do not block CI merges. Only FAIL blocks merges.

## Consequences

- **Positive**: Detects drift near thresholds without blocking merges on noise
- **Positive**: Teams can tune sensitivity per-metric via warning_zone in `pipeline_config.yaml`
- **Positive**: Warning provides an audit trail — teams can investigate before the metric actually fails
- **Negative**: More complex than binary — three outcomes require three handling paths in CI and CLI
- **Negative**: warning_zone introduces a tuning parameter that must be set per-metric

## Alternatives Considered

- **Binary pass/fail**: Simple but produces too many false positives. Rejected.
- **Statistical significance test**: Compare distributions rather than point values. More principled but requires multiple runs per benchmark session (expensive).
- **Trend-based detection**: Compare against moving average. Good for long-running CI but requires historical data that doesn't exist for a new dataset.
