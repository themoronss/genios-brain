"""D2 · `drain_parked` and `parked_aging` against a real database.

Both functions run on every heartbeat (`api/routes.py`) and on the `/parked/aging` route, and
neither had a test. That is how DOC-07/08/09 got orphaned without anything going red: a park code
in neither drain class is COUNTED by `drain_parked` — it lands in `by_reason` — and then walked
past, and `parked_aging` reports it as ``class="terminal"``, which reads like a decision somebody
made rather than a code nobody wired. The whole failure is a discrepancy between two numbers in
the same dict, so the assertions here are on the classification, not on the totals.

Marked `pg`: these are SQL, and a fake would only prove the fake.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.parked.drain import (NEEDS_REFETCH, RE_ADJUDICABLE, drain_parked,
                                                parked_aging)
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_l1_drain_surfaces"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
_TABLES = ("raw_payloads", "parked_events", "source_events")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres drain tests skipped")
    eng = get_engine(live_db_url)
    _reset(eng)
    _seed_org(eng)
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    with eng.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": ORG})
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _seed_org(eng) -> None:
    """Required columns are discovered rather than listed, so a later NOT NULL migration does not
    silently turn this file into a skip."""
    with eng.begin() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": ORG}).scalar():
            return
        required = c.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, placeholders, values = ["id"], [":id"], {"id": ORG}
        for row in required:
            cols.append(row.column_name)
            placeholders.append(f":{row.column_name}")
            kind = row.data_type
            values[row.column_name] = ("2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                                       else 0 if ("int" in kind or "numeric" in kind)
                                       else False if kind == "boolean"
                                       else "{}" if kind in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                       f"({', '.join(placeholders)}) on conflict (id) do nothing"), values)


def _park(eng, *, event_id: str, reason: str, status: str = "pending",
          failure_kind: str | None = None, parked_at: datetime | None = None) -> None:
    parked_at = parked_at or (NOW - timedelta(days=5))
    with eng.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) "
            "values (:e, :o, 'conn_1', 'gmail', 'email_attachment', :soid, :dedup, "
            "cast('{}' as jsonb), :at, :at, 'parked')"),
            {"e": event_id, "o": ORG, "soid": f"m1::{event_id}", "dedup": f"d_{event_id}",
             "at": parked_at})
        c.execute(text(
            "insert into parked_events (event_id, org_id, source, reason_code, stage, status, "
            "refetch_failure_kind, created_at) "
            "values (:e, :o, 'gmail', :r, 'gate', :s, :k, :at)"),
            {"e": event_id, "o": ORG, "r": reason, "s": status, "k": failure_kind,
             "at": parked_at})


# ── the drain's own accounting ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason_code", sorted(NEEDS_REFETCH))
def test_every_refetch_code_is_accounted_as_needs_refetch_not_walked_past(engine, reason_code):
    """The discrepancy that hid D2: a code in neither class is counted into `by_reason` and then
    silently skipped, so `examined` moves and `needs_refetch` does not. One row per code."""
    _park(engine, event_id=f"evt_{reason_code}", reason=reason_code)
    out = drain_parked(engine, org_id=ORG, now=NOW)
    assert out["examined"] == 1
    assert out["needs_refetch"] == 1, f"{reason_code} was examined and then walked past"
    assert out["reinjected"] == 0, "a stub cannot be re-adjudicated; that is the whole class"


@pytest.mark.parametrize("reason_code", sorted(RE_ADJUDICABLE))
def test_every_re_adjudicable_code_is_dropped_when_its_payload_is_gone(engine, reason_code):
    """The other class, and its honest exit: with no retained payload there is nothing to read
    again, so it is settled rather than left pending forever."""
    _park(engine, event_id=f"evt_{reason_code}", reason=reason_code)
    out = drain_parked(engine, org_id=ORG, now=NOW)
    assert out["blocked_no_payload"] == 1
    with engine.connect() as c:
        assert c.execute(text("select status from parked_events where event_id=:e"),
                         {"e": f"evt_{reason_code}"}).scalar() == "dropped"


def test_an_old_park_is_reported_as_stale(engine):
    """`stale` is the age signal an operator alarms on — the number that says the queue is not
    moving, as distinct from the number that says it is large."""
    _park(engine, event_id="evt_old", reason="DOC-08", parked_at=NOW - timedelta(days=30))
    _park(engine, event_id="evt_new", reason="DOC-08", parked_at=NOW - timedelta(hours=2))
    out = drain_parked(engine, org_id=ORG, now=NOW)
    assert (out["examined"], out["stale"]) == (2, 1)


# ── the aging surface ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason_code, expected_class", (
    [(code, "needs_refetch") for code in sorted(NEEDS_REFETCH)]
    + [(code, "re_adjudicable") for code in sorted(RE_ADJUDICABLE)]
    + [("poison_quarantine", "terminal")]))
def test_the_aging_surface_names_the_class_that_owns_each_code(engine, reason_code,
                                                               expected_class):
    """``"terminal"`` must mean "no drain is supposed to take this", not "no drain was written".
    DOC-07/08/09 read as terminal for a year of this file's life."""
    _park(engine, event_id=f"evt_{reason_code}", reason=reason_code)
    rows = parked_aging(engine, org_id=ORG, now=NOW)
    assert [r["class"] for r in rows] == [expected_class]
    assert rows[0]["count"] == 1 and rows[0]["age_days"] == 5.0


def test_the_aging_surface_separates_dead_letters_by_what_stopped_them(engine):
    """The operator's question is never "how many dead letters"; it is "which of these do I fix by
    wiring an engine, and which by looking at the connection". The kind is the only column that
    answers it — `refetch_last_error` is truncated provider prose."""
    _park(engine, event_id="evt_cap", reason="DOC-06", status="dead_letter",
          failure_kind="capability")
    _park(engine, event_id="evt_gone", reason="DOC-06", status="dead_letter",
          failure_kind="permanent")
    _park(engine, event_id="evt_wait", reason="DOC-06")

    rows = parked_aging(engine, org_id=ORG, now=NOW)
    kinds = {r["failure_kind"]: (r["status"], r["count"]) for r in rows}
    assert kinds == {"capability": ("dead_letter", 1), "permanent": ("dead_letter", 1),
                     None: ("pending", 1)}
