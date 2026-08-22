"""
Remove orphaned documents from the knowledge store.

Orphans are documents whose chunks exist in PGVector (and Whoosh) but whose
original file is no longer present in data/uploads/. They show up in the
Knowledge Base list but cannot be opened (PDF viewer falls back to text).

Usage:
    docker compose exec web python scripts/cleanup_orphans.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import engine
from app.core.whoosh_manager import delete_from_whoosh_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("cleanup_orphans")

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"


async def main() -> None:
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT COALESCE(cmetadata->>'filename', cmetadata->>'source', 'unknown') as filename,
                   count(*) as chunks
            FROM langchain_pg_embedding
            GROUP BY COALESCE(cmetadata->>'filename', cmetadata->>'source', 'unknown')
            ORDER BY filename ASC
        """))).fetchall()

    orphans = [
        (row.filename, row.chunks)
        for row in rows
        if not (UPLOAD_DIR / row.filename).exists()
    ]
    kept = [row.filename for row in rows if (UPLOAD_DIR / row.filename).exists()]

    if not orphans:
        logger.info("No orphans found. All %d documents have originals on disk.", len(rows))
        return

    logger.info("Orphans to remove (%d):", len(orphans))
    for name, count in orphans:
        logger.info("  - %s (%d chunks)", name, count)

    async with engine.connect() as conn:
        for name, count in orphans:
            await conn.execute(text("""
                DELETE FROM langchain_pg_embedding
                WHERE cmetadata->>'filename' = :f OR cmetadata->>'source' = :f
            """), {"f": name})
            await conn.commit()
            deleted_whoosh = delete_from_whoosh_index(name)
            logger.info("Removed %s (%d chunks, %d whoosh docs)", name, count, deleted_whoosh)

    logger.info("Done. Remaining documents (%d): %s", len(kept), ", ".join(kept))


if __name__ == "__main__":
    asyncio.run(main())
