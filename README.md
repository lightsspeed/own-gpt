# OwnGPT

An evidence-driven AI engineering platform with a RAG-powered agent, continuous self-evaluation, explicit governance, offline experimentation, and operational workflows.

## Architecture

The platform is organized into ten stable pillars, each with one responsibility:

| Pillar | Responsibility |
|--------|---------------|
| **Runtime** | Chat streaming, tool calling, agent orchestration |
| **Evaluation** | Offline benchmarking, regression gates, reproducibility |
| **Learning** | Telemetry collection, storage (SQLite + JSONL) |
| **Analytics** | Query intelligence, retrieval analytics, routing analytics, user behavior, trends |
| **Evidence** | Confidence calibration, knowledge gap diagnosis, retrieval failure tree |
| **Recommendations** | Thin presentation layer over Evidence findings |
| **Experiments** | Counterfactual replay, comparator, decision candidates |
| **Governance** | Lineage tracking, artifact registry, principles, policies, guardrails |
| **Configuration** | Versioned snapshots, pointer-based rollback, diff |
| **Operations / Automation** | Workspace UIs, health scoring, trigger engine, daily briefs, schedules |

### Lifecycle

```
Observe → Measure → Explain → Propose → Validate → Apply → Operate
```

Every layer reads from previous layers. No layer mutates previous layers. All conclusions are evidence-backed. All production changes are human-approved and traceable.

### Artifact Graph (explains *why* decisions were made)

```
LearningRecord → AnalyticsReport → Evidence → Finding → Recommendation
→ Experiment → DecisionCandidate → Decision → ConfigurationSnapshot
```

### Capability Graph (explains *what* the platform can do)

The platform is self-describing via a [Capability Registry](app/learning/architecture/capabilities.py) — 26 registered capabilities across all 10 pillars, each with owner, dependencies, lifecycle stage, maturity, artifacts, and API prefix.

## Features

### RAG Pipeline
- **Intent classification**: rule-based + LLM classifier (6 intents: chat, rag, analyze, search, image, diagnose)
- **Query rewrite**: contextual compression, multi-query expansion
- **Retrieval**: BM25 (Whoosh) + hybrid (dense + sparse fusion), configurable top-k
- **Reranker**: cross-encoder reranking with confidence scores
- **Confidence scoring**: evidence-based, calibrated against empirical accuracy
- **Validation**: PII sanitization (11 patterns), response quality guards
- **Tracing**: per-request token counts, latency, confidence, cost tracking

### Evaluation Engine
- **Benchmark runner**: run RAGAS-based evaluations against 5 built-in datasets (fastapi, kubernetes, terraform, aws_well_architected, thinking_fast_and_slow)
- **Intent accuracy**: 40-query benchmark for intent classifier accuracy
- **Regression gates**: three-level gates (warn/fail thresholds) with trend-aware comparison
- **Reproducibility**: metadata capture (model, temperature, chunk params), lockfile pinning
- **Analytics**: corpus coverage, cost tracking, trend analysis over time
- **Reporting**: HTML reports, comparison reports, CLI output
- **CI/CD integration**: GitHub Actions workflow for automated benchmarking

### Ingestion Pipeline
- Multi-format document parser: PDF, DOCX, PPTX, XLSX, CSV, HTML, TXT, Markdown
- Configurable chunking strategies
- Embedding and storage in pgvector

### Learning Platform

#### Analytics Engine
- Query intelligence: patterns, failures, rewrite effectiveness
- Retrieval intelligence: chunk quality, score distributions
- Routing analytics: intent distribution, fallback rates
- User behavior: session analysis, engagement metrics
- Trend analytics: metric changes over time

#### Evidence Engine
- Confidence calibration: ECE calculation, 10-bucket reliability curves, over/underconfidence detection
- Knowledge gap diagnosis: decision tree analysis (no_docs → insufficient_coverage → poor_reranker → bad_routing → low_confidence → unknown)
- Retrieval failure tree: classifier for every failed query

#### Architecture Governance
- **Artifact registry**: 9 artifact types with lineage tracking (parent/children/path queries)
- **8 principles**: modeled and importable (PRINCIPLES 001–008)
- **Guardrails**: `validate_lineage()`, `validate_finding()`, `validate_recommendation()`
- **Evidence policies**: multi-dimensional threshold checks with trend, source count, and observation requirements

#### Experimentation Framework
- **ReplayRunner**: counterfactual metrics for reranker_threshold, confidence_threshold, retriever_top_k changes
- **Comparator**: wins/losses/unchanged per metric with overall verdict
- **DecisionCandidate**: auto-generated from experiments

