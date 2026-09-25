"""L3-02 · the coverage READ — *how much of this window did we actually see?*

THE DEFECT THIS MODULE ENDS. Step 5 measured sweep completeness correctly and migration 0178
persisted it: `l1_sync_runs` carries `scanned`, `emitted`, `claimed_total`, `claimed_is_estimate`,
`cursor_exhausted`, `page_budget_spent` and `error`. **It has one writer and zero readers.** No
`select` anywhere in the engine reads those columns back, so the sentence the product needs —
*"read 37 of about 465"* — could not be said by anything, on any surface, however carefully the
number had been measured.

That is `not_carried` one seam further along than the class usually appears. The value does not
stop inside `capture/`; it reaches storage and stops there, which is harder to see because the
write looks like success.

WHY IT MATTERS MORE THAN IT SOUNDS. On 23 Sept two general-purpose assistants were asked the same
question against one mailbox. One read about 18 threads of roughly 465 and reported *"18 of 18"*;
the other read 37 and said *"about 8%"*. Every downstream difference followed from that single
number — *"0 explicit commitments"* means *"0 in the 4% I looked at"*, and *"40 meetings had no
follow-up"* was 40 calendar events checked against ONE email thread. **An empty result over an
unmeasured slice, reported as a fact about the business.**

⛔ WHAT THIS IS NOT. `source_coverage.coverage_ready` already answers a different and equally real
question — *can we see this DOMAIN at all for this org* — and it is computed per sweep, persisted,
carried on the QES and read in forty-odd modules including five in `context/`. That is the licence
to make a negative inference. **This module answers the quantitative half: of the window we claim
to have observed, what share did we actually land, and can we prove it?** Neither substitutes for
the other, and conflating them is how *"we can see email"* becomes *"we read the mailbox"*.

PURE-ish: no clock. `since` and `until` are parameters, so a caller pins the window and a test can
pin the boundary rather than race the wall clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import text


class SyncHealth(str, Enum):
    """What a sweep's own record says about itself.

    ⛔ `SUCCESS_EMPTY` AND `FAILED` MUST NEVER COLLAPSE. A rate limit that returns an empty page
    instead of an error, and a mailbox that genuinely holds nothing, produce the same
    `scanned = 0` — and a caller that cannot tell them apart will publish "no meeting scheduled"
    off the back of an outage. `l1_sync_runs.error` is what separates them and it has always been
    there; nothing had ever read it for this purpose.
    """

    #: The cursor was exhausted and nothing failed. The only state that licenses an absence claim.
    HEALTHY = "healthy"
    #: Nothing failed and nothing was found. A real answer, and NOT evidence of an empty source
    #: unless the cursor was also exhausted.
    SUCCESS_EMPTY = "success_empty"
    #: The sweep stopped before the provider ran out — a page budget, a cap, a truncation. There
    #: is a tail we were never shown.
    PARTIAL = "partial"
    #: The sweep recorded an error. Whatever it did or did not return says nothing about the world.
    FAILED = "failed"
    #: No run at all covers this window. Distinct from every state above: we did not look.
    UNKNOWN = "unknown"


#: Closed vocabulary, guarded in both directions by `tests/capture/test_coverage_window.py`.
SYNC_HEALTHS: tuple[SyncHealth, ...] = (
    SyncHealth.HEALTHY, SyncHealth.SUCCESS_EMPTY, SyncHealth.PARTIAL,
    SyncHealth.FAILED, SyncHealth.UNKNOWN,
)

#: The health states under which an absence claim may be made AT ALL. `scoped_absence` (L3-03) is
#: the gate that uses it; this set is the part of the decision that belongs to the sweep.
#:
#: ⛔ `SUCCESS_EMPTY` IS DELIBERATELY ABSENT. A sweep that found nothing and did not exhaust its
#: cursor has not established that nothing exists — it has established that it saw nothing, which
#: is the exact substitution this whole module exists to prevent.
ABSENCE_CAPABLE: frozenset[SyncHealth] = frozenset({SyncHealth.HEALTHY})


@dataclass(frozen=True, slots=True)
class WindowCoverage:
    """How much of one source's window we landed, as of the runs that cover it.

    Frozen for the same reason `SignalCoverage` is: a mutable block could be rewritten by a later
    backfill, and yesterday's claim would silently restate itself tonight.
    """

    source: str
    window_start: datetime | None
    window_end: datetime | None
    #: Runs that overlapped the window. Zero means `UNKNOWN`, never "complete".
    runs: int
    #: What we actually landed across those runs.
    indexed: int
    #: What the provider said exists. ⛔ `None` means the provider gave us NO COUNT — not zero, and
    #: not everything.
    claimed_total: int | None
    #: Gmail's `resultSizeEstimate` is an estimate and Google named it that. An estimate stored
    #: without its label becomes a fact at the first reader.
    is_estimate: bool
    #: Did every run reach the end of what it was offered?
    cursor_exhausted: bool
    health: SyncHealth
    #: The first error text recorded in the window, when there was one. Kept because "it failed"
    #: without "how" sends an operator to the wrong place.
    error: str | None = None

    @property
    def completeness_bp(self) -> int | None:
        """Share of the window we read, in integer basis points — or `None` when unknowable.

        ⛔ `None` RATHER THAN 10000 IS THE WHOLE POINT. No denominator means no ratio, and a
        confident 100% is the exact failure this module exists to prevent. Integer basis points
        because a float here would compare unequal across two reads of the same rows.

        `indexed > claimed_total` is LEGAL and clamps rather than raising: Gmail's estimate runs
        low routinely, and a checker that treated the excess as an error would fire on a perfectly
        correct sweep.
        """
        if self.claimed_total is None or self.claimed_total <= 0:
            return None
        return min(10000, round(self.indexed * 10000 / self.claimed_total))

    @property
    def can_support_absence(self) -> bool:
        """⛔ May a caller say "there is none" on the strength of this window?

        Health alone is not enough: a healthy sweep with no denominator read everything it was
        OFFERED, which is not the same as everything that EXISTS. Both conditions, or neither.
        """
        return self.health in ABSENCE_CAPABLE and self.completeness_bp is not None

    def describe(self) -> str:
        """The sentence a card or an answer prints. Never a bare percentage.

        The shape is deliberate: the numerator is exact, the denominator carries `about` when it is
        an estimate, and an unknown denominator says so instead of being omitted — a missing
        denominator that reads as a complete answer is the failure being prevented.
        """
        if self.health is SyncHealth.UNKNOWN:
            return f"no {self.source} sync covers this window"
        if self.health is SyncHealth.FAILED:
            return f"{self.source} sync failed in this window — coverage unknown"
        if self.claimed_total is None:
            return f"read {self.indexed} from {self.source}; the provider gave no total"
        about = "about " if self.is_estimate else ""
        tail = "" if self.cursor_exhausted else " (incomplete — a tail was never read)"
        return f"read {self.indexed} of {about}{self.claimed_total} from {self.source}{tail}"


def _health_of(runs: list, cursor_exhausted: bool, indexed: int) -> SyncHealth:
    """The health of a WINDOW, which is not the health of its best run.

    Order is the design, and it is the same instinct as `fact_write_action`: the states that mean
    "do not trust this" are decided FIRST. A window containing one failure and nine clean sweeps is
    not healthy — the failure is exactly where the missing mail would be.
    """
    if not runs:
        return SyncHealth.UNKNOWN
    if any(r.error for r in runs):
        return SyncHealth.FAILED
    if not cursor_exhausted:
        return SyncHealth.PARTIAL
    if indexed == 0:
        return SyncHealth.SUCCESS_EMPTY
    return SyncHealth.HEALTHY


def coverage_for_window(conn, *, org_id: str, source: str,
                        since: datetime, until: datetime) -> WindowCoverage:
    """What `l1_sync_runs` says about one source between two instants.

    ⛔ THIS IS THE READ THAT DID NOT EXIST. Migration 0178 added `cursor_exhausted`,
    `page_budget_spent`, `claimed_total` and `claimed_is_estimate`; `api/routes.py` writes them on
    every sync; and no `select` in the engine had ever read them back.

    Runs are matched on `finished_at` inside the half-open window `[since, until)` — the same
    convention as the graph's point-in-time read, and for the same reason: a run finishing exactly
    at `until` must belong to one window and not to two.

    A missing table is treated as `UNKNOWN`, not as an error and never as zero. A tenant whose
    migrations have not run has not proven anything about their mailbox.
    """
    try:
        rows = conn.execute(text(
            "select scanned, claimed_total, claimed_is_estimate, cursor_exhausted, "
            "       page_budget_spent, error "
            "  from l1_sync_runs "
            " where org_id = :o and source = :s "
            "   and finished_at >= :since and finished_at < :until"),
            {"o": org_id, "s": source, "since": since, "until": until}).fetchall()
    except Exception:                       # noqa: BLE001 — absent table, absent columns, no rows
        rows = []

    indexed = sum(int(r.scanned or 0) for r in rows)
    # THE DENOMINATOR IS A MAX, NOT A SUM. Consecutive sweeps of one source each report the
    # provider's total for the same corpus; adding them would multiply the mailbox by the number of
    # times we looked at it. `None` when no run supplied one — and `None` is not zero.
    claims = [int(r.claimed_total) for r in rows if r.claimed_total is not None]
    claimed_total = max(claims) if claims else None
    # An estimate anywhere makes the whole figure an estimate. The label may only ever widen.
    is_estimate = any(bool(r.claimed_is_estimate) for r in rows)
    # EVERY run must have finished for the window to be finished. `None` counts as not exhausted:
    # a run written before 0178 cannot vouch for itself, and treating silence as completion is the
    # fabricated 100% in a different costume.
    exhausted = bool(rows) and all(bool(r.cursor_exhausted) for r in rows)
    error = next((r.error for r in rows if r.error), None)

    return WindowCoverage(
        source=source, window_start=since, window_end=until, runs=len(rows),
        indexed=indexed, claimed_total=claimed_total, is_estimate=is_estimate,
        cursor_exhausted=exhausted, health=_health_of(list(rows), exhausted, indexed), error=error)
