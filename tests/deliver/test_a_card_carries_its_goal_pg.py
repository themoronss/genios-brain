"""GeniOS-012 S31.U1 · a card carries the live goals its work moves (`deliver/goal_line`, `cards.goal_refs`).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_card_carries_its_goal_pg.py -q

19 of Rohit's 20 ideal cards name the goal they move; on 24 Oct no card carried one ("Not linked to a goal yet",
hard-coded on the Cards page). A card's goals are the LIVE goals (a human made them real) proposed for its file, or
linked by a judgment's impact to one of its file's admitted situations — refreshed at the end of every card build,
so a goal approved after its file was judged reaches the card with no new judgment.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.deliver.goal_line import refresh_card_goals

pytestmark = pytest.mark.pg

ORG = "org_s31u1_goal_line"
AT = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)

    def _clean(c):
        for t in ("cards", "company_goals", "goal_situation_links", "context_situations", "context_correlations"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    with eng.begin() as c:
        _clean(c)
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        _clean(c)


def _goal(c, goal_id, statement, *, status="approved", subject=None, revision=1):
    live = status in ("approved", "active")
    c.execute(text("insert into company_goals (org_id, goal_id, revision, statement, status, source, subject_ref, "
                   "approved_by, approved_at) values (:o, :g, :r, :s, :st, 'brief', :subj, :by, :at)"),
              {"o": ORG, "g": goal_id, "r": revision, "s": statement, "st": status, "subj": subject,
               "by": "seat_owner" if live else None, "at": AT if live else None})


def _card(c, card_id, file_id, *, state="queued"):
    c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                   "expires_at, state, file_id) values (:c, :s, :o, 'prescriptive', 'standard', 'h', 's', 10, :exp, "
                   ":st, :f)"),
              {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "exp": AT + timedelta(days=7), "st": state, "f": file_id})


def _refs(c, card_id):
    return c.execute(text("select goal_refs from cards where card_id = :c"), {"c": card_id}).scalar()


def test_a_card_carries_the_live_goal_proposed_for_its_file_and_none_pending(engine):
    with engine.begin() as c:
        _goal(c, "goal_round", "Raise the pre-seed round", subject="file:node_fund")
        _goal(c, "goal_hire", "Hire a founding engineer", status="proposed", subject="file:node_hire")
        _card(c, "k_fund", "node_fund")
        _card(c, "k_hire", "node_hire")
        assert refresh_card_goals(c, ORG) == 1
        assert _refs(c, "k_fund") == [{"ref": "goal:goal_round", "statement": "Raise the pre-seed round"}]
        assert _refs(c, "k_hire") == [], "a proposal waits for the founder: no card shows it as its goal"


def test_a_goal_approved_later_reaches_the_card_on_the_next_build(engine):
    with engine.begin() as c:
        _goal(c, "goal_hire", "Hire a founding engineer", status="proposed", subject="file:node_hire")
        _card(c, "k_hire", "node_hire")
        refresh_card_goals(c, ORG)
        _goal(c, "goal_hire", "Hire a founding engineer", subject="file:node_hire", revision=2)   # approved
        refresh_card_goals(c, ORG)
        assert _refs(c, "k_hire") == [{"ref": "goal:goal_hire", "statement": "Hire a founding engineer"}]


def test_a_goal_linked_to_the_files_admitted_situation_reaches_its_card(engine):
    with engine.begin() as c:
        _goal(c, "goal_partners", "Win paying design partners")
        c.execute(text("insert into context_correlations (correlation_id, org_id, anchor_node_id) "
                       "values ('corr_s31', :o, 'node_customer')"), {"o": ORG})
        c.execute(text("insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
                       "situation_type, domain, status, last_seen_at) values ('sit_s31', :o, 'corr_s31', "
                       "'node_customer', 'opportunity', 'sales', 'active', :at)"), {"o": ORG, "at": AT})
        c.execute(text("insert into goal_situation_links (org_id, goal_id, situation_id, relation, why) "
                       "values (:o, 'goal_partners', 'sit_s31', 'advances', 'a pilot they asked for')"), {"o": ORG})
        _card(c, "k_customer", "node_customer")
        _card(c, "k_done", "node_customer", state="resolved")
        refresh_card_goals(c, ORG)
        assert _refs(c, "k_customer") == [{"ref": "goal:goal_partners", "statement": "Win paying design partners"}]
        assert _refs(c, "k_done") == [], "a closed card is left as it was"


def test_every_card_build_refreshes_the_goals_and_the_queue_serves_them():
    """The call sites: `build_cards_for_org` calls the refresh; each of the queue's three doors selects the column."""
    from genios_engine.deliver import pipeline, store
    tree = ast.parse(inspect.getsource(pipeline.build_cards_for_org))
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "refresh_card_goals" in calls
    assert inspect.getsource(store.CardStore.queue).count("k.goal_refs") == 3
