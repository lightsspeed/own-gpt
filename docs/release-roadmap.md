# Release Roadmap & Checklist

## 1. Project Status

### What is this platform?

The **LLM Evaluation & Retrieval Platform** is a closed-loop benchmarking system for evaluating retrieval-augmented generation (RAG) pipelines. It measures retrieval quality, answer faithfulness, latency, coverage, cost, and more across multiple datasets with a deterministic, CI-integrated evaluation framework.

### What problems does it solve?

- **Benchmarking RAG** — systematically measure retrieval + generation quality across datasets, retrievers, and configurations
- **Regression detection** — catch quality degradation before it reaches production via three-level gates (PASS/WARNING/FAIL)
- **Reproducibility** — lock every variable (dependencies, datasets, metadata) so runs are comparable across time and environments
- **Multi-corpus validation** — validate against 5 diverse corpuses (psychology, FastAPI, Kubernetes, Terraform, AWS WAF) totalling 153 questions
- **Cost awareness** — track prompt/completion/embedding tokens per run with estimated USD cost
- **CI/CD integration** — quality gates block merges on regression, PR summaries auto-generated, trend dashboard tracks history

### Current architecture

```
CLI (typer)
  |
EvaluationEngine (orchestrator)
  |-- validate
  |-- benchmark (parallel HTTP workers)
  |-- generate_reports (HTML + comparison)
  |-- compute_analytics (method distribution, coverage, effectiveness)
  |-- write_summary (enriched summary.json)
  |-- generate_comparison (vs baseline)
  |-- check_gates (regression thresholds)
  |-- update_trends (Chart.js dashboard)
  |-- write_bundle_readme
  |
Backend (FastAPI)
  |-- GET /api/v1/index/status
  |-- GET /api/v1/index/corpus
  |-- POST /api/v1/chat/evaluate
  |
Retrieval Pipeline
  |-- Embedding (text-embedding-3-small)
  |-- Vector search (pgvector)
  |-- BM25 search (Whoosh)
  |-- RRF fusion
  |-- Reranking (FlashRank)
  |-- LLM (gpt-4o-mini)
```

### Current capabilities

| Capability | Status |
|---|---|
| Hybrid retrieval (vector + BM25 + RRF) | Mature |
| Reranking with FlashRank | Mature |
| Deterministic evaluation endpoint | Mature |
| YAML-driven regression gates (3-level) | Mature |
| HTML reports with analytics | Mature |
| Comparison reports | Mature |
| Multi-corpus benchmarking (5 datasets) | Mature |
| Weighted questions (1-4) | Mature |
| Retrieval provenance per chunk | Mature |
| Retrieval method distribution analytics | Mature |
| Retrieval coverage analytics | Mature |
| Retrieval method effectiveness | Mature |
| True corpus coverage | Mature |
| CI/CD integration (GitHub Actions) | Mature |
| PR summary generation | Mature |
| Trend dashboard (Chart.js) | Mature |
| Reproducibility metadata (14 fields) | Mature |
| Dependency freezing (lockfile) | Mature |
| Install verification | Mature |
| Cost tracking (token usage + USD) | Mature |
| Evaluation engine orchestration | Mature |
| Documentation (7 docs) | Mature |

### Current maturity

This is no longer a RAG application. It is an **LLM Evaluation & Retrieval Platform** with five mature subsystems:

| Subsystem | Maturity |
|---|---|
| Retrieval Platform | Mature |
| Evaluation Framework | Mature |
| Benchmarking Framework | Mature |
| Reporting & Analytics | Mature |
| CI/CD & Reproducibility | Mature |

---

## 2. v1.0 Scope

### Included

