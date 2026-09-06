"""L2.6.1-U3 · the six shipped patterns — a POSITIVE fixture and a NEGATIVE fixture for each.

Doc 06's group gate asks for six registered patterns; this file asks the harder question, which is
whether each one DISCRIMINATES. A pattern with only a positive fixture has been shown to fire and
has not been shown to be about anything: a pattern that matches every anchor passes a positive
fixture perfectly, and that is precisely the failure the fire-rate guard exists for.

Each negative row is the specific way that pattern would be WRONG, not an arbitrary non-match.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.context.patterns.matcher import match
from genios_engine.context.patterns.registry import seed_registry
from genios_engine.context.patterns.slice import SliceEdge
from genios_engine.contracts.analytic import TrendDirection
from genios_engine.contracts.quality import AbsenceType


@pytest.fixture
def seed():
    return seed_registry()


# =================================================================================================
# commitment_unresolved — fact + temporal + absence
# =================================================================================================

def _commitment_world(graph_slice, fact, absent, eval_time, **overrides):
    base = dict(
        node_type="commitment", node_id="node_cmt_1",
        facts=(fact("commitment.status", "open", node_id="node_cmt_1"),
               fact("commitment.due_at", (eval_time - timedelta(days=9)).isoformat(),
                    node_id="node_cmt_1")),
        absences=(absent("commitment.delivered_at", AbsenceType.GENUINELY_ABSENT,
                         node_id="node_cmt_1"),))
    base.update(overrides)
    return graph_slice(**base)


def test_commitment_unresolved_fires(seed, graph_slice, fact, absent, eval_time):
    result = match(seed.get("commitment_unresolved"),
                   _commitment_world(graph_slice, fact, absent, eval_time), eval_time=eval_time)
    assert result is not None
    assert result.situation_type == "commitment_unresolved"
    assert len(result.evidence) == 3


def test_commitment_unresolved_holds_off_when_delivery_is_unknowable(seed, graph_slice, fact,
                                                                     absent, eval_time):
    """THE negative row for this pattern. An org whose delivery evidence lives in a tool we do not
    read would otherwise have every promise it ever made reported as broken."""
    world = _commitment_world(graph_slice, fact, absent, eval_time,
                              absences=(absent("commitment.delivered_at", AbsenceType.UNKNOWABLE,
                                                node_id="node_cmt_1"),))
    assert match(seed.get("commitment_unresolved"), world, eval_time=eval_time) is None


def test_commitment_unresolved_ignores_a_promise_not_yet_due(seed, graph_slice, fact, absent,
                                                             eval_time):
    world = _commitment_world(graph_slice, fact, absent, eval_time,
                              facts=(fact("commitment.status", "open", node_id="node_cmt_1"),
                                     fact("commitment.due_at",
                                          (eval_time - timedelta(days=1)).isoformat(),
                                          node_id="node_cmt_1")))
    assert match(seed.get("commitment_unresolved"), world, eval_time=eval_time) is None


# =================================================================================================
# relationship_going_cold — trend + cohort
# =================================================================================================

def test_relationship_going_cold_fires(seed, graph_slice, fact, trend, position, eval_time):
    world = graph_slice(node_type="company", node_id="node_acct_north",
                        facts=(fact("account.status", "active", node_id="node_acct_north"),),
                        trends=(trend(),), cohort_positions=(position(percentile_bp=1200),))
    result = match(seed.get("relationship_going_cold"), world, eval_time=eval_time)
    assert result is not None
    # Both analytic conditions carry their own receipt, and the cohort's names its population —
    # a percentile whose cohort is unnamed cannot be checked or reproduced.
    cohort_evidence = dict(result.evidence[2].record)
    assert cohort_evidence["cohort_id"] == "coh_seed_accounts"
    assert cohort_evidence["population_size"] == 20


def test_relationship_going_cold_refuses_a_thin_cohort(seed, graph_slice, fact, trend, position,
                                                       eval_time):
    """A bottom-decile position over four peers is a comparison nobody should act on, and Law 2
    makes it unconstructible — so the refusal is proven where it can be built: the position exists,
    the pattern still needs the population floor."""
    world = graph_slice(node_type="company", node_id="node_acct_north",
                        facts=(fact("account.status", "active", node_id="node_acct_north"),),
                        trends=(trend(),), cohort_positions=())
    assert match(seed.get("relationship_going_cold"), world, eval_time=eval_time) is None


def test_relationship_going_cold_does_not_fire_on_a_churned_account(seed, graph_slice, fact,
                                                                    trend, position, eval_time):
    """Without `account.status = active` this fires on every account that ever left, forever."""
    world = graph_slice(node_type="company", node_id="node_acct_north",
                        facts=(fact("account.status", "churned", node_id="node_acct_north"),),
                        trends=(trend(),), cohort_positions=(position(),))
    assert match(seed.get("relationship_going_cold"), world, eval_time=eval_time) is None


def test_relationship_going_cold_does_not_fire_on_an_org_wide_silence(seed, graph_slice, fact,
                                                                      trend, position, eval_time):
    """H6's false-churn row, from the pattern's side: a trend that could not be computed
    confidently is not a decline, and `INSUFFICIENT_COVERAGE` is not registrable as a direction
    at all — so the only way this pattern can fire is on a trend that says DECLINING and means it.
    """
    unsure = graph_slice(node_type="company", node_id="node_acct_north",
                         facts=(fact("account.status", "active", node_id="node_acct_north"),),
                         trends=(trend(confidence_bp=3000),),
                         cohort_positions=(position(),))
    assert match(seed.get("relationship_going_cold"), unsure, eval_time=eval_time) is None
    rising = graph_slice(node_type="company", node_id="node_acct_north",
                         facts=(fact("account.status", "active", node_id="node_acct_north"),),
                         trends=(trend(direction=TrendDirection.RISING),),
                         cohort_positions=(position(),))
    assert match(seed.get("relationship_going_cold"), rising, eval_time=eval_time) is None


# =================================================================================================
# meeting_preparation_gap
# =================================================================================================

def test_meeting_preparation_gap_fires(seed, graph_slice, fact, absent, eval_time):
    world = graph_slice(
        node_type="meeting", node_id="node_meet_1",
        facts=(fact("meeting.status", "confirmed", node_id="node_meet_1"),
               fact("meeting.start_at", (eval_time + timedelta(days=1)).isoformat(),
                    node_id="node_meet_1")),
        absences=(absent("meeting.agenda", AbsenceType.GENUINELY_ABSENT, node_id="node_meet_1"),))
    assert match(seed.get("meeting_preparation_gap"), world, eval_time=eval_time) is not None


def test_meeting_preparation_gap_ignores_a_meeting_already_held(seed, graph_slice, fact, absent,
                                                                eval_time):
    """`within_days` is future-only, so a meeting last Tuesday cannot produce "you have two days
    to prepare"."""
    world = graph_slice(
        node_type="meeting", node_id="node_meet_1",
        facts=(fact("meeting.status", "confirmed", node_id="node_meet_1"),
               fact("meeting.start_at", (eval_time - timedelta(days=6)).isoformat(),
                    node_id="node_meet_1")),
        absences=(absent("meeting.agenda", AbsenceType.GENUINELY_ABSENT, node_id="node_meet_1"),))
    assert match(seed.get("meeting_preparation_gap"), world, eval_time=eval_time) is None


