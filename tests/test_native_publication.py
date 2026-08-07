"""Executable contract for the Layer 4 → Layer 5 native publication seam.

The whole risk of this seam is silent: a signal row that fails
``AUTHORITATIVE_SIGNAL_PREDICATE`` is not rejected, it is *invisible*, because every downstream
read joins through that predicate. There is no error to notice and no row to inspect — the product
simply shows nothing. So these tests are written against the predicate's text rather than against a
database, and assert the correspondence field by field.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.packs.capabilities import BUILTIN_CAPABILITIES, DEAL_COOLING_V1
from genios_engine.packs.capabilities.deal_cooling_v2 import DEAL_COOLING_FULL_V2
from genios_engine.reason.authority import (
    AUDITED_SIGNAL_PREDICATE,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    projected_score,
)
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.publication import (
    COOLDOWN_HOURS_KEY,
    NATIVE_SIGNAL_LEVEL,
    build_native_publication,
    native_rule_id,
    native_rule_ids,
)
from genios_engine.reason.reasoners import default_registry

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
INBOUND = (NOW - timedelta(days=10)).isoformat()

BUNDLE = {"run": {"run_id": "run_1"},
          "output": {"selected_candidate_id": "cand_1", "decision_hash": "hash_1"}}


def _context() -> ContextSnapshot:
    facts = {
        "deal.status": {"value": "open"},
        "deal.value": {"value": 500_000},
        "derived.engagement": {"value_bp": 4_000},
        "thread.last_inbound": {"value": INBOUND},
        "relationship.verified_stakeholder_count": {"value": 2},
    }
    evidence = (
        EvidenceRef("ev_status", "deal.status", "open", source_ref_id="crm_1",
                    occurred_at=NOW - timedelta(days=1), confidence_bp=9_500,
                    authority_rank=3, independence_group="crm"),
        EvidenceRef("ev_value", "deal.value", 500_000, source_ref_id="crm_1",
                    occurred_at=NOW - timedelta(days=1), confidence_bp=9_500,
                    authority_rank=3, independence_group="crm"),
        EvidenceRef("ev_engagement", "derived.engagement", 4_000, source_ref_id="derived_1",
                    occurred_at=NOW - timedelta(hours=6), confidence_bp=8_500,
                    authority_rank=2, independence_group="derived"),
        EvidenceRef("ev_inbound", "thread.last_inbound", INBOUND, source_ref_id="gmail_1",
                    occurred_at=NOW - timedelta(days=10), confidence_bp=9_000,
                    authority_rank=3, independence_group="gmail"),
        EvidenceRef("ev_stakeholders", "relationship.verified_stakeholder_count", 2,
                    source_ref_id="crm_1", occurred_at=NOW - timedelta(days=2),
                    confidence_bp=9_000, authority_rank=3, independence_group="crm"),
    )
    return ContextSnapshot(
        org_id="org_1", graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="deal_cooling.selector.v1",
        facts=facts, evidence=evidence,
        neighbor_facts={"deal.status": "open", "contact.verified_recipient": True,
                        "account.alternate_stakeholder_verified": True},
        edge_count=2)


def _request(capability, *, mode=ExecutionMode.LIVE) -> ReasoningRequest:
    return ReasoningRequest(
        org_id="org_1", capability=capability, context=_context(), evaluation_time=NOW,
        trigger_kind="capability.graph_scan", config_snapshot_id="cfg_1", mode=mode)


@pytest.fixture(scope="module")
def orchestrator():
    return ReasoningOrchestrator(default_registry())


@pytest.fixture(scope="module")
def execution(orchestrator):
    return orchestrator.execute(_request(DEAL_COOLING_FULL_V2))


@pytest.fixture(scope="module")
def publication(execution):
    built = build_native_publication(execution=execution, audit_bundle=BUNDLE)
    assert built is not None, "the activated capability must publish on its own worked example"
    return built


# -- the rule id, which is a SQL contract -------------------------------------------------------

def test_the_python_rule_id_matches_the_sql_regex_the_predicate_uses():
    """`s.rule_id=regexp_replace(rr.capability_id, '^.*\\.', '')`. `.*` is greedy, so the split is
    on the LAST dot. A Python implementation that split on the first would make every native
    signal unreadable, and nothing would report it."""
    for capability_id in ("sales.deal_cooling_full", "sales.deal_cooling",
                          "a.b.c.deep_capability", "flat"):
        assert native_rule_id(capability_id) == re.sub(r"^.*\.", "", capability_id)


def test_the_rule_id_and_reason_code_are_the_same_string(publication):
    """For a non-legacy run the predicate compares both columns against the same expression."""
    assert publication.rule_id == publication.reason_code == "deal_cooling_full"


def test_a_capability_id_is_required():
    with pytest.raises(ValueError):
        native_rule_id("   ")


def test_native_rule_ids_covers_every_scheduled_capability():
    assert native_rule_ids(BUILTIN_CAPABILITIES) == {"deal_cooling", "deal_cooling_full"}


# -- the bindings the predicate checks ----------------------------------------------------------

def test_the_score_uses_the_one_projection_law(publication, execution):
    """`s.score=((selected_rc.final_utility_bp + 50) / 100)` — asserted against the same helper
    the SQL mirrors, not against a recomputed constant."""
    assert publication.score == projected_score(execution.selected_candidate.utility_bp)


def test_the_expiry_is_the_decision_s_own(publication, execution):
    """`s.authority_expires_at = (ro.decision_core->'expires_at')::timestamptz`. Equality, not
    tolerance: a signal outliving its decision by one microsecond is unauthorized."""
    assert publication.authority_expires_at == execution.decision.expires_at


def test_the_play_is_the_selected_candidate_s(publication, execution):
    assert publication.play == execution.selected_candidate.play_id
    assert publication.reasoning_candidate_id == BUNDLE["output"]["selected_candidate_id"]
    assert publication.reasoning_decision_hash == BUNDLE["output"]["decision_hash"]
    assert publication.reasoning_run_id == BUNDLE["run"]["run_id"]


def test_the_subject_is_the_root_the_run_reasoned_about(publication):
    """`rr.root_node_id=s.subject_node_id`."""
    assert publication.subject_node_id == "deal_1"


def test_the_level_is_prescriptive(publication):
    assert publication.level == NATIVE_SIGNAL_LEVEL == "prescriptive"


def test_the_rule_version_is_the_capability_major(publication):
    assert publication.rule_version == 2


# -- refusals ------------------------------------------------------------------------------------

def test_a_shadow_run_does_not_publish(orchestrator):
    shadow = orchestrator.execute(_request(DEAL_COOLING_FULL_V2, mode=ExecutionMode.SHADOW))

    assert shadow.decision.outcome == DecisionOutcome.DECISION
    assert build_native_publication(execution=shadow, audit_bundle=BUNDLE) is None


def test_a_capability_that_is_not_delivery_enabled_does_not_publish(orchestrator):
    """v1 stays shadow-only while it serves as the comparison baseline."""
    baseline = orchestrator.execute(_request(DEAL_COOLING_V1))

    assert DEAL_COOLING_V1.live_delivery_enabled is False
    assert build_native_publication(execution=baseline, audit_bundle=BUNDLE) is None


@pytest.mark.parametrize("bundle", [
    {},
    {"run": {"run_id": "run_1"}, "output": {}},
    {"run": {}, "output": {"selected_candidate_id": "c", "decision_hash": "h"}},
    {"run": {"run_id": "run_1"}, "output": {"selected_candidate_id": "c"}},
], ids=["empty", "no-output-ids", "no-run-id", "no-decision-hash"])
def test_an_incomplete_audit_bundle_refuses_rather_than_dangles(execution, bundle):
    """A signal pointing at an audit trail that does not exist is the dangling authority the
    predicate exists to catch. Refuse at the writer instead of writing an invisible row."""
    assert build_native_publication(execution=execution, audit_bundle=bundle) is None


def test_refusal_is_an_absent_value_not_an_exception(orchestrator):
    """Refusal is the normal case during rollout; a caller must not need a try/except to sweep."""
    shadow = orchestrator.execute(_request(DEAL_COOLING_FULL_V2, mode=ExecutionMode.SHADOW))

    assert build_native_publication(execution=shadow, audit_bundle=BUNDLE) is None


# -- what the card will show ---------------------------------------------------------------------

def test_the_evidence_is_what_the_decision_actually_cited(publication, execution):
    """Driven by the candidate's evidence ids, so a card can never cite more than moved the score."""
    cited = set(execution.selected_candidate.evidence_ids)
    fields = {item["field"] for item in publication.evidence}
    expected = {ref.field for ref in execution.request.context.evidence
                if ref.evidence_id in cited}

    assert fields == expected
    assert fields, "the worked example must cite something"


