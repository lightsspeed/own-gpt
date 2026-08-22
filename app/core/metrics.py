"""Prometheus metrics for memory extraction (V2.2 P2.1).

Namespace: owngpt_memory_extraction_* (namespace="owngpt",
subsystem="memory_extraction"). In-process counters/gauges/histograms only —
no network calls, no DB queries, no per-metric I/O. Scraping collects
current state via the exported registry.

CARDINALITY POLICY (constitution-level):
- Labels are finite enums ONLY (see label sets below). Every label value is
  validated before use.
- NEVER labels: user_id, user_hash, session_id, conversation_id, message_id,
  request_id, extraction_run_id, memory_id, raw error text, prompts,
  memory statements. These may appear in structured logs, never in metrics.
- `model` is bounded by the application's configured allowlist plus a
  single catch-all "other" — free-form model strings can never reach
  Prometheus.

FAILURE ISOLATION: ExtractionMetrics.count/observe/set are fail-open —
any instrumentation exception (including a broken metric object) is
swallowed so observability can never break chat or extraction.
validate() is the strict path used by tests and pre-flight checks.

Exported value functions:
- render_metrics() -> bytes  (for the /metrics endpoint)
"""

from __future__ import annotations

import json
import logging
from functools import partial
from typing import Any, Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# -- Label sets: finite enums -------------------------------------------------

REASONS: frozenset[str] = frozenset(
    {
        # scheduling exits
        "DISABLED",        # MEMORY_V2_GRAPH off or no user_msg_id
        "CLAIM_CONFLICT",  # single-flight claim denied (already in flight / extracted)
        "QUEUE_FULL",      # bounded executor queue saturated
        # run exits
        "CONVERSATION_MISSING",  # conversation row absent
        "NO_TURN",               # turn resolution failed (no user msg / no completed reply)
        "INELIGIBLE",            # Gate 1: eval-*, filler, command/recall, general intent
        "THROTTLED",             # Gate 1b: per-session turn interval
        "NO_CANDIDATES",         # LLM returned a valid empty candidate list
        "INVALID_CANDIDATE",     # Gate 3: malformed/oversized/unknown-domain candidates
        "SECRET_DETECTED",       # Gate 3: credential-shaped content (batch dropped)
        # failures (failed_total)
        "LLM_ERROR",        # LLM output unparseable after retries / provider call error
        "DB_ERROR",         # persistence failure
        "PROVIDER_UNAVAILABLE",  # Ollama/OpenAI unreachable or misconfigured
        "WORKER_ERROR",     # executor worker defensive catch
        "UNKNOWN_ERROR",
    }
)

GATES: frozenset[str] = frozenset({"1", "1b", "2", "3"})
OPERATIONS: frozenset[str] = frozenset({"claim", "release", "throttle"})
KINDS: frozenset[str] = frozenset({"input", "output", "total"})
PROVIDERS: frozenset[str] = frozenset({"openai", "ollama", "unknown"})
STATUSES: frozenset[str] = frozenset({"pending", "active"})
# extraction_info gauge: enabled="1" | "0" (constant value 1; the label is the
# signal). Lets alerting distinguish "extraction disabled by config" from
# "extraction silently not running" — never an ID, always bounded.
ENABLE_STATES: frozenset[str] = frozenset({"1", "0"})

# -- Agent (V4.12 / Phase 3.2) label sets --------------------------------------
# ONE authoritative status vocabulary: the V4.12 API contract statuses. The
# SAME value is recorded on the request_completed trace event and the request
# metrics counter at the single finalization boundary (finalize_trace) — the
# trace and Prometheus can never disagree.
AGENT_STATUSES: frozenset[str] = frozenset(
    {"completed", "partial", "failed", "blocked", "cancelled", "timed_out"}
)

# Tool call outcomes as recorded at the shared guarded tool boundary
# (app/agent/tool_gate.py). "blocked" = guardrail denial (never executed);
# "pending" approval-required calls are NOT counted until they terminate
# (each logical call is counted exactly once, with its real outcome).
TOOL_STATUSES: frozenset[str] = frozenset({"completed", "failed", "blocked"})

