# Developer Guide

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension (or Docker)
- Redis (or Docker)
- OpenAI API key

### Quick Start (Docker)

```bash
docker compose up -d
```

This starts PostgreSQL (with pgvector) and Redis, then launches the backend.

### Quick Start (Local)

```bash
# Install dependencies
pip install -r requirements-lock.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Start services (PostgreSQL + Redis required)
# Then start the backend
uvicorn app.main:app --reload --port 8000
```

### Verify Setup

```bash
# Check backend is running
curl http://localhost:8000/docs

# Rebuild search index
rag index rebuild
```

## Ingestion Workflow

### Upload a Document

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@path/to/document.pdf"

# Via ingest script (for full corpuses)
python scripts/ingest_corpus.py fastapi --api-url http://localhost:8000
```

The system supports PDF, Markdown, and plain text files.

### Rebuild Search Index

```bash
rag index rebuild

# Or via API
curl -X POST http://localhost:8000/api/v1/index/rebuild

# Check status
rag index status
```

## Running Benchmarks

### Basic

```bash
rag benchmark thinking_fast_and_slow
```

### CI Mode

```bash
rag benchmark thinking_fast_and_slow --ci --compare latest
```

### With Different Retriever

```bash
rag benchmark thinking_fast_and_slow --retriever vector
rag benchmark thinking_fast_and_slow --retriever bm25
```

## Viewing Results

### Reports

```bash
# List all runs
rag reports

# Show specific run
rag report <run-timestamp>

# Show history
rag history thinking_fast_and_slow
```

### Trend Dashboard

```bash
rag trends thinking_fast_and_slow
rag trends thinking_fast_and_slow --open   # Open in browser
```

## Extending the Platform

### Adding a New Retriever

1. Create the retriever module in `app/retrievers/`
2. Implement a class with `search(query, k)` method returning chunks
3. Register it in `app/agent/pipeline/retriever.py`
4. Add the mode to `pipeline_config.yaml`
5. Add the mode to the CLI's validator in `engine.py`

### Adding a New Metric

1. Add the computation to `app/evaluation/analytics.py`
2. If it's a threshold metric, add to `pipeline_config.yaml`
3. Add to the regression detector in `regression.py`
4. Add to the report in the appropriate reporter module
5. Add to the CI output in `cli.py`

### Adding a New Reporter

1. Create a module in `app/evaluation/reporters/`
2. Implement a function that takes `summary, results, dataset, output_dir`
3. Call it from the engine's `_generate_reports()` or `_compute_analytics()`
4. Add the output file to `_write_bundle_readme()`

### Adding a New Dataset

See [datasets.md](datasets.md) for the full guide.

## Architecture Conventions

- **Engine pattern** — all evaluation orchestration goes through `engine.py`. CLI, future API endpoints, and scheduled jobs all use the same `EvaluationEngine` class.
- **Reproducibility** — every run records metadata (git commit, dataset hash, dependency hash). Never skip this.
- **Reporters** — each output format is a separate module in `reporters/`. Keep them modular.
- **Backend as source of truth** — the benchmark communicates with the backend via HTTP. Never query the database directly from evaluation code.

## Testing

```bash
# Run a quick benchmark
python scripts/test_benchmark.py

# Test comparison report
python scripts/test_comparison.py

# Test CI output
python scripts/test_ci.py

# Test reproducibility
python scripts/test_reproducibility.py

# Verify install
python scripts/verify_install.py
```

## Troubleshooting

### Backend Not Running

```bash
# Start manually
uvicorn app.main:app --reload --port 8000

# Check logs
tail -f uvicorn.log
```

### No Documents Retrieved

```bash
# Check index status
rag index status

# Rebuild index
rag index rebuild

# Check documents are uploaded
curl http://localhost:8000/api/v1/documents/
```

### RAGAS Scores Return 0

```bash
pip install ragas
```

RAGAS is optional — the benchmark works without it, but all RAGAS-based gates will fail.

### Dataset Not Found

```bash
# List available datasets
rag datasets
```

### Comparison Report Missing

Ensure you've run at least two benchmarks with the same dataset, then:

```bash
rag benchmark thinking_fast_and_slow --compare latest
```
