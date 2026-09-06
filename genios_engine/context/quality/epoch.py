"""L-5 · the COVERAGE EPOCH — the window over which `coverage_ready` was true for a source.

`source_coverage` answers one question: what can we see *now*. It is an upsert, so the instant a
tenant connects Intercom the evidence that we could NOT see support last week is overwritten in
place — and every negative inference drawn last week ("no tickets, therefore healthy") silently
becomes a claim about a source set that no longer exists.

An epoch is the append-only half of that row. One epoch is one coverage REGIME: a window
`[opened_at, closed_at)` over which the domain's capability state did not change, carrying the
answer that held throughout it. That makes three questions answerable which an upserted row can
only ever answer "now":

    was this source reporting at the instant we drew this conclusion?   `epoch_at`
    did coverage change under this trend's window?                      `coverage_over`
    is a stored negative inference still standing on its evidence?      `stale_coverage`

**Scoped per domain, deliberately.** Doc 13: *"a new billing connector does not invalidate
support-absence inferences. The epoch check is per-capability, or every connector change
re-derives the whole graph."* `source_coverage.connected` holds the org's WHOLE capability set on
every domain's row, so hashing the row would bump all four domains every time any connector
moved. `fingerprint` hashes only the capabilities that domain's own requirements name.

**The epoch is advanced on a real path, once per sweep.** `platform.wiring.make_coverage_fn` is
the single factory all four capture doors share; it files the declaration to `source_coverage` and
then calls `advance_epochs` with the same rows. A sweep that sees an unchanged source set writes
nothing — the advance is keyed on the fingerprint, not on the fact that a sweep ran, so a
ten-minute cadence does not mint 144 epochs a day.

**No clock in logic.** `at` is a parameter everywhere; the wall clock is read at the process
boundary (the declaration's own `computed_at`) and passed down.

**Nothing is deleted.** A superseded epoch is CLOSED. An inference drawn under it is MARKED, not
dropped: deleting it would lose the record of what the system believed and why.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.platform.canonical import stable_id

#: The table `source_coverage`'s history lives in. Named here so the two writers and the three
#: readers cannot disagree about it by typo.
EPOCH_TABLE = "coverage_epochs"

#: The epoch every (org, domain) starts at. `1` rather than `0` matches migration 0104's default
#: on `source_coverage.coverage_epoch`, so a tenant whose sweep has not run since the migration
#: reads the same number from either table instead of one of them saying "no epoch".
FIRST_EPOCH = 1

#: What a capability contributes to a fingerprint when the org has no connection satisfying it.
#: Stated rather than left as a missing key so the fingerprint of "we never had a CRM" and
#: "we lost the CRM" are the same string — they are the same coverage regime.
NOT_CONNECTED = "not_connected"


@dataclass(frozen=True, slots=True)
class CoverageEpoch:
    """One coverage regime for one (org, domain), and the window it held over.

    Frozen, and `capabilities` is a tuple, for the reason `capture.coverage.store.CoverageRow`
    gives: a row read back is a record of what was true, and a caller that could append to it
    would be editing history in place.
    """

    org_id: str
    domain: str
    epoch: int
    coverage_ready: bool
    fingerprint: str
    capabilities: tuple[str, ...]
    opened_at: datetime
    closed_at: datetime | None = None

    def covers(self, at: datetime) -> bool:
        """Is `at` inside this epoch? Half-open `[opened_at, closed_at)`.

        Half-open rather than closed because the boundary instant belongs to exactly one epoch:
        `advance_epochs` closes the old window and opens the new one at the SAME instant, and a
        closed interval would make that instant belong to both — so a reader asking "what could we
        see when we decided this" would get two answers and take whichever came back first.
        """
        if at < self.opened_at:
            return False
        return self.closed_at is None or at < self.closed_at

    @property
    def is_open(self) -> bool:
        return self.closed_at is None


@dataclass(frozen=True, slots=True)
class EpochChange:
    """One (org, domain) whose coverage regime changed, and what it changed from.

    Returned by `advance_epochs` rather than logged, because "which connector moved" is the
    receipt for every inference the bump invalidates, and a receipt that only exists in a log line
    cannot be read by the code that has to act on it.
    """

    org_id: str
    domain: str
    previous_epoch: int | None
    epoch: int
    was_ready: bool | None
    coverage_ready: bool
    at: datetime

    @property
    def is_first(self) -> bool:
        """The domain's first epoch — a declaration, not a change. Nothing to invalidate."""
        return self.previous_epoch is None

    @property
    def withdraws_licence(self) -> bool:
        """Coverage was ready and is not any more: doc 13's E-5. Every FUTURE absence in this
        domain is `UNKNOWABLE`, and every stored one is standing on a source that has gone."""
        return self.was_ready is True and self.coverage_ready is False


