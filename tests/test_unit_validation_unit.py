"""Executable contract for the Validation Unit — "is this reasoning safe to act on?".

This unit is the last thing between a run and synthesis, so most of these tests defend one of three
properties:

* **It catches what nothing downstream catches.** Two units disagreeing on the same quantity, a
  claim nobody can retrace, a basis older than the world it describes.
* **It stays silent where it has no grounds.** A run it did not inspect is never reported as
  validated, and an absent reading is never a fabricated zero — those two mistakes are what would
  make the unit dangerous rather than useful.
* **It vetoes, it never chooses.** The one authority it holds is a symmetric safety elimination.
  It must never rank, adjust, or prefer a play, and must never eliminate on the strength of having
  looked at nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    EvidenceRef,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.common import active_spec
from genios_engine.reason.reasoners.validation_unit import (
    ContradictionPlugin,
    EvidenceSufficiencyPlugin,
    StalenessPlugin,
    ValidationUnit,
)
from genios_engine.reason.unit import Observation, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
LONG_AGO = datetime(2026, 5, 1, 9, tzinfo=timezone.utc)          # 2,331 hours before NOW
FACTS = {"deal.status": "open", "deal.last_inbound": "2026-05-01T09:00:00+00:00",
         "deal.owner": "rep_amara"}


def _play(play_id: str) -> PlayDefinition:
    return PlayDefinition(play_id=play_id, version="1", label=play_id.replace("_", " ").title(),
                          steps=("Draft a grounded reply",))


def _request(*, facts=None, evidence=(), config=None, plays=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.validation", "1.0.0", config=config or {}),),
        plays=tuple(plays or (_play("restore_momentum"),)),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=42,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=dict(FACTS if facts is None else facts),
        evidence=tuple(evidence),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
    )


def _view(prior=None, **kwargs) -> UnitView:
    request = _request(**kwargs)
    return UnitView(request=request, spec=active_spec(request, "core.validation"),
                    prior=dict(prior or {}))


def _completed(reasoner_id, *, matched=None, metrics=None, findings=(),
               evidence_ids=()) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=matched,
                          metrics=dict(metrics or {}), findings=tuple(findings),
                          evidence_ids=tuple(evidence_ids))


def _evidence(evidence_id, field="deal.last_inbound", *, occurred_at=None) -> EvidenceRef:
    return EvidenceRef(evidence_id=evidence_id, field=field, value=FACTS[field],
                       occurred_at=occurred_at)


def _contradiction(severity_bp: int) -> Observation:
    return Observation(plugin_id="test", kind="validation.synthetic",
                       metrics={"contradiction": 1, "severity_bp": severity_bp})


def _sufficiency(claims: int, grounded: int, *, inspected: int = 2) -> Observation:
    return Observation(plugin_id="evidence_sufficiency", kind="validation.evidence_sufficiency",
                       metrics={"inspected_results": inspected, "claims": claims,
                                "grounded": grounded})


# ---------------------------------------------------------------------------------------------
# Contradiction — the fault with no downstream remedy
# ---------------------------------------------------------------------------------------------

def test_two_units_far_apart_on_one_quantity_is_a_contradiction_nobody_else_will_catch():
    """The Decision Maker consumes whichever value it reads; neither unit can see the other."""
    observations = ContradictionPlugin().contribute(_view({
        "core.risk": _completed("core.risk", metrics={"risk_bp": 9_200}),
        "legacy.rule": _completed("legacy.rule", metrics={"risk_bp": 1_000}),
    }))

    assert len(observations) == 1
    clash = observations[0]
    assert clash.kind == "validation.metric_divergence"
    assert clash.metrics["gap_bp"] == 8_200
    assert clash.metrics["severity_bp"] == 8_200     # severity is the size of the disagreement
    assert "units_disagree_on_metric" in clash.reason_codes
    assert "metric:risk_bp" in clash.reason_codes
    assert {"publisher:core.risk", "publisher:legacy.rule"} <= set(clash.reason_codes)


def test_two_close_readings_of_one_quantity_are_opinions_not_a_clash():
    """Units are expected to differ slightly; flagging that would bury the genuine breaks in noise."""
    assert ContradictionPlugin().contribute(_view({
        "core.risk": _completed("core.risk", metrics={"risk_bp": 6_000}),
        "legacy.rule": _completed("legacy.rule", metrics={"risk_bp": 4_500}),
    })) == ()


def test_metrics_with_a_declared_authority_are_never_reported_as_contradictions():
    """Several units observe confidence and exactly one publishes it — that is the design working."""
    assert ContradictionPlugin().contribute(_view({
        "legacy.rule": _completed("legacy.rule", metrics={"confidence_bp": 3_000}),
        "core.confidence": _completed("core.confidence", metrics={"confidence_bp": 9_100}),
    })) == ()


def test_two_units_reaching_opposite_verdicts_on_the_same_subject_contradict():
    observations = ContradictionPlugin().contribute(_view({
        "core.temporal": _completed("core.temporal", findings=(
            Finding("temporal.cooling", "temporal", matched=True),)),
        "core.momentum": _completed("core.momentum", findings=(
            Finding("momentum.healthy", "temporal", matched=False),)),
    }))

    assert observations[0].kind == "validation.verdict_clash"
    assert observations[0].metrics["severity_bp"] == 8_000
    assert "kind:temporal" in observations[0].reason_codes


def test_one_unit_reporting_both_polarities_is_describing_a_mixed_situation():
    """A unit that finds two gates clear and one blocked is doing its job, not contradicting itself."""
    assert ContradictionPlugin().contribute(_view({
        "core.dependency": _completed("core.dependency", findings=(
            Finding("dependency.gate_a", "dependency", matched=True),
            Finding("dependency.gate_b", "dependency", matched=False))),
        "core.context": _completed("core.context", metrics={"completeness_bp": 7_000}),
    })) == ()


def test_a_unit_that_did_not_complete_cannot_be_cited_as_the_second_voice():
    """A failed unit has no opinion; treating its silence as disagreement would invent a fault."""
    assert ContradictionPlugin().contribute(_view({
        "core.risk": _completed("core.risk", metrics={"risk_bp": 9_200}),
        "core.relationship": ReasonerResult("core.relationship", "1", ResultStatus.FAILED,
                                            reason_codes=("reasoner_failure",)),
    })) == ()


# ---------------------------------------------------------------------------------------------
# Evidence sufficiency — can a human retrace this?
# ---------------------------------------------------------------------------------------------

def test_a_claim_citing_nothing_is_reported_by_the_unit_that_made_it():
    """"3 of 5 claims ungrounded" is a metric; "core.opportunity cited nothing" is actionable."""
    observations = EvidenceSufficiencyPlugin().contribute(
        _view({"core.opportunity": _completed("core.opportunity", matched=True)},
              evidence=(_evidence("ev_inbound"),)))

    ungrounded = [item for item in observations if item.kind == "validation.ungrounded_claim"]
    assert len(ungrounded) == 1
    assert "claimant:core.opportunity" in ungrounded[0].reason_codes


def test_a_citation_this_snapshot_cannot_produce_is_not_grounding():
    """A reviewer who follows the reference finds nothing, which is the same as finding no reference."""
    observations = EvidenceSufficiencyPlugin().contribute(
        _view({"core.risk": _completed("core.risk", matched=True, evidence_ids=("ev_ghost",))},
              evidence=(_evidence("ev_inbound"),)))

    assert any(item.kind == "validation.ungrounded_claim" for item in observations)


def test_a_unit_that_only_reported_numbers_is_not_asked_to_cite_anything():
    """Publishing elapsed_hours is an observation about the snapshot, not a claim about the world."""
    observations = EvidenceSufficiencyPlugin().contribute(
        _view({"core.temporal": _completed("core.temporal", metrics={"elapsed_hours": 31})}))

    summary = observations[-1]
    assert summary.kind == "validation.evidence_sufficiency"
    assert summary.metrics["claims"] == 0
    assert not any(item.kind == "validation.ungrounded_claim" for item in observations)


def test_a_run_in_which_nothing_completed_yields_no_sufficiency_reading():
    """Zero would read as "everything is ungrounded" — a far stronger claim than "we do not know"."""
    assert EvidenceSufficiencyPlugin().contribute(_view({})) == ()


# ---------------------------------------------------------------------------------------------
# Staleness — is the basis describing the world as it is now?
# ---------------------------------------------------------------------------------------------

def test_the_freshest_evidence_governs_because_one_recent_look_makes_the_picture_current():
    """A thread with a message from this morning is live however many old attachments hang off it."""
    observations = StalenessPlugin().contribute(_view(evidence=(
        _evidence("ev_recent", occurred_at=NOW - timedelta(hours=2)),
        _evidence("ev_ancient", "deal.owner", occurred_at=NOW - timedelta(days=400)),
    )))

    assert observations[0].kind == "validation.evidence_fresh"
    assert observations[0].metrics["staleness_bp"] == 0
    assert observations[0].metrics["freshest_age_hours"] == 2
    assert observations[0].metrics["stale_count"] == 1     # the old row is still counted, not hidden


def test_a_basis_twice_past_its_acceptable_age_is_fully_stale():
    """Two weeks on a one-week limit means nobody has looked at this since it mattered."""
    observations = StalenessPlugin().contribute(_view(evidence=(
        _evidence("ev_old", occurred_at=NOW - timedelta(hours=336)),)))

    assert observations[0].kind == "validation.evidence_stale"
    assert observations[0].metrics["staleness_bp"] == 10_000
    assert "evidence_older_than_limit" in observations[0].reason_codes


def test_undated_evidence_produces_no_staleness_reading_rather_than_a_zero():
    """Evidence without a timestamp is not evidence about time; assuming it is fresh is a fabrication."""
    assert StalenessPlugin().contribute(_view(evidence=(_evidence("ev_undated"),))) == ()


def test_layer_three_may_declare_how_old_is_too_old_for_its_own_domain():
    """A quarterly renewal tolerates month-old facts; an inbound reply does not."""
    fresh_for_a_quarter = StalenessPlugin().contribute(_view(
        config={"max_evidence_age_hours": 2_160},
        evidence=(_evidence("ev_old", occurred_at=NOW - timedelta(hours=336)),)))

    assert fresh_for_a_quarter[0].kind == "validation.evidence_fresh"


# ---------------------------------------------------------------------------------------------
# The arithmetic: severity of a broken basis, not a tally of complaints
# ---------------------------------------------------------------------------------------------

def test_the_worst_contradiction_governs_and_the_others_add_bounded_drag():
    """Three mild clashes are not three times as broken as one outright one."""
    metrics = ValidationUnit().calculate(
        _view(), [_contradiction(6_000), _contradiction(4_000), _contradiction(2_000),
                  _sufficiency(claims=2, grounded=2)])

    # 10000 - 6000 - (6000 / 4) = 2500, not 10000 - 12000 = 0.
    assert metrics["safe_bp"] == 2_500
    assert metrics["contradiction_count"] == 3


def test_a_missing_citation_weakens_the_basis_where_a_contradiction_breaks_it():
    """An uncited claim may still be true; a contradiction guarantees something is actually wrong."""
    uncited = ValidationUnit().calculate(_view(), [_sufficiency(claims=2, grounded=1)])
    contradicted = ValidationUnit().calculate(
        _view(), [_contradiction(5_000), _sufficiency(claims=2, grounded=2)])

    assert uncited["evidence_sufficiency_bp"] == 5_000
    assert uncited["safe_bp"] == 7_000             # 10000 - (5000 gap × 6000 weight)
    assert contradicted["safe_bp"] == 5_000
    assert contradicted["safe_bp"] < uncited["safe_bp"]


def test_a_run_where_nobody_claimed_anything_publishes_no_sufficiency_share():
    """Nothing was asserted, so no share of assertions was grounded — the metric does not apply."""
    metrics = ValidationUnit().calculate(_view(), [_sufficiency(claims=0, grounded=0)])

    assert "evidence_sufficiency_bp" not in metrics
    assert metrics["safe_bp"] == 10_000


# ---------------------------------------------------------------------------------------------
# Validated versus never checked — the distinction the unit exists to preserve
# ---------------------------------------------------------------------------------------------

def test_an_uninspected_run_is_never_reported_as_validated():
    """The worst output this unit could produce is a confident all-clear over an empty room."""
    result = ValidationUnit().evaluate(_request(), {})

    assert result.metrics["inspected_result_count"] == 0
    assert result.metrics["safe_bp"] == 10_000              # no fault was demonstrated...
    assert result.reason_codes == ("validation_not_observable",)   # ...and none could have been
    assert result.matched is False


def test_an_uninspected_run_never_eliminates_anything():
    """Vetoing on the grounds of having looked at nothing would be a bug wearing caution's costume."""
    assert ValidationUnit().evaluate(_request(), {}).checks == ()