def test_meeting_preparation_gap_ignores_a_cancelled_meeting(seed, graph_slice, fact, absent,
                                                             eval_time):
    world = graph_slice(
        node_type="meeting", node_id="node_meet_1",
        facts=(fact("meeting.status", "cancelled", node_id="node_meet_1"),
               fact("meeting.start_at", (eval_time + timedelta(days=1)).isoformat(),
                    node_id="node_meet_1")),
        absences=(absent("meeting.agenda", AbsenceType.GENUINELY_ABSENT, node_id="node_meet_1"),))
    assert match(seed.get("meeting_preparation_gap"), world, eval_time=eval_time) is None


# =================================================================================================
# founder_bottleneck — the Authority view's own reading
# =================================================================================================

def test_founder_bottleneck_fires(seed, graph_slice, fact, eval_time):
    world = graph_slice(
        node_type="person", node_id="node_rohit",
        facts=(fact("authority.sole_approver_subject_count", 4, node_id="node_rohit"),
               fact("authority.undelegated_subject_count", 2, node_id="node_rohit")))
    result = match(seed.get("founder_bottleneck"), world, eval_time=eval_time)
    assert result is not None
    assert result.evidence[0].observed == 4


def test_founder_bottleneck_ignores_a_delegated_approver(seed, graph_slice, fact, eval_time):
    """Sole approver for four classes, every one of them delegated: structurally fine, and the
    whole point of the Bottleneck surface is the classes with NO escape hatch."""
    world = graph_slice(
        node_type="person", node_id="node_rohit",
        facts=(fact("authority.sole_approver_subject_count", 4, node_id="node_rohit"),
               fact("authority.undelegated_subject_count", 0, node_id="node_rohit")))
    assert match(seed.get("founder_bottleneck"), world, eval_time=eval_time) is None