@dataclass(frozen=True, slots=True)
class CoverageWindow:
    """What coverage did across a PERIOD, rather than at an instant.

    `ready` is a TRI-STATE and `None` is not `False`. A window that no epoch describes, or one
    whose epochs disagree, is *unknown*: reading either as `False` would be a claim that we could
    not see, and reading it as `True` would license an inference over a period nobody assessed.

    `crossed` is the other half of doc 13's rule — *"no trend may cross an epoch boundary without
    saying so"*. A series computed over a window where a connector was added is not wrong, but the
    step in it is OUR step, not the customer's, and the consumer has to be told which.
    """

    domain: str
    ready: bool | None
    crossed: bool
    epochs: tuple[int, ...]

    @property
    def licenses_negative_inference(self) -> bool:
        """Only a window that was covered THROUGHOUT, with no boundary inside it, licenses
        "nothing happened here". A crossed window does not, however green both halves are: the
        two halves were different questions."""
        return self.ready is True and not self.crossed


def epoch_fingerprint(*, domain: str, coverage_ready: bool,
                      capabilities: Mapping[str, str]) -> str:
    """The content address of one domain's coverage regime.

    Two sweeps that see the same sources produce the same fingerprint and therefore no new epoch;
    any change of any kind produces a different one. Comparing fingerprints rather than timestamps
    is what makes `advance_epochs` idempotent under a sweep that runs every ten minutes.

    `coverage_ready` is inside the hash as well as the capability statuses because the requirement
    table can move underneath a tenant whose connections did not: adding `crm` to `sales`'
    required list flips readiness with an identical connection set, and that is a change of regime
    exactly as connecting a mailbox is.
    """
    return stable_id("cov_epoch", {"domain": domain, "ready": bool(coverage_ready),
                                   "capabilities": dict(sorted(capabilities.items()))})


def scoped_capabilities(*, required: Sequence[str], recommended: Sequence[str],
                        freshness: Mapping[str, str]) -> dict[str, str]:
    """The capability statuses THIS domain's coverage depends on — nothing else.

    The scoping doc 13 demands, and the reason it cannot be taken off the coverage row as stored:
    `rows_for` writes the org's whole connected set onto every domain's row, so `sales` and
    `admin` differ only in their `required` array. Hashing the row would bump `sales` when Stripe
    is connected, mark every sales absence stale, and re-derive the whole graph for a connector
    that has nothing to do with it.

    A capability the org does not have contributes `not_connected` rather than being omitted, so
    the fingerprint has a fixed shape per domain and "we never had it" and "we lost it" hash the
    same — they are the same regime.
    """
    return {cap: str(freshness.get(cap, NOT_CONNECTED))
            for cap in sorted({*required, *recommended})}


def _row_capabilities(row: Any) -> dict[str, str]:
    """One `CoverageRow`'s domain-scoped capability statuses.

    `required` comes off the row (the store reads it from the requirement table rather than
    deriving it, so it is authoritative); `recommended` is not stored, so it is read from the same
    requirement table the store used. An unregistered domain has neither, and its scoped set is
    empty — which is correct and self-consistent: `compute_coverage` fails such a domain closed at
    `coverage_ready=False`, so its regime is "unassessed" and does not change when connectors do.
    """
    from genios_engine.capture.coverage.model import PACK_REQUIREMENTS
    reqs = PACK_REQUIREMENTS.get(row.domain, {})
    return scoped_capabilities(required=tuple(row.required or ()),
                               recommended=tuple(reqs.get("recommended", ())),
                               freshness=dict(row.freshness or {}))


def _capability_list(capabilities: Mapping[str, str]) -> list[str]:
    """`capability=status` pairs, sorted — the stored receipt for a bump.

    A flat text[] rather than jsonb because the only questions asked of it are "which capabilities
    were in scope" and "what did they say", and both are answered by reading it. Sorted so two
    sweeps that saw the same thing store byte-identical arrays.
    """
    return [f"{cap}={status}" for cap, status in sorted(capabilities.items())]


def _to_epoch(row: Any) -> CoverageEpoch:
    return CoverageEpoch(
        org_id=row.org_id, domain=row.domain, epoch=int(row.epoch),
        coverage_ready=bool(row.coverage_ready), fingerprint=str(row.fingerprint),
        capabilities=tuple(row.capabilities or ()),
        opened_at=row.opened_at, closed_at=row.closed_at)


