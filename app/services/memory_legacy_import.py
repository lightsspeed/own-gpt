"""
Legacy memory import — operator CLI.

    python -m app.services.memory_legacy_import --memory-dir memory_facts [--user-id <id>] [--dry-run]

Reads legacy MemoryFact JSON files (the JSON store behind the superseded
`app/learning/operations/memory.py`) and imports them into Memory V2 as
`source=migrated` entities with lineage metadata.

Migration rules (spec §10):
- `scope == "global"`          → project_id=None (user-wide).
- `scope == "session:<id>"`    → migrated ONLY when ALL of: the referenced
  session row exists; session.owner_id is set; session.owner_id matches the
  import target user. Otherwise SKIP + REPORT. Never infer ownership and
  never guess a project mapping — the previously deleted legacy sessions
  deterministically skip.
- Idempotent: a legacy_fact_id already present in `metadata` is skipped
  (query on metadata_->>'legacy_fact_id').
- status preserved (superseded stays superseded); no embeddings imported —
  the search-time backfill covers them.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.database import SyncSessionLocal
from app.models.chat import ChatSession
from app.models.memory import DOMAIN_SEMANTIC, SOURCE_MIGRATED, STATUS_SUPERSEDED
from app.models.user import User
from app.services import memory as mem

logger = logging.getLogger(__name__)

INDEX_FILENAME = ".memory_index.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy memory facts into Memory V2")
    parser.add_argument("--memory-dir", required=True, help="Path to the legacy memory_facts directory")
    parser.add_argument("--user-id", default=None, help="Target user id; defaults to the single fallback user")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing anything")
    return parser.parse_args(argv)


def _fact_files(memory_dir: Path) -> list[Path]:
    if not memory_dir.is_dir():
        raise SystemExit(f"memory dir not found: {memory_dir}")
    return sorted(
        p for p in memory_dir.glob("*.json") if p.name != INDEX_FILENAME
    )


def _resolve_target_user(db, user_id: str | None) -> User:
    if user_id:
        user = db.get(User, user_id)
        if user is None:
            raise SystemExit(f"user not found: {user_id}")
        return user
    users = db.execute(select(User)).scalars().all()
    if len(users) == 1:
        return users[0]
    raise SystemExit(
        "no --user-id given and the target user is ambiguous "
        f"({len(users)} users exist); pass --user-id explicitly"
    )


def _session_owner(db, session_id: str) -> str | None:
    row = db.execute(
        select(ChatSession.owner_id).where(ChatSession.id == session_id)
    ).scalar_one_or_none()
    return row


def _import_fact(db, fact: dict, user: User) -> tuple[str, str]:
    """Import one fact; returns (status, detail)."""
    fact_id = str(fact.get("id") or "")
    statement = str(fact.get("fact") or "")
    scope = str(fact.get("scope") or "global")
    legacy_status = str(fact.get("status") or "active")

    if not fact_id or not statement.strip():
        return "skip", "missing id or fact text"

    project_id = None
    if scope != "global":
        if not scope.startswith("session:"):
            return "skip", f"unknown scope {scope!r}"
        session_id = scope[len("session:") :]
        owner = _session_owner(db, session_id)
        if owner is None:
            return "skip", f"session {session_id!r} does not exist"
        if not owner:
            return "skip", f"session {session_id!r} has no owner"
        if owner != user.id:
            return "skip", f"session {session_id!r} owned by another user"

    legacy_hits = [
        e
        for e in db.execute(
            select(mem.MemoryEntity).where(mem.MemoryEntity.user_id == user.id)
        ).scalars().all()
        if (e.metadata_ or {}).get("legacy_fact_id") == fact_id
    ]
    if legacy_hits:
        return "skip", "already imported (legacy_fact_id match)"

    entity = mem.create_memory(
        db,
        user_id=user.id,
        statement=statement,
        domain=DOMAIN_SEMANTIC,
        source=SOURCE_MIGRATED,
        authority=mem.AUTHORITY_MIGRATED,
        confidence=0.5,
        importance=0.5,
        project_id=project_id,
        apply_domain_ttl=False,
        metadata={
            "legacy_fact_id": fact_id,
            "legacy_scope": scope,
        },
    )
    if legacy_status == STATUS_SUPERSEDED and entity.status != STATUS_SUPERSEDED:
        entity.status = STATUS_SUPERSEDED
    db.commit()
    return "imported", f"scope={scope}"


def run_import(
    memory_dir: Path,
    user_id: str | None,
    dry_run: bool,
    db=None,
) -> dict:
    """Run the import. `db` is injectable for tests; defaults to the
    production sync session (CLI usage)."""
    from sqlalchemy.orm import Session

    own_session = db is None
    if own_session:
        with SyncSessionLocal() as db_ctx:
            return _run_import(db_ctx, memory_dir, user_id, dry_run)
    if not isinstance(db, Session):
        raise TypeError("db must be a sqlalchemy Session")
    return _run_import(db, memory_dir, user_id, dry_run)


def _run_import(db, memory_dir: Path, user_id: str | None, dry_run: bool) -> dict:
    user = _resolve_target_user(db, user_id)
    report = {"imported": [], "skipped": [], "dry_run": dry_run, "target_user": user.id}
    for path in _fact_files(memory_dir):
        try:
            fact = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            report["skipped"].append({"file": path.name, "status": "error", "detail": str(exc)})
            continue
        if not isinstance(fact, dict):
            report["skipped"].append({"file": path.name, "status": "skip", "detail": "not a dict"})
            continue
        if dry_run:
            scope = str(fact.get("scope") or "global")
            status = "plan" if scope == "global" else "plan-conditional"
            report["imported"].append({"file": path.name, "status": status, "detail": f"scope={scope}"})
            continue
        status, detail = _import_fact(db, fact, user)
        bucket = report["imported"] if status == "imported" else report["skipped"]
        bucket.append({"file": path.name, "status": status, "detail": detail})
    return report


def _print_report(report: dict) -> None:
    print(f"target_user={report['target_user']} dry_run={report['dry_run']}")
    print(f"imported/planned: {len(report['imported'])}")
    for row in report["imported"]:
        print(f"  + {row['file']}: {row['status']} ({row['detail']})")
    print(f"skipped: {len(report['skipped'])}")
    for row in report["skipped"]:
        print(f"  - {row['file']}: {row['status']} ({row['detail']})")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.WARNING)
    report = run_import(Path(args.memory_dir), args.user_id, args.dry_run)
    _print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())