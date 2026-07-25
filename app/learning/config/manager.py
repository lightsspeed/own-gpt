"""ConfigManager — manages immutable configuration snapshots and the production pointer."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from .models import ConfigurationSnapshot, ConfigDiff

logger = logging.getLogger(__name__)

CURRENT_POINTER_FILE = "current_config.json"
SNAPSHOT_DIR = "config_snapshots"


class ConfigManager:
    """Manages configuration snapshots with immutable history and pointer-based rollback.

    Storage is file-based (JSON) for simplicity. Each snapshot is an individual file.
    The 'current' pointer is a separate file containing the current snapshot ID.
    """

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR, pointer_file: str = CURRENT_POINTER_FILE):
        self._snapshot_dir = snapshot_dir
        self._pointer_file = pointer_file
        os.makedirs(snapshot_dir, exist_ok=True)

    # ── Snapshot CRUD ────────────────────────────────────────────────────

    def save_snapshot(self, snapshot: ConfigurationSnapshot) -> ConfigurationSnapshot:
        """Persist a snapshot to disk. Returns the snapshot."""
        path = self._snapshot_path(snapshot.id)
        with open(path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2, default=str)
        return snapshot

    def load_snapshot(self, snapshot_id: str) -> Optional[ConfigurationSnapshot]:
        """Load a snapshot by ID."""
        path = self._snapshot_path(snapshot_id)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return ConfigurationSnapshot.from_dict(data)

    def list_snapshots(self, limit: int = 50) -> list[ConfigurationSnapshot]:
        """List all snapshots, newest first."""
        if not os.path.exists(self._snapshot_dir):
            return []
        files = sorted(os.listdir(self._snapshot_dir), reverse=True)[:limit]
        snapshots = []
        for fname in files:
            path = os.path.join(self._snapshot_dir, fname)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                snapshots.append(ConfigurationSnapshot.from_dict(data))
            except (json.JSONDecodeError, IOError):
                continue
        return snapshots

    # ── Current pointer ──────────────────────────────────────────────────

    def get_current(self) -> Optional[ConfigurationSnapshot]:
        """Get the current production configuration."""
        current_id = self._read_pointer()
        if not current_id:
            return None
        return self.load_snapshot(current_id)

    def set_current(self, snapshot_id: str) -> bool:
        """Set the current production pointer. Returns True on success."""
        snapshot = self.load_snapshot(snapshot_id)
        if not snapshot:
            logger.warning("Cannot set current to unknown snapshot %s", snapshot_id)
            return False
        self._write_pointer(snapshot_id)
        snapshot.is_current = True
        self.save_snapshot(snapshot)
        return True

    def create_from_dict(self, params: dict, name: str = "", description: str = "",
                         decision_id: Optional[str] = None, experiment_id: Optional[str] = None) -> ConfigurationSnapshot:
        """Create a new snapshot from a parameter dict. Auto-increments version."""
        current = self.get_current()
        version = (current.version + 1) if current else 1
        snapshot = ConfigurationSnapshot(
            version=version,
            parent_id=current.id if current else None,
            name=name or f"Config v{version}",
            description=description,
            parameters=params,
            created_from_decision_id=decision_id,
            created_from_experiment_id=experiment_id,
        )
        self.save_snapshot(snapshot)
        return snapshot

    # ── Diff ─────────────────────────────────────────────────────────────

    def diff(self, snapshot_a_id: str, snapshot_b_id: str) -> Optional[ConfigDiff]:
        """Compute the parameter diff between two snapshots."""
        a = self.load_snapshot(snapshot_a_id)
        b = self.load_snapshot(snapshot_b_id)
        if not a or not b:
            return None

        params_a = a.parameters
        params_b = b.parameters
        all_keys = set(params_a.keys()) | set(params_b.keys())

        added, removed, changed, unchanged = {}, {}, {}, 0
        for key in all_keys:
            if key not in params_a:
                added[key] = params_b[key]
            elif key not in params_b:
                removed[key] = params_a[key]
            elif params_a[key] != params_b[key]:
                changed[key] = {"from": params_a[key], "to": params_b[key]}
            else:
                unchanged += 1

        return ConfigDiff(
            snapshot_a_id=snapshot_a_id,
            snapshot_b_id=snapshot_b_id,
            a_name=a.name,
            b_name=b.name,
            added=added,
            removed=removed,
            changed=changed,
            unchanged_count=unchanged,
        )

    def diff_current(self, snapshot_id: str) -> Optional[ConfigDiff]:
        """Diff a snapshot against the current production config."""
        current = self.get_current()
        if not current:
            return None
        return self.diff(current.id, snapshot_id)

    # ── Rollback ─────────────────────────────────────────────────────────

    def rollback(self, target_snapshot_id: str) -> Optional[ConfigurationSnapshot]:
        """Rollback the current pointer to a previous snapshot."""
        target = self.load_snapshot(target_snapshot_id)
        if not target:
            logger.warning("Cannot rollback: snapshot %s not found", target_snapshot_id)
            return None
        self.set_current(target_snapshot_id)
        logger.info("Rolled back to config snapshot %s (v%s)", target_snapshot_id, target.version)
        return target

    # ── Internal helpers ─────────────────────────────────────────────────

    def _snapshot_path(self, snapshot_id: str) -> str:
        return os.path.join(self._snapshot_dir, f"{snapshot_id}.json")

    def _read_pointer(self) -> Optional[str]:
        if not os.path.exists(self._pointer_file):
            return None
        try:
            with open(self._pointer_file, "r") as f:
                data = json.load(f)
            return data.get("current_snapshot_id")
        except (json.JSONDecodeError, IOError):
            return None

    def _write_pointer(self, snapshot_id: str) -> None:
        with open(self._pointer_file, "w") as f:
            json.dump({"current_snapshot_id": snapshot_id}, f)
