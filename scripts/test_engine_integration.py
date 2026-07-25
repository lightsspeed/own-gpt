import subprocess, time, requests, sys, json
sys.path.insert(0, ".")
from pathlib import Path

# Start backend
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
try:
    for i in range(10):
        time.sleep(2)
        try:
            requests.get("http://localhost:8000/docs", timeout=3)
            break
        except:
            continue
    else:
        print("Backend not ready")
        raise SystemExit(1)

    # Run via engine directly
    from app.evaluation.engine import EvaluationConfig, EvaluationEngine
    config = EvaluationConfig(
        dataset="thinking_fast_and_slow",
        max_workers=2,
        report_dir="reports",
    )
    engine = EvaluationEngine(config)
    ctx = engine.run()

    if ctx.error:
        print(f"Engine error: {ctx.error}")
        raise SystemExit(1)

    s = ctx.summary
    print(f"Questions: {s['total']}")
    print(f"Passed: {s['successful']}")
    print(f"Failed: {s['failed']}")
    print(f"Latency: {s['avg_latency_ms']:.0f}ms")
    print(f"Weighted pass rate: {s.get('weighted_scores', {}).get('weighted_pass_rate', '?')}%")
    print(f"Report: {s.get('report_path', 'N/A')}")
    print(f"Gates: {ctx.gate_result['status'] if ctx.gate_result else 'N/A'}")

    # Verify artifacts exist
    rp = Path(s["report_path"])
    expected = ["summary.json", "results.json", "results.csv", "report.html", "metadata.json",
                "README.md", "analytics/retrieval_coverage.json", "trends.html"]
    for f in expected:
        assert (rp / f).exists(), f"Missing {f}"
        print(f"  OK: {f}")

    print("\n=== Engine integration OK ===")

finally:
    proc.terminate()
    proc.wait(timeout=10)
