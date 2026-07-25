import sys, json
sys.path.insert(0, ".")

from typer.testing import CliRunner
from app.evaluation.cli import app

runner = CliRunner()
result = runner.invoke(app, [
    "benchmark", "thinking_fast_and_slow",
    "--workers", "2",
    "--retriever", "hybrid",
    "--compare", "latest",
    "--ci",
])
if result.exit_code != 0:
    data = json.loads(result.output)
else:
    data = json.loads(result.output)

print("=== CI Output Metadata ===")
for key in ["benchmark_version", "git_commit", "git_branch", "git_dirty",
            "dataset_hash", "python_version", "requirements_hash",
            "embedding_model", "embedding_dimensions", "reranker_model"]:
    print(f"  {key}: {data.get(key, 'MISSING')}")

# Check metadata.json on disk
import glob
runs = sorted(glob.glob("reports/thinking_fast_and_slow/*/"))
latest = runs[-1]
meta = json.load(open(latest + "metadata.json"))
print(f"\n=== metadata.json ({latest}) ===")
for k, v in meta.items():
    print(f"  {k}: {v}")

# Check summary.json has reproducibility block
summary = json.load(open(latest + "summary.json"))
if "reproducibility" in summary:
    print("\n=== summary.json reproducibility block ===")
    for k, v in summary["reproducibility"].items():
        print(f"  {k}: {v}")
else:
    print("\nWARNING: reproducibility block MISSING from summary.json!")
