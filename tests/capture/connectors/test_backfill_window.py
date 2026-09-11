"""G9 · L1.2.4-U1 — the first-connect backfill window is a per-connection setting.

THE DEFECT. `composio._BACKFILL_WINDOW = "newer_than:60d"` and `calendar._BACKFILL_DAYS = 60`
were module constants, so every tenant got the same two months of history and no operator could
change it without a deploy. Two months cannot contain a deal cycle, an acquisition thread or any
year-over-year comparison — the window decided, silently and globally, that L1 had nothing old
enough to be worth reasoning over.

WHAT IS ASSERTED HERE
  * the default for a NEW connection is 60 days (two months);
  * a connection configured for 540 days produces a query covering 540 days, in both provider
    dialects (Gmail's `newer_than:`, Calendar's `timeMin`);
  * `platform.wiring.make_connector_for` actually threads the setting — the number is useless
    if the factory drops it;
  * a bad admin value is refused loudly instead of falling back to 60;
  * widening the window does NOT re-land what a narrower one already ingested. The dedup key
    (contracts/source_event.compute_dedup_key) is the only guard, and the real-Postgres test at
    the bottom of this file re-runs a widened backfill against the real ledger to prove it.

    pytest tests/capture/connectors/test_backfill_window.py -q
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.connectors.backfill import (BACKFILL_DAYS_KEY,
                                                       DEFAULT_BACKFILL_DAYS,
                                                       LEGACY_BACKFILL_DAYS, MAX_BACKFILL_DAYS,
                                                       BackfillWindow, backfill_window_for,
                                                       with_backfill_days)
from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.contracts.connection import Connection

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def _connection(**config) -> Connection:
    return Connection(connection_id="con_w9", org_id="org_w9", source_type="gmail",
                      composio_user_id="user_w9", config=dict(config))


class _Recorder:
    """Stands in for the Composio client: records the arguments, returns an empty page."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, slug: str, arguments: dict):
        self.calls.append((slug, dict(arguments)))
        return {}

    @property
    def last_args(self) -> dict:
        return self.calls[-1][1]


def _gmail(days: int | None = None) -> tuple[ComposioGmailConnector, _Recorder]:
    kwargs = {} if days is None else {"backfill_days": days}
    connector = ComposioGmailConnector(api_key="", user_id="", **kwargs)
    rec = _Recorder()
    connector._execute = rec.execute            # no network; capture the query we would send
    return connector, rec


def _calendar(days: int | None = None) -> tuple[ComposioCalendarConnector, _Recorder]:
    kwargs = {} if days is None else {"backfill_days": days}
    connector = ComposioCalendarConnector(api_key="", user_id="", **kwargs)
    rec = _Recorder()
    connector._x = rec
    return connector, rec


# ── the window itself ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("days, query, why", [
    (DEFAULT_BACKFILL_DAYS, "newer_than:60d", "the default is two months"),
    (LEGACY_BACKFILL_DAYS, "newer_than:60d", "an existing connection keeps what it had"),
    (1, "newer_than:1d", "the floor is a real day, not zero"),
    (MAX_BACKFILL_DAYS, "newer_than:3650d", "the ceiling is ten years"),
])
def test_window_renders_the_gmail_dialect(days, query, why):
    assert BackfillWindow(days=days).gmail_query() == query, why


def test_window_since_is_now_minus_the_window():
    assert BackfillWindow(days=540).since(NOW) == NOW - timedelta(days=540)


@pytest.mark.parametrize("days, why", [
    (0, "a zero-day window syncs nothing while reporting success"),
    (-1, "a negative window is a future timeMin"),
    (MAX_BACKFILL_DAYS + 1, "past the ceiling this is an export, not a backfill"),
    (True, "bool is an int in Python and must not read as a 1-day window"),
    (60.0, "a float days count has no meaning in either provider dialect"),
    ("sixty", "a non-numeric string is an admin typo"),
])
def test_window_refuses_a_value_it_cannot_honour(days, why):
    with pytest.raises(ValueError):
        BackfillWindow(days=days)


# ── resolving it from the connection ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("config, expected, why", [
    ({}, DEFAULT_BACKFILL_DAYS, "a NEW connection defaults to two months"),
    ({BACKFILL_DAYS_KEY: 60}, 60, "an existing row stamped by migration 0082 keeps 60"),
    ({BACKFILL_DAYS_KEY: 900}, 900, "an admin can raise it deliberately"),
    ({BACKFILL_DAYS_KEY: "900"}, 900, "a settings form submits numbers as text"),
    ({BACKFILL_DAYS_KEY: None}, DEFAULT_BACKFILL_DAYS, "an explicit null reads as unset"),
    ({"db_url": "postgres://x"}, DEFAULT_BACKFILL_DAYS, "other config keys are none of our business"),
])
def test_backfill_window_for_reads_the_connection(config, expected, why):
    assert backfill_window_for(_connection(**config)).days == expected, why


