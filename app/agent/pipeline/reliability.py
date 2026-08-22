"""
V4.11 - Production Reliability & Cancellation

Bounded, observable execution guarantees on top of the V3.12 loop and the
V4.7 ToolResult taxonomy (no new taxonomy — everything maps back onto the
standard statuses/error codes):

  Timeouts (three boundaries, all existing vocabulary):
    - per-tool   : a handler exceeding the tool cap is re-labeled timeout
                   (TOOL_TIMEOUT), never returned as a bogus success.
    - per-step   : a step exceeding the step cap is a timeout even when
                   the underlying tool reported success.
    - request    : an expired request blocks pending steps BEFORE any
                   handler runs (request_expired() is checked by the loop
                   and the executor gate).
    The guard reads time from an injectable clock (defaults to the
    monotonic clock) so behavior is deterministic in tests.

  Cancellation (cooperative, request -> execution -> current step):
    - the operator sets context.cancel_requested; the loop checks it
      before scheduling, the executor checks it before running a handler.
    - cancelled/expired steps are marked blocked (never left running or
      pending), with step_cancelled / step_blocked trace events and the
      request_cancelled / request_timeout events recorded once per run.

  Partial execution recovery:
    - completed steps stay valid; failed stays failed; pending steps that
      depend on a terminal failure are marked blocked; INDEPENDENT steps
      may continue. No automatic retry, no replanning — the loop only
      ever executes the existing approved plan.

  Idempotency:
    - one execution_id x step_id pair executes at most once: when a
      terminal (completed/failed/blocked) result is already recorded, the
      executor REPLAYS it instead of running the handler again. First
      terminal result wins; non-terminal entries are never cached.
    - this never bypasses capability selection, tool selection, the
      security boundary, or the token budget — replay is checked only
      AFTER the V3.10/V3.11 enforcement passes, and the terminal result
      already passed every gate when it was first produced.

Context access is defensive (isinstance checks, `is True` flag checks) —
a context without these attributes behaves exactly as before V4.11 and
never trips on MagicMock-based test contexts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Default boundaries (seconds). Config keys live in pipeline_config.yaml.
DEFAULT_TOOL_TIMEOUT_S = 15.0
DEFAULT_STEP_TIMEOUT_S = 30.0
DEFAULT_REQUEST_TIMEOUT_S = 120.0

# Stable, deterministic reason strings (blocked step errors + loop reasons).
REASON_REQUEST_CANCELLED = "Request cancelled."
REASON_REQUEST_TIMED_OUT = "Request timed out."
REASON_STEP_TIMED_OUT = "Step timed out."
REASON_TOOL_TIMED_OUT = "Tool timed out."

# Statuses that settle an execution for idempotent replay.
TERMINAL_STATUSES = frozenset({"completed", "failed", "blocked"})


@dataclass
class TimeoutPolicy:
    """The three timeout boundaries for one request (seconds, positive)."""
    tool_timeout_s: float = DEFAULT_TOOL_TIMEOUT_S
    step_timeout_s: float = DEFAULT_STEP_TIMEOUT_S
    request_timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S

    def __post_init__(self) -> None:
        for name, val in (
            ("tool_timeout_s", self.tool_timeout_s),
            ("step_timeout_s", self.step_timeout_s),
            ("request_timeout_s", self.request_timeout_s),
        ):
            if not isinstance(val, (int, float)) or isinstance(val, bool) or val <= 0:
                raise ValueError(f"{name} must be a positive number, got {val!r}")


class ReliabilityGuard:
    """Wall-clock decision maker for timeouts on an injectable clock.

    The clock is a zero-arg callable returning float seconds (defaults to
    time.monotonic). Deterministic tests pass a fake clock.
    """

    def __init__(
        self,
        policy: Optional[TimeoutPolicy] = None,
        clock: Optional[Callable[[], float]] = None,
        request_started: Optional[float] = None,
    ) -> None:
        self._policy = policy if isinstance(policy, TimeoutPolicy) else TimeoutPolicy()
        self._clock = clock if callable(clock) else time.monotonic
        self._request_started = (
            request_started if request_started is not None else self._clock()
        )

    @property
    def policy(self) -> TimeoutPolicy:
        return self._policy

    @property
    def request_started(self) -> float:
        return self._request_started

    def now(self) -> float:
        """Current time on the guard's clock."""
        return self._clock()

    def elapsed(self, start: float) -> float:
        """Seconds since `start` on the guard's clock (never negative)."""
        return max(0.0, self._clock() - start)

    def tool_exceeded(self, start: float) -> bool:
        return self.elapsed(start) >= self._policy.tool_timeout_s

    def step_exceeded(self, start: float) -> bool:
        return self.elapsed(start) >= self._policy.step_timeout_s

    def request_expired(self) -> bool:
        """True when the WHOLE request has exceeded its timeout."""
        return self.elapsed(self._request_started) >= self._policy.request_timeout_s