# Bounded tool-failure taxonomy — raw exception text NEVER becomes a label.
TOOL_ERROR_CODES: frozenset[str] = frozenset(
    {
        "execution_failed",    # in-process run raised (read-only/memory tools)
        "sandbox_failed",      # sandboxed run failed (post-approval)
        "sandbox_timed_out",   # sandboxed run exceeded its deadline
        "unregistered_impl",   # no implementation registered for the tool
        "unknown",
    }
)

# Bounded tool-block taxonomy (guardrail-denied calls). Each code maps to a
# deterministic guardrail reason family; never the raw reason string (which
# can embed user-shaped values, e.g. an offending target).
TOOL_BLOCK_REASONS: frozenset[str] = frozenset(
    {
        "unregistered_tool",
        "deny_listed",
        "fact_too_long",
        "empty_fact",
        "secret_content",
        "session_too_long",
        "invalid_target",
        "invalid_action",
        "approval_required",
        "unknown",
    }
)

# Tool-name allowlist mirrors IMPL_FUNCS in app/agent/tool_gate.py. Kept
# static here so the registry stays import-coupled to nothing; unknown tool
# names collapse to the single catch-all "other".
AGENT_TOOLS: frozenset[str] = frozenset(
    {
        "search_knowledge_base",
        "web_search",
        "sm_integration",
        "remember_user_fact",
        "remember_session_fact",
        "forget_user_fact",
    }
)

_LABEL_SETS: dict[str, frozenset[str]] = {
    "reason": REASONS,
    "gate": GATES,
    "operation": OPERATIONS,
    "kind": KINDS,
    "provider": PROVIDERS,
    "status": STATUSES,
    "enabled": ENABLE_STATES,
}

_AGENT_LABEL_SETS: dict[str, frozenset[str]] = {
    "status": AGENT_STATUSES,
    "error_code": TOOL_ERROR_CODES,
    "reason": TOOL_BLOCK_REASONS,
}

_OTHER_MODEL = "other"
_OTHER_TOOL = "other"

# Durations: queue wait + LLM + persistence for one extraction attempt.
_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)


def bounded_model(model: str) -> str:
    """Map a model string to the bounded label set.

    The allowlist is the configured SUPPORTED_MODELS plus the provider
    defaults (LLM_MODEL / DEFAULT_MODEL) plus the extraction model constant
    itself. Anything else collapses to "other".
    """
    if not model:
        return _OTHER_MODEL
    allowlist: set[str] = {settings.LLM_MODEL, settings.DEFAULT_MODEL, _OTHER_MODEL}
    try:
        allowlist.update(json.loads(settings.SUPPORTED_MODELS))
    except (TypeError, ValueError):  # pragma: no cover - config is trusted
        allowlist.update({"gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"})
    if model in allowlist:
        return model
    return _OTHER_MODEL


def bounded_provider(provider: str) -> str:
    if provider in PROVIDERS:
        return provider
    return "unknown"


def bounded_tool(tool: str) -> str:
    """Map a tool name to the bounded label set (allowlist + "other")."""
    if tool in AGENT_TOOLS:
        return tool
    return _OTHER_TOOL


