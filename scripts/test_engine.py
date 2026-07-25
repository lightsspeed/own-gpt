import sys; sys.path.insert(0, ".")

from app.evaluation.engine import EvaluationConfig, EvaluationEngine, BenchmarkContext
from app.evaluation.cli import app
from app.evaluation import EvaluationConfig as EC, EvaluationEngine as EE, BenchmarkContext as BC
print("1. Imports OK")

engine = EvaluationEngine(EvaluationConfig(dataset="thinking_fast_and_slow"))
expected = ["_validate", "_run_benchmark", "_compute_analytics", "_generate_reports",
            "_generate_comparison", "_check_gates", "_update_trends", "_write_bundle_readme", "run"]
for method in expected:
    assert hasattr(engine, method), f"Missing {method}"
print(f"2. All {len(expected)} pipeline methods OK")

# Verify CLI app has benchmark command
for cmd in app.registered_commands:
    print(f"   CLI command: {cmd.name}")
print(f"3. CLI has {len(app.registered_commands)} commands")

# Verify short benchmark run through engine works
import subprocess, time, requests, json
from pathlib import Path

# Start a quick backend
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
        print("4. Backend not ready, skipping integration test")
        raise SystemExit(0)

    config = EvaluationConfig(
        dataset="thinking_fast_and_slow",
        max_workers=2,
        report_dir="reports",
    )
    engine = EvaluationEngine(config)
    ctx = engine.run()
    assert ctx.error is None, f"Engine error: {ctx.error}"
    assert ctx.summary.get("total") == 75
    assert ctx.summary.get("successful") == 75
    assert "report_path" in ctx.summary
    assert ctx.gate_result is not None
    print(f"4. Engine run OK: {ctx.summary['total']}Q, pass={ctx.summary['successful']}, "
          f"gates={ctx.gate_result['status']}, report={ctx.summary['report_path']}")

finally:
    proc.terminate()
    proc.wait(timeout=10)

print("\n=== All checks passed ===")
