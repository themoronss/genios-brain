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
document is extracted once, ever) but not zero. So the default stays at two months
(`DEFAULT_BACKFILL_DAYS`) and an admin raises or lowers it per connection. It was 540 for a
while; a first Sync then walked 18 months of mail before Layer 2 ran at all — hours with an empty
graph — which is not what a user pressing Sync asked for.

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

#: Two months — what a first Sync pulls unless the connection says otherwise.
DEFAULT_BACKFILL_DAYS = 60

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


# ── GeniOS-011 S09.U1 · the window the founder picks is the window captured ─────────────────────
#
# THE DEFECT. The dashboard's Sources modal offers a "Historical backfill" — 30 days, 90 days,
# 6 months, 12 months — and PUTs it to `/api/org/{org}/integrations/{tool}/config`, which stored it
# in `integration_preferences.sync_settings.historical_backfill`. Nothing in capture read it: every
# connector reads `BACKFILL_DAYS_KEY` off the connection, sixty days unless an operator PATCHed it.
# A founder could pick "12 months" and get sixty days (audit `l1-resync-and-history-window`, the
# skeptic's correction). The parse lives here, beside the window it becomes, so the modal's
# vocabulary and `BackfillWindow`'s range rule cannot drift apart; `api/account_routes` writes the
# result through to the connections.

#: Where the Sources modal puts its choice inside `sync_settings` (dashboard
#: `sources-page.tsx` save), and the camelCase key the older Integrations page sends.
HISTORICAL_BACKFILL_KEY = "historical_backfill"
HISTORICAL_BACKFILL_LEGACY_KEY = "historicalBackfill"

#: The older Integrations page's labels. A closed table, not arithmetic: "12 months" is a year of
#: mail — 365 days, the window D16 recommends — never 12 × 30.
_MONTH_LABELS = {"1 month": 30, "3 months": 90, "6 months": 180, "12 months": 365}


def chosen_backfill_days(sync_settings) -> int | None:
    """The window, in days, the founder picked in the Sources modal — or `None` when no pick is
    present. `None` is not `DEFAULT_BACKFILL_DAYS`: a save that names no window must leave the
    connection's window as it is, never reset it.

    Accepted: the modal's ids (`"30d"`, `"90d"`, `"180d"`, `"365d"`, any `"<N>d"`), the older page's
    labels (`_MONTH_LABELS`), and a whole number of days. Anything else raises `ValueError` — the
    same loudness as `backfill_window_for`: a pick that cannot be honoured is refused at the save,
    not turned into sixty days at the next sync. The range is `BackfillWindow`'s own.
    """
    settings = sync_settings if isinstance(sync_settings, dict) else {}
    value = settings.get(HISTORICAL_BACKFILL_KEY)
    if value is None:
        value = settings.get(HISTORICAL_BACKFILL_LEGACY_KEY)
    if value is None:
        return None
    days = None
    if isinstance(value, int) and not isinstance(value, bool):
        days = value
    elif isinstance(value, str):
        label = " ".join(value.strip().lower().split())
        if label in _MONTH_LABELS:
            days = _MONTH_LABELS[label]
        elif label.endswith("d") and label[:-1].isdigit():
            days = int(label[:-1])
    if days is None:
        raise ValueError(f"{HISTORICAL_BACKFILL_KEY}={value!r} is not a window this engine reads "
                         "(30d, 90d, 180d, 365d, or a month label)")
    return BackfillWindow(days=days).days           # the range rule, at the save


# ── GeniOS-011 S09.U1 · the owner's history drain and the ingestion meter ──────────────────────
#
# `POST /connections/{id}/backfill` — the door STEP-08's resync lands the deleted mail through —
# never read the ingestion meter (`platform/quota`). That was a bypass nobody had decided and
# nobody could see. It is now decided, here, and the door logs it before the first page.
#
# WHY BYPASS, NOT RESERVE-AND-TRIM. The drain is owner-triggered and deliberate (its own docstring).
# Trimming it to the headroom would leave the resync's freed keys with no message (`--finish` then
# reports them "not listed"), and a TRUNCATED drain always restarts from the newest page, so a
# trimmed drain would never reach the old mail it exists for. What the drain lands DOES count
# toward the meter (`source_events.captured_at`), so a full meter afterwards stops the live sweep
# (`l1_quota_full`) — the line says so, with the numbers, so that is never discovered later.
DRAIN_QUOTA_DECISION = "bypass"


def drain_quota_decision(connection: Connection, meter: dict | None) -> str:
    """The one log line that records the drain's decision about the meter. PURE: the caller reads
    the meter (`platform/quota.sync_status`); `None` means it could not be read, said as such —
    never a fabricated zero."""
    try:
        window = f"{backfill_window_for(connection).days}d"
    except ValueError:
        window = "unreadable"
    if meter is None:
        numbers = "meter unread"
    else:
        numbers = (f"used={meter.get('used')} limit={meter.get('limit')} "
                   f"remaining={meter.get('remaining')}"
                   + (" exhausted" if meter.get("exhausted") else ""))
    return (f"backfill drain org={connection.org_id} conn={connection.connection_id} "
            f"window={window} quota={DRAIN_QUOTA_DECISION} ({numbers}): an owner-triggered history "
            "drain is never trimmed to the ingestion meter; what it lands counts toward the meter, "
            "so a full meter afterwards stops the live sweep until the period rolls or the plan grows")
