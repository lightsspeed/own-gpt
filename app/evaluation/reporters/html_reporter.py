from __future__ import annotations

from pathlib import Path

from app.evaluation.loader import BenchmarkDataset


def generate_html_report(summary: dict, results: list[dict], dataset: BenchmarkDataset, run_dir: Path):
    scores = summary.get("ragas_scores", {})
    analytics = summary.get("analytics", {})
    coverage = summary.get("coverage", {})
    effectiveness = summary.get("effectiveness", {})

    rows = ""
    for r in results:
        status_icon = "\u2705" if r["status"] == "success" else "\u274c"
        lat = f"{r.get('latency_ms', 0):.0f}ms" if r["status"] == "success" else "-"
        err = f"<span class='error'>{r.get('error', '')}</span>" if r.get("error") else ""
        missing = r.get("missing_claims", [])
        hallu = r.get("hallucinated_terms", [])
        warnings = ""
        if missing:
            warnings += f"<span class='warn'>missing {len(missing)} claims</span> "
        if hallu:
            warnings += f"<span class='warn'>hallucinated: {', '.join(hallu)}</span> "
        weight = r.get("weight", 1)
        rows += f"""<tr>
            <td>{r.get('id', '')}</td>
            <td>{r.get('category', '')}</td>
            <td>{r.get('difficulty', '')}</td>
            <td>{status_icon}</td>
            <td>{lat}</td>
            <td>{warnings}{err}</td>
        </tr>"""

    ragas_rows = ""
    for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]:
        val = scores.get(key, 0)
        pct = val * 100
        color = "#22c55e" if pct >= 80 else "#eab308" if pct >= 50 else "#ef4444"
        ragas_rows += f"""<div class="metric">
            <span class="metric-label">{key.replace('_', ' ').title()}</span>
            <div class="metric-bar"><div class="metric-fill" style="width:{pct}%;background:{color}"></div></div>
            <span class="metric-value">{pct:.1f}%</span>
        </div>"""

    # Retrieval distribution bars
    method_dist = analytics.get("retrieval_method_distribution", {})
    dist_rows = ""
    for method, pct in sorted(method_dist.items()):
        color = "#3b82f6" if method == "vector" else "#a855f7" if method == "bm25" else "#22c55e"
        dist_rows += f"""<div class="metric">
            <span class="metric-label">{method}</span>
            <div class="metric-bar"><div class="metric-fill" style="width:{pct}%;background:{color}"></div></div>
            <span class="metric-value">{pct}%</span>
        </div>"""

    # Coverage section
    coverage_html = ""
    if coverage:
        docs = coverage.get("per_document", [])
        cov_rows = ""
        for d in docs:
            cov_rows += f"""<tr>
                <td>{d.get('document', 'unknown')[:50]}</td>
                <td>{d.get('total_chunks', 0)}</td>
                <td>{d.get('retrieved_chunks', 0)}</td>
                <td>{d.get('coverage_percent', 0):.1f}%</td>
                <td>{d.get('never_retrieved', 0)}</td>
            </tr>"""
        if cov_rows:
            coverage_html = f"""<h2>Retrieval Coverage</h2>
            <table><thead><tr><th>Document</th><th>Chunks</th><th>Retrieved</th><th>Coverage</th><th>Never Retrieved</th></tr></thead>
            <tbody>{cov_rows}</tbody></table>"""

    # Effectiveness section
    effectiveness_html = ""
    if effectiveness:
        eff_rows = ""
        for method_data in effectiveness.get("per_method", []):
            eff_rows += f"""<tr>
                <td>{method_data.get('method', 'unknown')}</td>
                <td>{method_data.get('query_count', 0)}</td>
                <td>{method_data.get('avg_faithfulness', 0):.2%}</td>
                <td>{method_data.get('avg_relevancy', 0):.2%}</td>
                <td>{method_data.get('avg_latency_ms', 0):.0f}ms</td>
            </tr>"""
        if eff_rows:
            effectiveness_html = f"""<h2>Retrieval Method Effectiveness</h2>
            <table><thead><tr><th>Method</th><th>Queries</th><th>Faithfulness</th><th>Relevancy</th><th>Avg Latency</th></tr></thead>
            <tbody>{eff_rows}</tbody></table>"""

    passed = sum(1 for r in results if r["status"] == "success" and not r.get("missing_claims") and not r.get("hallucinated_terms"))
    failed_q = len(results) - passed

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Benchmark Report - {summary['dataset']}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #0f172a; color: #e2e8f0; }}
h1, h2, h3 {{ color: #f1f5f9; }}
.exec {{ background: #1e293b; border-left: 4px solid #3b82f6; padding: 16px 20px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
.exec h2 {{ margin: 0 0 8px 0; font-size: 1.1em; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
.exec-row {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.exec-item {{ }}
.exec-label {{ font-size: 0.75em; color: #64748b; text-transform: uppercase; }}
.exec-value {{ font-size: 1.6em; font-weight: bold; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
.card {{ background: #1e293b; padding: 16px; border-radius: 8px; text-align: center; }}
.card-value {{ font-size: 2em; font-weight: bold; }}
.metric {{ display: flex; align-items: center; gap: 12px; margin: 12px 0; }}
.metric-label {{ width: 180px; text-transform: capitalize; }}
.metric-bar {{ flex: 1; height: 20px; background: #334155; border-radius: 10px; overflow: hidden; }}
.metric-fill {{ height: 100%; border-radius: 10px; transition: width 0.5s; }}
.metric-value {{ width: 60px; text-align: right; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #334155; }}
th {{ background: #1e293b; position: sticky; top: 0; }}
.error {{ color: #ef4444; font-size: 0.85em; }}
.warn {{ color: #eab308; font-size: 0.85em; }}
.pass {{ color: #22c55e; }}
</style>
</head>
<body>
<h1>Benchmark Report: {summary.get('display_name', summary.get('dataset', 'Unknown'))}</h1>
<p>{dataset.description} &bull; {summary['timestamp'][:10]} &bull; retriever: {summary.get('retriever', 'default')}</p>

<div class="exec">
<h2>Executive Summary</h2>
<div class="exec-row">
    <div class="exec-item">
        <div class="exec-label">Questions</div>
        <div class="exec-value" style="color:#3b82f6">{summary['total']}</div>
    </div>
    <div class="exec-item">
        <div class="exec-label">Passed</div>
        <div class="exec-value" style="color:#22c55e">{passed}</div>
    </div>
    <div class="exec-item">
        <div class="exec-label">Failed</div>
        <div class="exec-value" style="color:#ef4444">{failed_q}</div>
    </div>
    <div class="exec-item">
        <div class="exec-label">Pass Rate</div>
        <div class="exec-value" style="color:#a855f7">{passed / summary['total'] * 100:.0f}%</div>
    </div>
    <div class="exec-item">
        <div class="exec-label">Avg Latency</div>
        <div class="exec-value" style="color:#a855f7">{summary['avg_latency_ms']:.0f}ms</div>
    </div>
    <div class="exec-item">
        <div class="exec-label">Est. Cost</div>
        <div class="exec-value" style="color:#f59e0b">${summary.get('cost', {}).get('estimated_cost_usd', 0):.4f}</div>
    </div>
    <div class="exec-item">
        <div class="exec-label">Total Tokens</div>
        <div class="exec-value" style="color:#f59e0b">{summary.get('cost', {}).get('total_tokens', 0):,}</div>
    </div>
</div>
</div>

{coverage_html}
{effectiveness_html}

<h2>Retrieval Distribution</h2>
{dist_rows}

<h2>Ragas Scores</h2>
{ragas_rows}

<h2>Results</h2>
<table>
<thead><tr><th>ID</th><th>Category</th><th>Difficulty</th><th>Status</th><th>Latency</th><th>Warnings</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""
    with open(run_dir / "report.html", "w", encoding="utf-8") as f:
        f.write(html)
