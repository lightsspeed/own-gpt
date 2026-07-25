"""
CLI display for analytics reports. Pretty-prints to stdout.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from .engine import AnalyticsEngine, AnalyticsReport

logger = logging.getLogger(__name__)


def display_report(report: AnalyticsReport, json_output: bool = False) -> None:
    """Print an analytics report to stdout."""
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return

    _print_header("Analytics Report")
    print(f"  Generated: {report.generated_at}")
    print(f"  Records:   {report.total_records}")
    print(f"  Events:    {report.total_events}")
    print()

    if report.query:
        _print_section("Query Intelligence")
        if report.query.top_queries:
            print("  Top Questions:")
            for i, q in enumerate(report.query.top_queries[:10], 1):
                sample = q.get("sample", "")[:72]
                print(f"    {i:2d}. [{q['count']:3d}x] {sample}")
                print(f"        confidence={q.get('avg_confidence', 'N/A')}  accept={q.get('accept_rate', 'N/A')}")
        if report.query.knowledge_gaps:
            print(f"\n  Knowledge Gaps ({len(report.query.knowledge_gaps)}):")
            for gap in report.query.knowledge_gaps[:10]:
                print(f"    - \"{gap.get('sample', '')[:60]}\" ({gap['count']}x, conf={gap.get('avg_confidence', 'N/A')})")
        if report.query.most_failed:
            print(f"\n  Most Failed:")
            for f in report.query.most_failed[:5]:
                print(f"    - \"{f.get('sample', '')[:60]}\" ({f['failures']} failures / {f['total']} total)")
        print()

    if report.routing:
        _print_section("Routing Analytics")
        print(f"  Intent distribution: {dict(sorted(report.routing.intent_distribution.items(), key=lambda x: -x[1])[:10])}")
        print(f"  Rule vs LLM: {report.routing.rule_vs_llm_rate}")
        print()

    if report.retrieval:
        _print_section("Retrieval Intelligence")
        print(f"  Chunk quality: {report.retrieval.chunk_quality}")
        if report.retrieval.top_documents:
            print("  Top documents:")
            for d in report.retrieval.top_documents[:5]:
                print(f"    - {d.get('document', '')[:60]} (retrieved {d['retrieved_count']}x, conf={d.get('avg_confidence', 'N/A')})")
        print()

    if report.behavior:
        _print_section("User Behavior")
        s = report.behavior.summary
        print(f"  Events: {s.get('total_events', 0)} ({s.get('events_per_record', 0):.2f}/record)")
        print(f"  Thumbs: {s.get('thumb_up', 0)}↑ / {s.get('thumb_down', 0)}↓")
        print(f"  Copy rate:      {s.get('copy_rate', 0):.1%}")
        print(f"  Regenerate rate: {s.get('regenerate_rate', 0):.1%}")
        print()

    if report.trends:
        _print_section("Trends")
        if report.trends.weekly_growth.get("query_growth_pct") is not None:
            w = report.trends.weekly_growth
            print(f"  Weekly growth:   {w['query_growth_pct']:+.1f}% ({w['current_queries']} vs {w['previous_queries']} queries)")
            print(f"  Confidence Δ:    {w.get('confidence_change_pct', 0):+.1f}%")
        if report.trends.daily_volume:
            print(f"  Recent volume:   {report.trends.daily_volume[-1]['queries']} queries (today)")
        print()

    if report.recommendations:
        _print_section("Recommendations")
        print(f"  Total: {report.recommendations.count}")
        if report.recommendations.knowledge_gaps:
            print(f"  Knowledge Gaps:     {len(report.recommendations.knowledge_gaps)}")
            for r in report.recommendations.knowledge_gaps[:5]:
                print(f"    - [{r.severity.value.upper()}] {r.title[:70]}")
        if report.recommendations.weak_chunks:
            print(f"  Weak Chunks:        {len(report.recommendations.weak_chunks)}")
        if report.recommendations.dead_chunks:
            print(f"  Dead Chunks:        {len(report.recommendations.dead_chunks)}")
        if report.recommendations.benchmark_candidates:
            print(f"  Benchmark Cand.:    {len(report.recommendations.benchmark_candidates)}")
        print()

    _print_footer()


def run_cli(args: Optional[list[str]] = None) -> None:
    """Entry point for 'python -m app.learning.analytics.cli ...'"""
    import argparse
    parser = argparse.ArgumentParser(description="Analytics CLI")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parsed = parser.parse_args(args)

    engine = AnalyticsEngine()
    report = engine.run_all()
    display_report(report, json_output=parsed.json)


def _print_section(title: str) -> None:
    print(f"─── {title} ───")


def _print_header(title: str) -> None:
    line = "═" * 60
    print(f"\n{line}")
    print(f"  {title}")
    print(line)


def _print_footer() -> None:
    print("═" * 60)


if __name__ == "__main__":
    run_cli()
