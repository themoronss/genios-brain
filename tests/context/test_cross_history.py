"""Cross History — the correlator that was missing, and the two joins that would have been wrong.

    pytest tests/context/test_cross_history.py -q

Eight correlators are named and built and every one of them correlates observations that
COEXIST. None correlates a situation against its own past, so every customer's second time
through anything was treated as their first: in March a billing complaint was refunded and
`execution_outcomes` recorded `succeeded`; in September the same complaint from the same
customer opened generation 2 as a stranger.

HERMETIC, AGAINST A REAL SCHEMA. Every table below is created here and every query is the one
the module ships. The joins were wrong twice before this file existed — `execution_outcomes
.subject_ref` is not a node id, and `card_feedback_verdicts` has no `verdict` column — and both
mistakes would have matched NOTHING silently forever. A Postgres-only suite would have skipped,
and a skip is not a pass.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.correlation_history import (
    NO_PRIOR,
    UNKNOWN_OUTCOME,
    read_histories,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
ORG = "org1"

SCHEMA = (
    "create table context_correlations (correlation_id text primary key, org_id text, "
    "anchor_node_id text, anchor_type text, domain text, generation int, "
    "first_event_at timestamp, last_event_at timestamp)",
    "create table execution_outcomes (outcome_id text primary key, org_id text, "
    "subject_ref text, label text, closed_at timestamp)",
    "create table signals (signal_id text primary key, org_id text, subject_node_id text)",
    "create table cards (card_id text primary key, org_id text, signal_id text)",
    "create table card_feedback_verdicts (feedback_id text primary key, org_id text, "
    "card_id text, cause text, reason text, occurred_at timestamp)",
)


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for statement in SCHEMA:
            c.execute(text(statement))
        yield c


def generation(conn, anchor, gen, *, domain="sales", first, last):
    conn.execute(text(
        "insert into context_correlations values (:id, :o, :n, 'company', :d, :g, :f, :l)"),
        {"id": f"corr-{anchor}-{domain}-{gen}", "o": ORG, "n": anchor, "d": domain,
         "g": gen, "f": first, "l": last})


def one(histories, anchor):
    return next(h for h in histories if h.anchor_node_id == anchor)


# =============================================================================================
# The chain itself.
# =============================================================================================
def test_a_first_visit_says_so_rather_than_saying_nothing(conn):
    """A rule asking "is this a recurrence?" must get FALSE on a first visit, not UNKNOWN."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=3), last=NOW)

    h = one(read_histories(conn, ORG), "n1")

    assert h.times_seen == 1
    assert h.is_recurrence is False
    assert h.prior_outcome == NO_PRIOR
    assert h.days_since_prior is None


def test_the_third_time_is_counted_as_the_third(conn):
    """"This is the third time this quarter" — the sentence the engine could not say."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=100), last=NOW - timedelta(days=90))
    generation(conn, "n1", 3, first=NOW - timedelta(days=5), last=NOW)

    h = one(read_histories(conn, ORG), "n1")

    assert h.times_seen == 3
    assert h.is_recurrence is True
    assert h.days_since_prior == 85


def test_two_domains_on_one_anchor_are_two_histories(conn):
    """A customer who complains about billing and separately asks about a feature has not
    'been here twice' — those are different situations with the same subject."""
    generation(conn, "n1", 1, domain="sales", first=NOW - timedelta(days=9), last=NOW)
    generation(conn, "n1", 1, domain="admin", first=NOW - timedelta(days=9), last=NOW)

    histories = read_histories(conn, ORG)

    assert len(histories) == 2
    assert {h.domain for h in histories} == {"sales", "admin"}
    assert all(h.times_seen == 1 for h in histories)


def test_a_tenant_with_no_correlations_yields_nothing(conn):
    assert read_histories(conn, ORG) == ()


def test_another_tenants_generations_are_not_counted(conn):
    generation(conn, "n1", 1, first=NOW - timedelta(days=9), last=NOW)
    conn.execute(text(
        "insert into context_correlations values ('x', 'other-org', 'n1', 'company', "
        "'sales', 2, :f, :l)"), {"f": NOW - timedelta(days=2), "l": NOW})

    assert one(read_histories(conn, ORG), "n1").times_seen == 1


# =============================================================================================
# The join that would have matched nothing.
# =============================================================================================
def test_the_prior_outcome_is_reached_through_the_signal(conn):
    """`subject_ref` holds `signal:<id>`, never a node id — `deliver/pipeline.py:357`. Joining
    it straight to the anchor would have returned zero rows on every tenant, silently."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=2), last=NOW)
    conn.execute(text("insert into signals values ('sig1', :o, 'n1')"), {"o": ORG})
    conn.execute(text(
        "insert into execution_outcomes values ('out1', :o, 'signal:sig1', 'succeeded', :t)"),
        {"o": ORG, "t": NOW - timedelta(days=185)})

    assert one(read_histories(conn, ORG), "n1").prior_outcome == "succeeded"


