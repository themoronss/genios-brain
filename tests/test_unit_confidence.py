"""Executable contract for the Confidence Unit (`core.confidence`).

`core.confidence` is the sole publisher of `confidence_bp` — the number the Decision Maker uses to
decide how hard to lean on everything else Layer 4 produced. Its arithmetic is therefore
load-bearing for replay: a decision recorded last quarter must re-derive the same hash today.

These tests pin four things:

* **Byte-identical migration.** The unit was moved onto the ReasoningUnit framework. A differential
  test runs the pre-framework implementation and the migrated one over the same requests and asserts
  `ReasonerResult.semantic_hash` matches, so the refactor provably changed no output.
* **Each plugin's claim, in isolation.** Bridge, per-fact source quality, coverage/completeness.
* **Determinism** — the same frozen situation twice, byte for byte.
* **Config ordering** — capability config round-trips through JSON in the audit store and returns
  re-ordered; the result must not notice.

**How the reference implementation is provided.** The module was rewritten in place, so the old
class can no longer be imported. `_FrozenConfidenceReasoner` below is a verbatim copy of the
pre-migration `genios_engine/reason/reasoners/confidence.py` (commit 2f77657), kept frozen in this
file. Copying rather than importing is deliberate: it survives the rewrite, and it keeps the
oracle's exact bytes visible to a reviewer who is asked to trust the equivalence claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
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
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.common import (
    active_spec,
    basis_points,
    clamp_bp,
    divide_half_up,
    fact_record,
    integer,
    ratio_bp,
)
from genios_engine.reason.reasoners.confidence import (
    CONFIDENCE_REASON,
    UNDECLARED_METRICS,
    ConfidenceReasoner,
    CoverageCompletenessPlugin,
    FactSourceQualityPlugin,
    LegacyBridgePlugin,
)
from genios_engine.reason.unit import ReasoningUnit, UnitCategory

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


# =============================================================================================
# The frozen oracle — a verbatim copy of the pre-framework implementation
# =============================================================================================

class _FrozenConfidenceReasoner:
    """Pre-migration `ConfidenceReasoner`, copied unchanged. Do not tidy: it is the oracle."""

    _descriptor = ReasonerSpec(reasoner_id="core.confidence", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        source = str(spec.config.get("source_reasoner") or "")
        if source and source in prior_results and "confidence_bp" in prior_results[source].metrics:
            confidence_bp = basis_points(
                prior_results[source].metrics["confidence_bp"], "confidence_bp")
            metrics = {"confidence_bp": confidence_bp, "source": "legacy"}
        else:
            fields = tuple(spec.required_fields or request.capability.required_fields)
            present = [field for field in fields if field in request.context.facts]
            completeness_bp = divide_half_up(len(present) * 10_000, len(fields)) if fields else 10_000
            confidences = []
            corroborations = []
            for field in present:
                record = fact_record(request, field)
                if isinstance(record, Mapping):
                    if "confidence_bp" in record:
                        confidences.append(basis_points(
                            record["confidence_bp"], f"{field}.confidence_bp"))
                    elif "confidence" in record:
                        confidences.append(ratio_bp(record["confidence"], f"{field}.confidence"))
                    groups = integer(record.get("src_count", 1), f"{field}.src_count")
                    corroborations.append(10_000 if groups >= 3 else (8_500 if groups == 2 else 6_000))
            source_bp = divide_half_up(sum(confidences), len(confidences)) if confidences else 5_000
            corroboration_bp = (divide_half_up(sum(corroborations), len(corroborations))
                                if corroborations else 5_000)
            independent_groups = {
                item.independence_group or "unattributed"
                for item in request.context.evidence
            }
            evidence_coverage_bp = min(10_000, len(independent_groups) * 2_500)
            confidence_bp = clamp_bp(divide_half_up(
                source_bp * 40 + completeness_bp * 30 + corroboration_bp * 20
                + evidence_coverage_bp * 10, 100))
            metrics = {"confidence_bp": confidence_bp, "source_quality_bp": source_bp,
                       "completeness_bp": completeness_bp,
                       "corroboration_bp": corroboration_bp,
                       "evidence_coverage_bp": evidence_coverage_bp,
                       "independent_evidence_groups": len(independent_groups)}
        finding = Finding("confidence.decomposition", "confidence", metrics=metrics,
                          reason_codes=("confidence_computed",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              metrics=metrics, findings=(finding,),
                              reason_codes=finding.reason_codes)


# =============================================================================================
# Situation builders
# =============================================================================================

def _capability(*, config=None, required_fields=(), capability_fields=()) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="sales.deal_cooling_probe",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("keep_deals_warm", "Keep live deals moving"),
        reasoners=(ReasonerSpec("core.confidence", "1.0.0",
                                required_fields=tuple(required_fields),
                                config=config or {}),),
        plays=(PlayDefinition(play_id="clarify_next_step", version="1",
                              label="Clarify the next step",
                              steps=("Ask the buyer what happens next.",)),),
        required_fields=tuple(capability_fields),
        policies=(),
    )


def _request(*, facts=None, config=None, evidence=(), required_fields=(),
             capability_fields=(), capability=None) -> ReasoningRequest:
    manifest = capability or _capability(config=config, required_fields=required_fields,
                                         capability_fields=capability_fields)
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=11,
        root_entity_id="deal_northwind",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=facts or {},
        evidence=tuple(evidence),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=manifest,
        context=context,
        evaluation_time=NOW,
        trigger_kind="crm.deal_updated",
    )


def _view(request: ReasoningRequest, prior=None):
    unit = ConfidenceReasoner()
    return unit.retrieve(request, active_spec(request, "core.confidence"), prior or {})


def _prior(reasoner_id: str, **metrics) -> dict[str, ReasonerResult]:
    return {reasoner_id: ReasonerResult(reasoner_id, "1", ResultStatus.COMPLETED,
                                        metrics=metrics)}


def _deal_cooling_request(*, facts=None, evidence=()) -> ReasoningRequest:
    """The shipped capability, whose `core.confidence` spec names four required fields."""
    return _request(capability=DEAL_COOLING_V1, facts=facts, evidence=evidence)


# =============================================================================================
# Identity — the contract a capability resolves against
# =============================================================================================

def test_the_unit_keeps_its_shipped_identity():
    """Capabilities declare ReasonerSpec("core.confidence", "1.0.0"); either half moving is an
    unresolvable capability at startup, not a test failure."""
    unit = ConfidenceReasoner()

    assert unit.spec.reasoner_id == "core.confidence"
    assert unit.spec.version == "1.0.0"
    assert unit.category is UnitCategory.BUSINESS_EVALUATION
    assert isinstance(unit, ReasoningUnit)
    assert isinstance(unit, Reasoner)


def test_the_unit_declares_confidence_as_its_own_metric():
    """It is the CONFIDENCE_AUTHORITY; the declaration is what stops a second publisher landing."""
    assert "confidence_bp" in ConfidenceReasoner.publishes


def test_completeness_is_emitted_but_undeclared_and_that_is_recorded():
    """`core.context` already declares `completeness_bp`, and the roster invariant permits one
    declared publisher per name. The value is still emitted, because removing it would change every
    decision hash — so the collision is recorded rather than fixed."""
    result = ConfidenceReasoner().evaluate(
        _request(required_fields=("deal.status",), facts={"deal.status": "open"}), {})

    assert "completeness_bp" in result.metrics
    assert "completeness_bp" in UNDECLARED_METRICS
    assert "completeness_bp" not in ConfidenceReasoner.publishes


# =============================================================================================
# Plugin 1 — the legacy bridge
# =============================================================================================

def test_the_bridge_carries_a_named_reasoners_confidence_through_unchanged():
    """Strangler packs keep confidence in the old engine; this unit is only its publisher."""
    view = _view(_request(config={"source_reasoner": "legacy.rule"}),
                 _prior("legacy.rule", confidence_bp=7_300))

    (observation,) = LegacyBridgePlugin().contribute(view)

    assert observation.metrics == {"confidence_bp": 7_300}
    assert observation.kind == "confidence.legacy_bridge"


def test_the_bridge_stays_silent_when_no_source_is_configured():
    assert LegacyBridgePlugin().contribute(_view(_request())) == ()


def test_the_bridge_stays_silent_when_the_named_source_did_not_run():
    view = _view(_request(config={"source_reasoner": "legacy.rule"}), {})

    assert LegacyBridgePlugin().contribute(view) == ()


def test_the_bridge_stays_silent_when_the_source_published_no_confidence():
    """A source that ran but scored nothing is not a zero-confidence source."""
    view = _view(_request(config={"source_reasoner": "legacy.rule"}),
                 _prior("legacy.rule", score_bp=8_000))

    assert LegacyBridgePlugin().contribute(view) == ()


def test_a_bridged_confidence_is_re_validated_even_though_the_contract_already_guarantees_it():
    """`ReasonerResult` already refuses a non-bp `confidence_bp`, so the bridge's own check is
    belt-and-braces. It is kept because the pre-framework unit had it, and because the guarantee
    lives in a different module that this one must not depend on quietly."""
    with pytest.raises(ValueError):
        ReasonerResult("legacy.rule", "1", ResultStatus.COMPLETED,
                       metrics={"confidence_bp": 99_999})

    view = _view(_request(config={"source_reasoner": "legacy.rule"}),
                 _prior("legacy.rule", confidence_bp=10_000))
    (observation,) = LegacyBridgePlugin().contribute(view)

    assert observation.metrics["confidence_bp"] == 10_000


def test_the_decomposition_plugins_stand_down_when_the_bridge_applies():
    """The branch is exclusive: a bridged run must not even inspect the facts, so a malformed fact
    cannot fail a run whose confidence came from somewhere else entirely."""
    broken = {"deal.status": {"value": "open", "confidence_bp": "not a number"}}
    view = _view(_request(config={"source_reasoner": "legacy.rule"},
                          required_fields=("deal.status",), facts=broken),
                 _prior("legacy.rule", confidence_bp=6_100))

    assert FactSourceQualityPlugin().contribute(view) == ()
    assert CoverageCompletenessPlugin().contribute(view) == ()


# =============================================================================================
# Plugin 2 — per-fact source quality and corroboration
# =============================================================================================

def test_facts_that_state_their_own_confidence_are_averaged():
    view = _view(_request(required_fields=("deal.status", "deal.value"),
                          facts={"deal.status": {"value": "open", "confidence_bp": 9_000},
                                 "deal.value": {"value": 120_000, "confidence_bp": 6_000}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["source_quality_bp"] == 7_500
    assert observation.metrics["self_reported_fact_count"] == 2


def test_a_legacy_ratio_confidence_is_read_as_basis_points():
    """Older producers wrote 0..1; the unit accepts both spellings of the same claim."""
    view = _view(_request(required_fields=("deal.value",),
                          facts={"deal.value": {"value": 120_000, "confidence": "0.8"}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["source_quality_bp"] == 8_000


def test_explicit_basis_points_win_over_a_ratio_on_the_same_record():
    view = _view(_request(required_fields=("deal.value",),
                          facts={"deal.value": {"value": 1, "confidence_bp": 2_500,
                                                "confidence": "0.9"}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["source_quality_bp"] == 2_500


def test_a_fact_with_no_stated_confidence_leaves_source_quality_neutral():
    """Unknown is not untrustworthy: an unstated confidence must not drag the axis to zero."""
    view = _view(_request(required_fields=("deal.status",),
                          facts={"deal.status": {"value": "open"}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["source_quality_bp"] == 5_000
    assert observation.metrics["self_reported_fact_count"] == 0


@pytest.mark.parametrize("sources,expected", [(1, 6_000), (2, 8_500), (3, 10_000), (9, 10_000)])
def test_corroboration_climbs_a_discrete_ladder_by_source_count(sources, expected):
    view = _view(_request(required_fields=("deal.status",),
                          facts={"deal.status": {"value": "open", "src_count": sources}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["corroboration_bp"] == expected


def test_a_record_without_a_source_count_reads_as_one_sighting():
    view = _view(_request(required_fields=("deal.status",),
                          facts={"deal.status": {"value": "open"}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["corroboration_bp"] == 6_000
    assert observation.metrics["described_fact_count"] == 1


def test_a_bare_scalar_fact_carries_no_metadata_and_is_counted_nowhere_here():
    """It still counts for completeness — it arrived — but it makes no claim about itself."""
    view = _view(_request(required_fields=("derived.engagement",),
                          facts={"derived.engagement": 42}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["described_fact_count"] == 0
    assert observation.metrics["source_quality_bp"] == 5_000
    assert observation.metrics["corroboration_bp"] == 5_000


def test_a_declared_field_that_never_arrived_is_not_scored_for_quality():
    view = _view(_request(required_fields=("deal.status", "deal.value"),
                          facts={"deal.status": {"value": "open", "confidence_bp": 10_000}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["source_quality_bp"] == 10_000
    assert observation.metrics["self_reported_fact_count"] == 1


# =============================================================================================
# Plugin 3 — completeness and independent evidence coverage
# =============================================================================================

def test_completeness_is_the_share_of_declared_fields_that_arrived():
    view = _view(_request(required_fields=("a.one", "a.two", "a.three", "a.four"),
                          facts={"a.one": 1, "a.three": 3}))

    (observation,) = CoverageCompletenessPlugin().contribute(view)

    assert observation.metrics["completeness_bp"] == 5_000
    assert observation.metrics["declared_field_count"] == 4
    assert observation.metrics["present_field_count"] == 2


def test_a_capability_that_declared_nothing_asked_for_nothing_and_got_all_of_it():
    view = _view(_request())

    (observation,) = CoverageCompletenessPlugin().contribute(view)

    assert observation.metrics["completeness_bp"] == 10_000
    assert observation.metrics["declared_field_count"] == 0


def test_the_capabilitys_own_required_fields_are_used_when_the_unit_declares_none():
    view = _view(_request(capability_fields=("a.one", "a.two"), facts={"a.one": 1}))

    (observation,) = CoverageCompletenessPlugin().contribute(view)

    assert observation.metrics["completeness_bp"] == 5_000


@pytest.mark.parametrize("groups,expected", [(0, 0), (1, 2_500), (3, 7_500), (4, 10_000),
                                             (6, 10_000)])
def test_each_independent_source_group_buys_coverage_up_to_a_ceiling(groups, expected):
    facts = {f"f.{index}": index for index in range(max(groups, 1))}
    evidence = tuple(EvidenceRef(evidence_id=f"ev_{index}", field=f"f.{index}", value=index,
                                 independence_group=f"group_{index}")
                     for index in range(groups))

    view = _view(_request(facts=facts, evidence=evidence))
    (observation,) = CoverageCompletenessPlugin().contribute(view)

    assert observation.metrics["evidence_coverage_bp"] == expected
    assert observation.metrics["independent_evidence_groups"] == groups


def test_evidence_without_independence_metadata_collapses_into_one_unknown_group():
    """Missing provenance is one unknown source, not proof of four independent ones."""
    facts = {"f.0": 0, "f.1": 1}
    evidence = (EvidenceRef(evidence_id="ev_0", field="f.0", value=0),
                EvidenceRef(evidence_id="ev_1", field="f.1", value=1))

    view = _view(_request(facts=facts, evidence=evidence))
    (observation,) = CoverageCompletenessPlugin().contribute(view)

    assert observation.metrics["independent_evidence_groups"] == 1
    assert observation.metrics["evidence_coverage_bp"] == 2_500


# =============================================================================================
# The blend and the shape of the result
# =============================================================================================

def test_the_blend_is_the_documented_weighted_mean_of_the_four_axes():
    """40/30/20/10 over source quality, completeness, corroboration and coverage."""
    facts = {"deal.status": {"value": "open", "confidence_bp": 9_000, "src_count": 2},
             "deal.value": {"value": 120_000, "confidence": "0.5", "src_count": 3}}
    evidence = (EvidenceRef(evidence_id="ev_1", field="deal.status", value="open",
                            independence_group="crm"),)

    result = ConfidenceReasoner().evaluate(
        _request(required_fields=("deal.status", "deal.value", "thread.last_inbound"),
                 facts=facts, evidence=evidence), {})

    assert result.metrics["source_quality_bp"] == 7_000        # (9000 + 5000) / 2
    assert result.metrics["corroboration_bp"] == 9_250         # (8500 + 10000) / 2
    assert result.metrics["completeness_bp"] == 6_667          # 2 of 3, half-up
    assert result.metrics["evidence_coverage_bp"] == 2_500
    assert result.metrics["confidence_bp"] == divide_half_up(
        7_000 * 40 + 6_667 * 30 + 9_250 * 20 + 2_500 * 10, 100)


def test_the_result_reports_a_reading_rather_than_a_verdict():
    """Confidence is not a gate; a False here would read downstream as a failed check."""
    result = ConfidenceReasoner().evaluate(_request(facts={"deal.status": "open"}), {})

    assert result.matched is None
    assert result.status is ResultStatus.COMPLETED
    assert result.reason_codes == (CONFIDENCE_REASON,)
    assert result.evidence_ids == ()


def test_the_decomposition_travels_beside_the_score():
    result = ConfidenceReasoner().evaluate(
        _request(required_fields=("deal.status",), facts={"deal.status": "open"}), {})

    (finding,) = result.findings
    assert finding.finding_id == "confidence.decomposition"
    assert finding.kind == "confidence"
    assert dict(finding.metrics) == dict(result.metrics)


def test_a_bridged_run_is_labelled_as_somebody_elses_number():
    """The non-integer `source` metric is the audit trail's way of saying 'not computed here'."""
    result = ConfidenceReasoner().evaluate(
        _request(config={"source_reasoner": "legacy.rule"}),
        _prior("legacy.rule", confidence_bp=7_300))

    assert dict(result.metrics) == {"confidence_bp": 7_300, "source": "legacy"}


