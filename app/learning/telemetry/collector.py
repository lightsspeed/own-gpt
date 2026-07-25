"""
Learning Collector — singleton that bridges the pipeline to the event store.

Usage from chat endpoint:
    from app.learning.telemetry.collector import learning_collector
    learning_collector.record(ctx, response)
    learning_collector.track_event(record_id, "thumb_up", ...)
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agent.pipeline import PipelineContext

from ..models import LearningRecord, UserEvent
from ..storage.sqlite import LearningStore
from .builder import build_learning_record

logger = logging.getLogger(__name__)


class LearningCollector:
    """
    Singleton collector that writes telemetry to the LearningStore.

    Designed to be called from the FastAPI chat endpoint after
    pipeline execution completes. Never modifies pipeline behavior.
    """

    def __init__(self, store: Optional[LearningStore] = None):
        self._store = store or LearningStore()

    @property
    def store(self) -> LearningStore:
        return self._store

    def record(self, ctx: PipelineContext, response: str = "") -> str:
        """
        Build and persist a LearningRecord from the pipeline context.

        Returns the record_id for correlation with future user events.
        This is a fire-and-forget write — exceptions are logged but never raised.
        """
        try:
            record = build_learning_record(ctx, response)
            self._store.store_record(record)
            logger.debug(
                "learning_record_stored record_id=%s intent=%s mode=%s",
                record.record_id, record.intent, record.answer_mode,
            )
            return record.record_id
        except Exception as e:
            logger.error("learning_record_failed error=%s", e, exc_info=True)
            return ""

    def track_event(
        self,
        record_id: str,
        event_type: str,
        session_id: str = "",
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Persist a user event linked to a learning record.

        Supported event types:
            thumb_up, thumb_down, copy, regenerate, retry,
            rename, share, bookmark, open_reference, feedback
        """
        if event_type not in UserEvent.SUPPORTED_TYPES:
            logger.warning("unknown_event_type type=%s", event_type)
            return
        try:
            event = UserEvent(
                record_id=record_id,
                session_id=session_id,
                type=event_type,
                metadata=metadata or {},
            )
            self._store.store_event(event)
        except Exception as e:
            logger.error("event_record_failed type=%s error=%s", event_type, e)

    def update_thumb(self, record_id: str, thumb: str) -> None:
        """Update the thumb state on an existing LearningRecord."""
        try:
            record = self._store.get_record(record_id)
            if record:
                record.thumb = thumb
                self._store.store_record(record)
        except Exception as e:
            logger.error("thumb_update_failed record_id=%s error=%s", record_id, e)


# Singleton instance — imported by chat endpoints
learning_collector = LearningCollector()
