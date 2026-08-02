"""Scheduler — defines evaluation cadences and runs jobs on demand or on schedule.

The scheduler itself is simple: it knows about job types and cadences.
It does NOT know about analytics, evidence, or any specific module.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .models import JobType, JobStatus, AutomationRun
from .jobs import run_daily_evaluation, run_calibration_check, run_benchmark_regression
from .state import SnapshotStore, RunStore

logger = logging.getLogger(__name__)


class ScheduleCadence(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


@dataclass
class ScheduleDef:
    """Definition of a scheduled job."""
    job_type: JobType
    cadence: ScheduleCadence
    enabled: bool = True
    description: str = ""
    timeout_minutes: int = 30

    def should_run(self, last_run: Optional[datetime] = None) -> bool:
        """Determine if this job should run based on cadence."""
        if not self.enabled:
            return False
        if last_run is None:
            return True

        now = datetime.now(timezone.utc)
        if self.cadence == ScheduleCadence.HOURLY:
            return (now - last_run).total_seconds() >= 3600
        elif self.cadence == ScheduleCadence.DAILY:
            return (now - last_run).total_seconds() >= 86400
        elif self.cadence == ScheduleCadence.WEEKLY:
            return (now - last_run).total_seconds() >= 604800
        return False


# ── Default schedules ──────────────────────────────────────────────────

DEFAULT_SCHEDULES: list[ScheduleDef] = [
    ScheduleDef(
        job_type=JobType.DAILY_EVALUATION,
        cadence=ScheduleCadence.DAILY,
        description="Full pipeline: Analytics / Evidence / Health / Snapshot",
        timeout_minutes=30,
    ),
    ScheduleDef(
        job_type=JobType.CALIBRATION_CHECK,
        cadence=ScheduleCadence.HOURLY,
        description="Lightweight calibration monitoring",
        timeout_minutes=5,
    ),
    ScheduleDef(
        job_type=JobType.BENCHMARK_REGRESSION,
        cadence=ScheduleCadence.WEEKLY,
        description="Benchmark regression detection",
        timeout_minutes=60,
    ),
]


# ── Run history (persisted to disk; survives restarts) ─────────────────

_run_store = RunStore()
_run_lock = threading.Lock()


def run_job(job_type: JobType) -> AutomationRun:
    """Execute a single job by type. Returns the AutomationRun record, persisted."""
    runner_map = {
        JobType.DAILY_EVALUATION: run_daily_evaluation,
        JobType.CALIBRATION_CHECK: run_calibration_check,
        JobType.BENCHMARK_REGRESSION: run_benchmark_regression,
    }
    runner = runner_map.get(job_type)
    if not runner:
        run = AutomationRun(job_type=job_type, status=JobStatus.FAILED, error=f"No runner for {job_type}")
    else:
        run = runner()

    with _run_lock:
        _run_store.record(run)
    return run


def run_due_jobs() -> list[AutomationRun]:
    """Check all schedules and run any that are due."""
    runs = []
    store = SnapshotStore()
    latest = store.latest()

    for schedule in DEFAULT_SCHEDULES:
        last_run = None
        if latest and latest.timestamp:
            try:
                last_run = datetime.fromisoformat(latest.timestamp)
            except (ValueError, TypeError):
                pass
        if schedule.should_run(last_run=last_run):
            logger.info("Running scheduled job: %s", schedule.job_type.value)
            run = run_job(schedule.job_type)
            runs.append(run)

    return runs


def get_run_history(limit: int = 50) -> list[AutomationRun]:
    """Return recent automation run history (persisted)."""
    return _run_store.list_all(limit=limit)


def get_schedules() -> list[ScheduleDef]:
    """Return the current schedule definitions."""
    return list(DEFAULT_SCHEDULES)


# ── Background scheduler ────────────────────────────────────────────────

SCHEDULE_INTERVAL_SECONDS = 3600  # 1 hour between schedule checks


def _scheduler_loop(stop_event: threading.Event):
    """Background loop that runs due jobs on cadence."""
    logger.info("scheduler started (interval=%ss)", SCHEDULE_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            runs = run_due_jobs()
            if runs:
                logger.info("scheduler ran %d due job(s)", len(runs))
        except Exception:  # noqa: BLE001
            logger.exception("scheduler tick failed")
        stop_event.wait(SCHEDULE_INTERVAL_SECONDS)


class SchedulerLoop:
    """Owns the background scheduler thread lifecycle."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=_scheduler_loop, args=(self._stop,), daemon=True, name="automation-scheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


scheduler = SchedulerLoop()
