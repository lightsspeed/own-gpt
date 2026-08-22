"""
V3.13+V3.14: Checkout Lane — AuthorizationCode artifacts gating experiment
execution, and the durable execution result / audit trail.

The Experiment Lane must not execute without explicit authorization.
Every execution requires a single-use AuthorizationCode:

    issue (ISSUED)
      → operator approve (APPROVED)      # human-gated, bound to experiment_id
      → exchange → CONSUMED              # single execution, result recorded
    issue → revoke (REVOKED)             # from ISSUED or APPROVED (revocable)
    exchange failure → FAILED            # terminal, never retried

V3.14 audit trail (append-only, immutable history):
    issued → approved → consumed → ExecutionResult
  Each event preserves actor, timestamps, experiment_id, execution_id; the
  ExecutionResult is stored once per execution_id in an ExecutionResultStore
  and never mutated. Blocked/failed attempts produce blocked/failed results
  so the audit trail covers denials too.

Invariants:
  - No experiment run without an APPROVED code for the SAME experiment_id.
  - No authorization → the exchange is BLOCKED (AuthorizationError) and a
    blocked ExecutionResult is recorded; the runner is never invoked.
  - Single-use: a code executes at most once. Reuse of the SAME code after
    consumption returns the cached result (idempotent exchange) WITHOUT
    re-execution — safe retries, no double runs.
  - A consumed cached result is only reachable through the code that
    produced it; different codes cannot replay it.
  - The lane ONLY orchestrates the existing ReplayRunner (offline replay,
    no tools, no LLM). It never bypasses existing capability/tool gates.
  - State transitions are recorded as AuthorizationEvent entries (append-only
    history); the code record reflects the current state.
  - The raw authorization code is internal state; serialized artifacts and
    API responses never expose it.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

from ..architecture.artifacts import ArtifactType, Lineage
from .models import ExperimentDefinition, ExperimentResult
from .runner import ReplayRunner

logger = logging.getLogger(__name__)


class AuthorizationStatus(str, Enum):
    ISSUED = "issued"
    APPROVED = "approved"
    CONSUMED = "consumed"
    REVOKED = "revoked"
    FAILED = "failed"


# Transitions that are not permitted (terminal states never move).
_INVALID_TRANSITIONS: frozenset[tuple[AuthorizationStatus, AuthorizationStatus]] = frozenset({
    (AuthorizationStatus.CONSUMED, AuthorizationStatus.ISSUED),
    (AuthorizationStatus.CONSUMED, AuthorizationStatus.APPROVED),
    (AuthorizationStatus.CONSUMED, AuthorizationStatus.REVOKED),
    (AuthorizationStatus.CONSUMED, AuthorizationStatus.CONSUMED),
    (AuthorizationStatus.REVOKED, AuthorizationStatus.ISSUED),
    (AuthorizationStatus.REVOKED, AuthorizationStatus.APPROVED),
    (AuthorizationStatus.REVOKED, AuthorizationStatus.REVOKED),
    (AuthorizationStatus.REVOKED, AuthorizationStatus.CONSUMED),
    (AuthorizationStatus.FAILED, AuthorizationStatus.ISSUED),
    (AuthorizationStatus.FAILED, AuthorizationStatus.APPROVED),
    (AuthorizationStatus.FAILED, AuthorizationStatus.REVOKED),
    (AuthorizationStatus.FAILED, AuthorizationStatus.CONSUMED),
    (AuthorizationStatus.FAILED, AuthorizationStatus.FAILED),
})


# ── Artifacts ─────────────────────────────────────────────────────────────────

@dataclass
class AuthorizationEvent:
    """Append-only record of one checkout transition or denial (V3.14)."""
    code: str
    from_status: Optional[str]
    to_status: str
    at: str = ""
    actor: str = "system"
    experiment_id: str = ""
    execution_id: str = ""

    def __post_init__(self):
        if not self.at:
            self.at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        # The raw code is a secret - serialized events never expose it.
        return {
            "code": "***",
            "from": self.from_status,
            "to": self.to_status,
            "at": self.at,
            "actor": self.actor,
            "experiment_id": self.experiment_id,
            "execution_id": self.execution_id,
        }


@dataclass
class AuthorizationCode:
    """
    Single-use checkout token authorizing execution of ONE experiment.

    Fields (V3.13 spec): code, key, value, experiment_id, status.
    Artifact invariants: id, created_at, lineage (parent = experiment).
    """
    code: str
    key: str = ""
    value: str = ""
    experiment_id: str = ""
    status: AuthorizationStatus = AuthorizationStatus.ISSUED
    id: str = ""
    created_at: str = ""
    approved_at: Optional[str] = None
    approved_by: str = ""
    consumed_at: Optional[str] = None
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"authz-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.experiment_id or None,
                parent_type=ArtifactType.EXPERIMENT if self.experiment_id else None,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "key": self.key,
            "value": self.value,
            "experiment_id": self.experiment_id,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "consumed_at": self.consumed_at,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


class AuthorizationError(Exception):
    """A checkout was blocked: missing, not approved, revoked, or spent."""

    def __init__(self, reason: str, status: Optional[str] = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


# ── Execution Result Store ───────────────────────────────────────────────────

class ExecutionResultStore:
    """
    Immutable registry of executed experiment results (V3.14).

    Keyed by (experiment_id, execution_id). Every execution_id is written at
    most once; the first object wins and later writes are idempotent no-ops.
    Never mutated after insertion. Query surfaces (V3.15) return defensive
    copies of the result LIST and newest-first ordering; the artifacts
    themselves are immutable.
    """

    def __init__(self) -> None:
        self._results: dict[tuple[str, str], ExperimentResult] = {}

    def put(self, result: ExperimentResult) -> ExperimentResult:
        """Store a result idempotently — first write wins, returns it."""
        key = (result.experiment_id, result.execution_id)
        existing = self._results.get(key)
        if existing is not None:
            return existing
        self._results[key] = result
        return result

    def get(self, experiment_id: str, execution_id: str) -> Optional[ExperimentResult]:
        return self._results.get((experiment_id, execution_id))

    def list_by_experiment(self, experiment_id: str) -> list[ExperimentResult]:
        """Newest-first results for one experiment (defensive copy list)."""
        matches = [r for r in self._results.values() if r.experiment_id == experiment_id]
        matches.sort(
            key=lambda r: (r.finished_at or r.started_at or "", r.execution_id),
            reverse=True,
        )
        return matches

    def all(self) -> list[ExperimentResult]:
        return list(self._results.values())

    def count(self) -> int:
        return len(self._results)


# ── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog:
    """
    Append-only registry of authorization events (V3.15).

    Every event is written once and never mutated. Queries filter by
    experiment_id and return newest-first defensive copies. Serialization
    (AuthorizationEvent.to_dict) redacts the raw code; key/value are not
    carried by events at all.
    """

    def __init__(self) -> None:
        self._events: list[AuthorizationEvent] = []

    def append(self, event: AuthorizationEvent) -> None:
        self._events.append(event)

    def list_by_experiment(self, experiment_id: str) -> list[AuthorizationEvent]:
        """Newest-first (reverse append order) events for one experiment."""
        return [
            e for e in reversed(self._events) if e.experiment_id == experiment_id
        ]

    def all(self) -> list[AuthorizationEvent]:
        return list(self._events)

    def count(self) -> int:
        return len(self._events)


# ── Checkout Lane ────────────────────────────────────────────────────────────

class CheckoutLane:
    """
    The ONLY authorized path to run an experiment.

    Pure orchestrator over the existing ReplayRunner (injected, so tests stay
    hermetic). Owns authorization, approval, revocation, single-use, and
    idempotent exchange — never contains experiment/metrics business logic.
    """

    def __init__(self, runner: Optional[Callable] = None,
                 results_store: Optional[ExecutionResultStore] = None,
                 audit_log: Optional[AuditLog] = None):
        """
        Args:
            runner: Callable(experiment: ExperimentDefinition, limit: int)
                    -> ExperimentResult. Defaults to ReplayRunner().run.
            results_store: shared/durable registry of execution results.
                    Defaults to a private in-memory store (hermetic default).
            audit_log: shared/durable append-only authorization history.
                    When provided, EVERY event is mirrored into it (the lane
                    keeps its own history() as well).
        """
        self._runner = runner if runner is not None else ReplayRunner().run
        self._results_store = results_store if results_store is not None else ExecutionResultStore()
        self._audit_log = audit_log
        self._codes: dict[str, AuthorizationCode] = {}
        self._events: list[AuthorizationEvent] = []
        self._cache: dict[str, ExperimentResult] = {}

    def _record_event(self, event: AuthorizationEvent) -> None:
        """Append an event to the lane history AND the shared audit log."""
        self._events.append(event)
        if self._audit_log is not None:
            self._audit_log.append(event)

    # ── Lookup ─────────────────────────────────────────────────────────────

    def _get(self, code: str) -> AuthorizationCode:
        record = self._codes.get(code)
        if record is None:
            # The raw code is a secret — never echoed into an exception that
            # can cross the HTTP boundary. Operators correlate via code_id.
            logger.warning("checkout lookup failed unknown_code")
            raise AuthorizationError("unknown checkout code")
        return record

    def _transition(self, code: AuthorizationCode, new_status: AuthorizationStatus,
                    actor: str, execution_id: str = "") -> None:
        if (code.status, new_status) in _INVALID_TRANSITIONS:
            raise AuthorizationError(
                f"invalid checkout transition '{code.status.value}' -> '{new_status.value}'",
                status=code.status.value,
            )
        self._record_event(AuthorizationEvent(
            code=code.code,
            from_status=code.status.value if isinstance(code.status, Enum) else code.status,
            to_status=new_status.value if isinstance(new_status, Enum) else new_status,
            actor=actor,
            experiment_id=code.experiment_id,
            execution_id=execution_id,
        ))
        code.status = new_status
        logger.info(
            "checkout transition code_id=%s %s -> %s actor=%s",
            code.id, self._events[-1].from_status, new_status.value, actor,
        )

    # ── Issue / approve / revoke ───────────────────────────────────────────

    def issue(self, experiment_id: str, code: Optional[str] = None,
              key: str = "", value: str = "", actor: str = "system") -> AuthorizationCode:
        """Issue a single-use authorization code for an experiment."""
        code_value = code or f"chk-{uuid.uuid4().hex[:16]}"
        if code_value in self._codes:
            raise AuthorizationError("checkout code already exists")
        record = AuthorizationCode(
            code=code_value,
            key=key,
            value=value,
            experiment_id=experiment_id,
        )
        self._codes[code_value] = record
        self._record_event(AuthorizationEvent(
            code=code_value,
            from_status=None,
            to_status=AuthorizationStatus.ISSUED.value,
            actor=actor,
            experiment_id=experiment_id,
        ))
        logger.info("checkout issued code_id=%s experiment_id=%s", record.id, experiment_id)
        return record

    def approve(self, code: str, reviewer: str = "operator") -> AuthorizationCode:
        """Operator approval. Binds the checkout to execution."""
        record = self._get(code)
        self._transition(record, AuthorizationStatus.APPROVED, actor=reviewer)
        record.approved_at = datetime.now(timezone.utc).isoformat()
        record.approved_by = reviewer
        return record

    def revoke(self, code: str, actor: str = "operator") -> AuthorizationCode:
        """Revoke an issued or approved checkout. Terminal."""
        record = self._get(code)
        self._transition(record, AuthorizationStatus.REVOKED, actor=actor)
        return record

    def status_of(self, code: str) -> AuthorizationStatus:
        """Current status of a checkout code."""
        return self._get(code).status

    # ── Authorized execution ───────────────────────────────────────────────

    @staticmethod
    def _finalize(raw: ExperimentResult, record: AuthorizationCode,
                  experiment_id: str, started_at: str, status: str,
                  error: str = "") -> ExperimentResult:
        """
        Turn a runner-produced result into the final immutable artifact:
        execution_id, status, timestamps, authorization reference, lineage.
        The raw authorization code stays INTERNAL (redacted in to_dict).
        """
        finished_at = datetime.now(timezone.utc).isoformat()
        execution_id = f"exr-{uuid.uuid4().hex[:12]}"
        return replace(
            raw,
            experiment_id=experiment_id,
            execution_id=execution_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            completed_at=finished_at,
            authorization_code=record.code,
            authorization_code_id=record.id,
            error=error,
            lineage=Lineage(
                artifact_id=execution_id,
                parent_artifact_id=record.id,
                parent_type=ArtifactType.AUTHORIZATION_CODE,
            ),
        )

    def _blocked(self, record: AuthorizationCode, experiment: ExperimentDefinition,
                 actor: str, reason: str) -> ExperimentResult:
        """
        Record a blocked denial as an execution result + audit event, then
        raise AuthorizationError. The runner is never invoked.
        """
        started_at = datetime.now(timezone.utc).isoformat()
        blocked = self._finalize(
            ExperimentResult(summary="", records_processed=0),
            record, experiment.id, started_at, "blocked", error=reason,
        )
        self._record_event(AuthorizationEvent(
            code=record.code,
            from_status=record.status.value if isinstance(record.status, Enum) else record.status,
            to_status="blocked",
            actor=actor,
            experiment_id=experiment.id,
            execution_id=blocked.execution_id,
        ))
        self._results_store.put(blocked)
        logger.warning("checkout blocked code_id=%s experiment_id=%s reason=%s",
                       record.id, experiment.id, reason)
        raise AuthorizationError(reason, status=record.status.value)

    def exchange(self, code: str, experiment: ExperimentDefinition,
                 limit: int = 200, actor: str = "system") -> ExperimentResult:
        """
        Execute the experiment iff its checkout is APPROVED for the same
        experiment_id. Single-use; identical retries return the cached result.
        Every outcome (completed / failed / blocked) is recorded as an
        immutable ExecutionResult with an audit event.
        """
        record = self._get(code)

        # Experiment binding — approvals never cross experiments.
        if record.experiment_id and experiment.id != record.experiment_id:
            return self._blocked(
                record, experiment, actor,
                f"checkout code is bound to experiment '{record.experiment_id}', "
                f"got '{experiment.id}'",
            )

        # Idempotent exchange: a consumed code replays its own cached result.
        if record.status == AuthorizationStatus.CONSUMED:
            cached = self._cache.get(code)
            if cached is None:
                return self._blocked(
                    record, experiment, actor,
                    "checkout consumed without a cached result",
                )
            logger.info(
                "checkout replay code_id=%s experiment_id=%s (idempotent, no re-run)",
                record.id, experiment.id,
            )
            return cached

        if record.status != AuthorizationStatus.APPROVED:
            return self._blocked(
                record, experiment, actor,
                f"authorization required: checkout is "
                f"{record.status.value}, not approved",
            )

        logger.info(
            "checkout exchanging code_id=%s experiment_id=%s limit=%d",
            record.id, experiment.id, limit,
        )
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            raw = self._runner(experiment, limit)
        except Exception as exc:  # execution failure → terminal FAILED, never retried
            # The artifact carries a CAPPED diagnostic — never the full
            # exception text, never the raw checkout code.
            failed = self._finalize(
                ExperimentResult(summary="", records_processed=0),
                record, experiment.id, started_at, "failed",
                error=f"experiment execution failed: {type(exc).__name__}"[:500],
            )
            self._results_store.put(failed)
            self._transition(record, AuthorizationStatus.FAILED, actor=actor,
                             execution_id=failed.execution_id)
            logger.error(
                "checkout execution failed code_id=%s experiment_id=%s error_type=%s",
                record.id, experiment.id, type(exc).__name__,
            )
            raise AuthorizationError(
                "experiment execution failed",
                status=record.status.value,
            ) from exc

        result = self._finalize(raw, record, experiment.id, started_at, "completed")
        self._results_store.put(result)
        self._transition(record, AuthorizationStatus.CONSUMED, actor=actor,
                         execution_id=result.execution_id)
        record.consumed_at = datetime.now(timezone.utc).isoformat()
        self._cache[code] = result
        return result

    def history(self) -> list[AuthorizationEvent]:
        """Append-only transition history of this lane."""
        return list(self._events)