def test_a_thin_snapshot_answers_with_low_confidence_rather_than_insufficient_context():
    """The default validator would refuse on a missing declared field. Refusing here would delete
    the only signal that the input was thin, so this unit always answers."""
    result = ConfidenceReasoner().evaluate(
        _request(required_fields=("a.one", "a.two", "a.three", "a.four")), {})

    assert result.status is ResultStatus.COMPLETED
    assert result.missing_fields == ()
    assert result.metrics["completeness_bp"] == 0
    assert result.metrics["confidence_bp"] == 3_000        # (5000*40 + 0*30 + 5000*20 + 0*10)/100


@pytest.mark.parametrize("stated,expected", [(0, 0), (10_000, 10_000)])
def test_boundary_confidences_survive_the_blend_intact(stated, expected):
    view = _view(_request(required_fields=("deal.status",),
                          facts={"deal.status": {"value": "open", "confidence_bp": stated}}))

    (observation,) = FactSourceQualityPlugin().contribute(view)

    assert observation.metrics["source_quality_bp"] == expected


# =============================================================================================
# Determinism and config ordering
# =============================================================================================

def test_the_same_situation_twice_is_byte_identical():
    request = _deal_cooling_request(
        facts={"deal.status": {"value": "open", "confidence_bp": 8_800, "src_count": 2},
               "deal.value": {"value": 90_000, "confidence": "0.75", "src_count": 1},
               "derived.engagement": 31},
        evidence=(EvidenceRef(evidence_id="ev_crm", field="deal.status", value="open",
                              independence_group="crm"),))
    unit = ConfidenceReasoner()

    assert unit.evaluate(request, {}).semantic_hash == unit.evaluate(request, {}).semantic_hash


