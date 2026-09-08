from __future__ import annotations

from genios_engine.context.situation_publisher import (
    HoldReason,
    PublicationOutcome,
    decide_publication,
)
from genios_engine.contracts.domain_expertise import BusinessSituationObject
from genios_engine.contracts.situation import BUSINESS_SITUATION_V2_VERSION, ImportanceBasis
from genios_engine.contracts.quality import MissingFact


QUOTE = "The renewal is due Friday."
SPAN = {
    "source_ref": "prepared_content:evt_1",
    "quote": QUOTE,
    "start_offset": 0,
    "end_offset": len(QUOTE),
    "verified": True,
    "signal_id": "sig_1",
}


def candidate(**changes) -> BusinessSituationObject:
    fields = dict(
        org_id="org_admit", trace_id="trace_admit", visibility={"scope": "org"},
        id="sit_1", signal_ids=("sig_1",), type="renewal", confidence_bp=7000,
        importance_bp=8100, evidence=(SPAN,), state="active",
        entities=({"id": "node_1", "type": "company", "name": "Acme"},),
        metadata={
            "domain_ids": ["admin"],
            "importance_source": "l1_qualified_signals",
            "importance_version": "alg17.v2",
            "importance_components": {"weighted_bp": 8100},
            "confidence_vector": {"evidence": 7000, "freshness": 8000,
                                  "consistency": 9000, "identity": 8500,
                                  "coverage": 7500, "analytic": -1},
            "evidence_verified_spans": 1,
            "split_required": False,
            "pattern_activated": False,
        })
    fields.update(changes)
    return BusinessSituationObject(**fields)


def test_admit_exposes_only_the_strict_v2_object():
    result = decide_publication(candidate(state="partial"))
    assert result.outcome is PublicationOutcome.ADMIT
    assert result.situation is not None
    assert result.situation.schema_version == BUSINESS_SITUATION_V2_VERSION
    assert result.situation.state == "partial"
    assert result.situation.domain_hints == ("admin",)
    assert result.situation.semantic_hash


def test_no_qes_is_held_and_exposes_no_object():
    value = candidate(metadata={**candidate().metadata, "importance_source": "default"})
    result = decide_publication(value)
    assert result.outcome is PublicationOutcome.HOLD
    assert HoldReason.QES_REQUIRED.value in result.reasons
    assert result.situation is None


# =================================================================================================
# L2.5.8 · THE ONE CONDITIONAL HOLD — a tenant Layer 1 has never scored is not held forever
#
# `qes_required` used to fire unconditionally, which meant a tenant whose Layer 1 scorer is not
# live lost its whole L3/L4 lane rather than degrading. Three facts settled it, and they are
# argued in full in `situation_publisher.decide_publication`: HOLD is defined in this module as
# RECOVERABLE incompleteness and migration 0122 makes every held row carry a `reevaluate_after`,
# but no sweep will ever produce a score for a tenant that has none; doc 04 SPECIFIES the
# downstream behaviour ("if L2 has not activated importance for this org, the component is absent,
# not defaulted ... record L2_IMPORTANCE_NOT_ACTIVE"), which an unconditional hold makes
# unreachable; and `context/importance.assess_l1_supply` already answers the identical question
# the other way ("an EMPTY supply is unknown, not flat").
# =================================================================================================

def test_a_scoring_tenants_unscored_situation_is_still_held_because_a_retry_can_repair_it():
    """The strict arm, restated as the DEFAULT so nothing reaches it by forgetting to pass a flag.

    Layer 1 is scoring this tenant and skipped this situation: the next sweep can genuinely fix
    that, which is the whole meaning of HOLD.
    """
    value = candidate(metadata={**candidate().metadata, "importance_source": "l1_unscored"})
    assert decide_publication(value).outcome is PublicationOutcome.HOLD
    assert decide_publication(value, l1_scoring_active=True).outcome is PublicationOutcome.HOLD


def test_a_tenant_layer_one_never_scored_is_admitted_carrying_its_absence_not_held_forever():
    """The condition. The candidate publishes, and it publishes SAYING importance is absent.

    Admitted is not the same as defaulted: the attribution is typed `UNSCORED`, pinned to 0 with
    no base and no components, which is the contract's own spelling of "this is an absence, not a
    low number" — and it is what Layer 4's honesty guard reads to reweigh the other five
    components instead of substituting 5000.
    """
    value = candidate(metadata={**candidate().metadata, "importance_source": "l1_unscored"})
    result = decide_publication(value, l1_scoring_active=False)

    assert result.outcome is PublicationOutcome.ADMIT
    assert result.situation is not None
    assert result.situation.importance.basis is ImportanceBasis.UNSCORED
    assert result.situation.importance.score_bp == 0
    assert result.situation.importance.base_bp is None
    assert result.situation.importance.components == {}


