"""GeniOS-012 S29 · a judged file sees the company's goals, says which one its move bears on, and proposes its own.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_a_file_proposes_its_goal_pg.py -q

`speedrun008/GeniOS-012/07-GOALS.md` S29.U1-U3. Block G prints the goals a human made real, each with the id a move
cites, and the proposals still waiting apart and with no id. A move's `GoalImpact` cites only a printed goal. A
proposal is admitted by L3 as a PENDING brief line, only for a piece of work, only with an act of the company's own,
once per work and at most 3 a week. On 24 Oct the design partner had 0 goals: nothing proposed a goal for a file.

The world is the admitted-judgment test's (`test_an_admitted_judgment_reviews_its_file_pg`): Kunal's fund, one live
situation — plus a mail WE sent on the thread, the company's own act.
"""
from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import goals as GS
from genios_engine.context.goal_admission import ADMIT, HOLD, WEEKLY_CAP, admit_proposal
from genios_engine.contracts import goals as G
from genios_engine.platform import company_brief_store as brief
from genios_engine.platform.self_identity import identity_for
from genios_engine.reason.l2.sweep import l2_pass
from tests.context.workstream_world import FOUNDER, process
from tests.reason.l2.test_an_admitted_judgment_reviews_its_file_pg import KUNAL, ORG, _R9, world  # noqa: F401

pytestmark = pytest.mark.pg


class _R9Goals(_R9):
    """R-9 answering as `_R9`, plus a goal proposal citing `cite` and, when block G prints one, an impact on it."""

    def __init__(self, cite: str = "evt_k_out", impact_on: str | None = None):
        super().__init__()
        self.cite, self.impact_on = cite, impact_on

    def call(self, prompt, *, max_tokens=400, **kw):
        out = super().call(prompt, max_tokens=max_tokens, **kw)
        out.parsed["goal_proposal"] = {"statement": "Close the seed round with the fund", "why": "we pitched them",
                                       "evidence": [self.cite]}
        printed = re.search(r"\[(goal:[^\]\s]+)\]", prompt)
        ref = self.impact_on or (printed.group(1) if printed else None)
        if ref:
            out.parsed["goal_impacts"] = [{"goal_ref": ref, "relation": "advances", "why": "the fund is the round",
                                           "evidence": [self.cite]}]
        return out


@pytest.fixture
def ours(world):
    """The world, with a mail we sent on Kunal's thread; brief lines and goals cleaned after."""
    store, now, file_id = world
    process(store, ORG, event_id="evt_k_out", sender=FOUNDER, recipients=(KUNAL,), thread="t_k",
            at=now - timedelta(days=2))
    yield store, now, file_id
    with store.engine.begin() as c:
        for t in ("company_goals", "company_brief_lines", "goal_situation_links"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})


def _goal_lines(store) -> list:
    with store.engine.connect() as c:
        return c.execute(text("select line_id, status, proposed_by, evidence::text as ev from company_brief_lines "
                              "where org_id = :o and section = 'goals'"), {"o": ORG}).all()


def test_a_judged_file_proposes_its_goal_as_a_pending_brief_line(ours):
    store, now, file_id = ours
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=_R9Goals())
    assert receipt.get("goal_proposals") == {ADMIT: 1}, str(receipt)
    [line] = _goal_lines(store)
    assert (line.status, line.proposed_by) == ("proposed", "l2") and f"file:{file_id}" in line.ev
    with store.engine.begin() as c:
        GS.sync_from_brief(c, ORG, at=now)
    with store.engine.connect() as c:
        [goal] = GS.goals(c, ORG)
        assert (goal.status, goal.subject_ref) == (G.PROPOSED, f"file:{file_id}")
        assert GS.live_goals(c, ORG) == [], "a proposal is never the company's goal"


def test_a_proposal_with_no_act_of_ours_is_held(ours):
    store, now, _file_id = ours
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=_R9Goals(cite="evt_k_in"))
    assert receipt.get("goal_proposals") == {HOLD: 1}, str(receipt)
    assert _goal_lines(store) == []


