# Reproducibility

## Why It Matters

Every benchmark run records enough environmental context to reproduce the exact same conditions months later. This is essential for:

- Auditing historical results
- Debugging regressions after dependency upgrades
- Comparing results across different team members' machines
- Proving that benchmark improvements come from code changes, not environmental drift

## What Is Recorded

Every run produces a `metadata.json` and a `reproducibility` block in `summary.json` containing:

| Field | Source | Purpose |
|---|---|---|
| `benchmark_version` | Hardcoded constant | Which version of the evaluation framework |
| `git_commit` | `git rev-parse --short HEAD` | Exact code state |
| `git_branch` | `git rev-parse --abbrev-ref HEAD` | Development branch |
| `git_dirty` | `git status --porcelain` | Whether uncommitted changes exist |
| `dataset_hash` | SHA256 of `questions.jsonl` | Exact dataset content |
| `requirements_hash` | SHA256 of `requirements-lock.txt` | Exact dependency set |
| `python_version` | `platform.python_version()` | Runtime version |
| `embedding_model` | Config | OpenAI embedding model |
| `embedding_dimensions` | Config | Embedding vector size |
| `reranker_model` | From `pipeline_config.yaml` | Cross-encoder model |
| `llm` | Config | Language model |
| `chunk_size` | Config | Document chunk size |
| `timestamp` | System clock | When the run occurred |
| `category` | CLI argument | Category filter (if any) |

## Lockfile

`requirements-lock.txt` contains exact pinned versions for every dependency (direct and transitive). To reproduce an environment:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements-lock.txt
```

## Verify Install

```bash
# Quick check in current environment
python scripts/verify_install.py

# Full clean-room test
python scripts/verify_install.py --clean
```

The verification script checks that all 11 key imports resolve correctly:

- fastapi, uvicorn, pydantic, sqlalchemy
- langchain_openai, langchain_postgres
- langgraph
- tavily, flashrank
- typer, rich

## CI Enforcement

The GitHub Actions workflow runs `verify_install.py` before every benchmark. If imports fail, the pipeline stops with a clear error message.

## Best Practices

1. **Commit lockfile changes** — whenever you add or upgrade a dependency, regenerate the lockfile
2. **Check git_dirty** — if a benchmark shows `git_dirty: true`, results may not be reproducible
3. **Use named baselines** — instead of `--compare latest`, create named baselines for releases
4. **Pin major versions** — `requirements.txt` uses exact pins (not `>=`) to prevent unexpected upgrades
