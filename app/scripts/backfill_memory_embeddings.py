"""Safe one-time backfill utility for memory_entities embeddings.

Finds active memory_entities with NULL embeddings, generates vectors using
the configured Memory V2 embedding provider (e.g. Gemini Embedding 2),
and stores them in the 1536-dimensional embedding column.

Features:
- Idempotent: skips rows that already have embeddings.
- Safe: never deletes or mutates statements, status, or history.
- Reports detailed success/failure/skip counts.
"""

from __future__ import annotations

import logging
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select, update, text
from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.memory import MemoryEntity, STATUS_ACTIVE
from app.services.embeddings import build_embedding_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("backfill_memory_embeddings")


def run_backfill(batch_size: int = 50) -> dict[str, int]:
    """Backfill missing embeddings for active memory_entities."""
    stats = {"total_processed": 0, "succeeded": 0, "failed": 0, "skipped_already_embedded": 0}

    provider = build_embedding_provider()
    if provider is None:
        logger.error("Embedding provider is 'none' or unavailable. Cannot run backfill.")
        return stats

    logger.info(
        "Starting memory embedding backfill using provider=%s model=%s dim=%d",
        settings.MEMORY_EMBEDDING_PROVIDER,
        settings.MEMORY_EMBEDDING_MODEL,
        settings.MEMORY_EMBEDDING_DIMENSION,
    )

    with SyncSessionLocal() as db:
        # Check total active and total with NULL embeddings
        total_active = db.execute(
            select(MemoryEntity).where(MemoryEntity.status == STATUS_ACTIVE)
        ).scalars().all()

        missing_entities = [e for e in total_active if e.embedding is None]
        stats["skipped_already_embedded"] = len(total_active) - len(missing_entities)

        logger.info(
            "Found %d total active memory entities: %d need embeddings, %d already embedded",
            len(total_active),
            len(missing_entities),
            stats["skipped_already_embedded"],
        )

        for i in range(0, len(missing_entities), batch_size):
            batch = missing_entities[i : i + batch_size]
            statements = [e.statement for e in batch]

            try:
                vectors = provider.embed(statements)
                for entity, vec in zip(batch, vectors):
                    if len(vec) != settings.MEMORY_EMBEDDING_DIMENSION:
                        logger.error(
                            "Dimension mismatch for entity %s: expected %d, got %d",
                            entity.id,
                            settings.MEMORY_EMBEDDING_DIMENSION,
                            len(vec),
                        )
                        stats["failed"] += 1
                        continue

                    # Direct update to avoid ORM mutation issues with pgvector
                    db.execute(
                        update(MemoryEntity)
                        .where(MemoryEntity.id == entity.id)
                        .values(embedding=vec)
                    )
                    stats["succeeded"] += 1
                    stats["total_processed"] += 1

                db.commit()
                logger.info("Processed batch of %d entities successfully", len(batch))
            except Exception as exc:
                db.rollback()
                stats["failed"] += len(batch)
                logger.error("Failed to generate embeddings for batch: %s", exc)

    logger.info("Backfill completed. Summary: %s", stats)
    return stats


if __name__ == "__main__":
    run_backfill()
