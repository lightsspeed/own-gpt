"""Sandbox runner — executes tool core functions in an isolated subprocess.

Isolation guarantees (per the roadmap):
  - separate OS process (no shared memory with the app server)
  - hard wall-clock timeout (default 10s)
  - memory cap via resource limits (RLIMIT_AS)
  - restricted environment (no inherited secrets or network credentials)
  - stdout is captured and returned to the caller

Network egress restriction at the container level (Docker/WASM) remains future
work; the subprocess boundary already prevents direct access to the app server's
process memory, open connections, and checkpointer state.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_MEMORY_MB = 256

# The child payload executed in the sandboxed interpreter.
_SANDBOX_PAYLOAD = r"""
import json, sys

def _limit_memory(max_bytes: int):
    try:
        import resource
    except ImportError:
        return  # resource limits are POSIX-only; subprocess timeout still applies
    try:
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    except (ValueError, OSError):
        pass

def main():
    try:
        payload = json.loads(sys.stdin.read())
        module_name = payload["module"]
        func_name = payload["func"]
        args = payload["args"]
        kwargs = payload["kwargs"]
        max_memory_bytes = payload.get("max_memory_bytes") or 0
        mod = __import__(module_name, fromlist=[func_name])
        fn = getattr(mod, func_name)
        if max_memory_bytes:
            # Apply the cap only after imports so numpy/OpenBLAS can initialize.
            _limit_memory(max_memory_bytes)
        result = fn(*args, **kwargs)
        print(json.dumps({"ok": True, "result": result}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
"""


@dataclass
class SandboxResult:
    ok: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: float = 0.0
    timed_out: bool = False


# LLM / external API credentials — the platform's own tools must not read these
_SECRET_ENV_PREFIXES = ("OPENAI", "TAVILY", "ANTHROPIC", "AZURE", "LANGCHAIN", "LANGSMITH", "AWS_")
_SECRET_ENV_KEYS = frozenset()


def _sandbox_env() -> dict:
    """Environment for sandboxed children.

    Passes through platform configuration (DB/Redis hosts) so tools can reach
    platform services, but strips secrets and LLM credentials.
    """
    env = {}
    for key, value in os.environ.items():
        if key in _SECRET_ENV_KEYS or key.startswith(_SECRET_ENV_PREFIXES):
            continue
        env[key] = value
    return env


def run_sandboxed(
    module_name: str,
    func_name: str,
    args: Optional[list] = None,
    kwargs: Optional[dict] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
) -> SandboxResult:
    """Execute `module_name.func_name` in a sandboxed subprocess."""
    payload = {
        "module": module_name,
        "func": func_name,
        "args": list(args or []),
        "kwargs": dict(kwargs or {}),
        "max_memory_bytes": max_memory_mb * 1024 * 1024,
    }
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _SANDBOX_PAYLOAD],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_sandbox_env(),
        )
    except subprocess.TimeoutExpired:
        duration = (time.perf_counter() - start) * 1000
        return SandboxResult(
            ok=False,
            error=f"Sandboxed execution exceeded {timeout_seconds}s timeout",
            duration_ms=duration,
            timed_out=True,
        )

    duration = (time.perf_counter() - start) * 1000
    stdout = proc.stdout.strip()

    if proc.returncode == 0:
        try:
            data = json.loads(stdout)
            if data.get("ok"):
                return SandboxResult(ok=True, output=str(data.get("result", "")), duration_ms=duration)
            return SandboxResult(
                ok=False, error=data.get("error"), output=stdout, duration_ms=duration
            )
        except json.JSONDecodeError:
            return SandboxResult(ok=False, error="Unexpected sandbox output", output=stdout, duration_ms=duration)

    return SandboxResult(
        ok=False,
        error=f"Sandbox exit code {proc.returncode}: {proc.stderr.strip()[:300]}",
        output=stdout,
        duration_ms=duration,
    )
