"""Hermetic unit tests for Gemini Memory V2 integration.

Covers:
- Extraction model resolution when LLM_PROVIDER=gemini
- Memory creation storing embeddings immediately
- Missing embedding backfill during search_memories
- Existing embeddings preservation
- Cross-session retrieval
- Fail-safe behavior on embedding provider errors (memory is preserved, not deleted)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.learning.extraction.extractor import resolve_extraction_model
from app.services import auth
from app.services.memory import create_memory, search_memories, get_memory, STATUS_ACTIVE
from app.models.memory import DOMAIN_SEMANTIC


def _set(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        monkeypatch.setattr(settings, k, v)


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
def user(db):
    return auth.create_user(db, "alice", "password123")


class TestExtractionModelResolution:
    def test_extraction_model_resolves_gemini(self, monkeypatch):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_MODEL="gemini-3.6-flash")
        assert resolve_extraction_model() == "gemini-3.6-flash"

    def test_extraction_model_resolves_ollama(self, monkeypatch):
        _set(monkeypatch, LLM_PROVIDER="ollama", LLM_MODEL="qwen3:8b")
        assert resolve_extraction_model() == "qwen3:8b"

    def test_extraction_model_resolves_groq(self, monkeypatch):
        _set(monkeypatch, LLM_PROVIDER="groq", GROQ_MODEL="llama-3.3-70b-versatile")
        assert resolve_extraction_model() == "llama-3.3-70b-versatile"

    def test_extraction_model_resolves_openai(self, monkeypatch):
        _set(monkeypatch, LLM_PROVIDER="openai", DEFAULT_MODEL="gpt-4o-mini")
        assert resolve_extraction_model() == "gpt-4o-mini"


class TestMemoryEmbeddingsAndRetrieval:
    def test_memory_creation_stores_embedding(self, db, user):
        fake_embed = lambda texts: [[0.5] * 1536 for _ in texts]
        mem = create_memory(
            db,
            user_id=user.id,
            statement="the user loves kubernetes and terraform",
            domain=DOMAIN_SEMANTIC,
            embed=fake_embed,
        )
        assert mem.embedding is not None
        assert len(mem.embedding) == 1536
        assert mem.status == STATUS_ACTIVE

    def test_embedding_failure_does_not_delete_memory(self, db, user):
        def failing_embed(texts):
            raise RuntimeError("API quota exceeded")

        mem = create_memory(
            db,
            user_id=user.id,
            statement="the user prefers Python over Go",
            domain=DOMAIN_SEMANTIC,
            embed=failing_embed,
        )
        # Entity preserved despite embedding failure
        assert mem is not None
        fetched = get_memory(db, mem.id, user.id)
        assert fetched is not None
        assert fetched.statement == "the user prefers python over go"
        assert fetched.embedding is None
        assert fetched.status == STATUS_ACTIVE

    def test_missing_embedding_backfill_and_cross_chat_retrieval(self, db, user):
        # 1. Create a memory without embedding (simulating prior state)
        mem = create_memory(
            db,
            user_id=user.id,
            statement="user's favorite cloud is AWS",
            domain=DOMAIN_SEMANTIC,
            embed=None,
        )
        assert mem.embedding is None

        # 2. Mock embedding provider for backfill and query search
        fake_embed = lambda texts: [[0.2] * 1536 for _ in texts]

        hits = search_memories(
            db,
            user_id=user.id,
            query="which cloud does user like?",
            embed=fake_embed,
        )

        assert len(hits) > 0
        hit_statements = [h.entity.statement for h in hits]
        assert "user's favorite cloud is aws" in hit_statements

        # Verify entity embedding was backfilled in DB
        db.refresh(mem)
        assert mem.embedding is not None
        assert len(mem.embedding) == 1536

    def test_existing_embeddings_not_overwritten_unnecessarily(self, db, user):
        vec1 = [0.1] * 1536
        fake_embed1 = lambda texts: [vec1]

        mem = create_memory(
            db,
            user_id=user.id,
            statement="user builds microservices with FastAPI",
            domain=DOMAIN_SEMANTIC,
            embed=fake_embed1,
        )
        assert list(mem.embedding) == vec1

        # Search with a different fake embedder — backfill shouldn't run since embedding is not NULL
        vec2 = [0.9] * 1536
        fake_embed2 = lambda texts: [vec2]

        hits = search_memories(
            db,
            user_id=user.id,
            query="FastAPI microservices",
            embed=fake_embed2,
        )
        assert len(hits) > 0
        db.refresh(mem)
        # Original embedding vector preserved
        assert list(mem.embedding) == vec1