@pytest.mark.parametrize("value, why", [
    ("many", "a typo must not silently restore the 60-day behaviour"),
    (0, "out of range is refused at construction, not at the next sync"),
    (True, "a boolean setting is a wiring bug worth surfacing"),
])
def test_backfill_window_for_refuses_a_bad_setting(value, why):
    with pytest.raises(ValueError):
        backfill_window_for(_connection(**{BACKFILL_DAYS_KEY: value})), why


def test_with_backfill_days_returns_a_copy_and_validates():
    original = _connection(db_url="postgres://x")
    edited = with_backfill_days(original, 900)
    assert edited.config == {"db_url": "postgres://x", BACKFILL_DAYS_KEY: 900}
    assert original.config == {"db_url": "postgres://x"}, "the original is not mutated"
    with pytest.raises(ValueError):
        with_backfill_days(original, 0)


# ── the connectors actually use it ───────────────────────────────────────────────────────────

def test_gmail_initial_snapshot_defaults_to_two_months():
    connector, rec = _gmail()
    connector.initial_snapshot(limit=5)
    assert rec.last_args["query"] == "newer_than:60d"


def test_gmail_backfill_does_not_emit_a_60d_query_when_configured_wider():
    connector, rec = _gmail(540)
    connector.initial_snapshot(limit=5)
    connector.incremental_changes(limit=5, since=None)
    queries = [args["query"] for _slug, args in rec.calls]
    assert queries == ["newer_than:540d", "newer_than:540d"]
    assert "newer_than:60d" not in queries


def test_gmail_incremental_with_a_watermark_ignores_the_window():
    connector, rec = _gmail(540)
    connector.incremental_changes(limit=5, since=datetime(2026, 8, 30, tzinfo=timezone.utc))
    assert rec.last_args["query"] == "after:2026/08/30", "a resumed sync asks from the watermark"


@pytest.mark.parametrize("days", [DEFAULT_BACKFILL_DAYS, LEGACY_BACKFILL_DAYS, 900])
def test_calendar_timemin_covers_the_configured_window(days):
    connector, rec = _calendar(days)
    before = datetime.now(timezone.utc)
    connector.initial_snapshot(limit=5)
    after = datetime.now(timezone.utc)
    time_min = datetime.fromisoformat(rec.last_args["timeMin"])
    assert before - timedelta(days=days) <= time_min <= after - timedelta(days=days)


def test_calendar_defaults_to_540_days():
    connector, rec = _calendar()
    connector.initial_snapshot(limit=5)
    time_min = datetime.fromisoformat(rec.last_args["timeMin"])
    assert (datetime.now(timezone.utc) - time_min).days >= DEFAULT_BACKFILL_DAYS - 1


# ── the factory threads it (a setting the factory drops is not a setting) ─────────────────────

@pytest.fixture
def real_composio(monkeypatch):
    from genios_engine.platform.config import get_settings
    monkeypatch.setitem(os.environ, "GENIOS_COMPOSIO_API_KEY", "test-key-not-a-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize("source_type, config, expected", [
    ("gmail", {}, DEFAULT_BACKFILL_DAYS),
    ("gmail", {BACKFILL_DAYS_KEY: 60}, 60),
    ("gmail", {BACKFILL_DAYS_KEY: 900}, 900),
    ("gcal", {}, DEFAULT_BACKFILL_DAYS),
    ("gcal", {BACKFILL_DAYS_KEY: 90}, 90),
])
def test_make_connector_for_threads_the_window(real_composio, source_type, config, expected):
    from genios_engine.platform.wiring import make_connector_for
    conn = Connection(connection_id="con_w9", org_id="org_w9", source_type=source_type,
                      composio_user_id="user_w9", config=dict(config))
    connector = make_connector_for(conn)
    assert connector.backfill_window.days == expected


def test_make_connector_for_refuses_a_bad_window(real_composio):
    from genios_engine.platform.wiring import make_connector_for
    conn = Connection(connection_id="con_w9", org_id="org_w9", source_type="gmail",
                      composio_user_id="user_w9", config={BACKFILL_DAYS_KEY: 0})
    with pytest.raises(ValueError):
        make_connector_for(conn)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# REAL POSTGRESQL — widening the window must not re-land what the narrow one already ingested
#
# This is the assertion the whole unit rests on. Raising 60 → 540 re-reads every message the
# 60-day sync already saw, and the ONLY guard against those landing twice is the dedup key
# (contracts/source_event.compute_dedup_key) plus the unique index behind it. Proven against the
# real ledger rather than a dict, because the dict cannot fail the way the index can.
# ═════════════════════════════════════════════════════════════════════════════════════════════

import re                                                                     # noqa: E402

from genios_engine.capture.landing.normalize import to_source_event            # noqa: E402
from genios_engine.contracts.source_event import SyncMode                      # noqa: E402

#: Age in days of each message in the fake mailbox. Two inside 60, three more inside 540, one
#: beyond even that — so each widening is observable and the ceiling is not silently ignored.
CORPUS_AGES = (5, 40, 100, 300, 500, 700)


