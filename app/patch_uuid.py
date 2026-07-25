"""
Patch uuid_utils with a pure-Python uuid7 before any langchain import.
Must be imported before langchain_core to prevent DLL load failure.
"""

import os
import time
import types
import uuid as _uuid
import sys as _sys
from uuid import UUID

_ALREADY_PATCHED = "_uuid_utils_patched" in _sys.modules


def _patch():
    if _ALREADY_PATCHED:
        return

    def uuid7(nanoseconds: int | None = None, *, timestamp: float | None = None, nanos: int | None = None) -> UUID:
        if nanoseconds is not None:
            timestamp_ms = nanoseconds // 1_000_000
        elif timestamp is not None:
            timestamp_ms = int(timestamp * 1000) + (nanos // 1_000_000 if nanos else 0)
        else:
            timestamp_ms = time.time_ns() // 1_000_000

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

    _uuid_utils_mod = types.ModuleType("uuid_utils")
    _uuid_utils_mod.uuid7 = uuid7

    _compat_mod = types.ModuleType("uuid_utils.compat")
    _compat_mod.uuid7 = uuid7

    _sys.modules["uuid_utils"] = _uuid_utils_mod
    _sys.modules["uuid_utils.compat"] = _compat_mod
    _sys.modules["_uuid_utils_patched"] = True


_patch()
