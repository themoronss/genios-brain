"""STEP-16 · how each decision of a file ended — verified, replied, taken, called wrong, lapsed, replaced, cleared.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_how_a_file_decision_ended.py

Tree `yc2_w27_s16` M47.C1.L-data.V2.U03 (`context/file_outcomes`; §8.4 item 8). Read back from what is already written —
the card's ending event, the button pressed, your verdict, the ask's closure a cleared decision carries — never a table
of its own: verified (by which event), only replied (by which), taken by you, called wrong (and why), lapsed,
dismissed, replaced, cleared, open, and an end with no cause written said as such. Rates by kind of work and by lane.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import file_outcomes as O

ORG = "org_s16_file_outcomes"
FILE = "node_pinecrest"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the endings are read from Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(c, card_id, *, state, file=FILE, lane="decision", hours=0, events=(), verdict=None):
    c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                   "expires_at, state, file_id, output_lane, lane_reason, created_at) values (:c, :s, :o, 'prescriptive', "
                   "'standard', 'h', 's', 10, :exp, :st, :f, :lane, 'a test lane', :at)"),
              {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "exp": AT + timedelta(days=7), "st": state, "f": file,
               "lane": lane, "at": AT + timedelta(hours=hours)})
    for i, (kind, cause, detail) in enumerate(events):
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
                       "values (:id, :c, :o, :k, :cause, 'system', cast(:d as jsonb), :at)"),
                  {"id": f"cev_{card_id}_{i}", "c": card_id, "o": ORG, "k": kind, "cause": cause,
                   "d": json.dumps(detail or {}), "at": AT + timedelta(hours=hours + 1 + i)})
    if verdict:
        c.execute(text("insert into card_feedback_verdicts (feedback_id, org_id, card_id, pack_id, pack_version, "
                       "authority_pack_revision, capability_id, capability_version, rule_id, cause, reason, detail, "
                       "actor_id, occurred_at) values (:fb, :o, :c, 'founder_office', '0.1.0', 1, 'expert.file_review', "
                       "'1.0.0', 'file_review', :cause, :reason, '{}'::jsonb, 'founder', :at)"),
                  {"fb": f"fb_{card_id}", "o": ORG, "c": card_id, "cause": verdict[0], "reason": verdict[1],
                   "at": AT + timedelta(hours=hours + 5)})


@pytest.mark.pg
def test_each_card_of_a_file_says_how_it_ended(engine):
    with engine.begin() as c:
        _card(c, "k_verified", state="resolved", hours=0, events=[
            ("card.resolved", "verified", {"event_id": "evt_signed_nda", "loop_id": "loop_nda", "basis": "answered"})])
        _card(c, "k_replied", state="expired", hours=1, events=[
            ("card.expired", "rule_cleared", {"closed_by": {"event_id": "evt_thanks", "loop_id": "loop_x",
                                                            "basis": "replied"}})])
        _card(c, "k_taken", state="acted", hours=2, events=[("human.card_action", "run_play", {})],
              verdict=("run_play", None))
        _card(c, "k_wrong", state="acted", hours=3, events=[("human.card_action", "wrong", {"reason": "bad_timing"})],
              verdict=("wrong", "bad_timing"))
        _card(c, "k_lapsed", state="expired", hours=4, events=[("window.lapsed", "expired", {})])
        _card(c, "k_dismissed", state="expired", hours=5, events=[("card.dismissed", "extension", {})])
        _card(c, "k_replaced", state="expired", hours=6, events=[("card.expired", "replaced", {})])
        _card(c, "k_cleared", state="expired", hours=7, events=[("card.expired", "rule_cleared", {})])
        _card(c, "k_open", state="queued", hours=8)
        _card(c, "k_silent", state="expired", hours=9)
        _card(c, "k_other_file", state="queued", hours=10, file="node_elsewhere")
    with engine.connect() as c:
        ended = O.ended_for_files(c, ORG, [FILE])
    got = {e.card_id: (e.ended, e.by, e.reason) for e in ended}
    assert got == {
        "k_verified": (O.VERIFIED, "evt_signed_nda", None),
        "k_replied": (O.REPLIED, "evt_thanks", "rule_cleared"),
        "k_taken": (O.TAKEN, None, "run_play"),
        "k_wrong": (O.CALLED_WRONG, None, "bad_timing"),
        "k_lapsed": (O.LAPSED, None, "expired"),
        "k_dismissed": (O.DISMISSED, None, "extension"),
        "k_replaced": (O.REPLACED, None, "replaced"),
        "k_cleared": (O.CLEARED, None, "rule_cleared"),
        "k_open": (O.OPEN, None, None),
        "k_silent": (O.UNRECORDED, None, None)}
    assert [e.card_id for e in ended][0] == "k_verified", "oldest first"


@pytest.mark.pg
def test_a_card_taken_from_the_dashboard_with_no_verdict_is_still_taken(engine):
    """Before STEP-16's one writer a dashboard press wrote its card event only — it reads as what it was."""
    with engine.begin() as c:
        _card(c, "k_old_press", state="acted", events=[("human.card_action", "do_it_myself", {})])
    with engine.connect() as c:
        [e] = O.ended_for_files(c, ORG, [FILE])
    assert (e.ended, e.reason) == (O.TAKEN, "do_it_myself")


