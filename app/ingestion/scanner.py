from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import IngestionConfig, SUPPORTED_EXTENSIONS
from .models import FileRecord, ScanDiff

logger = logging.getLogger(__name__)

class Scanner:
    """Walks a directory tree and produces a list of FileRecords with SHA256 hashes."""

    def __init__(self, config: IngestionConfig):
        self._config = config
        self._root = config.resolve_source_dir()

    def scan(self) -> List[FileRecord]:
        """Walk the source directory and return FileRecords for every supported file."""
        if not self._root.is_dir():
            raise NotADirectoryError(f"Source directory not found: {self._root}")

        records: List[FileRecord] = []
        for entry in self._walk():
            try:
                stat = entry.stat()
                digest = self._hash_file(entry)
            except (OSError, PermissionError) as exc:
                logger.warning("Cannot read %s: %s", entry, exc)
                continue

            records.append(FileRecord(
                rel_path=str(entry.relative_to(self._root).as_posix()),
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                sha256=digest,
            ))

        records.sort(key=lambda r: r.rel_path)
        return records

    def _walk(self) -> List[Path]:
        """Yield all supported file paths under the root."""
        paths: List[Path] = []
        if self._config.recursive:
            for dirpath, _dirnames, filenames in os.walk(self._root):
                for fn in filenames:
                    p = Path(dirpath, fn)
                    if p.suffix.lower() in self._config.supported_extensions:
                        paths.append(p)
        else:
            for entry in self._root.iterdir():
                if entry.is_file() and entry.suffix.lower() in self._config.supported_extensions:
                    paths.append(entry)
        return paths

    @staticmethod
    def _hash_file(path: Path, chunk_size: int = 65536) -> str:
        """Compute SHA-256 of a file in streaming fashion (low memory)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                block = f.read(chunk_size)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()


# ---------------------------------------------------------------------------
# Manifest — persistent file-state store (JSON on disk)
# ---------------------------------------------------------------------------

class Manifest:
    """
    Loads/saves a JSON manifest that records every file known to the pipeline.

    The manifest enables incremental ingestion by remembering SHA256 hashes
    so the next run can skip unchanged files.
    """

    _VERSION = 1

    def __init__(self, config: IngestionConfig):
        self._path = config.resolve_manifest_path()
        self._data: Dict[str, dict] = {}

    def load(self) -> None:
        """Load existing manifest from disk (no-op if missing)."""
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._data = raw.get("files", {})
                logger.info("Loaded manifest with %d entries from %s", len(self._data), self._path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Corrupt manifest at %s — starting fresh: %s", self._path, exc)
                self._data = {}

    def save(self, records: List[FileRecord]) -> None:
        """Overwrite manifest with the current file set."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized: Dict[str, dict] = {}
        for r in records:
            serialized[r.rel_path] = {
                "size": r.size,
                "modified_at": r.modified_at.isoformat() if r.modified_at else None,
                "sha256": r.sha256,
                "last_ingested": r.last_ingested.isoformat() if r.last_ingested else None,
            }
        payload = {
            "version": self._VERSION,
            "updated_at": datetime.utcnow().isoformat(),
            "files": serialized,
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved manifest with %d entries to %s", len(serialized), self._path)

    def diff(self, current: List[FileRecord]) -> ScanDiff:
        """
        Compare a current scan against the loaded manifest.

        Returns a ScanDiff with new, modified, deleted, and unchanged files.
        """
        diff = ScanDiff()

        prev_by_path = {r.rel_path: r for r in self._to_records()}
        curr_by_path = {r.rel_path: r for r in current}

        for rel_path, cur in curr_by_path.items():
            prev = prev_by_path.get(rel_path)
            if prev is None:
                cur.last_ingested = None
                diff.new.append(cur)
            elif prev.sha256 != cur.sha256:
                cur.last_ingested = prev.last_ingested
                diff.modified.append(cur)
            else:
                cur.last_ingested = prev.last_ingested
                diff.unchanged.append(cur)

        for rel_path, prev in prev_by_path.items():
            if rel_path not in curr_by_path:
                diff.deleted.append(prev)

        logger.info(
            "Scan diff: %d new, %d modified, %d deleted, %d unchanged",
            len(diff.new), len(diff.modified), len(diff.deleted), len(diff.unchanged),
        )
        return diff

    # -- helpers ------------------------------------------------------------

    def _to_records(self) -> List[FileRecord]:
        records: List[FileRecord] = []
        for rel_path, meta in self._data.items():
            records.append(FileRecord(
                rel_path=rel_path,
                size=meta.get("size", 0),
                modified_at=self._parse_dt(meta.get("modified_at")),
                sha256=meta.get("sha256", ""),
                last_ingested=self._parse_dt(meta.get("last_ingested")),
            ))
        return records

    @staticmethod
    def _parse_dt(val: Optional[str]) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return None
