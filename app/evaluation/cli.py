from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

# Must patch uuid_utils before any langchain import (DLL blocked by AppLocker)
import app.patch_uuid  # noqa: F401

from app.evaluation.engine import EvaluationConfig, EvaluationEngine
from app.evaluation.loader import list_datasets
from app.evaluation.trends import collect_trends, write_trend_report
from app.ingestion.cli import ingest_app

app = typer.Typer(help="RAG evaluation and benchmarking CLI")
app.add_typer(ingest_app, name="ingest", help="Ingest files into the knowledge base")
console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _load_summary(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


@app.command()
def benchmark(
    dataset: str = typer.Argument(..., help="Dataset name (e.g. thinking_fast_and_slow)"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    report: str = typer.Option("reports", "--report", "-r", help="Report output directory"),
    top_failures: int = typer.Option(0, "--top-failures", "-f", help="Show top N failure reasons"),
    max_workers: int = typer.Option(3, "--workers", "-w", help="Max parallel requests"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url", "-u", help="Backend URL"),
    check_regression: bool = typer.Option(False, "--regression", help="Check against previous baseline"),
    export_csv: bool = typer.Option(False, "--export-csv", help="Also export results as CSV to stdout"),
    retriever: str = typer.Option(None, "--retriever", help="Retriever mode: hybrid, vector, or bm25"),
    compare: str = typer.Option(None, "--compare", help="Compare against a specific baseline run name or 'latest'"),
    ci: bool = typer.Option(False, "--ci", help="CI mode: output JSON to stdout, exit 1 on gate failure"),
    pr_summary: bool = typer.Option(False, "--pr-summary", help="Generate PR summary markdown"),
):
    # Build config and run engine
    config = EvaluationConfig(
        dataset=dataset,
        category=category,
        report_dir=report,
        max_workers=max_workers,
        base_url=base_url,
        retriever=retriever,
        compare=compare,
        ci=ci,
        pr_summary=pr_summary,
        top_failures=top_failures,
        export_csv=export_csv,
    )
    engine = EvaluationEngine(config)
    ctx = engine.run()

    # Handle validation errors
    if ctx.error:
        err = {"status": "error", "message": ctx.error}
        if ci:
            console.print(json.dumps(err))
            raise typer.Exit(1)
        console.print(f"[red]{ctx.error}[/]")
        raise typer.Exit(1)

    summary = ctx.summary
    results = ctx.results
    gate_result = ctx.gate_result or {"status": "unknown", "gates_passed": 0, "gates_warned": 0, "gates_failed": 0, "failures": [], "warnings": []}

    # ── CI mode output ────────────────────────────────────────────────────
    if ci:
        ci_output = {
            "status": "completed",
            "dataset": dataset,
            "retriever": summary.get("retriever", "default"),
            "total": summary["total"],
            "successful": summary["successful"],
            "failed": summary["failed"],
            "avg_latency_ms": round(summary["avg_latency_ms"], 2),
            "avg_latency_s": round(summary["avg_latency_ms"] / 1000, 2),
            "weighted_pass_rate": summary.get("weighted_scores", {}).get("weighted_pass_rate", 0),
            "gates": gate_result["status"],
            "gates_passed": gate_result["gates_passed"],
            "gates_warned": gate_result["gates_warned"],
            "gates_failed": gate_result["gates_failed"],
            "failures": [
                {"gate": f["gate"], "metric": f["metric"], "actual": f["actual"], "minimum": f["minimum"]}
                for f in gate_result["failures"]
            ],
            "warnings": [
                {"gate": w["gate"], "metric": w["metric"], "actual": w["actual"], "minimum": w["minimum"]}
                for w in gate_result.get("warnings", [])
            ],
            "report_path": summary.get("report_path", ""),
            "benchmark_version": summary.get("benchmark_version", ""),
            "git_commit": summary.get("reproducibility", {}).get("git_commit", ""),
            "git_branch": summary.get("reproducibility", {}).get("git_branch", ""),
            "git_dirty": summary.get("reproducibility", {}).get("git_dirty", False),
            "dataset_hash": summary.get("reproducibility", {}).get("dataset_hash", ""),
            "python_version": summary.get("reproducibility", {}).get("python_version", ""),
            "requirements_hash": summary.get("reproducibility", {}).get("requirements_hash", ""),
            "embedding_model": summary.get("reproducibility", {}).get("embedding_model", ""),
            "embedding_dimensions": summary.get("reproducibility", {}).get("embedding_dimensions", 0),
            "reranker_model": summary.get("reproducibility", {}).get("reranker_model", ""),
            "cost": summary.get("cost", {}).get("estimated_cost_usd", 0),
            "total_tokens": summary.get("cost", {}).get("total_tokens", 0),
        }

        if pr_summary:
            ci_output["pr_summary"] = _generate_pr_summary(
                dataset, summary, gate_result, ctx.baseline_summary if compare else None
            )

        console.print(json.dumps(ci_output, indent=2, default=str))
        if gate_result["status"] == "fail":
            raise typer.Exit(1)
        return

    # ── Interactive mode output (non-CI) ──────────────────────────────────

    if not ci:
        console.print(f"[bold]Running benchmark:[/] {dataset}")
        if category:
            console.print(f"  Category filter: {category}")
        if retriever:
            console.print(f"  Retriever: {retriever}")
        console.print(f"  Workers: {max_workers}")
        console.print()

    # ── Summary table ───────────────────────────────────────────────────────
    table = Table(title=f"Benchmark Results - {dataset}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total", str(summary["total"]))
    table.add_row("Passed", str(summary["successful"]))
    table.add_row("Failed", str(summary["failed"]))
    table.add_row("Avg Latency", f"{summary['avg_latency_ms']:.0f}ms")

    cost = summary.get("cost", {})
    if cost.get("estimated_cost_usd"):
        table.add_row("Est. Cost", f"${cost['estimated_cost_usd']:.4f}")
        table.add_row("Total Tokens", f"{cost.get('total_tokens', 0):,}")

    scores = summary.get("ragas_scores", {})
    for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]:
        if key in scores:
            val = scores[key]
            if val:
                table.add_row(key.replace("_", " ").title(), f"{val:.2%}")
            else:
                table.add_row(key.replace("_", " ").title(), "[dim]N/A[/]")

    console.print(table)

    # ── Gate pass/fail/warning ──────────────────────────────────────────────
    if gate_result["status"] == "pass":
        console.print("\n[bold green]GATES: PASS[/] All quality thresholds met.")
    elif gate_result["status"] == "warning":
        console.print("\n[bold yellow]GATES: WARNING[/] Some metrics are near thresholds:")
        for w in gate_result.get("warnings", []):
            console.print(f"  [yellow]{w['gate']}[/]: {w['metric']} = {w['actual']} (minimum: {w['minimum']})")
        console.print("  [dim]Warnings do not block merges[/]")
    elif gate_result["status"] == "fail":
        console.print("\n[bold red]GATES: FAIL[/]")
        for f in gate_result["failures"]:
            console.print(f"  [red]{f['gate']}[/]: {f['metric']} = {f['actual']} (minimum: {f['minimum']})")

    # ── Top failures ────────────────────────────────────────────────────────
    if top_failures > 0:
        failures = [r for r in results if r["status"] != "success" or r.get("missing_claims") or r.get("hallucinated_terms")]
        if failures:
            console.print(f"\n[bold red]Top {top_failures} Failures:[/]")
            for f_result in failures[:top_failures]:
                err = f_result.get("error", "")
                missing = f_result.get("missing_claims", [])
                hallu = f_result.get("hallucinated_terms", [])
                parts = []
                if err:
                    parts.append(err)
                if missing:
                    parts.append(f"missing {len(missing)} claims")
                if hallu:
                    parts.append(f"hallucinated: {', '.join(hallu)}")
                console.print(f"  [{f_result['id']}] {'; '.join(parts)}")

    # ── Regression comparison ───────────────────────────────────────────────
    if check_regression:
        regression_result = detector.detect(summary, dataset)
        if regression_result["status"] == "no_baseline":
            console.print("\n[yellow]No baseline found — this run will serve as baseline for future comparisons.[/]")
        elif regression_result["status"] == "regression":
            console.print("\n[bold red]Regressions detected (vs baseline):[/]")
            for r in regression_result["regressions"]:
                console.print(f"  {r['metric']}: {r['baseline']:.4f} \u2192 {r['current']:.4f} ({r['delta']:+.4f})")
        else:
            console.print("\n[green]\u2713 No regressions detected (vs baseline)[/]")

    # ── Export CSV ──────────────────────────────────────────────────────────
    if export_csv:
        import csv as csv_module
        import io
        buf = io.StringIO()
        writer = csv_module.writer(buf)
        writer.writerow(["id", "category", "difficulty", "status", "latency_ms", "missing_claims", "hallucinated_terms", "error"])
        for r in results:
            writer.writerow([
                r.get("id"), r.get("category"), r.get("difficulty"), r.get("status"),
                r.get("latency_ms"), ";".join(r.get("missing_claims", [])),
                ";".join(r.get("hallucinated_terms", [])), r.get("error", ""),
            ])
        console.print(f"\nCSV output:\n{buf.getvalue()}")

    # ── Comparison table ────────────────────────────────────────────────────
    if compare and comparison_table:
        console.print(f"\n[bold]Comparison vs {compare}:[/]")
        console.print(comparison_table)

    # ── Weighted scores ──────────────────────────────────────────────────────
    weighted = summary.get("weighted_scores", {})
    if weighted and weighted.get("total_weight", 0) > 0:
        console.print(f"\n[bold]Weighted Scores:[/]")
        console.print(f"  Pass Rate: {weighted['weighted_pass_rate']}% (weight: {weighted['passed_weight']:.0f}/{weighted['total_weight']:.0f})")
        console.print(f"  Avg Latency: {weighted['avg_weighted_latency_ms']:.0f}ms")

    # ── Report path ─────────────────────────────────────────────────────────
    report_paths = []
    for p in Path(report).rglob("summary.json"):
        report_paths.append(str(p.parent))
    if report_paths:
        latest = sorted(report_paths)[-1]
        console.print(f"\n[bold]Report:[/] {latest}")

        # Show analytics summary if available
        analytics_path = Path(latest) / "analytics" / "retrieval_analytics.json"
        if analytics_path.exists():
            with open(analytics_path) as f:
                analytics = json.load(f)
            method_dist = analytics.get("retrieval_method_distribution", {})
            if method_dist:
                console.print("\n[bold]Retrieval Distribution:[/]")
                for method, pct in sorted(method_dist.items()):
                    console.print(f"  {method}: {pct}%")

        # Show coverage summary if available
        coverage_path = Path(latest) / "analytics" / "retrieval_coverage.json"
        if coverage_path.exists():
            with open(coverage_path) as f:
                coverage = json.load(f)
            if coverage.get("per_document"):
                console.print("\n[bold]Retrieval Coverage:[/]")
                for doc in coverage["per_document"][:3]:
                    console.print(f"  {doc.get('document','?')[:50]}: {doc['coverage_percent']}% ({doc['retrieved_chunks']}/{doc['total_chunks']} chunks)")
                total_coverage = coverage.get("overall_coverage_percent", 0)
                console.print(f"  [italic]Overall: {total_coverage}%[/]")

        # Show method effectiveness if available
        eff_path = Path(latest) / "analytics" / "method_effectiveness.json"
        if eff_path.exists():
            with open(eff_path) as f:
                effectiveness = json.load(f)
            if effectiveness.get("per_method"):
                console.print("\n[bold]Retrieval Method Effectiveness:[/]")
                for m in effectiveness["per_method"]:
                    console.print(f"  {m['method']}: {m['query_count']} queries, {m['pass_count']} pass/{m['fail_count']} fail, {m['avg_latency_ms']}ms")

        # Check for comparison report
        comparison_dir = Path(latest) / "comparison"
        if comparison_dir.exists() and (comparison_dir / "comparison.html").exists():
            console.print(f"\n[bold]Comparison Report:[/] {comparison_dir / 'comparison.html'}")

    console.print("\n[green]Benchmark complete![/]")


def _build_comparison_table(current_summary: dict, dataset_name: str, compare_ref: str) -> Optional[Table]:
    """Build a Rich table comparing current run against a previous baseline."""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return None

    baseline = None
    if compare_ref == "latest":
        ds_dir = reports_dir / dataset_name
        if ds_dir.exists():
            runs = sorted(ds_dir.iterdir(), reverse=True)
            for run_dir in runs:
                summary_file = run_dir / "summary.json"
                if summary_file.exists():
                    summary = _load_summary(summary_file)
                    ts = summary.get("timestamp", "")
                    current_ts = current_summary.get("timestamp", "")
                    if ts < current_ts:
                        baseline = summary
                        break
    else:
        found = list(reports_dir.rglob(f"{compare_ref}/summary.json"))
        if found:
            baseline = _load_summary(found[0])

    if not baseline:
        return None

    current_scores = current_summary.get("ragas_scores", {})
    baseline_scores = baseline.get("ragas_scores", {})

    table = Table(title=f"Comparison: {current_summary.get('dataset', '?')}")
    table.add_column("Metric", style="cyan")
    table.add_column(f"Baseline ({baseline.get('retriever', 'default')})", style="yellow")
    table.add_column(f"Current ({current_summary.get('retriever', 'default')})", style="green")
    table.add_column("Delta", style="blue")

    for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]:
        base_val = baseline_scores.get(key, 0) or 0
        curr_val = current_scores.get(key, 0) or 0
        delta = curr_val - base_val
        delta_str = f"{delta:+.2%}" if delta != 0 else "-"
        table.add_row(
            key.replace("_", " ").title(),
            f"{base_val:.2%}" if base_val else "N/A",
            f"{curr_val:.2%}" if curr_val else "N/A",
            delta_str,
        )

    base_lat = baseline.get("avg_latency_ms", 0)
    curr_lat = current_summary.get("avg_latency_ms", 0)
    lat_delta = curr_lat - base_lat
    table.add_row(
        "Avg Latency",
        f"{base_lat:.0f}ms",
        f"{curr_lat:.0f}ms",
        f"{lat_delta:+.0f}ms" if lat_delta else "-",
    )

    return table


# ── PR summary helper ────────────────────────────────────────────────────

def _generate_pr_summary(dataset: str, summary: dict, gates: dict, baseline: Optional[dict] = None) -> str:
    doc = []
    doc.append(f"## RAG Benchmark Report")
    doc.append(f"")
    doc.append(f"**Dataset:** {dataset}")
    doc.append(f"**Retriever:** {summary.get('retriever', 'default')}")
    doc.append(f"**Questions:** {summary['total']}")
    doc.append(f"")

    passed = summary["successful"]
    total = summary["total"]
    pass_rate = f"{passed / total * 100:.1f}%" if total else "N/A"
    doc.append(f"| Metric | Value |")
    doc.append(f"|--------|-------|")
    doc.append(f"| Total | {total} |")
    doc.append(f"| Passed | {passed} |")
    doc.append(f"| Failed | {summary['failed']} |")
    doc.append(f"| Pass Rate | {pass_rate} |")
    doc.append(f"| Avg Latency | {summary['avg_latency_ms']:.0f}ms |")

    cost = summary.get("cost", {})
    if cost.get("estimated_cost_usd"):
        doc.append(f"| Est. Cost | ${cost['estimated_cost_usd']:.4f} |")
        doc.append(f"| Total Tokens | {cost.get('total_tokens', 0):,} |")

    weighted = summary.get("weighted_scores", {})
    if weighted:
        doc.append(f"| Weighted Pass Rate | {weighted.get('weighted_pass_rate', 0)}% |")

    scores = summary.get("ragas_scores", {})
    for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]:
        val = scores.get(key, 0)
        if val:
            doc.append(f"| {key.replace('_', ' ').title()} | {val:.2%} |")

    doc.append(f"")

    # Gate status
    gate_status = gates["status"]
    if gate_status == "pass":
        doc.append(f"**Gates: PASS**")
    elif gate_status == "warning":
        doc.append(f"**Gates: WARNING**")
        for w in gates.get("warnings", []):
            doc.append(f"- {w['metric']}: {w['actual']} (threshold: {w['minimum']}) - within warning zone")
    elif gate_status == "fail":
        doc.append(f"**Gates: FAIL**")
        for f in gates["failures"]:
            doc.append(f"- {f['metric']}: {f['actual']} (threshold: {f['minimum']})")

    doc.append(f"")

    # Comparison vs baseline
    if baseline:
        base_scores = baseline.get("ragas_scores", {})
        doc.append(f"### Comparison vs Baseline ({baseline.get('retriever', '?')})")
        doc.append(f"")
        doc.append(f"| Metric | Baseline | Current | Delta |")
        doc.append(f"|--------|----------|---------|-------|")
        for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]:
            bv = base_scores.get(key, 0) or 0
            cv = scores.get(key, 0) or 0
            if bv or cv:
                delta = cv - bv
                icon = "+" if delta > 0 else ""
                doc.append(f"| {key.replace('_', ' ').title()} | {bv:.2%} | {cv:.2%} | {icon}{delta:.2%} |")
        bl = baseline.get("avg_latency_ms", 0)
        cl = summary.get("avg_latency_ms", 0)
        lat_delta = cl - bl
        icon = "+" if lat_delta > 0 else ""
        doc.append(f"| Avg Latency | {bl:.0f}ms | {cl:.0f}ms | {icon}{lat_delta:.0f}ms |")
        bc = baseline.get("cost", {}).get("estimated_cost_usd", 0)
        cc = cost.get("estimated_cost_usd", 0)
        if bc and cc:
            cd = cc - bc
            doc.append(f"| Est. Cost | ${bc:.4f} | ${cc:.4f} | ${cd:+.4f} |")

    doc.append(f"")
    doc.append(f"---")
    doc.append(f"_Generated by RAG Benchmark CI_")
    return "\n".join(doc)


