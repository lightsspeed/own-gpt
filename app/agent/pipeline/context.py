"""
Stage 2.5: Retrieval & Context Orchestrator (V3.6)

Purpose: Decide what context is needed, retrieve it through existing systems
(Memory V2, KB vector store, Web-search tool gate), normalize it into one
structured context object, deduplicate, prioritize, budget, and make it
available to the executor and synthesizer.

Key architectural invariants:
  - ContextOrchestrator DOES NOT implement database queries, Tavily direct calls,
    or new LLM abstractions itself. It delegates to the existing systems.
  - No retrieval happens for intents that do not require it (e.g. general, coding).
  - All web retrieval respects the existing tool architecture and passes through the tool gate.
  - Memory retrieval is user-scoped and project-scoped.
"""

from __future__ import annotations

import logging
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agent.pipeline.planner import Plan
from app.agent.pipeline.intent import Intent, IntentResult

logger = logging.getLogger(__name__)


# ── Context Models ────────────────────────────────────────────────────────────

@dataclass
class ContextSource:
    source_id: str
    source_type: str        # memory | knowledge | document | web
    title: str
    content: str
    score: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedContext:
    query: str
    sources: list[ContextSource]
    memory_context: str = ""
    knowledge_context: str = ""
    web_context: str = ""
    document_context: str = ""
    has_evidence: bool = False
    source_count: int = 0
    grounding_required: bool = False
    retrieved_chunks: list = field(default_factory=list)
    ranked_chunks: list = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Produce a clean, deterministic representation suitable for the LLM prompt."""
        parts = []
        if self.memory_context.strip():
            parts.append(f"[MEMORY]\n{self.memory_context.strip()}")
        if self.knowledge_context.strip():
            parts.append(f"[KNOWLEDGE]\n{self.knowledge_context.strip()}")
        if self.web_context.strip():
            parts.append(f"[WEB]\n{self.web_context.strip()}")
        if self.document_context.strip():
            parts.append(f"[DOCUMENT]\n{self.document_context.strip()}")
        return "\n\n".join(parts)


@dataclass
class ContextRequest:
    needs_memory: bool
    needs_knowledge: bool
    needs_web: bool
    needs_document: bool
    query: str


# ── Context Orchestrator ──────────────────────────────────────────────────────

class ContextOrchestrator:
    """
    Orchestrates controlled context acquisition before executor/synthesis runs.
    """

    MAX_CONTEXT_SOURCES = 20
    MAX_CONTEXT_CHARS = 30000

    def __init__(self, vector_retriever=None, hybrid_retriever=None, reranker=None):
        self.vector_retriever = vector_retriever
        self.hybrid_retriever = hybrid_retriever
        self.reranker = reranker

    def build_request(
        self,
        question: str,
        intent: Intent | IntentResult,
        plan: Optional[Plan],
    ) -> ContextRequest:
        """Determine what context is needed based on intent or plan."""
        # Normalize intent to raw Intent Enum
        intent_enum = intent.intent if isinstance(intent, IntentResult) else intent
        
        needs_memory = False
        needs_knowledge = False
        needs_web = False
        needs_document = False

        q_lower = question.lower()

        if intent_enum == Intent.GENERAL:
            pass
        elif intent_enum == Intent.CODING:
            pass
        elif intent_enum == Intent.MEMORY:
            needs_memory = True
        elif intent_enum == Intent.KNOWLEDGE:
            needs_knowledge = True
        elif intent_enum == Intent.WEB:
            needs_web = True
        elif intent_enum == Intent.DOCUMENT:
            needs_document = True
        elif intent_enum == Intent.REASONING:
            # Check keywords to decide what reasoning context we need
            if any(k in q_lower for k in ["pdf", "file", "document", "uploaded"]):
                needs_document = True
            elif any(k in q_lower for k in ["my", "remember", "favorite", "hobby", "like"]):
                needs_memory = True
            else:
                # Default is no RAG context for reasoning unless it references resources
                pass
        elif intent_enum == Intent.MULTI_INTENT and plan:
            # Scan plan steps to collect needed context types
            for step in plan.steps:
                if step.action == "memory":
                    needs_memory = True
                elif step.action in ("knowledge", "search_knowledge_base"):
                    needs_knowledge = True
                elif step.action == "document":
                    needs_document = True
                elif step.action == "web_search":
                    needs_web = True
        else:
            # Defensive fallback
            if "remember" in q_lower or "my favorite" in q_lower:
                needs_memory = True
            if "search" in q_lower or "latest" in q_lower or "news" in q_lower:
                needs_web = True
            if "document" in q_lower or "pdf" in q_lower:
                needs_document = True

        return ContextRequest(
            needs_memory=needs_memory,
            needs_knowledge=needs_knowledge,
            needs_web=needs_web,
            needs_document=needs_document,
            query=question,
        )

    def retrieve(
        self,
        request: ContextRequest,
        pipeline_context: object,
    ) -> RetrievedContext:
        """Retrieve and normalize contexts based on context request requirements."""
        user_id = getattr(pipeline_context, "user_id", "") or ""
        project_id = getattr(pipeline_context, "project_id", None)
        filename = getattr(pipeline_context, "filename", None)

        sources: list[ContextSource] = []
        retrieved_chunks_acc = []
        ranked_chunks_acc = []

        # ── 1. Memory Retrieval ───────────────────────────────────────────────
        if request.needs_memory and user_id:
            try:
                from app.services.embeddings import build_embedding_provider
                from app.services.memory import search_memories
                from app.core.database import SyncSessionLocal

                provider = build_embedding_provider()
                with SyncSessionLocal() as db:
                    hits = search_memories(
                        db,
                        user_id=user_id,
                        query=request.query,
                        project_id=project_id,
                        k=5,
                        max_tokens=400,
                        embed=provider.embed if provider else None,
                    )

                for hit in hits:
                    sources.append(ContextSource(
                        source_id=hit.entity.id,
                        source_type="memory",
                        title="User Memory",
                        content=hit.entity.statement,
                        score=hit.score,
                        metadata={
                            "domain": hit.entity.domain,
                            "authority": hit.entity.authority,
                            "confidence": hit.entity.confidence,
                        }
                    ))
            except Exception as e:
                logger.error("orchestrator.memory_recall_failed error=%s", e)

        # ── 2. Knowledge Retrieval ────────────────────────────────────────────
        if request.needs_knowledge:
            retriever = self.hybrid_retriever or self.vector_retriever
            if retriever:
                try:
                    chunks, _ = retriever.retrieve(request.query, filename=filename, project_id=project_id)
                    retrieved_chunks_acc.extend(chunks)
                    
                    if self.reranker and chunks:
                        ranked_chunks = self.reranker.rerank(request.query, chunks)
                    else:
                        ranked_chunks = chunks
                    ranked_chunks_acc.extend(ranked_chunks)

                    for rc in ranked_chunks:
                        # Handles both RerankedChunk wrapper and plain RetrievedChunk
                        chunk = getattr(rc, "chunk", rc)
                        score = getattr(rc, "reranker_score", getattr(rc, "score", 0.0))
                        
                        sources.append(ContextSource(
                            source_id=chunk.chunk_id or f"kb-{hash(chunk.document.page_content)}",
                            source_type="knowledge",
                            title=chunk.source,
                            content=chunk.document.page_content,
                            score=score,
                            metadata={"collection": chunk.collection, "provenance": chunk.provenance}
                        ))
                except Exception as e:
                    logger.error("orchestrator.knowledge_recall_failed error=%s", e)

        # ── 3. Document Retrieval ─────────────────────────────────────────────
        if request.needs_document:
            retriever = self.vector_retriever or self.hybrid_retriever
            if retriever:
                try:
                    chunks, _ = retriever.retrieve(request.query, filename=filename, project_id=project_id)
                    retrieved_chunks_acc.extend(chunks)
                    
                    if self.reranker and chunks:
                        ranked_chunks = self.reranker.rerank(request.query, chunks)
                    else:
                        ranked_chunks = chunks
                    ranked_chunks_acc.extend(ranked_chunks)

                    for rc in ranked_chunks:
                        chunk = getattr(rc, "chunk", rc)
                        score = getattr(rc, "reranker_score", getattr(rc, "score", 0.0))

                        sources.append(ContextSource(
                            source_id=chunk.chunk_id or f"doc-{hash(chunk.document.page_content)}",
                            source_type="document",
                            title=chunk.source,
                            content=chunk.document.page_content,
                            score=score,
                            metadata={"collection": chunk.collection, "provenance": chunk.provenance}
                        ))
                except Exception as e:
                    logger.error("orchestrator.document_recall_failed error=%s", e)

        # ── 4. Web Retrieval ──────────────────────────────────────────────────
        if request.needs_web:
            try:
                from app.agent.tool_gate import request_tool_execution
                execution = request_tool_execution("web_search", {"query": request.query})
                if execution.status in ("executed", "allowed") and execution.result:
                    sources.append(ContextSource(
                        source_id=f"web-{hash(execution.result)}",
                        source_type="web",
                        title="Web Search Results",
                        content=execution.result,
                        score=1.0,
                        metadata={"status": execution.status}
                    ))
            except Exception as e:
                logger.error("orchestrator.web_recall_failed error=%s", e)

        # ── 5. Context Normalization, Deduplication & Priority ────────────────
        seen_ids = set()
        deduped_sources: list[ContextSource] = []
        for src in sources:
            if src.source_id not in seen_ids:
                seen_ids.add(src.source_id)
                deduped_sources.append(src)

        # Priority ranks: lower values run higher
        priority_order = {"memory": 0, "document": 1, "knowledge": 2, "web": 3}

        def get_priority(src: ContextSource) -> int:
            if request.needs_document and src.source_type == "document":
                return -1
            if request.needs_web and src.source_type == "web":
                return -1
            return priority_order.get(src.source_type, 99)

        sorted_sources = sorted(deduped_sources, key=get_priority)

        # ── 6. Truncation and Budgeting ───────────────────────────────────────
        accepted_sources: list[ContextSource] = []
        total_chars = 0
        for src in sorted_sources:
            if len(accepted_sources) >= self.MAX_CONTEXT_SOURCES:
                break
            if total_chars + len(src.content) > self.MAX_CONTEXT_CHARS:
                # Truncate clean at word/character limit without corrupting other sources
                space_left = self.MAX_CONTEXT_CHARS - total_chars
                if space_left > 10:
                    truncated = src.content[:space_left] + "\n[Content truncated due to context limit]"
                    src.content = truncated
                    accepted_sources.append(src)
                    total_chars += len(truncated)
                break
            accepted_sources.append(src)
            total_chars += len(src.content)

        # Group accepted sources back into target fields
        memory_parts = [s.content for s in accepted_sources if s.source_type == "memory"]
        doc_parts = [f"Source: {s.title}\n{s.content}" for s in accepted_sources if s.source_type == "document"]
        kb_parts = [f"Source: {s.title}\n{s.content}" for s in accepted_sources if s.source_type == "knowledge"]
        web_parts = [s.content for s in accepted_sources if s.source_type == "web"]

        memory_context = ""
        if memory_parts:
            facts_list = "\n".join(f"- {c}" for c in memory_parts)
            memory_context = (
                "Long-Term Memory:\n"
                "You have learned the following persistent facts about the user from previous sessions. "
                "Use these to personalize your responses:\n"
                f"{facts_list}"
            )

        document_context = "\n\n--─\n\n".join(doc_parts)
        knowledge_context = "\n\n--─\n\n".join(kb_parts)
        web_context = "\n\n".join(web_parts)

        has_evidence = len(accepted_sources) > 0
        grounding_required = (
            request.needs_memory or
            request.needs_knowledge or
            request.needs_web or
            request.needs_document
        )

        return RetrievedContext(
            query=request.query,
            sources=accepted_sources,
            memory_context=memory_context,
            knowledge_context=knowledge_context,
            web_context=web_context,
            document_context=document_context,
            has_evidence=has_evidence,
            source_count=len(accepted_sources),
            grounding_required=grounding_required,
            retrieved_chunks=retrieved_chunks_acc,
            ranked_chunks=ranked_chunks_acc,
        )
