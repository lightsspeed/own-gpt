from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATASETS_DIR = Path(__file__).resolve().parents[2] / "tests" / "rag" / "datasets"


@dataclass
class BenchmarkQuestion:
    id: str
    category: str
    difficulty: str
    question: str
    expected_claims: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    expected_sources: list[str] = field(default_factory=list)
    complexity: str = "medium"
    priority: str = "normal"
    weight: int = 1
    tags: list[str] = field(default_factory=list)
    context: Optional[str] = None
    source_description: Optional[str] = None


@dataclass
class BenchmarkDataset:
    name: str
    display_name: str
    description: str
    questions: list[BenchmarkQuestion] = field(default_factory=list)

    def by_category(self, category: str) -> list[BenchmarkQuestion]:
        return [q for q in self.questions if q.category == category]

    def by_difficulty(self, difficulty: str) -> list[BenchmarkQuestion]:
        return [q for q in self.questions if q.difficulty == difficulty]

    def to_dicts(self) -> list[dict]:
        return [asdict(q) for q in self.questions]


def list_datasets() -> list[str]:
    if not _DATASETS_DIR.exists():
        logger.warning("Datasets directory not found: %s", _DATASETS_DIR)
        return []
    return sorted(
        d.name
        for d in _DATASETS_DIR.iterdir()
        if d.is_dir() and (d / "questions.jsonl").exists()
    )


def load_dataset(name: str) -> BenchmarkDataset:
    dataset_dir = _DATASETS_DIR / name
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset '{name}' not found at {dataset_dir}")

    questions_file = dataset_dir / "questions.jsonl"
    meta_file = dataset_dir / "meta.json"

    display_name = name
    description = ""
    if meta_file.exists():
        with open(meta_file) as f:
            meta = json.load(f)
            display_name = meta.get("display_name", name)
            description = meta.get("description", "")

    questions: list[BenchmarkQuestion] = []
    if questions_file.exists():
        with open(questions_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                questions.append(BenchmarkQuestion(**data))

    logger.info(
        "Loaded dataset '%s': %d questions (%d categories)",
        name,
        len(questions),
        len({q.category for q in questions}),
    )
    return BenchmarkDataset(
        name=name, display_name=display_name, description=description, questions=questions
    )
