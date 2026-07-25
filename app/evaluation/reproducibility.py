from __future__ import annotations

import hashlib
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BENCHMARK_VERSION = "2.0.0"


def _git_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def _git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def _git_dirty() -> bool:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return bool(r.stdout.strip())
    except Exception:
        pass
    return False


def _file_hash(path: str | Path) -> str:
    try:
        h = hashlib.sha256()
        h.update(Path(path).read_bytes())
        return h.hexdigest()[:16]
    except Exception:
        return ""


def _requirements_hash(req_path: str | Path = "requirements.txt") -> str:
    return _file_hash(req_path)


def _dataset_hash(dataset_name: str, datasets_root: str | Path = "tests/rag/datasets") -> str:
    path = Path(datasets_root) / dataset_name / "questions.jsonl"
    return _file_hash(path)


def _python_version() -> str:
    return platform.python_version()


def _read_config_for(key: str, config_path: str | Path = "pipeline_config.yaml") -> str:
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        # Walk dotted path e.g. "retriever.reranker_model"
        parts = key.split(".")
        val = cfg
        for p in parts:
            val = val.get(p, {}) if isinstance(val, dict) else ""
        return str(val) if val else ""
    except Exception:
        return ""


def collect_metadata(
    dataset_name: str = "",
    retriever_mode: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    metadata = {
        "benchmark_version": BENCHMARK_VERSION,
        "python_version": _python_version(),
        "git_commit": _git_commit(),
        "git_branch": _git_branch(),
        "git_dirty": _git_dirty(),
        "requirements_hash": _requirements_hash(),
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "reranker_model": _read_config_for("reranker_model", "pipeline_config.yaml"),
        "llm": "gpt-4o-mini",
        "chunk_size": 1000,
    }

    if dataset_name:
        metadata["dataset_hash"] = _dataset_hash(dataset_name)
        metadata["dataset"] = dataset_name

    if retriever_mode:
        metadata["retriever_mode"] = retriever_mode

    if extra:
        metadata.update(extra)

    return metadata
