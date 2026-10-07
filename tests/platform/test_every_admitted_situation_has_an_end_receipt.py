"""STEP-06 · every admitted situation has a recorded end — the receipt over the compiled lane's ledger.

    pytest tests/platform/test_every_admitted_situation_has_an_end_receipt.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_every_admitted_situation_has_an_end_receipt.py -q

`platform/receipts.py` (tree `yc2_w27_s06 · M24.C4.L-integration.V3.U02`). What ended between admission
and a decision used to be a counter in one log line. From STEP-06 the compiled lane records every
admitted live candidate's end in `situation_outcomes` (0194); this receipt counts the active
situations whose latest admission — a day old, made since 0194 — is `admit` with no recorded end.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform.receipts import Receipt, receipts

CLAIM = "every admitted situation has a recorded end"
ORG = "org_s06_admitted_end"
NOW = datetime.now(timezone.utc)


def _receipt(org: str | None = "org_x") -> Receipt:
    return next(r for r in receipts(org) if r.claim == CLAIM)


def test_the_receipt_exists_once_and_belongs_to_reason():
    from genios_engine.platform.receipt_coverage import RECEIPT_PACKAGE
    assert sum(r.claim == CLAIM for r in receipts("org_x")) == 1
    assert RECEIPT_PACKAGE[CLAIM][0] == "reason"


def test_one_unrecorded_admission_fails_it_and_it_is_scoped_to_the_tenant():
    assert _receipt().expect(0) is True and _receipt().expect(1) is False
    assert ":org" in _receipt().sql and ":org" not in _receipt(org=None).sql


@pytest.fixture
def engine(live_db_url):
    """STEP-06 'deployed' a week ago on this scratch database, so a day-old admission can be counted;
    the migration's own timestamp is put back afterwards."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    _clear(eng)
    with eng.begin() as c:
        applied = c.execute(text("select applied_at from schema_migrations "
                                 "where filename = '0194_situation_outcomes.sql'")).scalar()
        assert applied is not None, "0194 is not recorded in schema_migrations"
        c.execute(text("update schema_migrations set applied_at = :t "
                       "where filename = '0194_situation_outcomes.sql'"),
                  {"t": NOW - timedelta(days=7)})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'f@adm.test')"),
                  {"o": ORG})
    yield eng
    _clear(eng)
    with eng.begin() as c:
        c.execute(text("update schema_migrations set applied_at = :t "
                       "where filename = '0194_situation_outcomes.sql'"), {"t": applied})


def _clear(eng):
    with eng.begin() as c:
        c.execute(text("delete from context_situations where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _situation(c, sid, *, admitted_at, outcome="admit", status="active", end=None):
    c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, "
                   "anchor_node_id, situation_type, domain, status) "
                   "values (:s, :o, :c, 'n1', 'awaiting_response', 'admin', :st)"),
              {"s": sid, "o": ORG, "c": f"corr_{sid}", "st": status})
    c.execute(text(
        "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
        "candidate_hash, outcome, candidate, schema_version, decided_at, reevaluate_after) "
        "values (:d, :o, :s, :h, :out, cast('{}' as jsonb), 'v1', :at, :retry)"),
        {"d": f"dec_{sid}", "o": ORG, "s": sid, "h": f"h_{sid}", "out": outcome,
         "at": admitted_at, "retry": admitted_at + timedelta(hours=1) if outcome == "hold" else None})
    if end:
        c.execute(text("insert into situation_outcomes (org_id, decision_id, situation_id, outcome, "
                       "recorded_at, last_seen_at) values (:o, :d, :s, :out, :at, :at)"),
                  {"o": ORG, "d": f"dec_{sid}", "s": sid, "out": end, "at": admitted_at})


def _count(eng):
    with eng.connect() as c:
        return c.execute(text(_receipt(ORG).sql), {"org": ORG}).scalar()


def test_only_an_admitted_live_situation_with_no_end_is_counted(engine):
    two_days = NOW - timedelta(days=2)
    with engine.begin() as c:
        _situation(c, "s_silent", admitted_at=two_days)                       # counted
        _situation(c, "s_ended", admitted_at=two_days, end="no_route")        # has its end
        _situation(c, "s_held", admitted_at=two_days, outcome="hold")         # the ledger says why
        _situation(c, "s_fresh", admitted_at=NOW - timedelta(hours=1))        # not a day old
        _situation(c, "s_gone", admitted_at=two_days, status="resolved")      # no longer active
        _situation(c, "s_before", admitted_at=NOW - timedelta(days=30))       # before STEP-06
    assert _count(engine) == 1
