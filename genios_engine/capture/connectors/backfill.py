"""L1.2.4-U1 · the first-connect backfill window, as a per-connection setting.

THE DEFECT THIS MODULE ENDS. The window was two module constants —
`composio._BACKFILL_WINDOW = "newer_than:60d"` and `calendar._BACKFILL_DAYS = 60` — so every
tenant, forever, got the same two months of history and no operator could change it without a
deploy. Two months is not enough history to be worth reasoning over: an acquisition thread, a
deal cycle longer than a quarter, and any year-over-year comparison all sit outside it, which
means the questions a tenant actually asks ("who are my best customers", "what worked before")
were unanswerable by construction.

WHY A SETTING RATHER THAN A BIGGER CONSTANT. A ten-year mailbox and a three-month-old startup do
not want the same first sync, and the cost of the choice is one-time (the extraction cache means a
document is extracted once, ever) but not zero. So the default is wide (`DEFAULT_BACKFILL_DAYS`,
18 months) and an admin can raise or lower it per connection.

WHERE IT LIVES. In `Connection.config` — the `capture_scope` jsonb that already holds every
source-specific setting — so this needs no contract change and no new column. Migration
0082 stamps the OLD default onto rows that already exist: widening history for a live tenant is a
deliberate act by an operator, never a side effect of deploying this file.

PURE: no clock, no DB, no network. `since()` takes `now` as a parameter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from genios_engine.contracts.connection import Connection

#: The key inside `Connection.config` (connections.capture_scope jsonb).
BACKFILL_DAYS_KEY = "backfill_days"

#: 18 months. Wide enough for a full deal cycle plus the prior year to compare it against.
DEFAULT_BACKFILL_DAYS = 540

#: What every connection used to get, and what connections created before this change keep
#: until an admin raises them (migration 0082 stamps it explicitly).
LEGACY_BACKFILL_DAYS = 60

#: A window of zero days would sync nothing while reporting success; ten years is past any
#: provider's practical retention and is the point where "backfill" means "export".
MIN_BACKFILL_DAYS = 1
MAX_BACKFILL_DAYS = 3650


@dataclass(frozen=True, slots=True)
class BackfillWindow:
    """How far back a first-ever sync reaches, and the two provider dialects for saying so."""

    days: int

    def __post_init__(self) -> None:
        if isinstance(self.days, bool) or not isinstance(self.days, int):
            raise ValueError(f"backfill_days must be an int, got {self.days!r}")
        if not MIN_BACKFILL_DAYS <= self.days <= MAX_BACKFILL_DAYS:
            raise ValueError(
                f"backfill_days must be between {MIN_BACKFILL_DAYS} and {MAX_BACKFILL_DAYS}, "
                f"got {self.days}")

    def gmail_query(self) -> str:
        """Gmail's search dialect for "no older than this window"."""
        return f"newer_than:{self.days}d"

    def since(self, now: datetime) -> datetime:
        """The earliest instant this window covers. `now` is a parameter so the unit stays pure
        and a test can pin the boundary instead of racing the wall clock."""
        return now - timedelta(days=self.days)


def backfill_window_for(connection: Connection) -> BackfillWindow:
    """The window THIS connection is configured for.

    Absent key → `DEFAULT_BACKFILL_DAYS`. A present value is validated and never silently
    ignored: a typo'd admin setting must fail loudly at connector construction rather than
    quietly restore the 60-day behaviour this unit exists to remove. Digit strings are accepted
    because a JSON settings form submits numbers as text.
    """
    value = (connection.config or {}).get(BACKFILL_DAYS_KEY)
    if value is None:
        return BackfillWindow(days=DEFAULT_BACKFILL_DAYS)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"connection {connection.connection_id}: {BACKFILL_DAYS_KEY}={value!r} is not a "
            "whole number of days")
    return BackfillWindow(days=value)


def with_backfill_days(connection: Connection, days: int) -> Connection:
    """A COPY of `connection` carrying a new window — the seam an admin console writes through.

    Returns a new model rather than mutating: the caller persists it with
    `ConnectionStore.add`, which upserts `capture_scope`. Validation happens here, so an
    out-of-range value is refused at the edit, not at the next sync.
    """
    BackfillWindow(days=days)                       # validate before we write it anywhere
    return connection.model_copy(
        update={"config": {**(connection.config or {}), BACKFILL_DAYS_KEY: days}})