class ExtractionMetrics:
    """All extraction metrics over one CollectorRegistry.

    Metric names (full): owngpt_memory_extraction_<name>.
    """

    def __init__(self, registry: CollectorRegistry) -> None:
        self._registry = registry
        kwargs = {"namespace": "owngpt", "subsystem": "memory_extraction", "registry": registry}
        counter = partial(Counter, **kwargs)
        gauge = partial(Gauge, **kwargs)
        histogram = partial(Histogram, **kwargs)

        # Scheduling
        self.scheduled_total = counter("scheduled_total", "Extraction attempts enqueued")
        self.skipped_total = counter(
            "skipped_total", "Extraction attempts skipped deterministically", ["reason"]
        )
        self.failed_total = counter(
            "failed_total", "Extraction attempts that failed with an error", ["reason"]
        )
        self.gate_rejections_total = counter(
            "gate_rejections_total", "Gate rejections (slice of skipped_total)", ["gate", "reason"]
        )

        # Execution
        self.started_total = counter("started_total", "Extraction runs started")
        self.completed_total = counter(
            "completed_total", "Extraction runs that reached a terminal decision"
        )
        self.duration_seconds = histogram(
            "duration_seconds", "Extraction attempt duration (claim->terminal)", buckets=_DURATION_BUCKETS
        )
        self.inflight = gauge(
            "inflight",
            "Extraction tasks currently executing in the bounded executor "
            "(owned by the executor; one increment per running task)",
        )
        self.extraction_info = Gauge(
            "owngpt_memory_extraction_info",
            "Extraction scheduling enabled state (constant 1, set once at "
            "startup; enabled=1 when MEMORY_V2_GRAPH is on)",
            ["enabled"],
            registry=registry,
        )

        # LLM
        self.llm_calls_total = counter(
            "llm_calls_total", "LLM extraction calls made", ["provider", "model"]
        )
        self.llm_errors_total = counter(
            "llm_errors_total", "LLM extraction calls that raised", ["provider", "model"]
        )
        self.llm_duration_seconds = histogram(
            "llm_duration_seconds", "LLM extraction call duration", ["provider", "model"],
            buckets=_DURATION_BUCKETS,
        )
        self.llm_tokens_total = counter(
            "llm_tokens_total", "LLM tokens consumed (where the provider reports them)",
            ["provider", "model", "kind"],
        )

        # Memory outcomes (all create_memory writes, documented)
        self.memory_created_total = counter(
            "memory_created_total", "Memory entities persisted", ["status"]
        )
        self.memory_deduplicated_total = counter(
            "memory_deduplicated_total", "create_memory hits an identical existing entity"
        )
        self.memory_conflict_total = counter(
            "memory_conflict_total", "create_memory records a potential-conflict (pending)"
        )
        self.memory_superseded_total = counter(
            "memory_superseded_total", "create_memory supersedes an existing memory"
        )

        # Coordination
        self.redis_claim_success_total = counter(
            "redis_claim_success_total", "Single-flight claims granted (redis or in-process)"
        )
        self.redis_claim_conflict_total = counter(
            "redis_claim_conflict_total", "Single-flight claims denied (redis or in-process)"
        )
        self.redis_fallback_total = counter(
            "redis_fallback_total", "Coordination operations that fell back to in-process state",
            ["operation"],
        )

        # Queue (executor)
        self.queue_depth = gauge("queue_depth", "Pending extraction tasks in the bounded queue")
        self.queue_capacity = gauge("queue_capacity", "Bounded executor queue capacity")

        self._counters = {
            "scheduled_total": self.scheduled_total,
            "skipped_total": self.skipped_total,
            "failed_total": self.failed_total,
            "gate_rejections_total": self.gate_rejections_total,
            "started_total": self.started_total,
            "completed_total": self.completed_total,
            "llm_calls_total": self.llm_calls_total,
            "llm_errors_total": self.llm_errors_total,
            "llm_tokens_total": self.llm_tokens_total,
            "memory_created_total": self.memory_created_total,
            "memory_deduplicated_total": self.memory_deduplicated_total,
            "memory_conflict_total": self.memory_conflict_total,
            "memory_superseded_total": self.memory_superseded_total,
            "redis_claim_success_total": self.redis_claim_success_total,
            "redis_claim_conflict_total": self.redis_claim_conflict_total,
            "redis_fallback_total": self.redis_fallback_total,
        }
        self._histograms = {
            "duration_seconds": self.duration_seconds,
            "llm_duration_seconds": self.llm_duration_seconds,
        }
        self._gauges = {
            "inflight": self.inflight,
            "queue_depth": self.queue_depth,
            "queue_capacity": self.queue_capacity,
            "extraction_info": self.extraction_info,
        }

    # -- strict validation (tests + pre-flight) -------------------------------

    def validate(self, label: str, value: str) -> str:
        """Raise ValueError when a label value is not in its finite set.

        `model` is the exception by design: it has a config-driven allowlist
        plus a single catch-all "other" (never raises). Every other label is
        strict — an unknown value is a misconfiguration, not a collapse.
        """
        if label == "model":
            return bounded_model(value)
        allowed = _LABEL_SETS.get(label)
        if allowed is None:
            raise ValueError(f"unknown label {label!r}")
        if value not in allowed:
            raise ValueError(f"unbounded {label} label value {value!r} (allowed: {sorted(allowed)})")
        return value

    # -- fail-open emitters ---------------------------------------------------

    def _labeled(self, metric, labels: dict[str, str]):
        """Return the labeled child metric, or the metric itself when the
        metric has no labels (labels() on a label-less metric raises)."""
        if not labels:
            return metric
        return metric.labels(**labels)

    def count(self, name: str, amount: int = 1, **labels: str) -> None:
        try:
            metric = self._counters[name]
            validated = self._validate_labels(labels)
            self._labeled(metric, validated).inc(amount)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_count_failed name=%s error=%s", name, exc)

    def observe(self, name: str, value: float, **labels: str) -> None:
        try:
            metric = self._histograms[name]
            validated = self._validate_labels(labels)
            self._labeled(metric, validated).observe(value)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_observe_failed name=%s error=%s", name, exc)

    def set(self, name: str, value: float, **labels: str) -> None:
        try:
            metric = self._gauges[name]
            validated = self._validate_labels(labels)
            self._labeled(metric, validated).set(value)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_set_failed name=%s error=%s", name, exc)

    def gauge_inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        try:
            metric = self._gauges[name]
            validated = self._validate_labels(labels)
            self._labeled(metric, validated).inc(amount)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_inc_failed name=%s error=%s", name, exc)

    def gauge_dec(self, name: str, amount: float = 1.0, **labels: str) -> None:
        try:
            metric = self._gauges[name]
            validated = self._validate_labels(labels)
            self._labeled(metric, validated).dec(amount)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_dec_failed name=%s error=%s", name, exc)

    def _validate_labels(self, labels: dict[str, str]) -> dict[str, str]:
        metric_labels: dict[str, str] = {}
        for name, value in labels.items():
            metric_labels[name] = self.validate(name, value)
        return metric_labels

    @property
    def registry(self) -> CollectorRegistry:
        return self._registry


