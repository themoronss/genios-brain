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

STEP-10 · PER MAILBOX, AND NEVER MORE READ THAN EXISTS (`yc2_w27_s10 · M29.C5.L-logic.V1.U02`).
Two things were wrong with the read above, and both showed on the golden set. It was per SOURCE —
two Gmail mailboxes were one window, over an interval the caller chose — when the question a file
asks is about ONE mailbox over the window that mailbox was set to sweep. And its measure summed what
every run read against the LARGEST total any single run had been told: right for the rounds of one
backfill, which each re-count the same query, wrong for an incremental sweep, whose total counts only
its own new mail — so F14's two sweeps, 1 of 1 and then 3 of 3, said *"read 4 of about 3"*. Now each
run is measured against its own total (`_measure`), and `coverage_for_connection` reads one mailbox
— one `connections` row — over its own `backfill_days`, as of an instant.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import text

from genios_engine.capture.connectors.backfill import backfill_window_for
from genios_engine.contracts.connection import Connection


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
    #: What the provider said exists — each run's own count, summed (`_measure`), and never below
    #: what was read. ⛔ `None` means we were given NO COUNT for what was read — not zero, and not
    #: everything.
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
    #: STEP-10 · set when this is ONE MAILBOX's window (`coverage_for_connection`): its
    #: `connections` row, the address that row names (`external_account_id`, when written and an
    #: address — Composio does not report it today), and the window it is set to sweep, in days
    #: (`capture_scope.backfill_days`, default 60). `None` window days: the setting cannot be read.
    connection_id: str | None = None
    address: str | None = None
    window_days: int | None = None

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
            "select connection_id, mode, scanned, claimed_total, claimed_is_estimate, "
            "       cursor_exhausted, page_budget_spent, error "
            "  from l1_sync_runs "
            " where org_id = :o and source = :s "
            "   and finished_at >= :since and finished_at < :until"),
            {"o": org_id, "s": source, "since": since, "until": until}).fetchall()
    except Exception:                       # noqa: BLE001 — absent table, absent columns, no rows
        rows = []
    return _window_of(rows, source=source, since=since, until=until)


def coverage_for_connection(conn, *, org_id: str, connection_id: str,
                            now: datetime) -> WindowCoverage | None:
    """STEP-10 · ONE MAILBOX, over the window it is set to sweep, as of `now`.

    One mailbox is one `connections` row, and only this tenant's: another tenant's id reads as no
    connection, never as theirs. Its window is the row's own `backfill_days`
    (`connectors/backfill.backfill_window_for`, sixty days unless an admin set it), measured back
    from `now`. The runs counted are this connection's that finished after the window opened and
    no later than `now` — AS OF an instant, so a replay asked at its case's instant counts the sweep
    that finished at it and none that came after.

    ⛔ A WINDOW SETTING THAT CANNOT BE READ IS AN UNKNOWN WINDOW. The connector refuses such a
    setting loudly at construction; a coverage read that fell back to sixty days would vouch for a
    window nobody configured. No run is counted and the health is `UNKNOWN`.

    `None` when the tenant has no such connection, or the row cannot be read.
    """
    try:
        row = conn.execute(text(
            "select source_type, external_account_id, capture_scope "
            "  from connections where org_id = :o and connection_id = :c"),
            {"o": org_id, "c": connection_id}).first()
    except Exception:                       # noqa: BLE001 — absent table: no mailbox is known
        return None
    if row is None:
        return None
    window = _backfill_window(row, org_id=org_id, connection_id=connection_id)
    mailbox = dict(connection_id=connection_id, address=_address(row.external_account_id),
                   window_days=window.days if window is not None else None)
    if window is None:
        return _window_of([], source=row.source_type, since=None, until=now, **mailbox)
    since = window.since(now)
    try:
        rows = conn.execute(text(
            "select mode, scanned, claimed_total, claimed_is_estimate, "
            "       cursor_exhausted, page_budget_spent, error "
            "  from l1_sync_runs "
            " where org_id = :o and connection_id = :c "
            "   and finished_at > :since and finished_at <= :now"),
            {"o": org_id, "c": connection_id, "since": since, "now": now}).fetchall()
    except Exception:                       # noqa: BLE001 — absent table: no run vouches for it
        rows = []
    return _window_of(rows, source=row.source_type, since=since, until=now, **mailbox)


