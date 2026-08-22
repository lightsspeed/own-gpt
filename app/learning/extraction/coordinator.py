"""Distributed execution coordination for memory extraction (V2.2 P1).

Provides the two coordination primitives that replace the old in-process-only
controls, using the Redis that OwnGPT already depends on in production
(redis:7-alpine compose service, arq ingestion worker, pipeline tracing):

1. Single-flight claim — at most ONE extraction per logical conversation turn
   across ALL application workers. Turn identity is the immutable chat_messages
   primary key of the user message that starts the turn (never a timestamp):
       key:   memory:extraction:sf:{session_id}:{user_message_id}
       value: owner worker label (informational)
       op:    SET NX EX <MEMORY_EXTRACTION_SINGLE_FLIGHT_TTL_SECONDS>
   The TTL is a crash safety net: if the claiming worker dies mid-extraction
   the claim expires and a later re-schedule may retry. Re-execution is always
   safe because MemoryService.create_memory is idempotent (content_hash dedupe).

2. Distributed throttle — at most one extraction per
   MEMORY_EXTRACTION_TURN_INTERVAL user turns, per session, across workers.
   Atomic via a Lua script (read-compare-set; no TOCTOU window):
       key:   memory:extraction:throttle:{session_id}
       value: sequence of the last extracted user message
       op:    GET, then SET EX <MEMORY_EXTRACTION_THROTTLE_TTL_SECONDS>
              when the distance >= interval or the key is absent
   The TTL protects against orphaned markers when a worker crashes without
   finishing (marker expires after 24h by default, extraction resumes).

Failure policy — FAIL OPEN, mandatory:
- Redis unavailable / any Redis error → log + fall back to in-process state
  (per-worker). The chat request is NEVER affected by coordination.
- In-process fallbacks provide the original per-process guarantees (throttle
  per session, duplicate suppression within the process); cross-worker
  duplicates degrade to the idempotent create_memory dedupe. Availability is
  preserved; correctness is preserved by idempotency.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from app.core.config import settings
from app.core.logging_config import sanitize_exception_message
from app.core import metrics as core_metrics
from app.learning.extraction import observability

logger = logging.getLogger(__name__)

# Lua throttle script — atomic read-compare-set. Mirrored by FakeRedis in the
# test suite; keep both in sync.
_THROTTLE_SCRIPT = """
local last = redis.call('GET', KEYS[1])
if last == false then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
  return 1
end
if (tonumber(ARGV[1]) - tonumber(last)) >= tonumber(ARGV[3]) then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
  return 1
