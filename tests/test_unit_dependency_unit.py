"""Executable contract for the Dependency Unit — "what is blocked by what?".

The whole value of this unit is that it refuses to confuse three things that look identical from
the outside: work that is free to start, work that is blocked, and work whose blockage nobody
looked at. Most of these tests exist to keep those three apart under pressure.

The rest pin the properties that make the unit safe to compose: it observes and never decides, it
publishes no reserved shared metric, and the same situation always yields the same numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.common import active_spec
from genios_engine.reason.reasoners.dependency_unit import (
    ApprovalGatePlugin,
    DependencyUnit,
    PrerequisiteAbsencePlugin,
    UpstreamOwnerPlugin,
)
from genios_engine.reason.unit import Observation, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _request(facts=None, *, config=None, required_fields=(), evidence=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.enterprise_renewal",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("close_renewal", "Close the enterprise renewal before it lapses"),
        reasoners=(ReasonerSpec("core.dependency", "1.0.0", config=config or {}),),
        plays=(PlayDefinition(play_id="chase_legal", version="1", label="Chase Legal",
                              steps=("Ask the reviewer for a decision date",)),),
        required_fields=tuple(required_fields),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=42,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=dict(facts or {}),
        evidence=tuple(evidence),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="crm.deal_updated",
    )


def _view(facts=None, *, config=None, required_fields=(), evidence=()) -> UnitView:
    request = _request(facts, config=config, required_fields=required_fields, evidence=evidence)
    return UnitView(request=request, spec=active_spec(request, "core.dependency"), prior={})


def _by_kind(observations):
    return {item.kind: item for item in observations}


def _blocker(severity_bp: int, *, depth: int = 1, hard: int = 0) -> Observation:
    return Observation(plugin_id="test", kind="dependency.synthetic",
                       metrics={"blocked": 1, "inspected": 1, "depth": depth,
                                "severity_bp": severity_bp, "hard": hard})


# ---------------------------------------------------------------------------------------------
# Approval and gate blockers
# ---------------------------------------------------------------------------------------------

def test_a_gate_awaiting_a_decision_is_a_blocker_this_workflow_can_chase():
    """A pending review is invisible to every activity metric; if this unit misses it, nobody sees it."""
    observations = ApprovalGatePlugin().contribute(
        _view({"legal.review_status": "in_review"}))

    assert len(observations) == 1
    blocker = observations[0]
    assert blocker.kind == "dependency.gate_pending"
    assert blocker.metrics["blocked"] == 1
    assert blocker.metrics["depth"] == 1          # ours to chase, not somebody else's to release
    assert blocker.metrics["hard"] == 0
    assert "gate_awaiting_decision" in blocker.reason_codes
    assert "blocker:legal.review_status" in blocker.reason_codes


def test_a_refused_gate_is_hard_because_waiting_will_never_clear_it():
    """Rejection is not a queue — reporting it like a pending item would suggest patience works."""
    observations = ApprovalGatePlugin().contribute(
        _view({"security.review_status": "rejected"}))

    assert observations[0].kind == "dependency.gate_rejected"
    assert observations[0].metrics["severity_bp"] == 10_000
    assert observations[0].metrics["hard"] == 1
    assert observations[0].metrics["depth"] == 2   # someone else must change their mind first


def test_an_unrecognised_gate_status_produces_no_claim_at_all():
    """We do not know what "escalated" means for this tenant, and "probably fine" is a fabrication."""
    assert ApprovalGatePlugin().contribute(
        _view({"approval.status": "escalated"},
              config={"gate_fields": ["approval.status"]})) == ()


def test_cleared_gates_are_recorded_as_inspection_rather_than_silence():
    """"Five gates checked, all clear" must never come out looking like "no gates were checked"."""
    observations = ApprovalGatePlugin().contribute(
        _view({"approval.status": "approved", "legal.review_status": "waived"}))

    assert len(observations) == 1
    assert observations[0].kind == "dependency.gates_cleared"
    assert observations[0].metrics["blocked"] == 0
    assert observations[0].metrics["inspected"] == 2


def test_gate_status_wording_is_normalised_before_it_is_matched():
    """CRM exports write "In Review", "in-review" and "in_review" for one state; all three block."""
    for wording in ("In Review", "in-review", "IN_REVIEW"):
        observations = ApprovalGatePlugin().contribute(
            _view({"legal.review_status": wording}))
        assert observations[0].kind == "dependency.gate_pending", wording


# ---------------------------------------------------------------------------------------------
# Absent prerequisites
# ---------------------------------------------------------------------------------------------

def test_a_declared_prerequisite_that_is_missing_blocks_and_a_present_one_does_not():
    observations = _by_kind(PrerequisiteAbsencePlugin().contribute(
        _view({"deal.renewal_date": "2026-09-30"},
              required_fields=("deal.renewal_date", "deal.signatory_email"))))

    absent = observations["dependency.prerequisite_absent"]
    assert "blocker:deal.signatory_email" in absent.reason_codes
    assert absent.metrics["depth"] == 1           # we can go and fetch a fact ourselves
    assert observations["dependency.prerequisites_met"].metrics["inspected"] == 1


def test_a_null_placeholder_is_treated_as_an_absent_prerequisite():
    """L2 writes nulls for fields it tried and failed to resolve; a present key is not a value."""
    observations = PrerequisiteAbsencePlugin().contribute(
        _view({"deal.signatory_email": None},
              required_fields=("deal.signatory_email",)))

    assert observations[0].kind == "dependency.prerequisite_absent"


def test_a_capability_that_declared_no_prerequisites_gets_none_invented():
    """Nothing was stated as needed, so nothing can honestly be called missing."""
    assert PrerequisiteAbsencePlugin().contribute(_view({"deal.status": "open"})) == ()


def test_layer_three_may_name_the_prerequisites_itself():
    """A capability whose real preconditions differ from its context requirements can say so."""
    observations = PrerequisiteAbsencePlugin().contribute(
        _view({"deal.renewal_date": "2026-09-30"},
              config={"prerequisite_fields": ["contract.countersigned_at"]},
              required_fields=("deal.renewal_date",)))

    assert len(observations) == 1
    assert "blocker:contract.countersigned_at" in observations[0].reason_codes


# ---------------------------------------------------------------------------------------------
# Upstream owner blockers
# ---------------------------------------------------------------------------------------------

def test_work_with_nobody_assigned_is_blocked_for_want_of_hands():
    observations = _by_kind(UpstreamOwnerPlugin().contribute(_view({"deal.owner": ""})))

    assert observations["dependency.owner_unassigned"].metrics["depth"] == 1
    assert observations["dependency.owner_unassigned"].metrics["hard"] == 0


def test_an_owner_field_l2_never_supplied_is_not_read_as_unassigned():
    """Absent evidence is not evidence of absence; the silent case must stay silent."""
    assert UpstreamOwnerPlugin().contribute(_view({"deal.status": "open"})) == ()


def test_an_unavailable_owner_deepens_the_chain_only_when_a_gate_waits_on_them():
    """Depth 2 is a claim about structure: it needs a second link actually present in the facts."""
    alone = _by_kind(UpstreamOwnerPlugin().contribute(
        _view({"deal.owner": "rep_amara", "owner.availability": "out_of_office"})))
    chained = _by_kind(UpstreamOwnerPlugin().contribute(
        _view({"deal.owner": "rep_amara", "owner.availability": "out_of_office",
               "legal.review_status": "pending"})))

    assert alone["dependency.owner_unavailable"].metrics["depth"] == 1
    assert chained["dependency.owner_unavailable"].metrics["depth"] == 2
    assert "blocked_gate_has_no_decider" in chained["dependency.owner_unavailable"].reason_codes


def test_a_named_upstream_party_is_two_links_away_by_construction():
    observations = _by_kind(UpstreamOwnerPlugin().contribute(
        _view({"deal.blocked_by": "customer_procurement"})))

    upstream = observations["dependency.upstream_party"]
    assert upstream.metrics["depth"] == 2
    assert upstream.metrics["hard"] == 1          # not ours to release


def test_a_healthy_owner_records_the_inspection_it_performed():
    observations = _by_kind(UpstreamOwnerPlugin().contribute(
        _view({"deal.owner": "rep_amara", "owner.availability": "active"})))

    assert observations["dependency.ownership_clear"].metrics["inspected"] == 2
    assert "dependency.owner_unavailable" not in observations


# ---------------------------------------------------------------------------------------------
# The arithmetic: shape of blockage, not sum of complaints
# ---------------------------------------------------------------------------------------------

def test_the_worst_blocker_governs_and_the_others_add_bounded_drag():
    """Summing severities would call three mild blockers more impossible than one absolute wall."""
    metrics = DependencyUnit().calculate(
        _view(), [_blocker(8_000), _blocker(4_000), _blocker(2_000)])

    # 10000 - 8000 - (6000 / 4) = 500, not 10000 - 14000 = 0.
    assert metrics["unblocked_bp"] == 500
    assert metrics["blocker_severity_bp"] == 8_000
    assert metrics["blocked_count"] == 3


def test_blocking_depth_reports_the_longest_chain_not_how_many_things_are_wrong():
    metrics = DependencyUnit().calculate(
        _view(), [_blocker(3_000), _blocker(3_000), _blocker(3_000, depth=2, hard=1)])

    assert metrics["blocking_depth"] == 2
    assert metrics["blocked_count"] == 3
    assert metrics["hard_blocked_count"] == 1


def test_an_upstream_chain_costs_more_than_the_same_severity_held_in_house():
    """Being unable to act yourself is materially worse than having work to do."""
    in_house = DependencyUnit().calculate(_view(), [_blocker(5_000, depth=1)])
    upstream = DependencyUnit().calculate(_view(), [_blocker(5_000, depth=2)])

    assert in_house["unblocked_bp"] == 5_000
    assert upstream["unblocked_bp"] == 3_500     # flat 1500bp depth penalty


# ---------------------------------------------------------------------------------------------
# Clear versus blind — the distinction the unit exists to preserve
# ---------------------------------------------------------------------------------------------

def test_nothing_inspected_is_never_reported_as_nothing_blocking():
    """The most dangerous output this unit could produce is a confident all-clear from no evidence."""
    result = DependencyUnit().evaluate(_request({"deal.status": "open"}), {})

    assert result.metrics["inspected_count"] == 0
    assert result.metrics["unblocked_bp"] == 10_000   # no blockage was demonstrated...
    assert result.reason_codes == ("dependency_not_observable",)   # ...and none could have been
    assert result.matched is False


def test_a_genuinely_clear_situation_is_distinguishable_from_a_blind_run():
    result = DependencyUnit().evaluate(
        _request({"approval.status": "approved", "legal.review_status": "signed",
                  "deal.owner": "rep_amara", "owner.availability": "active"}), {})

    assert result.metrics["blocked_count"] == 0
    assert result.metrics["inspected_count"] == 4
    assert result.reason_codes == ("no_blocking_dependency_observed",)


# ---------------------------------------------------------------------------------------------
# Composition safety
# ---------------------------------------------------------------------------------------------

def test_the_unit_publishes_no_reserved_shared_metric():
    """core.confidence and core.priority own these; a second writer silently re-scores everything."""
    result = DependencyUnit().evaluate(
        _request({"legal.review_status": "pending", "deal.owner": ""}), {})

    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}
    assert reserved.isdisjoint(DependencyUnit.publishes)
    assert reserved.isdisjoint(result.metrics)


def test_the_unit_reports_blockage_without_ranking_or_eliminating_anything():
    """Blocked does not mean "do not act" — deciding that is Part 3's job, and only Part 3's."""
    result = DependencyUnit().evaluate(
        _request({"security.review_status": "rejected"}), {})

    assert result.matched is True
    assert result.adjustments == ()      # never moves a play's score
    assert result.checks == ()           # never eliminates a play


def test_every_published_metric_is_declared():
    result = DependencyUnit().evaluate(_request({"legal.review_status": "pending"}), {})

    assert set(result.metrics) <= set(DependencyUnit.publishes)


def test_the_same_situation_twice_produces_identical_metrics():
    """Replayability is the reason none of this may touch a clock, a model, or a random source."""
    facts = {"legal.review_status": "in_review", "deal.owner": "rep_amara",
             "owner.availability": "out_of_office", "deal.blocked_by": "customer_procurement"}

    first = DependencyUnit().evaluate(_request(facts), {})
    second = DependencyUnit().evaluate(_request(facts), {})

    assert dict(first.metrics) == dict(second.metrics)
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


def test_findings_keep_a_stable_identity_when_another_blocker_clears():
    """Findings are compared across runs; a positional id would make every clearance look like churn."""
    both = DependencyUnit().evaluate(
        _request({"legal.review_status": "pending", "deal.owner": ""}), {})
    one = DependencyUnit().evaluate(
        _request({"legal.review_status": "pending", "deal.owner": "rep_amara"}), {})

    surviving = "dependency.approval_gate.legal.review_status"
    assert surviving in {item.finding_id for item in both.findings}
    assert {item.finding_id for item in one.findings} == {surviving}


def test_configuration_that_is_not_basis_points_is_a_manifest_fault():
    """Bad tuning must fail loudly at Layer 3 rather than quietly skew every renewal decision."""
    with pytest.raises(ValueError, match="integer basis points"):
        ApprovalGatePlugin().contribute(
            _view({"legal.review_status": "pending"},
                  config={"gate_pending_severity_bp": 20_000}))


def test_the_unit_satisfies_the_reasoner_protocol():
    assert isinstance(DependencyUnit(), Reasoner)


# ---------------------------------------------------------------------------------------------
# One real situation, end to end
# ---------------------------------------------------------------------------------------------

def test_a_stalled_enterprise_renewal_reports_its_whole_blocking_graph():
    """Acme's renewal: legal is still reviewing, the only person who can push legal is on leave,
    and we still do not have the signatory's address. Three blockers, one chain two links long,
    and no freedom to proceed — the exact situation where a value-only unit would cheerfully
    recommend "send the renewal pack today"."""
    facts = {
        "deal.renewal_date": "2026-09-30",
        "approval.status": "approved",
        "legal.review_status": "in_review",
        "deal.owner": "rep_amara",
        "owner.availability": "on_leave",
    }
    evidence = (
        EvidenceRef(evidence_id="ev_legal", field="legal.review_status", value="in_review"),
        EvidenceRef(evidence_id="ev_owner", field="owner.availability", value="on_leave"),
    )
    request = _request(facts, required_fields=("deal.renewal_date", "deal.signatory_email"),
                       evidence=evidence)

    result = DependencyUnit().evaluate(request, {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is True
    assert result.metrics["blocked_count"] == 3
    assert result.metrics["blocking_depth"] == 2        # legal → the person who is not there
    assert result.metrics["hard_blocked_count"] == 1
    assert result.metrics["blocker_severity_bp"] == 7_000
    # 10000 - 7000 - ((6000 + 5000) / 4) - 1500 depth penalty → below zero, clamped.
    assert result.metrics["unblocked_bp"] == 0
    assert result.metrics["inspected_count"] == 6       # 2 gates, 2 prerequisites, 2 owner facts
    assert result.reason_codes == (
        "blocked_gate_has_no_decider", "gate_awaiting_decision",
        "owner_unavailable", "prerequisite_not_available")
    assert result.evidence_ids == ("ev_legal", "ev_owner")
    assert {item.finding_id for item in result.findings} == {
        "dependency.approval_gate.legal.review_status",
        "dependency.prerequisite_absent.deal.signatory_email",
        "dependency.upstream_owner.owner.availability",
    }
