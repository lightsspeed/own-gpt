"""Shared PromQL reference validation for ops/ config-as-code tests (V2.2 P2.2).

Mirrors the bounded-label policy of app/core/metrics.py: metric names must be
ones this process can actually emit, and none of the forbidden identifier
words may appear anywhere in queries, alerts, dashboards, or compose files.
"""

from __future__ import annotations

import re

from app.core import metrics as core_metrics

# Identifiers that must NEVER surface in observability configuration.
FORBIDDEN_WORDS = [
    "user_id",
    "user_hash",
    "session_id",
    "conversation_id",
    "message_id",
    "request_id",
    "run_id",
    "extraction_run_id",
    "memory_id",
]

_METRIC_TOKEN = re.compile(r"(?<![A-Za-z0-9_])owngpt_[A-Za-z0-9_]+")
_SERIES_HEAD = re.compile(r"^([a-z0-9_]+)(\{.*\})?$")
_VALUE_PATTERN = re.compile(r"^-?\d+(\.\d+)?([+-]\d+(\.\d+)?)?x\d+$")


def known_metric_names() -> set[str]:
    return set(core_metrics.registered_metric_names()) | {"up"}


def unknown_metric_refs(expr: str) -> set[str]:
    known = known_metric_names()
    return {m for m in _METRIC_TOKEN.findall(expr) if m not in known}


def forbidden_words_present(text: str) -> list[str]:
    return [w for w in FORBIDDEN_WORDS if w in text]


def assert_no_unknown_metric_refs(expr: str) -> None:
    unknown = unknown_metric_refs(expr)
    assert not unknown, f"PromQL references unknown metrics: {sorted(unknown)}"


def assert_no_forbidden_words(text: str) -> None:
    found = forbidden_words_present(text)
    assert not found, f"forbidden identifier words found: {sorted(found)}"


def assert_valid_series_spec(series: str, values: str) -> None:
    head = series.split("{", 1)[0]
    assert _SERIES_HEAD.match(series), f"malformed series spec: {series!r}"
    assert head in known_metric_names(), f"unknown metric in series spec: {head}"
    assert _VALUE_PATTERN.match(values), f"malformed values spec: {values!r}"