class AgentMetrics:
    """Agent request + tool metrics over one CollectorRegistry (Phase 3.2).

    Metric names (full): owngpt_agent_<name>. Same cardinality policy as the
    extraction registry: finite enums only, `model`/`tool` bounded by
    allowlist plus one "other" catch-all. Recorded at the TWO authoritative
    agent boundaries:

      - requests      → finalize_trace() (the single finalization boundary:
                        same status as the request_completed trace event, same
                        TokenBudget totals that feed the API contract)
      - tools         → request_tool_execution / execute_approved (the shared
                        guarded tool gate every tool call passes through)
    """

    def __init__(self, registry: CollectorRegistry) -> None:
        self._registry = registry
        kwargs = {"namespace": "owngpt", "subsystem": "agent", "registry": registry}
        counter = partial(Counter, **kwargs)
        histogram = partial(Histogram, **kwargs)

        # Requests (recorded once per finalized request)
        self.requests_total = counter(
            "requests_total", "Agent requests finalized, by API status", ["status"]
        )
        self.request_tokens_total = counter(
            "request_tokens_total", "Agent request tokens consumed, per model", ["model"]
        )
        self.request_cost_usd_total = counter(
            "request_cost_usd_total",
            "Agent request estimated cost USD (governance estimate, never billing)",
            ["model"],
        )
        self.request_duration_seconds = histogram(
            "request_duration_seconds", "Agent request duration (request start -> finalize)",
            buckets=_DURATION_BUCKETS,
        )

        # Tools (recorded at the guarded gate, one record per logical call)
        self.tool_calls_total = counter(
            "tool_calls_total", "Guarded tool calls, by tool and terminal outcome",
            ["tool", "status"],
        )
        self.tool_duration_seconds = histogram(
            "tool_duration_seconds", "Tool execution duration", ["tool"],
            buckets=_DURATION_BUCKETS,
        )
        self.tool_failures_total = counter(
            "tool_failures_total", "Tool executions that failed, by bounded error code",
            ["tool", "error_code"],
        )
        self.tool_blocked_total = counter(
            "tool_blocked_total", "Tool calls blocked before execution, by bounded reason",
            ["tool", "reason"],
        )

        self._counters = {
            "requests_total": self.requests_total,
            "request_tokens_total": self.request_tokens_total,
            "request_cost_usd_total": self.request_cost_usd_total,
            "tool_calls_total": self.tool_calls_total,
            "tool_failures_total": self.tool_failures_total,
            "tool_blocked_total": self.tool_blocked_total,
        }
        self._histograms = {
            "request_duration_seconds": self.request_duration_seconds,
            "tool_duration_seconds": self.tool_duration_seconds,
        }
        self._gauges: dict[str, Any] = {}

    # -- strict validation (tests + pre-flight) -------------------------------

    def validate(self, label: str, value: str) -> str:
        """Raise ValueError when a label value is not in its finite set.

        `model` and `tool` are the exception by design: allowlist plus a
        single catch-all "other" (never raises). Every other label is strict.
        """
        if label == "model":
            return bounded_model(value)
        if label == "tool":
            return bounded_tool(value)
        allowed = _AGENT_LABEL_SETS.get(label)
        if allowed is None:
            raise ValueError(f"unknown label {label!r}")
        if value not in allowed:
            raise ValueError(f"unbounded {label} label value {value!r} (allowed: {sorted(allowed)})")
        return value

    def _validate_labels(self, labels: dict[str, str]) -> dict[str, str]:
        metric_labels: dict[str, str] = {}
        for name, value in labels.items():
            metric_labels[name] = self.validate(name, value)
        return metric_labels

    def _labeled(self, metric, labels: dict[str, str]):
        if not labels:
            return metric
        return metric.labels(**labels)

    def count(self, name: str, amount: int = 1, **labels: str) -> None:
        try:
            metric = self._counters[name]
            self._labeled(metric, self._validate_labels(labels)).inc(amount)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_count_failed name=%s error=%s", name, exc)

    def observe(self, name: str, value: float, **labels: str) -> None:
        try:
            metric = self._histograms[name]
            self._labeled(metric, self._validate_labels(labels)).observe(value)
        except Exception as exc:  # pragma: no cover - fail-open contract
            logger.warning("metrics_observe_failed name=%s error=%s", name, exc)

    @property
    def registry(self) -> CollectorRegistry:
        return self._registry


