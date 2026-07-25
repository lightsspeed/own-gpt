"""
JSONL export — dump LearningRecords to JSONL for offline analysis.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .sqlite import LearningStore

logger = logging.getLogger(__name__)


def export_jsonl(
    output_path: str | Path,
    limit: int = 0,
    store: Optional[LearningStore] = None,
) -> int:
    """
    Export LearningRecords from the store to a JSONL file.

    Args:
        output_path: Path to the output .jsonl file.
        limit: Maximum number of records to export (0 = all).
        store: LearningStore instance (defaults to new instance).

    Returns:
        Number of records exported.
    """
    store = store or LearningStore()
    records = store.export_jsonl(limit=limit)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r, default=str) + "\n")

    logger.info("exported_jsonl path=%s count=%d", output_path, len(records))
    return len(records)