# =================================================================================================
# condition_now_satisfied — L2.3.4's two-span fact
# =================================================================================================

def test_condition_now_satisfied_fires(seed, graph_slice, fact, eval_time):
    world = graph_slice(
        node_type="person", node_id="node_priya",
        facts=(fact("derived.timeline.condition_satisfied", '{"statement": "..."}',
                    node_id="node_priya"),
               fact("thread.ball_in_court", "us", node_id="node_priya")))
    assert match(seed.get("condition_now_satisfied"), world, eval_time=eval_time) is not None


def test_condition_now_satisfied_ignores_their_move(seed, graph_slice, fact, eval_time):
    """A condition that came true on the other side of the exchange is their move, not ours."""
    world = graph_slice(
        node_type="person", node_id="node_priya",
        facts=(fact("derived.timeline.condition_satisfied", '{"statement": "..."}',
                    node_id="node_priya"),
               fact("thread.ball_in_court", "them", node_id="node_priya")))
    assert match(seed.get("condition_now_satisfied"), world, eval_time=eval_time) is None


# =================================================================================================
# vendor_renewal_unowned — Globe's worked example, five conditions
# =================================================================================================

def _renewal_world(graph_slice, fact, absent, eval_time, **overrides):
    base = dict(
        node_type="subscription", node_id="node_sub_aws",
        facts=(fact("subscription.status", "active"),
               fact("subscription.current_period_end",
                    (eval_time + timedelta(days=12)).isoformat()),
               fact("contract.value", 8_400_000)),
        absences=(absent("decision.scheduled", AbsenceType.GENUINELY_ABSENT),),
        edge_coverage=("owns",), authority_threshold_minor_units=5_000_000,
        authority_rule_id="authr_finance")
    base.update(overrides)
    return graph_slice(**base)


def test_vendor_renewal_unowned_fires_on_all_five(seed, graph_slice, fact, absent, eval_time):
    result = match(seed.get("vendor_renewal_unowned"),
                   _renewal_world(graph_slice, fact, absent, eval_time), eval_time=eval_time)
    assert result is not None
    assert len(result.evidence) == 5, "six things co-occurring is what an anchor type cannot say"
    assert result.situation_type == "vendor_renewal_decision"


@pytest.mark.parametrize("break_it, why", [
    ({"facts": ()}, "no status, no window, no value"),
    ({"edges": (SliceEdge("ev_own", "owns", "node_sub_aws", "node_rohit"),)}, "it has an owner"),
    ({"absences": ()}, "no typed answer about a scheduled decision"),
    ({"edge_coverage": ()}, "the absence of an owner edge is unknowable here"),
    ({"authority_threshold_minor_units": None}, "no approval threshold in force"),
])
def test_vendor_renewal_unowned_needs_every_condition(seed, graph_slice, fact, absent, eval_time,
                                                      break_it, why):
    """Five rows, one per condition. This is the test that distinguishes a pattern from a filter."""
    world = _renewal_world(graph_slice, fact, absent, eval_time, **break_it)
    assert match(seed.get("vendor_renewal_unowned"), world, eval_time=eval_time) is None, why


