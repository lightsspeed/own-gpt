from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from app.core.config import settings

# Async engine — used by the request path (FastAPI endpoints).
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine (psycopg) — used by background threads that must not touch the
# event loop (LangGraph streaming thread, migration runner). Connections are
# lazy: no server connection is opened until first use.
sync_engine = create_engine(settings.sync_database_url, echo=False, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, class_=Session, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_db():
    """Synchronous session dependency — FastAPI runs it in a worker thread."""
    with SyncSessionLocal() as session:
        yield session