# Process-wide singletons (tests build fresh ExtractionMetrics/AgentMetrics
# instances and monkeypatch these attributes).
metrics = ExtractionMetrics(CollectorRegistry())
agent_metrics = AgentMetrics(CollectorRegistry())

# -- API-level registry (request middleware) ----------------------------------
# One bounded traffic counter, separate from the extraction namespace. Its only
# purpose is alerting semantics: "is the system receiving chat traffic at all?"
# — so a stalled-extraction alert can distinguish "no users" (healthy silence)
# from "users chatting but extraction scheduling stopped" (breakage). Ids and
# content never appear; endpoint is a finite enum.
API_REGISTRY = CollectorRegistry()
HTTP_ENDPOINTS: frozenset[str] = frozenset({"chat", "other"})
_api_http_requests_total = Counter(
    "owngpt_http_requests_total",
    "HTTP requests observed by the request logging middleware (bounded endpoint label)",
    ["endpoint"],
    registry=API_REGISTRY,
)


def safe_count_http(endpoint: str, amount: int = 1) -> None:
    """Fail-open increment for the request-level traffic counter."""
    try:
        if endpoint not in HTTP_ENDPOINTS:
            raise ValueError(f"unbounded http endpoint label {endpoint!r}")
        _api_http_requests_total.labels(endpoint=endpoint).inc(amount)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_count_failed name=owngpt_http_requests_total error=%s", exc)


