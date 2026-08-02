"""State management for EvaluationSnapshots — CRUD, persistence, and diff engine."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from .models import EvaluationSnapshot

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "eval_snapshots"
RUN_DIR = "eval_run_history"


class RunStore:
    """Persists AutomationRun history as JSON files (append-only, newest-first)."""

    def __init__(self, run_dir: str = RUN_DIR):
        self._run_dir = run_dir
        os.makedirs(run_dir, exist_ok=True)

    def record(self, run) -> run.__class__:
        path = self._path(run.id)
        with open(path, "w") as f:
            json.dump(run.to_dict(), f, indent=2, default=str)
        return run

    def _path(self, run_id: str) -> str:
        return os.path.join(self._run_dir, f"{run_id}.json")

    def list_all(self, limit: int = 50) -> list:
        from .models import AutomationRun
        if not os.path.exists(self._run_dir):
            return []
        files = sorted(os.listdir(self._run_dir), key=lambda f: f, reverse=True)[:limit]
        result = []
        for fname in files:
            path = os.path.join(self._run_dir, fname)
            try:
                with open(path, "r") as f:
                    result.append(AutomationRun.from_dict(json.load(f)))
            except (json.JSONDecodeError, IOError):
                continue
        return result


class SnapshotStore:
    """Persists EvaluationSnapshots as JSON files and computes diffs."""

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR):
        self._snapshot_dir = snapshot_dir
        os.makedirs(snapshot_dir, exist_ok=True)

    def save(self, snapshot: EvaluationSnapshot) -> EvaluationSnapshot:
        path = self._path(snapshot.id)
        with open(path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2, default=str)
        return snapshot

    def load(self, snapshot_id: str) -> Optional[EvaluationSnapshot]:
        path = self._path(snapshot_id)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return EvaluationSnapshot(**data)

    def latest(self) -> Optional[EvaluationSnapshot]:
        """Load the most recent snapshot."""
        snapshots = self.list_all(limit=1)
        return snapshots[0] if snapshots else None

    def second_latest(self) -> Optional[EvaluationSnapshot]:
        """Load the second most recent snapshot (for diffing)."""
        snapshots = self.list_all(limit=2)
        return snapshots[1] if len(snapshots) >= 2 else None

    def list_all(self, limit: int = 50) -> list[EvaluationSnapshot]:
        if not os.path.exists(self._snapshot_dir):
            return []
        files = sorted(os.listdir(self._snapshot_dir), reverse=True)[:limit]
        result = []
        for fname in files:
            path = os.path.join(self._snapshot_dir, fname)
            try:
                with open(path, "r") as f:
                    result.append(EvaluationSnapshot(**json.load(f)))
            except (json.JSONDecodeError, IOError):
                continue
        return result

    def delete(self, snapshot_id: str) -> bool:
        path = self._path(snapshot_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    # ── Diff Engine ───────────────────────────────────────────────────

    def diff(self, current_id: str, previous_id: str) -> Optional[EvaluationSnapshot]:
        """Diff two snapshots and enrich `current` with delta information.

        Returns a copy of the current snapshot with change_summary,
        findings_delta, and confidence_delta populated.
        """
        current = self.load(current_id)
        previous = self.load(previous_id)
        if not current or not previous:
            return None

        changes = {}

        # Numeric diffs
        for field in ("avg_confidence", "accept_rate", "ece",
                       "findings_count", "critical_findings", "high_findings",
                       "knowledge_gap_count", "weak_chunk_count"):
            curr_val = getattr(current, field, None)
            prev_val = getattr(previous, field, None)
            if curr_val is not None and prev_val is not None:
                if isinstance(curr_val, (int, float)) and isinstance(prev_val, (int, float)):
                    delta = round(curr_val - prev_val, 3)
                    delta_pct = round(((curr_val - prev_val) / max(abs(prev_val), 0.001)) * 100, 1)
                    if abs(delta) > 0.001:
                        changes[field] = {
                            "previous": prev_val,
                            "current": curr_val,
                            "delta": delta,
                            "delta_pct": delta_pct,
                        }

        # Health score diffs
        health_deltas = {}
        for domain, score in current.health_scores.items():
            prev_score = previous.health_scores.get(domain)
            if prev_score is not None:
                diff = round(score - prev_score, 1)
                if abs(diff) > 0.1:
                    health_deltas[domain] = {"previous": prev_score, "current": score, "delta": diff}

        if health_deltas:
            changes["health_scores"] = health_deltas

        # Compute deltas
        current.change_summary = changes
        current.findings_delta = (current.findings_count or 0) - (previous.findings_count or 0)
        if current.avg_confidence is not None and previous.avg_confidence is not None:
            current.confidence_delta = round(current.avg_confidence - previous.avg_confidence, 3)
        if current.ece is not None and previous.ece is not None:
            current.ece_change_pct = round(((current.ece - previous.ece) / max(previous.ece, 0.001)) * 100, 1)
        current.previous_snapshot_id = previous_id

        return current

    # ── Internal ──────────────────────────────────────────────────────

    def _path(self, snapshot_id: str) -> str:
        return os.path.join(self._snapshot_dir, f"{snapshot_id}.json")