def test_the_condition_lifts_the_score_requirement_and_nothing_else():
    """The half that must NEVER be conditional: no claim without a receipt.

    A tenant with no Layer 1 scoring is still refused when it carries no verified evidence span,
    an open conflict, or an unresolved identity. If this ever goes green with an ADMIT, the
    relaxation has stopped being scoped and the gate has been lowered.
    """
    base = {**candidate().metadata, "importance_source": "default"}

    no_span = decide_publication(
        candidate(evidence=({"event_id": "evt_1", "source": "situation"},),
                  metadata={**base, "evidence_verified_spans": 0}),
        l1_scoring_active=False)
    assert no_span.outcome is PublicationOutcome.HOLD
    assert HoldReason.VERIFIED_EVIDENCE_REQUIRED.value in no_span.reasons
    assert HoldReason.QES_REQUIRED.value not in no_span.reasons

    conflicted = decide_publication(
        candidate(metadata={**base, "conflict_ids": ["cf_1"]}), l1_scoring_active=False)
    assert conflicted.outcome is PublicationOutcome.HOLD
    assert HoldReason.CONFLICT_OPEN.value in conflicted.reasons

    split = decide_publication(
        candidate(metadata={**base, "split_required": True}), l1_scoring_active=False)
    assert split.outcome is PublicationOutcome.HOLD
    assert HoldReason.IDENTITY_REVIEW_REQUIRED.value in split.reasons


def test_no_verified_span_is_held_not_fabricated():
    value = candidate(evidence=({"event_id": "evt_1", "source": "situation"},),
                      metadata={**candidate().metadata, "evidence_verified_spans": 0})
    result = decide_publication(value)
    assert result.outcome is PublicationOutcome.HOLD
    assert HoldReason.VERIFIED_EVIDENCE_REQUIRED.value in result.reasons
    assert result.situation is None


def test_an_activated_pattern_without_span_receipts_is_held():
    value = candidate(metadata={**candidate().metadata, "pattern_id": "renewal-risk",
                                "pattern_activated": True,
                                "matched_conditions": [{"ref": "fact:fv_1"}]})
    result = decide_publication(value)
    assert result.outcome is PublicationOutcome.HOLD
    assert HoldReason.PATTERN_EVIDENCE_REQUIRED.value in result.reasons


def test_malformed_lifecycle_is_rejected_and_never_exposed():
    result = decide_publication(candidate(state="invented"))
    assert result.outcome is PublicationOutcome.REJECT
    assert result.situation is None


def test_open_conflict_is_held_until_both_sides_can_be_published():
    value = candidate(metadata={**candidate().metadata, "conflict_ids": ["conflict_1"]})
    result = decide_publication(value)
    assert result.outcome is PublicationOutcome.HOLD
    assert HoldReason.CONFLICT_OPEN.value in result.reasons


def test_declared_complete_coverage_requirement_fails_closed():
    value = candidate(metadata={**candidate().metadata,
                                "requires_complete_coverage": True,
                                "coverage_ready": False})
    result = decide_publication(value)
    assert result.outcome is PublicationOutcome.HOLD
    assert HoldReason.SOURCE_COVERAGE_INSUFFICIENT.value in result.reasons


def test_same_candidate_gets_same_decision_identity_across_traces():
    one = decide_publication(candidate(trace_id="trace_one"))
    two = decide_publication(candidate(trace_id="trace_two"))
    assert one.decision_id == two.decision_id


def test_typed_absence_is_first_class_and_changes_candidate_identity():
    absent = MissingFact(
        subject_node_id="node_1", expected_fact="thread.last_inbound",
        absence_type="genuinely_absent", coverage_ready=True,
        coverage_basis=("gmail:messages",))
    without = decide_publication(candidate())
    with_absence = decide_publication(candidate(), missing_facts=(absent,))
    assert with_absence.situation is not None
    assert with_absence.situation.missing_facts == (absent,)
    assert with_absence.decision_id != without.decision_id


def test_admission_tables_are_erased_on_tenant_reset():
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "situation_admission_decisions" in _ORG_SCOPED_TABLES
    assert "edge_coverage_declarations" in _ORG_SCOPED_TABLES
