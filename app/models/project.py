"""
Project model — the mid-tier of the ownership chain.

Ownership chain invariant: Project.owner_id == ChatSession.owner_id ==
MemoryEntity.user_id. Every project reference is ownership-verified at
write time; the FK below proves existence only, never ownership.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)  # uuid4 hex
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)  # SQLAlchemy reserves `metadata`
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __init__(self, **kwargs):
        if not kwargs.get("id"):
            kwargs["id"] = str(uuid.uuid4())
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Project id={self.id} owner_id={self.owner_id} name={self.name!r}>"