# =================================================================================================
# Overlap — patterns MAY overlap; situations must not
# =================================================================================================

def test_two_patterns_over_one_entity_produce_two_matches_that_share_it(seed, graph_slice, fact,
                                                                        absent, eval_time):
    """Doc 06: *"patterns may overlap, situations must not"*, and the mitigation is L2.7.3's
    deterministic shared-entity clustering — which lives in `context/situations.py` and is not
    this package's to write.

    What this package owes is the PRECONDITION for that merge: two matches over one reality must
    name the same entity, or nothing downstream can merge them. Two patterns anchored on the same
    node produce matches whose `matched_nodes` intersect, which is exactly the key BLG-17 groups
    on.
    """
    person = graph_slice(
        node_type="person", node_id="node_rohit",
        facts=(fact("authority.sole_approver_subject_count", 4, node_id="node_rohit"),
               fact("authority.undelegated_subject_count", 2, node_id="node_rohit"),
               fact("derived.timeline.condition_satisfied", "{}", node_id="node_rohit"),
               fact("thread.ball_in_court", "us", node_id="node_rohit")))
    bottleneck = match(seed.get("founder_bottleneck"), person, eval_time=eval_time)
    satisfied = match(seed.get("condition_now_satisfied"), person, eval_time=eval_time)
    assert bottleneck is not None and satisfied is not None
    shared = set(bottleneck.matched_nodes) & set(satisfied.matched_nodes)
    assert shared == {"node_rohit"}
    assert bottleneck.situation_type != satisfied.situation_type


# =================================================================================================
# Every seed pattern is evaluable end to end
# =================================================================================================

def test_every_seed_pattern_carries_evidence_for_every_required_condition(seed, graph_slice, fact,
                                                                          absent, trend, position,
                                                                          eval_time):
    """One assertion over all six: whatever fires, fires with a full receipt. A pattern that
    matched and could not say why would break the contract with Layer 3 for that one situation
    only, which is the kind of gap a per-pattern test set misses."""
    worlds = [
        _commitment_world(graph_slice, fact, absent, eval_time),
        _renewal_world(graph_slice, fact, absent, eval_time),
        graph_slice(node_type="company", node_id="node_acct_north",
                    facts=(fact("account.status", "active", node_id="node_acct_north"),),
                    trends=(trend(),), cohort_positions=(position(),)),
        graph_slice(node_type="person", node_id="node_rohit",
                    facts=(fact("authority.sole_approver_subject_count", 4, node_id="node_rohit"),
                           fact("authority.undelegated_subject_count", 2, node_id="node_rohit"),
                           fact("derived.timeline.condition_satisfied", "{}",
                                node_id="node_rohit"),
                           fact("thread.ball_in_court", "us", node_id="node_rohit"))),
        graph_slice(node_type="meeting", node_id="node_meet_1",
                    facts=(fact("meeting.status", "confirmed", node_id="node_meet_1"),
                           fact("meeting.start_at", (eval_time + timedelta(days=1)).isoformat(),
                                node_id="node_meet_1")),
                    absences=(absent("meeting.agenda", AbsenceType.GENUINELY_ABSENT,
                                     node_id="node_meet_1"),)),
    ]
    fired = set()
    for pattern in seed.all():
        for world in worlds:
            result = match(pattern, world, eval_time=eval_time)
            if result is None:
                continue
            fired.add(pattern.pattern_id)
            assert len(result.evidence) == len(pattern.conditions)
            for evidence in result.evidence:
                assert evidence.ref
    assert fired == {p.pattern_id for p in seed.all()}, "every shipped pattern has a world it fires in"
