"""L2.6.1-U2 · the pattern evaluator — every row in the spec's ACCEPTANCE list.

The first test in this file is the one the reverse prompt says to write first, and it is the one
that inverts the whole system if it is written backwards: **GENUINELY_ABSENT satisfies an absence
condition; UNKNOWABLE does not.** Backwards, every unconnected source becomes a confident finding
about a customer.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.context.patterns.contract import BASE_MATCH_STRENGTH_BP
from genios_engine.context.patterns.matcher import (FAIL_ABSENCE_NOT_LICENSED,
                                                    FAIL_EDGE_ABSENCE_UNKNOWABLE,
                                                    FAIL_FACT_COMPARISON,
                                                    FAIL_REFERENCE_UNRESOLVED, ConditionEvidence,
                                                    evaluate, match)
from genios_engine.context.patterns.slice import SliceEdge
from genios_engine.contracts.analytic import AnomalyDirection, TrendDirection
from genios_engine.contracts.quality import AbsenceType

FIVE_CONDITIONS = {
    "pattern_id": "five", "anchor": {"node_type": "subscription"},
    "conditions": [
        {"kind": "fact", "field": "subscription.status", "op": "eq", "value": "active"},
        {"kind": "temporal", "field": "subscription.current_period_end", "op": "within_days",
         "value": 30},
        {"kind": "fact", "field": "contract.value", "op": "gte", "value": "@authority_threshold"},
        {"kind": "edge", "type": "owns", "from": "@anchor", "op": "missing"},
        {"kind": "absence", "field": "decision.scheduled", "type": "GENUINELY_ABSENT"}],
    "emits": {"situation_type": "vendor_renewal_decision"}}


@pytest.fixture
def five(pattern):
    return pattern(**FIVE_CONDITIONS)


@pytest.fixture
def full_slice(graph_slice, fact, absent, eval_time):
    """The world in which all five conditions hold."""
    def _build(**overrides):
        base = dict(
            facts=(fact("subscription.status", "active"),
                   fact("subscription.current_period_end",
                        (eval_time + timedelta(days=12)).isoformat()),
                   fact("contract.value", 8_400_000)),
            absences=(absent("decision.scheduled", AbsenceType.GENUINELY_ABSENT),),
            edge_coverage=("owns",), authority_threshold_minor_units=5_000_000,
            authority_rule_id="authr_finance")
        base.update(overrides)
        return graph_slice(**base)
    return _build


# =================================================================================================
# The rule that inverts the system if it is written backwards
# =================================================================================================

@pytest.mark.parametrize("absence_type", [AbsenceType.UNKNOWABLE, AbsenceType.STALE,
                                          AbsenceType.NOT_EXPECTED, AbsenceType.PRESENT])
def test_only_genuinely_absent_satisfies_an_absence_condition(five, full_slice, absent,
                                                              eval_time, absence_type):
    """UNKNOWABLE, STALE, NOT_EXPECTED and PRESENT do NOT satisfy. Each is a separate row.

    `UNKNOWABLE` is the dangerous one: it means no connected source could have carried the fact,
    so satisfying on it would turn our own missing plumbing into "no decision is scheduled" —
    a confident finding about a customer, produced by a connector nobody installed.
    """
    outcome = evaluate(five, full_slice(
        absences=(absent("decision.scheduled", absence_type),)), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure is not None
    assert outcome.failure.reason == FAIL_ABSENCE_NOT_LICENSED
    assert absence_type.value in outcome.failure.detail


def test_genuinely_absent_satisfies_and_cites_what_was_looked_at(five, full_slice, eval_time):
    result = match(five, full_slice(), eval_time=eval_time)
    assert result is not None
    absence_evidence = result.evidence[4]
    assert absence_evidence.observed == "genuinely_absent"
    # The receipt for an absence is WHAT WE CHECKED. Without it the evidence is the bare assertion
    # "it is not there", which is exactly the claim a founder cannot verify.
    assert dict(absence_evidence.record)["coverage_basis"] == ["gcal", "gmail"]


def test_a_missing_absence_row_is_not_an_absence(five, full_slice, eval_time):
    """No typed answer recorded is UNKNOWN, not absent. The safe direction."""
    outcome = evaluate(five, full_slice(absences=()), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.reason == FAIL_ABSENCE_NOT_LICENSED
    assert "no typed answer" in outcome.failure.detail


# =================================================================================================
# Five conditions, and four of five
# =================================================================================================

def test_a_five_condition_pattern_fires_only_when_all_five_hold(five, full_slice, eval_time):
    result = match(five, full_slice(), eval_time=eval_time)
    assert result is not None
    assert len(result.evidence) == 5
    assert result.situation_type == "vendor_renewal_decision"


def test_four_of_five_returns_none_and_records_which_condition_failed(five, full_slice, fact,
                                                                      eval_time):
    outcome = evaluate(five, full_slice(
        facts=(fact("subscription.status", "canceled"),
               fact("subscription.current_period_end", (eval_time + timedelta(days=12)).isoformat()),
               fact("contract.value", 8_400_000))), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.index == 0
    assert outcome.failure.field_path == "subscription.status"
    assert outcome.failure.reason == FAIL_FACT_COMPARISON


def test_a_window_that_already_closed_does_not_satisfy_within_days(five, full_slice, fact,
                                                                   eval_time):
    """`within_days` is future-only. A closed window is a different situation, and letting it
    satisfy is how a card says "12 days left" about a date last month."""
    outcome = evaluate(five, full_slice(
        facts=(fact("subscription.status", "active"),
               fact("subscription.current_period_end", (eval_time - timedelta(days=4)).isoformat()),
               fact("contract.value", 8_400_000))), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.index == 1


# =================================================================================================
# @authority_threshold — resolved against the org, never a constant
# =================================================================================================

def test_two_orgs_with_different_thresholds_match_differently_on_the_same_amount(five, full_slice,
                                                                                 eval_time):
    """The whole point of the reference: "high value" means THIS company's approval threshold."""
    strict = match(five, full_slice(authority_threshold_minor_units=5_000_000),
                   eval_time=eval_time)
    lenient = match(five, full_slice(authority_threshold_minor_units=90_000_000),
                    eval_time=eval_time)
    assert strict is not None
    assert lenient is None