def test_the_evidence_order_is_total(publication):
    fields = [item["field"] for item in publication.evidence]

    assert fields == sorted(fields)


def test_the_score_inputs_decompose_the_score(publication, execution):
    components = execution.selected_candidate.score_components
    assert publication.score_inputs["U"] == projected_score(components["urgency"])
    assert publication.score_inputs["I"] == projected_score(components["impact"])
    assert publication.score_inputs["C"] == projected_score(execution.decision.confidence_bp)


def test_the_projection_is_a_total_function(orchestrator, publication):
    """Publishing twice from one execution must bind identically, or replay proves nothing."""
    again = build_native_publication(
        execution=orchestrator.execute(_request(DEAL_COOLING_FULL_V2)), audit_bundle=BUNDLE)

    assert again == publication


# -- cooldown --------------------------------------------------------------------------------------

def test_the_cooldown_comes_from_the_capability(publication):
    assert DEAL_COOLING_FULL_V2.metadata[COOLDOWN_HOURS_KEY] == 72
    assert publication.cooldown_hours == 72


def test_a_capability_without_a_declared_cooldown_rests_for_its_own_expiry(orchestrator):
    """Absent metadata must not mean "no cooldown" — that would republish the same reading daily."""
    from dataclasses import replace

    quiet = replace(DEAL_COOLING_FULL_V2, metadata={
        key: value for key, value in DEAL_COOLING_FULL_V2.metadata.items()
        if key != COOLDOWN_HOURS_KEY})
    built = build_native_publication(
        execution=orchestrator.execute(_request(quiet)), audit_bundle=BUNDLE)

    assert built.cooldown_hours == quiet.expiry_hours


