# Benchmark Guide

## Running a Benchmark

### Basic Usage

```bash
rag benchmark thinking_fast_and_slow
```

This runs all 75 questions against `http://localhost:8000` and prints a summary table.

### Options

| Flag | Default | Description |
|---|---|---|
| `--category, -c` | (all) | Filter to a specific category (e.g. `system_1_2`) |
| `--retriever` | default | Retriever mode: `hybrid`, `vector`, or `bm25` |
| `--workers, -w` | 3 | Max parallel requests to backend |
| `--base-url, -u` | http://localhost:8000 | Backend API URL |
| `--report, -r` | reports | Report output directory |
| `--compare` | — | Compare against a baseline run (`latest` or specific run name) |
| `--ci` | — | CI mode: output JSON to stdout, exit 1 on gate failure |
| `--pr-summary` | — | Include PR summary markdown in CI output |
| `--top-failures, -f` | 0 | Show top N failure reasons |
| `--export-csv` | — | Export results as CSV to stdout |

### Examples

```bash
# Full benchmark with CI output
rag benchmark thinking_fast_and_slow --ci

# Compare against latest run
rag benchmark thinking_fast_and_slow --compare latest

# CI mode with PR summary
rag benchmark thinking_fast_and_slow --ci --pr-summary --compare latest

# Single retriever mode for comparison
rag benchmark thinking_fast_and_slow --retriever bm25

# Filtered category with more workers
rag benchmark thinking_fast_and_slow --category biases --workers 5
```

## CI Mode

When `--ci` is set:

1. The benchmark runs normally
2. Output is printed as a single JSON object to stdout
3. The JSON includes `status`, `gates`, `failures`, `warnings`, `report_path`
4. If any gate fails, exit code is 1 (blocks CI pipeline)

### CI JSON Structure

```json
{
  "status": "completed",
  "dataset": "thinking_fast_and_slow",
  "total": 75,
  "successful": 75,
  "failed": 0,
  "gates": "pass",
  "gates_passed": 5,
  "gates_failed": 0,
  "failures": [],
  "warnings": [],
  "report_path": "reports/thinking_fast_and_slow/2026-07-22_19-31-15",
  "benchmark_version": "2.0.0",
  "git_commit": "270b0d3",
  "dataset_hash": "ffdf755b..."
}
```

## What Happens During a Benchmark

1. **Validation** — dataset exists, retriever mode is valid
2. **Execution** — all questions are sent to `/chat/evaluate` in parallel (up to `--workers` at a time)
3. **Scoring** — claims are checked, RAGAS scores computed, weighted pass rate calculated
4. **Analytics** — retrieval distribution, coverage, method effectiveness
5. **Reporting** — summary.json, results.json, results.csv, report.html, metadata.json
6. **Gates** — regression thresholds checked (PASS/WARNING/FAIL)
7. **Comparison** — if `--compare` is set, diff vs baseline run
8. **Trends** — historical trend dashboard updated
9. **Output** — CI JSON or interactive Rich table

## Report Directory Structure

```
reports/<dataset>/<timestamp>/
    summary.json            — Run summary with scores, latencies, metadata
    results.json            — Per-question results with claims, chunks, scores
    results.csv             — Tabular per-question results
    report.html             — Full HTML report with visualizations
    metadata.json           — Environment and configuration metadata
    README.md               — Index of all artifact files
    analytics/
        retrieval_analytics.json     — Method distribution, average scores
        retrieval_coverage.json      — Per-document chunk coverage statistics
        method_effectiveness.json    — Vector vs BM25 vs hybrid comparison
    comparison/
        comparison.json     — Machine-readable metric deltas vs baseline
        comparison.csv      — Tabular metric comparison
        comparison.html     — Visual comparison report
    failures/
        <question-id>.json  — Detailed failure artifacts (if any)
    trends.html             — Historical trend dashboard (at dataset root)
```