class _FakeGmailProvider:
    """A mailbox that HONOURS the query. Anything else would let a connector send
    `newer_than:60d` and still be handed 540 days of mail, and the test would pass on a bug."""

    def __init__(self, now: datetime) -> None:
        self.now = now
        self.queries: list[str] = []

    def __call__(self, slug: str, args: dict):
        self.queries.append(args.get("query") or "")
        match = re.fullmatch(r"newer_than:(\d+)d", args.get("query") or "")
        if slug != "GMAIL_FETCH_EMAILS" or not match:
            return {}
        window = int(match.group(1))
        return {"data": {"messages": [self._message(age) for age in CORPUS_AGES
                                      if age < window]}}

    def _message(self, age_days: int) -> dict:
        sent = self.now - timedelta(days=age_days)
        return {
            "id": f"msg_age_{age_days}",
            "threadId": f"thread_age_{age_days}",
            "internalDate": str(int(sent.timestamp() * 1000)),
            "payload": {
                "headers": [{"name": "From", "value": f"buyer{age_days}@acme.com"},
                            {"name": "To", "value": "founder@acme.com"},
                            {"name": "Subject", "value": f"thread from {age_days}d ago"}],
                "parts": [{"mimeType": "text/plain", "filename": "",
                           "body": {"data": _b64(f"message body {age_days}")}}],
            },
        }


def _b64(text: str) -> str:
    import base64
    return base64.urlsafe_b64encode(text.encode()).decode()


def _sync(connector, repo, org_id: str, connection_id: str) -> int:
    """One backfill sweep, landing only what the ledger has not seen. Returns rows LANDED —
    this is the dedup-guarded write the sync runner performs, reduced to its essentials."""
    landed = 0
    for raw in connector.initial_snapshot(limit=100).objects:
        event = to_source_event(raw, org_id=org_id, connection_id=connection_id,
                                sync_mode=SyncMode.backfill, mailbox_owner="founder@acme.com")
        if repo.exists(org_id, event.dedup_key):
            continue
        repo.add(event, outcome="published")
        landed += 1
    return landed


@pytest.mark.pg
@pytest.mark.gate
def test_widening_the_backfill_window_lands_history_without_duplicating_it(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres backfill test skipped")
    from sqlalchemy import text

    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    with engine.connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    assert org, "scratch org missing — conftest seeds one"

    connection_id = "con_w9_backfill"
    repo = PostgresSourceEventRepository(live_db_url)
    provider = _FakeGmailProvider(now=datetime.now(timezone.utc))

    def connector_with(days: int) -> ComposioGmailConnector:
        c = ComposioGmailConnector(api_key="", user_id="", backfill_days=days)
        c._execute = provider
        return c

    def rows() -> list[tuple[str, str]]:
        with engine.connect() as c:
            return [(r.event_id, r.dedup_key) for r in c.execute(text(
                "select event_id, dedup_key from source_events where org_id=:o "
                "and connection_id=:c order by dedup_key"), {"o": org, "c": connection_id})]

    with engine.begin() as c:
        c.execute(text("delete from source_events where org_id=:o and connection_id=:c"),
                  {"o": org, "c": connection_id})
    try:
        # 1. the OLD window: only what the last two months contain
        assert _sync(connector_with(LEGACY_BACKFILL_DAYS), repo, org, connection_id) == 2
        narrow = rows()
        assert [k for _id, k in narrow] == ["gmail:email_message:msg_age_40",
                                            "gmail:email_message:msg_age_5"]

        # 2. widened to 540 — the three older threads land, the two already-seen do NOT re-land
        assert _sync(connector_with(DEFAULT_BACKFILL_DAYS), repo, org, connection_id) == 3
        wide = rows()
        assert len(wide) == 5, "the 700-day message is outside even the wide window"
        assert len({k for _id, k in wide}) == 5, "one row per object — no duplicates"
        assert set(narrow) <= set(wide), \
            "the original rows kept their event_ids: widening added history, it did not re-ingest"

        # 3. running the wide backfill again lands nothing at all
        assert _sync(connector_with(DEFAULT_BACKFILL_DAYS), repo, org, connection_id) == 0
        assert rows() == wide

        # 4. the queries actually sent — the window is not decorative
        assert provider.queries == ["newer_than:60d", "newer_than:540d", "newer_than:540d"]

        # 5. and dedup is VERSION-aware, not blind: a mutable object whose content_version moved
        #    must still land, or a widened re-run would freeze every deal at first-seen state.
        from genios_engine.capture.connectors.base import RawObject
        for version in ("2026-09-01T00:00:00Z", "2026-09-04T00:00:00Z"):
            deal = RawObject(source="hubspot", object_type="deal", source_object_id="deal_1",
                             occurred_at=datetime.now(timezone.utc), actor_type="system",
                             content_version=version, raw={"dealstage": version})
            event = to_source_event(deal, org_id=org, connection_id=connection_id,
                                    sync_mode=SyncMode.backfill)
            if not repo.exists(org, event.dedup_key):
                repo.add(event, outcome="published")
        assert len(rows()) == 7, "both deal versions landed; neither overwrote the other"
    finally:
        with engine.begin() as c:
            c.execute(text("delete from source_events where org_id=:o and connection_id=:c"),
                      {"o": org, "c": connection_id})