# -- the score-input anchor -----------------------------------------------------------------------

def test_score_inputs_prefer_the_legacy_anchor_then_the_publishing_unit():
    """Legacy cards must be byte-identical to what they were, so `authority_source` stays the first
    term of every chain; the native fallbacks may only fill what the anchor cannot answer."""
    for metric in ("urgency_bp", "impact_bp", "recency_bp"):
        anchor = AUTHORITATIVE_SCORE_INPUTS_SQL.index(
            "authority_source.output->'metrics'->>'" + metric + "'")
        scan = AUTHORITATIVE_SCORE_INPUTS_SQL.index(
            "published_metric.output->'metrics'->>'" + metric + "'")
        assert anchor < scan, f"{metric}: the legacy anchor must be resolved first"


def test_recency_falls_back_to_the_native_freshness_vocabulary():
    assert "'freshness_bp'" in AUTHORITATIVE_SCORE_INPUTS_SQL


def test_the_metric_scan_avoids_the_jsonb_question_mark_operator():
    """`?` collides with parameter markers in some drivers; a query that only breaks in production
    is the worst kind, so the scan tests for null instead."""
    scan = AUTHORITATIVE_SCORE_INPUTS_SQL[AUTHORITATIVE_SCORE_INPUTS_SQL.index("published_metric"):]

    assert "?" not in scan


def test_the_predicate_still_never_reads_score_inputs():
    """score_inputs is diagnostic. If it ever became load-bearing, a mutable column would be
    deciding authority — which is the thing this whole design refuses."""
    assert "score_inputs" not in AUDITED_SIGNAL_PREDICATE
