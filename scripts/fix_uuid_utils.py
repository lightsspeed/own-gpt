"""
Pure-Python replacement for uuid_utils (Rust C extension blocked by AppLocker).
Provides uuid7() used by langchain-core for monotonic time-ordered UUIDs.
"""

import os
import time
import types
import uuid as _uuid
import sys as _sys
from uuid import UUID


def uuid7(nanoseconds: int | None = None) -> UUID:
    """Generate a UUIDv7 (time-ordered) in pure Python.

    UUIDv7 format:
      - 48 bits: Unix timestamp in milliseconds
      - 74 bits: random
      -  2 bits: UUID version (7)
      - 12 bits: UUID variant (RFC 4122)
    """
    if nanoseconds is None:
        nanoseconds = time.time_ns()
    timestamp_ms = nanoseconds // 1_000_000

    time_high = (timestamp_ms >> 16) & 0xFFFFFFFF
    time_mid = timestamp_ms & 0xFFFF

    clock_seq = os.urandom(1)[0] & 0x3F | 0x80
    node = int.from_bytes(os.urandom(6), "big") & ((1 << 48) - 1)
    clock_seq_low = os.urandom(1)[0] & 0xFF

    fields = (
        time_high,
        time_mid,
        (timestamp_ms & 0x0FFF) | 0x7000,
        clock_seq,
        clock_seq_low,
        node,
    )
    return _uuid.UUID(fields=fields)


# Inject into sys.modules so langchain_core imports find uuid7
_uuid_utils_mod = types.ModuleType("uuid_utils")
_uuid_utils_mod.uuid7 = uuid7

_compat_mod = types.ModuleType("uuid_utils.compat")
_compat_mod.uuid7 = uuid7

_sys.modules["uuid_utils"] = _uuid_utils_mod
_sys.modules["uuid_utils.compat"] = _compat_mod
