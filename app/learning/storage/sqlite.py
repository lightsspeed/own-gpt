"""
SQLite event store for the Learning Ledger.

Append-only writes, indexed columns for analytics queries.
Designed for local/single-instance deployments — not horizontally scalable.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from ..models import LearningRecord, UserEvent

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "learning.db"


class LearningStore:
    """Thread-safe SQLite store for LearningRecords and UserEvents."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self._path = Path(db_path or _DEFAULT_DB_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()
        self._migrate()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS learning_records (
                    record_id         TEXT PRIMARY KEY,
                    learning_schema_version INTEGER DEFAULT 1,
                    timestamp         TEXT NOT NULL,
                    session_id        TEXT NOT NULL,
                    message_id        TEXT,
                    question          TEXT,
                    normalized_question TEXT,
                    question_hash     TEXT,
                    intent            TEXT,
                    matched_rule      TEXT,
                    intent_confidence REAL,
                    retriever         TEXT,
                    answer_mode       TEXT,
                    documents         TEXT,
                    chunks            TEXT,
                    vector_scores     TEXT,
                    bm25_scores       TEXT,
                    rrf_scores        TEXT,
                    reranker_scores   TEXT,
                    model             TEXT,
                    prompt_version    TEXT,
                    latency_ms        REAL,
                    tokens_in         INTEGER,
                    tokens_out        INTEGER,
                    confidence        REAL,
                    faithfulness      REAL,
                    context_precision REAL,
                    context_recall    REAL,
                    hallucination_risk TEXT,
                    thumb             TEXT,
                    copied            INTEGER DEFAULT 0,
                    regenerated       INTEGER DEFAULT 0,
                    edited            INTEGER DEFAULT 0,
                    follow_up         TEXT,
                    accepted          INTEGER DEFAULT 1,
                    resolved          INTEGER DEFAULT 1,
                    failure_reason    TEXT,
                    pipeline_version  TEXT,
                    prompt_version_id TEXT,
                    embedding_model   TEXT,
                    reranker_model    TEXT,
                    chunk_size        INTEGER DEFAULT 0,
                    git_commit        TEXT,
                    dataset_hash      TEXT,
                    created_at        TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS user_events (
                    event_id   TEXT PRIMARY KEY,
                    record_id  TEXT,
                    session_id TEXT NOT NULL,
                    type       TEXT NOT NULL,
                    metadata   TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (record_id) REFERENCES learning_records(record_id)
                );
            """)
            # Indexes created separately so old schemas don't block startup
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_lr_timestamp ON learning_records(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_lr_session   ON learning_records(session_id)",
                "CREATE INDEX IF NOT EXISTS idx_lr_intent    ON learning_records(intent)",
                "CREATE INDEX IF NOT EXISTS idx_lr_mode      ON learning_records(answer_mode)",
                "CREATE INDEX IF NOT EXISTS idx_ue_record    ON user_events(record_id)",
                "CREATE INDEX IF NOT EXISTS idx_ue_session   ON user_events(session_id)",
                "CREATE INDEX IF NOT EXISTS idx_ue_type      ON user_events(type)",
            ]:
                try:
                    conn.execute(idx_sql)
                except sqlite3.OperationalError:
                    pass

    def _migrate(self) -> None:
        """Apply schema migrations for existing databases."""
        with self._lock:
            with self._connection() as conn:
                for col_sql in [
                    "ADD COLUMN question_hash TEXT",
                    "ADD COLUMN learning_schema_version INTEGER DEFAULT 1",
                    "ADD COLUMN normalized_question TEXT",
                ]:
                    try:
                        conn.execute(f"ALTER TABLE learning_records {col_sql}")
                    except sqlite3.OperationalError:
                        pass
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_lr_qhash ON learning_records(question_hash)")
                except sqlite3.OperationalError:
                    pass

    # ── Write ─────────────────────────────────────────────────────────────

    def _existing_columns(self, table: str) -> set[str]:
        """Return the set of column names that exist in the given table."""
        with self._connection() as conn:
            try:
                cursor = conn.execute(f"SELECT * FROM {table} LIMIT 0")
                return {d[0] for d in cursor.description}
            except sqlite3.OperationalError:
                return set()

    def store_record(self, record: LearningRecord) -> None:
        """Append a learning record. Idempotent on record_id.
        Filters to only columns that exist in the table for schema resilience."""
        existing = self._existing_columns("learning_records")
        data = {k: v for k, v in record.to_dict().items() if k in existing}
        if not data:
            return
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        values = list(data.values())

        with self._lock:
            with self._connection() as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO learning_records ({cols}) VALUES ({placeholders})",
                    values,
                )

    def store_event(self, event: UserEvent) -> None:
        """Append a user event."""
        with self._lock:
            with self._connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO user_events (event_id, record_id, session_id, type, metadata, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (event.event_id, event.record_id, event.session_id, event.type,
                     json.dumps(event.metadata) if event.metadata else None,
                     event.created_at),
                )

    # ── Query ─────────────────────────────────────────────────────────────

    def get_record(self, record_id: str) -> Optional[LearningRecord]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM learning_records WHERE record_id = ?", (record_id,)
            ).fetchone()
        return LearningRecord.from_dict(dict(row)) if row else None

    def query_records(self, **filters) -> list[LearningRecord]:
        """Simple equality-filter query. Returns all if no filters provided."""
        where = []
        values = []
        for key, val in filters.items():
            if val is not None:
                where.append(f"{key} = ?")
                values.append(val)
        sql = "SELECT * FROM learning_records"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY timestamp DESC LIMIT 1000"
        with self._connection() as conn:
            rows = conn.execute(sql, values).fetchall()
        return [LearningRecord.from_dict(dict(r)) for r in rows]

    def get_events_for_record(self, record_id: str) -> list[UserEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM user_events WHERE record_id = ? ORDER BY created_at", (record_id,)
            ).fetchall()
        events = []
        for r in rows:
            d = dict(r)
            if d.get("metadata"):
                d["metadata"] = json.loads(d["metadata"])
            events.append(UserEvent(**d))
        return events

    # ── Counters (dashboard) ─────────────────────────────────────────────

    def count_records(self) -> int:
        with self._connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0]

    def count_events(self) -> int:
        with self._connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM user_events").fetchone()[0]

    def count_events_by_type(self) -> dict[str, int]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM user_events GROUP BY type ORDER BY cnt DESC"
            ).fetchall()
        return {r["type"]: r["cnt"] for r in rows}

    def count_records_by_intent(self) -> dict[str, int]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT intent, COUNT(*) as cnt FROM learning_records GROUP BY intent ORDER BY cnt DESC"
            ).fetchall()
        return {r["intent"]: r["cnt"] for r in rows}

    # ── Raw SQL for analytics ────────────────────────────────────────────

    def query_sql(self, sql: str, params: list | None = None) -> list[dict]:
        """Execute a raw SQL query and return results as dicts. For analytics use only."""
        with self._connection() as conn:
            rows = conn.execute(sql, params or []).fetchall()
        return [dict(r) for r in rows]

    # ── Export ────────────────────────────────────────────────────────────

    def export_jsonl(self, limit: int = 0) -> list[dict]:
        sql = "SELECT * FROM learning_records ORDER BY timestamp DESC"
        if limit > 0:
            sql += f" LIMIT {limit}"
        with self._connection() as conn:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
