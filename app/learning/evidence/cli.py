"""
CLI for the Evidence Engine. Displays findings and diagnostics.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from .engine import EvidenceEngine

logger = logging.getLogger(__name__)


def display_report(engine: Optional[EvidenceEngine] = None, json_output: bool = False) -> None:
    """Print evidence findings to stdout."""
    ee = engine or EvidenceEngine()
    report = ee.analyze()

    if json_output:
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return

    print(f"\n{'═' * 60}")
    print("  Evidence Engine Report")
    print(f"{'═' * 60}")
    print(f"  Generated: {report.generated_at}")
    print(f"  Findings:  {len(report.findings)}")
    print()

    if report.calibration:
        print("─── Confidence Calibration ───")
        c = report.calibration
        print(f"  ECE: {c.ece:.4f}")
        print(f"  Records analyzed: {c.total_records_analyzed}")
        if c.max_overconfidence_bucket:
            print(f"  Max overconfidence: {c.max_overconfidence_bucket}")
        if c.max_underconfidence_bucket:
            print(f"  Max underconfidence: {c.max_underconfidence_bucket}")
        if c.buckets:
            print("  Buckets:")
            for b in c.buckets:
                if b.count > 0:
                    marker = " ←" if abs(b.gap) > 0.15 else ""
                    print(f"    {b.bucket:>8s}: n={b.count:4d}  conf={b.avg_confidence:.2f}  accept={b.accept_rate:.2f}  gap={b.gap:+.2f}{marker}")
        if c.findings:
            print(f"  Findings: {len(c.findings)}")
            for f in c.findings:
                print(f"    [{f.severity.upper()}] {f.title[:70]}")
        print()

    if report.knowledge_gaps:
        print("─── Knowledge Gap Diagnosis ───")
        for d in report.knowledge_gaps.diagnoses:
            rc = d.root_cause
            print(f"  [{d.severity.upper()}] {d.title[:70]}")
            print(f"    Cause: {rc.category} (conf={rc.confidence:.2f})")
            print(f"    Rec:   {d.recommendation_text[:80]}")
        print()

    if report.failure_tree:
        print("─── Retrieval Failure Tree ───")
        ft = report.failure_tree
        print(f"  Total failures analyzed: {ft.total_failed}")
        if ft.classifications:
            print("  By category:")
            for cat, cnt in sorted(ft.classifications.items(), key=lambda x: -x[1]):
                print(f"    {cat}: {cnt}")
        if ft.findings:
            print(f"  Findings: {len(ft.findings)}")
            for f in ft.findings:
                print(f"    [{f.severity.upper()}] {f.title[:70]}")
        print()

    print(f"{'═' * 60}\n")


def run_cli(args: Optional[list[str]] = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Evidence Engine CLI")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parsed = parser.parse_args(args)

    engine = EvidenceEngine()
    display_report(engine=engine, json_output=parsed.json)


if __name__ == "__main__":
    run_cli()
