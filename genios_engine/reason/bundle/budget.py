"""Doc 11's budget guards — the money half of the C5 gate.

**L4 is the only layer where the model runs AFTER the work is done**, which is what makes its
spend safe to cap absolutely: a refused consult costs a plainer sentence and never a different
decision. So this module fails CLOSED, unlike `platform/wiring._spent_today_minor`, which fails
open because refusing extraction would stop the graph being built. The two directions are not an
inconsistency; they are the same rule applied to two different consequences.

**Integer micro-dollars, end to end.** A bundle costs about a cent, so cents cannot express one
and a float re-rounds differently on every worker — the same argument basis points win everywhere
else in this codebase, one decimal place further out. Every division here rounds UP: a cost
estimate that rounds down authorises a little more than the number a human approved, once per
call, forever.

**The prices are not a new table.** `capture.semantic.batch.DEFAULT_TIER_PRICES` already prices
T1/T2/T3 in cents per million tokens for the extraction governor, and it exists precisely because
`platform/metrics.LLM_PRICE` prices HISTORY rather than a call about to be made. This module
reuses it. A second price table for the same two tiers is a second place a rate can be stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from genios_engine.capture.semantic.batch import DEFAULT_TIER_PRICES
from genios_engine.platform.logging import get_logger

from .sites import TIER_T1, TIER_T2, tier_for

_log = get_logger("genios.reason.bundle.budget")

MICRO_PER_USD = 1_000_000

#: Doc 11 §2's pilot org spends about $0.58/day on narrative. The default ceiling is a little over
#: three times that, so an ordinary day never touches it and a runaway is stopped inside one day
#: rather than at the end of a month. Zero means "no L4 narrative ceiling", which is the same
#: meaning `daily_llm_usd_cap` gives zero — a documented off-switch must not change meaning
#: between two modules that an operator reads together.
DEFAULT_DAILY_USD_CAP = "2.00"
#: Doc 11 §5's acceptance row is "measured $/published decision <= $0.02". This is that row as a
#: control rather than a report: a single consult estimated above it is refused before it runs.
DEFAULT_PER_DECISION_USD_CAP = "0.05"


def usd_to_micro(value: object) -> int:
    """USD as a human types it into config -> integer micro-dollars, exactly.

    Through `Decimal(str(...))` rather than `int(value * 1_000_000)`, because `2.00 * 1_000_000`
    is not 2000000 for every float a settings file can hold, and a ceiling that is one micro-dollar
    below the number an operator wrote is a ceiling that binds for a reason nobody can see.
    Truncates rather than rounds: a cap is a maximum, so the remainder belongs to the customer.
    """
    try:
        micro = int(Decimal(str(value or 0)) * MICRO_PER_USD)
    except Exception:      # noqa: BLE001 — an unreadable ceiling is a ZERO ceiling, see below
        _log.warning("unreadable USD ceiling %r — treating as no ceiling", value)
        return 0
    return max(0, micro)


def cost_micro_usd(*, tier: str, input_tokens: int, output_tokens: int) -> int:
    """What a call at this tier with these token counts cost, in micro-dollars. Rounded UP.

    `DEFAULT_TIER_PRICES` is cents per million tokens, so micro-dollars per token is
    `cents_per_mtok / 100` per token — the division is done once over the whole token count with a
    ceiling, never per token, so the rounding is applied to the number that is charged rather than
    accumulated a token at a time.
    """
    price = DEFAULT_TIER_PRICES.get(tier)
    if price is None:
        raise ValueError(f"no price for tier {tier!r}")
    tokens_in = max(0, int(input_tokens))
    tokens_out = max(0, int(output_tokens))
    return (_ceil_div(tokens_in * int(price.input_per_mtok), 100)
            + _ceil_div(tokens_out * int(price.output_per_mtok), 100))


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def estimate_micro_usd(*, site: str, prompt_chars: int, max_output_tokens: int) -> int:
    """The PRE-FLIGHT cost of a consult, before a token exists to count.

    Four characters per token is the crude estimate every provider publishes and it is used here
    for the same reason `batch.py` uses one: the number this guards is a refusal, and a refusal
    computed from a generous estimate refuses slightly early, which is the safe direction. Output
    is priced at its CEILING rather than at an expectation — a budget check that assumed the model
    would be brief would be a budget check that a verbose model walks straight through.
    """
    return cost_micro_usd(tier=tier_for(site),
                          input_tokens=_ceil_div(max(0, int(prompt_chars)), 4),
                          output_tokens=max(0, int(max_output_tokens)))


@dataclass(frozen=True, slots=True)
class BudgetVerdict:
    """Whether one consult may run, and the numbers that decided it. Never a bare boolean: doc 01
    C5 records the gate's reasoning, and "refused" without "spent 2000000 of 2000000" is a log line
    an operator cannot act on."""

    allowed: bool
    reason: str | None
    spent_micro_usd: int
    daily_cap_micro_usd: int
    estimate_micro_usd: int
    per_call_cap_micro_usd: int

    @property
    def remaining_micro_usd(self) -> int:
        if self.daily_cap_micro_usd <= 0:
            return 0
        return max(0, self.daily_cap_micro_usd - self.spent_micro_usd)


REASON_DAILY_EXHAUSTED = "l4_daily_narrative_budget_exhausted"
REASON_PER_CALL = "l4_per_decision_ceiling"
REASON_LEDGER_UNREADABLE = "l4_budget_ledger_unreadable"


class NarrativeBudget:
    """One tenant's narrative allowance for one day, read once and advanced in process.

    READ ONCE, ADVANCED IN PROCESS, for the reason `platform/wiring.make_cost_governor` gives:
    a ceiling re-read from the ledger on every call binds only BETWEEN calls, because the row for
    the call in flight is not written yet. A sweep that narrates forty decisions would then check
    forty times against a ledger that is always one call stale. So the opening balance is read from
    the database and every consult's actual cost is added here.

    Not a singleton and not cached across sweeps: the day boundary is the ledger's, and a governor
    that outlived a process would open tomorrow with today's balance.
    """

    def __init__(self, *, org_id: str, engine=None, daily_cap_micro_usd: int | None = None,
                 per_call_cap_micro_usd: int | None = None, now: datetime | None = None) -> None:
        self.org_id = org_id
        self._daily_cap = (usd_to_micro(DEFAULT_DAILY_USD_CAP) if daily_cap_micro_usd is None
                           else max(0, int(daily_cap_micro_usd)))
        self._per_call_cap = (usd_to_micro(DEFAULT_PER_DECISION_USD_CAP)
                              if per_call_cap_micro_usd is None
                              else max(0, int(per_call_cap_micro_usd)))
        self._ledger_readable = True
        self._spent = self._opening_balance(engine, now)

    @classmethod
    def from_settings(cls, *, org_id: str, engine=None, now: datetime | None = None
                      ) -> NarrativeBudget:
        """The production constructor. Reads the two ceilings from `platform.config`."""
        from genios_engine.platform.config import get_settings
        settings = get_settings()
        return cls(org_id=org_id, engine=engine, now=now,
                   daily_cap_micro_usd=usd_to_micro(
                       getattr(settings, "l4_bundle_daily_usd_cap", DEFAULT_DAILY_USD_CAP)),
                   per_call_cap_micro_usd=usd_to_micro(
                       getattr(settings, "l4_bundle_max_usd_per_decision",
                               DEFAULT_PER_DECISION_USD_CAP)))

    def _opening_balance(self, engine, now: datetime | None) -> int:
        """Today's L4 narrative spend, from `l4_r_site_calls` — this layer's OWN ledger.

        Not from `llm_costs`: that table records no site and no tier, so a sum over it would charge
        the narrative budget for every extraction the tenant paid for that morning and the
        narrative would go quiet for a reason that has nothing to do with narration. Every consult
        writes both — `llm_costs` so platform-wide spend stays whole, here so this ceiling is
        about this spend.

        FAILS CLOSED. An unreadable ledger means the day is treated as spent, which costs a day of
        plainer prose on a tenant whose decisions are unchanged. The opposite default spends real
        money against a ceiling nobody can see.
        """
        if engine is None:
            return 0
        from sqlalchemy import text
        try:
            with engine.connect() as conn:
                spent = conn.execute(text(
                    "select coalesce(sum(cost_micro_usd), 0) from l4_r_site_calls "
                    "where org_id = :o and created_at >= date_trunc('day', :now)"),
                    {"o": self.org_id, "now": now or datetime.now(tz=_utc())}).scalar()
            return int(spent or 0)
        except Exception as exc:      # noqa: BLE001 — see the docstring
            _log.warning("l4 narrative ledger unreadable for org=%s (%s) — refusing consults "
                         "today and falling back to template prose", self.org_id, exc)
            self._ledger_readable = False
            return self._daily_cap if self._daily_cap else 1

    @property
    def spent_micro_usd(self) -> int:
        return self._spent

    @property
    def daily_cap_micro_usd(self) -> int:
        return self._daily_cap

    def check(self, estimate: int) -> BudgetVerdict:
        """May a consult estimated at `estimate` micro-dollars run right now?"""
        estimate = max(0, int(estimate))
        verdict = BudgetVerdict(
            allowed=True, reason=None, spent_micro_usd=self._spent,
            daily_cap_micro_usd=self._daily_cap, estimate_micro_usd=estimate,
            per_call_cap_micro_usd=self._per_call_cap)
        if not self._ledger_readable:
            return _refuse(verdict, REASON_LEDGER_UNREADABLE)
        if self._per_call_cap and estimate > self._per_call_cap:
            return _refuse(verdict, REASON_PER_CALL)
        if self._daily_cap and self._spent + estimate > self._daily_cap:
            return _refuse(verdict, REASON_DAILY_EXHAUSTED)
        return verdict

    def charge(self, actual: int) -> int:
        """Record what a consult ACTUALLY cost. Returns the new balance.

        The actual, not the estimate: charging the estimate would make the ceiling bind against a
        number that was deliberately generous, and forty decisions into a sweep the two disagree by
        more than a day's budget.
        """
        self._spent += max(0, int(actual))
        return self._spent


def _refuse(verdict: BudgetVerdict, reason: str) -> BudgetVerdict:
    from dataclasses import replace
    return replace(verdict, allowed=False, reason=reason)


def _utc():
    from datetime import timezone
    return timezone.utc


__all__ = ["BudgetVerdict", "DEFAULT_DAILY_USD_CAP", "DEFAULT_PER_DECISION_USD_CAP",
           "MICRO_PER_USD", "NarrativeBudget", "REASON_DAILY_EXHAUSTED",
           "REASON_LEDGER_UNREADABLE", "REASON_PER_CALL", "TIER_T1", "TIER_T2",
           "cost_micro_usd", "estimate_micro_usd", "usd_to_micro"]
