import sys, os, json
sys.path.insert(0, ".")
os.chdir(".")

from typer.testing import CliRunner
from app.evaluation.cli import app
from app.evaluation.cli import _generate_pr_summary
from app.evaluation.regression import RegressionDetector

runner = CliRunner()

# 1. Test the PR summary generation directly
print("=== Testing PR Summary Generation ===")

from pathlib import Path
reports_root = Path("reports") / "thinking_fast_and_slow"
runs = sorted(reports_root.iterdir(), reverse=True)
if runs:
    latest_summary = json.load(open(runs[0] / "summary.json"))
    detector = RegressionDetector(baseline_dir="reports")
    gates = detector.check_gates(latest_summary)

    # Find baseline (second-to-last run)
    baseline = None
    if len(runs) >= 2:
        baseline = json.load(open(runs[1] / "summary.json"))

    summary_md = _generate_pr_summary("thinking_fast_and_slow", latest_summary, gates, baseline)
    print(summary_md)
    print()

    # Write to file
    report_path = latest_summary.get("report_path", "")
    if report_path:
        with open(Path(report_path) / "PR_SUMMARY.md", "w") as f:
            f.write(summary_md)
        print(f"PR summary written to {report_path}/PR_SUMMARY.md")

# 2. Test the --ci CLI output with --pr-summary
print()
print("=== Testing --ci CLI Mode ===")
# Run a subset via CLI
result = runner.invoke(app, [
    "benchmark", "thinking_fast_and_slow",
    "--workers", "2",
    "--retriever", "hybrid",
    "--compare", "latest",
    "--ci",
    "--pr-summary",
])
if result.exit_code == 0:
    data = json.loads(result.output)
    print(f"CI status: {data['status']}")
    print(f"Gates: {data['gates']}")
    print(f"Questions: {data['total']}, Passed: {data['successful']}, Failed: {data['failed']}")
    print(f"Weighted pass rate: {data['weighted_pass_rate']}%")
    print(f"Latency: {data['avg_latency_s']}s")
    print(f"PR summary length: {len(data.get('pr_summary', ''))} chars")
    print("CI mode OK")
else:
    print(f"Exit: {result.exit_code}")
    # Try to parse JSON anyway
    try:
        data = json.loads(result.output)
        print(f"Gates: {data.get('gates')}")
    except:
        print(f"Output (first 500): {result.output[:500]}")