def test_config_key_order_cannot_change_the_result():
    """Capability config round-trips through JSON in the audit store and returns re-ordered. A unit
    that iterated it unsorted would hash differently on the replay than on the original run."""
    prior = _prior("legacy.rule", confidence_bp=6_400)
    forward = _request(config={"source_reasoner": "legacy.rule", "unused_note": "a",
                               "zzz_trailing": 1})
    reversed_order = _request(config={"zzz_trailing": 1, "unused_note": "a",
                                      "source_reasoner": "legacy.rule"})
    unit = ConfidenceReasoner()

    assert unit.evaluate(forward, prior).semantic_hash == \
        unit.evaluate(reversed_order, prior).semantic_hash


def test_fact_insertion_order_cannot_change_the_result():
    """Facts are declared-order-scanned, so two spellings of the same snapshot must agree."""
    forward = _request(required_fields=("a.one", "a.two"),
                       facts={"a.one": {"value": 1, "confidence_bp": 9_000},
                              "a.two": {"value": 2, "confidence_bp": 3_000}})
    backward = _request(required_fields=("a.two", "a.one"),
                        facts={"a.two": {"value": 2, "confidence_bp": 3_000},
                               "a.one": {"value": 1, "confidence_bp": 9_000}})
    unit = ConfidenceReasoner()

    assert unit.evaluate(forward, {}).semantic_hash == unit.evaluate(backward, {}).semantic_hash


