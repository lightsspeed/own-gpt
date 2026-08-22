# The existing suite is written against OpenAI model semantics (gpt-4o-mini
# allowlist, ChatOpenAI). Pin the provider BEFORE any app import so module
# scope resolution (model_config, config) matches those tests. Ollama
# behavior is covered by dedicated tests that set LLM_PROVIDER explicitly.
import os

os.environ["LLM_PROVIDER"] = "openai"

import pytest
from langchain_core.documents import Document
from app.agent.pipeline.retriever import RetrievedChunk
from app.agent.pipeline.reranker import RankedChunk
from app.agent.pipeline.intent import Intent, IntentResult


@pytest.fixture
def sample_retrieved_chunks():
    return [
        RetrievedChunk(
            document=Document(page_content=f"Content chunk {i}", metadata={"source": f"doc{i}.pdf"}),
            score=round(1.0 - i * 0.1, 4),
            source=f"doc{i}.pdf",
            collection="test_collection",
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_ranked_chunks(sample_retrieved_chunks):
    return [
        RankedChunk(
            chunk=sample_retrieved_chunks[i],
            reranker_score=round(10.0 - i * 2.0, 4),
            original_rank=i,
            reranked_rank=i,
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_intent_result():
    return IntentResult(
        intent=Intent.RAG,
        confidence=0.95,
        reason="Rule match",
        latency_ms=1.0,
        used_llm=False,
    )
