from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_retrieval(results: list[dict]) -> dict:
    successful = [r for r in results if r.get("status") == "success"]
    method_dist = Counter()
    vector_scores = []
    bm25_scores = []
    rrf_scores = []
    reranker_scores = []
    chunk_retrieval_count = Counter()
    source_retrieval_count = Counter()
    source_pairs = []
    query_methods = Counter()

    for r in successful:
        retrieved = r.get("retrieved_chunks", [])
        ranked = r.get("ranked_chunks", [])
        sources_in_run = set()
        methods_in_query = set()

        for c in retrieved:
            provenance = c.get("provenance", {})
            method = provenance.get("retrieval_method", "unknown")
            method_dist[method] += 1
            methods_in_query.add(method)

            if provenance.get("vector_score"):
                vector_scores.append(provenance["vector_score"])
            if provenance.get("bm25_score"):
                bm25_scores.append(provenance["bm25_score"])
            if provenance.get("rrf_score"):
                rrf_scores.append(provenance["rrf_score"])

            chunk_id = c.get("chunk_id", "unknown")
            chunk_retrieval_count[chunk_id] += 1
            sources_in_run.add(c.get("source", "unknown"))

        for rc in ranked:
            provenance = rc.get("provenance", {})
            if provenance.get("reranker_score"):
                reranker_scores.append(provenance["reranker_score"])

        for src in sources_in_run:
            source_retrieval_count[src] += 1
        source_pairs.append(sources_in_run)

        if "both" in methods_in_query:
            query_methods["both"] += 1
        elif "vector" in methods_in_query:
            query_methods["vector_only"] += 1
        elif "bm25" in methods_in_query:
            query_methods["bm25_only"] += 1
        else:
            query_methods["none"] += 1

    total = sum(method_dist.values())
    method_pct = {
        k: round(v / total * 100, 1) if total else 0
        for k, v in sorted(method_dist.items())
    }

    total_sources = len(source_retrieval_count)
    avg_sources = round(len(successful) and sum(len(s) for s in source_pairs) / len(successful), 2) if source_pairs else 0
    most_retrieved = chunk_retrieval_count.most_common(20)

    return {
        "total_queries": len(successful),
        "total_chunk_retrievals": total,
        "retrieval_method_distribution": method_pct,
        "avg_vector_score": round(sum(vector_scores) / len(vector_scores), 4) if vector_scores else 0,
        "avg_bm25_score": round(sum(bm25_scores) / len(bm25_scores), 4) if bm25_scores else 0,
        "avg_rrf_score": round(sum(rrf_scores) / len(rrf_scores), 4) if rrf_scores else 0,
        "avg_reranker_score": round(sum(reranker_scores) / len(reranker_scores), 4) if reranker_scores else 0,
        "most_retrieved_chunks": [
            {"chunk_id": cid, "count": cnt} for cid, cnt in most_retrieved
        ],
        "source_diversity": {
            "total_sources": total_sources,
            "avg_sources_per_query": avg_sources,
            "source_retrieval_frequency": {src: cnt for src, cnt in source_retrieval_count.most_common()},
        },
        "retrieval_method_examples": {
            "vector_only": query_methods.get("vector_only", 0),
            "bm25_only": query_methods.get("bm25_only", 0),
            "both": query_methods.get("both", 0),
            "none": query_methods.get("none", 0),
        },
    }


def analyze_retrieval_coverage(results: list[dict]) -> dict:
    successful = [r for r in results if r.get("status") == "success"]
    if not successful:
        return {"total_queries": 0, "per_document": []}

    doc_total_chunks: dict[str, set[str]] = defaultdict(set)
    chunk_retrieval_count = Counter()
    doc_retrieval_count = Counter()
    page_retrieval: dict[str, Counter] = defaultdict(Counter)
    retrieved_chunk_ids: set[str] = set()

    for r in successful:
        retrieved = r.get("retrieved_chunks", [])
        docs_in_run = set()
        for c in retrieved:
            cid = c.get("chunk_id", "unknown")
            source = c.get("source", "unknown")
            page = c.get("page")
            retrieved_chunk_ids.add(cid)
            chunk_retrieval_count[cid] += 1
            doc_total_chunks[source].add(cid)
            docs_in_run.add(source)
            if page is not None:
                page_retrieval[source][page] += 1

        for src in docs_in_run:
            doc_retrieval_count[src] += 1

    per_document = []
    for doc, chunk_set in doc_total_chunks.items():
        total = len(chunk_set)
        retrieved_count = sum(1 for cid in chunk_set if cid in retrieved_chunk_ids)
        never = total - retrieved_count
        per_document.append({
            "document": doc,
            "total_chunks": total,
            "retrieved_chunks": retrieved_count,
            "never_retrieved": never,
            "coverage_percent": round(retrieved_count / total * 100, 1) if total else 0,
            "retrieval_frequency": doc_retrieval_count.get(doc, 0),
        })

    per_document.sort(key=lambda d: d["coverage_percent"])
    top_retrieved = chunk_retrieval_count.most_common(10)

    total_chunks = sum(d["total_chunks"] for d in per_document)
    total_retrieved = sum(d["retrieved_chunks"] for d in per_document)

    return {
        "total_queries": len(successful),
        "total_chunks_tracked": total_chunks,
        "total_chunks_retrieved": total_retrieved,
        "overall_coverage_percent": round(total_retrieved / max(total_chunks, 1) * 100, 1),
        "per_document": per_document,
        "top_retrieved_chunks": [{"chunk_id": cid, "count": cnt} for cid, cnt in top_retrieved],
        "page_retrieval_heatmap": {doc: dict(pc.most_common(20)) for doc, pc in page_retrieval.items()},
    }