def advance_epochs(conn, org_id: str, rows: Iterable[Any], *,
                   at: datetime) -> tuple[EpochChange, ...]:
    """Open a new epoch for every domain whose coverage regime CHANGED. Idempotent.

    Called with the `CoverageRow`s a sweep just filed, on the same connection, from
    `platform.wiring.make_coverage_fn` — the one factory every capture door shares. Returns the
    changes rather than a count so the caller can see which domains moved.

    The sequence per domain is: fingerprint the scoped capabilities, compare to the OPEN epoch's
    fingerprint, and if and only if they differ, close the open window at `at` and open a new one
    at the same instant with `epoch + 1`. Equal fingerprints write nothing at all — not even a
    touched timestamp — because a sweep every ten minutes would otherwise mint 144 epochs a day
    and every one of them would mark the previous day's inferences stale.

    `source_coverage.coverage_epoch` is updated in the same transaction, so the current epoch is
    readable from the row a reader already has instead of from a window query per absence.
    """
    changes: list[EpochChange] = []
    for row in rows:
        capabilities = _row_capabilities(row)
        fingerprint = epoch_fingerprint(domain=row.domain,
                                        coverage_ready=bool(row.coverage_ready),
                                        capabilities=capabilities)
        open_row = conn.execute(text(
            f"select org_id, domain, epoch, coverage_ready, fingerprint, capabilities, "
            f"opened_at, closed_at from {EPOCH_TABLE} "
            "where org_id = :o and domain = :d and closed_at is null"),
            {"o": org_id, "d": row.domain}).first()
        if open_row is not None and str(open_row.fingerprint) == fingerprint:
            continue                       # same regime — a sweep is not a change
        previous = int(open_row.epoch) if open_row is not None else None
        epoch = FIRST_EPOCH if previous is None else previous + 1
        if open_row is not None:
            conn.execute(text(
                f"update {EPOCH_TABLE} set closed_at = :at "
                "where org_id = :o and domain = :d and epoch = :e and closed_at is null"),
                {"at": at, "o": org_id, "d": row.domain, "e": previous})
        conn.execute(text(
            f"insert into {EPOCH_TABLE} (org_id, domain, epoch, coverage_ready, fingerprint, "
            "  capabilities, opened_at, closed_at) "
            "values (:o, :d, :e, :ready, :fp, :caps, :at, null)"),
            {"o": org_id, "d": row.domain, "e": epoch, "ready": bool(row.coverage_ready),
             "fp": fingerprint, "caps": _capability_list(capabilities), "at": at})
        conn.execute(text(
            "update source_coverage set coverage_epoch = :e where org_id = :o and domain = :d"),
            {"e": epoch, "o": org_id, "d": row.domain})
        changes.append(EpochChange(
            org_id=org_id, domain=row.domain, previous_epoch=previous, epoch=epoch,
            was_ready=bool(open_row.coverage_ready) if open_row is not None else None,
            coverage_ready=bool(row.coverage_ready), at=at))
    return tuple(changes)


def current_epochs(conn, org_id: str) -> dict[str, CoverageEpoch]:
    """The OPEN epoch per domain — what we can see now, and since when. One query per org."""
    rows = conn.execute(text(
        f"select org_id, domain, epoch, coverage_ready, fingerprint, capabilities, opened_at, "
        f"closed_at from {EPOCH_TABLE} where org_id = :o and closed_at is null"),
        {"o": org_id}).all()
    return {str(r.domain): _to_epoch(r) for r in rows}


def epoch_at(conn, org_id: str, domain: str, at: datetime) -> CoverageEpoch | None:
    """Which regime held at ONE instant. `None` means no epoch describes it.

    `None` is the third state and is never `coverage_ready=False`: a period before the tenant's
    first sweep is a period nobody assessed, and answering `False` there would be a claim we made
    up. It is the same distinction `history.gap_point` keeps when it returns `coverage_ready=None`
    for a period with no reading.
    """
    row = conn.execute(text(
        f"select org_id, domain, epoch, coverage_ready, fingerprint, capabilities, opened_at, "
        f"closed_at from {EPOCH_TABLE} "
        "where org_id = :o and domain = :d and opened_at <= :at "
        "  and (closed_at is null or closed_at > :at) "
        "order by epoch desc limit 1"),
        {"o": org_id, "d": domain, "at": at}).first()
    return _to_epoch(row) if row is not None else None