end
return 0
"""


def _claim_key(session_id: str, user_msg_id: object) -> str:
    return f"memory:extraction:sf:{session_id}:{user_msg_id}"


def _throttle_key(session_id: str) -> str:
    return f"memory:extraction:throttle:{session_id}"


class ExecutionCoordinator:
    """Coordinates extraction execution across workers (Redis) with
    in-process fallback state. Thread-safe. All methods fail open."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        client=None,
        sf_ttl: int = settings.MEMORY_EXTRACTION_SINGLE_FLIGHT_TTL_SECONDS,
        interval: int = settings.MEMORY_EXTRACTION_TURN_INTERVAL,
        throttle_ttl: int = settings.MEMORY_EXTRACTION_THROTTLE_TTL_SECONDS,
    ) -> None:
        self._redis_url = redis_url
        self._client = client  # test injection
        self._script = None
        self._sf_ttl = sf_ttl
        self._interval = interval
        self._throttle_ttl = throttle_ttl
        # In-process fallback state (used when Redis is unavailable or absent).
        self._memory_lock = threading.Lock()
        self._memory_claims: set[tuple[str, object]] = set()
        self._memory_throttle: dict[str, int] = {}

    # -- Redis plumbing -----------------------------------------------------

    def _get_redis(self):
        """Lazy Redis client; None when no URL and no injected client."""
        if self._client is not None:
            return self._client
        if self._redis_url is None:
            return None
        try:
            import redis

            self._client = redis.from_url(self._redis_url)
            return self._client
        except Exception as exc:  # pragma: no cover - import/env failure
            logger.warning("memory_extraction_redis_init_failed error=%s", exc)
            self._redis_url = None
            return None

    def _get_script(self, r):
        if self._script is None:
            self._script = r.register_script(_THROTTLE_SCRIPT)
        return self._script

    # -- Single-flight claim -----------------------------------------------

    def claim_turn(
        self,
        session_id: str,
        user_msg_id: object,
        owner: str = "worker",
        run_id: Optional[str] = None,
    ) -> bool:
        """Claim the exclusive right to extract this turn. Returns True when
        this caller may proceed. Atomic across workers via SET NX EX; falls
        back to in-process state when Redis is unreachable.

        Metrics contract: every claim call counts exactly once as
        redis_claim_success_total or redis_claim_conflict_total; a Redis
        failure additionally counts redis_fallback_total{operation=claim}.
        """
        r = self._get_redis()
        if r is not None:
            try:
                claimed = bool(
                    r.set(_claim_key(session_id, user_msg_id), owner, ex=self._sf_ttl, nx=True)
                )
            except Exception as exc:
                observability.emit_redis_unavailable(
                    op="claim",
                    error_class=type(exc).__name__,
                    error_message=sanitize_exception_message(str(exc)),
                    run_id=run_id,
                )
                claimed = None
            else:
                if claimed:
                    core_metrics.safe_count("redis_claim_success_total")
                else:
                    core_metrics.safe_count("redis_claim_conflict_total")
                return claimed
        with self._memory_lock:
            key = (session_id, user_msg_id)
            if key in self._memory_claims:
                core_metrics.safe_count("redis_claim_conflict_total")
                return False
            self._memory_claims.add(key)
            core_metrics.safe_count("redis_claim_success_total")
            return True

    def release_turn(
        self, session_id: str, user_msg_id: object, run_id: Optional[str] = None
    ) -> None:
        """Best-effort release after the extraction task finishes. The Redis
        TTL is the authoritative cleanup for crashed workers; releasing on
        completion simply allows a legitimate later re-schedule sooner."""
        r = self._get_redis()
        if r is not None:
            try:
                r.delete(_claim_key(session_id, user_msg_id))
            except Exception as exc:
                observability.emit_redis_unavailable(
                    op="release",
                    error_class=type(exc).__name__,
                    error_message=sanitize_exception_message(str(exc)),
                    run_id=run_id,
                )
        with self._memory_lock:
            self._memory_claims.discard((session_id, user_msg_id))

    # -- Distributed throttle ----------------------------------------------

    def throttle_allowed(
        self, session_id: str, sequence: int, run_id: Optional[str] = None
    ) -> bool:
        """True when an extraction may run for this turn given the per-session
        interval throttle. Atomic across workers (Lua read-compare-set);
        TTL-protected against crashed workers; in-process fallback otherwise."""
        r = self._get_redis()
        if r is not None:
            try:
                script = self._get_script(r)
                result = script(
                    keys=[_throttle_key(session_id)],
                    args=[str(sequence), str(self._throttle_ttl), str(self._interval)],
                )
                return bool(result)
            except Exception as exc:
                observability.emit_redis_unavailable(
                    op="throttle",
                    error_class=type(exc).__name__,
                    error_message=sanitize_exception_message(str(exc)),
                    run_id=run_id,
                )
        with self._memory_lock:
            last = self._memory_throttle.get(session_id)
            if last is not None and (sequence - last) < self._interval:
                return False
            self._memory_throttle[session_id] = sequence
            return True

    # -- Test helper ---------------------------------------------------------

    def clear(self) -> None:
        """Reset in-process fallback state (test/restart simulation only)."""
        with self._memory_lock:
            self._memory_claims.clear()
            self._memory_throttle.clear()


# Process-wide singleton. Built once at import; used by the extraction
# scheduler. Tests construct fresh instances (injected fake Redis or no Redis).
coordinator = ExecutionCoordinator(redis_url=settings.REDIS_URL)