def test_the_same_work_is_proposed_once_and_the_week_holds_three(ours):
    store, now, file_id = ours
    proposal = G.GoalProposal(statement="Close the seed round with the fund", why="we pitched them",
                              evidence=("evt_k_out",))
    with store.engine.begin() as c:
        us = identity_for(c, ORG)
        first = admit_proposal(c, org_id=ORG, proposal=proposal, subject_ref=f"file:{file_id}", us=us, at=now)
        reworded = G.GoalProposal(statement="Get the fund to lead our seed", why="we pitched them",
                                  evidence=("evt_k_out",))         # other words, the SAME work
        again = admit_proposal(c, org_id=ORG, proposal=reworded, subject_ref=f"file:{file_id}", us=us, at=now)
        assert (first.decision, again.decision) == (ADMIT, HOLD) and "duplicate" in again.reason
        for n in range(WEEKLY_CAP - 1):
            other = G.GoalProposal(statement=f"Another piece of work {chr(65 + n)}", why="we wrote", evidence=("evt_k_out",))
            assert admit_proposal(c, org_id=ORG, proposal=other, subject_ref=f"file:node_other_{n}", us=us,
                                  at=now).decision == ADMIT
        over = G.GoalProposal(statement="One more piece of work", why="we wrote", evidence=("evt_k_out",))
        ruled = admit_proposal(c, org_id=ORG, proposal=over, subject_ref="file:node_other_x", us=us, at=now)
    assert ruled.decision == HOLD and "weekly cap" in ruled.reason


def test_a_live_goal_is_printed_with_its_id_and_the_move_cites_it(ours):
    """An accepted goals line is a live goal: block G prints `[goal:…]`, and the move's impact on it is kept."""
    store, now, _file_id = ours
    with store.engine.begin() as c:
        line = brief.propose(c, org_id=ORG, section="goals", words="Raise the seed round", proposed_by="founder",
                             at=now)
        brief.accept(c, org_id=ORG, line_id=line, decided_by="seat_owner", at=now)
        GS.sync_from_brief(c, ORG, at=now)
        [goal] = GS.live_goals(c, ORG)
    r9 = _R9Goals()
    l2_pass(store=store, org_id=ORG, now=now, llm=r9)
    assert f"[{goal.ref}] Raise the seed round" in r9.prompts[0]
    with store.engine.connect() as c:
        result = c.execute(text("select result from reasoning_results where org_id = :o and status = 'result'"),
                           {"o": ORG}).scalar()
    assert [g["goal_ref"] for g in result["judgment"]["goal_impacts"]] == [goal.ref]


def test_a_move_citing_a_goal_block_g_never_printed_loses_that_impact(ours):
    store, now, _file_id = ours
    l2_pass(store=store, org_id=ORG, now=now, llm=_R9Goals(impact_on="goal:goal_never_printed"))
    with store.engine.connect() as c:
        result = c.execute(text("select result from reasoning_results where org_id = :o and status = 'result'"),
                           {"o": ORG}).scalar()
    assert result["judgment"]["goal_impacts"] == []


def test_s30_a_moves_impact_on_a_live_goal_links_the_admitted_situation(ours):
    """S30.U1: the move cites the live goal; L3 admitted the file's situation — one link, goal → situation."""
    store, now, _file_id = ours
    with store.engine.begin() as c:
        line = brief.propose(c, org_id=ORG, section="goals", words="Raise the seed round", proposed_by="founder",
                             at=now)
        brief.accept(c, org_id=ORG, line_id=line, decided_by="seat_owner", at=now)
        GS.sync_from_brief(c, ORG, at=now)
        [goal] = GS.live_goals(c, ORG)
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=_R9Goals())
    assert receipt.get("goal_links") == 1, str(receipt)
    with store.engine.connect() as c:
        rows = c.execute(text("select goal_id, situation_id, relation from goal_situation_links where org_id = :o"),
                         {"o": ORG}).all()
    assert [tuple(r) for r in rows] == [(goal.goal_id, "sit_c1", "advances")]


def test_s30_no_live_goal_no_link(ours):
    store, now, _file_id = ours
    receipt = l2_pass(store=store, org_id=ORG, now=now, llm=_R9Goals())
    assert not receipt.get("goal_links"), str(receipt)


def test_h14_every_dossier_says_who_the_model_works_for(ours):
    """G012 H-14: the founder named once in the head — on 24 Oct goals came back from the other side of the table."""
    store, now, _file_id = ours
    r9 = _R9Goals()
    l2_pass(store=store, org_id=ORG, now=now, llm=r9)
    assert "YOU WORK FOR" in r9.prompts[0] and FOUNDER in r9.prompts[0]
    assert "they are never the counterparty" in r9.prompts[0]