def test_a_validated_run_records_a_passing_safety_check_on_every_play():
    """A candidate showing safety:PASS was checked; one with no safety check never was."""
    prior = {"core.risk": _completed("core.risk", matched=True, evidence_ids=("ev_recent",))}
    request = _request(evidence=(_evidence("ev_recent", occurred_at=NOW - timedelta(hours=2)),),
                       plays=(_play("send_reply"), _play("schedule_call")))

    result = ValidationUnit().evaluate(request, prior)

    assert result.matched is False
    assert result.metrics["safe_bp"] == 10_000
    assert result.metrics["evidence_sufficiency_bp"] == 10_000
    assert {check.play_id for check in result.checks} == {"schedule_call", "send_reply"}
    assert {check.outcome for check in result.checks} == {CheckOutcome.PASS}
    assert {check.stage for check in result.checks} == {"safety"}


# ---------------------------------------------------------------------------------------------
# The veto: symmetric, bounded, and never a preference
# ---------------------------------------------------------------------------------------------

def test_an_unsafe_basis_eliminates_every_play_identically():
    """Reasoning that does not hold together is unsafe for all plays — this can never pick one."""
    prior = {"core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 9_500},
                                     evidence_ids=("ev_recent",)),
             "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 500},
                                       evidence_ids=("ev_recent",))}
    request = _request(evidence=(_evidence("ev_recent", occurred_at=NOW - timedelta(hours=2)),),
                       plays=(_play("send_reply"), _play("schedule_call")))

    result = ValidationUnit().evaluate(request, prior)

    assert result.metrics["contradiction_count"] == 1
    assert result.metrics["safe_bp"] == 1_000               # 10000 - 9000 gap
    assert len(result.checks) == 2
    assert {check.outcome for check in result.checks} == {CheckOutcome.ELIMINATE}
    assert {check.stage for check in result.checks} == {"safety"}
    assert {check.reason_code for check in result.checks} == {"unsafe_reasoning_basis"}


