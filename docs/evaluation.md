# Evaluation Methodology

## How Benchmark Questions Work

Each question in a dataset is a JSON object with these fields:

```json
{
  "id": "sys1-01",
  "category": "system_1_2",
  "difficulty": "easy",
  "question": "What are the two systems in Kahneman's framework?",
  "expected_claims": [
    "System 1 operates automatically and quickly",
    "System 2 allocates attention to effortful mental activities"
  ],
  "must_not_contain": [
    "unconscious bias",
    "personality trait"
  ],
  "expected_sources": [
    "Chapter 1: The Characters of the Story"
  ],
  "weight": 2
}
```

- **expected_claims** — claims the generated answer MUST contain (pass condition)
- **must_not_contain** — terms/phrases that indicate hallucination (fail condition)
- **expected_sources** — which document sources should contain the answer (for source diversity analysis)
- **weight** — importance of the question (1-4) for weighted scoring

## Pass/Fail Logic

A question **passes** if:

1. The API returns a 200 status (no timeout or error)
2. ALL expected_claims are present in the answer (checked via word overlap on first 5 words of each claim)
3. NO must_not_contain terms appear in the answer

A question **fails** if any of these conditions is violated.

## Scoring

### Pass Rate

```
pass_rate = successful_questions / total_questions
```

### Weighted Pass Rate

Each question carries a weight (1-4). Weighted pass rate accounts for importance:

```
weighted_pass_rate = sum(weight of passed questions) / sum(weight of all questions)
```

This ensures that high-importance questions count more than low-importance ones.

### RAGAS Scores

If the `ragas` package is installed, the benchmark computes four RAGAS metrics:

| Metric | Range | What it measures |
|---|---|---|
| Faithfulness | 0-1 | Is the answer factually grounded in the retrieved context? |
| Answer Relevancy | 0-1 | Does the answer actually address the question? |
| Context Precision | 0-1 | Are the retrieved chunks relevant to the question? |
| Context Recall | 0-1 | Do the retrieved chunks cover all needed information? |

These are computed by the `RagasRunner` class, which requires `pip install ragas`.

### Latency

Average end-to-end latency per question, measured in milliseconds. Includes all pipeline stages (retrieval, reranking, LLM generation, validation).

## Retrieval Analytics

### Method Distribution

Each retrieved chunk carries provenance metadata indicating whether it came from vector search, BM25 search, or both (after RRF fusion). The analytics module tracks:

- Percentage of chunks from each method
- Average similarity scores per method
- Query-level distribution (vector-only, BM25-only, hybrid, none)

### Retrieval Coverage

**Retrieved Coverage** — tracks which chunks appear in at least one retrieval across all benchmark questions. Measures whether the benchmark exercises diverse parts of the document.

**True Corpus Coverage** — compares retrieved chunk IDs against the full indexed corpus (from PGVector). Reveals chunks that are NEVER retrieved by any query — the "cold corners" of the corpus.

### Method Effectiveness

Groups queries by retrieval method (vector-only, BM25-only, hybrid) and compares:
- Query count and percentage
- Average latency
- Pass/fail counts

This helps determine whether hybrid retrieval is genuinely better than either method alone.

## Weighted Scoring

Questions carry weights from 1 (standard) to 4 (critical). The weighted score prevents the pass rate from being dominated by easy or low-importance questions.

Weighted pass rate is the primary quality metric in CI/CD gate evaluation.
