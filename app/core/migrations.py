"""
Lightweight, idempotent schema migrations.

The project previously created tables with `Base.metadata.create_all` and had
no migration mechanism (alembic is pinned in requirements but never wired).
This runner fills that gap:

- `schema_migrations` records which migrations already ran.
- Every migration is idempotent (CREATE ... IF NOT EXISTS / ADD COLUMN IF
  NOT EXISTS) and data-preserving, so it is safe on both fresh and existing
  databases.
- Runs at application startup after `create_all`, which handles brand-new
  tables; migrations evolve existing tables without destructive operations.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from app.core.config import settings

logger = logging.getLogger(__name__)

_MIGRATIONS: list[tuple[str, list[str]]] = [
    # m001 — identity foundation (fresh installs also get these via create_all)
    (
        "m001_identity",
        [
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                username VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)",
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                expires_at TIMESTAMPTZ
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_auth_tokens_user_id ON auth_tokens (user_id)",
        ],
    ),
    # m002 — conversation ownership + explicit thread mapping.
    # owner_id is nullable in the schema (legacy rows have no owner); the
    # bootstrap assigns them to the default user. NULL owner_id rows are
    # invisible to every user and migrated on bootstrap.
    (
        "m002_conversation_ownership",
        [
            "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS owner_id VARCHAR REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS thread_id VARCHAR",
            "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS selected_model VARCHAR",
            "CREATE INDEX IF NOT EXISTS ix_chat_sessions_owner_id ON chat_sessions (owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_chat_sessions_thread_id ON chat_sessions (thread_id)",
        ],
    ),
    # m003 — message hardening: model used, streaming status, idempotency,
    # deterministic ordering.
    (
        "m003_message_hardening",
        [
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS model VARCHAR",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'completed'",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error VARCHAR",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS request_id VARCHAR",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS sequence INTEGER",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id)",
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_sequence ON chat_messages (session_id, sequence)",
        ],
    ),
    # m004 — Memory V2 storage + governance.
    # Tables are also created by create_all on fresh DBs; this migration is
    # idempotent and data-preserving for existing DBs.
    (
        "m004_memory_v2",
        [
            "CREATE EXTENSION IF NOT EXISTS vector",
            """
            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR PRIMARY KEY,
                owner_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR NOT NULL,
                description TEXT,
                metadata JSON NOT NULL DEFAULT '{}'::json,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects (owner_id)",
            f"""
            CREATE TABLE IF NOT EXISTS memory_entities (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id VARCHAR REFERENCES projects(id) ON DELETE CASCADE,
                domain VARCHAR NOT NULL,
                statement TEXT NOT NULL,
                source VARCHAR NOT NULL,
                authority VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                importance FLOAT NOT NULL DEFAULT 0.5,
                source_conversation_id VARCHAR REFERENCES chat_sessions(id) ON DELETE SET NULL,
                content_hash VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                version INTEGER NOT NULL DEFAULT 1,
                supersedes_id VARCHAR,
                conflicts_with_id VARCHAR,
                expires_at TIMESTAMPTZ,
                last_accessed_at TIMESTAMPTZ,
                deleted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now(),
                embedding vector({settings.MEMORY_EMBEDDING_DIMENSION}),
                metadata JSON NOT NULL DEFAULT '{{}}'::json
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_user_id ON memory_entities (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_project_id ON memory_entities (project_id)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_content_hash ON memory_entities (content_hash)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_status ON memory_entities (status)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_expires_at ON memory_entities (expires_at)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_supersedes_id ON memory_entities (supersedes_id)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_conflicts_with_id ON memory_entities (conflicts_with_id)",
            "CREATE INDEX IF NOT EXISTS ix_memory_entities_user_status ON memory_entities (user_id, status)",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_entities_dedupe
            ON memory_entities (user_id, COALESCE(project_id, ''), content_hash)
            WHERE status IN ('active', 'pending')
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_memory_entities_embedding
            ON memory_entities USING hnsw (embedding vector_cosine_ops)
            """,
            """
            CREATE TABLE IF NOT EXISTS memory_events (
                id SERIAL PRIMARY KEY,
                entity_id VARCHAR NOT NULL REFERENCES memory_entities(id) ON DELETE CASCADE,
                event_type VARCHAR NOT NULL,
                actor VARCHAR,
                note TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                metadata JSON NOT NULL DEFAULT '{}'::json
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_memory_events_entity_id ON memory_events (entity_id)",
        ],
    ),
    # m005 — chat sessions link to projects (ownership chain: projects.owner_id
    # == chat_sessions.owner_id == memory_entities.user_id).
    (
        "m005_chat_session_project",
        [
            "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS project_id VARCHAR REFERENCES projects(id) ON DELETE SET NULL",
            "CREATE INDEX IF NOT EXISTS ix_chat_sessions_project_id ON chat_sessions (project_id)",
        ],
    ),
    # m006 — ingestion jobs carry the project that owns the upload so the
    # worker can tag chunk metadata with project_id (retrieval isolation).
    (
        "m006_ingestion_job_project",
        [
            "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS project_id VARCHAR REFERENCES projects(id) ON DELETE SET NULL",
            "CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_project_id ON ingestion_jobs (project_id)",
        ],
    ),
]


def run_migrations(engine: Engine) -> None:
    """Apply all pending migrations. Idempotent; safe to run on every boot."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name VARCHAR PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
        )
        applied = {
            row[0]
            for row in conn.execute(text("SELECT name FROM schema_migrations")).fetchall()
        }

    for name, statements in _MIGRATIONS:
        if name in applied:
            continue
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
            conn.execute(
                text("INSERT INTO schema_migrations (name) VALUES (:name)"), {"name": name}
            )
        logger.info("migration_applied name=%s", name)

    logger.info("migrations_ok total=%d", len(_MIGRATIONS))