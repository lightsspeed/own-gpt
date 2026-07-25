"""
Report generation — save analytics reports as JSON files.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from .engine import AnalyticsEngine, AnalyticsReport

logger = logging.getLogger(__name__)


def generate_report(
    output_dir: str = "reports",
    filename: Optional[str] = None,
    engine: Optional[AnalyticsEngine] = None,
) -> str:
    """Generate a JSON report file. Returns the file path."""
    os.makedirs(output_dir, exist_ok=True)
    engine = engine or AnalyticsEngine()
    report = engine.run_all()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, filename or f"analytics_report_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)
    logger.info("Report written to %s", path)
    return path


def run_reporter(args: Optional[list[str]] = None) -> None:
    """Entry point for 'python -m app.learning.analytics.reports ...'"""
    import argparse
    parser = argparse.ArgumentParser(description="Generate analytics report JSON")
    parser.add_argument("--out", default="reports", help="Output directory")
    parsed = parser.parse_args(args)
    path = generate_report(output_dir=parsed.out)
    print(f"Report: {path}")


if __name__ == "__main__":
    run_reporter()
