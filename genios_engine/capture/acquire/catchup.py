"""L1.2.6-U3 · Catch-up windows.

After an outage — ours or the provider's — a connection resumes at its normal cadence and pulls
its normal one-or-twenty pages. For a source that kept receiving traffic for the whole gap, that
page budget covers a fraction of what arrived, and because the watermark advances to the newest
thing it DID see, the rest of the gap is never requested again. The loss is silent: every run
after the outage reports success.

The two wrong fixes are equally easy. Re-running a full backfill re-ingests the entire history
(paid for at the provider, at the LLM gate, and in wall-clock, every time anything hiccups), and
doing nothing skips the gap. The right answer is the CURSOR, which already records where the last
run got to: resume from the stored watermark and simply pay for MORE PAGES this once, in
proportion to how much time was missed, so the backlog drains without anything being re-read
from before the watermark.

`now` is a parameter, never a call — this decides schedules, and a unit whose answer depends on
when the suite ran is a unit nobody can test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

#: A gap wider than this many cadences is an outage rather than a late tick. Three is the plan's
#: number and it is deliberately not one: a single slow sweep, a deploy, or a restart routinely
#: pushes one interval, and treating that as an outage would make every deploy trigger a
#: catch-up storm across every tenant.
CATCH_UP_INTERVAL_MULTIPLE = 3
#: Hard ceiling on the extended page budget. The budget scales with the gap, and a connection
#: that was disconnected for a month would otherwise ask for a five-figure page count and turn a
#: recovery into a self-inflicted outage. Whatever is left after 200 pages drains on the NEXT
#: run, which is still a catch-up because the watermark has barely moved.
MAX_CATCH_UP_PAGES = 200
#: How far back a catch-up may look when there is NO watermark to resume from (a connection that
#: has never completed a page). Bounded so "catch up" can never silently become "backfill all
#: history" — the real backfill path is `backfill_drain`, chosen explicitly.
MAX_CATCH_UP_LOOKBACK_SECONDS = 30 * 24 * 3600


def _utc(value: datetime) -> datetime:
    """Naive datetimes are read as UTC rather than rejected: this runs inside a background sweep
    over rows written by several code paths, and one connection with a naive timestamp must not
    take the whole sweep down. Everything the engine stores is UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class CatchUpRequest:
    now: datetime
    #: when this connection last completed a poll — `Cursor.synced_at`
    last_success_at: datetime | None
    #: the newest `occurred_at` the connection has seen — `Cursor.watermark`
    watermark: datetime | None
    interval_seconds: int
    base_page_budget: int


@dataclass(frozen=True)
class CatchUpPlan:
    """What this one run should do about the time it missed.

    `catch_up` is the flag the run is marked with so a recovery is visible in the admin console
    instead of looking like an ordinary sync that happened to be big.
    """
    catch_up: bool
    gap_seconds: int
    missed_intervals: int
    max_pages: int
    since: datetime | None
    reason: str            # first_run | current | gap


def plan_catch_up(request: CatchUpRequest) -> CatchUpPlan:
    """Decide the page budget and resume point for one poll — U3's public unit."""
    if request.interval_seconds <= 0:
        raise ValueError(f"interval_seconds must be positive, got {request.interval_seconds}")
    if request.base_page_budget <= 0:
        raise ValueError(f"base_page_budget must be positive, got {request.base_page_budget}")
    now = _utc(request.now)
    watermark = _utc(request.watermark) if request.watermark is not None else None

    if request.last_success_at is None:
        # Never polled. This is not an outage and must not be treated as one: the first pull is
        # the connector's own bounded first page, and the FULL history is `backfill_drain`'s job.
        return CatchUpPlan(False, 0, 0, request.base_page_budget, watermark, "first_run")

    # A last_success in the future (clock skew, a restored backup) is nonsense, not a negative
    # gap — clamp to zero rather than compute a negative page budget out of it.
    gap_seconds = max(0, int((now - _utc(request.last_success_at)).total_seconds()))
    missed_intervals = gap_seconds // request.interval_seconds
    if gap_seconds <= CATCH_UP_INTERVAL_MULTIPLE * request.interval_seconds:
        return CatchUpPlan(False, gap_seconds, missed_intervals,
                           request.base_page_budget, watermark, "current")

    max_pages = min(request.base_page_budget * missed_intervals, MAX_CATCH_UP_PAGES)
    max_pages = max(max_pages, request.base_page_budget)     # never BELOW a normal run
    if watermark is not None:
        since = watermark          # resume exactly where the last run stopped: no re-ingest
    else:
        since = now - timedelta(seconds=min(gap_seconds, MAX_CATCH_UP_LOOKBACK_SECONDS))
    return CatchUpPlan(True, gap_seconds, missed_intervals, max_pages, since, "gap")
