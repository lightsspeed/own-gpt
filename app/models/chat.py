from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ChatSession(Base):
    """A conversation. Owned by exactly one user.

    `id` is the application-level conversation id (UUID string, kept for
    backward compatibility with existing sessions). `thread_id` is the
    LangGraph checkpoint thread — historically identical to `id`.
    """

    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)  # UUID string
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    thread_id = Column(String, index=True)
    title = Column(String, default="New Chat")
    is_pinned = Column(Boolean, default=False)
    selected_model = Column(String, nullable=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """An application-level chat message (canonical chat history).

    LangGraph checkpoints hold the *execution* representation of the same
    exchange; this table is the user-visible conversation history.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        # Optional client-supplied idempotency key: one logical request per
        # (conversation, request_id). NULL rows are not deduplicated.
        UniqueConstraint("session_id", "request_id", name="uq_chat_messages_session_request"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), index=True)
    role = Column(String)  # user, assistant, system, tool
    content = Column(Text)
    model = Column(String, nullable=True)
    status = Column(String, default="completed")  # completed | failed
    error = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)
    sequence = Column(Integer, nullable=True, index=True)  # deterministic order
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    additional_kwargs = Column(JSON, default={})  # tool calls, resources, etc.

    session = relationship("ChatSession", back_populates="messages")