def test_a_basis_exactly_at_the_safety_floor_still_passes():
    """The floor is a minimum, not a margin — meeting it exactly is meeting it."""
    prior = {"core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 7_500},
                                     evidence_ids=("ev_recent",)),
             "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 2_500},
                                       evidence_ids=("ev_recent",))}
    request = _request(evidence=(_evidence("ev_recent", occurred_at=NOW - timedelta(hours=2)),),
                       config={"safety_floor_bp": 5_000})

    result = ValidationUnit().evaluate(request, prior)

    assert result.metrics["safe_bp"] == 5_000
    assert result.checks[0].outcome == CheckOutcome.PASS


def test_the_unit_never_ranks_adjusts_or_prefers_a_play():
    """Elimination is a veto. Moving a score would make this unit a second Decision Maker."""
    prior = {"core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 9_500}),
             "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 500})}

    result = ValidationUnit().evaluate(_request(), prior)

    assert result.adjustments == ()
    assert all(check.score_before_bp is None and check.score_after_bp is None
               for check in result.checks)


# ---------------------------------------------------------------------------------------------
# Composition safety
# ---------------------------------------------------------------------------------------------

def test_the_unit_publishes_no_reserved_shared_metric():
    """core.confidence and core.priority own these; a second writer silently re-scores everything."""
    result = ValidationUnit().evaluate(
        _request(), {"core.risk": _completed("core.risk", matched=True)})

    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}
    assert reserved.isdisjoint(ValidationUnit.publishes)
    assert reserved.isdisjoint(result.metrics)