@pytest.mark.pg
def test_the_team_lanes_resolutions_read_as_replaced_and_cleared(engine):
    with engine.begin() as c:
        _card(c, "k_superseded", state="resolved", events=[("card.resolved", "superseded", {})])
        _card(c, "k_situation", state="resolved", hours=1, events=[("card.resolved", "situation_cleared", {})])
    with engine.connect() as c:
        got = {e.card_id: e.ended for e in O.ended_for_files(c, ORG, [FILE])}
    assert got == {"k_superseded": O.REPLACED, "k_situation": O.CLEARED}


@pytest.mark.pg
def test_a_window_reads_the_cards_created_in_it(engine):
    with engine.begin() as c:
        _card(c, "k_before", state="queued", hours=-48, file="node_a")
        _card(c, "k_in", state="queued", hours=0, file="node_b")
        _card(c, "k_after", state="queued", hours=48, file="node_c")
    with engine.connect() as c:
        inside = O.ended_between(c, ORG, since=AT - timedelta(hours=1), until=AT + timedelta(hours=1))
    assert [e.card_id for e in inside] == ["k_in"]


def test_rates_count_by_kind_and_by_lane_and_the_verified_share_says_its_n():
    endings = (
        O.Ended("k1", "f_inv", "decision", O.VERIFIED, by="evt_1"),
        O.Ended("k2", "f_inv", "decision", O.REPLIED),
        O.Ended("k3", "f_inv", "monitor", O.OPEN),
        O.Ended("k4", "f_prog", "decision", O.TAKEN),
        O.Ended("k5", None, "investigation", O.CLEARED))
    out = O.rates(endings, kinds={"f_inv": "investor", "f_prog": "program"})
    investor = out["kind"]["investor"]
    assert (investor.counts[O.VERIFIED], investor.counts[O.REPLIED], investor.counts[O.OPEN]) == (1, 1, 1)
    assert (investor.verified.value, investor.verified.n) == (0.5, 2), "open cards are in no denominator"
    assert set(out["kind"]) == {"investor", "program", "no file"}
    assert out["lane"]["decision"].counts[O.TAKEN] == 1 and out["all"]["all"].verified.n == 4
    assert "usually" not in investor.verified.says(), "never a habit below five"
    assert investor.as_dict()["counts"][O.VERIFIED] == 1


@pytest.mark.pg
def test_the_cards_a_dossier_shows_are_read_by_their_ids(engine):
    with engine.begin() as c:
        _card(c, "k_a", state="expired", events=[("window.lapsed", "expired", {})])
        _card(c, "k_b", state="queued", hours=1, file="node_b")
        _card(c, "k_c", state="queued", hours=2, file="node_c")
    with engine.connect() as c:
        got = {e.card_id: e.ended for e in O.ended_for_cards(c, ORG, ["k_a", "k_b"])}
        assert O.ended_for_cards(c, ORG, []) == ()
    assert got == {"k_a": O.LAPSED, "k_b": O.OPEN}


@pytest.mark.pg
def test_the_cards_of_several_files_are_read_at_once(engine):
    """A kind of work's files, in one read (`context/kind_numbers`) — only theirs, oldest first."""
    with engine.begin() as c:
        _card(c, "k_a", state="queued", file="node_a")
        _card(c, "k_b", state="expired", hours=1, file="node_b", events=[("window.lapsed", "expired", {})])
        _card(c, "k_c", state="queued", hours=2, file="node_c")
    with engine.connect() as c:
        got = [(e.card_id, e.ended) for e in O.ended_for_files(c, ORG, ["node_b", "node_a"])]
        assert O.ended_for_files(c, ORG, []) == ()
    assert got == [("k_a", O.OPEN), ("k_b", O.LAPSED)]
