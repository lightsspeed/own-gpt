"""Continuous Evaluation — makes the platform proactive.

Automation orchestrates existing modules (Analytics, Evidence, Experiments, Config)
on a schedule, detects meaningful changes via triggers, and produces daily briefs.
"""

from .models import AutomationRun, EvaluationSnapshot, HealthDomainScore, DailyBrief, Trigger, JobType, JobStatus
from .scheduler import run_job, run_due_jobs, get_run_history, get_schedules
from .state import SnapshotStore
from .triggers import TriggerEngine
from .health import compute_all, compute_domain_score, compute_overall
from .reports import generate_daily_brief
from .jobs import run_daily_evaluation, run_calibration_check

__all__ = [
    "AutomationRun", "EvaluationSnapshot", "HealthDomainScore", "DailyBrief", "Trigger",
    "JobType", "JobStatus",
    "run_job", "run_due_jobs", "get_run_history", "get_schedules",
    "SnapshotStore", "TriggerEngine",
    "compute_all", "compute_domain_score", "compute_overall",
    "generate_daily_brief",
    "run_daily_evaluation", "run_calibration_check",
]
