"""STEP-14 · the health check says what the founder sees — one card per file, none replaced, what the contract refused,
every expert card on the app.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_cards.py -q

Tree `yc2_w27_s14` M43.C4.L-integration.V2.U05 (`scripts/pipeline_health`). Beside "cards reach the app" — which passes
while ONE card of the tenant does — four checks over what the founder sees:

  files with two open cards              0 — one file, one card (`migrations/0220`);
  file cards expired REPLACED            0 — a file's next decision versions its card, never replaces it;
  cards the contract refused, per rule   said (`card_refusals`, 0222) — never shown, so counted where they can be read;
  expert cards with no app surface       0 — an expert card is graded by its check, not a quote gate.

Read-only, like every check: the connection is rolled back here.
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "s14_health_cards"
NOW: datetime = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _clock():
    global NOW
    NOW = datetime.now(timezone.utc)


def _health():
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def conn():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    engine = create_engine(url)
    c = engine.connect()
    tx = c.begin()
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    c.execute(text("insert into orgs (id, name, email) values (:o, 'cards', 'h14@example.test')"), {"o": ORG})
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _card(c, card_id, *, file_id=None, state="queued", surfaces=("app", "ask", "api"), capability=None,
          subject_node="node_f"):
    c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, eval_time) "
                   "values (:s, :o, 'file_review', :n, 50, 'file_review', :t)"),
              {"s": f"sig_{card_id}", "o": ORG, "n": subject_node, "t": NOW})
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, state, "
        "expires_at, file_id, surfaces, capability_key) values (:c, :s, :o, 'prescriptive', 'high', 'h', 's', 50, :st, "
        ":exp, :f, :surf, :cap)"),
        {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "st": state, "exp": NOW + timedelta(days=3),
         "f": file_id, "surf": list(surfaces), "cap": capability})


def _check(conn, name):
    return getattr(_health(), name)(conn, ORG)


def test_each_new_check_is_in_the_run():
    h = _health()
    for name in ("check_one_file_one_card", "check_no_file_card_is_replaced", "check_what_the_card_contract_refused",
                 "check_every_expert_card_reaches_the_app"):
        assert getattr(h, name) in h.CHECKS, name


def test_files_with_two_open_cards(conn):
    assert _check(conn, "check_one_file_one_card").verdict == "NO DATA"
    _card(conn, "c1", file_id="node_f")
    _card(conn, "c0", file_id="node_f", state="expired")
    assert _check(conn, "check_one_file_one_card").verdict == "PASS"
    _card(conn, "c_old", capability="expert.file_review", subject_node="node_f")     # a card from before 0220
    got = _check(conn, "check_one_file_one_card")
    assert (got.verdict, got.measured) == ("FAIL", "1 file(s) with two open cards"), got.measured
    assert got.detail == ["node_f × 2"]


def test_file_cards_expired_replaced(conn):
    _card(conn, "c_legacy0", state="expired")                                      # no file: nothing to judge
    assert _check(conn, "check_no_file_card_is_replaced").verdict == "NO DATA"
    _card(conn, "c1", file_id="node_f", state="expired")
    conn.execute(text("insert into card_events (id, card_id, org_id, kind, cause) values "
                      "('cev_c', 'c1', :o, 'card.expired', 'rule_cleared')"), {"o": ORG})    # cleared: not this
    assert _check(conn, "check_no_file_card_is_replaced").verdict == "PASS"
    conn.execute(text("insert into card_events (id, card_id, org_id, kind, cause) values "
                      "('cev_r', 'c1', :o, 'card.expired', 'replaced')"), {"o": ORG})
    got = _check(conn, "check_no_file_card_is_replaced")
    assert got.verdict == "FAIL" and got.measured.startswith("1 file card(s)")
    _card(conn, "c_legacy", state="expired")                                       # no file: not this check's
    conn.execute(text("insert into card_events (id, card_id, org_id, kind, cause) values "
                      "('cev_l', 'c_legacy', :o, 'card.expired', 'replaced')"), {"o": ORG})
    assert _check(conn, "check_no_file_card_is_replaced").measured.startswith("1 file card(s)")


def test_what_the_card_contract_refused_is_said_per_rule(conn):
    assert _check(conn, "check_what_the_card_contract_refused").verdict == "NO DATA"
    from genios_engine.contracts.card_contract import Refusal
    from genios_engine.platform import card_refusals
    assert card_refusals.record(conn, org_id=ORG, writer=card_refusals.PIPELINE, ref="sig_1",
                                refusals=(Refusal("money", "payment"), Refusal("internal", "party.role")),
                                at=NOW) == 2
    card_refusals.record(conn, org_id=ORG, writer=card_refusals.PIPELINE, ref="sig_0",          # last week's: not
                         refusals=(Refusal("money", "fee"),), at=NOW - timedelta(days=8))
    with pytest.raises(ValueError):
        card_refusals.record(conn, org_id=ORG, writer="renderer", ref="sig_2", refusals=(Refusal("us", "x"),))
    card_refusals.record(conn, org_id=ORG, writer=card_refusals.TEAM, ref="discrepancy:d1",
                         refusals=(Refusal("internal", "party.role"),), at=NOW)
    got = _check(conn, "check_what_the_card_contract_refused")
    assert got.verdict == "PASS", "refused is the contract working: said, never a failure"
    assert got.measured == "3 refusal(s) in 7 days: internal 2, money 1"
    assert got.detail == ["pipeline sig_1 internal: party.role", "pipeline sig_1 money: payment",
                          "team discrepancy:d1 internal: party.role"]


def test_expert_cards_with_no_app_surface(conn):
    assert _check(conn, "check_every_expert_card_reaches_the_app").verdict == "NO DATA"
    _card(conn, "c_ok", file_id="node_a", capability="expert.file_review")
    _card(conn, "c_ok2", file_id="node_c", capability="expert.file_review", subject_node="node_c")
    _card(conn, "c_gone", file_id="node_d", capability="expert.file_review", subject_node="node_d", state="expired",
          surfaces=("ask", "api"))                                                   # ended: not live
    assert _check(conn, "check_every_expert_card_reaches_the_app").verdict == "PASS"
    _card(conn, "c_hidden", file_id="node_b", capability="expert.file_review", surfaces=("ask", "api"))
    _card(conn, "c_legacy_hidden", surfaces=("ask", "api"))                          # not an expert card
    got = _check(conn, "check_every_expert_card_reaches_the_app")
    assert (got.verdict, got.measured) == ("FAIL", "1 of 3 live expert card(s) carry no app surface")


def test_a_file_card_closed_by_design_is_no_replacement_and_an_old_one_is_history(conn):
    """⛔ STEP-14 fix (the crosscheck's finding 13, `yc2_w27_s14` M43.C4.L-integration.V2.U08): a question settled, a file
    that left coverage — each closes its card with its own cause, and the check counts only REPLACED (the version
    path's failure), over the last 7 days: one from before is history, not a red gate for ever."""
    from genios_engine.platform import card_lifecycle as cl
    assert {cl.QUESTION_SETTLED, cl.LEFT_COVERAGE} <= cl.CAUSES
    _card(conn, "c1", file_id="node_f", state="expired")
    for n, cause in enumerate((cl.QUESTION_SETTLED, cl.LEFT_COVERAGE)):
        conn.execute(text("insert into card_events (id, card_id, org_id, kind, cause) values "
                          "(:i, 'c1', :o, 'card.expired', :c)"), {"i": f"cev_d{n}", "o": ORG, "c": cause})
    assert _check(conn, "check_no_file_card_is_replaced").verdict == "PASS"
    # 0220 a month old (this connection is rolled back): the window, not the deploy, is what leaves the old one out.
    conn.execute(text("update schema_migrations set applied_at = now() - interval '30 days' "
                      "where filename = '0220_the_living_card.sql'"))
    conn.execute(text("insert into card_events (id, card_id, org_id, kind, cause, occurred_at) values "
                      "('cev_old', 'c1', :o, 'card.expired', 'replaced', now() - interval '8 days')"), {"o": ORG})
    got = _check(conn, "check_no_file_card_is_replaced")
    assert got.verdict == "PASS", got.measured
    conn.execute(text("insert into card_events (id, card_id, org_id, kind, cause) values "
                      "('cev_new', 'c1', :o, 'card.expired', 'replaced')"), {"o": ORG})
    assert _check(conn, "check_no_file_card_is_replaced").measured == "1 file card(s) expired replaced in 7 days"