def test_every_published_metric_is_declared():
    result = ValidationUnit().evaluate(
        _request(evidence=(_evidence("ev_old", occurred_at=LONG_AGO),)),
        {"core.risk": _completed("core.risk", matched=True)})

    assert set(result.metrics) <= set(ValidationUnit.publishes)


def test_the_same_run_twice_produces_identical_metrics():
    """Replayability is why none of this may touch a clock, a model, or a random source."""
    prior = {"core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 9_200}),
             "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 1_000})}
    request = _request(evidence=(_evidence("ev_old", occurred_at=LONG_AGO),))

    first = ValidationUnit().evaluate(request, prior)
    second = ValidationUnit().evaluate(request, prior)

    assert dict(first.metrics) == dict(second.metrics)
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


def test_the_order_prior_results_arrived_in_cannot_change_the_verdict():
    """This unit reads a mapping filled by the orchestrator; iteration order must never reach output."""
    risk = _completed("core.risk", matched=True, metrics={"risk_bp": 9_200})
    rule = _completed("legacy.rule", matched=True, metrics={"risk_bp": 1_000})

    forward = ValidationUnit().evaluate(_request(), {"core.risk": risk, "legacy.rule": rule})
    reverse = ValidationUnit().evaluate(_request(), {"legacy.rule": rule, "core.risk": risk})

    assert forward.semantic_hash == reverse.semantic_hash


def test_findings_keep_a_stable_identity_when_one_fault_is_repaired():
    """Findings are compared across runs; a positional id would make every repair look like churn."""
    broken = ValidationUnit().evaluate(_request(), {
        "core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 9_200}),
        "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 1_000})})
    repaired = ValidationUnit().evaluate(_request(), {
        "core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 9_200}),
        "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 9_000})})

    surviving = "validation.evidence_sufficiency.legacy.rule"
    assert surviving in {item.finding_id for item in broken.findings}
    assert "validation.contradiction.risk_bp" in {item.finding_id for item in broken.findings}
    assert surviving in {item.finding_id for item in repaired.findings}
    assert "validation.contradiction.risk_bp" not in {item.finding_id
                                                      for item in repaired.findings}


def test_configuration_that_is_not_basis_points_is_a_manifest_fault():
    """A safety floor that quietly became zero would mean this unit never stopped anything again."""
    with pytest.raises(ValueError, match="integer basis points"):
        ValidationUnit().evaluate(
            _request(config={"safety_floor_bp": 20_000}),
            {"core.risk": _completed("core.risk", matched=True)})


def test_an_age_limit_that_is_not_a_positive_duration_is_a_manifest_fault():
    with pytest.raises(ValueError, match="positive integer"):
        StalenessPlugin().contribute(_view(
            config={"max_evidence_age_hours": 0},
            evidence=(_evidence("ev_old", occurred_at=LONG_AGO),)))


def test_the_unit_satisfies_the_reasoner_protocol():
    assert isinstance(ValidationUnit(), Reasoner)


# ---------------------------------------------------------------------------------------------
# One real run, end to end
# ---------------------------------------------------------------------------------------------

def test_a_run_that_disagrees_with_itself_on_stale_uncited_facts_is_stopped():
    """The Northwind deal. core.risk read the account as nearly lost (9,200bp) from a May email;
    the tenant's legacy scoring rule read the same deal as healthy (1,000bp) and cited nothing at
    all to say why. Nothing downstream reconciles those two numbers — the Decision Maker would
    score the follow-up play on whichever it happened to read, on a picture of the account that is
    three months old. This is precisely the run that must not reach a human as a recommendation."""
    request = _request(evidence=(_evidence("ev_inbound", occurred_at=LONG_AGO),),
                       plays=(_play("send_reply"), _play("schedule_call")))
    prior = {
        "core.risk": _completed("core.risk", matched=True, metrics={"risk_bp": 9_200},
                                evidence_ids=("ev_inbound",)),
        "legacy.rule": _completed("legacy.rule", matched=True, metrics={"risk_bp": 1_000}),
    }

    result = ValidationUnit().evaluate(request, prior)

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is True
    assert result.metrics["inspected_result_count"] == 2
    assert result.metrics["contradiction_count"] == 1
    assert result.metrics["ungrounded_claim_count"] == 1
    assert result.metrics["evidence_sufficiency_bp"] == 5_000      # 1 of 2 claims retraceable
    assert result.metrics["staleness_bp"] == 10_000                # freshest fact is 2,331h old
    assert result.metrics["stale_evidence_count"] == 1
    # 10000 - 8200 contradiction - 3000 grounding - 4000 staleness → below zero, clamped.
    assert result.metrics["safe_bp"] == 0
    assert result.reason_codes == ("claim_without_evidence", "evidence_older_than_limit",
                                   "units_disagree_on_metric")
    assert {item.finding_id for item in result.findings} == {
        "validation.contradiction.risk_bp",
        "validation.evidence_sufficiency.legacy.rule",
        "validation.staleness",
    }
    assert [(check.play_id, check.outcome) for check in result.checks] == [
        ("schedule_call", CheckOutcome.ELIMINATE), ("send_reply", CheckOutcome.ELIMINATE)]
    assert result.evidence_ids == ("ev_inbound",)
