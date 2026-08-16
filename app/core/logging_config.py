"""Structured JSON logging foundation (V2.2 P2.1).

OwnGPT ships a hand-rolled kv-pair logging style that depends on the
launcher for level/format. This module provides the application-owned
foundation:

- JsonFormatter — one JSON line per record: ts, level, logger, event,
  message, plus whitelisted extra fields (run_id, session, reason, ...).
- setup_logging() — installs the JSON handler on the root logger with a
  configurable LOG_LEVEL (settings.LOG_LEVEL).
- sanitize_exception_message() — scrubs credentials/secret shapes from
  exception text before it reaches logs (never log raw provider payloads).
- classify_exception() — maps exceptions to the bounded reason taxonomy
  (see app/core/metrics.py REASONS).

Invariants:
- Logging must never break chat: the stdlib logging framework swallows
  handler errors by design, and this module never raises from formatting.
- Whitelist-only extras: only ALLOWED_EXTRA_FIELDS ever reach the JSON
  payload — a stray extra is dropped, never emitted.
- No message content, no prompts, no memory statements, no tokens,
  no API keys (key shapes are scrubbed by sanitize_exception_message).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

# Fields permitted as structured extras on any log record. Anything else
# (including accidental content) is dropped by JsonFormatter.
ALLOWED_EXTRA_FIELDS: frozenset[str] = frozenset(
    {
        "event",
        "run_id",
        "request_id",
        "session",
        "turn",
        "reason",
        "gate",
        "provider",
        "model",
        "attempt",
        "written",
        "duration_ms",
        "op",
        "operation",
        "status",
        "outcome",
        "kind",
        "tokens_in",
        "tokens_out",
        "error_class",
        "error_message",
        "user_hash",
        "queue_depth",
        "dropped",
        "entity",
    }
)

# Credential shapes scrubbed from exception messages before logging.
# Narrow by design (mirrors app/agent/guardrail.py SECRET_PATTERNS) so
# innocent text is never mangled.
_SECRET_SHAPES: tuple[re.Pattern, ...] = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
)

_SCRUB = "sk-[REDACTED]"


def sanitize_exception_message(message: str, limit: int = 500) -> str:
    """Scrub credential shapes from an exception string.

    Never trust provider exception bodies: an HTTP client error may embed
    URLs, headers, or keys. Any unknown shape is additionally truncated to
    `limit` chars to bound log size.
    """
    if not message:
        return ""
    scrubbed = message
    for pattern in _SECRET_SHAPES:
        scrubbed = pattern.sub(_SCRUB, scrubbed)
    return scrubbed[:limit]


def classify_exception(exc: BaseException) -> str:
    """Map an exception to the bounded reason taxonomy (metrics.REASONS).

    Module-prefix heuristics only — never inspects exception payloads.
    """
    module = type(exc).__module__ or ""
    if any(module.startswith(p) for p in ("sqlalchemy", "psycopg", "asyncpg", "pg8000")):
        return "DB_ERROR"
    if any(
        module.startswith(p)
        for p in (
            "openai",
            "httpx",
            "requests",
            "urllib3",
            "aiohttp",
            "langchain_ollama",
            "langchain_openai",
            "langchain_core",
            "ollama",
            "langsmith",
        )
    ):
        return "PROVIDER_UNAVAILABLE"
    if type(exc).__name__ == "ConnectionError" and module == "builtins":
        return "PROVIDER_UNAVAILABLE"
    return "UNKNOWN_ERROR"


class JsonFormatter(logging.Formatter):
    """One JSON object per log line.

    Fields: ts, level, logger, event (extra), message, then any
    ALLOWED_EXTRA_FIELDS present on the record. Exception info becomes
    error_class + sanitized error_message (never the raw traceback text).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in sorted(ALLOWED_EXTRA_FIELDS):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            exc_type, exc, _tb = record.exc_info
            payload["error_class"] = exc_type.__name__
            payload["error_message"] = sanitize_exception_message(str(exc))
        try:
            return json.dumps(payload, default=str)
        except Exception:  # pragma: no cover - defensive: never fail logging
            return json.dumps(
                {"ts": payload["ts"], "level": payload["level"], "message": "log_format_error"}
            )


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Install the JSON handler on the root logger (idempotent).

    Replaces existing root handlers so application logs are JSON regardless
    of the launcher (uvicorn etc.). Never raises.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    try:
        root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    except Exception:  # pragma: no cover - invalid level strings fall back
        root.setLevel(logging.INFO)
    return root
