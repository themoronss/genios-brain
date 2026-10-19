"""GeniOS-008 L2 Group A · the ReasoningResult contract (spec §11), its request, its receipt.

    pytest tests/contracts/test_the_reasoning_result.py -q
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from genios_engine.contracts import reasoning_result as R
from genios_engine.contracts.expert_review import DossierCatalogue, ExpertReview

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
CAT = DossierCatalogue(evidence_ids=frozenset({"ev:1", "ev:2", "case:1", "sit:7"}),
                       numbers=frozenset({"2", "48"}), stages=("introduced",))


def _review(mode="act", by_when="2026-10-19"):
    return ExpertReview.from_mapping({
        "facts": [{"claim": "Boardy introduced Asha", "evidence": ["ev:1"]}],
        "inferences": [{"claim": "the intro is warm", "based_on": ["fact:1"]}],
        "patterns": [], "hypotheses": [], "unknowns": [],
        "frames": {"primary": "a warm intro waiting on us", "rivals": ["a scout, not a partner"]},
        "expected_vs_actual": {"stage": "introduced", "expected": "a reply", "actual": "none yet"},
        "scenarios": {"do_nothing": "it goes cold", "act": "a call", "best": "a call", "worst": "silence",
                      "signals_to_watch": ["a reply"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible", "reasons": ["warm"]},
        "mode": mode,
        "next_move": {"who": "you", "what": "reply", "for_whom": "Asha", "by_when": by_when,
                      "rests_on": ["fact:1"]} if mode in ("act", "find_out") else None,
        "alternative": "", "wait_or_stop": "stop if she declines", "done_when": "a call is booked"})


def _judgment(**over):
    raw = {
        "intervention_mode": "prepare_decision",
        "confidence": {d: {"level": "high", "reason": "the mail says so", "evidence": ["ev:1"]}
                       for d in R.CONFIDENCE_DIMENSIONS},
        "options": [{"option": "reply today", "benefit": "warm", "downside": "none",
                     "reversibility": "reversible", "affects": "Asha", "would_change": "a decline"}],
        "history_used": [{"case": "an earlier intro", "applies": True, "why": "same connector",
                          "based_on": ["case:1"]}],
        "second_order": ["the connector keeps sending intros"],
        "decision_need": {"needed": False},
        "proposed_mutations": [{"op": "create", "situation": "investor intro — Asha", "why": "new work",
                                "evidence": ["ev:1"]}],
        "evidence_needs": [], "coverage_limitations": ["the sent folder was not read"],
        "open_conflict": None, "deeper": None}
    raw.update(over)
    return R.L2Judgment.from_mapping(raw)


def test_every_confidence_dimension_is_answered():
    raw = _judgment().as_mapping()
    del raw["confidence"]["causal"]
    with pytest.raises(ValueError, match="causal"):
        R.L2Judgment.from_mapping(raw)


def test_a_confidence_level_is_a_level_never_a_number():
    raw = _judgment().as_mapping()
    raw["confidence"]["evidence"]["level"] = "0.8"
    with pytest.raises(ValueError):
        R.L2Judgment.from_mapping(raw)


def test_a_clean_judgment_has_no_problems():
    assert R.validate_judgment(_review(), _judgment(), CAT, as_of=NOW) == ()


def test_an_act_review_cannot_abstain():
    problems = R.validate_judgment(_review("act"), _judgment(intervention_mode="abstain"), CAT, as_of=NOW)
    assert (R.MODE_MISMATCH, "mode act does not allow abstain") in problems
    assert R.MODE_MISMATCH in R.STRUCTURAL


def test_a_citation_the_dossier_never_printed_is_named_and_dropped():
    j = _judgment(history_used=[{"case": "x", "applies": True, "why": "y", "based_on": ["case:99"]}])
    assert any(k == R.UNPRINTED_REF for k, _ in R.validate_judgment(_review(), j, CAT, as_of=NOW))
    assert R.drop_unprinted(j, CAT, facts=1).history_used == ()


def test_an_update_must_name_a_situation_the_dossier_printed():
    j = _judgment(proposed_mutations=[{"op": "close", "situation": "s", "why": "done", "evidence": ["ev:1"]}])
    assert any(k == R.MUTATION_WITHOUT_TARGET for k, _ in R.validate_judgment(_review(), j, CAT, as_of=NOW))
    assert R.drop_unprinted(j, CAT, facts=1).proposed_mutations == ()
    ok = _judgment(proposed_mutations=[{"op": "close", "situation": "s", "why": "done", "evidence": ["ev:1"],
                                        "situation_ref": "sit:7"}])
    assert R.validate_judgment(_review(), ok, CAT, as_of=NOW) == ()


def test_a_number_the_dossier_does_not_hold_is_named():
    j = _judgment(second_order=["she will reply in 3 days"])
    assert (R.NUMBER_NOT_PRINTED, "3") in R.validate_judgment(_review(), j, CAT, as_of=NOW)


def test_a_needed_decision_with_no_owner_needs_review():
    j = _judgment(decision_need={"needed": True, "what": "sign"})
    problems = R.validate_judgment(_review(), j, CAT, as_of=NOW)
    assert any(k == R.DECISION_WITHOUT_OWNER for k, _ in problems)


def test_a_move_due_before_the_run_needs_review():
    problems = R.validate_judgment(_review(by_when="2026-10-01"), _judgment(), CAT, as_of=NOW)
    assert any(k == R.MOVE_IN_THE_PAST for k, _ in problems)


# ── the lane is code's ─────────────────────────────────────────────────────────────────────────

def test_an_open_conflict_routes_first():
    j = _judgment(open_conflict={"about": "the date", "between": ["ev:1", "ev:2"]})
    assert R.lane_for(j)[0] == R.LANE_CONFLICT


def test_a_decision_needs_evidence_and_framing():
    assert R.lane_for(_judgment())[0] == R.LANE_DECISION
    conf = {d: {"level": "high", "reason": "r"} for d in R.CONFIDENCE_DIMENSIONS}
    conf["framing"] = {"level": "low", "reason": "could be a scout"}
    assert R.lane_for(_judgment(confidence=conf))[0] == R.LANE_MONITOR


@pytest.mark.parametrize("mode,lane", [("observe", R.LANE_SUPPRESS), ("abstain", R.LANE_SUPPRESS),
                                       ("monitor", R.LANE_MONITOR), ("gather_evidence", R.LANE_INVESTIGATION),
                                       ("clarify", R.LANE_INVESTIGATION), ("escalate", R.LANE_DECISION)])
def test_each_mode_has_its_lane(mode, lane):
    assert R.lane_for(_judgment(intervention_mode=mode))[0] == lane


def test_every_lane_is_reachable_and_every_mode_routes():
    reached = {R.lane_for(_judgment(intervention_mode=m))[0] for m in R.INTERVENTION_MODES}
    reached.add(R.lane_for(_judgment(open_conflict={"about": "a", "between": ["ev:1", "ev:2"]}))[0])
    assert reached == set(R.LANES)


def test_every_review_mode_allows_some_intervention():
    from genios_engine.contracts.expert_review import MODES
    assert set(R.MODE_FITS) == set(MODES)
    assert all(fits <= set(R.INTERVENTION_MODES) for fits in R.MODE_FITS.values())


# ── result, request, receipt ───────────────────────────────────────────────────────────────────

def _result():
    j = _judgment()
    lane, why = R.lane_for(j)
    return R.ReasoningResult(request_ref="l2req:x", subject_ref="file:n1", context_ref="graph@7",
                             expertise_ref="pkg:abc", depth=R.DEPTH_STANDARD, review=_review(), judgment=j,
                             lane=lane, lane_reason=why)


def test_a_result_reads_back_byte_for_byte():
    r = _result()
    back = R.ReasoningResult.from_mapping(r.as_mapping())
    assert back.as_mapping() == r.as_mapping()
    assert back.output_hash() == r.output_hash()


def test_the_spec_names_read_through():
    r = _result()
    assert r.frame == "a warm intro waiting on us"
    assert r.alternative_frames == ("a scout, not a partner",)
    assert r.best_next_move.by_when == date(2026, 10, 19)
    assert r.consequences["second_order"] == ["the connector keeps sending intros"]
    assert set(r.confidence) == set(R.CONFIDENCE_DIMENSIONS)
    assert not r.review_required


def test_a_request_is_its_content():
    a = R.L2Request(org_id="o", subject_ref="file:n1", trigger=R.TRIGGER_BUNDLE, eval_time=NOW,
                    bundle_ids=("b2", "b1"), fingerprint="fp")
    b = R.L2Request(org_id="o", subject_ref="file:n1", trigger=R.TRIGGER_BUNDLE, eval_time=NOW,
                    bundle_ids=("b1", "b2"), fingerprint="fp")
    assert a.request_id == b.request_id
    with pytest.raises(ValueError):
        R.L2Request(org_id="o", subject_ref="file:n1", trigger="legacy.rule_scan", eval_time=NOW)
    with pytest.raises(ValueError):
        R.L2Request(org_id="o", subject_ref="file:n1", trigger=R.TRIGGER_BUNDLE, eval_time=NOW,
                    request_id="l2req:forged")


def test_a_receipt_names_how_the_run_ended():
    with pytest.raises(ValueError):
        R.ReasoningReceipt(request_ref="r", org_id="o", subject_ref="s", trigger="bundle", context_ref="c",
                           expertise_ref="e", depth="standard", depth_why=(), groups_run=(), groups_skipped={},
                           tool_results={}, model=None, prompt_version="p", calls=0, termination="fine")
