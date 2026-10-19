"""L2 rebuild B3 — Layer 3 admits what the Layer 2 judgment proposed: ADMIT / HOLD / REJECT, never a guess.

Atlas v2 (L3 §): the Intelligence Graph is written only by "L3 admission of L2's mutations". Today's joins file a
situation row per file BEFORE reasoning — those rows are seeds; a seed is a situation GeniOS stands behind only
when its file's judgment is admitted (`context/l2_admission`).
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from genios_engine.context.l2_admission import ADMIT, HOLD, NO_SITUATION, REJECT, decide
from genios_engine.contracts.reasoning_result import ProposedMutation

pytestmark = pytest.mark.unit


def _m(op, ref=None, why="because"):
    return ProposedMutation(op=op, situation="the work", why=why, evidence=("fact:1",), situation_ref=ref)


def _result(*mutations, lane="decision", mode="prepare_decision"):
    return NS(lane=lane, lane_reason="a reply is owed", intervention_mode=mode, proposed_mutations=mutations)


def _sit(sid, status="active"):
    return NS(situation_id=sid, status=status)


def _d(result, situations=(), subject="file:n1"):
    return [(a.situation_id, a.decision, a.op)
            for a in decide(org_id="o", subject_ref=subject, fingerprint="fp", result=result, situations=situations)]


def test_an_update_or_close_naming_a_seed_is_admitted_with_its_op():
    assert _d(_result(_m("update", "sit:s1"), _m("close", "sit:s2")), [_sit("s1"), _sit("s2")]) == [
        ("s1", ADMIT, "update"), ("s2", ADMIT, "close")]


def test_a_merge_or_link_is_held_never_applied_by_guess():
    assert _d(_result(_m("merge", "sit:s1")), [_sit("s1")]) == [("s1", HOLD, "merge")]


def test_nothing_material_rejects_every_live_seed():
    assert _d(_result(lane="suppress", mode="abstain"), [_sit("s1"), _sit("s2")]) == [
        ("s1", REJECT, "none"), ("s2", REJECT, "none")]


def test_a_create_binds_the_live_seed_the_judgment_reasoned_about():
    assert _d(_result(_m("create")), [_sit("s1"), _sit("s0", status="resolved")]) == [("s1", ADMIT, "create")]


def test_the_only_live_seed_unnamed_is_what_the_judgment_is_about():
    assert _d(_result(), [_sit("s1")]) == [("s1", ADMIT, "unchanged")]


def test_one_of_several_live_seeds_unnamed_is_held():
    assert _d(_result(), [_sit("s1"), _sit("s2")]) == [("s1", HOLD, "unchanged"), ("s2", HOLD, "unchanged")]


def test_a_seed_subject_with_no_situation_row_is_held_at_subject_level():
    assert _d(_result(_m("create")), [], subject="seed:thread:t1") == [(NO_SITUATION, HOLD, "create")]


def test_a_run_that_concluded_nothing_decides_nothing():
    assert _d(None, [_sit("s1")]) == []
