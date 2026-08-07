"""Executable contract for the Context Unit (`core.context`).

The Context Unit is the floor every other unit stands on: it states what is actually known right
now. These tests pin the properties that make that reading trustworthy.

* **Silence over fabrication.** No dated evidence must produce *no* freshness metric, never a zero.
  A fabricated zero reads downstream as "we checked and it is stale", which is a claim the unit has
  no basis to make.
* **Corroboration counts witnesses, not rows.** Two copies of the same source are one witness;
  otherwise a duplicated sync manufactures agreement out of thin air.
* **It reports, it never rules.** No `matched` verdict, and none of the reserved shared metrics
  (`confidence_bp`, `urgency_bp`, `priority_override_bp`) — publishing those from here would
  silently re-score every decision in the plan.
* **Determinism.** Same snapshot, same numbers, every time, regardless of iteration order.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from genios_engine.reason.reasoners.context_unit import (
    ContextUnit,
    EvidenceFreshnessPlugin,
    FactCoveragePlugin,
    SourceCorroborationPlugin,
    declared_fields,
    independence_key,
)
from genios_engine.reason.unit import UnitCategory, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _hours_ago(hours: int) -> datetime:
    return NOW - timedelta(hours=hours)


def _request(*, facts=None, evidence=(), missing=(), config=None, required=(),
             reasoner_fields=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(
            ReasonerSpec("core.context", "1.0.0", config=config or {}),
            ReasonerSpec("core.temporal", "1.0.0", required_fields=tuple(reasoner_fields)),
        ),
        plays=(PlayDefinition(play_id="restore_momentum", version="1",
                              label="Restore momentum", steps=("Draft a grounded reply",)),),
        required_fields=tuple(required),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=facts if facts is not None else {},
        missing_fields=tuple(missing),
        evidence=tuple(evidence),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _view(request: ReasoningRequest) -> UnitView:
    unit = ContextUnit()
    spec = next(item for item in request.capability.reasoners
                if item.reasoner_id == "core.context")
    return unit.retrieve(request, spec, {})


def _metrics(request: ReasoningRequest):
    return dict(ContextUnit().evaluate(request, {}).metrics)


# ---------------------------------------------------------------------------------------------
# Fact coverage — the denominator is declared, never invented
# ---------------------------------------------------------------------------------------------

def test_completeness_is_measured_against_what_the_capability_declared_it_needs():
    """Three of four declared fields present is 7500bp — a share nobody can dispute later."""
    request = _request(
        facts={"deal.status": "open", "deal.owner": "rep_1", "deal.value_minor": 4_500_000},
        required=("deal.status", "deal.owner", "deal.value_minor", "deal.close_date"))

    observation, = FactCoveragePlugin().contribute(_view(request))

    assert observation.metrics["completeness_bp"] == 7_500
    assert observation.metrics["declared_field_count"] == 4
    assert observation.metrics["known_field_count"] == 3
    assert observation.metrics["missing_field_count"] == 1
    assert observation.reason_codes == ("context_fields_absent",)


def test_fields_the_selector_failed_to_supply_still_count_against_completeness():
    """Otherwise a snapshot looks complete precisely because retrieval broke — the worst failure."""
    request = _request(facts={"deal.status": "open"},
                       required=("deal.status",),
                       missing=("deal.owner", "deal.close_date"))

    observation, = FactCoveragePlugin().contribute(_view(request))

    assert observation.metrics["declared_field_count"] == 3
    assert observation.metrics["completeness_bp"] == 3_333


def test_every_reasoners_declared_need_joins_the_denominator():
    """A field only core.temporal asked for is still a fact this capability cares about."""
    request = _request(facts={"deal.status": "open"}, required=("deal.status",),
                       reasoner_fields=("thread.last_inbound",))

    assert declared_fields(_view(request)) == ("deal.status", "thread.last_inbound")


def test_a_capability_may_name_its_own_coverage_yardstick():
    request = _request(facts={"deal.status": "open"}, required=("deal.status", "deal.owner"),
                       config={"context_fields": ["deal.status"]})

    observation, = FactCoveragePlugin().contribute(_view(request))

    assert observation.metrics["completeness_bp"] == 10_000
    assert observation.reason_codes == ("context_fields_all_present",)


def test_a_capability_that_declares_nothing_gets_no_completeness_reading():
    """100% of zero declared fields is not "complete" — it is a question nobody asked."""
    request = _request(facts={"deal.status": "open"})

    assert FactCoveragePlugin().contribute(_view(request)) == ()
    assert "completeness_bp" not in _metrics(request)


def test_a_malformed_coverage_override_is_a_deployment_fault():
    """Silently ignoring bad config would make coverage mean something different per tenant."""
    request = _request(facts={"deal.status": "open"}, config={"context_fields": ["  "]})

    with pytest.raises(ValueError, match="context_fields"):
        FactCoveragePlugin().contribute(_view(request))


# ---------------------------------------------------------------------------------------------
# Evidence freshness — measured from the newest thing we know
# ---------------------------------------------------------------------------------------------

def _dated(evidence_id: str, field: str, value, hours_ago: int, **kwargs) -> EvidenceRef:
    return EvidenceRef(evidence_id=evidence_id, field=field, value=value,
                       occurred_at=_hours_ago(hours_ago), **kwargs)


def test_freshness_follows_the_newest_evidence_not_the_oldest():
    """One message yesterday makes a situation current however old the rest of the file is."""
    request = _request(
        facts={"deal.status": "open", "thread.last_inbound": "2026-08-05T12:00:00+00:00"},
        evidence=(_dated("ev_old", "deal.status", "open", hours_ago=2_000),
                  _dated("ev_new", "thread.last_inbound", "2026-08-05T12:00:00+00:00",
                         hours_ago=24)))

    observation, = EvidenceFreshnessPlugin().contribute(_view(request))

    assert observation.metrics["evidence_age_hours"] == 24
    # Linear decay across the default seven-day horizon: 24/168 consumed.
    assert observation.metrics["freshness_bp"] == 8_571
    assert observation.evidence_ids == ("ev_new",)


def test_evidence_older_than_the_horizon_reads_as_zero_freshness_not_negative():
    request = _request(facts={"deal.status": "open"},
                       evidence=(_dated("ev_old", "deal.status", "open", hours_ago=5_000),))

    observation, = EvidenceFreshnessPlugin().contribute(_view(request))

    assert observation.metrics["freshness_bp"] == 0
    assert observation.metrics["evidence_age_hours"] == 5_000


def test_the_freshness_horizon_belongs_to_the_capability():
    """A day-old touch is current on an enterprise deal and ancient on a live support thread."""
    request = _request(facts={"deal.status": "open"},
                       evidence=(_dated("ev_1", "deal.status", "open", hours_ago=12),),
                       config={"freshness_horizon_hours": 24})

    observation, = EvidenceFreshnessPlugin().contribute(_view(request))

    assert observation.metrics["freshness_bp"] == 5_000


def test_undated_evidence_produces_no_freshness_claim_rather_than_a_zero():
    """"We do not know how old this is" and "this is stale" are different claims."""
    request = _request(facts={"deal.status": "open"},
                       evidence=(EvidenceRef("ev_1", "deal.status", "open"),))

    assert EvidenceFreshnessPlugin().contribute(_view(request)) == ()
    assert "freshness_bp" not in _metrics(request)


def test_evidence_dated_after_the_evaluation_instant_is_not_treated_as_perfectly_fresh():
    """A clock skew must never be able to present itself as up-to-the-second knowledge."""
    request = _request(
        facts={"deal.status": "open"},
        evidence=(EvidenceRef("ev_future", "deal.status", "open",
                              occurred_at=NOW + timedelta(hours=3)),))

    assert EvidenceFreshnessPlugin().contribute(_view(request)) == ()


# ---------------------------------------------------------------------------------------------
# Source corroboration — witnesses, not rows
# ---------------------------------------------------------------------------------------------

def test_two_independent_sources_corroborate_a_fact():
    request = _request(
        facts={"deal.status": "open"},
        evidence=(EvidenceRef("ev_crm", "deal.status", "open", independence_group="crm"),
                  EvidenceRef("ev_mail", "deal.status", "open", independence_group="mailbox")))

    observation, = SourceCorroborationPlugin().contribute(_view(request))

    assert observation.metrics["corroboration_count"] == 2
    assert observation.metrics["corroborated_field_count"] == 1
    assert observation.metrics["single_sourced_field_count"] == 0
    assert observation.reason_codes == ("context_sources_agree",)


def test_the_same_source_reported_twice_is_one_witness():
    """A mailbox sync ingesting the same thread twice must not manufacture agreement."""
    request = _request(
        facts={"deal.status": "open"},
        evidence=(EvidenceRef("ev_a", "deal.status", "open", independence_group="mailbox"),
                  EvidenceRef("ev_b", "deal.status", "open", independence_group="mailbox")))

    observation, = SourceCorroborationPlugin().contribute(_view(request))

    assert observation.metrics["corroboration_count"] == 1
    assert observation.metrics["single_sourced_field_count"] == 1


def test_an_unattributed_row_can_only_speak_for_itself():
    """No independence group and no source reference means one row, one witness — never more."""
    first = EvidenceRef("ev_a", "deal.status", "open")
    second = EvidenceRef("ev_b", "deal.status", "open", source_ref_id="crm_sync")

    assert independence_key(first) == "evidence:ev_a"
    assert independence_key(second) == "source:crm_sync"


def test_a_group_and_a_source_of_the_same_name_are_different_witnesses():
    """Namespacing stops an accidental string collision from collapsing two real observers."""
    assert independence_key(EvidenceRef("ev_a", "deal.status", "open",
                                        independence_group="crm")) \
        != independence_key(EvidenceRef("ev_b", "deal.status", "open", source_ref_id="crm"))


def test_disagreeing_independent_sources_are_reported_and_never_resolved():
    """Choosing which witness to believe is a judgement; this unit only says they differ."""
    request = _request(
        facts={"deal.contacts": ("ana@buyer.com", "raj@buyer.com")},
        evidence=(EvidenceRef("ev_crm", "deal.contacts", "ana@buyer.com",
                              independence_group="crm"),
                  EvidenceRef("ev_mail", "deal.contacts", "raj@buyer.com",
                              independence_group="mailbox")))

    observation, = SourceCorroborationPlugin().contribute(_view(request))

    assert observation.metrics["conflict_count"] == 1
    assert observation.reason_codes == ("context_sources_conflict",)
    # It counts the disagreement and cites both rows; it never names a winner.
    assert observation.evidence_ids == ("ev_crm", "ev_mail")


def test_one_source_citing_two_members_of_a_list_fact_is_not_a_conflict():
    """A single observer describing two facets of one fact has not contradicted itself."""
    request = _request(
        facts={"deal.contacts": ("ana@buyer.com", "raj@buyer.com")},
        evidence=(EvidenceRef("ev_a", "deal.contacts", "ana@buyer.com",
                              independence_group="crm"),
                  EvidenceRef("ev_b", "deal.contacts", "raj@buyer.com",
                              independence_group="crm")))

    observation, = SourceCorroborationPlugin().contribute(_view(request))

    assert observation.metrics["conflict_count"] == 0


def test_a_snapshot_with_no_evidence_makes_no_corroboration_claim():
    """Zero witnesses is not "one weak witness" — it is nothing to report."""
    request = _request(facts={"deal.status": "open"})

    assert SourceCorroborationPlugin().contribute(_view(request)) == ()
    assert "corroboration_count" not in _metrics(request)


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_satisfies_the_reasoner_protocol():
    unit = ContextUnit()

    assert isinstance(unit, Reasoner)
    assert unit.unit_id == "core.context"
    assert unit.category is UnitCategory.SITUATION_UNDERSTANDING


def test_the_unit_never_publishes_a_metric_another_unit_owns():
    """Only core.confidence and core.priority may move these; a second publisher re-scores all."""
    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}

    assert reserved.isdisjoint(ContextUnit().publishes)


def test_the_unit_reports_and_never_rules():
    """`matched` stays None: whether this context is good enough depends on the decision at hand."""
    request = _request(facts={"deal.status": "open"}, required=("deal.status",),
                       evidence=(_dated("ev_1", "deal.status", "open", hours_ago=4),))

    result = ContextUnit().evaluate(request, {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is None
    assert result.adjustments == ()      # it never nudges a play's score
    assert result.checks == ()           # and it never eliminates one


def test_the_same_snapshot_reasoned_twice_yields_identical_metrics():
    """Replayability is the whole promise of Layer 4; a drifting reading would void every audit."""
    request = _request(
        facts={"deal.status": "open", "deal.owner": "rep_1"},
        required=("deal.status", "deal.owner", "deal.close_date"),
        evidence=(_dated("ev_crm", "deal.status", "open", hours_ago=30,
                         independence_group="crm"),
                  _dated("ev_mail", "deal.status", "open", hours_ago=6,
                         independence_group="mailbox")))

    first = ContextUnit().evaluate(request, {})
    second = ContextUnit().evaluate(request, {})

    assert dict(first.metrics) == dict(second.metrics)
    assert first.semantic_hash == second.semantic_hash


def test_a_thin_situation_is_described_as_thin_end_to_end():
    """The scenario this unit exists for: two known fields, month-old evidence, one source.

    Everything downstream is entitled to know that before it recommends anything, so all three
    readings must appear in one result with the thresholds they crossed named.
    """
    request = _request(
        facts={"deal.status": "open", "deal.owner": "rep_1"},
        required=("deal.status", "deal.owner", "deal.value_minor", "deal.close_date",
                  "thread.last_inbound"),
        evidence=(_dated("ev_crm", "deal.status", "open", hours_ago=720,
                         independence_group="crm_sync"),))

    result = ContextUnit().evaluate(request, {})

    assert result.metrics["completeness_bp"] == 4_000        # 2 of 5 declared fields
    assert result.metrics["missing_field_count"] == 3
    assert result.metrics["freshness_bp"] == 0               # 30 days, past the 7-day horizon
    assert result.metrics["evidence_age_hours"] == 720
    assert result.metrics["corroboration_count"] == 1
    assert set(result.reason_codes) >= {
        "context_incomplete", "context_stale", "context_single_sourced"}
    assert result.evidence_ids == ("ev_crm",)


def test_a_well_evidenced_situation_crosses_the_other_side_of_every_threshold():
    request = _request(
        facts={"deal.status": "open", "deal.owner": "rep_1"},
        required=("deal.status", "deal.owner"),
        evidence=(_dated("ev_crm", "deal.status", "open", hours_ago=3,
                         independence_group="crm_sync"),
                  _dated("ev_mail", "deal.status", "open", hours_ago=9,
                         independence_group="mailbox")))

    result = ContextUnit().evaluate(request, {})

    assert result.metrics["completeness_bp"] == 10_000
    assert result.metrics["corroboration_count"] == 2
    assert set(result.reason_codes) >= {
        "context_substantially_known", "context_current", "context_corroborated"}


def test_every_reading_is_written_down_even_when_it_is_unflattering():
    """The record of what was known at decision time is only useful if it is always there."""
    request = _request(
        facts={"deal.status": "open"}, required=("deal.status", "deal.owner"),
        evidence=(_dated("ev_crm", "deal.status", "open", hours_ago=900),))

    findings = ContextUnit().evaluate(request, {}).findings

    assert [item.finding_id for item in findings] == [
        "context.evidence_freshness", "context.fact_coverage", "context.source_corroboration"]
    assert all(item.matched is None for item in findings)


def test_thresholds_are_tuned_per_capability_not_hardcoded():
    """A capability that genuinely needs everything can say so without a code change."""
    evidence = (_dated("ev_crm", "deal.status", "open", hours_ago=1),)
    facts = {"deal.status": "open", "deal.owner": "rep_1"}
    strict = _request(facts=facts, required=("deal.status", "deal.owner", "deal.close_date"),
                      evidence=evidence, config={"completeness_floor_bp": 9_000})
    lenient = _request(facts=facts, required=("deal.status", "deal.owner", "deal.close_date"),
                       evidence=evidence, config={"completeness_floor_bp": 5_000})

    assert "context_incomplete" in ContextUnit().evaluate(strict, {}).reason_codes
    assert "context_substantially_known" in ContextUnit().evaluate(lenient, {}).reason_codes


def test_a_malformed_threshold_is_rejected_rather_than_rounded():
    request = _request(facts={"deal.status": "open"}, required=("deal.status",),
                       config={"completeness_floor_bp": 20_000})

    with pytest.raises(ValueError, match="completeness_floor_bp"):
        ContextUnit().evaluate(request, {})


def test_an_empty_snapshot_completes_with_no_fabricated_readings():
    """Knowing nothing is a legitimate, reportable state — not a crash and not a set of zeroes."""
    result = ContextUnit().evaluate(_request(), {})

    assert result.status == ResultStatus.COMPLETED
    assert dict(result.metrics) == {}
    assert result.findings == ()