def analyze_retrieval_method_effectiveness(results: list[dict]) -> dict:
    successful = [r for r in results if r.get("status") == "success"]
    if not successful:
        return {"per_method": []}

    method_results: dict[str, list[dict]] = defaultdict(list)

    for r in successful:
        retrieved = r.get("retrieved_chunks", [])
        methods_in_query = set()
        for c in retrieved:
            method = c.get("provenance", {}).get("retrieval_method", "unknown")
            methods_in_query.add(method)

        if "both" in methods_in_query:
            method_results["both"].append(r)
        elif "vector" in methods_in_query:
            method_results["vector_only"].append(r)
        elif "bm25" in methods_in_query:
            method_results["bm25_only"].append(r)
        else:
            method_results["unknown"].append(r)

    per_method = []
    for name in ["vector_only", "bm25_only", "both"]:
        items = method_results.get(name, [])
        if not items:
            continue
        latencies = [r.get("latency_ms", 0) for r in items if r.get("latency_ms")]
        per_method.append({
            "method": name.replace("_", " ").title(),
            "query_count": len(items),
            "query_pct": round(len(items) / len(successful) * 100, 1),
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
            "pass_count": sum(1 for r in items if not r.get("missing_claims") and not r.get("hallucinated_terms")),
            "fail_count": sum(1 for r in items if r.get("missing_claims") or r.get("hallucinated_terms")),
        })

    return {"total_queries": len(successful), "per_method": per_method}


def compute_weighted_scores(results: list[dict]) -> dict:
    successful = [r for r in results if r["status"] == "success"]
    if not successful:
        return {"weighted_pass_rate": 0, "avg_weighted_latency_ms": 0}

    total_weight = sum(r.get("weight", 1) for r in results)
    pass_weight = sum(
        r.get("weight", 1) for r in results
        if r["status"] == "success" and not r.get("missing_claims") and not r.get("hallucinated_terms")
    )
    latency_weighted = sum(r.get("latency_ms", 0) * r.get("weight", 1) for r in successful) / sum(r.get("weight", 1) for r in successful) if successful else 0

    return {
        "total_weight": total_weight,
        "passed_weight": pass_weight,
        "weighted_pass_rate": round(pass_weight / max(total_weight, 1) * 100, 1),
        "avg_weighted_latency_ms": round(latency_weighted, 2),
    }


def generate_analytics_report(results: list[dict], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    analytics = analyze_retrieval(results)
    report_path = output_dir / "retrieval_analytics.json"
    with open(report_path, "w") as f:
        json.dump(analytics, f, indent=2)
    logger.info("Retrieval analytics written to %s", report_path)
    return report_path


def compute_true_corpus_coverage(
    retrieved_results: list[dict],
    corpus_chunks: list[dict],
) -> dict:
    """Compute coverage of the *full* indexed corpus, not just observed chunks.

    corpus_chunks should be the full manifest from the pgvector table
    (via /api/v1/index/corpus).
    """
    if not corpus_chunks:
        return {"corpus_available": False, "note": "Corpus manifest not available"}

    # All chunk IDs in the corpus
    corpus_ids: set[str] = {c["chunk_id"] for c in corpus_chunks}
    total_corpus_chunks = len(corpus_ids)

    # Group corpus by source
    corpus_by_source: dict[str, set[str]] = defaultdict(set)
    for c in corpus_chunks:
        src = c.get("filename") or c.get("source", "unknown")
        corpus_by_source[src].add(c["chunk_id"])

    # Chunks actually retrieved during the benchmark
    retrieved_ids: set[str] = set()
    for r in retrieved_results:
        for c in r.get("retrieved_chunks", []):
            cid = c.get("chunk_id", "")
            if cid:
                retrieved_ids.add(cid)

    # Chunks never retrieved at all
    never_retrieved = corpus_ids - retrieved_ids
    true_coverage = round(len(retrieved_ids) / total_corpus_chunks * 100, 2) if total_corpus_chunks else 0

    # Per-document true coverage
    per_doc = []
    for src, chunk_ids in sorted(corpus_by_source.items()):
        total = len(chunk_ids)
        retrieved = len(chunk_ids & retrieved_ids)
        never = total - retrieved
        per_doc.append({
            "document": src,
            "total_chunks": total,
            "retrieved_chunks": retrieved,
            "never_retrieved": never,
            "coverage_percent": round(retrieved / total * 100, 1) if total else 0,
        })

    per_doc.sort(key=lambda d: d["coverage_percent"])

    return {
        "corpus_available": True,
        "total_corpus_chunks": total_corpus_chunks,
        "total_retrieved_unique": len(retrieved_ids),
        "never_retrieved_count": len(never_retrieved),
        "true_coverage_percent": true_coverage,
        "per_document": per_doc,
        "top_unretrieved": sorted(never_retrieved)[:50],
    }


def generate_coverage_report(
    results: list[dict],
    output_dir: str | Path,
    corpus_chunks: Optional[list[dict]] = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage = analyze_retrieval_coverage(results)

    # If corpus manifest is provided, add true coverage
    if corpus_chunks:
        coverage["true_corpus_coverage"] = compute_true_corpus_coverage(results, corpus_chunks)

    report_path = output_dir / "retrieval_coverage.json"
    with open(report_path, "w") as f:
        json.dump(coverage, f, indent=2)
    logger.info("Retrieval coverage written to %s", report_path)
    return report_path


def generate_effectiveness_report(results: list[dict], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    effectiveness = analyze_retrieval_method_effectiveness(results)
    report_path = output_dir / "method_effectiveness.json"
    with open(report_path, "w") as f:
        json.dump(effectiveness, f, indent=2)
    logger.info("Method effectiveness written to %s", report_path)
    return report_path
