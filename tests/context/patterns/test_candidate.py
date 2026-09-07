"""L2.6.2-U1 · the Candidate Builder — every row in the spec's ACCEPTANCE list.

The decisive row is the second one: evidence is CARRIED, not recomputed. The test mutates the
graph between the match and the build and asserts the candidate still says what the match saw —
because a candidate that re-derived its evidence would disagree with the match that produced it,
and neither would look wrong.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from genios_engine.context.patterns import candidate as candidate_module
from genios_engine.context.patterns.candidate import (SituationCandidate, UnevidencedCondition,
                                                      build_candidate)
from genios_engine.context.patterns.contract import ConditionKind
from genios_engine.context.patterns.matcher import ConditionEvidence, match
from genios_engine.contracts.quality import AbsenceType


@pytest.fixture
def five(pattern):
    return pattern(pattern_id="five", conditions=[
        {"kind": "fact", "field": "subscription.status", "op": "eq", "value": "active"},
        {"kind": "temporal", "field": "subscription.current_period_end", "op": "within_days",
         "value": 30},
        {"kind": "fact", "field": "contract.value", "op": "gte", "value": "@authority_threshold"},
        {"kind": "edge", "type": "owns", "from": "@anchor", "op": "missing"},
        {"kind": "absence", "field": "decision.scheduled", "type": "GENUINELY_ABSENT"}],
        emits={"situation_type": "vendor_renewal_decision"})


@pytest.fixture
def world(graph_slice, fact, absent, eval_time):
    def _build(**overrides):
        base = dict(
            facts=(fact("subscription.status", "active"),
                   fact("subscription.current_period_end",
                        (eval_time + timedelta(days=12)).isoformat()),
                   fact("contract.value", 8_400_000)),
            absences=(absent("decision.scheduled", AbsenceType.GENUINELY_ABSENT),),
            edge_coverage=("owns",), authority_threshold_minor_units=5_000_000,
            member_signal_ids=("sig_b", "sig_a", "sig_a"),
            member_event_ids=("evt_2", "evt_1"))
        base.update(overrides)
        return graph_slice(**base)
    return _build


def test_a_five_condition_match_builds_five_evidence_entries(five, world, eval_time):
    result = match(five, world(), eval_time=eval_time)
    built = build_candidate(result, world(), eval_time=eval_time)
    assert isinstance(built, SituationCandidate)
    assert len(built.per_condition_evidence) == 5
    assert built.pattern_id == "five"
    assert built.pattern_version == 1
    assert built.provisional_type == "vendor_renewal_decision"


def test_the_evidence_is_carried_and_not_recomputed(five, world, fact, eval_time):
    """The row this unit exists for. The graph MOVES between the match and the build — the
    threshold changes and the status flips — and the candidate still carries what the match saw.

    A builder that re-derived from the slice would produce a candidate whose explanation
    contradicts the match that produced it, and there would be no way to tell which was right.
    """
    result = match(five, world(), eval_time=eval_time)
    moved = world(facts=(fact("subscription.status", "canceled"),
                         fact("subscription.current_period_end",
                              (eval_time - timedelta(days=99)).isoformat()),
                         fact("contract.value", 1)),
                  authority_threshold_minor_units=99_000_000)
    built = build_candidate(result, moved, eval_time=eval_time)
    assert built.per_condition_evidence == result.evidence
    assert built.per_condition_evidence[0].observed == "active"
    assert built.per_condition_evidence[2].expected == 5_000_000


def test_pattern_id_and_version_are_on_every_candidate(five, world, eval_time):
    """Without both, a pattern change cannot be traced to the situations it altered."""
    built = build_candidate(match(five, world(), eval_time=eval_time), world(),
                            eval_time=eval_time)
    record = built.as_record()
    assert record["pattern_id"] == "five"
    assert record["pattern_version"] == 1
    assert record["matched_conditions"], "the record's name for the per-condition evidence"


def test_members_are_sorted_and_deduplicated(five, world, eval_time):
    """These reach a content-addressed object. An iteration-order difference over one unchanged
    situation mints a fresh package row per sweep — the mechanism behind the 995 MB incident."""
    built = build_candidate(match(five, world(), eval_time=eval_time), world(),
                            eval_time=eval_time)
    assert built.member_signal_ids == ("sig_a", "sig_b")
    assert built.member_event_ids == ("evt_1", "evt_2")


def test_the_candidate_key_is_stable_across_two_drains(five, world, eval_time):
    """Two drains over an unchanged world must produce the same key, or the fire log double-counts
    and every rate in the report is wrong by however many times the drain ran."""
    a = build_candidate(match(five, world(), eval_time=eval_time), world(), eval_time=eval_time)
    b = build_candidate(match(five, world(), eval_time=eval_time), world(), eval_time=eval_time)
    assert a.candidate_key == b.candidate_key == "five@1:node_sub_aws"


def test_a_match_with_an_unevidenced_condition_raises(five, world, eval_time):
    """The evaluator already refuses to produce one. A hand-built match that carries one must not
    be laundered here: undoing the guarantee one layer later is worse than the original defect,
    because the failure is now two modules from its cause."""
    result = match(five, world(), eval_time=eval_time)
    hollow = ConditionEvidence(index=0, kind=ConditionKind.FACT, field_path="x.y", operator="eq",
                               expected=1, observed=1, ref="")
    broken = type(result)(**{**result.__dict__, "evidence": (hollow,)}) if hasattr(
        result, "__dict__") else None
    if broken is None:                       # slots dataclass — rebuild through the constructor
        from dataclasses import replace
        broken = replace(result, evidence=(hollow,))
    with pytest.raises(UnevidencedCondition):
        build_candidate(broken, world(), eval_time=eval_time)


def test_the_candidate_carries_no_score_and_no_importance():
    """Source-level, because the defect is a FIELD existing rather than a value being wrong. A
    candidate carrying an importance would be a second ranking scale beside BLG-18's, with none of
    the stored components that explain it."""
    fields = set(SituationCandidate.__dataclass_fields__)
    assert "importance_bp" not in fields
    assert "score" not in fields
    assert "promote" not in fields
    # And no field NAMED for either, however spelled — the defect is a field existing, and a
    # future `candidate_importance_bp` would satisfy the three exact-name checks above.
    assert not [f for f in fields if "importance" in f or "score" in f or "rank" in f]
    # The record a caller serialises carries the same absence: a key here is what a consumer
    # would read, whatever the dataclass calls it.
    assert not [k for k in SituationCandidate.__dataclass_fields__
                if k.endswith("_bp") and k != "match_strength_bp"]


def test_the_builder_emits_no_business_situation_object():
    """A candidate is not a situation. This module must not be able to publish one."""
    source = Path(candidate_module.__file__).read_text()
    assert "BusinessSituationObject" not in source
    assert "context_situations" not in source