# =============================================================================================
# The differential test — the migration's actual deliverable
# =============================================================================================

def _differential_cases() -> list[tuple[str, ReasoningRequest, dict]]:
    """Representative situations, chosen to reach every branch of the pre-framework code."""
    rich_facts = {"deal.status": {"value": "open", "confidence_bp": 9_000, "src_count": 2},
                  "deal.value": {"value": 120_000, "confidence": "0.8", "src_count": 3},
                  "derived.engagement": 42}
    crm_evidence = (
        EvidenceRef(evidence_id="ev_crm", field="deal.status", value="open",
                    independence_group="crm"),
        EvidenceRef(evidence_id="ev_mail", field="derived.engagement", value=42,
                    independence_group="mailbox"),
    )
    return [
        # The shipped capability, whose confidence spec names four required fields and no config.
        ("deal_cooling_partial_facts",
         _deal_cooling_request(facts=rich_facts, evidence=crm_evidence), {}),
        ("deal_cooling_no_facts_at_all", _deal_cooling_request(), {}),
        ("deal_cooling_every_field_present",
         _deal_cooling_request(facts={**rich_facts,
                                      "thread.last_inbound": {"value": "2026-07-01T00:00:00Z",
                                                              "confidence_bp": 10_000,
                                                              "src_count": 4}}), {}),
        # The legacy bridge, taken and not taken.
        ("bridge_taken", _request(config={"source_reasoner": "legacy.rule"},
                                  required_fields=("deal.status",),
                                  facts={"deal.status": {"value": "open"}}),
         _prior("legacy.rule", confidence_bp=7_300)),
        ("bridge_taken_at_zero", _request(config={"source_reasoner": "legacy.rule"}),
         _prior("legacy.rule", confidence_bp=0)),
        ("bridge_taken_at_ceiling", _request(config={"source_reasoner": "legacy.rule"}),
         _prior("legacy.rule", confidence_bp=10_000)),
        ("bridge_named_but_source_absent",
         _request(config={"source_reasoner": "legacy.rule"},
                  required_fields=("deal.status",), facts={"deal.status": "open"}), {}),
        ("bridge_named_but_source_published_no_confidence",
         _request(config={"source_reasoner": "legacy.rule"},
                  required_fields=("deal.status",), facts={"deal.status": "open"}),
         _prior("legacy.rule", score_bp=9_000)),
        ("bridge_configured_empty", _request(config={"source_reasoner": ""},
                                             required_fields=("deal.status",),
                                             facts={"deal.status": "open"}), {}),
        # Config present and absent on the computed branch.
        ("no_config_no_fields", _request(), {}),
        ("capability_fields_fallback",
         _request(capability_fields=("a.one", "a.two", "a.three"), facts={"a.one": 1}), {}),
        # Fact-shape edge cases.
        ("scalar_facts_only",
         _request(required_fields=("a.one", "a.two"), facts={"a.one": 1, "a.two": "two"}), {}),
        ("ratio_confidences",
         _request(required_fields=("a.one", "a.two"),
                  facts={"a.one": {"value": 1, "confidence": "0.25"},
                         "a.two": {"value": 2, "confidence": "1"}}), {}),
        ("boundary_confidences",
         _request(required_fields=("a.one", "a.two"),
                  facts={"a.one": {"value": 1, "confidence_bp": 0, "src_count": 1},
                         "a.two": {"value": 2, "confidence_bp": 10_000, "src_count": 3}}), {}),
        ("rounding_half_up_on_three_fields",
         _request(required_fields=("a.one", "a.two", "a.three"),
                  facts={"a.one": {"value": 1, "confidence_bp": 3_333},
                         "a.two": {"value": 2, "confidence_bp": 3_333}}), {}),
        # Evidence coverage: none, unattributed, saturating.
        ("no_evidence", _request(required_fields=("a.one",), facts={"a.one": 1}), {}),
        ("unattributed_evidence",
         _request(required_fields=("a.one", "a.two"), facts={"a.one": 1, "a.two": 2},
                  evidence=(EvidenceRef(evidence_id="ev_1", field="a.one", value=1),
                            EvidenceRef(evidence_id="ev_2", field="a.two", value=2))), {}),
        ("saturating_evidence_coverage",
         _request(required_fields=tuple(f"f.{index}" for index in range(6)),
                  facts={f"f.{index}": index for index in range(6)},
                  evidence=tuple(EvidenceRef(evidence_id=f"ev_{index}", field=f"f.{index}",
                                             value=index, independence_group=f"g_{index}")
                                 for index in range(6))), {}),
    ]


