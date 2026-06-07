"""Single entry point every LLM call MUST funnel through for cost logging.

Writes one row to `llm_costs` per call. Fail-soft: if the DB write fails
(missing migration in some env, transient outage), the logger emits a
warning but does NOT raise into the caller — losing the audit row is
worse than dropping the business operation it served.

Pricing is reproduced here (not imported from neural.client) so it stays
visible at the cost write site; a future Anthropic pricing change updates
both files together.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import text

from core.foundations.db import get_session
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

# $ per 1M tokens — keep in sync with core/neural/client.py constants.
# Anthropic public pricing (claude.com/pricing — accurate as of cutoff).
_PRICE_PER_M_TOKENS_USD: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
    # Older model ids the codebase may still mention — keep so a stale
    # config_overrides.yaml doesn't silently log $0.
    "claude-3-5-haiku-20241022":   {"input": 0.80, "output": 4.00},
    "claude-3-5-sonnet-20241022":  {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229":      {"input": 15.00, "output": 75.00},
}

Purpose = Literal[
    "extract",
    "intelligence",
    "custom_mapping",
    "persona_distill",
    "proactive",
    "artifact_narrate",
    "other",
]


def estimate_cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost from token counts. Unknown model → 0.0 + warning.

    The "unknown" case isn't an error — it's a signal the model id was
    typo'd or the price table is stale. We log so ops sees it but keep the
    cost row going (cost=0 is honest about "we don't know").
    """
    table = _PRICE_PER_M_TOKENS_USD.get(model)
    if table is None:
        log.warning("llm_cost_unknown_model", model=model)
        return 0.0
    return (input_tokens / 1_000_000) * table["input"] + (
        output_tokens / 1_000_000
    ) * table["output"]


def record_llm_call(
    *,
    org_id: str,
    model: str,
    purpose: Purpose,
    input_tokens: int,
    output_tokens: int,
    credits_billed: int = 0,
    success: bool = True,
    error: str | None = None,
    agent_id: str | None = None,
    source_item_id: str | None = None,
    decision_id: str | None = None,
) -> None:
    """Persist one llm_costs row + emit a structured log line.

    Designed to be called from inside the LLM-using function right after
    the API call returns, regardless of success — failed calls still cost
    nothing in tokens but the row carries the error so debug + budget
    accounting both see the attempt.
    """
    cost = estimate_cost_usd(model, input_tokens=input_tokens, output_tokens=output_tokens)
    log.info(
        "llm_call",
        org_id=org_id, model=model, purpose=purpose,
        input_tokens=input_tokens, output_tokens=output_tokens,
        cost_usd=round(cost, 6), credits_billed=credits_billed,
        success=success, source_item_id=source_item_id, decision_id=decision_id,
    )
    try:
        with get_session() as s:
            s.execute(
                text(
                    """
                    INSERT INTO llm_costs
                        (org_id, agent_id, model, purpose,
                         input_tokens, output_tokens, cost_usd,
                         credits_billed, success, error,
                         source_item_id, decision_id, ts)
                    VALUES
                        (:org, :agent, :model, :purpose,
                         :it, :ot, :cost,
                         :cb, :ok, :err,
                         :sid, :did, NOW())
                    """
                ),
                {
                    "org": org_id, "agent": agent_id, "model": model,
                    "purpose": purpose, "it": input_tokens, "ot": output_tokens,
                    "cost": cost, "cb": credits_billed, "ok": success,
                    "err": error, "sid": source_item_id, "did": decision_id,
                },
            )
            s.commit()
    except Exception as e:
        log.warning("llm_cost_persist_failed", error=str(e), model=model, purpose=purpose)


def usage_extract(resp: Any) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) from an Anthropic Messages response.

    The SDK exposes them on .usage; old wrappers may have stripped it.
    Returns (0, 0) on missing data so the call still logs (cost=0 then).
    """
    usage = getattr(resp, "usage", None)
    if usage is None:
        return (0, 0)
    return (
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )
