"""
V4.7 - Tool Result & Failure Handling

Standardizes every tool's output and failure behavior so the Agent can
reliably reason about completed / failed / blocked / empty / timeout
outcomes WITHOUT parsing arbitrary strings or exceptions.

Design invariants:
  - ToolResult is THE boundary object for all tool outcomes. Existing
    tool implementations (Memory V2, KB, Tavily, document retrieval)
    are NEVER modified; normalization happens at the boundary only.
  - Failures are mapped to stable ERROR_CODES. Raw provider/exception
    text is never the primary client-facing error - error_code is.
  - Lineage preserved: execution_id, step_id, latency_ms, tool.
  - No new telemetry or persistence: pure dataclasses + normalizers.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# API-key style secrets redacted from internal error detail.
_SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b|\bapi[_-]?key[=: ]+[^\s,;]{8,}", re.IGNORECASE)


def _sanitize_error(error: str) -> str:
    """Cap and clean internal error detail (never the primary signal)."""
    text = str(error)
    text = _SECRET_PATTERN.sub("[REDACTED]", text)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) > MAX_ERROR_CHARS:
        text = text[: MAX_ERROR_CHARS - 3] + "..."
    return text

# All legal ToolResult statuses. The Agent reasons ONLY over these.
VALID_TOOL_STATUSES = frozenset({"completed", "failed", "blocked", "empty", "timeout"})

# Stable error taxonomy. Primary client error is always one of these codes.
ERROR_CODES = frozenset({
    "TOOL_FAILED",
    "TOOL_BLOCKED",
    "TOOL_EMPTY",
    "TOOL_TIMEOUT",
    "PROVIDER_UNAVAILABLE",
    "INVALID_TOOL_ARGUMENTS",
    "AUTHORIZATION_REQUIRED",
})

# Provider-layer exception class names mapped to PROVIDER_UNAVAILABLE.
_PROVIDER_ERROR_CLASS_NAMES = frozenset({
    "APIConnectionError",
    "RateLimitError",
    "ProviderUnavailableError",
    "ServiceUnavailableError",
    "ConnectionError",
    "APITimeoutError",
})

# Internal detail cap - never persist/display unbounded provider text.
MAX_ERROR_CHARS = 300


@dataclass
class ToolResult:
    """Standardized outcome of ONE tool execution (boundary artifact).

    Fields:
        status:       one of VALID_TOOL_STATUSES.
        tool:         canonical tool name (e.g. 'remember_user_fact').
        output:       usable result text ("" for non-completed statuses).
        error_code:   stable ERROR_CODES value - the PRIMARY client error.
        error:        sanitized internal detail (never primary).
        execution_id: lineage - originating execution run.
        step_id:      lineage - originating plan step.
        latency_ms:   observed execution latency.
        metadata:     structured extras (kept separate from output).
    """

    status: str
    tool: str
    output: str = ""
    error_code: Optional[str] = None
    error: Optional[str] = None
    execution_id: str = ""
    step_id: Optional[int] = None
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in VALID_TOOL_STATUSES:
            raise ValueError(
                f"invalid ToolResult status {self.status!r}; "
                f"must be one of {sorted(VALID_TOOL_STATUSES)}"
            )
        if self.error is not None:
            self.error = _sanitize_error(self.error)

    @property
    def has_output(self) -> bool:
        return bool(self.output and self.output.strip())

    def to_dict(self) -> dict:
        """Serialization-safe view; error stays capped, codes stay primary."""
        return {
            "status": self.status,
            "tool": self.tool,
            "output": self.output,
            "error_code": self.error_code,
            "error": self.error,
            "execution_id": self.execution_id,
            "step_id": self.step_id,
            "latency_ms": self.latency_ms,
            "metadata": dict(self.metadata),
        }


def normalize_execution(
    execution,
    tool: str,
    execution_id: str = "",
    step_id: Optional[int] = None,
    latency_ms: float = 0.0,
    metadata: Optional[dict] = None,
) -> ToolResult:
    """Boundary normalizer: tool_gate execution object -> ToolResult.

    Maps the existing gate statuses onto the stable taxonomy:
      executed / allowed + non-empty -> completed
      executed / allowed + empty     -> empty (TOOL_EMPTY)
      denied / blocked               -> blocked (TOOL_BLOCKED)
      pending / approved-unacked     -> blocked (AUTHORIZATION_REQUIRED)
      timed_out                      -> timeout (TOOL_TIMEOUT)
      failed / unknown               -> failed (TOOL_FAILED)
    """
    status = getattr(execution, "status", "") or ""
    result = getattr(execution, "result", "") or ""
    error = getattr(execution, "error", None)
    meta = dict(metadata or {})

    if not isinstance(result, str):
        result = str(result) if result is not None else ""

    if status in ("executed", "allowed"):
        if result.strip():
            return ToolResult(
                status="completed", tool=tool, output=result,
                execution_id=execution_id, step_id=step_id,
                latency_ms=latency_ms, metadata=meta,
            )
        return ToolResult(
            status="empty", tool=tool, output="",
            error_code="TOOL_EMPTY",
            error=(error or "Tool executed but returned no usable output."),
            execution_id=execution_id, step_id=step_id,
            latency_ms=latency_ms, metadata=meta,
        )

    if status in ("denied", "blocked"):
        return ToolResult(
            status="blocked", tool=tool, output="",
            error_code="TOOL_BLOCKED",
            error=(error or "Tool execution was blocked."),
            execution_id=execution_id, step_id=step_id,
            latency_ms=latency_ms, metadata=meta,
        )

    if status in ("pending", "approved"):
        return ToolResult(
            status="blocked", tool=tool, output="",
            error_code="AUTHORIZATION_REQUIRED",
            error=(error or "Tool execution requires operator approval."),
            execution_id=execution_id, step_id=step_id,
            latency_ms=latency_ms, metadata=meta,
        )

    if status in ("timed_out", "timeout"):
        return ToolResult(
            status="timeout", tool=tool, output="",
            error_code="TOOL_TIMEOUT",
            error=(error or "Tool execution timed out."),
            execution_id=execution_id, step_id=step_id,
            latency_ms=latency_ms, metadata=meta,
        )

    return ToolResult(
        status="failed", tool=tool, output="",
        error_code="TOOL_FAILED",
        error=(error or f"Tool execution failed (status={status!r})."),
        execution_id=execution_id, step_id=step_id,
        latency_ms=latency_ms, metadata=meta,
    )


def normalize_exception(
    exc: Exception,
    tool: str,
    execution_id: str = "",
    step_id: Optional[int] = None,
    latency_ms: float = 0.0,
) -> ToolResult:
    """Exception normalizer: exception -> stable ToolResult.

      TimeoutError                    -> timeout  (TOOL_TIMEOUT)
      ValueError                      -> failed   (INVALID_TOOL_ARGUMENTS)
      known provider error classes    -> failed   (PROVIDER_UNAVAILABLE)
      anything else                   -> failed   (TOOL_FAILED)
    """
    cls_name = exc.__class__.__name__
    if isinstance(exc, TimeoutError) or "Timeout" in cls_name:
        return ToolResult(
            status="timeout", tool=tool, error_code="TOOL_TIMEOUT",
            error=f"Tool execution timed out: {exc}",
            execution_id=execution_id, step_id=step_id, latency_ms=latency_ms,
        )
    if isinstance(exc, ValueError):
        return ToolResult(
            status="failed", tool=tool, error_code="INVALID_TOOL_ARGUMENTS",
            error=f"Invalid tool arguments: {exc}",
            execution_id=execution_id, step_id=step_id, latency_ms=latency_ms,
        )
    if cls_name in _PROVIDER_ERROR_CLASS_NAMES:
        return ToolResult(
            status="failed", tool=tool, error_code="PROVIDER_UNAVAILABLE",
            error=f"Provider unavailable: {exc}",
            execution_id=execution_id, step_id=step_id, latency_ms=latency_ms,
        )
    return ToolResult(
        status="failed", tool=tool, error_code="TOOL_FAILED",
        error=f"Tool execution failed: {exc}",
        execution_id=execution_id, step_id=step_id, latency_ms=latency_ms,
    )