@app.command()
def datasets():
    """List available benchmark datasets."""
    available = list_datasets()
    if not available:
        console.print("[yellow]No datasets found.[/]")
        return
    table = Table(title="Available Datasets")
    table.add_column("Name", style="cyan")
    for d in available:
        table.add_row(d)
    console.print(table)


@app.command()
def reports(
    dataset: str = typer.Option(None, "--dataset", "-d", help="Filter by dataset name"),
):
    """List all benchmark report runs."""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        console.print("[yellow]No reports found.[/]")
        return

    table = Table(title="Benchmark Reports")
    table.add_column("Dataset", style="cyan")
    table.add_column("Run", style="green")
    table.add_column("Timestamp", style="white")
    table.add_column("Questions", style="blue")
    table.add_column("Passed", style="green")
    table.add_column("Failed", style="red")

    datasets_found = sorted(d.name for d in reports_dir.iterdir() if d.is_dir())
    for ds_name in datasets_found:
        if dataset and ds_name != dataset:
            continue
        ds_dir = reports_dir / ds_name
        runs = sorted(ds_dir.iterdir(), reverse=True)
        for run_dir in runs:
            summary_file = run_dir / "summary.json"
            if not summary_file.exists():
                continue
            summary = _load_summary(summary_file)
            table.add_row(
                ds_name,
                run_dir.name,
                summary.get("timestamp", "")[:19],
                str(summary.get("total", "")),
                str(summary.get("successful", "")),
                str(summary.get("failed", "")),
            )

    console.print(table)


