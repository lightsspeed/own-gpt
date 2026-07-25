from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TREND_METRICS = [
    "avg_latency_ms",
    "weighted_pass_rate",
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "overall",
    "estimated_cost_usd",
]


def collect_trends(
    dataset: str,
    reports_root: str = "reports",
    metric_names: Optional[list[str]] = None,
) -> list[dict]:
    """Read all historical summary.json files for a dataset and return
    a time-ordered list of trend snapshots."""
    root = Path(reports_root) / dataset
    if not root.exists():
        logger.warning("No reports found for dataset '%s' at %s", dataset, root)
        return []

    metrics = metric_names or TREND_METRICS
    snapshots = []

    for run_dir in sorted(root.iterdir()):
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue

        try:
            summary = json.loads(summary_path.read_text())
        except Exception as e:
            logger.warning("Failed to read %s: %s", summary_path, e)
            continue

        ts = summary.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            label = dt.strftime("%m-%d %H:%M")
        except Exception:
            label = run_dir.name

        snapshot = {
            "run_dir": run_dir.name,
            "timestamp": ts,
            "label": label,
            "total": summary.get("total", 0),
            "successful": summary.get("successful", 0),
            "failed": summary.get("failed", 0),
            "pass_rate": round(summary["successful"] / summary["total"] * 100, 1)
            if summary.get("total")
            else 0,
        }

        for metric in metrics:
            if metric in ("weighted_pass_rate",):
                weighted = summary.get("weighted_scores", {})
                snapshot[metric] = weighted.get("weighted_pass_rate", None)
            elif metric in ("faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"):
                ragas = summary.get("ragas_scores", {})
                val = ragas.get(metric, None)
                if val is not None and isinstance(val, (int, float)) and val <= 1:
                    snapshot[metric] = round(val * 100, 1)
                else:
                    snapshot[metric] = val
            elif metric == "estimated_cost_usd":
                cost = summary.get("cost", {})
                snapshot[metric] = cost.get("estimated_cost_usd", None)
            else:
                snapshot[metric] = summary.get(metric, None)

        snapshots.append(snapshot)

    return snapshots


def generate_trend_html(trends: list[dict], dataset: str) -> str:
    """Generate a standalone HTML page with trend charts using Chart.js."""
    if not trends:
        return "<p>No trend data available.</p>"

    labels = json.dumps([t["label"] for t in trends])

    chart_datasets = []
    for metric in TREND_METRICS:
        values = [t.get(metric) for t in trends]
        # Skip metrics with no data
        if all(v is None for v in values):
            continue
        safe_vals = [v if v is not None else None for v in values]
        chart_datasets.append({
            "label": metric.replace("_", " ").title(),
            "data": safe_vals,
            "borderWidth": 2,
            "fill": False,
            "spanGaps": False,
        })

    datasets_json = json.dumps(chart_datasets)

    # Build the summary table
    last = trends[-1]
    first = trends[0] if len(trends) > 1 else None
    delta_rows = ""
    if first:
        for metric in TREND_METRICS:
            curr = last.get(metric)
            prev = first.get(metric)
            if curr is not None and prev is not None and prev != 0:
                delta = curr - prev
                arrow = "▲" if delta > 0 else "▼" if delta < 0 else "—"
                delta_rows += f"""
                <tr>
                    <td>{metric.replace('_', ' ').title()}</td>
                    <td>{prev}</td>
                    <td>{curr}</td>
                    <td class="{'positive' if delta > 0 else 'negative' if delta < 0 else ''}">{arrow} {delta:+.1f}</td>
                </tr>
                """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Benchmark Trends — {dataset}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; background: #f5f5f5; }}
