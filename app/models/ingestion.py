import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class IngestionJob(Base):
    """Queue entry for an async document ingestion (arq worker)."""

    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(512), index=True)
    # pending | processing | completed | duplicate | failed
    status = Column(String(32), default="pending", index=True)
    sha256 = Column(String(64), default="")
    chunks = Column(Integer, default=0)
    error = Column(Text, default="")
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IngestedFile(Base):
    """Ingested-file registry used for sha256 deduplication."""

    __tablename__ = "ingested_files"

    filename = Column(String(512), primary_key=True)
    sha256 = Column(String(64), default="")
    chunks = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
