import logging
import traceback
import re
import asyncio
import json
import time
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session, sessionmaker

from app.agent.graph import graph, pool
from app.evaluation.models import build_evaluation_result
from app.core.database import get_sync_db
from app.core.config import settings
from app.core.model_config import resolve_model, validate_temperature, ModelConfigError
from app.api.deps import get_current_user, api_error
from app.services import chat_persistence as store
from app.agent.pipeline import RAGPipeline, PipelineContext, load_pipeline_config
from app.agent.pipeline.evidence_builder import _parse_chunk_references
from app.agent.pipeline.source_validator import SourceValidator
from app.services.vector_store import vector_store, embeddings as _embeddings
from app.learning.telemetry.collector import learning_collector
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from datetime import datetime
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Singleton RAG pipeline — initialized once with config + store
# ---------------------------------------------------------------------------
_pipeline_config = load_pipeline_config()
# Lazy-load Whoosh BM25 retriever for hybrid search
try:
    from app.core.whoosh_manager import get_whoosh_retriever
    _bm25 = get_whoosh_retriever()
    logger.info("rag_pipeline_hybrid_enabled bm25_docs=%d", _bm25.doc_count)
except Exception:
    _bm25 = None
    logger.info("rag_pipeline_hybrid_disabled (no whoosh index)")
_pipeline = RAGPipeline(
    vector_store=vector_store,
    bm25_retriever=_bm25,
    redis_url=settings.REDIS_URL,
    config=_pipeline_config,
    embed_fn=_embeddings.embed_documents,
)


def _count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    request_id: Optional[str] = None
    system_prompt: Optional[str] = None
    active_tools: Optional[dict[str, bool]] = None
    document: Optional[str] = None


class ResourceItem(BaseModel):
    type: str
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    resources: List[ResourceItem] = []
    answer_mode: str = "grounded"
    record_id: str = ""


class HistoryMessage(BaseModel):
    role: str
    content: str
    resources: List[ResourceItem] = []
    model: Optional[str] = None
    status: str = "completed"


class HistoryResponse(BaseModel):
    session_id: str
    messages: List[HistoryMessage]


class SessionListItem(BaseModel):
    id: str
    title: str
    is_pinned: bool = False
    selected_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    project_id: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]


class SearchResultItem(BaseModel):
    session_id: str
    session_title: str
    match_type: str  # 'title' | 'message'
    preview: str
    timestamp: datetime


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int


search_logger = logging.getLogger("search")


