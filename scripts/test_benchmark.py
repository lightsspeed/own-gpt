import sys, os, json
sys.path.insert(0, ".")
os.chdir(".")

from app.evaluation.benchmark import run_benchmark

print("Starting benchmark (75 questions, hybrid)...")
result = run_benchmark(
    "thinking_fast_and_slow",
    base_url="http://localhost:8000",
    max_workers=3,
    report_dir="reports",
    retriever="hybrid",
)

summary = result["summary"]
total = summary["total"]
passed = summary["successful"]
failed = summary["failed"]
latency = summary["avg_latency_ms"]
weighted = summary.get("weighted_scores", {})
coverage = summary.get("coverage", {})
effectiveness = summary.get("effectiveness", {})
rp = summary.get("report_path", "")

print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
print(f"Latency: {latency:.0f}ms, Retriever: {summary['retriever']}")

if weighted:
    print(f"Weighted pass rate: {weighted['weighted_pass_rate']}%")

if coverage:
    print(f"Coverage: {coverage.get('overall_coverage_percent', 0)}% "
          f"({coverage.get('total_chunks_retrieved', 0)}/{coverage.get('total_chunks_tracked', 0)})")

if effectiveness:
    for m in effectiveness.get("per_method", []):
        print(f"  Method {m['method']}: {m['query_count']} queries, "
              f"{m['pass_count']}/{m['fail_count']} pass/fail, {m['avg_latency_ms']}ms")

if rp:
    print(f"Report: {rp}")
    for fn in [
        "report.html", "summary.json", "results.json", "results.csv", "metadata.json",
        "analytics/retrieval_analytics.json", "analytics/retrieval_coverage.json",
        "analytics/method_effectiveness.json",
    ]:
        p = os.path.join(rp, fn)
        print(f"  {'OK' if os.path.exists(p) else 'MISSING'}: {fn}")
