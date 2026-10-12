"""STEP-18 B11 · the behaviour brain holds THIS company's conduct — never the counterparty's reply time.

    GENIOS_TEST_DATABASE_URL=… pytest tests/packs/brains/test_their_latency_is_not_our_behaviour.py -q

`yc2_w27_s18` M49.C2.L-logic.V0.U03 (L2 Signals Qualification, Plane D — `packs/brains`).

⛔ WHAT WAS WRONG. `packs/brains/behavior_distill.BEHAVIOR_ELIGIBLE_METRICS` listed
`relationship.response_latency_hours` as *"how fast this company answers"*. It is measured from OUR
outbound to the counterparty's NEXT inbound (`context/analytic/sampler._reply_latencies_hours`) — how
fast THEY answer. The module's own rule is that the Behavior brain holds *what this company actually
does*, and that an inbound count is the world's conduct; the counterparty's reply time is too. A
pattern of it would have been published as a habit of the company. It leaves the eligible set,
declared with why (`THEIR_CONDUCT`); and an entry published from it before is named — never read as a
series gone dark.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.sampler import _reply_latencies_hours
from genios_engine.contracts.learning import LearningPolicy
from genios_engine.packs.brains import behavior_distill as bd

LATENCY = "relationship.response_latency_hours"
T0 = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def test_the_latency_is_measured_from_our_mail_to_their_reply():
    """The premise, measured on the sampler itself: out at 09:00, their reply at 14:00 — 5 hours."""
    timeline = [("out", T0), ("in", T0 + timedelta(hours=5))]
    assert _reply_latencies_hours(timeline, T0 - timedelta(days=1)) == [5]
    assert _reply_latencies_hours([("in", T0), ("out", T0 + timedelta(hours=2))],
                                  T0 - timedelta(days=1)) == [], "our own reply time is not in it"


def test_their_reply_time_is_not_this_companys_behaviour():
    assert LATENCY not in bd.BEHAVIOR_ELIGIBLE_METRICS
    assert LATENCY in bd.THEIR_CONDUCT and "counterparty" in bd.THEIR_CONDUCT[LATENCY].lower()
    assert f"derived.trend.{LATENCY}" not in bd.eligible_trend_fields()


def test_the_eligible_set_and_their_conduct_never_overlap():
    assert not set(bd.THEIR_CONDUCT) & bd.BEHAVIOR_ELIGIBLE_METRICS


# ── an entry published before is named, not left looking like a habit gone quiet ─────────────

@pytest.fixture()
def conn(live_db_url):
    """A real-Postgres transaction, rolled back. The scratch database, never the configured one."""
    if not live_db_url:
        pytest.skip("no database configured")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def test_a_published_entry_of_their_latency_is_named_not_their_series_gone_dark(conn):
    c, org = conn
    subject = bd.behavior_subject(LATENCY, "node_s18_ira")
    c.execute(text(
        "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
        "visibility_scope, visibility) values (:o, 'behavior', :s, 1, 'lo_s18', cast(:v as jsonb), "
        "'organization', cast('{}' as jsonb))"),
        {"o": org, "s": subject,
         "v": json.dumps({"metric": LATENCY, "direction": "rising", "active": True})})
    _proposals, refusals = bd.distill(c, org_id=org, policy=LearningPolicy(org_id=org, revision=1))
    ours = [r for r in refusals if r.detail == subject or r.subject_node_id == subject]
    assert [r.reason for r in ours] == ["metric_not_ours"], refusals
