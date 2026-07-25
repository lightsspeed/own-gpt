# Datasets

## Available Datasets

| Dataset | Questions | Categories | Total Weight | Domain |
|---|---|---|---|---|
| `thinking_fast_and_slow` | 75 | 11 | 130 | Psychology / Behavioral Economics |
| `fastapi` | 20 | 6 | 38 | Web Framework |
| `kubernetes` | 20 | 6 | 39 | Container Orchestration |
| `terraform` | 20 | 6 | 42 | Infrastructure as Code |
| `aws_well_architected` | 18 | 6 | 40 | Cloud Architecture |

## Dataset Format

Each dataset lives in `tests/rag/datasets/<name>/` with two files:

### `meta.json`

```json
{
  "display_name": "Thinking, Fast and Slow",
  "description": "Benchmark questions based on Daniel Kahneman's book...",
  "source": "Thinking, Fast and Slow by Daniel Kahneman (2011)",
  "total_questions": 75,
  "categories": ["system_1_2", "heuristics", "biases", ...]
}
```

### `questions.jsonl`

One JSON object per line. Each question has:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier (e.g. `sys1-01`) |
| `category` | string | yes | Functional area (e.g. `system_1_2`) |
| `difficulty` | string | yes | `easy`, `medium`, or `hard` |
| `question` | string | yes | The actual question text |
| `expected_claims` | string[] | yes | Claims the answer must contain |
| `must_not_contain` | string[] | yes | Terms that indicate hallucination |
| `expected_sources` | string[] | no | Source document references |
| `weight` | int | no | Importance (1-4, default 1) |
| `complexity` | string | no | `low`, `medium`, `high` |
| `priority` | string | no | `low`, `normal`, `high` |
| `tags` | string[] | no | Arbitrary tags for filtering |

## Adding a New Dataset

### 1. Create the directory

```bash
mkdir tests/rag/datasets/<name>
```

### 2. Write meta.json

```json
{
  "display_name": "My Dataset",
  "description": "What this dataset tests",
  "source": "URL or citation",
  "total_questions": 15,
  "categories": ["category_a", "category_b"]
}
```

### 3. Write questions.jsonl

Each line is a question. Start with 10-15 questions across 2-3 categories.

### 4. Ingest source documents

```bash
python scripts/ingest_corpus.py <name> --api-url http://localhost:8000
```

Or upload manually via the API:

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@path/to/document.pdf"
```

### 5. Verify

```bash
rag benchmark <name> --ci
```

### Guidelines for Writing Questions

- **expected_claims** — 3-5 distinct factual claims the answer must contain. Use complete phrases, not keywords.
- **must_not_contain** — 2-3 terms that are plausible-sounding but incorrect. Think about common misconceptions.
- **weight** — 1 for standard, 2-3 for important, 4 for critical (safety/security related)
- **difficulty** — `easy` (direct recall), `medium` (requires synthesis), `hard` (multi-step reasoning)
- **categories** — mirror the document's structure (e.g., chapters, pillars, sections)
- **expected_sources** — reference specific sections/chapters so coverage analysis works

### Categories for New Datasets

Choose categories that reflect the document's structure:

- **Technical docs**: `basics`, `configuration`, `troubleshooting`, `advanced`, `api_reference`
- **Framework docs**: `getting_started`, `core_concepts`, `guides`, `deployment`, `security`
- **Books**: chapter-based categories or thematic groupings

## Dataset Weights

Weights should reflect question importance:

| Weight | Meaning | Examples |
|---|---|---|
| 1 | Standard | Definition recall, general knowledge |
| 2 | Important | Application of concepts, practical usage |
| 3 | High priority | Multi-step reasoning, edge cases |
| 4 | Critical | Security, safety, correctness constraints |
