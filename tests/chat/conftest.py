"""Test setup for chat V1.1.

chat.py imports real infrastructure (LangGraph PostgresSaver pool, PGVector
store) that requires a live PostgreSQL at import time. To keep chat endpoint
tests hermetic we inject lightweight fakes into sys.modules BEFORE importing
app.api.endpoints.chat, and remove them afterwards so other test suites
(pipeline, learning, ...) still import the real modules:

- app.agent.graph                  → FakeGraph (get_state/invoke/stream)
- app.services.vector_store        → stub (only used to construct the pipeline)
- app.agent.pipeline.pipeline      → FakePipeline (no LLM, no retrieval)
- app.agent.pipeline.evidence_builder / source_validator → stubs
- app.learning.telemetry.collector → stub (no SQLite writes)
- app.evaluation.models            → stub
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.user import User

# Register every table (chat_sessions.project_id FK resolves lazily to the
# projects table — all model modules must be imported before create_all).
from app.models import chat as _chat_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import project as _project_model  # noqa: F401

_FAKE_NAMES = [
    "app.agent.graph",
    "app.services.vector_store",
    "app.agent.pipeline.pipeline",
    "app.agent.pipeline.evidence_builder",
    "app.agent.pipeline.source_validator",
    "app.learning.telemetry.collector",
    "app.evaluation.models",
    "app.learning.extraction.extractor",
]


def _fake(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


async def async_lambda(value):
    return value


# ---------------------------------------------------------------------------
# Fake agent graph — controllable via its `messages` list
# ---------------------------------------------------------------------------
class FakeState:
    def __init__(self, values: dict | None = None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakePool:
    class _Cursor:
        def execute(self, *a, **k):
            return None

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            return FakePool._Cursor()

    def connection(self):
        return FakePool._Conn()


class FakeGraph:
    """Mirrors the subset of LangGraph API chat.py uses."""

    def __init__(self, existing_messages: list[BaseMessage] | None = None):
        self.messages: list[BaseMessage] = list(existing_messages or [])
        self.stream_error: Exception | None = None
        self.partial_chunks: list[str] = []
        self.last_invoke_state: dict | None = None
        self.last_config: dict | None = None
        # Tool-call round trip: the agent proposes tool calls, the action
        # node returns ToolMessages (with .name) — mirrors the real graph.
        self.agent_tool_calls: list[dict] = []
        self.action_tool_messages: list = []
        # Opt-in usage_metadata attached to the agent update AIMessage
        # (mirrors the real graph node returning the raw provider response).
        self.agent_usage_metadata: dict | None = None

    def get_state(self, config: dict):
        return FakeState({"messages": list(self.messages)})

    def invoke(self, state: dict, config: dict) -> dict:
        self.last_invoke_state = state
        self.last_config = config
        self.messages.extend(list(state.get("messages", [])))
        self.messages.append(AIMessage(content="invoked answer"))
        return {"messages": list(self.messages)}

    def stream(self, state: dict, config: dict, stream_mode):
        self.last_invoke_state = state
        self.last_config = config
        self.messages.extend(list(state.get("messages", [])))
        for chunk in self.partial_chunks:
            yield "messages", (AIMessageChunk(content=chunk), None)
        if self.stream_error is not None:
            raise self.stream_error
        self.messages.append(AIMessage(content="".join(self.partial_chunks)))
        agent_update = AIMessage(content="")
        if self.agent_usage_metadata is not None:
            agent_update.usage_metadata = dict(self.agent_usage_metadata)
        yield "updates", {"agent": {"messages": [agent_update]}}
        if self.agent_tool_calls:
            yield "updates", {"agent": {"messages": [AIMessage(content="", tool_calls=self.agent_tool_calls)]}}
        if self.action_tool_messages:
            yield "updates", {"action": {"messages": self.action_tool_messages}}


class FakeEvidenceResult:
    evidence = []


class FakeEvidenceBuilder:
    def build(self, **kwargs):
        return FakeEvidenceResult()


class FakeValidator:
    def validate(self, **kwargs):
        return type("V", (), {
            "valid": True, "cited_count": 0, "required_count": 0,
            "unique_chunks_cited": 0, "total_citation_uses": 0,
            "warnings": [], "reason": "",
        })()


class FakePipeline:
    """Stands in for RAGPipeline: deterministic, no LLM/retrieval."""

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._evidence_builder = FakeEvidenceBuilder()
        self.tracer = type("T", (), {"store": lambda self, t: None})()
        self.source_policy = None

    def process(self, question, session_id, retriever_mode=None, filename=None, project_id=None, **kwargs):
        return FakePipelineContext(
            question=question,
            session_id=session_id,
            project_id=project_id,
            confidence=None,
            source_policy=None,
            intent_label="general",
            final_query=question,
            answer_mode="synthesis",
            context_text="",
            ranked_chunks=[],
            retrieved_chunks=[],
            answer_mode_metadata={},
            trace=FakeTrace(),
        )

    def kb_not_covered_message(self):
        return "Not covered by the knowledge base."

    def clarification_message(self):
        return "Could you clarify?"

    def validate_response(self, **kwargs):
        return None

    def run_grounding(self, *a, **k):
        return type("G", (), {
            "validations": [], "all_supported": True,
            "unsupported_count": 0, "total_count": 0,
        })()

    def record_agent_usage(self, ctx, usage_metadata=None, *, fallback_model=""):
        return None

    def finalize_trace(self, ctx, status=None):
        return None


@dataclass
class FakeTrace:
    model: str = ""
    temperature: float = 0.0
    memory_used: bool = False
    tools_used: list = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    final_response_len: int = 0
    total_latency_ms: float = 0.0

    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = []


@dataclass
class FakePipelineContext:
    question: str
    session_id: str
    confidence: Any
    source_policy: Any
    intent_label: str
    final_query: str
    answer_mode: str
    context_text: str
    ranked_chunks: list
    retrieved_chunks: list
    answer_mode_metadata: dict
    trace: Any
    project_id: Optional[str] = None


def _install_fakes() -> None:
    _fake("app.agent.graph", graph=FakeGraph(), pool=FakePool(), setup_checkpointer=lambda: None)
    fake_embeddings = type("E", (), {
        "embed_documents": lambda texts: [[0.0] * 3 for _ in texts],
        "embed_query": lambda text: [0.0] * 3,
    })()
    _fake("app.services.vector_store", vector_store=object(), embeddings=fake_embeddings, similarity_search=lambda *a, **k: [])
    _fake("app.agent.pipeline.pipeline", RAGPipeline=FakePipeline, PipelineContext=FakePipelineContext, load_pipeline_config=lambda: {})
    _fake("app.agent.pipeline.evidence_builder",
          _parse_chunk_references=lambda text: [],
          EvidenceBuilder=FakeEvidenceBuilder,
          EvidenceBuilderResult=FakeEvidenceResult)
    _fake("app.agent.pipeline.source_validator",
          SourceValidator=FakeValidator,
          SourceValidationResult=type("SVR", (), {}))
    _fake("app.learning.telemetry.collector", learning_collector=type("C", (), {
        "record": lambda self, ctx, response: "",
        "store": type("S", (), {"save_quality_report": lambda self, **k: None})(),
    })())
    _fake("app.evaluation.models", build_evaluation_result=lambda *a, **k: type("R", (), {"to_dict": lambda self: {}})())
    _fake("app.learning.extraction.extractor", schedule_extraction=lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _chat_fakes():
    for name in _FAKE_NAMES + ["app.api.endpoints.chat"]:
        sys.modules.pop(name, None)
    _install_fakes()
    yield
    for name in _FAKE_NAMES + ["app.api.endpoints.chat"]:
        sys.modules.pop(name, None)


@pytest.fixture
def chat_module():
    from app.api.endpoints import chat

    return chat


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(test_engine):
    from sqlalchemy.orm import Session

    return sessionmaker(bind=test_engine, class_=Session, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def user(db) -> User:
    from app.services import auth as auth_svc

    return auth_svc.create_user(db, "alice", "password123")


@pytest.fixture
def second_user(db) -> User:
    from app.services import auth as auth_svc

    return auth_svc.create_user(db, "bob", "password123")


@pytest.fixture
def alice_token(db, user) -> str:
    from app.services import auth as auth_svc

    return auth_svc.issue_token(db, user.id)


@pytest.fixture
def bob_token(db, second_user) -> str:
    from app.services import auth as auth_svc

    return auth_svc.issue_token(db, second_user.id)


@pytest.fixture
def client(test_engine, chat_module):
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    from app.core.database import get_sync_db

    TestingSessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_db():
        with TestingSessionLocal() as s:
            yield s

    app = FastAPI()
    app.include_router(chat_module.router)

    @app.exception_handler(HTTPException)
    async def _handle(request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            body = {"error": {"code": "error", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    app.dependency_overrides[get_sync_db] = override_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_chat_globals(monkeypatch, chat_module):
    """Isolate chat endpoint globals per test."""
    g = FakeGraph()
    monkeypatch.setattr(chat_module, "graph", g)
    monkeypatch.setattr(chat_module, "pool", FakePool())
    monkeypatch.setattr(chat_module, "_pipeline", FakePipeline())
    monkeypatch.setattr(chat_module, "_generate_session_title", async_lambda)
    monkeypatch.setattr(chat_module, "_pipeline_config", {})
    yield g


@pytest.fixture
def fake_graph(_reset_chat_globals) -> FakeGraph:
    return _reset_chat_globals