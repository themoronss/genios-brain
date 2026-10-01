"""U05 · a met need clears its hold — and an unavailable one stops the waiting.

Step 3 turned a hold into a question. This closes the loop: it reads the state of a held situation's
evidence needs and says what should happen to the situation.

⛔ `unavailable` MUST NOT LOOK LIKE `met`, AND NEITHER MAY LOOK LIKE `open`. Three outcomes, and every
pair of them is a different thing to do:

    still open        → KEEP_WAITING. Nothing has changed. Re-running admission would spend a sweep
                        to re-derive the same hold reason.
    at least one met  → RETRY. New evidence exists, so admission gets another go and may ADMIT. It
                        may also hold again — on the NEW reason, which is progress either way.
    all unavailable   → GIVE_UP. ⛔ The situation stops waiting and SAYS WHY. A situation that gave up
                        because the document does not exist and a situation still waiting are
                        different states, and a card that cannot tell them apart will either nag
                        forever or go quiet with no explanation.

⛔ AN EXPIRED OPEN NEED IS NOT STILL WAITING. A need past `expires_at` will never be met — but if the
executor has not run, its row still says `open`. Counting it as waiting is how a hold becomes
permanent: the situation waits on a question nobody will answer, forever, and no surface says so. So
expiry is evaluated here too, and an expired open need counts as unavailable with a reason that names
the expiry.

`eval_time` IS A PARAMETER, NEVER `now()`, because the same hold and the same needs must produce the
same disposition when replayed — otherwise a decision cannot be audited after the fact.

⛔ A PARTIAL ARRIVAL IS NOT A COMPLETE ONE. When one need was met and another came back unavailable,
the disposition is RETRY *and the unavailable reasons travel with it*. Dropping them would let the
retry read as "we have everything now", which is the `not_carried` defect: a value computed at one
boundary and silently lost at the next.

THIS MODULE DECIDES; IT DOES NOT WRITE. The compare-and-set belongs to the caller that applies the
disposition — see `STEP-02-WITHDRAWN-compare-and-set.md` for why `reason/`'s existing
`_graph_version_guard` is the mechanism and not a second copy of it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

#: Nothing closed. Do not re-run admission.
KEEP_WAITING = "keep_waiting"
#: Something arrived. Re-run admission; it may admit, or hold on a new reason.
RETRY = "retry"
#: ⛔ Every question closed and none was answered. Stop waiting, and say why on the card.
GIVE_UP = "give_up"
#: This hold was never an evidence question — see `hold_needs`, four of seven reasons are not. It is
#: waiting on a ruling, not a fetch, and calling that KEEP_WAITING would imply a pending fetch.
NO_EVIDENCE_QUESTION = "no_evidence_question"

DISPOSITIONS = (KEEP_WAITING, RETRY, GIVE_UP, NO_EVIDENCE_QUESTION)


@dataclass(frozen=True, slots=True)
class HoldDisposition:
    """What to do with one held situation, and what to say about it."""

    disposition: str
    #: The sources that actually settled a need. Non-empty exactly when `disposition` is RETRY.
    met_sources: tuple[str, ...] = ()
    #: ⛔ Why each unanswerable question could not be answered. Carried even on RETRY: a retry that
    #: dropped these would read as "we have everything now".
    unavailable_reasons: tuple[str, ...] = ()
    #: How many needs are still genuinely open, so a caller can say "waiting on 2 of 3".
    still_open: int = 0

    @property
    def should_retry_admission(self) -> bool:
        return self.disposition == RETRY

    @property
    def should_stop_waiting(self) -> bool:
        return self.disposition == GIVE_UP

    def explain(self) -> str:
        """One line a card can carry. Never empty, and never the same for two dispositions."""
        if self.disposition == NO_EVIDENCE_QUESTION:
            return "this hold is waiting on a ruling, not on evidence"
        if self.disposition == KEEP_WAITING:
            return f"waiting on {self.still_open} evidence question(s)"
        if self.disposition == RETRY:
            got = ", ".join(self.met_sources) or "new evidence"
            if self.unavailable_reasons:
                # ⛔ Partial. Saying only the good half is how a partial answer becomes a complete one.
                return (f"retrying with {got}; still missing: "
                        f"{'; '.join(self.unavailable_reasons)}")
            return f"retrying with {got}"
        return "stopped waiting: " + "; ".join(self.unavailable_reasons)


def _closed_unavailable(need: Any, eval_time: datetime) -> str | None:
    """The reason this need cannot be answered, or `None` if it is still a live question.

    Handles the state the executor has recorded AND the state the clock has decided. A need whose row
    still says `open` because nothing has run yet, but whose `expires_at` has passed, is not a live
    question — treating it as one is how a hold becomes permanent.
    """
    state = str(getattr(need, "state", "open") or "open")
    if state == "unavailable":
        return str(getattr(need, "unavailable_reason", None)
                   or "closed unavailable with no reason recorded")
    if state == "met":
        return None

    expires_at = getattr(need, "expires_at", None)
    if expires_at is not None and expires_at <= eval_time:
        # ⛔ Not still waiting. The answer would arrive after the decision it was for, and the
        # executor's own first refusal says the same thing.
        return (f"the question expired unanswered at {expires_at.isoformat()} "
                f"and was never worked")
    return None


def _is_open(need: Any, eval_time: datetime) -> bool:
    state = str(getattr(need, "state", "open") or "open")
    if state != "open":
        return False
    return _closed_unavailable(need, eval_time) is None


def resolve_hold(needs: Sequence[Any], *, eval_time: datetime) -> HoldDisposition:
    """What to do with a held situation, given the state of the needs it raised.

    `needs` empty means the hold raised no evidence question — see `hold_needs`, where four of the
    seven hold reasons deliberately raise none.
    """
    if not needs:
        return HoldDisposition(NO_EVIDENCE_QUESTION)

    met: list[str] = []
    unavailable: list[str] = []
    open_count = 0

    for need in needs:
        if _is_open(need, eval_time):
            open_count += 1
            continue
        reason = _closed_unavailable(need, eval_time)
        if reason is not None:
            unavailable.append(reason)
        else:
            met.append(str(getattr(need, "met_source", None)
                           or getattr(need, "subject_ref", None) or "evidence"))

    if open_count:
        # ⛔ Deliberately checked BEFORE `met`. A situation with one met need and one still open has
        # not got everything it asked for, and retrying now would re-derive the same hold while the
        # outstanding question is still in flight.
        return HoldDisposition(KEEP_WAITING, met_sources=tuple(met),
                               unavailable_reasons=tuple(unavailable), still_open=open_count)

    if met:
        return HoldDisposition(RETRY, met_sources=tuple(met),
                               unavailable_reasons=tuple(unavailable))

    return HoldDisposition(GIVE_UP, unavailable_reasons=tuple(unavailable))


__all__ = ["DISPOSITIONS", "GIVE_UP", "KEEP_WAITING", "NO_EVIDENCE_QUESTION", "RETRY",
           "HoldDisposition", "resolve_hold"]
