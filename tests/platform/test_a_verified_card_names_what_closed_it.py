"""STEP-16 · every verified card names what closed it — the receipt, its witness, and the health check's rate.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/platform/test_a_verified_card_names_what_closed_it.py

Tree `yc2_w27_s16` M47.C3.L-integration.V2.U03 (`platform/receipts`; `scripts/pipeline_health`; `09` G6). A card
resolved `verified` with no evidence event is 0 to pass; the receipt is witnessed by the verified resolutions in
scope — none, and it is `NOT_EXERCISED`, never a pass; the deploy gate fails on one too, and prints the
verified-outcome rate with its n.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import card_lifecycle as L
from genios_engine.platform import receipts as R

ORG = "org_s16_verified_receipt"
CLAIM = "every verified card names what closed it"
AT = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


def _receipt(org: str | None = ORG) -> R.Receipt:
    [found] = [r for r in R.receipts(org) if r.claim == CLAIM]
    return found


def test_the_receipt_is_a_correctness_receipt_on_the_lifecycles_words():
    receipt = _receipt()
    assert receipt.expect(0) is True and receipt.expect(1) is False
    assert f"'{L.RESOLVED}'" in receipt.sql and f"'{L.VERIFIED}'" in receipt.sql and ":org" in receipt.sql


def test_it_is_witnessed_by_the_verified_resolutions_not_every_card_event():
    witness = R.witness_sql(_receipt(), ORG)
    assert witness == ("select count(*) from card_events where kind = 'card.resolved' and cause = 'verified' "
                       "and org_id = :org")
    assert (L.RESOLVED, L.VERIFIED) == ("card.resolved", "verified"), "the witness's words are the lifecycle's"


def test_it_names_the_package_it_guards():
    from genios_engine.platform.receipt_coverage import RECEIPT_PACKAGE
    assert RECEIPT_PACKAGE[CLAIM][0] == "platform"


# =================================================================================================
# on Postgres
# =================================================================================================
@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt reads Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'verified@s16.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(c, card_id: str, *, state: str = "queued", file: str = "node_a") -> None:
    c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                   "expires_at, state, file_id, output_lane, lane_reason, created_at) values (:c, :s, :o, "
                   "'prescriptive', 'standard', 'h', 's', 10, :exp, :st, :f, 'decision', 'a test lane', :at)"),
              {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "exp": AT + timedelta(days=7), "st": state, "f": file,
               "at": AT})


def _status(engine) -> str:
    [row] = [r for r in R.evaluate(engine, ORG) if r["claim"] == CLAIM]
    return row["status"]


@pytest.mark.pg
def test_no_verified_end_is_not_exercised(engine):
    with engine.begin() as c:
        _card(c, "k_open")
    assert _status(engine) == "NOT_EXERCISED", "nothing ended verified: the receipt judged nothing"


@pytest.mark.pg
def test_a_verified_end_naming_its_event_passes(engine):
    with engine.begin() as c:
        _card(c, "k_nda")
        L.resolve_cards(c, org_id=ORG, cause=L.VERIFIED, card_ids=["k_nda"], at=AT,
                        evidence={"event_id": "evt_signed_nda", "loop_id": "loop_nda", "basis": "answered"})
    assert _status(engine) == "PASS"


@pytest.mark.pg
@pytest.mark.parametrize("detail", [{}, {"event_id": ""}, {"event_id": "  ", "loop_id": "loop_nda"}])
def test_a_verified_end_naming_nothing_fails(engine, detail):
    with engine.begin() as c:
        _card(c, "k_nothing", state="resolved")
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
                       "values ('cev_nothing', 'k_nothing', :o, :k, :cause, 'system', cast(:d as jsonb), :at)"),
                  {"o": ORG, "k": L.RESOLVED, "cause": L.VERIFIED, "d": json.dumps(detail), "at": AT})
    assert _status(engine) == "FAIL"


@pytest.mark.pg
def test_another_resolution_is_no_part_of_it(engine):
    with engine.begin() as c:
        _card(c, "k_team", state="resolved")
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
                       "values ('cev_team', 'k_team', :o, :k, :cause, 'system', '{}'::jsonb, :at)"),
                  {"o": ORG, "k": L.RESOLVED, "cause": L.SITUATION_CLEARED, "at": AT})
    assert _status(engine) == "NOT_EXERCISED", "a cleared situation names no closing event, and needs none"


# =================================================================================================
# the deploy gate: fails on one, and prints the verified-outcome rate with its n
# =================================================================================================
@pytest.mark.pg
def test_the_health_check_prints_the_verified_outcome_rate(engine):
    from scripts import pipeline_health as ph
    with engine.begin() as c:
        _card(c, "k_nda")
        L.resolve_cards(c, org_id=ORG, cause=L.VERIFIED, card_ids=["k_nda"], at=AT,
                        evidence={"event_id": "evt_signed_nda", "loop_id": "loop_nda", "basis": "answered"})
        _card(c, "k_lapsed", state="queued", file="node_b")
        L.expire_cards(c, org_id=ORG, card_ids=["k_lapsed"], cause=L.LAPSED, kind=L.LAPSED_KIND)
    with engine.connect() as c:
        check = ph.check_every_verified_card_names_what_closed_it(c, ORG, now=AT + timedelta(days=1))
    assert check.verdict == ph.PASS, check.measured
    assert check.measured == ("0 verified card(s) naming nothing; verified outcomes over the last 30 days: 1 of 2 "
                              "decision(s) that ended")
    assert ph.check_every_verified_card_names_what_closed_it in ph.CHECKS


@pytest.mark.pg
def test_the_health_check_says_no_data_when_nothing_ended(engine):
    from scripts import pipeline_health as ph
    with engine.begin() as c:
        _card(c, "k_open")
    with engine.connect() as c:
        check = ph.check_every_verified_card_names_what_closed_it(c, ORG, now=AT + timedelta(days=1))
    assert check.verdict == ph.NO_DATA


@pytest.mark.pg
def test_the_health_check_fails_on_a_verified_end_naming_nothing(engine):
    from scripts import pipeline_health as ph
    with engine.begin() as c:
        _card(c, "k_nothing", state="resolved")
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
                       "values ('cev_nothing', 'k_nothing', :o, :k, :cause, 'system', '{}'::jsonb, :at)"),
                  {"o": ORG, "k": L.RESOLVED, "cause": L.VERIFIED, "at": AT})
    with engine.connect() as c:
        check = ph.check_every_verified_card_names_what_closed_it(c, ORG, now=AT + timedelta(days=1))
    assert check.verdict == ph.FAIL and check.measured.startswith("1 verified card(s) naming nothing")