def _backfill_window(row, *, org_id: str, connection_id: str):
    """The window this connection's row is set to sweep, or None when the setting cannot be read.

    Through `backfill_window_for`, the one reader of the setting, so this cannot drift from what
    the connector actually sweeps. `capture_scope` is read straight off the row: the only thing a
    store adds is decrypting secret fields, and `backfill_days` is not one.
    """
    scope = row.capture_scope
    try:
        if isinstance(scope, str):          # a driver that hands jsonb back as text
            scope = json.loads(scope)
        return backfill_window_for(Connection(connection_id=connection_id, org_id=org_id,
                                              source_type=row.source_type,
                                              config=dict(scope or {})))
    except (TypeError, ValueError):         # a typo'd setting, a scope that is not an object
        return None


def _address(value) -> str | None:
    """The row's `external_account_id` as an address — trimmed, lowercase, the way every address of
    ours is compared — or None: unwritten, or not an address at all (an account id is not one)."""
    address = str(value or "").strip().lower()
    return address if "@" in address else None


def _window_of(rows, *, source: str, since: datetime | None, until: datetime | None,
               **mailbox) -> WindowCoverage:
    """A window's runs, as one `WindowCoverage` — the per-source read and the per-mailbox read
    measure the same way."""
    indexed, claimed_total, is_estimate = _measure(rows)
    # EVERY run must have finished for the window to be finished. `None` counts as not exhausted:
    # a run written before 0178 cannot vouch for itself, and treating silence as completion is the
    # fabricated 100% in a different costume.
    exhausted = bool(rows) and all(bool(r.cursor_exhausted) for r in rows)
    error = next((r.error for r in rows if r.error), None)
    return WindowCoverage(
        source=source, window_start=since, window_end=until, runs=len(rows),
        indexed=indexed, claimed_total=claimed_total, is_estimate=is_estimate,
        cursor_exhausted=exhausted, health=_health_of(list(rows), exhausted, indexed), error=error,
        **mailbox)


def _measure(rows) -> tuple[int, int | None, bool]:
    """`(indexed, claimed_total, is_estimate)` — STEP-10: every run against its OWN count.

    ⛔ A RUN'S COUNT IS OF ITS OWN QUERY. The rounds of one backfill each re-count the SAME query —
    the connection's whole window — so their reads add up and their counts do not: one corpus,
    its largest count (adding them would multiply the mailbox by the rounds it took). Every other
    run — an incremental sweep, a recovery re-scan — was told how much matched ITS query, its own
    slice, so its count adds to the others'. Taking the largest of those as the window's total
    is what said *"read 4 of about 3"* over F14's two sweeps, 1 of 1 and then 3 of 3. A run that
    does not say its mode is read as a backfill round: the rule every row was read by before.

    ⛔ NEVER MORE READ THAN COUNTED. A count below what was read from it is no longer the
    provider's number — an estimate that ran low, or a message and its attachment landing as two
    objects against one counted message — so it is raised to what was read, and the figure is
    an estimate. A slice that read mail and was given no count, or a count of none, leaves the
    WINDOW without a total: its mail would sit in the numerator over a total that never counted
    it. A slice that read nothing adds nothing either way. `None` is not zero, throughout.
    """
    corpora: dict[tuple, list] = {}
    for i, r in enumerate(rows):
        mode = getattr(r, "mode", None)
        key = (("round", getattr(r, "connection_id", None)) if mode in (None, "backfill")
               else ("run", i))
        corpus = corpora.setdefault(key, [0, None])          # [read, count]
        corpus[0] += int(r.scanned or 0)
        if r.claimed_total is not None:
            corpus[1] = max(int(r.claimed_total), corpus[1] or 0)
    indexed = sum(read for read, _ in corpora.values())
    # An estimate anywhere makes the whole figure an estimate. The label may only ever widen.
    is_estimate = any(bool(r.claimed_is_estimate) for r in rows)
    total, counted = 0, False
    for read, count in corpora.values():
        if read and not count:
            return indexed, None, is_estimate
        if count is None:
            continue
        counted = True
        is_estimate = is_estimate or read > count
        total += max(count, read)
    return indexed, (total if counted else None), is_estimate
