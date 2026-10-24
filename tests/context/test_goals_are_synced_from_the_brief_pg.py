"""GeniOS-012 S28.U1 · the goal object, synced from the company brief every sweep (`context/goals`).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_goals_are_synced_from_the_brief_pg.py -q

The brief is the one door (D11): a pending `goals` line is a proposed goal, an accepted one an approved goal (a human
approved it: who and when), a rejected one cancelled. A quiet sync writes nothing. The table itself refuses an
approved goal with no approver. On 24 Oct the design partner had 0 goals and the drafter proposed 4 goal lines; nothing
turned a line into a goal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from genios_engine.context import goals as GS
from genios_engine.contracts import goals as G
from genios_engine.platform import company_brief_store as store

pytestmark = pytest.mark.pg

ORG = "org_s28u1_goals"
AT = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)

    def _clean(c):
        for t in ("company_goals", "goal_situation_links", "company_brief_lines"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    with eng.begin() as c:
        _clean(c)
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        _clean(c)


def _propose(eng, words: str) -> str:
    with eng.begin() as c:
        return store.propose(c, org_id=ORG, section="goals", words=words, proposed_by="drafter", at=AT)


def _sync(eng, at=AT) -> dict:
    with eng.begin() as c:
        return GS.sync_from_brief(c, ORG, at=at)


def _goals(eng) -> dict[str, G.Goal]:
    with eng.connect() as c:
        return {g.line_id: g for g in GS.goals(c, ORG)}


def test_a_pending_goals_line_is_a_proposed_goal_never_shown_as_the_companys(engine):
    line = _propose(engine, "Get the accelerator to reconsider the application")
    assert _sync(engine) == {G.PROPOSED: 1}
    goal = _goals(engine)[line]
    assert (goal.status, goal.source, goal.approved_by, goal.revision) == (G.PROPOSED, G.INFERRED, None, 1)
    with engine.connect() as c:
        assert GS.live_goals(c, ORG) == [], "a proposal is never the company's goal"


def test_an_accepted_line_is_an_approved_goal_with_who_and_when(engine):
    line = _propose(engine, "Raise the pre-seed round")
    _sync(engine)
    with engine.begin() as c:
        store.accept(c, org_id=ORG, line_id=line, decided_by="seat_owner", at=AT + timedelta(hours=1))
    assert _sync(engine, AT + timedelta(hours=1)) == {G.APPROVED: 1}
    goal = _goals(engine)[line]
    assert (goal.status, goal.source, goal.approved_by, goal.revision) == (G.APPROVED, G.BRIEF, "seat_owner", 2)
    assert goal.approved_at is not None
    with engine.connect() as c:
        assert [g.line_id for g in GS.live_goals(c, ORG)] == [line]


def test_a_quiet_sync_writes_no_revision(engine):
    _propose(engine, "Hire a founding engineer")
    _sync(engine)
    assert _sync(engine, AT + timedelta(minutes=5)) == {}
    with engine.connect() as c:
        assert c.execute(text("select count(*) from company_goals where org_id = :o"), {"o": ORG}).scalar() == 1


def test_a_rejected_line_is_a_cancelled_goal(engine):
    line = _propose(engine, "Enter a new market this quarter")
    _sync(engine)
    with engine.begin() as c:
        store.reject(c, org_id=ORG, line_id=line, decided_by="seat_owner", at=AT + timedelta(hours=1))
    assert _sync(engine) == {G.CANCELLED: 1}
    assert _goals(engine)[line].status == G.CANCELLED


def test_the_table_refuses_an_approved_goal_with_no_approver(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.execute(text("insert into company_goals (org_id, goal_id, revision, statement, status, source) "
                           "values (:o, 'goal_x', 1, 'a goal', 'approved', 'brief')"), {"o": ORG})


def test_the_contract_refuses_an_approved_goal_with_no_approver():
    with pytest.raises(ValueError, match="human approved"):
        G.Goal(goal_id="goal_x", org_id=ORG, statement="a goal", status=G.APPROVED, source=G.BRIEF)


def test_every_sweep_syncs_the_goals_first(engine, pg_store):
    """The call site (`reason/runner.run_all`): a sweep turns the brief's pending goals line into a proposed goal."""
    from genios_engine.packs.wiring import make_registry
    from genios_engine.reason.runner import run_all
    line = _propose(engine, "Win the first paying design partners")
    run_all(org_id=ORG, store=pg_store, eval_time=AT, registry=make_registry(
        pg_store.engine.url.render_as_string(hide_password=False)))
    assert _goals(engine)[line].status == G.PROPOSED
