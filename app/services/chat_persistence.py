"""
Chat persistence service — the canonical application chat database.

Responsibilities (PostgreSQL, sync sessions so both the async request path
and the streaming worker thread share one implementation):

- conversations belong to a user (ownership enforced in every query)
- deterministic message ordering (per-conversation sequence numbers,
  serialized with SELECT ... FOR UPDATE on the conversation row)
- user messages persisted BEFORE graph execution
- assistant messages persisted after generation (completed/failed status)
- idempotent backfill of legacy conversations from LangGraph checkpoints
- optional request_id idempotency (one logical request per conversation)

LangGraph checkpoints remain the source of truth for *execution* state; this
module never reads checkpoint blobs for chat history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.model_config import DEFAULT_MODEL
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

logger = logging.getLogger(__name__)

MESSAGE_STATUS_COMPLETED = "completed"
MESSAGE_STATUS_FAILED = "failed"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def get_conversation(db: Session, conversation_id: str, user_id: str) -> ChatSession | None:
    """Fetch a conversation ONLY when it belongs to the user. Ownership is
    enforced in the query — never trust a client-provided id alone."""
    return db.execute(
        select(ChatSession).where(
            ChatSession.id == conversation_id,
            ChatSession.owner_id == user_id,
        )
    ).scalar_one_or_none()


def get_conversation_any_owner(db: Session, conversation_id: str) -> ChatSession | None:
    """Fetch a conversation regardless of owner. Used ONLY to detect that an
    id is taken by someone else so cross-owner access can 404 like a missing
    resource. Never returns this row to the caller as an owned object."""
    return db.execute(
        select(ChatSession).where(ChatSession.id == conversation_id)
    ).scalar_one_or_none()


def create_conversation(
    db: Session,
    owner: User,
    conversation_id: str,
    title: str = "New Chat",
    selected_model: str | None = None,
) -> ChatSession:
    session = ChatSession(
        id=conversation_id,
        owner_id=owner.id,
        thread_id=conversation_id,  # explicit mapping: conversation.id -> thread_id
        title=title,
        selected_model=selected_model,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_conversations(db: Session, owner: User, limit: int = 100) -> list[ChatSession]:
    return list(
        db.execute(
            select(ChatSession)
            .where(ChatSession.owner_id == owner.id)
            .order_by(ChatSession.is_pinned.desc(), ChatSession.updated_at.desc())
            .limit(limit)
        ).scalars()
    )


def update_conversation(
    db: Session,
    session: ChatSession,
    title: str | None = None,
    is_pinned: bool | None = None,
    selected_model: str | None = None,
    project_id: str | None = None,
) -> ChatSession:
    if title is not None:
        session.title = title
    if is_pinned is not None:
        session.is_pinned = is_pinned
    if selected_model is not None:
        session.selected_model = selected_model
    if project_id is not None:
        session.project_id = project_id
    session.updated_at = now_utc()
    db.commit()
    db.refresh(session)
    return session


def touch_conversation(db: Session, session: ChatSession) -> None:
    """Bump updated_at so recent activity reorders the sidebar."""
    session.updated_at = now_utc()
    db.commit()


def delete_conversation(db: Session, session: ChatSession) -> None:
    """Delete the conversation and all its messages (cascade)."""
    db.delete(session)
    db.commit()


def count_conversation_messages(db: Session, conversation_id: str) -> int:
    return db.execute(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == conversation_id)
    ).scalar_one()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def _next_sequence(db: Session, conversation_id: str) -> int:
    """Allocate the next deterministic sequence number for a conversation.

    The conversation row is locked (SELECT ... FOR UPDATE) so concurrent
    requests in the same conversation serialize and never produce duplicate
    sequence numbers.
    """
    db.execute(select(ChatSession.id).where(ChatSession.id == conversation_id).with_for_update())
    current = db.execute(
        select(func.max(ChatMessage.sequence)).where(ChatMessage.session_id == conversation_id)
    ).scalar_one()
    return (current or 0) + 1


def persist_user_message(
    db: Session,
    conversation: ChatSession,
    content: str,
    model: str | None,
    request_id: str | None = None,
) -> ChatMessage:
    """Persist a user message BEFORE graph execution. When a request_id is
    given and a user message for it already exists, the existing row is
    returned — callers decide whether to treat that as a duplicate."""
    if request_id:
        existing = get_user_message_by_request_id(db, conversation.id, request_id)
        if existing is not None:
            logger.info("duplicate_request_ignored conversation=%s request_id=%s", conversation.id, request_id)
            return existing
    msg = ChatMessage(
        session_id=conversation.id,
        role="user",
        content=content,
        model=model,
        status=MESSAGE_STATUS_COMPLETED,
        request_id=request_id,
        sequence=_next_sequence(db, conversation.id),
    )
    db.add(msg)
    db.commit()
    return msg


def get_user_message_by_request_id(
    db: Session, conversation_id: str, request_id: str
) -> ChatMessage | None:
    return db.execute(
        select(ChatMessage).where(
            ChatMessage.session_id == conversation_id,
            ChatMessage.request_id == request_id,
            ChatMessage.role == "user",
        )
    ).scalar_one_or_none()


def persist_assistant_message(
    db: Session,
    conversation: ChatSession,
    content: str,
    model: str | None,
    status: str = MESSAGE_STATUS_COMPLETED,
    error: str | None = None,
) -> ChatMessage:
    """Persist the final assistant message after generation completes/fails.

    Never called per token — streaming accumulates server-side and this is
    invoked exactly once per generation.
    """
    msg = ChatMessage(
        session_id=conversation.id,
        role="assistant",
        content=content,
        model=model,
        status=status,
        error=error,
        sequence=_next_sequence(db, conversation.id),
    )
    db.add(msg)
    db.commit()
    return msg


def list_messages(db: Session, conversation_id: str) -> list[ChatMessage]:
    """Ordered messages for rendering history (deterministic by sequence)."""
    return list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == conversation_id)
            .order_by(ChatMessage.sequence.asc(), ChatMessage.id.asc())
        ).scalars()
    )


def search_messages(db: Session, owner: User, query: str, limit: int = 20) -> list[ChatMessage]:
    """Message-content search scoped to the user's conversations."""
    return list(
        db.execute(
            select(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.owner_id == owner.id,
                ChatMessage.content.ilike(f"%{query}%"),
            )
            .order_by(ChatMessage.sequence.desc())
            .limit(limit)
        ).scalars()
    )