@app.command()
def report(
    run_ref: str = typer.Argument("latest", help="Run name or 'latest'"),
    dataset: str = typer.Option(None, "--dataset", "-d", help="Dataset name (required if not latest)"),
):
    """Show details of a specific benchmark report run."""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        console.print("[yellow]No reports found.[/]")
        raise typer.Exit(1)

    if run_ref == "latest":
        # Find the most recent run across all datasets
        latest_summary = None
        latest_path = None
        for ds_dir in reports_dir.iterdir():
            if not ds_dir.is_dir():
                continue
            runs = sorted(ds_dir.iterdir(), reverse=True)
            if not runs:
                continue
            candidate = runs[0] / "summary.json"
            if candidate.exists():
                summary = _load_summary(candidate)
                if latest_summary is None or summary.get("timestamp", "") > latest_summary.get("timestamp", ""):
                    latest_summary = summary
                    latest_path = candidate.parent
        if not latest_path:
            console.print("[yellow]No report runs found.[/]")
            raise typer.Exit(1)
    else:
        dataset_dir = reports_dir / (dataset or "")
        run_path = dataset_dir / run_ref
        summary_file = run_path / "summary.json"
        if not summary_file.exists():
            # Try searching across datasets
            found = list(reports_dir.rglob(f"{run_ref}/summary.json"))
            if not found:
                console.print(f"[red]Run '{run_ref}' not found.[/]")
                raise typer.Exit(1)
            summary_file = found[0]
            run_path = summary_file.parent
        latest_summary = _load_summary(summary_file)
        latest_path = run_path

    scores = latest_summary.get("ragas_scores", {})
    table = Table(title=f"Report: {latest_summary.get('dataset', '?')} @ {latest_path.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Run", latest_path.name)
    table.add_row("Dataset", latest_summary.get("dataset", "?"))
    table.add_row("Retriever", latest_summary.get("retriever", "default"))
    table.add_row("Timestamp", latest_summary.get("timestamp", "")[:19])
    table.add_row("Total", str(latest_summary.get("total", "")))
    table.add_row("Passed", str(latest_summary.get("successful", "")))
    table.add_row("Failed", str(latest_summary.get("failed", "")))
    table.add_row("Avg Latency", f"{latest_summary.get('avg_latency_ms', 0):.0f}ms")

    weighted = latest_summary.get("weighted_scores", {})
    if weighted:
        table.add_row("Weighted Pass Rate", f"{weighted.get('weighted_pass_rate', 0)}%")

    for key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]:
        if key in scores:
            val = scores[key]
            table.add_row(key.replace("_", " ").title(), f"{val:.2%}" if val else "[dim]N/A[/]")

    console.print(table)

    # Show coverage summary
    coverage_file = latest_path / "analytics" / "retrieval_coverage.json"
    if coverage_file.exists():
        coverage = json.load(open(coverage_file))
        console.print(f"\n[bold]Coverage:[/] {coverage.get('overall_coverage_percent', 0)}% ({coverage.get('total_chunks_retrieved', 0)}/{coverage.get('total_chunks_tracked', 0)} chunks)")

    # Show effectiveness
    eff_file = latest_path / "analytics" / "method_effectiveness.json"
    if eff_file.exists():
        eff = json.load(open(eff_file))
        if eff.get("per_method"):
            console.print(f"\n[bold]Method Effectiveness:[/]")
            for m in eff["per_method"]:
                console.print(f"  {m['method']}: {m['query_count']} queries ({m['query_pct']}%), pass rate {m['pass_count']}/{m['query_count']}")

    console.print(f"\nFull report: {latest_path / 'report.html'}")


