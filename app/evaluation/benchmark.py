from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from app.evaluation.loader import BenchmarkQuestion, load_dataset, list_datasets
from app.evaluation.metrics import EvaluationMetrics, compute_retrieval_metrics
from app.evaluation.ragas_runner import RagasRunner
from app.evaluation.analytics import compute_weighted_scores
from app.evaluation.reproducibility import collect_metadata

# OpenAI pricing per 1K tokens (as of July 2026)
COST_PER_1K_INPUT = 0.150    # gpt-4o-mini
COST_PER_1K_OUTPUT = 0.600   # gpt-4o-mini
COST_PER_1K_EMBEDDING = 0.020  # text-embedding-3-small

logger = logging.getLogger(__name__)


def _query_chat_api(question: str, base_url: str = "http://localhost:8000", retriever: Optional[str] = None) -> dict:
    url = f"{base_url}/api/v1/chat/evaluate"
    payload = {"message": question}
    if retriever:
        payload["retriever"] = retriever
    start = time.perf_counter()

    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    elapsed = time.perf_counter() - start
    answer = data.get("answer", "")
    latencies = data.get("latencies", {})

    # Build context list for ragas evaluation
    reranked = data.get("reranked_chunks", [])
    contexts = [c.get("content", "") for c in reranked]
    retrieved = data.get("retrieved_chunks", [])

    # Build chunks_by_source for analytics
    chunks_by_source = {}
    for rc in retrieved:
        src = rc.get("source", "unknown")
        if src not in chunks_by_source:
            chunks_by_source[src] = []
        chunks_by_source[src].append({
            "chunk_id": rc.get("chunk_id", ""),
            "score": rc.get("score", 0),
        })

    # Extract token usage from trace
    trace = data.get("trace", {})
    prompt_tokens = trace.get("prompt_tokens", 0) or 0
    completion_tokens = trace.get("completion_tokens", 0) or 0

    # Estimate embedding tokens from context
    embedding_tokens = sum(len(t.split()) * 1.3 for t in contexts) if contexts else 0
    embedding_tokens = int(embedding_tokens)

    # Compute estimated cost
    cost = (
        prompt_tokens / 1000 * COST_PER_1K_INPUT
        + completion_tokens / 1000 * COST_PER_1K_OUTPUT
        + embedding_tokens / 1000 * COST_PER_1K_EMBEDDING
    )

    return {
        "answer": answer,
        "contexts": contexts,
        "latency_ms": round(elapsed * 1000, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "embedding_tokens": embedding_tokens,
        "estimated_cost_usd": round(cost, 6),
        "trace_info": {
            "latencies": latencies,
            "chunk_ids": [c.get("chunk_id", "") for c in retrieved],
        },
        "retrieved_chunks": retrieved,
        "ranked_chunks": reranked,
        "context_text": data.get("context", ""),
        "chunks_by_source": chunks_by_source,
    }


def _run_single_question(
    question: BenchmarkQuestion,
    base_url: str,
    timeout: int,
    retriever: Optional[str] = None,
) -> dict:
    result = {
        "id": question.id,
        "category": question.category,
        "difficulty": question.difficulty,
        "question": question.question,
        "expected_claims": question.expected_claims,
        "must_not_contain": question.must_not_contain,
        "expected_sources": question.expected_sources,
        "weight": getattr(question, "weight", 1),
        "priority": getattr(question, "priority", "normal"),
        "status": "error",
        "error": None,
        "retrieved_chunks": [],
        "ranked_chunks": [],
        "context_text": "",
        "missing_claims": [],
        "hallucinated_terms": [],
    }
    try:
        resp = _query_chat_api(question.question, base_url, retriever=retriever)
        result.update(resp)
        result["status"] = "success"

        # Detect missing expected claims
        answer_lower = result.get("answer", "").lower()
        missing = []
        for claim in question.expected_claims:
            if not any(word in answer_lower for word in claim.lower().split()[:5]):
                missing.append(claim)
        result["missing_claims"] = missing

        # Detect hallucinated terms (must_not_contain)
        hallucinated = []
        for term in question.must_not_contain:
            if term.lower() in answer_lower:
                hallucinated.append(term)
        result["hallucinated_terms"] = hallucinated
    except requests.Timeout:
        result["error"] = f"Timeout after {timeout}s"
    except requests.RequestException as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
    return result


def run_benchmark_subset(
    questions: list[BenchmarkQuestion],
    base_url: str = "http://localhost:8000",
    timeout: int = 120,
) -> list[dict]:
    """Run a bounded subset of benchmark questions sequentially.

    Lightweight public entry used by the automation scheduler for periodic
    regression checks — no ragas scoring, no reports. Returns raw per-question
    results for the caller to aggregate and compare against baselines.
    """
    results = []
    for q in questions:
        try:
            results.append(_run_single_question(q, base_url, timeout))
        except Exception as e:  # noqa: BLE001
            results.append({
                "id": q.id,
                "category": q.category,
                "difficulty": q.difficulty,
                "question": q.question,
                "status": "error",
                "error": f"Unexpected error: {e}",
            })
    return results


def run_benchmark(
    dataset_name: str,
    base_url: str = "http://localhost:8000",
    category: Optional[str] = None,
    max_workers: int = 3,
    timeout: int = 120,
    report_dir: Optional[str] = None,
    retriever: Optional[str] = None,
) -> dict:
    dataset = load_dataset(dataset_name)
    questions = dataset.by_category(category) if category else dataset.questions
    logger.info("Running benchmark '%s' with %d questions", dataset_name, len(questions))

    if not questions:
        return {"dataset": dataset_name, "status": "no_questions", "results": []}

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_single_question, q, base_url, timeout, retriever): q
            for q in questions
        }
        for future in as_completed(futures):
            q = futures[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(
                    "Q[%s] %s | status=%s latency=%.0fms",
                    q.id, q.category, result["status"], result.get("latency_ms", 0),
                )
            except Exception as e:
                logger.error("Q[%s] unexpected failure: %s", q.id, e)
                results.append({
                    "id": q.id,
                    "category": q.category,
                    "difficulty": q.difficulty,
                    "question": q.question,
                    "status": "error",
                    "error": str(e),
                })

    results.sort(key=lambda r: (r.get("category", ""), r.get("id", "")))

    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    logger.info("Benchmark complete: %d/%d successful", len(successful), len(results))

    if successful:
        ragas_runner = RagasRunner()
        ragas_scores = ragas_runner.evaluate(
            questions=[r["question"] for r in successful],
            answers=[r["answer"] for r in successful],
            contexts=[r["contexts"] for r in successful],
        )
    else:
        ragas_scores = {}

    # Aggregate cost metrics
    total_prompt = sum(r.get("prompt_tokens", 0) for r in successful)
    total_completion = sum(r.get("completion_tokens", 0) for r in successful)
    total_embedding = sum(r.get("embedding_tokens", 0) for r in successful)
    total_cost = sum(r.get("estimated_cost_usd", 0) for r in successful)

    summary = {
        "dataset": dataset_name,
        "display_name": dataset.display_name,
        "timestamp": datetime.utcnow().isoformat(),
        "benchmark_version": "2.0.0",
        "total": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "category": category or "all",
        "retriever": retriever or "default",
        "config": {"base_url": base_url, "max_workers": max_workers, "timeout": timeout},
        "ragas_scores": ragas_scores,
        "avg_latency_ms": round(
            sum(r.get("latency_ms", 0) for r in successful) / len(successful), 2
        ) if successful else 0,
        "cost": {
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_embedding_tokens": total_embedding,
            "total_tokens": total_prompt + total_completion + total_embedding,
            "avg_prompt_tokens": round(total_prompt / len(successful), 1) if successful else 0,
            "avg_completion_tokens": round(total_completion / len(successful), 1) if successful else 0,
            "estimated_cost_usd": round(total_cost, 4),
            "avg_cost_per_question": round(total_cost / len(successful), 6) if successful else 0,
            "cost_per_1k_input": COST_PER_1K_INPUT,
            "cost_per_1k_output": COST_PER_1K_OUTPUT,
            "cost_per_1k_embedding": COST_PER_1K_EMBEDDING,
        },
    }

    # Attach reproducibility metadata to summary
    summary["reproducibility"] = collect_metadata(
        dataset_name=dataset_name,
        retriever_mode=retriever or "default",
    )

    # Weighted scores (computed here since purely data-derived)
    summary["weighted_scores"] = compute_weighted_scores(results)

    return {"summary": summary, "results": results}
