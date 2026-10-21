"""A situation a person marked handled comes back when NEW evidence arrives — and only then.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_human_close_yields_to_new_evidence_pg.py -q

L3 audit, 21 Oct 2026. `SITUATION_STATUS_ON_CONFLICT` kept a human close FOREVER on every synthetic reading (the
support and outreach readings, documents, meeting touches, periods), so a first-reply card the founder marked
handled never returned when the customer wrote again — while `POST /situations/{id}/resolve` answers
`reopens_on_new_evidence: true`. Now a human close yields to a re-mint whose `last_seen_at` is evidence newer than
the close (later than `resolved_at`, earlier than the sweep's `computed_at`). The halves that must not move: the
same old evidence, a writer that stamps the sweep's own clock, a future meeting start, an unknown time, and a
STATEMENT close (the claim ledger's to undo) all keep the close.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.situations import SITUATION_STATUS_ON_CONFLICT, resolve_situation
from genios_engine.context.support_situations import _upsert

pytestmark = pytest.mark.pg
ORG = f"org_human_close_{uuid.uuid4().hex[:8]}"
CORR = "corr_firstreply_support_thread_x"


@pytest.fixture
def engine(pg_store):
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"), {"o": ORG, "e": f"{ORG}@x.test"})
    yield pg_store.engine
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _mint(engine, *, last_seen: datetime, now: datetime) -> None:
    """The shared state-reading writer (`support_situations._upsert`, outreach's too) re-minting the reading."""
    with engine.begin() as c:
        _upsert(c, org_id=ORG, corr=CORR, node_id="node_customer", stype="first_response_overdue",
                domain="support", now=now, coverage=100, missing=[], inputs={}, evidence=60, freshness=60,
                identity=100, first_seen=last_seen, last_seen=last_seen)


def _row(engine):
    with engine.connect() as c:
        return c.execute(text("select situation_id, status, resolved_by from context_situations "
                              "where org_id=:o and correlation_id=:c"), {"o": ORG, "c": CORR}).one()


def _closed_by_you(engine) -> datetime:
    """Mint, then mark it handled; returns the close's own instant (the database's clock)."""
    with engine.connect() as c:
        t = c.execute(text("select now()")).scalar()
    _mint(engine, last_seen=t - timedelta(days=2), now=t - timedelta(days=1))
    with engine.begin() as c:
        assert resolve_situation(c, org_id=ORG, situation_id=_row(engine).situation_id)
        return c.execute(text("select resolved_at from context_situations where org_id=:o and correlation_id=:c"),
                         {"o": ORG, "c": CORR}).scalar()


def test_new_evidence_after_the_close_brings_it_back(engine):
    closed = _closed_by_you(engine)
    _mint(engine, last_seen=closed + timedelta(minutes=10), now=closed + timedelta(hours=1))
    row = _row(engine)
    assert (row.status, row.resolved_by) == ("active", None), (
        "the customer wrote after you marked it handled and the card stayed hidden")


@pytest.mark.parametrize("case", ["same_old_evidence", "the_sweeps_own_clock", "a_future_meeting_start"])
def test_what_is_not_new_evidence_keeps_your_close(engine, case):
    closed = _closed_by_you(engine)
    later = closed + timedelta(hours=2)
    last_seen = {"same_old_evidence": closed - timedelta(days=2), "the_sweeps_own_clock": later,
                 "a_future_meeting_start": later + timedelta(days=3)}[case]
    _mint(engine, last_seen=last_seen, now=later)
    row = _row(engine)
    assert (row.status, row.resolved_by) == ("resolved", "human"), f"{case} reopened a card you handled"


def test_an_unknown_time_is_no_evidence(engine):
    """A writer with no time at all (NULL) — the clause's own NULL, which a CASE would read as "reopen"."""
    closed = _closed_by_you(engine)
    with engine.begin() as c:
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, situation_type, "
            "  domain, status, last_seen_at, computed_at) values ('sit_x', :o, :c, 'node_customer', "
            "  'first_response_overdue', 'support', 'active', null, :now) "
            "on conflict (org_id, correlation_id) do update set " + SITUATION_STATUS_ON_CONFLICT +
            "  last_seen_at = excluded.last_seen_at, computed_at = excluded.computed_at"),
            {"o": ORG, "c": CORR, "now": closed + timedelta(hours=1)})
    assert _row(engine).status == "resolved"


def test_a_statement_close_is_the_ledgers_to_undo(engine):
    closed = _closed_by_you(engine)
    with engine.begin() as c:
        c.execute(text("update context_situations set resolved_by='statement' where org_id=:o and correlation_id=:c"),
                  {"o": ORG, "c": CORR})
    _mint(engine, last_seen=closed + timedelta(minutes=10), now=closed + timedelta(hours=1))
    row = _row(engine)
    assert (row.status, row.resolved_by) == ("resolved", "statement")
