"""Bounded daemon worker pool for memory extraction.

Replaces the previous unbounded per-request daemon-thread creation. The pool
bounds concurrent extractions to MEMORY_EXTRACTION_MAX_CONCURRENCY workers and
bounds the pending queue to MEMORY_EXTRACTION_MAX_QUEUE tasks. It is the
smallest production-grade execution mechanism compatible with the synchronous
FastAPI architecture (mirrors the learning_collector fire-and-forget precedent
with a bound).

Design decisions (V2.2 P1 hardening report):

- Worker threads are daemon threads: application shutdown never hangs on an
  in-flight extraction (slow/offline LLM provider cannot block process exit).
  Queued work is abandoned on shutdown; single-flight TTL + idempotent
  memory writes make re-execution safe.
- submit() never raises: a full queue or a stopped pool reports False and the
  caller (extraction scheduler) logs and releases the turn claim.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

from app.core.config import settings
from app.core import metrics as core_metrics

logger = logging.getLogger(__name__)


class BoundedDaemonExecutor:
    """A bounded pool of daemon worker threads executing fire-and-forget tasks.

    Thread-safe: submit() may be called from any thread (FastAPI request
    threads, streaming worker threads). Tasks run serially per worker; a task
    that raises is logged and never escapes the pool.
    """

    def __init__(self, max_workers: int, max_queue: int) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if max_queue < 1:
            raise ValueError("max_queue must be >= 1")
        self._max_workers = max_workers
        self._queue: "queue.Queue[Optional[Callable[[], None]]]" = queue.Queue(
            maxsize=max_queue
        )
        self._lock = threading.Lock()
        self._running = True
        self._workers: list[threading.Thread] = []
        core_metrics.safe_set("queue_capacity", max_queue)
        core_metrics.safe_set("queue_depth", 0)
        for i in range(max_workers):
            t = threading.Thread(
                target=self._run,
                name=f"memory-extraction-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                return  # shutdown sentinel
            core_metrics.safe_set("queue_depth", self._queue.qsize())
            core_metrics.safe_gauge_inc("inflight")
            try:
                task()
            except Exception as exc:  # defensive: tasks must never raise out
                logger.error("memory_extraction_task_error error=%s", exc, exc_info=True)
            finally:
                core_metrics.safe_gauge_dec("inflight")

    def submit(self, fn: Callable[..., None], *args) -> bool:
        """Enqueue a task. Returns True when accepted, False when the pool is
        stopped or the queue is full. Never raises."""
        task = lambda: fn(*args)  # noqa: E731
        with self._lock:
            if not self._running:
                return False
            try:
                self._queue.put_nowait(task)
                core_metrics.safe_set("queue_depth", self._queue.qsize())
                return True
            except queue.Full:
                return False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def shutdown(self) -> None:
        """Stop accepting work, abandon queued tasks, wake workers.

        Idempotent and thread-safe. In-flight tasks keep running on their
        daemon worker thread (they own their DB session and never block
        process exit). Workers exit on the sentinel after the queue is
        drained; queued tasks are dropped (abandoned safely — single-flight
        TTL + idempotent writes allow a later re-execution).
        """
        with self._lock:
            if not self._running:
                return
            self._running = False
            # Drop queued work: extraction for a completed turn is a
            # best-effort side effect, never a delivery obligation.
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            core_metrics.safe_set("queue_depth", 0)
            for _ in self._workers:
                self._queue.put_nowait(None)


# Process-wide singleton. Workers are daemon threads and start at import time;
# they sit idle until the scheduler enqueues an extraction.
extraction_executor = BoundedDaemonExecutor(
    max_workers=settings.MEMORY_EXTRACTION_MAX_CONCURRENCY,
    max_queue=settings.MEMORY_EXTRACTION_MAX_QUEUE,
)
