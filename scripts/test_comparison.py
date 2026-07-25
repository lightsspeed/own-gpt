import sys, os, json
from pathlib import Path
sys.path.insert(0, ".")
os.chdir(".")

from app.evaluation.benchmark import run_benchmark
from app.evaluation.reporters.comparison_reporter import generate_comparison_report, find_baseline_run

# Find the most recent baseline (the hybrid run from earlier)
reports_root = Path("reports")
dataset_dir = reports_root / "thinking_fast_and_slow"

# Find latest two runs to use as baseline vs current
runs = sorted(dataset_dir.iterdir(), reverse=True)
if len(runs) >= 2:
    current_run_dir = runs[0]  # most recent
    baseline_run_dir = runs[1]  # second most recent
else:
    print("Need at least 2 runs for comparison")
    sys.exit(1)

baseline_summary = json.load(open(baseline_run_dir / "summary.json"))
current_summary = json.load(open(current_run_dir / "summary.json"))
baseline_results = json.load(open(baseline_run_dir / "results.json"))
current_results = json.load(open(current_run_dir / "results.json"))

print(f"Baseline: {baseline_run_dir.name} (retriever: {baseline_summary.get('retriever', '?')})")
print(f"Current:  {current_run_dir.name} (retriever: {current_summary.get('retriever', '?')})")

generate_comparison_report(
    current_summary, current_results,
    baseline_summary, baseline_results,
    current_run_dir,
)

print(f"Comparison report generated at {current_run_dir / 'comparison' / 'comparison.html'}")
for fn in ["comparison.json", "comparison.csv", "comparison.html"]:
    p = current_run_dir / "comparison" / fn
    print(f"  {'OK' if p.exists() else 'MISSING'}: {fn}")
