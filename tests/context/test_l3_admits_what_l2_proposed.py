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


# ── L3 rebuild 5a/5b · what an admitted judgment concluded, recorded on the chain ─────────────────────────────
class _Result:
    def __init__(self, *, needed=False):
        self.context_ref = "graph@7"
        self._m = {"review": {"frames": {"primary": "a renewal waiting on us", "rivals": ["already sent"]},
                              "unknowns": [{"what": "who signs"}], "hypotheses": [],
                              "expected_vs_actual": {"expected": "signed", "actual": "not sent"},
                              "next_move": {"who": "you", "what": "sign it", "by_when": "2026-10-20"}},
                   "judgment": {"intervention_mode": "prepare_decision",
                                "decision_need": {"needed": needed, "who": "the founder" if needed else None,
                                                  "what": "renew at the new price" if needed else None}}}

    def as_mapping(self):
        return self._m


def _adm(decision, op="update", sit="s1"):
    from genios_engine.context.l2_admission import Admission
    return Admission(org_id="o", subject_ref="file:n1", situation_id=sit, decision=decision, op=op, reason="r",
                     result_fingerprint="fp1", lane="decision")


def test_an_admitted_judgment_is_recorded_with_its_conclusions_and_a_decision_object():
    from genios_engine.context.l2_admission import INTERPRETATION_VERSION, interpretation_of
    rec = interpretation_of(_adm(ADMIT), _Result(needed=True))
    assert rec["version"] == INTERPRETATION_VERSION and rec["frame"] == "a renewal waiting on us"
    assert rec["rivals"] == ["already sent"] and rec["unknowns"] == [{"what": "who signs"}]
    assert rec["decision"] == {"needed": True, "who": "the founder", "what": "renew at the new price",
                               "by_when": "2026-10-20"}
    assert "dossier" not in rec and "facts" not in rec, "conclusions only — the dossier is reasoning_results'"


def test_no_decision_owed_carries_no_deadline():
    from genios_engine.context.l2_admission import interpretation_of
    assert interpretation_of(_adm(ADMIT), _Result())["decision"] == {"needed": False, "who": None, "what": None,
                                                                     "by_when": None}


def test_only_an_admitted_judgment_of_a_real_situation_is_recorded():
    from genios_engine.context.l2_admission import interpretation_of
    assert interpretation_of(_adm(HOLD), _Result()) is None
    assert interpretation_of(_adm(REJECT, op="none"), _Result()) is None
    assert interpretation_of(_adm(ADMIT, sit=NO_SITUATION), _Result()) is None