@dataclass
class CachedStepResult:
    """Serialization-safe terminal snapshot used for idempotent replay.

    Holds only primitives plus an optional ToolResult.to_dict() view; no
    references into live execution objects (nothing can be mutated by a
    replay).
    """
    step_id: int
    status: str
    output: str = ""
    error: Optional[str] = None
    tool: Optional[str] = None
    tool_result: Optional[dict] = None


class IdempotencyLedger:
    """In-memory record of terminal step outcomes per (execution_id, step_id).

    First terminal result wins and is never overwritten: one execution of
    a step per execution_id, always. Non-terminal statuses (pending /
    running) are never cached.
    """

    def __init__(self) -> None:
        self._terminal: dict[tuple[str, int], CachedStepResult] = {}

    def terminal_for(
        self, execution_id: str, step_id: int
    ) -> Optional[CachedStepResult]:
        """Cached terminal outcome for (execution_id, step_id), or None."""
        cached = self._terminal.get((execution_id, step_id))
        if cached is not None and cached.status in TERMINAL_STATUSES:
            return cached
        return None

    def record(self, execution_id: str, step_id: int, result) -> None:
        """Store a terminal outcome (first wins; defensive, never raises)."""
        try:
            status = getattr(result, "status", "")
            if status not in TERMINAL_STATUSES:
                return
            key = (execution_id, step_id)
            if key in self._terminal:
                return
            tool_result = getattr(result, "tool_result", None)
            self._terminal[key] = CachedStepResult(
                step_id=getattr(result, "step_id", step_id),
                status=status,
                output=getattr(result, "output", "") or "",
                error=getattr(result, "error", None),
                tool=getattr(result, "tool", None),
                tool_result=tool_result.to_dict() if hasattr(tool_result, "to_dict") else None,
            )
        except Exception as exc:
            logger.warning("idempotency_ledger_record_failed step_id=%d error=%s", step_id, exc)

    def __len__(self) -> int:
        return len(self._terminal)


# ── Context access (defensive; MagicMock-safe) ───────────────────────────────

def reliability_guard_of(context: object) -> Optional[ReliabilityGuard]:
    """The ReliabilityGuard attached to a context, or None."""
    guard = getattr(context, "reliability", None) if context is not None else None
    return guard if isinstance(guard, ReliabilityGuard) else None


def idempotency_of(context: object) -> Optional[IdempotencyLedger]:
    """The IdempotencyLedger attached to a context, or None."""
    ledger = getattr(context, "idempotency", None) if context is not None else None
    return ledger if isinstance(ledger, IdempotencyLedger) else None


def is_cancel_requested(context: object) -> bool:
    """True only when the operator explicitly requested cancellation.

    `is True` (not truthiness) — MagicMock or non-bool attributes must
    never be mistaken for a cancellation request.
    """
    return getattr(context, "cancel_requested", None) is True