def test_a_subject_ref_that_is_not_a_signal_is_not_matched_by_luck(conn):
    """`lifecycle/resolution.py` and `analytic/cohort.py` write other shapes into the same
    column. An execution opened by another route is not this anchor's history."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=2), last=NOW)
    conn.execute(text(
        "insert into execution_outcomes values ('out1', :o, 'cohort-draft:abc', 'succeeded', :t)"),
        {"o": ORG, "t": NOW - timedelta(days=185)})

    assert one(read_histories(conn, ORG), "n1").prior_outcome == UNKNOWN_OUTCOME


def test_a_recurrence_with_no_recorded_ending_is_unrecorded_not_first_time(conn):
    """THE TWO ABSENCES ARE DIFFERENT ANSWERS. `first_time` is a finding — we have never seen
    this. `unrecorded` is an admission — it happened and we do not know how it went. Collapsing
    them lets "no record of last time" read as "there was no last time"."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=2), last=NOW)

    h = one(read_histories(conn, ORG), "n1")

    assert h.prior_outcome == UNKNOWN_OUTCOME
    assert h.prior_outcome != NO_PRIOR


# =============================================================================================
# What the person did with the last card.
# =============================================================================================
def test_the_last_card_verdict_carries_its_reason(conn):
    """"We already told them this and they said it was not relevant" is the most useful thing
    this file can say. `wrong` alone loses why, and `bad_timing` invites a later retry where
    `not_relevant` does not."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=2), last=NOW)
    conn.execute(text("insert into signals values ('sig1', :o, 'n1')"), {"o": ORG})
    conn.execute(text("insert into cards values ('card1', :o, 'sig1')"), {"o": ORG})
    conn.execute(text(
        "insert into card_feedback_verdicts values ('fb1', :o, 'card1', 'wrong', "
        "'not_relevant', :t)"), {"o": ORG, "t": NOW - timedelta(days=180)})

    assert one(read_histories(conn, ORG), "n1").prior_card_verdict == "wrong:not_relevant"


def test_doing_it_themselves_is_not_recorded_as_wrong(conn):
    """The precision-denominator defect this branch already fixed once at the feedback layer:
    "they handled it" is not "we were wrong"."""
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=2), last=NOW)
    conn.execute(text("insert into signals values ('sig1', :o, 'n1')"), {"o": ORG})
    conn.execute(text("insert into cards values ('card1', :o, 'sig1')"), {"o": ORG})
    conn.execute(text(
        "insert into card_feedback_verdicts values ('fb1', :o, 'card1', 'do_it_myself', "
        "null, :t)"), {"o": ORG, "t": NOW - timedelta(days=180)})

    assert one(read_histories(conn, ORG), "n1").prior_card_verdict == "do_it_myself"


def test_the_most_recent_verdict_wins(conn):
    generation(conn, "n1", 1, first=NOW - timedelta(days=200), last=NOW - timedelta(days=190))
    generation(conn, "n1", 2, first=NOW - timedelta(days=2), last=NOW)
    conn.execute(text("insert into signals values ('sig1', :o, 'n1')"), {"o": ORG})
    conn.execute(text("insert into cards values ('card1', :o, 'sig1')"), {"o": ORG})
    for n, (cause, at) in enumerate((("wrong", 190), ("run_play", 150))):
        conn.execute(text(
            "insert into card_feedback_verdicts values (:i, :o, 'card1', :c, null, :t)"),
            {"i": f"fb{n}", "o": ORG, "c": cause, "t": NOW - timedelta(days=at)})

    assert one(read_histories(conn, ORG), "n1").prior_card_verdict == "run_play"


# =============================================================================================
# It survives the tables it enriches from being absent.
# =============================================================================================
def test_a_missing_enrichment_table_does_not_lose_the_chain():
    """The generation chain is the load-bearing half and stands on its own."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(SCHEMA[0]))          # correlations only — no signals, cards or outcomes
        c.execute(text(
            "insert into context_correlations values ('c1', :o, 'n1', 'company', 'sales', 2, "
            ":f, :l)"), {"o": ORG, "f": NOW - timedelta(days=2), "l": NOW})

        h = one(read_histories(c, ORG), "n1")

    assert h.times_seen == 2
    assert h.prior_outcome == UNKNOWN_OUTCOME


def test_the_live_sweep_hands_it_a_connection_and_not_the_engine():
    """The one call that ships. Every assertion above passes a Connection, and the module can only
    take one — it reads three statements and writes derived facts through the same handle. The
    live caller in `context/runner.py` passed `store.engine` instead, and on SQLAlchemy 2.x an
    Engine has no `.execute`, so the ninth correlator raised AttributeError on EVERY sweep. Its own
    `except Exception` boundary caught it and logged, so nothing failed and nothing was ever
    published: `derived.history.*` was absent from production while this file stayed green.

    A test that only ever constructs its own Connection cannot see that, which is why this one
    reads the call site instead of a return value."""
    import pathlib
    import re

    source = (pathlib.Path(__file__).resolve().parents[2]
              / "genios_engine" / "context" / "runner.py").read_text()
    call = re.search(r"publish_histories\(([^,]+),", source)
    assert call, "the live sweep no longer calls publish_histories — has the pass moved?"
    handle = call.group(1).strip()
    assert handle != "store.engine", (
        "runner.py is passing the Engine again; publish_histories needs an open Connection "
        "(`with store.engine.begin() as c`) or it raises AttributeError into a boundary that "
        "swallows it")
    assert "with store.engine.begin()" in source, (
        "the history pass writes derived facts, so it must run inside a committed transaction")