def epochs_over(conn, org_id: str, domain: str, start: datetime,
                end: datetime) -> tuple[CoverageEpoch, ...]:
    """Every regime that OVERLAPS `[start, end)`, oldest first.

    Overlap rather than containment: an epoch that opened before the window and is still open
    covers the whole of it and would be missed by a containment test, which is exactly the case a
    stable tenant is in for every window it ever asks about.
    """
    if end < start:
        raise ValueError(f"a coverage window ends before it starts: {start} .. {end}")
    rows = conn.execute(text(
        f"select org_id, domain, epoch, coverage_ready, fingerprint, capabilities, opened_at, "
        f"closed_at from {EPOCH_TABLE} "
        "where org_id = :o and domain = :d and opened_at < :end "
        "  and (closed_at is null or closed_at > :start) "
        "order by epoch"),
        {"o": org_id, "d": domain, "start": start, "end": end}).all()
    return tuple(_to_epoch(r) for r in rows)


def coverage_over(domain: str, epochs: Sequence[CoverageEpoch], *,
                  start: datetime, end: datetime) -> CoverageWindow:
    """What coverage did across a whole period — the answer a trend has to consult.

    PURE: the epochs are injected, so the same window over the same regimes is the same answer on
    any machine, and `epochs_over` is the only thing that touches a database.

    Three outcomes, and the middle one is the product:

    * covered throughout, one regime      -> `ready=True`, and a negative inference is licensed;
    * a boundary inside the window        -> `crossed=True`, and it is NOT, however green both
                                             halves are. "engagement fell" and "we started being
                                             able to see engagement" are the same series and
                                             different sentences;
    * no regime describes the window,
      or the regimes disagree             -> `ready=None`. Unknown, never False.
    """
    if not epochs:
        return CoverageWindow(domain=domain, ready=None, crossed=False, epochs=())
    numbers = tuple(e.epoch for e in epochs)
    crossed = len(epochs) > 1 or not _spans(epochs, start, end)
    readies = {e.coverage_ready for e in epochs}
    ready: bool | None
    if len(readies) > 1:
        ready = None                       # the regimes disagree: no single answer is honest
    elif not _spans(epochs, start, end):
        ready = None                       # part of the window is undescribed
    else:
        ready = readies.pop()
    return CoverageWindow(domain=domain, ready=ready, crossed=crossed, epochs=numbers)


def _spans(epochs: Sequence[CoverageEpoch], start: datetime, end: datetime) -> bool:
    """Do these epochs, in order, cover `[start, end)` with no hole?

    A hole is not the same as a boundary: a boundary is two regimes meeting, and a hole is a
    stretch nobody described (before the first sweep, or between two runs of a tenant that was
    off). Both make `ready` unknown; only the hole makes it unknown for a reason the consumer
    cannot fix by looking at the epochs.
    """
    cursor = start
    for epoch in epochs:
        if epoch.opened_at > cursor:
            return False
        if epoch.closed_at is None or epoch.closed_at >= end:
            return True
        cursor = max(cursor, epoch.closed_at)
    return cursor >= end


def stale_coverage(*, domain: str, drawn_under: int | None,
                   current: Mapping[str, CoverageEpoch] | Mapping[str, int]) -> bool:
    """Was this negative inference drawn under a coverage regime that has since been superseded?

    Doc 13's read-side rule, and the whole of it: *"if inference.coverage_epoch <
    org.coverage_epoch and the change touched this capability -> mark STALE_COVERAGE,
    re-evaluate before use."* The capability scoping is structural here rather than a second
    condition — epochs are per domain and `epoch_fingerprint` is taken over the domain's own
    capabilities, so a billing connector never advances `support`'s number and a support
    inference is never marked by it.

    `drawn_under=None` is a claim with no epoch recorded at all, which is NOT stale — it is
    unverifiable, and treating it as stale would mark every pre-migration row and drown the real
    ones. The caller that cares about the difference reads the `None` itself.
    """
    if drawn_under is None:
        return False
    held = current.get(domain)
    if held is None:
        return False                       # no regime on record: nothing to be behind
    now_epoch = held.epoch if isinstance(held, CoverageEpoch) else int(held)
    return int(drawn_under) < now_epoch


__all__ = ["EPOCH_TABLE", "FIRST_EPOCH", "NOT_CONNECTED", "CoverageEpoch", "CoverageWindow",
           "EpochChange", "advance_epochs", "coverage_over", "current_epochs", "epoch_at",
           "epoch_fingerprint", "epochs_over", "scoped_capabilities", "stale_coverage"]