@pytest.mark.parametrize("name,request_,prior", _differential_cases(),
                         ids=[case[0] for case in _differential_cases()])
def test_the_migrated_unit_is_byte_identical_to_the_pre_framework_one(name, request_, prior):
    """The migration's whole contract: same metrics, same finding, same codes, same hash.

    `semantic_hash` covers every field a downstream consumer or a replay can observe — status,
    matched, metrics, findings, adjustments, checks, evidence ids, missing fields, reason codes — so
    one equality here is the full equivalence claim, not a spot check.
    """
    old = _FrozenConfidenceReasoner().evaluate(request_, prior)
    new = ConfidenceReasoner().evaluate(request_, prior)

    assert new.semantic_hash == old.semantic_hash, name
    assert dict(new.metrics) == dict(old.metrics)
    assert new.matched == old.matched
    assert new.reason_codes == old.reason_codes
    assert new.evidence_ids == old.evidence_ids


def test_a_malformed_fact_still_fails_the_run_exactly_as_it_used_to():
    """Preserved, not fixed: a fact whose stated confidence is unparseable takes the whole run
    down instead of degrading. Changing it would change behaviour, which this migration may not."""
    request = _request(required_fields=("deal.status",),
                       facts={"deal.status": {"value": "open", "confidence_bp": 12_000}})

    with pytest.raises(ValueError):
        _FrozenConfidenceReasoner().evaluate(request, {})
    with pytest.raises(ValueError):
        ConfidenceReasoner().evaluate(request, {})


def test_a_capability_that_never_declared_this_unit_is_refused_by_both():
    other = CapabilityManifest(
        capability_id="sales.other", version="1.0.0", domain="sales", root_entity_type="deal",
        goal=Goal("g", "Goal"),
        reasoners=(ReasonerSpec("core.temporal", "1.0.0"),),
        plays=(PlayDefinition(play_id="p", version="1", label="P", steps=("Do it.",)),),
        policies=(),
    )
    request = _request(capability=other)

    with pytest.raises(ValueError):
        _FrozenConfidenceReasoner().evaluate(request, {})
    with pytest.raises(ValueError):
        ConfidenceReasoner().evaluate(request, {})
