from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_comparison_report(
    current_summary: dict,
    current_results: list[dict],
    baseline_summary: dict,
    baseline_results: list[dict],
    output_dir: Path,
) -> Path:
    comp = _compute_comparison(current_summary, baseline_summary)
    comp_dir = output_dir / "comparison"
    comp_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    with open(comp_dir / "comparison.json", "w") as f:
        json.dump(comp, f, indent=2, default=str)

    # CSV
    with open(comp_dir / "comparison.csv", "w", newline="") as f:
        import csv
        writer = csv.writer(f)
        writer.writerow(["Metric", "Baseline", "Current", "Delta"])
        for row in comp.get("metric_deltas", []):
            writer.writerow([row["metric"], row["baseline"], row["current"], row["delta"]])
        writer.writerow(["Avg Latency", comp.get("baseline_latency_ms"), comp.get("current_latency_ms"), comp.get("latency_delta_ms")])

    # HTML
    html = _build_comparison_html(comp, current_summary, baseline_summary)
    with open(comp_dir / "comparison.html", "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Comparison report written to %s", comp_dir)
    return comp_dir


def _compute_comparison(current: dict, baseline: dict) -> dict:
    curr_scores = current.get("ragas_scores", {})
    base_scores = baseline.get("ragas_scores", {})

    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]
    deltas = []
    for key in metrics:
        cv = curr_scores.get(key, 0) or 0
        bv = base_scores.get(key, 0) or 0
        delta = round(cv - bv, 4)
        deltas.append({
            "metric": key,
            "baseline": bv,
            "current": cv,
            "delta": delta,
            "delta_pct": round(delta * 100, 2),
            "regression": delta < -0.03,
        })

    curr_lat = current.get("avg_latency_ms", 0)
    base_lat = baseline.get("avg_latency_ms", 0)

    return {
        "dataset": current.get("dataset", ""),
        "baseline_run": baseline.get("timestamp", ""),
        "current_run": current.get("timestamp", ""),
        "baseline_retriever": baseline.get("retriever", "default"),
        "current_retriever": current.get("retriever", "default"),
        "baseline_latency_ms": base_lat,
        "current_latency_ms": curr_lat,
        "latency_delta_ms": round(curr_lat - base_lat, 2),
        "metric_deltas": deltas,
        "regression_count": sum(1 for d in deltas if d.get("regression")),
        "improved_count": sum(1 for d in deltas if d.get("delta", 0) > 0.01),
    }


def _build_comparison_html(comp: dict, current: dict, baseline: dict) -> str:
    rows = ""
    for d in comp["metric_deltas"]:
        icon = "\u2191" if d["delta"] > 0 else "\u2193" if d["delta"] < 0 else "\u2192"
        color = "#22c55e" if d["delta"] > 0 else "#ef4444" if d["delta"] < 0 else "#94a3b8"
        pct_color = "#ef4444" if d["regression"] else "#22c55e"
        regression_tag = f' <span style="color:{pct_color};font-weight:bold">REGRESSION</span>' if d["regression"] else ""
        rows += f"""<tr>
            <td>{d['metric'].replace('_', ' ').title()}</td>
            <td>{d['baseline']:.2%}</td>
            <td>{d['current']:.2%}</td>
            <td style="color:{color}">{icon} {d['delta']:+.4f}</td>
            <td style="color:{pct_color}">{d['delta_pct']:+.2f}%{regression_tag}</td>
        </tr>"""

    lat_icon = "\u2191" if comp["latency_delta_ms"] > 0 else "\u2193" if comp["latency_delta_ms"] < 0 else "\u2192"
    lat_color = "#ef4444" if comp["latency_delta_ms"] > 0 else "#22c55e" if comp["latency_delta_ms"] < 0 else "#94a3b8"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Comparison Report - {comp['dataset']}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #0f172a; color: #e2e8f0; }}
h1, h2 {{ color: #f1f5f9; }}
.info {{ background: #1e293b; padding: 16px; border-radius: 8px; display: flex; gap: 32px; flex-wrap: wrap; margin: 20px 0; }}
.info-item .label {{ font-size: 0.75em; color: #64748b; text-transform: uppercase; }}
.info-item .value {{ font-size: 1.2em; font-weight: bold; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #334155; }}
th {{ background: #1e293b; }}
.pass {{ background: #052e16; border-left: 4px solid #22c55e; padding: 12px 16px; border-radius: 0 8px 8px 0; }}
.warn {{ background: #451a03; border-left: 4px solid #eab308; padding: 12px 16px; border-radius: 0 8px 8px 0; }}
</style>
</head>
<body>
<h1>Comparison: {comp['baseline_retriever']} vs {comp['current_retriever']}</h1>
<p>Dataset: {comp['dataset']}</p>

<div class="info">
    <div class="info-item">
        <div class="label">Baseline Run</div>
        <div class="value">{comp['baseline_run'][:19]}</div>
    </div>
    <div class="info-item">
        <div class="label">Current Run</div>
        <div class="value">{comp['current_run'][:19]}</div>
    </div>
    <div class="info-item">
        <div class="label">Baseline Retriever</div>
        <div class="value">{comp['baseline_retriever']}</div>
    </div>
    <div class="info-item">
        <div class="label">Current Retriever</div>
        <div class="value">{comp['current_retriever']}</div>
    </div>
</div>

<div class="{'warn' if comp['regression_count'] > 0 else 'pass'}">
    <strong>{'Regressions' if comp['regression_count'] > 0 else 'No Regressions'}:</strong>
    {comp['regression_count']} regression(s), {comp['improved_count']} improvement(s)
</div>

<h2>Metric Deltas</h2>
<table>
<thead><tr><th>Metric</th><th>Baseline</th><th>Current</th><th>Delta</th><th>Delta %</th></tr></thead>
<tbody>{rows}</tbody>
</table>

<h2>Latency</h2>
<table>
<thead><tr><th>Baseline</th><th>Current</th><th>Delta</th></tr></thead>
<tbody>
<tr>
    <td>{comp['baseline_latency_ms']:.0f}ms</td>
    <td>{comp['current_latency_ms']:.0f}ms</td>
    <td style="color:{lat_color}">{lat_icon} {comp['latency_delta_ms']:+.0f}ms</td>
</tr>
</tbody>
</table>

<h2>Summary</h2>
<table>
<tr><td>Total Regressions</td><td>{comp['regression_count']}</td></tr>
<tr><td>Total Improvements</td><td>{comp['improved_count']}</td></tr>
<tr><td>Metrics Checked</td><td>{len(comp['metric_deltas'])}</td></tr>
</table>
</body>
</html>"""
    return html


def find_baseline_run(
    dataset_name: str,
    current_retriever: str,
    reports_dir: Path,
    compare_ref: str = "latest",
    current_timestamp: str = "",
) -> Optional[dict]:
    if compare_ref == "latest":
        ds_dir = reports_dir / dataset_name
        if not ds_dir.exists():
            return None
        runs = sorted(ds_dir.iterdir(), reverse=True)
        for run_dir in runs:
            summary_file = run_dir / "summary.json"
            if not summary_file.exists():
                continue
            with open(summary_file) as f:
                summary = json.load(f)
            ts = summary.get("timestamp", "")
            if ts < current_timestamp:
                return summary
    else:
        found = list(reports_dir.rglob(f"{compare_ref}/summary.json"))
        if found:
            with open(found[0]) as f:
                return json.load(f)
    return None
