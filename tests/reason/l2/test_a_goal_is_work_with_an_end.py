"""G012 H-16 · a goal is work with an END, the same goal is admitted once, and the most important goes first.

    pytest tests/reason/l2/test_a_goal_is_work_with_an_end.py -q

On the design partner's org (local copy, 24 Oct) 27 of 40 judged files proposed a goal — most of them "keep the
relationship warm" and one per investor — and the week's cap took the first files judged, not the most important.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from genios_engine.context.goal_admission import same_goal
from genios_engine.reason.l2 import prompt as P
from genios_engine.reason.l2 import sweep

pytestmark = pytest.mark.unit


def test_the_rule_says_a_goal_has_an_end_and_staying_in_touch_is_a_move():
    rule = next(r for r in P.RULES if r.startswith("A goal is the company's only"))
    assert "END" in rule and "never a goal" in rule and "raise the round" in rule
    assert P.PROMPT_VERSION == "l2-judgment.v4"


@pytest.mark.parametrize("a, b, same", [
    ("Raise the pre-seed round", "Close the pre-seed round for the company", True),
    ("Get into an accelerator this cycle", "Get into an accelerator cohort this cycle", True),
    ("Raise the pre-seed round", "Hire a founding AI engineer", False),
    ("Win paying design partners", "Complete the startup registration filing", False),
])
def test_the_same_goal_in_other_words(a, b, same):
    assert same_goal(a, b) is same


def _result(stakes, urgency):
    return SimpleNamespace(review=SimpleNamespace(appraisal=SimpleNamespace(stakes=stakes, urgency=urgency)))


def test_a_proposal_is_ranked_by_its_works_stakes_then_urgency():
    ranked = sorted([("low", "high"), ("high", "low"), ("high", "high"), ("medium", "medium")],
                    key=lambda su: sweep._goal_rank(_result(*su)))
    assert ranked == [("high", "high"), ("high", "low"), ("medium", "medium"), ("low", "high")]


def test_the_pass_admits_its_proposals_in_rank_order():
    """The call site: the admission loop walks the proposals sorted by rank, never in the order judged."""
    assert "sorted(goal_proposals, key=lambda p: p[0])" in inspect.getsource(sweep.l2_pass)


def test_h19_a_goal_is_worded_at_the_companys_level_and_a_waiting_one_may_be_served():
    """G012 H-19: six of fourteen goals were "land a partnership with <one company>"; the founder's are company-level."""
    rule = next(r for r in P.RULES if r.startswith("A goal is the company's only"))
    assert "at the level the company pursues it" in rule and "a waiting one too" in rule
    assert "partner's or customer's conversation" in rule and "never call a waiting goal the company's" in rule


def test_h19_the_pass_keeps_the_work_each_judgment_serves_and_syncs_the_goals():
    """The call sites: every judged file's impacts reach `cover_work`, and the goals are synced after the writes."""
    source = inspect.getsource(sweep.l2_pass)
    assert "cover_work(conn, org_id, impacts=impacts, subject_ref=work_ref, at=now)" in source
    assert "goal_work.append((impacts, f\"file:{subject.file_id}\"))" in source
    assert "sync_from_brief(conn, org_id, at=now)" in source
