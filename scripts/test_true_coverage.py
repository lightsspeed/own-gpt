import subprocess, time, requests, sys, json
from pathlib import Path

# Start backend
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

try:
    for i in range(12):
        time.sleep(2)
        try:
            r = requests.get("http://localhost:8000/docs", timeout=3)
            if r.status_code == 200:
                break
        except:
            continue
    else:
        print("Backend failed")
        sys.exit(1)

    # Run benchmark with --ci to get full output including true coverage
    from typer.testing import CliRunner
    sys.path.insert(0, ".")
    from app.evaluation.cli import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, [
        "benchmark", "thinking_fast_and_slow",
        "--workers", "2",
        "--retriever", "hybrid",
        "--ci",
    ])

    if result.exit_code != 0:
        try:
            data = json.loads(result.output)
        except:
            print(f"Benchmark output (exit={result.exit_code}):")
            print(result.output[:1000])
            sys.exit(1)
    else:
        data = json.loads(result.output)

    print(f"Status: {data['status']}")
    print(f"Total: {data['total']}, Passed: {data['successful']}, Failed: {data['failed']}")

    # Check coverage in latest report
    report_path = data.get("report_path", "")
    if report_path:
        coverage_file = Path(report_path) / "analytics" / "retrieval_coverage.json"
        if coverage_file.exists():
            coverage = json.loads(coverage_file.read_text())
            print(f"\n=== Coverage Analysis ===")
            print(f"Total chunks tracked (retrieved): {coverage.get('total_chunks_tracked', 'N/A')}")
            print(f"Total chunks retrieved: {coverage.get('total_chunks_retrieved', 'N/A')}")
            print(f"Overall coverage % (retrieved): {coverage.get('overall_coverage_percent', 'N/A')}")

            true_cov = coverage.get("true_corpus_coverage", {})
            if true_cov:
                print(f"\n=== TRUE Corpus Coverage ===")
                print(f"Corpus available: {true_cov.get('corpus_available')}")
                print(f"Total corpus chunks: {true_cov.get('total_corpus_chunks')}")
                print(f"Unique retrieved: {true_cov.get('total_retrieved_unique')}")
                print(f"Never retrieved: {true_cov.get('never_retrieved_count')}")
                print(f"True coverage %: {true_cov.get('true_coverage_percent')}%")
                for doc in true_cov.get("per_document", []):
                    print(f"  {doc['document'][:50]}: {doc['coverage_percent']}% ({doc['retrieved_chunks']}/{doc['total_chunks']})")
            else:
                print("\nNo true corpus coverage data")
        else:
            print(f"Coverage file not found at {coverage_file}")
    else:
        print("No report_path in output")

finally:
    proc.terminate()
    proc.wait(timeout=10)