def record_extraction_enabled() -> None:
    """Emit the extraction-enabled info gauge once at startup.

    enabled="1" when MEMORY_V2_GRAPH is on (extraction is expected to run);
    enabled="0" when the feature is disabled by configuration. The gauge value
    is a constant 1 — the label carries the signal. Alert rules compare their
    queries against this label before concluding extraction "stopped".
    """
    safe_set("extraction_info", 1.0, enabled="1" if settings.MEMORY_V2_GRAPH else "0")


def _registered_names(registry_obj) -> set[str]:
    """Metric names emitted by one *_Metrics registry object.

    Follows the prometheus_client convention: counters are suffixed `_total`,
    histograms emit `_bucket/_sum/_count`, gauges emit the bare name.
    """
    names: set[str] = set()
    histogram_metrics = set(registry_obj._histograms.values())
    gauge_metrics = set(registry_obj._gauges.values())
    all_metrics = (
        list(registry_obj._counters.values())
        + list(registry_obj._histograms.values())
        + list(registry_obj._gauges.values())
    )
    for metric in all_metrics:
        base = metric._name  # prometheus name without the _total counter suffix
        if metric in histogram_metrics:
            for suffix in ("_bucket", "_sum", "_count"):
                names.add(f"{base}{suffix}")
        elif metric in gauge_metrics:
            names.add(base)
        else:
            names.add(f"{base}_total")
    return names


def registered_metric_names() -> set[str]:
    """All metric names this process can emit (used by config-as-code tests).

    Derived from the registry objects themselves so a renamed metric cannot
    silently desync the dashboards/rules validation.
    """
    return (
        _registered_names(metrics)
        | _registered_names(agent_metrics)
        | {"owngpt_http_requests_total"}
    )


def safe_count(name: str, amount: int = 1, **labels: str) -> None:
    """Fail-open count against the process singleton. Catches a broken
    metrics object so observability can never break chat or extraction."""
    try:
        metrics.count(name, amount, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_count_failed name=%s error=%s", name, exc)


def safe_observe(name: str, value: float, **labels: str) -> None:
    try:
        metrics.observe(name, value, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_observe_failed name=%s error=%s", name, exc)


def safe_agent_count(name: str, amount: int = 1, **labels: str) -> None:
    """Fail-open count against the agent registry singleton.

    Same fail-open contract as safe_count: observability can never break the
    agent, the chat API, or the tool gate.
    """
    try:
        agent_metrics.count(name, amount, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_count_failed name=%s error=%s", name, exc)


def safe_agent_observe(name: str, value: float, **labels: str) -> None:
    try:
        agent_metrics.observe(name, value, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_observe_failed name=%s error=%s", name, exc)


def safe_set(name: str, value: float, **labels: str) -> None:
    try:
        metrics.set(name, value, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_set_failed name=%s error=%s", name, exc)


def safe_gauge_inc(name: str, amount: float = 1.0, **labels: str) -> None:
    try:
        metrics.gauge_inc(name, amount, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_inc_failed name=%s error=%s", name, exc)


def safe_gauge_dec(name: str, amount: float = 1.0, **labels: str) -> None:
    try:
        metrics.gauge_dec(name, amount, **labels)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_dec_failed name=%s error=%s", name, exc)


def render_metrics() -> bytes:
    """Serialize the registries for the /metrics endpoint (extraction + agent + API)."""
    try:
        parts = [
            generate_latest(metrics.registry),
            generate_latest(agent_metrics.registry),
            generate_latest(API_REGISTRY),
        ]
        return b"".join(parts)
    except Exception as exc:  # pragma: no cover - fail-open contract
        logger.warning("metrics_render_failed error=%s", exc)
        return b""


def provider_label() -> str:
    """Bounded provider label from the current configuration."""
    return bounded_provider(settings.LLM_PROVIDER)


def model_label(model: str) -> str:
    return bounded_model(model)
