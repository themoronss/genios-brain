"""STEP-04 · no open card's subject is one of us — the receipt that holds the card to its contract.

    pytest tests/platform/test_no_card_is_about_us.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_no_card_is_about_us.py -q

`platform/receipts.py` (tree `yc2_w27_s04/M22.C6.L-logic.V2.U02`). Production carried *"Send Mr Rohit
Swerashi your traction metrics"* and an offer card naming `ceo@thegenios.com` and the founder as
"waiting longest" — cards whose subject was the tenant itself (`speedrun008/YC-II W27/` STEP-04 §8.2).
A card's subject is the counterparty, always. The receipt counts open cards whose
`business_subject` is one of us: the founder's full name, the company's name, an address of ours,
or a domain we declared. After STEP-04's repair it reads 0.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform.receipts import Receipt, receipts

CLAIM = "no open card's subject is one of us"
ORG = "org_card_about_us"


def _receipt(org: str | None = "org_x") -> Receipt:
    return next(r for r in receipts(org) if r.claim == CLAIM)


def test_the_receipt_exists_once_and_belongs_to_deliver():
    from genios_engine.platform.receipt_coverage import RECEIPT_PACKAGE

    assert sum(r.claim == CLAIM for r in receipts("org_x")) == 1
    assert RECEIPT_PACKAGE[CLAIM][0] == "deliver"


def test_one_card_about_us_fails_it():
    assert _receipt().expect(0) is True and _receipt().expect(1) is False


def test_it_asks_only_open_cards_and_is_scoped_to_the_tenant():
    sql = _receipt().sql
    for state in ("queued", "surfaced", "snoozed", "claimed", "delivered"):
        assert f"'{state}'" in sql
    assert ":org" in sql and ":org" not in _receipt(org=None).sql


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt needs real Postgres")
    from genios_engine.platform.db import get_engine

    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from cards where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email, first_name, last_name) values "
                       "(:o, 'GeniOS Labs', 'founder@example.test', 'Rohit', 'Swerashi')"), {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', 'ceo@thegenios.test', 'test'), (:o, 'domain', 'thegenios.test', 'test')"),
                  {"o": ORG})
        # The connected mailbox — a source the receipt's first cut did not read (M22.C6.L-logic.V2.U03).
        c.execute(text("insert into connections (connection_id, org_id, external_account_id) "
                       "values ('conn_card_about_us', :o, 'founder.mailbox@example.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from cards where org_id = :o"), {"o": ORG})
        c.execute(text("delete from connections where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(eng, card_id: str, subject: str, state: str = "queued") -> None:
    at = datetime.now(timezone.utc)
    with eng.begin() as c:
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
            "score, why, actions, artifact, state, expires_at, business_subject) values "
            "(:c, :s, :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), cast('[]' as jsonb), "
            "cast('{}' as jsonb), :st, :exp, :subj)"),
            {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "st": state,
             "exp": at + timedelta(days=3), "subj": subject})


def _count(eng) -> int:
    with eng.connect() as c:
        return int(c.execute(text(_receipt(org=ORG).sql), {"org": ORG}).scalar())


@pytest.mark.pg
@pytest.mark.parametrize("subject", ["Mr Rohit Swerashi", "GeniOS Labs", "founder@example.test",
                                     "ceo@thegenios.test", "invite@thegenios.test — awaiting reply",
                                     "founder.mailbox@example.test"])
def test_an_open_card_about_us_is_counted(engine, subject):
    _card(engine, "c_us", subject)
    _card(engine, "c_them", "Manik (Titan Capital)")
    assert _count(engine) == 1


@pytest.mark.pg
def test_a_closed_card_or_a_counterparty_is_not(engine):
    _card(engine, "c_gone", "Mr Rohit Swerashi", state="dismissed")
    _card(engine, "c_them", "Rohit Sharma")          # another Rohit is somebody else
    assert _count(engine) == 0
