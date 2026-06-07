"""LLM client wrapper — single point of LLM access for the engine.

Wraps the Anthropic SDK with:
- Timeout + retries from config (LLM_TIMEOUT_SECONDS, LLM_MAX_RETRIES)
- Token + cost tracking for cost_guard
- Structured logging (no content in logs)
- Self-consistency sampling (n samples) for ConfidenceScorer.consistency_score

This module is the ONLY place that imports the Anthropic SDK in the engine path.
Callers go through Gateway.route(), which goes through this client.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from anthropic import Anthropic
from anthropic._exceptions import APIError, RateLimitError

from core.foundations.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


# Per Anthropic public pricing (approximate; tune via config_overrides later).
# Cost per 1M tokens, in USD.
_COST_PER_M_INPUT_TOKENS = {
    "claude-haiku-4-5-20251001": 0.80,
    "claude-sonnet-4-6": 3.00,
}
_COST_PER_M_OUTPUT_TOKENS = {
    "claude-haiku-4-5-20251001": 4.00,
    "claude-sonnet-4-6": 15.00,
}

ModelChoice = Literal["haiku", "sonnet"]


@dataclass(frozen=True)
class LLMCall:
    """One LLM request. The client returns LLMResponse."""

    model: ModelChoice
    system_prompt: str
    user_prompt: str
    max_tokens: int = 1024
    temperature: float = 0.0
    org_id: str = ""  # for audit + cost tracking
    purpose: str = "gateway"  # e.g. 'gap_fill' | 'extraction' | 'narrator' | 'reflection'


@dataclass(frozen=True)
class LLMResponse:
    """One LLM response. Includes cost metrics for CostGuard.charge()."""

    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_id: str
    latency_ms: int


class LLMClientError(Exception):
    """Raised when LLM call fails after retries."""


class LLMClient:
    """Stateless LLM client. Construct once, call call() many times."""

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise LLMClientError("ANTHROPIC_API_KEY not configured")
        self._client = Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=float(LLM_TIMEOUT_SECONDS),
            max_retries=0,  # we handle retries ourselves for visibility
        )

    def call(self, call: LLMCall) -> LLMResponse:
        """Single LLM call with retry on transient errors."""
        model_id = self._resolve_model(call.model)
        last_err: Exception | None = None

        for attempt in range(LLM_MAX_RETRIES + 1):
            t_start = time.monotonic()
            try:
                resp = self._client.messages.create(
                    model=model_id,
                    system=call.system_prompt,
                    messages=[{"role": "user", "content": call.user_prompt}],
                    max_tokens=call.max_tokens,
                    temperature=call.temperature,
                )
                latency_ms = int((time.monotonic() - t_start) * 1000)
                text = "".join(b.text for b in resp.content if b.type == "text")

                in_toks = resp.usage.input_tokens
                out_toks = resp.usage.output_tokens
                cost = _cost_usd(model_id, in_toks, out_toks)

                log.info(
                    "llm_call_ok",
                    model=model_id,
                    purpose=call.purpose,
                    org_id=call.org_id,
                    input_tokens=in_toks,
                    output_tokens=out_toks,
                    cost_usd=round(cost, 6),
                    latency_ms=latency_ms,
                    attempts=attempt + 1,
                )
                # Persist to llm_costs so cost visibility + the daily budget
                # breaker have a single source of truth. Fail-soft inside
                # record_llm_call — never blocks the business path.
                if call.org_id:
                    try:
                        from core.foundations.llm_costs import record_llm_call
                        record_llm_call(
                            org_id=call.org_id,
                            model=model_id,
                            purpose=call.purpose or "other",  # type: ignore[arg-type]
                            input_tokens=in_toks,
                            output_tokens=out_toks,
                        )
                    except Exception:
                        # logger inside record_llm_call already warned; the
                        # outer try keeps a misnamed purpose from crashing
                        # the LLM path.
                        pass
                return LLMResponse(
                    text=text,
                    input_tokens=in_toks,
                    output_tokens=out_toks,
                    cost_usd=cost,
                    model_id=model_id,
                    latency_ms=latency_ms,
                )

            except RateLimitError as e:
                last_err = e
                wait = (2**attempt) * 0.5
                log.warning(
                    "llm_rate_limit",
                    attempt=attempt + 1,
                    wait_seconds=wait,
                    model=model_id,
                )
                time.sleep(wait)
            except APIError as e:
                last_err = e
                log.warning("llm_api_error", attempt=attempt + 1, error=str(e)[:200])
                if attempt < LLM_MAX_RETRIES:
                    time.sleep(0.5 * (attempt + 1))

        raise LLMClientError(
            f"LLM call failed after {LLM_MAX_RETRIES + 1} attempts: {last_err}"
        ) from last_err

    def call_n(
        self,
        call: LLMCall,
        *,
        n: int,
        temperature: float = 0.5,
    ) -> list[LLMResponse]:
        """Run the same prompt n times for self-consistency scoring.

        Per MD g-i-2 §2.2.2 confidence formula — consistency_score = agreement across n samples.
        Use temperature > 0 to get sampling diversity.
        """
        if n <= 0:
            return []
        adjusted = LLMCall(
            model=call.model,
            system_prompt=call.system_prompt,
            user_prompt=call.user_prompt,
            max_tokens=call.max_tokens,
            temperature=temperature,
            org_id=call.org_id,
            purpose=call.purpose,
        )
        return [self.call(adjusted) for _ in range(n)]

    @staticmethod
    def _resolve_model(choice: ModelChoice) -> str:
        if choice == "haiku":
            return settings.ANTHROPIC_HAIKU_MODEL
        if choice == "sonnet":
            return settings.ANTHROPIC_SONNET_MODEL
        raise LLMClientError(f"Unknown model choice: {choice}")


def _cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    in_rate = _COST_PER_M_INPUT_TOKENS.get(model_id, 0.0)
    out_rate = _COST_PER_M_OUTPUT_TOKENS.get(model_id, 0.0)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def sum_cost(responses: Iterable[LLMResponse]) -> float:
    return sum(r.cost_usd for r in responses)
