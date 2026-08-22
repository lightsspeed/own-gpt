from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_CHUNK_STRATEGY = "semantic"
DEFAULT_MANIFEST_PATH = "data/ingestion/manifest.json"
DEFAULT_BATCH_SIZE = 10
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_S = 2.0

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".csv", ".xlsx",
    ".html", ".htm",
}

EXTENSION_DESCRIPTION = {
    ".pdf": "PDF document",
    ".docx": "Word document",
    ".pptx": "PowerPoint presentation",
    ".csv": "CSV spreadsheet",
    ".xlsx": "Excel workbook",
    ".html": "HTML page",
    ".htm": "HTML page",
}


@dataclass
class IngestionConfig:
    source_dir: str
    recursive: bool = True
    supported_extensions: set = field(default_factory=lambda: SUPPORTED_EXTENSIONS)

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    chunk_strategy: str = DEFAULT_CHUNK_STRATEGY  # "recursive" | "semantic"

    manifest_path: str = DEFAULT_MANIFEST_PATH
    batch_size: int = DEFAULT_BATCH_SIZE
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay_s: float = DEFAULT_RETRY_DELAY_S

    def resolve_source_dir(self) -> Path:
        return Path(self.source_dir).resolve()

    def resolve_manifest_path(self) -> Path:
        return Path(self.manifest_path).resolve()

    @classmethod
    def from_yaml(cls, path: str | Path) -> IngestionConfig:
        import yaml
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Ingestion config not found: {p}")
        with open(p) as f:
            raw = yaml.safe_load(f)
        sec = raw.get("ingestion", raw)
        return cls(
            source_dir=sec.get("source_dir", "."),
            recursive=sec.get("recursive", True),
            supported_extensions=set(
                sec.get("supported_extensions", SUPPORTED_EXTENSIONS)
            ),
            chunk_size=sec.get("chunking", {}).get("chunk_size", DEFAULT_CHUNK_SIZE),
            chunk_overlap=sec.get("chunking", {}).get("chunk_overlap", DEFAULT_CHUNK_OVERLAP),
            chunk_strategy=sec.get("chunking", {}).get("strategy", DEFAULT_CHUNK_STRATEGY),
            manifest_path=sec.get("manifest", {}).get("path", DEFAULT_MANIFEST_PATH),
            batch_size=sec.get("processing", {}).get("batch_size", DEFAULT_BATCH_SIZE),
            max_retries=sec.get("processing", {}).get("max_retries", DEFAULT_MAX_RETRIES),
            retry_delay_s=sec.get("processing", {}).get("retry_delay", DEFAULT_RETRY_DELAY_S),
        )

    def to_yaml(self, path: str | Path) -> None:
        import yaml
        obj = {
            "ingestion": {
                "source_dir": self.source_dir,
                "recursive": self.recursive,
                "supported_extensions": sorted(self.supported_extensions),
                "chunking": {
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                },
                "manifest": {"path": self.manifest_path},
                "processing": {
                    "batch_size": self.batch_size,
                    "max_retries": self.max_retries,
                    "retry_delay": self.retry_delay_s,
                },
            }
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump(obj, f, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# File lock
# ---------------------------------------------------------------------------

class FileLock:
    """Simple cross-process file lock using PID file."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._acquired = False

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            content = self._path.read_text().strip()
            if content:
                try:
                    pid = int(content)
                    if self._pid_exists(pid):
                        logger.warning("Lock held by PID %s — skipping", pid)
                        return False
                    logger.info("Stale lock from PID %s — removing", pid)
                except ValueError:
                    pass
            self._path.unlink(missing_ok=True)
        self._path.write_text(str(os.getpid()))
        self._acquired = True
        return True

    def release(self) -> None:
        if self._acquired:
            self._path.unlink(missing_ok=True)
            self._acquired = False

    def __enter__(self) -> FileLock:
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self._path}")
        return self

    def __exit__(self, *args) -> None:
        self.release()

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, PermissionError):
            return False