def test_no_authority_rule_refuses_rather_than_defaulting_to_zero(five, full_slice, eval_time):
    """A zero threshold would make "high value" mean "any value" and fire on every subscription."""
    outcome = evaluate(five, full_slice(authority_threshold_minor_units=None),
                       eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.reason == FAIL_REFERENCE_UNRESOLVED


def test_the_authority_rule_is_named_in_the_evidence(five, full_slice, eval_time):
    result = match(five, full_slice(), eval_time=eval_time)
    assert dict(result.evidence[2].record)["authority_rule_id"] == "authr_finance"


# =================================================================================================
# A missing EDGE is a negative inference and needs the same licence
# =================================================================================================

def test_a_missing_edge_licenses_nothing_without_declared_coverage(five, full_slice, eval_time):
    """An org with no CRM connected has no `owns` edges at all, and "nobody owns this" would then
    be true of every contract in the company."""
    outcome = evaluate(five, full_slice(edge_coverage=()), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.reason == FAIL_EDGE_ABSENCE_UNKNOWABLE


def test_an_existing_owner_edge_stops_the_unowned_pattern(five, full_slice, eval_time):
    owned = full_slice(edges=(SliceEdge("ev_1", "owns", "node_sub_aws", "node_rohit", 9000),))
    assert match(five, owned, eval_time=eval_time) is None


# =================================================================================================
# Optional signals raise strength and never gate
# =================================================================================================

def test_a_pattern_fires_with_zero_optional_signals_satisfied(pattern, full_slice, eval_time):
    with_signals = pattern(**FIVE_CONDITIONS, optional_signals=[
        {"kind": "observation", "kind_name": "decision_deferred", "weight_bp": 1500}])
    result = match(with_signals, full_slice(), eval_time=eval_time)
    assert result is not None, "an optional signal must never be able to block a fire"
    assert result.match_strength_bp == BASE_MATCH_STRENGTH_BP
    assert result.optional_evidence == ()


def test_a_satisfied_optional_signal_raises_match_strength(pattern, full_slice, observation,
                                                           eval_time):
    with_signals = pattern(**FIVE_CONDITIONS, optional_signals=[
        {"kind": "observation", "kind_name": "decision_deferred", "within_days": 90,
         "weight_bp": 1500},
        {"kind": "trend", "metric": "engagement.touch_count_28d", "direction": "declining",
         "weight_bp": 1000}])
    result = match(with_signals, full_slice(
        observations=(observation("decision_deferred", days_ago=10),)), eval_time=eval_time)
    assert result.match_strength_bp == BASE_MATCH_STRENGTH_BP + 1500
    assert len(result.optional_evidence) == 1


def test_match_strength_clamps_at_the_scale(pattern, full_slice, observation, eval_time):
    loud = pattern(**FIVE_CONDITIONS, optional_signals=[
        {"kind": "observation", "kind_name": "decision_deferred", "weight_bp": 9000},
        {"kind": "observation", "kind_name": "going_dark", "weight_bp": 9000}])
    result = match(loud, full_slice(observations=(observation("decision_deferred"),
                                                  observation("going_dark"))),
                   eval_time=eval_time)
    assert result.match_strength_bp == 10_000


# =================================================================================================
# The three floors live with the CONDITION KIND, not with the pattern
# =================================================================================================

def test_a_trend_below_the_confidence_floor_does_not_satisfy(pattern, graph_slice, trend,
                                                             eval_time):
    p = pattern(pattern_id="cold", anchor={"node_type": "company"},
                conditions=[{"kind": "trend", "metric": "engagement.touch_count_28d",
                             "direction": "declining"}],
                emits={"situation_type": "relationship_going_cold"})
    thin = graph_slice(node_type="company", trends=(trend(confidence_bp=4000),))
    strong = graph_slice(node_type="company", trends=(trend(confidence_bp=5000),))
    assert match(p, thin, eval_time=eval_time) is None
    assert match(p, strong, eval_time=eval_time) is not None


def test_a_cohort_below_the_population_floor_does_not_satisfy(pattern, graph_slice, position,
                                                              eval_time):
    """Law 2. A `CohortPosition` cannot even be constructed below five members, so the fixture
    builds a legal one at the floor and the evaluator is proven against the boundary."""
    p = pattern(pattern_id="bottom", anchor={"node_type": "company"},
                conditions=[{"kind": "cohort", "metric": "engagement.touch_count_28d",
                             "op": "percentile_lte", "value": 2500}],
                emits={"situation_type": "relationship_going_cold"})
    at_floor = graph_slice(node_type="company",
                           cohort_positions=(position(population=5, percentile_bp=2000),))
    assert match(p, at_floor, eval_time=eval_time) is not None


def test_an_anomaly_below_the_period_floor_does_not_satisfy(pattern, graph_slice, anomaly,
                                                            eval_time):
    p = pattern(pattern_id="spike", anchor={"node_type": "company"},
                conditions=[{"kind": "anomaly", "metric": "support.ticket_count_28d",
                             "direction": "above"}],
                emits={"situation_type": "support_spike"})
    # `Anomaly` refuses fewer than six periods at construction, so the floor is proven at its
    # boundary rather than below it: six satisfies, and the contract makes five unbuildable.
    assert match(p, graph_slice(node_type="company", anomalies=(anomaly(periods_used=6),)),
                 eval_time=eval_time) is not None
    assert match(p, graph_slice(node_type="company",
                                anomalies=(anomaly(direction=AnomalyDirection.BELOW),)),
                 eval_time=eval_time) is None


def test_a_pattern_cannot_lower_a_floor_by_declaring_one(pattern):
    """The floors are not declarable — a pattern that could set its own trend floor could lower it
    until it fired. `extra=forbid` on the condition is what makes that unwritable."""
    with pytest.raises(Exception):
        pattern(conditions=[{"kind": "trend", "metric": "m", "direction": "declining",
                             "min_confidence_bp": 100}])


# =================================================================================================
# Every satisfied condition carries evidence; determinism
# =================================================================================================

def test_every_satisfied_condition_carries_an_evidence_object(five, full_slice, eval_time):
    result = match(five, full_slice(), eval_time=eval_time)
    assert len(result.evidence) == len(five.conditions)
    for evidence in result.evidence:
        assert evidence.ref, f"condition {evidence.index} satisfied with no recoverable object"
        assert evidence.field_path


def test_a_satisfaction_with_no_evidence_object_is_a_failure():
    """`_evidenced` is the one place this rule lives. Called directly because the evaluator can no
    longer produce an unevidenced satisfaction — which is the point — so the guard would otherwise
    be unreachable and untested."""
    from genios_engine.context.patterns.contract import ConditionKind
    from genios_engine.context.patterns.matcher import FAIL_NO_EVIDENCE, _evidenced
    hollow = ConditionEvidence(index=0, kind=ConditionKind.FACT, field_path="x.y", operator="eq",
                               expected=1, observed=1, ref="")
    found, failure = _evidenced(hollow, 0, ConditionKind.FACT, "x.y")
    assert found is None
    assert failure.reason == FAIL_NO_EVIDENCE


def test_the_same_slice_and_eval_time_twice_produce_an_identical_result(five, full_slice,
                                                                        eval_time):
    """Byte-identical, through the record: clustering and the shadow diff compare these across
    runs, and an unstable order reads as the world having changed."""
    import json
    a = match(five, full_slice(), eval_time=eval_time)
    b = match(five, full_slice(), eval_time=eval_time)
    assert json.dumps(a.as_record(), sort_keys=True) == json.dumps(b.as_record(), sort_keys=True)


def test_matched_nodes_are_sorted_and_include_the_anchor(pattern, graph_slice, fact, eval_time):
    p = pattern(pattern_id="owned", conditions=[
        {"kind": "edge", "type": "owns", "from": "@anchor", "op": "present"}])
    world = graph_slice(edges=(SliceEdge("ev_2", "owns", "node_sub_aws", "node_zoe"),
                               SliceEdge("ev_1", "owns", "node_sub_aws", "node_amy")))
    result = match(p, world, eval_time=eval_time)
    assert result.matched_nodes == tuple(sorted(result.matched_nodes))
    assert "node_sub_aws" in result.matched_nodes
    # The deterministic pick is the lowest edge_version_id, not whichever the list held first.
    assert result.evidence[0].ref == "edge:ev_1"


def test_matched_node_order_does_not_come_from_a_set(pattern, graph_slice, eval_time):
    """The sortedness row, made falsifiable. `matched_nodes` is built from a set, and a set of
    three short strings frequently iterates in sorted order by luck — so the test that catches an
    unsorted output has to use enough nodes that luck is not available.

    This matters because `L2.7.3`'s clustering and the shadow diff both compare these tuples
    across runs: an order that depends on hashing reads as the world having changed.
    """
    edges = tuple(SliceEdge(f"ev_{i:02d}", "owns", "node_sub_aws", f"node_{i:02d}_zx")
                  for i in range(40))
    p = pattern(pattern_id="wide", conditions=[
        {"kind": "edge", "type": "owns", "from": "@anchor", "op": "present"}],
        optional_signals=[{"kind": "edge", "type": "owns", "from": "@anchor", "op": "present",
                           "weight_bp": 500}])
    result = match(p, graph_slice(edges=edges), eval_time=eval_time)
    assert result.matched_nodes == tuple(sorted(result.matched_nodes))
    assert result.matched_edges == tuple(sorted(result.matched_edges))


def test_the_anchor_type_is_the_first_and_cheapest_rejection(five, graph_slice, eval_time):
    outcome = evaluate(five, graph_slice(node_type="person"), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.reason == "anchor_type"


# =================================================================================================
# No clock, no float
# =================================================================================================

def test_the_module_reads_no_clock():
    """`eval_time` is a parameter. A pattern that fired differently on replay could not be
    reviewed, and reviewing a misfire is the whole remedy the registry offers."""
    from pathlib import Path
    import genios_engine.context.patterns.matcher as module
    source = Path(module.__file__).read_text()
    assert "datetime.now(" not in source
    assert "utcnow(" not in source


def test_a_naive_eval_time_is_refused(five, full_slice):
    from datetime import datetime
    with pytest.raises(ValueError):
        match(five, full_slice(), eval_time=datetime(2026, 3, 1, 9, 0))


def test_a_float_fact_value_is_refused_rather_than_rounded(five, full_slice, fact, eval_time):
    outcome = evaluate(five, full_slice(
        facts=(fact("subscription.status", "active"),
               fact("subscription.current_period_end", (eval_time + timedelta(days=9)).isoformat()),
               fact("contract.value", 8_400_000.5))), eval_time=eval_time)
    assert outcome.matched is None
    assert outcome.failure.reason == "fact_non_integer"


def test_true_does_not_equal_one(pattern, graph_slice, fact, eval_time):
    """`bool` is an `int` in Python, so a plain `==` makes a pattern fire on a field it was never
    written about."""
    p = pattern(conditions=[{"kind": "fact", "field": "subscription.auto_renews", "op": "eq",
                             "value": True}])
    assert match(p, graph_slice(facts=(fact("subscription.auto_renews", 1),)),
                 eval_time=eval_time) is None
    assert match(p, graph_slice(facts=(fact("subscription.auto_renews", True),)),
                 eval_time=eval_time) is not None


def test_a_json_encoded_value_compares_as_the_thing_it_encodes(pattern, graph_slice, fact,
                                                               eval_time):
    """Graph facts arrive through several writers; `"active"` and `active` are one fact."""
    p = pattern(conditions=[{"kind": "fact", "field": "subscription.status", "op": "eq",
                             "value": "active"}])
    assert match(p, graph_slice(facts=(fact("subscription.status", '"ACTIVE"'),)),
                 eval_time=eval_time) is not None


def test_an_older_than_days_condition_reads_the_past(pattern, graph_slice, fact, eval_time):
    p = pattern(pattern_id="silent", conditions=[
        {"kind": "temporal", "field": "thread.last_inbound", "op": "older_than_days",
         "value": 21}])
    stale = graph_slice(facts=(fact("thread.last_inbound",
                                    (eval_time - timedelta(days=30)).isoformat()),))
    fresh = graph_slice(facts=(fact("thread.last_inbound",
                                    (eval_time - timedelta(days=3)).isoformat()),))
    assert match(p, stale, eval_time=eval_time) is not None
    assert match(p, fresh, eval_time=eval_time) is None
    assert match(p, stale, eval_time=eval_time).evidence[0].observed == 30


def test_an_observation_outside_its_window_does_not_satisfy(pattern, graph_slice, observation,
                                                            eval_time):
    p = pattern(pattern_id="recent", conditions=[
        {"kind": "observation", "kind_name": "going_dark", "within_days": 30}])
    assert match(p, graph_slice(observations=(observation("going_dark", days_ago=90),)),
                 eval_time=eval_time) is None
    assert match(p, graph_slice(observations=(observation("going_dark", days_ago=10),)),
                 eval_time=eval_time) is not None


def test_a_trend_refusal_can_never_be_a_condition(pattern):
    """`INSUFFICIENT_COVERAGE` is "we cannot see enough of this to say". A pattern that fired on it
    would be a pattern that fires on our own blindness."""
    for refusal in (TrendDirection.INSUFFICIENT_COVERAGE, TrendDirection.INSUFFICIENT_HISTORY):
        with pytest.raises(Exception):
            pattern(conditions=[{"kind": "trend", "metric": "m", "direction": refusal.value}])