- Hybrid retrieval (vector + BM25 + RRF)
- FlashRank reranking
- Deterministic `/chat/evaluate` endpoint
- Multi-corpus benchmarking (153 questions across 5 corpuses)
- Weighted questions (1-4)
- Retrieval provenance (method, scores, ranks per chunk)
- Retrieval method distribution analytics
- Retrieval coverage analytics (per-document + overall)
- True corpus coverage (vs pgvector manifest)
- Retrieval method effectiveness
- HTML reports with executive summary
- Comparison reports (vs baseline)
- YAML-driven three-level regression gates (PASS/WARNING/FAIL)
- CI/CD integration (GitHub Actions, matrix strategy, artifact upload)
- PR summary markdown generation
- Trend dashboard (Chart.js, per-metric line charts, snapshot table)
- Reproducibility metadata (14 fields per run)
- Dependency freezing (requirements-lock.txt)
- Install verification script
- Cost tracking (tokens + estimated USD)
- Evaluation engine orchestration (9-stage pipeline)
- CLI (benchmark, trends, history, datasets, index)
- Documentation (architecture, evaluation, benchmark, datasets, CI/CD, reproducibility, developer guide)

### Deferred (post-v1.0)

- **Named experiment tracking** — semantic grouping of runs into experiments (e.g. `hybrid-v1`, `hybrid-v2`), query by tag, promote to baseline
- **Python packaging** — `pyproject.toml`, `pip install rag-eval-platform`, entrypoint CLI
- **Configuration consolidation** — unified `BenchmarkConfig` pydantic model from YAML/env/defaults
- **Stress testing** — resource limits (peak memory, CPU, concurrent connections)
- **Failure injection / chaos testing** — graceful degradation under network, API, or dependency failures
- **Long-running regression** — scheduled CI runs to detect drift over time
- **Additional datasets** — beyond the current 5
- **Distributed benchmarking** — horizontal scaling for large corpora
- **New retrieval research** — Graph RAG, agentic retrieval, MCP, query decomposition (only when benchmark data shows a gap)

---

## 3. Release Criteria

```
□ All 5 datasets benchmark successfully with --ci
□ No regression gate failures on main
□ Clean install verified (verify_install.py --clean)
□ Documentation complete (all 7 docs reviewed)
□ No critical or high-severity bugs
□ Static analysis clean (Ruff: zero errors, zero warnings)
□ Type checking clean (Pyright: zero errors)
□ Unit test coverage >= 80% (core modules: analytics, gates, coverage, cost, engine)
□ Integration suite passing (benchmark, evaluate, index, ingestion, comparison)
□ CI workflow green on push and PR
□ Version tagged (v1.0.0)
□ Release notes written
```

---

## 4. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| RAGAS API changes or deprecation | Medium | High | Pin ragas version in lockfile; metric defaults to 0 if import fails |
| OpenAI pricing/ model changes | High | Medium | Centralized cost constants in benchmark.py; update pricing at release |
| Dataset drift (source docs change) | Medium | Medium | Dataset hashing in reproducibility metadata; pinned corpus snapshots |
| Dependency conflicts on upgrade | Medium | High | Lockfile verification; verify_install.py checks all key imports |
| Benchmark instability (flaky results) | Low | High | Warning zone (2%) prevents false positives; regression gates have configurable thresholds |
| pgvector version incompatibility | Low | Medium | Docker Compose pins pgvector image; migration tested end-to-end |
| Whoosh index corruption | Low | Low | GET /api/v1/index/status health check; rebuild endpoint available |

---

## 5. RC Sequence

### RC-1

**Focus: Release checklist, scope freeze, version policy**

- [ ] Draft and publish release roadmap (this document)
- [ ] Freeze v1.0 scope (no new features)
- [ ] Establish versioning policy (SemVer: MAJOR.MINOR.PATCH)
- [ ] Create v1.0.0 milestone
- [ ] Bug-fix-only mode for all PRs targeting v1.0
- [ ] Audit current issues and classify as v1.0 blocker vs deferred

### RC-2

**Focus: Tests, static analysis, config cleanup, documentation review**

- [ ] Run Ruff across entire codebase; fix all errors and warnings
- [ ] Run Pyright; fix all type errors
- [ ] Remove dead code and duplicated utilities
- [ ] Consolidate logging and exception handling patterns
- [ ] Write unit tests for:
  - `app/evaluation/analytics.py` — method distribution, coverage calculations
  - `app/evaluation/gates.py` — all three gate levels, warning zone behavior
  - `app/evaluation/coverage.py` — coverage percent, per-document aggregation
  - `app/evaluation/reproducibility.py` — all 14 metadata fields
  - `app/evaluation/trends.py` — snapshot collection, metric extraction
  - `app/evaluation/benchmark.py` — cost aggregation, summary construction
  - `app/evaluation/engine.py` — pipeline stage order, error propagation
