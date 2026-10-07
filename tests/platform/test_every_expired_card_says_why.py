"""STEP-06 · every expired card says why — the receipt that holds the one writer to its promise.

    pytest tests/platform/test_every_expired_card_says_why.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_every_expired_card_says_why.py -q

`platform/receipts.py` (tree `yc2_w27_s06 · M24.C4.L-integration.V3.U01`). Nine of twelve places that
expired a card wrote nothing about it; History showed the card gone and no reason. From STEP-06 every
expiry goes through `platform/card_lifecycle`, which writes the event. This receipt counts the cards
created since STEP-06's migration that are `expired` with no ending event — 0 is the promise. Cards
that expired before it are not backfilled (`06` D24) and are not counted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform.receipts import Receipt, receipts

CLAIM = "every expired card says why"
ORG = "org_s06_expired_says_why"
NOW = datetime.now(timezone.utc)


def _receipt(org: str | None = "org_x") -> Receipt:
    return next(r for r in receipts(org) if r.claim == CLAIM)


def test_the_receipt_exists_once_and_belongs_to_the_writer():
    from genios_engine.platform.receipt_coverage import RECEIPT_PACKAGE
    assert sum(r.claim == CLAIM for r in receipts("org_x")) == 1
    assert RECEIPT_PACKAGE[CLAIM][0] == "platform"


def test_one_silent_expiry_fails_it_and_it_is_scoped_to_the_tenant():
    assert _receipt().expect(0) is True and _receipt().expect(1) is False
    assert ":org" in _receipt().sql and ":org" not in _receipt(org=None).sql


def test_the_kinds_it_accepts_are_the_writers():
    from genios_engine.platform.card_lifecycle import KINDS
    for kind in KINDS:
        assert f"'{kind}'" in _receipt().sql


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    _clear(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'f@exp.test')"),
                  {"o": ORG})
        applied = c.execute(text("select applied_at from schema_migrations "
                                 "where filename = '0194_situation_outcomes.sql'")).scalar()
    assert applied is not None, "0194 is not recorded in schema_migrations"
    yield eng, applied
    _clear(eng)


def _clear(eng):
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(c, card_id, *, created):
    c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
                   "reason_code, eval_time) values (:s, :o, 'r1', 'n1', 50, 'rc', :t)"),
              {"s": f"sig_{card_id}", "o": ORG, "t": created})
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
        "score, why, actions, artifact, state, expires_at, created_at) values "
        "(:c, :s, :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), cast('[]' as jsonb), "
        "cast('{}' as jsonb), 'queued', :exp, :created)"),
        {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "exp": NOW + timedelta(days=3),
         "created": created})


def _count(eng):
    with eng.connect() as c:
        return c.execute(text(_receipt(ORG).sql), {"org": ORG}).scalar()


def test_a_card_expired_by_raw_sql_is_counted_and_one_from_the_writer_is_not(engine):
    from genios_engine.platform import card_lifecycle as cl
    eng, applied = engine
    with eng.begin() as c:
        _card(c, "c_raw", created=applied + timedelta(seconds=1))
        _card(c, "c_writer", created=applied + timedelta(seconds=1))
        _card(c, "c_before", created=applied - timedelta(days=30))
        c.execute(text("update cards set state = 'expired' where card_id in ('c_raw', 'c_before')"))
        cl.expire_cards(c, org_id=ORG, card_ids=["c_writer"], cause=cl.REPLACED)
    assert _count(eng) == 1          # c_raw — not c_writer (it says why), not c_before (D24)