#### Configuration Management
- **ConfigurationSnapshot**: immutable, versioned, with pointer-based rollback
- **ConfigManager**: JSON file store, CRUD, diff between any two snapshots

#### Operations Control Plane
- 5 workspaces: Findings, Recommendations, Experiments, Decisions, Configurations
- Priority scoring: severity × evidence_strength × frequency × trend
- Artifact Explorer: full lineage traversal from any artifact

#### Continuous Evaluation (Platform 2.0)
- **EvaluationSnapshot**: 30+ aggregate fields + delta tracking
- **Health scoring**: 6 domains (Retrieval, Knowledge, Calibration, Routing, Experiments, Overall), starts at 100, penalized by severity × evidence strength × frequency
- **Trigger engine**: 6 conditions (confidence drop >5%, ECE increase >2%, new critical findings, knowledge gap surge >1.5x, weak chunks >1.5x, findings doubled)
- **DailyBrief**: automated daily summary
- **Scheduler**: 3 default schedules (daily evaluation, hourly calibration, weekly benchmark)

### Frontend
- **Design system**: colors, typography, spacing, motion, icons, shadows, radii, breakpoints, z-index — all semantically mapped
- **Layout components**: AppShell, Sidebar, Header, Content, Stack, Inline, Section, Surface, Divider, ScrollArea, PageContainer
- **Primitive components**: Button, IconButton, Badge, Accordion, Tooltip, Skeleton, EmptyState
- **Chat workspace**: message list, streaming overlay, composer, conversation toolbar, code blocks, markdown rendering
- **Evidence panel**: confidence meter, debug accordion, pipeline summary, source cards, mode cards
- **Routing**: React Router with RootLayout, chat route, UI lab

## Tech Stack

### Frontend
- React 18, Vite, TypeScript
- TailwindCSS, Framer Motion
- React Router, React Markdown

### Backend
- Python 3.12.9, FastAPI, Uvicorn
- LangChain, LangGraph
- PostgreSQL with pgvector, Whoosh (BM25), SQLite with WAL (learning store)
- OpenAI API (embeddings + LLM)

## Getting Started

### Prerequisites
- Docker and Docker Compose
- OpenAI API Key

### Installation

```bash
git clone https://github.com/lightsspeed/own-gpt.git
cd own-gpt
```

Create `.env`:
```env
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key_for_web_search
```

```bash
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs

## Documentation

See [docs/](docs/) for detailed guides:

- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Benchmark](docs/benchmark.md)
- [Datasets](docs/datasets.md)
- [CI/CD](docs/ci-cd.md)
- [Reproducibility](docs/reproducibility.md)
- [Developer Guide](docs/developer-guide.md)
- [ADR](docs/adr/) — 11 Architecture Decision Records

## API Routes

68 API routes across the platform:

| Prefix | Module |
|--------|--------|
| `/api/chat` | Chat streaming |
| `/api/documents` | Document management |
| `/api/index` | Whoosh index management |
| `/api/system` | System info, health |
| `/api/v1/telemetry/*` | Learning telemetry |
| `/api/v1/analytics/*` | Analytics queries |
| `/api/v1/evidence/*` | Evidence + findings |
| `/api/v1/experiments/*` | Experiment management |
| `/api/v1/config/*` | Configuration snapshots |
| `/api/v1/operations/*` | Workspace UIs + explorer |
| `/api/v1/automation/*` | Evaluation runs, health, triggers, schedules, briefs |
| `/api/v1/capabilities/*` | Capability registry introspection |

## Project Structure

```
├── app/
│   ├── agent/            — LangGraph agent, RAG pipeline (intent, rewrite, retriever, reranker, confidence, validation)
│   ├── api/              — REST endpoints
│   ├── core/             — Config, LangSmith, Whoosh manager
│   ├── evaluation/       — Benchmark engine, metrics, regression, reporting, analytics, reproducibility
│   ├── ingestion/        — Document parser pipeline
│   ├── learning/         — Platform pillars (analytics, evidence, architecture, experiments, config, operations, automation)
│   ├── retrievers/       — BM25 + hybrid retriever
│   └── services/         — pgvector integration
├── frontend/             — React/Vite design system + chat workspace
├── docs/                 — Architecture, evaluation, benchmarks, ADRs
├── tests/                — Pipeline tests + RAG benchmark datasets
└── scripts/              — Ingestion, testing, verification utilities
```

## Principles

1. Every observation is persisted.
2. Every metric is reproducible.
3. Every conclusion is evidence-backed.
4. Every recommendation is traceable.
5. Every optimization is validated offline.
6. Every production change is human-approved.
7. Every artifact has lineage.
8. Every capability is discoverable.

## License

MIT