# ---------------------------------------------------------------------------
# Legacy backfill from LangGraph checkpoints
# ---------------------------------------------------------------------------

def backfill_messages_from_checkpoint(
    db: Session,
    conversation: ChatSession,
    checkpoint_messages: Iterable[object],
    model: str | None = None,
) -> int:
    """Backfill chat_messages from checkpoint state for legacy conversations.

    Idempotency rule: runs only when the conversation has NO application
    rows yet (count == 0). Checkpoint data is read-only — never modified.
    """
    if count_conversation_messages(db, conversation.id) > 0:
        return 0

    role_map = {"HumanMessage": "user", "AIMessage": "assistant", "SystemMessage": "system", "ToolMessage": "tool"}
    rows: list[ChatMessage] = []
    seq = 0
    for m in checkpoint_messages:
        role = role_map.get(type(m).__name__)
        if role is None or role == "tool":
            continue
        content = _plain_content(getattr(m, "content", ""))
        if not content.strip():
            continue
        seq += 1
        rows.append(
            ChatMessage(
                session_id=conversation.id,
                role=role,
                content=content,
                model=getattr(m, "model", None) or model,
                status=MESSAGE_STATUS_COMPLETED,
                sequence=seq,
                additional_kwargs={"backfilled": True},
            )
        )
    if rows:
        db.add_all(rows)
        db.commit()
    logger.info("messages_backfilled conversation=%s rows=%d", conversation.id, len(rows))
    return len(rows)


def _plain_content(content) -> str:
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


def models_used(db: Session, conversation_id: str) -> list[str]:
    """Distinct models used in a conversation (for the UI / analytics)."""
    return list(
        db.execute(
            select(ChatMessage.model)
            .where(ChatMessage.session_id == conversation_id, ChatMessage.model.is_not(None))
            .distinct()
        ).scalars()
    )