"""U08 · the executor — Layer 1 goes and gets the one fact Layer 2 named.

Layer 2 files an `EvidenceNeed` row; this picks it up. The two never call each other: a sweep that
fetched inline would make a graph pass wait on a network, so the need is data and the fetch is a
separate pass. `docs/LAYER_MAP.md` records the rule.

⛔ WHAT MAKES THIS AN EXECUTOR AND NOT A BACKFILL. Three refusals, and each one is a way the
question could quietly turn back into "fetch everything and hope":

  1. **An expired need is never fetched.** The answer would arrive after the decision it was for.
     Buying it anyway spends the tenant's money on history.
  2. **A need whose budget cannot cover the cheapest fetch closes rather than half-fetching.** A
     partial fetch produces a partial answer that LOOKS like an answer — the one outcome worse than
     no answer, because the hold clears on it.
  3. ⛔ **Evidence from an unacceptable source never closes the need.** A vendor's quote email is
     not the signed contract. Closing on one would let Layer 2 proceed on evidence that cannot
     carry the claim — worse than the hold it replaced, because the hold at least knew it was
     missing something.

⛔ AND EVERY PATH ENDS IN A CLOSED NEED. `met` or `unavailable`, and `unavailable` always carries a
reason. A need left `open` because nothing matched is a hold that can never clear — the exact state
this whole step exists to end, re-created one layer down.

NEVER RAISES, on the same terms as everything else in `capture/`: losing a fetch costs an answer,
raising costs the tenant their mail.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from genios_engine.contracts.evidence import EvidenceNeed
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.evidence_need")

#: The three things Layer 1 can actually go and do about a named gap. Closed: a need that maps to
#: none of them is unanswerable HERE, and says so rather than sitting open.
FETCH_THREAD = "fetch_thread"
BACKFILL_WINDOW = "backfill_window"
REEXTRACT = "reextract"
FETCH_KINDS = (FETCH_THREAD, BACKFILL_WINDOW, REEXTRACT)

#: What the cheapest fetch costs, as a floor for the budget check. Not a price list — a need whose
#: limit is under this cannot buy anything at all, and knowing that before dispatching is what
#: turns "we tried" into "we did not, and here is why".
MIN_FETCH_USD = 0.01


@dataclass(frozen=True, slots=True)
class FetchOutcome:
    """What one attempt concluded. `state` is always a CLOSED state — see the module docstring."""

    need_id: str
    state: str                      # "met" | "unavailable"
    reason: str | None = None       # mandatory when unavailable
    source: str | None = None       # what actually settled it
    kind: str | None = None         # which of FETCH_KINDS was run


def plan_fetch(need: EvidenceNeed) -> str | None:
    """Which of the three fetches this need calls for, or `None` when Layer 1 cannot answer it.

    Read off the subject rather than guessed from the question text: a subject is a typed reference
    the graph already produced, and matching on prose would make the plan depend on wording that
    changes whenever somebody improves a sentence.
    """
    subject = (need.subject_ref or "").strip()
    if subject.startswith("thread:"):
        return FETCH_THREAD
    if subject.startswith(("document:", "attachment:")):
        return REEXTRACT
    if subject.startswith("signal:") or need.window_from is not None:
        return BACKFILL_WINDOW
    return None


def _now(clock: datetime | None) -> datetime:
    return clock or datetime.now(timezone.utc)


def execute(need: EvidenceNeed, *,
            fetchers: Mapping[str, Callable[[EvidenceNeed], Any]],
            eval_time: datetime | None = None) -> FetchOutcome:
    """Work one need to a CLOSED state.

    `fetchers` maps a member of `FETCH_KINDS` to something that performs it and returns either
    `None` (nothing found) or a mapping carrying at least `source`. Injected rather than imported so
    this unit is a pure decision over a need, testable without a connector.
    """
    try:
        return _execute(need, fetchers=fetchers, eval_time=eval_time)
    except Exception as exc:      # noqa: BLE001 — a fetch failure must never break the pass
        _log.warning("evidence need %s failed to execute", need.need_id, exc_info=True)
        # ⛔ Still CLOSED, and honest about why. Leaving it open on an exception re-creates the
        # permanently-open need this contract exists to prevent, and hides a broken connector
        # behind a hold that simply never clears.
        return FetchOutcome(need.need_id, "unavailable",
                            reason=f"the fetch failed: {type(exc).__name__}")


def _execute(need: EvidenceNeed, *,
             fetchers: Mapping[str, Callable[[EvidenceNeed], Any]],
             eval_time: datetime | None) -> FetchOutcome:
    if need.state != "open":
        return FetchOutcome(need.need_id, need.state, reason=need.unavailable_reason)

    now = _now(eval_time)
    if need.expires_at is not None and need.expires_at <= now:
        return FetchOutcome(need.need_id, "unavailable",
                            reason="the need expired before it was worked; the answer would arrive "
                                   "after the decision it was for")

    if need.max_cost_usd is not None and need.max_cost_usd < MIN_FETCH_USD:
        # ⛔ Closed rather than half-fetched. A partial answer LOOKS like an answer, and the hold
        # clears on it.
        return FetchOutcome(need.need_id, "unavailable",
                            reason=f"the budget ({need.max_cost_usd}) is below the cheapest fetch "
                                   f"({MIN_FETCH_USD}); a partial fetch would answer partly and "
                                   f"close fully")

    kind = plan_fetch(need)
    if kind is None:
        return FetchOutcome(need.need_id, "unavailable",
                            reason=f"no Layer 1 fetch answers a need about "
                                   f"{need.subject_ref or 'nothing in particular'}")

    fetcher = fetchers.get(kind)
    if fetcher is None:
        return FetchOutcome(need.need_id, "unavailable", kind=kind,
                            reason=f"{kind} is not connected for this tenant")

    found = fetcher(need)
    if not found:
        return FetchOutcome(need.need_id, "unavailable", kind=kind,
                            reason=f"{kind} ran and found nothing in the window")

    source = str((found or {}).get("source") or "").strip()
    if not need.accepts(source):
        # ⛔ THE REFUSAL THAT MATTERS. Something was found and it is not what was asked for.
        return FetchOutcome(need.need_id, "unavailable", kind=kind, source=source,
                            reason=f"{source!r} was found but this need does not accept it; a "
                                   f"substitute would close the hold on evidence that cannot "
                                   f"carry the claim")

    return FetchOutcome(need.need_id, "met", source=source, kind=kind)


__all__ = ["BACKFILL_WINDOW", "FETCH_KINDS", "FETCH_THREAD", "MIN_FETCH_USD", "REEXTRACT",
           "FetchOutcome", "execute", "plan_fetch"]
