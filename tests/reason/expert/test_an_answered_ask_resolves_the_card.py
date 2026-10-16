"""STEP-16 · a file decision that ends on an answered ask says so — its card RESOLVED `verified`, naming what closed it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_an_answered_ask_resolves_the_card.py

Tree `yc2_w27_s16` M47.C1.L-integration.V1.U02 (`reason/domain_shadow._clear_file_decision`; §8.4 item 8, `s16-F6`). When a
covered file's new review names no move, a card whose move named the ask it answers and whose ask closed ANSWERED
(`open_loops.closed_basis`, `closed_by_event` — written since 0167, read here first) is RESOLVED `verified` with that
event; one closed only REPLIED, or with no ask named, is cleared as today (`rule_cleared`), the closing event in its
detail. A file that asks instead leaves its card to the question.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import card_lifecycle as L
from genios_engine.reason import domain_shadow

pytestmark = pytest.mark.pg

ORG = "org_s16_answered_ask"
FILE = "node_pinecrest"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


class _Store:
    def __init__(self, engine):
        self.engine = engine


@pytest.fixture
def store(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the file's cards and its asks are Postgres's")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from open_loops where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
    yield _Store(eng)
    with eng.begin() as c:
        c.execute(text("delete from open_loops where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _decision(c, n: int, *, ask: str | None, file: str = FILE):
    """An open file decision and its card, whose words name the ask its move answers."""
    sig, card = f"sig_s16_{n}", f"card_s16_{n}"
    c.execute(text("insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, subject_node_id, score, "
                   "reason_code, eval_time, status) values (:s, :o, 'founder_office', '0.1.0', 'file_review', :f, 50, "
                   "'file_review', :at, 'open')"), {"s": sig, "o": ORG, "f": file, "at": AT})
    c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                   "expires_at, file_id, state) values (:c, :s, :o, 'prescriptive', 'standard', 'Send the signed NDA', "
                   "'s', 50, :exp, :f, 'queued')"), {"c": card, "s": sig, "o": ORG, "exp": AT + timedelta(days=7),
                                                     "f": file})
    c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) values "
                   "(:id, :c, :o, 'card.created', 'built', 'system', cast(:d as jsonb))"),
              {"id": f"cev_s16_{n}", "c": card, "o": ORG,
               "d": json.dumps({"version": 1, "words": {"headline": "Send the signed NDA", "situation": "s",
                                                        "ask": ask}})})
    return card


def _loop(c, loop_id: str, *, basis: str | None, closed: bool = True):
    c.execute(text("insert into open_loops (org_id, loop_id, subject_node_id, kind, thread_id, status, opened_at, "
                   "last_seen_at, opened_by_event, closed_at, closed_by_event, closed_basis) values (:o, :l, :f, "
                   "'document_request', 't_nda', :st, :opened, :opened, 'evt_ask', :closed_at, :ev, :basis)"),
              {"o": ORG, "l": loop_id, "f": FILE, "st": "closed" if closed else "open", "opened": AT - timedelta(days=3),
               "closed_at": AT - timedelta(hours=2) if closed else None, "ev": "evt_signed_nda" if closed else None,
               "basis": basis})


def _ended(store, card):
    with store.engine.connect() as c:
        row = c.execute(text("select state from cards where card_id = :c"), {"c": card}).scalar()
        events = [tuple(r) for r in c.execute(text(
            "select kind, cause, detail from card_events where card_id = :c and kind <> 'card.created' "
            "order by occurred_at, id"), {"c": card})]
    return row, events


def test_a_card_whose_ask_closed_answered_is_resolved_verified_with_what_closed_it(store):
    with store.engine.begin() as c:
        card = _decision(c, 1, ask="loop:loop_nda")
        _loop(c, "loop_nda", basis="answered")
    assert domain_shadow._clear_file_decision(store, ORG, FILE, "file_review") == 1
    state, events = _ended(store, card)
    assert state == "resolved"
    assert events == [(L.RESOLVED, L.VERIFIED, {"event_id": "evt_signed_nda", "loop_id": "loop_nda",
                                                "basis": "answered", "signal_id": "sig_s16_1"})]


def test_an_ask_closed_only_replied_is_cleared_with_its_closing_event_in_the_detail(store):
    with store.engine.begin() as c:
        card = _decision(c, 2, ask="loop:loop_nda")
        _loop(c, "loop_nda", basis="replied")
    domain_shadow._clear_file_decision(store, ORG, FILE, "file_review")
    state, events = _ended(store, card)
    assert state == "expired"
    assert events == [(L.EXPIRED, L.RULE_CLEARED, {"closed_by": {"event_id": "evt_signed_nda", "loop_id": "loop_nda",
                                                                "basis": "replied"}, "signal_id": "sig_s16_2"})]


@pytest.mark.parametrize("ask, opened", [(None, False), ("move:send the signed nda", False),
                                         ("loop:loop_nda", True)])
def test_a_move_that_named_no_ask_or_an_ask_still_open_is_cleared_as_today(store, ask, opened):
    with store.engine.begin() as c:
        card = _decision(c, 3, ask=ask)
        if opened:
            _loop(c, "loop_nda", basis=None, closed=False)
    domain_shadow._clear_file_decision(store, ORG, FILE, "file_review")
    state, events = _ended(store, card)
    assert state == "expired" and events == [(L.EXPIRED, L.RULE_CLEARED, {"signal_id": "sig_s16_3"})]


def test_a_file_that_asks_instead_leaves_its_card_to_the_question(store):
    with store.engine.begin() as c:
        card = _decision(c, 4, ask="loop:loop_nda")
        _loop(c, "loop_nda", basis="answered")
    domain_shadow._clear_file_decision(store, ORG, FILE, "file_review", cards=False)
    assert _ended(store, card) == ("queued", [])


def test_a_decision_with_no_card_is_cleared_and_nothing_else(store):
    with store.engine.begin() as c:
        c.execute(text("insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, subject_node_id, "
                       "score, reason_code, eval_time, status) values ('sig_s16_bare', :o, 'founder_office', '0.1.0', "
                       "'file_review', :f, 50, 'file_review', :at, 'open')"), {"o": ORG, "f": FILE, "at": AT})
    assert domain_shadow._clear_file_decision(store, ORG, FILE, "file_review") == 1
    with store.engine.connect() as c:
        assert c.execute(text("select status from signals where signal_id = 'sig_s16_bare'")).scalar() == "expired"


@pytest.mark.parametrize("status, event", [("open", "evt_signed_nda"), ("closed", None)],
                         ids=["reopened", "closed_by_nothing"])
def test_an_ask_reopened_or_closed_by_no_event_proves_nothing(store, status, event):
    """An ask asked again after it closed is open — its old closure kept on the row proves nothing now; and a closure
    no event made names nothing to verify by. Both cleared as today."""
    with store.engine.begin() as c:
        card = _decision(c, 5, ask="loop:loop_nda")
        c.execute(text("insert into open_loops (org_id, loop_id, subject_node_id, kind, thread_id, status, opened_at, "
                       "last_seen_at, opened_by_event, closed_at, closed_by_event, closed_basis) values (:o, 'loop_nda', "
                       ":f, 'document_request', 't_nda', :st, :opened, :opened, 'evt_ask', :opened, :ev, 'answered')"),
                  {"o": ORG, "f": FILE, "st": status, "opened": AT - timedelta(days=3), "ev": event})
    domain_shadow._clear_file_decision(store, ORG, FILE, "file_review")
    state, events = _ended(store, card)
    assert state == "expired" and events == [(L.EXPIRED, L.RULE_CLEARED, {"signal_id": "sig_s16_5"})]
