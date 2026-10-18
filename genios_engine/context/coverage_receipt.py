"""STEP-10 · what a file can say it checked — the coverage receipt, one line per mailbox.

`receipt_for` and `covers` (tree `yc2_w27_s10 · M29.C5.L-logic.V2.U03`).

WHAT WAS WRONG. A file said *"no reply"* with nothing beside it to say what had been looked at. On
the golden set no card carried a coverage line (`STEP-10` §8.1), per-signal coverage was NULL on
every signal (`STEP-18` B5), and the one coverage read there was spoke per SOURCE over an interval
its caller chose. So a pitch sent before the mailbox's window opened, or answered after its last
sync, read exactly like one nobody ever answered — an empty result over an unmeasured slice,
reported as a fact about somebody's silence.

WHAT IS TRUE NOW. `receipt_for` reads, per CONNECTED MAILBOX of the tenant: its connection, its
address when the row has one, the window it is set to sweep in days, the oldest instant that window
covers, when its last sync finished and whether that sync completed. `covers` is the one rule a
file may use before it says *"no reply since then"*: some mailbox's window reaches back that far,
and a sync that completed has looked since. A tenant with no mailbox gets an empty receipt, and an
empty receipt covers nothing.

A READ THAT FAILS LOSES THAT READ ALONE, AND SAYS SO (`M29.C5.L-logic.V2.U05`, STEP-10's crosscheck
X3). Every read runs in a SAVEPOINT and logs a warning naming the tenant: Postgres aborts the
transaction that holds a failed statement, and a bare `except` here left every later read on the
connection — the next mailbox's, the file's numbers — failing and swallowed the same way. The
answer stays the safe one: a mailbox that cannot be read vouches for nothing.

AS OF AN INSTANT, AND READ ONLY. `now` is a parameter, and no run that finished after it is seen, so
a replay asked at its case's instant reads what was true then. Nothing here writes: a receipt that
could would be asserting a sweep that never happened.

NO `Measured` HERE, deliberately: the window is a SETTING an admin chose, not something measured
over a tenant's history, and the rest are instants and a yes or no. What a mailbox READ in its
window — *"read 37 of about 465"* — is `capture/coverage/window.coverage_for_connection`'s sentence.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from genios_engine.capture.coverage.window import coverage_for_connection
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.coverage_receipt")

#: The sources whose connection is a MAILBOX — the four the semantic router reads as mail
#: (`capture/semantic/router.EMAIL_OBJECT_TYPES`). A calendar or a CRM can be connected and swept
#: end to end and still say nothing about whether somebody replied.
MAILBOX_SOURCES: frozenset[str] = frozenset({"gmail", "outlook", "imap", "inkbox"})


@dataclass(frozen=True, slots=True)
class MailboxReceipt:
    """What one mailbox lets a file say it checked, as of an instant."""

    connection_id: str
    #: The mailbox's own address when its `connections` row names one (`external_account_id`).
    #: Composio does not report it, so this is None on every live row until something writes it.
    address: str | None
    #: The window the mailbox is set to sweep (`capture_scope.backfill_days`). None: unreadable.
    window_days: int | None
    #: The oldest instant that window covers, measured back from the instant asked about.
    window_start: datetime | None
    #: When its last sync FINISHED, as of the instant asked about. None: it never has.
    last_finished_at: datetime | None
    #: Whether that last sync completed — the provider ran out of mail and nothing failed.
    last_completed: bool

    def __post_init__(self) -> None:
        if self.last_completed and self.last_finished_at is None:
            raise ValueError("a sync that completed has a finish")


def receipt_for(conn, org_id: str, *, connection_ids: Iterable[str] | None = None,
                now: datetime) -> list[MailboxReceipt]:
    """One receipt per CONNECTED mailbox of `org_id`, ordered by connection — or only the ones in
    `connection_ids` (a file's own mailboxes), where an empty selection selects none.

    A disconnected or paused mailbox is not on it: nothing is reading it now, so it can vouch for
    nothing that has happened since. Another tenant's connection never is.
    """
    rows = _optional(conn, f"its mailboxes, org={org_id}", lambda: conn.execute(text(
        "select connection_id, source_type from connections "
        " where org_id = :o and status = 'connected' order by connection_id"),
        {"o": org_id}).fetchall(), [])
    wanted = None if connection_ids is None else set(connection_ids)
    receipts: list[MailboxReceipt] = []
    for row in rows:
        if row.source_type not in MAILBOX_SOURCES or (
                wanted is not None and row.connection_id not in wanted):
            continue
        window = coverage_for_connection(conn, org_id=org_id, connection_id=row.connection_id,
                                         now=now)
        if window is None:
            continue
        finished, completed = _last_sync(conn, org_id, row.connection_id, now)
        receipts.append(MailboxReceipt(
            connection_id=row.connection_id, address=window.address,
            window_days=window.window_days, window_start=window.window_start,
            last_finished_at=finished, last_completed=completed))
    return receipts


def covers(receipts: Sequence[MailboxReceipt], since: datetime) -> bool:
    """May a file say *"no reply since `since`"*? Only when SOME mailbox's window reaches back to
    `since` AND its last sync completed — and finished no earlier than `since`: a sync that ended
    before the pitch went has read nothing that could be its answer. No receipt covers nothing.
    """
    return any(r.last_completed and r.window_start is not None
               and r.window_start <= since <= r.last_finished_at for r in receipts)


def _last_sync(conn, org_id: str, connection_id: str,
               now: datetime) -> tuple[datetime | None, bool]:
    """`(finished, completed)` for this connection's last sync as of `now`.

    ⛔ "THE LAST SYNC" IS THE LATEST FINISH INSTANT, NOT A ROW. A replay freezes every round of a
    backfill at its case's instant, and only the final round ran out of mail; one row picked from a
    tie would answer differently from run to run. So the instant completed when some run at it
    exhausted its cursor and no run at it failed. A run written before migration 0178 cannot say
    whether it exhausted anything, and silence is not completion.
    """
    row = _optional(conn, f"its last sync, org={org_id} connection={connection_id}",
                    lambda: conn.execute(text(
                        "select finished_at, bool_or(coalesce(cursor_exhausted, false)) as exhausted, "
                        "       bool_or(error is not null) as failed "
                        "  from l1_sync_runs "
                        " where org_id = :o and connection_id = :c and finished_at <= :now "
                        " group by finished_at order by finished_at desc limit 1"),
                        {"o": org_id, "c": connection_id, "now": now}).first(), None)
    if row is None:
        return None, False
    return row.finished_at, bool(row.exhausted) and not row.failed


def _optional(conn, what: str, read, default):
    """What `read` returns, or `default` when it fails — in a SAVEPOINT, so the transaction that
    holds it reads on, and in the log, so a receipt that vouches for nothing because it could not be
    read is not mistaken for a tenant that has no mailbox (`context/outreach_situations._optional`
    is the same guard, and says why it exists)."""
    try:
        with conn.begin_nested():
            return read()
    except Exception:                       # noqa: BLE001 — one read of a receipt, never the rest
        _log.warning("coverage receipt: %s unreadable; it vouches for nothing", what,
                     exc_info=True)
        return default


__all__ = ["MAILBOX_SOURCES", "MailboxReceipt", "covers", "receipt_for"]