@app.command()
def history(
    dataset: str = typer.Argument(..., help="Dataset name"),
    metric: str = typer.Option("overall", "--metric", "-m", help="Metric to track: faithfulness, overall, latency"),
):
    """Show benchmark trend history for a dataset."""
    reports_dir = Path("reports") / dataset
    if not reports_dir.exists():
        console.print(f"[yellow]No reports found for dataset '{dataset}'.[/]")
        return

    runs = sorted(reports_dir.iterdir(), reverse=True)
    table = Table(title=f"Trend History - {dataset}")
    table.add_column("Run", style="cyan")
    table.add_column("Retriever", style="yellow")
    table.add_column("Pass Rate", style="green")
    table.add_column("Faithfulness", style="green")
    table.add_column("Coverage", style="blue")
    table.add_column("Latency", style="blue")
    table.add_column("Cost", style="magenta")

    for run_dir in runs:
        summary_file = run_dir / "summary.json"
        if not summary_file.exists():
            continue
        summary = _load_summary(summary_file)
        scores = summary.get("ragas_scores", {})
        coverage = summary.get("coverage", {})
        cost = summary.get("cost", {})
        total = summary.get("total", 0)
        passed = summary.get("successful", 0)
        pass_rate = f"{passed / total * 100:.0f}%" if total else "N/A"
        coverage_str = f"{coverage.get('overall_coverage_percent', 0):.0f}%" if coverage else "N/A"
        cost_str = f"${cost.get('estimated_cost_usd', 0):.4f}" if cost.get('estimated_cost_usd') else "N/A"

        table.add_row(
            run_dir.name[:16],
            summary.get("retriever", "default"),
            pass_rate,
            f"{scores.get('faithfulness', 0):.2%}" if scores.get("faithfulness") else "N/A",
            coverage_str,
            f"{summary.get('avg_latency_ms', 0):.0f}ms",
            cost_str,
        )

    console.print(table)


