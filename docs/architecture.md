# Architecture

## Overview

The system is a closed-loop RAG evaluation platform with CI/CD quality gates. It combines hybrid retrieval (vector + BM25), structured evaluation, regression detection, and rich reporting into a single pipeline.

```
User / CI
    |
    v
CLI (typer)  ──>  EvaluationEngine  ──>  Benchmark  ──>  Backend API
                         |                       |              |
                    collect_metadata          run questions   /chat/evaluate
                         |                       |
                    generate_reports         compute_analytics
                         |                       |
                    check_gates             write_results
                         |
                    update_trends
```

## Components

### Backend (`app/`)

| Module | Responsibility |
|---|---|
| `api/endpoints/chat.py` | `/chat/evaluate` — single evaluation endpoint |
| `api/endpoints/documents.py` | Document upload, list, delete |
| `api/endpoints/index.py` | Whoosh index status, rebuild, corpus manifest |
| `agent/pipeline/` | Full retrieval pipeline (intent, rewrite, retriever, fusion, reranker, confidence, response, validation) |
| `services/vector_store.py` | PGVector (pgvector) embedding storage |
| `retrievers/bm25.py` | Whoosh BM25 full-text search |
| `core/whoosh_manager.py` | Whoosh index lifecycle management |

### Evaluation (`app/evaluation/`)

| Module | Responsibility |
|---|---|
| `engine.py` | `EvaluationEngine` — single orchestration layer for the full evaluation pipeline |
| `benchmark.py` | `run_benchmark()` — execute questions against backend API |
| `loader.py` | Dataset loading and question representation |
| `analytics.py` | Retrieval analytics, coverage, effectiveness, weighted scores |
| `regression.py` | `RegressionDetector` — three-level gates (PASS/WARNING/FAIL) |
| `report.py` | `ReportGenerator` — writes summary.json, results, CSV, HTML, metadata |
| `reporters/` | Modular reporter package (HTML, comparison) |
| `trends.py` | Historical trend dashboard generation |
| `reproducibility.py` | Metadata collection for reproducibility |
| `cli.py` | CLI interface (thin presentation layer over engine) |
| `ragas_runner.py` | RAGAS scoring integration |
| `metrics.py` | Retrieval metric computation |

## Data Flow

### Document Ingestion

```
User uploads PDF
    |
    v
POST /api/v1/documents/upload
    |
    v
PyPDFLoader / TextLoader ──> RecursiveCharacterTextSplitter (1000/200)
    |
    v
Inject chunk_id + filename into metadata
    |
    v
OpenAIEmbeddings ──> PGVector (pgvector)
    |
    v
add_to_whoosh_index() ──> Whoosh BM25 index
```

### Query Processing

```
User message
    |
    v
Intent Classification ──> RAG or Web or Direct
    |
    v (RAG path)
Query Rewriting
    |
    v
Hybrid Retrieval:
  ├── Vector search (pgvector, top-20)
  └── BM25 search (Whoosh, top-20)
    |
    v
RRF Fusion (k=60) ──> Reranker (cross-encoder) ──> Top-5 chunks
    |
    v
Confidence Evaluation
    |
    v
LLM Response Generation ──> Validation ──> Answer
```

## Evaluation Flow

```
EvaluationEngine.run()
    |
    ├── 1. validate()       — dataset exists, retriever mode valid
    ├── 2. run_benchmark()  — execute all questions via backend API
    ├── 3. generate_reports() — write summary.json, results, HTML, metadata
    ├── 4. compute_analytics() — retrieval analytics, coverage, effectiveness
    ├── 5. write_summary()  — persist enriched summary to disk
    ├── 6. generate_comparison() — diff vs baseline run
    ├── 7. check_gates()    — PASS/WARNING/FAIL regression gates
    ├── 8. update_trends()  — update historical trend dashboard
    └── 9. write_bundle_readme() — index README at report root
```

## Key Design Decisions

- `/chat/evaluate` is the single evaluation source of truth — benchmark, CI/CD, and ad-hoc debugging all use the same endpoint
- `EvaluationEngine` orchestrates all pipeline stages — CLI, REST API, and scheduled jobs all share the same execution path
- Hybrid retrieval (vector + BM25 + RRF + reranker) gives best coverage across semantic and keyword queries
- Three-level gates (PASS/WARNING/FAIL) prevent alert fatigue from natural LLM metric fluctuation
- Reproducibility metadata (git commit, dataset hash, dependency lock hash) ensures every run is auditable months later
