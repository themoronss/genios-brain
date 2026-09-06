"""L1.3.8-U3 against a REAL Postgres — because the interesting half is the SQL.

`plan_recapture` is proved hermetically in `test_recapture.py`; nothing there executes the
statement that decides whether a MUT-01 park has a later capture, or the two updates that settle
a park. A correlated `exists` over `source_events`, `= any(:codes)` against a text column, and an
`update … set visibility_principals = :principals` against a `text[]` column are all things that
type-check in Python and fail in the database, which is exactly where this component runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.parked.recapture import (STATUS_PENDING, STATUS_RECOVERED,
                                                    STATUS_SUPERSEDED, drain_recapture)
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_l1_recapture_pg"
NOW = datetime(2026, 3, 11, 10, 30, tzinfo=timezone.utc)
_TABLES = ("prepared_content", "raw_payloads", "parked_events", "source_events")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres recapture tests skipped")
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


def _seed_org(eng, org_id: str = ORG) -> None:
    """Required columns are DISCOVERED rather than listed, so a later migration adding a
    not-null column turns this into a passing test instead of a skip or a hard failure."""
    with eng.begin() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": org_id}).scalar():
            return
        required = c.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, placeholders, values = ["id"], [":id"], {"id": org_id}
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


def _event(eng, *, event_id: str, source: str, object_type: str, source_object_id: str,
           outcome: str, captured_at: datetime, actor_email: str | None = "priya@acme.test",
           recipients: list[str] | None = None) -> None:
    with eng.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, recipients) "
            "values (:e, :o, 'conn_1', :src, :ot, :soid, :dedup, cast(:actor as jsonb), :at, "
            ":at, :outcome, :rcpt)"),
            {"e": event_id, "o": ORG, "src": source, "ot": object_type,
             "soid": source_object_id, "dedup": f"dedup_{event_id}",
             "actor": '{"type": "external_contact", "email": "%s"}' % (actor_email or ""),
             "at": captured_at, "outcome": outcome,
             "rcpt": recipients if recipients is not None else ["founder@genios.test"]})


def _park(eng, *, event_id: str, reason: str, source: str,
          parked_at: datetime | None = None) -> None:
    with eng.begin() as c:
        c.execute(text(
            "insert into parked_events (event_id, org_id, source, reason_code, stage, status, "
            "created_at) values (:e, :o, :src, :r, 'gate', 'pending', :at)"),
            {"e": event_id, "o": ORG, "src": source, "r": reason,
             "at": parked_at or (NOW - timedelta(days=5))})


def _park_status(eng, event_id: str) -> str | None:
    with eng.connect() as c:
        return c.execute(text("select status from parked_events where event_id=:e"),
                         {"e": event_id}).scalar()


def _event_row(eng, event_id: str):
    with eng.connect() as c:
        return c.execute(text(
            "select outcome, visibility_scope, visibility_principals, visibility_derived_from "
            "from source_events where event_id=:e"), {"e": event_id}).first()


def test_a_rederivable_visibility_park_is_stamped_and_released(engine):
    _event(engine, event_id="evt_vis", source="gmail", object_type="email_message",
           source_object_id="msg_1", outcome="parked", captured_at=NOW - timedelta(days=5))
    _park(engine, event_id="evt_vis", reason="visibility_unknown", source="gmail")

    report = drain_recapture(engine, eval_time=NOW, org_id=ORG)

    assert report.rederived == 1 and report.still_blocked == 0, report
    row = _event_row(engine, "evt_vis")
    assert row.outcome == "emitted"
    assert row.visibility_scope == "participants"
    assert set(row.visibility_principals) == {"priya@acme.test", "founder@genios.test"}
    assert row.visibility_derived_from == "connector:gmail:participants"
    assert _park_status(engine, "evt_vis") == STATUS_RECOVERED


def test_a_source_no_rule_covers_is_left_exactly_as_it_was(engine):
    """The negative case, against the real row: nothing written, nothing published."""
    _event(engine, event_id="evt_blind", source="a_source_no_registry_knows",
           object_type="record", source_object_id="rec_1", outcome="parked",
           captured_at=NOW - timedelta(days=5))
    _park(engine, event_id="evt_blind", reason="visibility_unknown",
          source="a_source_no_registry_knows")

    report = drain_recapture(engine, eval_time=NOW, org_id=ORG)

    assert report.still_blocked == 1 and report.rederived == 0, report
    row = _event_row(engine, "evt_blind")
    assert row.outcome == "parked"
    assert row.visibility_scope is None
    assert _park_status(engine, "evt_blind") == STATUS_PENDING


def test_a_mutable_park_with_a_later_emitted_capture_is_superseded(engine):
    """The correlated `exists` — the whole reason this file needs a server."""
    _event(engine, event_id="evt_deal_old", source="hubspot", object_type="deal",
           source_object_id="deal_77", outcome="parked", captured_at=NOW - timedelta(days=5))
    _event(engine, event_id="evt_deal_new", source="hubspot", object_type="deal",
           source_object_id="deal_77", outcome="emitted", captured_at=NOW - timedelta(days=1))
    _park(engine, event_id="evt_deal_old", reason="MUT-01", source="hubspot")

    report = drain_recapture(engine, eval_time=NOW, org_id=ORG)

    assert report.superseded == 1, report
    assert _park_status(engine, "evt_deal_old") == STATUS_SUPERSEDED
    # The stale copy is settled, NEVER republished.
    assert _event_row(engine, "evt_deal_old").outcome == "parked"


def test_a_mutable_park_with_no_later_capture_stays_pending(engine):
    _event(engine, event_id="evt_deal_only", source="hubspot", object_type="deal",
           source_object_id="deal_88", outcome="parked", captured_at=NOW - timedelta(days=5))
    _park(engine, event_id="evt_deal_only", reason="MUT-01", source="hubspot")

    report = drain_recapture(engine, eval_time=NOW, org_id=ORG)

    assert report.still_blocked == 1 and report.superseded == 0, report
    assert dict(report.blocked_by_reason) == {"MUT-01": 1}
    assert _park_status(engine, "evt_deal_only") == STATUS_PENDING


def test_a_later_capture_that_was_itself_parked_does_not_supersede(engine):
    """`outcome = 'emitted'` is load-bearing: a second versionless capture is the SAME failure
    again, and counting it as a supersession would settle a queue that never improved."""
    _event(engine, event_id="evt_x1", source="hubspot", object_type="deal",
           source_object_id="deal_99", outcome="parked", captured_at=NOW - timedelta(days=5))
    _event(engine, event_id="evt_x2", source="hubspot", object_type="deal",
           source_object_id="deal_99", outcome="parked", captured_at=NOW - timedelta(days=1))
    _park(engine, event_id="evt_x1", reason="MUT-01", source="hubspot")

    report = drain_recapture(engine, eval_time=NOW, org_id=ORG)
    assert report.superseded == 0 and report.still_blocked == 1, report


def test_another_tenants_later_capture_does_not_supersede_this_ones_park(engine):
    """Tenant isolation on the one join this unit makes."""
    other = f"{ORG}_neighbour"
    _seed_org(engine, other)
    _event(engine, event_id="evt_mine", source="hubspot", object_type="deal",
           source_object_id="deal_shared", outcome="parked", captured_at=NOW - timedelta(days=5))
    _park(engine, event_id="evt_mine", reason="MUT-01", source="hubspot")
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            "('evt_theirs', :o, 'c', 'hubspot', 'deal', 'deal_shared', 'd_theirs', "
            "cast('{}' as jsonb), :at, :at, 'emitted')"),
            {"o": other, "at": NOW - timedelta(days=1)})
    try:
        report = drain_recapture(engine, eval_time=NOW, org_id=ORG)
        assert report.superseded == 0, "another tenant's row settled this tenant's park"
        assert report.still_blocked == 1
    finally:
        with engine.begin() as c:
            c.execute(text("delete from source_events where org_id=:o"), {"o": other})
            c.execute(text("delete from orgs where id=:o"), {"o": other})


def test_a_park_whose_source_event_is_gone_is_not_claimed(engine):
    """The join is inner on purpose: a park with no row to re-derive from has nothing this unit
    can decide, and inventing a default audience for it is the failure, not the fix."""
    _park(engine, event_id="evt_orphan", reason="visibility_unknown", source="gmail")
    report = drain_recapture(engine, eval_time=NOW, org_id=ORG)
    assert report.examined == 0, report
    assert _park_status(engine, "evt_orphan") == STATUS_PENDING


def test_the_drain_is_idempotent(engine):
    """A settled park must not be re-settled on the next heartbeat — the claim filters on
    `status='pending'`, and a second cycle over the same data must examine nothing."""
    _event(engine, event_id="evt_vis2", source="gmail", object_type="email_message",
           source_object_id="msg_2", outcome="parked", captured_at=NOW - timedelta(days=5))
    _park(engine, event_id="evt_vis2", reason="visibility_unknown", source="gmail")

    first = drain_recapture(engine, eval_time=NOW, org_id=ORG)
    second = drain_recapture(engine, eval_time=NOW + timedelta(hours=1), org_id=ORG)
    assert first.rederived == 1
    assert second.examined == 0 and second.rederived == 0


def test_the_org_filter_scopes_the_claim(engine):
    _event(engine, event_id="evt_scope", source="gmail", object_type="email_message",
           source_object_id="msg_3", outcome="parked", captured_at=NOW - timedelta(days=5))
    _park(engine, event_id="evt_scope", reason="visibility_unknown", source="gmail")
    assert drain_recapture(engine, eval_time=NOW, org_id="org_that_does_not_exist").examined == 0
    assert _park_status(engine, "evt_scope") == STATUS_PENDING
    assert drain_recapture(engine, eval_time=NOW, org_id=ORG).examined == 1


def test_the_s1_report_metric_counts_the_backlog_this_drain_cannot_settle(engine):
    """The G2 surface. Before this metric existed the number below was unobservable."""
    import scripts.l1_s1_report as report_module
    _event(engine, event_id="evt_stuck", source="a_source_no_registry_knows",
           object_type="record", source_object_id="rec_9", outcome="parked",
           captured_at=NOW - timedelta(days=9))
    _park(engine, event_id="evt_stuck", reason="visibility_unknown",
          source="a_source_no_registry_knows", parked_at=NOW - timedelta(days=9))

    with engine.connect() as conn:
        metric = report_module.stuck_recapture_metric(conn, org_id=ORG, now=NOW)
    assert metric.observed == 1, metric
    assert metric.scanned == 1
    assert not metric.passed, "a nine-day-old held event must fail the gate, not pass it"
    assert any("visibility_unknown" in row for row in metric.sample), metric.sample