@app.command()
def trends(
    dataset: str = typer.Argument("thinking_fast_and_slow", help="Dataset name"),
    open_browser: bool = typer.Option(False, "--open", "-o", help="Open trend report in browser"),
):
    """Generate or view benchmark trend dashboard."""
    from app.evaluation.trends import collect_trends, generate_trend_html, write_trend_report

    snapshots = collect_trends(dataset)
    if not snapshots:
        console.print(f"[yellow]No historical data for dataset '{dataset}'[/]")
        raise typer.Exit(0)

    # Write to reports root
    path = write_trend_report(dataset)
    if not path:
        console.print(f"[red]Could not generate trend report for '{dataset}'[/]")
        raise typer.Exit(1)

    console.print(f"[green]Trend report: {path}[/]")
    console.print(f"[green]Run snapshots: {len(snapshots)}[/]")

    # Show quick summary table
    table = Table(title=f"Trend Summary — {dataset}")
    table.add_column("Run", style="cyan")
    table.add_column("Pass Rate", style="green")
    table.add_column("Latency", style="blue")
    table.add_column("Weighted Pass", style="magenta")

    for t in snapshots[-5:]:  # Show last 5
        table.add_row(
            t["label"],
            f"{t['pass_rate']}%",
            f"{t.get('avg_latency_ms', '—')}ms",
            f"{t.get('weighted_pass_rate', '—')}%",
        )
    console.print(table)

    if open_browser:
        import webbrowser
        webbrowser.open(str(path))


