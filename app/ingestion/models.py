from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional

FileStatus = Literal["new", "modified", "unchanged", "deleted"]


@dataclass
class FileRecord:
    """Tracks a single file's identity and ingestion state."""
    rel_path: str
    size: int
    modified_at: Optional[datetime]
    sha256: str
    last_ingested: Optional[datetime] = None


@dataclass
class ScanDiff:
    """Result of comparing current filesystem state against the manifest."""
    new: List[FileRecord] = field(default_factory=list)
    modified: List[FileRecord] = field(default_factory=list)
    deleted: List[FileRecord] = field(default_factory=list)
    unchanged: List[FileRecord] = field(default_factory=list)

    @property
    def changed(self) -> List[FileRecord]:
        return self.new + self.modified + self.deleted

    @property
    def to_process(self) -> List[FileRecord]:
        return self.new + self.modified


@dataclass
class FileResult:
    """Per-file outcome from the pipeline."""
    rel_path: str
    status: Literal["success", "failed", "skipped"]
    chunks: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class PipelineReport:
    """Aggregated result from a single pipeline run."""
    pipeline_id: str
    started_at: datetime
    duration_ms: float = 0.0
    config_source: str = ""

    scanned: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    deleted: int = 0
    total_chunks: int = 0

    file_results: List[FileResult] = field(default_factory=list)
