"""
V4.9 - Cost & Token Governance

Per-request and per-step token accounting with provider/model-aware
estimated cost and budget enforcement BEFORE LLM calls.

Design invariants:
  - PURE accounting module: no I/O, no telemetry, no memory access.
    It never imports Memory V2, Redis, SQLite, vector stores, or any
    service layer — budgets are in-memory caps attached to one request.
  - Provider/model-aware: a fixed pricing table maps model names to
    (input, output) USD per 1M tokens; unknown models fall back to a
    conservative default rate. No live pricing lookups.
  - Budgets are caps enforced by the CALLER before invoking an LLM:
    check() returns a stable reason when the request budget or the
    per-step budget is exhausted; enforcement points block the call
    (executor step, optional synthesis/validation escalation).
  - Cost data attaches to the existing V4.8 AgentTrace via its
    correlation IDs — this module introduces NO new tracking mechanism.
  - Nothing ever raises for accounting failures: record() is defensive
    and coercion never fails a caller.

This must never become a billing system. It estimates cost for
governance only; exact invoicing belongs elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Pricing (USD per 1M tokens, (input, output)) ────────────────────────────
# Snapshot of common provider list prices. Unknown models use DEFAULT_RATE.
# Provider-qualified names ("openai/gpt-4o-mini") resolve to the model part.
DEFAULT_RATES: dict[str, tuple[float, float]] = {
    "gpt-4o":             (2.50, 10.00),
    "gpt-4o-mini":        (0.15, 0.60),
    "gpt-4-turbo":        (10.00, 30.00),
    "gpt-4.1":            (2.00, 8.00),
    "gpt-4.1-mini":       (0.40, 1.60),
    "gpt-4.1-nano":       (0.10, 0.40),
    "claude-3-5-sonnet":  (3.00, 15.00),
    "claude-3-5-haiku":   (0.80, 4.00),
    "claude-sonnet-4":    (3.00, 15.00),
    "claude-haiku-4":     (1.00, 5.00),
    "deepseek-chat":      (0.27, 1.10),
    "deepseek-reasoner":  (0.55, 2.19),
    "gemini-2.0-flash":   (0.10, 0.40),
    "gemini-2.5-pro":     (1.25, 10.00),
    "llama-3.1-8b":       (0.10, 0.40),
}

# Conservative fallback for models without a known price.
DEFAULT_RATE = (1.00, 3.00)

# Default budget caps (tokens). Configurable via pipeline config:
#   request_token_budget / step_token_budget.
DEFAULT_REQUEST_BUDGET_TOKENS = 40_000
DEFAULT_STEP_BUDGET_TOKENS = 12_000

# Stable block reasons surfaced to error/trace (never raw provider text).
REASON_REQUEST_EXHAUSTED = "request token budget exhausted"
REASON_STEP_EXHAUSTED = "step token budget exhausted"


def _rate_for(model: str, rates: dict) -> tuple[float, float]:
    """Model-aware rate lookup; provider-prefixed names resolve to model."""
    if not model:
        return DEFAULT_RATE
    if model in rates:
        return rates[model]
    suffix = model.split("/")[-1]
    if suffix in rates:
        return rates[suffix]
    return DEFAULT_RATE


@dataclass(frozen=True)
class TokenUsage:
    """One immutable token usage record (per LLM call, snapshot at record)."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenBudget:
    """Per-request + per-step token budgets with model-aware cost estimates.

    The budget is a passive cap holder: enforcement happens at the LLM
    call boundary (executor step gate, synthesis/validation escalation).
    A context WITHOUT a budget behaves exactly as before V4.9.

    Immutability of caps: budgets are fixed per request — they are never
    modified, only consumed.
    """

    def __init__(
        self,
        request_budget_tokens: int = DEFAULT_REQUEST_BUDGET_TOKENS,
        per_step_budget_tokens: int = DEFAULT_STEP_BUDGET_TOKENS,
        rates: Optional[dict[str, tuple[float, float]]] = None,
    ) -> None:
        if int(request_budget_tokens) <= 0 or int(per_step_budget_tokens) <= 0:
            raise ValueError("token budgets must be positive integers")
        self.request_budget_tokens = int(request_budget_tokens)
        self.per_step_budget_tokens = int(per_step_budget_tokens)
        self._rates = dict(rates or DEFAULT_RATES)

        # Per-model usage (cost is model-aware) and per-step totals.
        self._usage: dict[str, TokenUsage] = {}
        # Step accounting is keyed by step_id (step-level, model-agnostic).
        self._use_order: list[str] = []
        self._step_tokens: dict[int, int] = {}

    # ── Accounting ────────────────────────────────────────────────────────

    def record(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        step_id: Optional[int] = None,
    ) -> None:
        """Record one LLM call's usage. Defensive: never raises.

        Negative/absent values coerce to 0; model coerces to str.
        Usage beyond a cap is still counted accurately — budgets gate
        FUTURE calls, they never hide already-spent tokens.
        """
        try:
            model_key = str(model) if model else "<unknown>"
            t_in = max(0, int(input_tokens or 0))
            t_out = max(0, int(output_tokens or 0))
            cost = self.estimate_cost(model_key, t_in, t_out)

            prev = self._usage.get(model_key)
            if prev is None:
                self._usage[model_key] = TokenUsage(
                    model=model_key, input_tokens=t_in,
                    output_tokens=t_out, cost_usd=cost,
                )
                self._use_order.append(model_key)
            else:
                self._usage[model_key] = TokenUsage(
                    model=model_key,
                    input_tokens=prev.input_tokens + t_in,
                    output_tokens=prev.output_tokens + t_out,
                    cost_usd=round(prev.cost_usd + cost, 10),
                )
            if step_id is not None:
                self._step_tokens[step_id] = (
                    self._step_tokens.get(step_id, 0) + t_in + t_out
                )
        except Exception:
            # Accounting must never break agent execution.
            return

    # ── Reads ─────────────────────────────────────────────────────────────

    def spent_tokens(self) -> int:
        return sum(u.total_tokens for u in self._usage.values())

    def step_spent(self, step_id: int) -> int:
        return self._step_tokens.get(step_id, 0)

    def usage_by_model(self) -> dict[str, dict]:
        """Per-model snapshot (audit-friendly, copy of internal state)."""
        return {
            m: {
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "total_tokens": u.total_tokens,
                "cost_usd": u.cost_usd,
            }
            for m, u in self._usage.items()
        }

    def models_used(self) -> list[str]:
        return sorted(self._usage.keys())

    def estimate_cost(
        self, model: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> float:
        """USD estimate = in/1M*in_rate + out/1M*out_rate (model-aware)."""
        in_rate, out_rate = _rate_for(str(model) if model else "", self._rates)
        t_in = max(0, int(input_tokens or 0))
        t_out = max(0, int(output_tokens or 0))
        return round((t_in / 1_000_000.0) * in_rate
                     + (t_out / 1_000_000.0) * out_rate, 10)

    def total_cost_usd(self) -> float:
        return round(sum(u.cost_usd for u in self._usage.values()), 10)

    # ── Enforcement (called BEFORE an LLM call) ───────────────────────────

    def check(self, step_id: Optional[int] = None) -> Optional[str]:
        """Return a stable block reason, or None when the call may run.

        Order matters: the request budget is the hard cap (runaway
        multi-step prevention); the per-step budget gates repeated LLM
        consumption within one logical step.
        """
        if self.spent_tokens() >= self.request_budget_tokens:
            return REASON_REQUEST_EXHAUSTED
        if (
            step_id is not None
            and self.step_spent(step_id) >= self.per_step_budget_tokens
        ):
            return REASON_STEP_EXHAUSTED
        return None

    def snapshot(self) -> dict:
        """Complete audit snapshot (correlates with the AgentTrace IDs)."""
        return {
            "request_budget_tokens": self.request_budget_tokens,
            "per_step_budget_tokens": self.per_step_budget_tokens,
            "spent_tokens": self.spent_tokens(),
            "estimated_cost_usd": self.total_cost_usd(),
            "models_used": self.models_used(),
            "usage_by_model": self.usage_by_model(),
            "step_tokens": dict(self._step_tokens),
        }