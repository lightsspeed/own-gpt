# Tasks

## BACKEND

### Experiment Portfolio
- [ ] Experiment catalog API (list/filter/compare)
- [ ] Deployment metadata attached to experiments
- [ ] Track which candidate is live in production
- [ ] Historical experiment results with confidence intervals

### Recommendation Confidence
- [ ] Feedback loop — log whether recommendations were accepted/rejected/dismissed
- [ ] Precision/recall per recommendation type
- [ ] Surface low-confidence recommendations for review

### Release Intelligence
- [ ] Gate CI/CD on evaluation health scores from Continuous Evaluation
- [ ] Compare evaluation snapshots across releases
- [ ] Auto-block deployment if regression exceeds threshold
- [ ] Generate release notes from health deltas

### Knowledge Lifecycle
- [ ] Monitor chunk access frequency
- [ ] Flag stale/unused chunks for re-ingestion
- [ ] Detect coverage gaps (query topics vs corpus topics)
- [ ] Auto-trigger ingestion pipeline when gap is detected

### Platform Stability
- [x] ~~Comprehensive test suite for learning platform (unit + integration)~~
- [ ] Error handling middleware for all API routes
- [ ] Structured logging with correlation IDs
- [ ] Prometheus metrics endpoint
- [ ] Health check endpoints per service

---

## ARCHITECTURE

### Capability Registry Evolution
- [ ] Add `introduced_version`, `last_modified`, `deprecation_status`, `stability` to capabilities
- [ ] Version artifact contracts
- [ ] Formalize API deprecation policy
- [ ] Cross-capability impact analysis endpoint

### Platform Documentation
- [ ] Publish Platform Manifesto doc (8 principles)
- [ ] Capability readiness dashboard (maturity heatmap by lifecycle stage)
- [ ] Capability dependency graph visualization

---

## FRONTEND

### Experiment Portfolio UI
- [ ] Experiment list view with status filters
- [ ] Experiment detail with replay results
- [ ] Comparison view (side-by-side metrics)
- [ ] Deployment indicator showing which candidate is live

### Operations Dashboard
- [ ] Health scores over time (sparklines)
- [ ] Active triggers list
- [ ] Daily brief viewer
- [ ] Findings/priorities workspace with accept/dismiss actions

### Capability Registry Explorer
- [ ] Browse all capabilities by pillar
- [ ] View dependency graph
- [ ] Filter by lifecycle stage / maturity
- [ ] Show API endpoints per capability

---

## UI/UX

### Chat Workspace Polish
- [ ] Streaming indicator animations
- [ ] Message grouping
- [ ] Keyboard shortcuts
- [ ] Command palette
- [ ] Dark/light mode toggle
- [ ] Responsive mobile layout

### Evidence Panel Interactions
- [ ] Clickable pipeline stages
- [ ] Drill-down from confidence score to calibration curve
- [ ] Expandable failure tree with suggestion actions
- [ ] Source card with inline preview

---

## LLM

### Multi-Provider Support
- [ ] Evaluate Anthropic, Gemini, local models (Ollama) vs OpenAI on benchmarks
- [ ] Model routing based on intent + cost
- [ ] Per-model cost/quality tradeoffs in analytics

### Intent Classifier
- [ ] Improve accuracy with few-shot examples
- [ ] New intents: summarize, translate, code
- [ ] Classifier vs LLM-based classification cost-accuracy pareto

### Reranker Quality
- [ ] Evaluate cross-encoder vs LLM-as-reranker
- [ ] Compute nDCG/MRR improvements
- [ ] A/B experiment support for reranker variants

### Confidence Calibration
- [ ] Calibrate per-domain (not global)
- [ ] Temperature scaling
- [ ] Evaluate calibration across different LLM providers
