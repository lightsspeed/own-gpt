"""Tool execution store — HITL approval records for mutating tool calls.

Every guarded tool call produces an immutable ToolExecution artifact:

  - read-only calls → executed immediately, recorded with result
  - mutating calls  → recorded as pending; a human operator approves or
    rejects via the operations API; only then does the sandbox run the tool

Records are append-only JSON files. State transitions append to an `events`
list; history is never rewritten.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

TOOL_EXECUTION_DIR = "tool_executions"


@dataclass
class ToolExecutionEvent:
    status: str
    at: str = ""
    note: str = ""

    def __post_init__(self):
        if not self.at:
            self.at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {"status": self.status, "at": self.at, "note": self.note}


@dataclass
class ToolExecution:
    """Immutable record of one guarded tool call."""
    id: str = ""
    tool_name: str = ""
    args: dict = field(default_factory=dict)
    status: str = "pending"      # pending | allowed | approved | rejected | denied | executed | failed | timed_out
    requested_at: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    events: list[ToolExecutionEvent] = field(default_factory=list)
    sandboxed: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = f"tx-{uuid.uuid4().hex[:12]}"
        if not self.requested_at:
            self.requested_at = datetime.now(timezone.utc).isoformat()

    def append_event(self, status: str, note: str = ""):
        self.events.append(ToolExecutionEvent(status=status, note=note))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "args": self.args,
            "status": self.status,
            "requested_at": self.requested_at,
            "result": self.result,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
            "events": [e.to_dict() for e in self.events],
            "sandboxed": self.sandboxed,
        }

    @staticmethod
    def from_dict(data: dict) -> "ToolExecution":
        events = [ToolExecutionEvent(**e) for e in data.get("events", [])]
        kwargs = {k: v for k, v in data.items() if k != "events"}
        return ToolExecution(events=events, **kwargs)


class ToolExecutionStore:
    """Persists ToolExecution artifacts (append-only per id)."""

    def __init__(self, store_dir: str = TOOL_EXECUTION_DIR):
        self._store_dir = store_dir
        os.makedirs(store_dir, exist_ok=True)

    def save(self, execution: ToolExecution) -> ToolExecution:
        path = self._path(execution.id)
        with open(path, "w") as f:
            json.dump(execution.to_dict(), f, indent=2, default=str)
        return execution

    def get(self, execution_id: str) -> Optional[ToolExecution]:
        path = self._path(execution_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return ToolExecution.from_dict(json.load(f))
        except (json.JSONDecodeError, IOError, TypeError):
            return None

    def list_all(self, status: Optional[str] = None, limit: int = 50) -> list[ToolExecution]:
        if not os.path.exists(self._store_dir):
            return []
        files = sorted(os.listdir(self._store_dir), reverse=True)[:limit]
        result = []
        for fname in files:
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._store_dir, fname)
            try:
                with open(path, "r") as f:
                    execution = ToolExecution.from_dict(json.load(f))
                if status and execution.status != status:
                    continue
                result.append(execution)
            except (json.JSONDecodeError, IOError, TypeError):
                continue
        return result

    def transition(self, execution_id: str, new_status: str, note: str = "") -> Optional[ToolExecution]:
        """Append a status transition to an execution record."""
        execution = self.get(execution_id)
        if not execution:
            return None
        execution.append_event(new_status, note=note)
        execution.status = new_status
        return self.save(execution)

    def _path(self, execution_id: str) -> str:
        return os.path.join(self._store_dir, f"{execution_id}.json")