def _flatten_content(content) -> str:
    """Convert structured content (list of content blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "image_url":
                    parts.append("[Image]")
                else:
                    parts.append(str(block))
            else:
                parts.append(str(block))
        return "\n".join(p.strip() for p in parts if p.strip())
    return str(content)


def _extract_tool_names(messages_subset) -> List[str]:
    tools_used = []
    for msg in messages_subset:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name") or tc.get("function", {}).get("name", "")
                if name:
                    tools_used.append(name)
    return tools_used


async def _generate_session_title(message: str) -> str:
    try:
        from app.core.llm_provider import build_llm
        title_model = build_llm(model=settings.DEFAULT_MODEL, temperature=0)
        res = await title_model.ainvoke([
            SystemMessage(content="Summarize the user's query in 3 to 5 words as a conversation title. Output ONLY the title, no punctuation, no quotes, no extra text."),
            HumanMessage(content=message)
        ])
        title = res.content.strip().replace('"', '').replace("'", "")
        return title[:50]
    except Exception as e:
        logger.error(f"Error generating session title: {e}")
        return message[:30] + "..." if len(message) > 30 else message


def _run_pipeline(message: str, session_id: str, retriever_mode: Optional[str] = None, document: Optional[str] = None) -> PipelineContext:
    """Run the pre-processing pipeline. Returns context with intent, route, context_text."""
    return _pipeline.process(question=message, session_id=session_id, retriever_mode=retriever_mode, filename=document)


def _post_process(ctx: PipelineContext, response: str, new_messages: list, model: str = "", temperature: float = 0.0) -> str:
    """Validate response, store trace, and record telemetry. Returns the learning record_id."""
    if ctx.trace:
        ctx.trace.model = model
        ctx.trace.temperature = temperature
    ctx.trace.memory_used = True  # memory is always checked in call_model
    ctx.trace.tools_used = _extract_tool_names(new_messages)
    ctx.trace.prompt_tokens = _count_tokens(ctx.question)
    ctx.trace.completion_tokens = _count_tokens(response)

    _pipeline.validate_response(question=ctx.question, response=response, ctx=ctx)

    # Record learning telemetry (fire-and-forget, never blocks the response)
    return learning_collector.record(ctx, response)


def _persist_quality(session_id: str, question: str, answer_mode: str, validation_result, claim_data: list[dict], record_id: str) -> None:
    """Persist citation + grounding validation as an answer-quality report."""
    try:
        supported = sum(1 for c in claim_data if c.get("supported"))
        learning_collector.store.save_quality_report({
            "record_id": record_id,
            "session_id": session_id,
            "question": question[:500],
            "answer_mode": answer_mode,
            "citation_valid": validation_result.valid,
            "cited": validation_result.cited_count,
            "required": validation_result.required_count,
            "unique_chunks": validation_result.unique_chunks_cited,
            "total_uses": validation_result.total_citation_uses,
            "warnings": validation_result.warnings,
            "reason": validation_result.reason,
            "claims_total": len(claim_data),
            "claims_supported": supported,
            "claims_unsupported": len(claim_data) - supported,
            "claims": claim_data,
        })
    except Exception as exc:
        logger.warning("quality_persist_failed error=%s", exc)


def _resolve_generation_params(request: ChatRequest) -> tuple[str, float]:
    """Validate model + temperature against the server allowlist."""
    try:
        model = resolve_model(request.model)
        temperature = validate_temperature(request.temperature)
        return model, temperature
    except ModelConfigError as e:
        raise api_error(400, "invalid_generation_config", str(e))


def _load_conversation(db: Session, user: User, session_id: str, require: bool = True):
    """Owned conversation lookup. 404 for both missing and foreign
    conversations — never reveal that a conversation exists."""
    conv = store.get_conversation(db, session_id, user.id)
    if conv is None and require:
        raise api_error(404, "conversation_not_found", "Conversation not found")
    return conv


def _checkpoint_len(existing_state) -> int:
    return len(existing_state.values.get("messages", [])) if existing_state and existing_state.values else 0


def _checkpoint_messages(existing_state):
    if existing_state and existing_state.values:
        return existing_state.values.get("messages", [])
    return []


def _ensure_backfilled(db: Session, conv, checkpoint_messages) -> None:
    """Idempotently backfill legacy conversations from checkpoint state."""
    if not checkpoint_messages:
        return
    try:
        store.backfill_messages_from_checkpoint(db, conv, checkpoint_messages)
    except Exception as exc:
        logger.warning("backfill_failed conversation=%s error=%s", conv.id, exc)


# ---------------------------------------------------------------------------
# POST /chat  – send a message (non-streaming); app DB is the chat history
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    model, temperature = _resolve_generation_params(request)
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        existing_state = await asyncio.to_thread(graph.get_state, config)
        existing_len = _checkpoint_len(existing_state)

        # Conversation (owned) — create if missing
        conv = _load_conversation(db, user, request.session_id, require=False)
        if conv is None:
            if store.get_conversation_any_owner(db, request.session_id) is not None:
                raise api_error(404, "not_found", "Session not found")
            title = await _generate_session_title(request.message)
            conv = store.create_conversation(db, user, request.session_id, title=title, selected_model=model)
        else:
            if conv.selected_model != model:
                store.update_conversation(db, conv, selected_model=model)
            store.touch_conversation(db, conv)

        # Backfill legacy history from checkpoints (idempotent, count==0 only)
        _ensure_backfilled(db, conv, _checkpoint_messages(existing_state))

        # Idempotency: identical request_id retry → reject before double work
        if request.request_id and store.get_user_message_by_request_id(db, conv.id, request.request_id):
            raise api_error(409, "duplicate_request", "A message with this request_id already exists")

        # Persist the user message BEFORE graph execution
        store.persist_user_message(db, conv, request.message, model, request_id=request.request_id)

        # ── Stage 1-7: Run pre-processing pipeline ────────────────────────────
        ctx = _run_pipeline(request.message, request.session_id, document=request.document)

        # Check if we should short-circuit with clarification
        if ctx.confidence and ctx.confidence.decision == "clarification" and not request.document:
            if not ctx.ranked_chunks:
                response = _pipeline.kb_not_covered_message()
            else:
                response = _pipeline.clarification_message()
            if ctx.trace:
                ctx.trace.final_response_len = len(response)
                ctx.trace.total_latency_ms = 0.0
            if _pipeline_config.get("trace_enabled", True):
                _pipeline.tracer.store(ctx.trace)
            store.persist_assistant_message(db, conv, response, model, status=store.MESSAGE_STATUS_COMPLETED)
            return ChatResponse(
                session_id=request.session_id,
                response=response,
                resources=[],
                answer_mode=ctx.answer_mode,
            )

        # Build initial state with pipeline context
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "system_prompt": request.system_prompt or "",
            "answer_mode_directive": ctx.source_policy.contract.system_directive if ctx.source_policy else "",
            "intent": ctx.intent_label,
            "rewritten_query": ctx.final_query,
            "pipeline_context": ctx.context_text,
            "answer_mode": ctx.answer_mode,
            "session_id": request.session_id,
            "user_id": user.id,
            "project_id": conv.project_id or "",
            "model": model,
            "temperature": temperature,
        }

        final_state = await asyncio.to_thread(graph.invoke, initial_state, config)

        new_messages = final_state["messages"][existing_len:]
        last_message = final_state["messages"][-1]
        response = last_message.content
        if not isinstance(response, str):
            response = _flatten_content(response)

        # Filter resources based on answer mode and evidence builder
        evidence_result = _pipeline._evidence_builder.build(
            response_text=response,
            ranked_chunks=ctx.ranked_chunks,
            source_policy=ctx.source_policy,
            answer_mode=ctx.answer_mode,
            answer_mode_metadata=ctx.answer_mode_metadata,
        )
        resources = [
            ResourceItem(type=e.source_type, title=e.title, url=e.url, snippet=e.chunk[:180] if e.chunk else None)
            for e in evidence_result.evidence
        ]

        # Citation contract check
        ref_indices = _parse_chunk_references(response)
        validator = SourceValidator()
        validation_result = validator.validate(
            ref_indices=ref_indices,
            total_chunks=len(ctx.ranked_chunks),
            mode=ctx.source_policy,
        )
        logger.info(
            "citation_check valid=%s cited=%d required=%d reason=%s",
            validation_result.valid,
            validation_result.cited_count,
            validation_result.required_count,
            validation_result.reason,
        )

        # Grounding validation (claim-level)
        claim_data: list[dict] = []
        if ctx.ranked_chunks and ctx.source_policy and ctx.source_policy.contract.requires_evidence:
            grounding = _pipeline.run_grounding(response, ctx)
            for v in grounding.validations:
                claim_data.append({
                    "id": v.claim.id,
                    "text": v.claim.text,
                    "supported": v.supported,
                    "best_score": v.best_score,
                    "threshold": v.threshold,
                    "best_chunk_idx": v.best_chunk_idx,
                    "document": v.document_name,
                })
            if not grounding.all_supported:
                logger.warning(
                    "grounding_unsupported session_id=%s unsupported=%d total=%d threshold=%.2f",
                    request.session_id,
                    grounding.unsupported_count,
                    grounding.total_count,
                    grounding.validations[0].threshold if grounding.validations else 0,
                )

        # ── Stages 8-9: Validate response + store trace ───────────────────────
        record_id = _post_process(ctx, response, new_messages, model=model, temperature=temperature)
        if record_id:
            _persist_quality(
                session_id=request.session_id,
                question=request.message,
                answer_mode=ctx.answer_mode,
                validation_result=validation_result,
                claim_data=claim_data,
                record_id=record_id,
            )

        # Persist the completed assistant message (exactly once, final content)
        store.persist_assistant_message(db, conv, response, model, status=store.MESSAGE_STATUS_COMPLETED)

        # Detached memory extraction — fire-and-forget, never on the request path
        from app.learning.extraction.extractor import schedule_extraction
        schedule_extraction(request.session_id, user.id, conv.project_id)

        return ChatResponse(
            session_id=request.session_id,
            response=response,
            resources=resources,
            answer_mode=ctx.answer_mode,
            record_id=record_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# GET /chat/sessions  – list the CURRENT user's conversations
# ---------------------------------------------------------------------------
@router.get("/chat/sessions", response_model=SessionListResponse)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    try:
        sessions = store.list_conversations(db, user)
        return SessionListResponse(
            sessions=[
                SessionListItem(
                    id=s.id,
                    title=s.title,
                    is_pinned=s.is_pinned,
                    selected_model=s.selected_model,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                ) for s in sessions
            ]
        )
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# GET /chat/search  – search titles + message content, scoped to the user
# ---------------------------------------------------------------------------
@router.get("/chat/search", response_model=SearchResponse)
async def search_conversations(
    q: str = "",
    type: str = "all",
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    try:
        query = q.strip()
        if not query:
            return SearchResponse(query="", results=[], total=0)

        results: List[SearchResultItem] = []

        # Search session titles (owned only)
        convs = store.list_conversations(db, user, limit=100)
        for s in convs:
            if query.lower() in (s.title or "").lower():
                preview = (s.title or "")[:120]
                idx = preview.lower().index(query.lower())
                start = max(0, idx - 30)
                end = min(len(preview), idx + len(query) + 30)
                preview = ("…" if start > 0 else "") + preview[start:end] + ("…" if end < len(preview) else "")
                results.append(SearchResultItem(
                    session_id=s.id,
                    session_title=s.title,
                    match_type="title",
                    preview=preview,
                    timestamp=s.updated_at or s.created_at,
                ))
                if len(results) >= limit:
                    break

        # Search message content via the application chat database — never
        # by parsing LangGraph checkpoint blobs.
        if len(results) < limit:
            for msg in store.search_messages(db, user, query, limit=limit * 2):
                if len(results) >= limit:
                    break
                if any(r.session_id == msg.session_id for r in results):
                    continue
                conv = next((c for c in convs if c.id == msg.session_id), None)
                if conv is None:
                    continue
                content = msg.content or ""
                if query.lower() in content.lower():
                    idx = content.lower().index(query.lower())
                    start = max(0, idx - 60)
                    end = min(len(content), idx + len(query) + 60)
                    preview = ("…" if start > 0 else "") + content[start:end] + ("…" if end < len(content) else "")
                    results.append(SearchResultItem(
                        session_id=msg.session_id,
                        session_title=conv.title,
                        match_type="message",
                        preview=preview,
                        timestamp=msg.created_at or conv.updated_at or conv.created_at,
                    ))

        search_logger.info("search query=%s hits=%d", query, len(results))
        return SearchResponse(query=query, results=results[:limit], total=len(results))
    except Exception as e:
        logger.error("Search endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# PATCH /chat/sessions/{session_id}  – update title / pin state (owned only)
# ---------------------------------------------------------------------------
@router.patch("/chat/sessions/{session_id}", response_model=SessionListItem)
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    try:
        conv = _load_conversation(db, user, session_id)
        body = request.model_dump(exclude_unset=True)
        if "project_id" in body:
            # Ownership chain: the project must belong to the requesting
            # user; the FK proves existence, not ownership.
            try:
                from app.services.memory import resolve_owned_project
                resolve_owned_project(db, body["project_id"], user.id)
            except ValueError:
                raise api_error(404, "project_not_found", "Project not found")
            store.update_conversation(db, conv, project_id=body["project_id"])
        store.update_conversation(db, conv, title=request.title, is_pinned=request.is_pinned)
        return SessionListItem(
            id=conv.id,
            title=conv.title,
            is_pinned=conv.is_pinned,
            selected_model=conv.selected_model,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# GET /chat/{session_id}/history  – load messages from application persistence
# ---------------------------------------------------------------------------
@router.get("/chat/{session_id}/history", response_model=HistoryResponse)
async def get_history(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    try:
        conv = _load_conversation(db, user, session_id, require=False)

        # Legacy conversations: backfill chat_messages from checkpoint state
        # (idempotent) so the UI never parses checkpoint blobs.
        existing_state = await asyncio.to_thread(graph.get_state, {"configurable": {"thread_id": session_id}})
        checkpoint_msgs = _checkpoint_messages(existing_state)
        if conv is None:
            # No app row yet: adopt the legacy checkpoint conversation for the
            # requesting user (404 if the id is owned by someone else).
            if store.get_conversation_any_owner(db, session_id) is not None:
                raise api_error(404, "not_found", "Session not found")
            first = next((m.content for m in checkpoint_msgs if m), session_id)
            conv = store.create_conversation(db, user, session_id, title=str(first)[:60])
        _ensure_backfilled(db, conv, checkpoint_msgs)

        messages: List[HistoryMessage] = []
        for m in store.list_messages(db, conv.id):
            if m.role not in ("user", "assistant"):
                continue
            kwargs = m.additional_kwargs or {}
            resources = [
                ResourceItem(**r) for r in kwargs.get("resources", [])
                if isinstance(r, dict) and r.get("title")
            ]
            messages.append(HistoryMessage(
                role=m.role,
                content=m.content,
                resources=resources,
                model=m.model,
                status=m.status,
            ))

        return HistoryResponse(session_id=session_id, messages=messages)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("History endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# DELETE /chat/sessions/{session_id}  – owned only; removes app rows + checkpoints
# ---------------------------------------------------------------------------
@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    try:
        conv = _load_conversation(db, user, session_id)
        store.delete_conversation(db, conv)  # cascades chat_messages

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (conv.thread_id,))
                    cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (conv.thread_id,))
                    cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (conv.thread_id,))
        except Exception as checkpoint_err:
            logger.warning(f"Failed to clean checkpointer tables for {session_id}: {checkpoint_err}")

        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# POST /chat/stream  – SSE streaming with reliable persistence
#
# Lifecycle:
#   validate user + ownership → persist user message → backfill (legacy) →
#   run graph in a worker thread streaming tokens to the client while
#   accumulating the final content server-side → on success persist the
#   completed assistant message exactly once → on failure emit error and
#   persist a failed/partial assistant row (never a fake success).
# ---------------------------------------------------------------------------
@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    model, temperature = _resolve_generation_params(request)
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        existing_state = await asyncio.to_thread(graph.get_state, config)
        existing_len = _checkpoint_len(existing_state)

        # Conversation (owned) — create if missing
        conv = _load_conversation(db, user, request.session_id, require=False)
        if conv is None:
            if store.get_conversation_any_owner(db, request.session_id) is not None:
                raise api_error(404, "not_found", "Session not found")
            title = await _generate_session_title(request.message)
            conv = store.create_conversation(db, user, request.session_id, title=title, selected_model=model)
        else:
            if conv.selected_model != model:
                store.update_conversation(db, conv, selected_model=model)
            store.touch_conversation(db, conv)

        _ensure_backfilled(db, conv, _checkpoint_messages(existing_state))

        # Idempotency: reject duplicate logical requests before any work
        if request.request_id and store.get_user_message_by_request_id(db, conv.id, request.request_id):
            raise api_error(409, "duplicate_request", "A message with this request_id already exists")

        # Persist the user message BEFORE graph execution
        store.persist_user_message(db, conv, request.message, model, request_id=request.request_id)

        # ── Stage 1-7: Run pre-processing pipeline ────────────────────────────
        ctx = _run_pipeline(request.message, request.session_id, document=request.document)

        # Override answer_mode based on active_tools (frontend tool toggles)
        at = request.active_tools or {}
        web_on = at.get("web", False)
        kb_on = at.get("kb", True)
        if web_on and not kb_on:
            ctx.answer_mode = "web"
            ctx.context_text = ""
            ctx.ranked_chunks = []
        elif not web_on and kb_on:
            ctx.answer_mode = "grounded"
        elif not web_on and not kb_on:
            ctx.answer_mode = "synthesis"
            ctx.context_text = ""
            ctx.ranked_chunks = []

        # Short-circuit for clarification (never when scoped to a document — the scope is known)
        if ctx.confidence and ctx.confidence.decision == "clarification" and not request.document:
            msg = (
                _pipeline.kb_not_covered_message()
                if not ctx.ranked_chunks
                else _pipeline.clarification_message()
            )
            if ctx.trace:
                ctx.trace.final_response_len = len(msg)
                ctx.trace.total_latency_ms = 0.0
            if _pipeline_config.get("trace_enabled", True):
                _pipeline.tracer.store(ctx.trace)
            store.persist_assistant_message(db, conv, msg, model, status=store.MESSAGE_STATUS_COMPLETED)

            async def clarify_generator():
                yield f"data: {json.dumps({'type': 'content', 'content': msg})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                clarify_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        human_message = HumanMessage(content=request.message)

        base_directive = ctx.source_policy.contract.system_directive if ctx.source_policy else ""
        if request.document:
            base_directive += (
                f"\n\nDOCUMENT SCOPE: The user is viewing the document '{request.document}' in the Knowledge Base."
                " Answer ONLY using content from that document. If the information is not in this document,"
                " say so clearly — do not use other knowledge base documents."
            )

        initial_state = {
            "messages": [human_message],
            "system_prompt": request.system_prompt or "",
            "answer_mode_directive": base_directive,
            "intent": ctx.intent_label,
            "rewritten_query": ctx.final_query,
            "pipeline_context": ctx.context_text,
            "answer_mode": ctx.answer_mode,
            "session_id": request.session_id,
            "user_id": user.id,
            "project_id": conv.project_id or "",
            "model": model,
            "temperature": temperature,
        }

        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        # Session factory bound to THIS request's engine: the stream thread
        # must never touch the global app engine (unbounded connect time),
        # and tests overriding the dependency get their engine here too.
        request_session_factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)

        def stream_in_thread():
            accumulated: list[str] = []
            persisted = False

            def persist_assistant(content: str, status: str, error: str | None = None) -> None:
                nonlocal persisted
                if persisted:
                    return
                try:
                    with request_session_factory() as sdb:
                        store.persist_assistant_message(sdb, conv, content, model, status=status, error=error)
                    persisted = True
                except Exception as exc:
                    logger.error("assistant_persist_failed conversation=%s error=%s", conv.id, exc)

            try:
                for stream_mode, stream_event in graph.stream(
                    initial_state,
                    config=config,
                    stream_mode=["messages", "updates"]
                ):
                    if stream_mode == "messages":
                        msg_chunk, _ = stream_event
                        if hasattr(msg_chunk, "content") and msg_chunk.content and msg_chunk.type == "AIMessageChunk":
                            chunk = msg_chunk.content
                            if isinstance(chunk, list):
                                chunk = _flatten_content(chunk)
                            accumulated.append(chunk)
                            loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "content", "content": chunk}))
                    elif stream_mode == "updates":
                        for node_name, node_output in stream_event.items():
                            if node_name == "tools" and isinstance(node_output, dict):
                                for m in node_output.get("messages", []):
                                    if hasattr(m, "name") and m.name:
                                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "tool_end", "tool": m.name}))
                            elif node_name == "agent" and isinstance(node_output, dict):
                                for m in node_output.get("messages", []):
                                    if hasattr(m, "tool_calls") and m.tool_calls:
                                        for tc in m.tool_calls:
                                            tname = tc.get("name") or tc.get("function", {}).get("name", "tool")
                                            loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "tool_start", "tool": tname}))

                # Streaming completed — post-processing + persistence
                final_state = graph.get_state(config)
                if final_state and final_state.values:
                    new_msgs = final_state.values.get("messages", [])[existing_len:]
                    response_text = "".join(accumulated).strip()

                    # Build evidence items from what the LLM actually cited
                    evidence_result = _pipeline._evidence_builder.build(
                        response_text=response_text,
                        ranked_chunks=ctx.ranked_chunks,
                        source_policy=ctx.source_policy,
                        answer_mode=ctx.answer_mode,
                        answer_mode_metadata=ctx.answer_mode_metadata,
                    )
                    evidence_items = evidence_result.evidence

                    serialized = [e.model_dump(exclude={"raw_score", "reranker_score", "retrieval_latency_ms", "embedding_model"}) for e in evidence_items]
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                        "type": "evidence",
                        "evidence": serialized,
                        "answer_mode": ctx.answer_mode,
                    }))
                    # Keep backward-compat resources event
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                        "type": "resources",
                        "resources": [{"type": e.source_type, "title": e.title, "url": e.url, "snippet": e.chunk[:180] if e.chunk else None} for e in evidence_items],
                        "answer_mode": ctx.answer_mode,
                        "answer_mode_metadata": ctx.answer_mode_metadata,
                    }))

                    # Citation contract check
                    ref_indices = _parse_chunk_references(response_text)
                    validator = SourceValidator()
                    validation_result = validator.validate(
                        ref_indices=ref_indices,
                        total_chunks=len(ctx.ranked_chunks),
                        mode=ctx.source_policy,
                    )
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                        "type": "citation_check",
                        "valid": validation_result.valid,
                        "cited": validation_result.cited_count,
                        "required": validation_result.required_count,
                        "unique_chunks": validation_result.unique_chunks_cited,
                        "total_uses": validation_result.total_citation_uses,
                        "warnings": validation_result.warnings,
                        "reason": validation_result.reason,
                    }))

                    # Grounding validation (claim-level)
                    claim_data: list[dict] = []
                    if ctx.ranked_chunks and ctx.source_policy and ctx.source_policy.contract.requires_evidence:
                        grounding = _pipeline.run_grounding(response_text, ctx)
                        for v in grounding.validations:
                            claim_data.append({
                                "id": v.claim.id,
                                "text": v.claim.text,
                                "supported": v.supported,
                                "best_score": v.best_score,
                                "threshold": v.threshold,
                                "best_chunk_idx": v.best_chunk_idx,
                                "document": v.document_name,
                            })
                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                            "type": "claim_validation",
                            "valid": grounding.all_supported,
                            "total": grounding.total_count,
                            "unsupported": grounding.unsupported_count,
                            "claims": claim_data,
                        }))
                        if not grounding.all_supported:
                            logger.warning(
                                "grounding_unsupported session_id=%s unsupported=%d/%d threshold=%.2f",
                                request.session_id,
                                grounding.unsupported_count,
                                grounding.total_count,
                                grounding.validations[0].threshold if grounding.validations else 0,
                            )

                    # Stages 8-9: Validate + trace
                    record_id = ""
                    if response_text:
                        record_id = _post_process(ctx, response_text, new_msgs, model=model, temperature=temperature)

                    # Persist the completed assistant message exactly once
                    if response_text:
                        persist_assistant(response_text, store.MESSAGE_STATUS_COMPLETED)
                        # Detached memory extraction — after the stream is done,
                        # own thread, never on the stream path.
                        from app.learning.extraction.extractor import schedule_extraction
                        schedule_extraction(request.session_id, user.id, conv.project_id)
                    else:
                        # Generation finished but produced nothing visible —
                        # do not fabricate an assistant message.
                        logger.warning("empty_assistant_response conversation=%s", conv.id)

                    # Emit the learning record_id for feedback correlation
                    if record_id:
                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                            "type": "record_id",
                            "record_id": record_id,
                        }))

                    if record_id:
                        _persist_quality(
                            session_id=request.session_id,
                            question=request.message,
                            answer_mode=ctx.answer_mode,
                            validation_result=validation_result,
                            claim_data=claim_data,
                            record_id=record_id,
                        )

                    # Emit trace metadata as final SSE event before [DONE]
                    if ctx.trace:
                        import dataclasses
                        trace_dict = dataclasses.asdict(ctx.trace)
                        # Build rich retrieval context for debugging
                        retrieved_debug = []
                        for rc in ctx.retrieved_chunks[:10]:
                            retrieved_debug.append({
                                "chunk_id": rc.chunk_id,
                                "score": rc.score,
                                "source": rc.source,
                                "page": rc.page,
                                "chapter": rc.chapter,
                                "content_preview": rc.document.page_content[:200],
                            })
                        trace_dict["_retrieved_debug"] = retrieved_debug
                        ranked_debug = []
                        for rk in ctx.ranked_chunks[:5]:
                            ranked_debug.append({
                                "chunk_id": rk.chunk.chunk_id,
                                "reranker_score": rk.reranker_score,
                                "original_rank": rk.original_rank,
                                "content_preview": rk.chunk.document.page_content[:200],
                            })
                        trace_dict["_ranked_debug"] = ranked_debug
                        trace_dict["_context_text"] = ctx.context_text[:500]
                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "trace", "trace": trace_dict}))
            except Exception as thread_err:
                logger.error(f"Stream thread error: {thread_err}", exc_info=True)
                err_msg = str(thread_err)
                # Friendly message for image-incompatible models
                if "does not support image" in err_msg.lower() or "cannot read" in err_msg.lower():
                    friendly = "This model doesn't support image analysis. Try using a different model (like gpt-4o) for image tasks, or describe the image in text."
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "content", "content": friendly}))
                else:
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "error", "message": err_msg}))
                partial = "".join(accumulated).strip()
                if partial:
                    # Case C: partial output exists → preserve it, marked failed.
                    persist_assistant(partial, store.MESSAGE_STATUS_FAILED, error=err_msg[:2000])
                # Case B: no output → no fake assistant message.
            finally:
                loop.call_soon_threadsafe(q.put_nowait, "[DONE]")

        async def event_generator():
            asyncio.get_event_loop().run_in_executor(None, stream_in_thread)
            while True:
                item = await q.get()
                if item == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {item}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat streaming endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise api_error(500, "internal_error", "An internal error occurred")


# ---------------------------------------------------------------------------
# POST /chat/evaluate  – run pipeline + agent, return structured evaluation.
# Evaluation runs use eval-* thread ids and are NOT user conversations: they
# are not persisted to chat_messages.
# ---------------------------------------------------------------------------
class EvaluateRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    retriever: Optional[str] = None  # "hybrid" | "vector" | "bm25" — runs default if None


@router.post("/chat/evaluate")
async def chat_evaluate_endpoint(
    request: EvaluateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    try:
        session_id = request.session_id or f"eval-{int(time.time())}"
        # If a real conversation id is given, enforce ownership.
        if request.session_id and not request.session_id.startswith("eval-"):
            _load_conversation(db, user, request.session_id)

        config = {"configurable": {"thread_id": session_id}}
        existing_state = await asyncio.to_thread(graph.get_state, config)
        existing_len = _checkpoint_len(existing_state)

        # Stage 1-7: Run pre-processing pipeline (with optional retriever mode)
        ctx = _run_pipeline(request.message, session_id, retriever_mode=request.retriever)

        # Short-circuit for clarification
        if ctx.confidence and ctx.confidence.decision == "clarification":
            msg = (
                _pipeline.kb_not_covered_message()
                if not ctx.ranked_chunks
                else _pipeline.clarification_message()
            )
            if ctx.trace:
                ctx.trace.final_response_len = len(msg)
                ctx.trace.total_latency_ms = 0.0
            if _pipeline_config.get("trace_enabled", True):
                _pipeline.tracer.store(ctx.trace)
            result = build_evaluation_result(ctx, answer=msg)
            return result.to_dict()

        # Build initial state with pipeline context
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "system_prompt": "",
            "answer_mode_directive": ctx.source_policy.contract.system_directive if ctx.source_policy else "",
            "intent": ctx.intent_label,
            "rewritten_query": ctx.final_query,
            "pipeline_context": ctx.context_text,
            "answer_mode": ctx.answer_mode,
            "session_id": session_id,
            "user_id": user.id,
            "project_id": "",
            "model": resolve_model(None),
            "temperature": settings.TEMPERATURE_DEFAULT,
        }

        final_state = await asyncio.to_thread(graph.invoke, initial_state, config)

        new_messages = final_state["messages"][existing_len:]
        last_message = final_state["messages"][-1]
        response = last_message.content

        # Stages 8-9: Validate + trace
        # Populate tool/token info
        ctx.trace.memory_used = True
        ctx.trace.tools_used = _extract_tool_names(new_messages)
        ctx.trace.prompt_tokens = _count_tokens(ctx.question)
        ctx.trace.completion_tokens = _count_tokens(response)
        _pipeline.validate_response(question=ctx.question, response=response, ctx=ctx)

        # Build structured result
        result = build_evaluation_result(ctx, answer=response)
        return result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Evaluate endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise api_error(500, "internal_error", "An internal error occurred")