- [ ] Write integration tests for:
  - Full benchmark cycle on `thinking_fast_and_slow` (3 questions)
  - `/chat/evaluate` endpoint returns valid response
  - Index status and rebuild endpoints
  - Comparison report generation
  - CI output structure and exit codes
- [ ] Review and finalize all 7 docs
- [ ] Verify dataset hashes are stable

### RC-3

**Focus: Performance baseline, cross-platform, dependency audit, release notes**

- [ ] Run full benchmark (all 5 datasets); record performance baseline:

  | Metric | Value |
  |---|---|
  | 153 questions total time | X min |
  | Average latency per question | X ms |
  | Peak memory | X GB |
  | CPU utilization | X% |

- [ ] Verify install on clean Windows and Ubuntu environments
- [ ] Final dependency audit (check for outdated or vulnerable packages)
- [ ] Update lockfile to latest compatible versions
- [ ] Write release notes (summary of changes, known issues, upgrade guide)
- [ ] Tag v1.0.0

### v1.0

- [ ] Stable APIs (`/api/v1/` — versioned)
- [ ] Stable benchmark datasets (hashed)
- [ ] Stable CI/CD (green on push/PR)
- [ ] Stable documentation (7 docs finalized)
- [ ] Stable reproducibility (lockfile + metadata)
- [ ] GitHub release published

---

## 6. Post-v1.0 Backlog (prioritized)

1. **⭐ Named experiment tracking** — `rag experiment create`, tag runs, query by tag, promote to baseline, compare experiments
2. **Packaging** — `pyproject.toml`, `rag` CLI entrypoint, `pip install` without source checkout
3. **Configuration consolidation** — single `BenchmarkConfig` pydantic model, merged YAML/env/defaults chain
4. **Stress testing** — resource limits, concurrent connections, large-corpus performance
5. **Failure injection** — graceful degradation under network/API/dependency failures
6. **Long-running regression** — scheduled CI drift detection
7. **Additional datasets** — community contributions, domain-specific corpora
8. **New retrieval research** — only when benchmark data reveals a measurable gap

---

## 7. Non-Goals (v1.0)

The following are explicitly **not** part of the v1.0 release:

- Implementing new retrieval algorithms (Graph RAG, agentic retrieval, MCP, query decomposition)
- Adding agentic or multi-agent workflows
- Introducing knowledge graphs
- Supporting every LLM provider (remains gpt-4o-mini for evaluation consistency)
- Building a production serving layer
- Real-time or streaming evaluation
- User authentication or multi-tenant support
- Web UI (beyond the trend dashboard)

---

## 8. Appendix: Design Rationale (for reference)

These are the key engineering decisions that shape the platform. Preserved here to avoid re-litigation during release stabilization.

| Decision | Rationale |
|---|---|
| `/chat/evaluate` as single evaluation source of truth | Benchmark, CI/CD, and debugging all use the same endpoint — no drift |
| RRF over weighted fusion | No tuning required; empirically robust across heterogeneous retrievers |
| Three-level gates (PASS/WARNING/FAIL) | Catches metric drift (2% warning zone) without blocking merges on noise |
| Separate `/chat` and `/chat/evaluate` endpoints | `/chat` is for users; `/evaluate` adds provenance, trace, confidence — different SLAs |
| Reproducibility metadata at benchmark time | Ensures accuracy even when configs change between runs |
| Lockfile + requirements.txt | Eliminates dependency drift as a variable in benchmark comparisons |
| tiktoken for token counting | Model-specific encoding matches actual API tokenization |
| Weighted questions (1-4) | Reflects real-world priority without complicating the scoring model |
| Per-chunk provenance | Enables drill-down analysis of retrieval behavior at the chunk level |