@app.command()
def index(
    action: str = typer.Argument("status", help="Action: status, rebuild, verify"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url", "-u", help="Backend URL"),
):
    """Manage the Whoosh BM25 search index."""
    import requests as http_requests

    if action == "status":
        try:
            resp = http_requests.get(f"{base_url}/api/v1/index/status", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            table = Table(title="Whoosh Index Status")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Document Count", str(data.get("doc_count", 0)))
            table.add_row("Index Path", data.get("index_path", "N/A"))
            table.add_row("Index Exists", str(data.get("index_exists", False)))
            table.add_row("Last Updated", data.get("last_updated", "N/A"))
            console.print(table)
        except http_requests.ConnectionError:
            console.print(f"[red]Cannot connect to backend at {base_url}[/]")
        except http_requests.RequestException as e:
            console.print(f"[red]Error: {e}[/]")
    elif action == "rebuild":
        try:
            console.print("[yellow]Rebuilding Whoosh index from PGVector...[/]")
            resp = http_requests.post(f"{base_url}/api/v1/index/rebuild", timeout=300)
            resp.raise_for_status()
            data = resp.json()
            console.print(f"[green]Index rebuild complete. Indexed {data.get('count', 0)} documents.[/]")
        except http_requests.ConnectionError:
            console.print(f"[red]Cannot connect to backend at {base_url}[/]")
        except http_requests.RequestException as e:
            console.print(f"[red]Error: {e}[/]")
    elif action == "verify":
        try:
            resp = http_requests.get(f"{base_url}/api/v1/index/status", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            doc_count = data.get("doc_count", 0)
            exists = data.get("index_exists", False)
            if exists and doc_count > 0:
                console.print(f"[green]Index verified: {doc_count} documents, ready for search.[/]")
            elif exists and doc_count == 0:
                console.print("[yellow]Index exists but is empty. Run 'rag index rebuild'.[/]")
            else:
                console.print("[red]Index does not exist. Run 'rag index rebuild'.[/]")
        except http_requests.ConnectionError:
            console.print(f"[red]Cannot connect to backend at {base_url}[/]")
        except http_requests.RequestException as e:
            console.print(f"[red]Error: {e}[/]")
    else:
        console.print(f"[red]Unknown action: {action}. Use: status, rebuild, verify[/]")


@app.command()
def monitor(
    base_url: str = typer.Option("http://localhost:8000", "--base-url", "-u", help="Backend URL"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Live-refresh every 5 seconds"),
):
    """Monitor backend health, index status, and recent benchmarks."""
    import time as _time
    import requests as http_requests
    from datetime import datetime as _datetime

    while True:
        console.clear() if watch else None
        from rich.text import Text as _RichText
        _header = _RichText("==============================\n RAG Platform Monitor\n==============================", style="bold cyan")
        console.print(_header)
        console.print(f"  URL: {base_url}  |  {_datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        console.print()

        # ── 1. Backend health ────────────────────────────────────────────────
        try:
            resp = http_requests.get(f"{base_url}/health", timeout=5)
            if resp.status_code == 200:
                console.print(f"  [green]*[/] Backend      [green]healthy[/]")
            else:
                console.print(f"  [red]*[/] Backend      [red]status={resp.status_code}[/]")
        except http_requests.ConnectionError:
            console.print(f"  [red]*[/] Backend      [red]down[/]")
        except Exception as e:
            console.print(f"  [red]*[/] Backend      [red]{e}[/]")

        # ── 2. Consolidated system status ────────────────────────────────────
        try:
            resp = http_requests.get(f"{base_url}/api/v1/system/status", timeout=10)
            if resp.status_code == 200:
                sys_data = resp.json()
                services = sys_data.get("services", {})

                # Postgres
                pg = services.get("postgres", {})
                pg_status = pg.get("status", "unknown")
                pg_color = "green" if pg_status == "ok" else "red"
                pg_info = pg.get("version", pg_status)
                console.print(f"  [{pg_color}]*[/] PostgreSQL   [{pg_color}]{pg_status}[/]  ({pg_info})")

                # pgvector
                vec = services.get("pgvector", {})
                vec_status = vec.get("status", "unknown")
                vec_color = "green" if vec_status == "ok" else "red"
                chunk_count = vec.get("chunk_count", 0)
                console.print(f"  [{vec_color}]*[/] pgvector     [{vec_color}]{vec_status}[/]  ({chunk_count:,} chunks)")

                # Whoosh
                wh = services.get("whoosh", {})
                wh_status = wh.get("status", "unknown")
                wh_color = "green" if wh_status == "ok" else "yellow" if wh_status == "degraded" else "red"
                doc_count = wh.get("doc_count", 0)
                console.print(f"  [{wh_color}]*[/] Whoosh       [{wh_color}]{wh_status}[/]  ({doc_count:,} docs)")
            else:
                console.print(f"  [yellow]*[/] System       [yellow]unavailable (status={resp.status_code})[/]")
        except http_requests.ConnectionError:
            console.print(f"  [yellow]*[/] System       [yellow]backend unreachable[/]")
        except Exception as e:
            console.print(f"  [yellow]*[/] System       [yellow]{e}[/]")

        # ── 3. Recent benchmarks ─────────────────────────────────────────────
        reports_root = Path("reports")
        if reports_root.exists():
            datasets_found = sorted(reports_root.iterdir())
            if datasets_found:
                console.print()
                console.print("  [bold]Recent Benchmarks:[/]")
                for ds_dir in datasets_found:
                    if ds_dir.is_dir():
                        runs = sorted(ds_dir.iterdir(), reverse=True)
                        if runs:
                            latest_run = runs[0]
                            summary_file = latest_run / "summary.json"
                            if summary_file.exists():
                                try:
                                    s = json.loads(summary_file.read_text())
                                    total = s.get("total", 0)
                                    passed = s.get("successful", 0)
                                    ts = s.get("timestamp", "")[:19]
                                    retriever = s.get("retriever", "default")
                                    cost = s.get("cost", {}).get("estimated_cost_usd", 0)
                                    rate = f"{passed / total * 100:.0f}%" if total else "N/A"
                                    console.print(
                                        f"    [cyan]{ds_dir.name:30}[/] {rate:>5}  "
                                        f"({passed}/{total})  {retriever:>7}  "
                                        f"${cost:.4f}  {ts}"
                                    )
                                except Exception:
                                    pass
            else:
                console.print()
                console.print("  [dim]No benchmark data yet. Run `rag benchmark` first.[/]")
        else:
            console.print()
            console.print("  [dim]No benchmark data yet.[/]")

        # ── 4. Reports directory size ─────────────────────────────────────────
        if reports_root.exists():
            total_size = sum(f.stat().st_size for f in reports_root.rglob("*") if f.is_file())
            if total_size > 1024 * 1024:
                size_str = f"{total_size / 1024 / 1024:.1f} MB"
            elif total_size > 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            else:
                size_str = f"{total_size} B"
            console.print(f"\n  Reports size: {size_str}")

        if not watch:
            break
        _time.sleep(5)


def main():
    app()