h1 {{ color: #333; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.chart-box {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; }}
.positive {{ color: #22c55e; }}
.negative {{ color: #ef4444; }}
.summary {{ background: #fff; border-radius: 8px; padding: 1rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
.stat {{ text-align: center; }}
.stat-value {{ font-size: 2rem; font-weight: 700; color: #333; }}
.stat-label {{ font-size: 0.875rem; color: #666; }}
</style>
</head>
<body>
<div class="container">
<h1>Benchmark Trends — {dataset}</h1>
<p><strong>{len(trends)}</strong> historical runs | Latest: <strong>{last['label']}</strong></p>

<div class="summary">
<div class="summary-grid">
    <div class="stat">
        <div class="stat-value">{last.get('pass_rate', '—')}%</div>
        <div class="stat-label">Pass Rate</div>
    </div>
    <div class="stat">
        <div class="stat-value">{last.get('avg_latency_ms', '—')}ms</div>
        <div class="stat-label">Avg Latency</div>
    </div>
    <div class="stat">
        <div class="stat-value">{last.get('weighted_pass_rate', '—')}%</div>
        <div class="stat-label">Weighted Pass Rate</div>
    </div>
    <div class="stat">
        <div class="stat-value">{last.get('overall', '—')}</div>
        <div class="stat-label">Overall RAGAS</div>
    </div>
    <div class="stat">
        <div class="stat-value">${last.get('estimated_cost_usd', '—')}</div>
        <div class="stat-label">Est. Cost (USD)</div>
    </div>
</div>
</div>

<div class="chart-box">
    <canvas id="trendChart"></canvas>
</div>

<h2>Metric Trends</h2>
<table>
    <thead>
        <tr>
            <th>Metric</th>
            <th>First Run</th>
            <th>Latest Run</th>
            <th>Delta</th>
        </tr>
    </thead>
    <tbody>
        {delta_rows}
    </tbody>
</table>

<h2>All Snapshots</h2>
<table>
    <thead>
        <tr>
            <th>Run</th>
            <th>Timestamp</th>
            <th>Total</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Pass Rate</th>
            <th>Latency (ms)</th>
            <th>Weighted Pass</th>
            <th>Cost (USD)</th>
        </tr>
    </thead>
    <tbody>
"""
    for t in trends:
        cost_val = t.get('estimated_cost_usd')
        cost_str = f"${cost_val:.4f}" if cost_val is not None else "—"
        html += f"""
        <tr>
            <td>{t['run_dir']}</td>
            <td>{t.get('timestamp', '')[:19]}</td>
            <td>{t['total']}</td>
            <td>{t['successful']}</td>
            <td>{t['failed']}</td>
            <td>{t['pass_rate']}%</td>
            <td>{t.get('avg_latency_ms', '—')}</td>
            <td>{t.get('weighted_pass_rate', '—')}%</td>
            <td>{cost_str}</td>
        </tr>
        """

    html += """
    </tbody>
</table>
</div>

<script>
const ctx = document.getElementById('trendChart').getContext('2d');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: LABELS_PLACEHOLDER,
        datasets: DATASETS_PLACEHOLDER,
    },
    options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { position: 'bottom' },
            title: { display: true, text: 'Benchmark Metrics Over Time' }
        },
        scales: {
            y: {
                beginAtZero: false,
            }
        }
    }
});
</script>
</body>
</html>
"""
    html = html.replace("LABELS_PLACEHOLDER", labels)
    html = html.replace("DATASETS_PLACEHOLDER", json.dumps(chart_datasets))
    return html


def write_trend_report(
    dataset: str,
    reports_root: str = "reports",
    output_dir: Optional[str] = None,
) -> Optional[Path]:
    trends = collect_trends(dataset, reports_root)
    if not trends:
        logger.warning("No trend data for dataset '%s'", dataset)
        return None

    html = generate_trend_html(trends, dataset)

    if output_dir:
        dest = Path(output_dir) / "trends.html"
    else:
        root = Path(reports_root) / dataset
        dest = root / "trends.html"

    dest.write_text(html, encoding="utf-8")
    logger.info("Trend report written to %s", dest)
    return dest
