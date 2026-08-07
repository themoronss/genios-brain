"""Executable contract for the Risk Unit (`core.risk`) and proof of its migration.

`core.risk` ships inside `sales.deal_cooling`. Its `ReasonerResult.semantic_hash` is inside the
decision trace, the replay comparison, and the legacy-parity ratchet, so the migration onto the
`ReasoningUnit` framework was required to be a pure refactor: same arithmetic, same finding, same
adjustments in the same order, same reason codes, therefore the same hash.

**How equivalence is proved here.** The pre-migration implementation is kept in this file as
`_LegacyRiskReasoner`, a verbatim frozen copy, rather than imported from its module. It could not
be imported: the migration rewrites `risk.py` in place, so after the change there is nothing left
to import — and pinning the old code as a literal is stronger anyway, because the reference cannot
drift when someone later edits the live unit. The copy below is byte-for-byte the shipped
`RiskReasoner.evaluate` as of the commit before the migration, with only the class name changed.

The properties pinned:

* **Byte-identical output.** Old and new agree on `semantic_hash` across every representative
  input, including the real shipped `DEAL_COOLING_V1` config.
* **Each plugin alone.** Decay, relationship health, and the authored mitigation table are three
  separable claims and are tested as such.
* **Total ordering.** Adjustment order is a function of content, so a config that arrives with its
  keys permuted — which is exactly what the audit store returns — hashes identically.
* **It reports, it never gates.** `matched` is None, and no check ever leaves this unit.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.contracts.reasoning import CandidateAdjustment, Finding
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.common import (
    active_spec,
    basis_points,
    clamp_bp,
    divide_half_up,
    integer,
)
from genios_engine.reason.reasoners.risk import (
    MomentumDecayPlugin,
    PlayMitigationPlugin,
    RelationshipHealthPlugin,
    RiskReasoner,
    RiskUnit,
)
from genios_engine.reason.unit import ReasoningUnit, UnitCategory, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------------------------
# The frozen pre-migration implementation. Do not "improve" it — its only job is to disagree.
# ---------------------------------------------------------------------------------------------

class _LegacyRiskReasoner:
    _descriptor = ReasonerSpec(reasoner_id="core.risk", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        temporal = prior_results.get(str(spec.config.get("temporal_reasoner") or "core.temporal"))
        relationship = prior_results.get(str(
            spec.config.get("relationship_reasoner") or "core.relationship"))
        drop = integer((temporal.metrics if temporal else {}).get("drop_bp", 0), "drop_bp")
        relationship_risk = integer((relationship.metrics if relationship else {}).get(
            "relationship_risk_bp", 0), "relationship_risk_bp")
        base = basis_points(spec.config.get("base_risk_bp", 1_000), "base_risk_bp")
        risk_bp = clamp_bp(base + divide_half_up(drop * 60 + relationship_risk * 40, 100))
        adjustments = []
        for play_id, reduction in sorted(
                dict(spec.config.get("play_risk_reduction_bp") or {}).items()):
            adjustments.append(CandidateAdjustment(
                str(play_id), "risk", -basis_points(
                    reduction, f"{play_id}.risk_reduction_bp"),
                                                    "play_mitigates_detected_risk"))
        finding = Finding("risk.do_nothing", "risk", metrics={"risk_bp": risk_bp},
                          reason_codes=("deal_momentum_risk",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              metrics=finding.metrics, findings=(finding,),
                              adjustments=tuple(adjustments),
                              reason_codes=finding.reason_codes)


# ---------------------------------------------------------------------------------------------
# Fixtures: a real capability, a real snapshot, real prior results
# ---------------------------------------------------------------------------------------------

#: The three plays deal_cooling actually declares, so authored mitigations name real candidates.
PLAYS = ("restore_momentum", "multithread_account", "clarify_next_step")

#: The config the shipped capability really carries for core.risk. Read from the pack rather than
#: retyped, so this file cannot go stale the day someone re-authors the capability.
SHIPPED_CONFIG = dict(next(spec for spec in DEAL_COOLING_V1.reasoners
                           if spec.reasoner_id == "core.risk").config)


def _request(*, config=None, required_fields=(), facts=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.risk", "1.0.0", dependencies=(),
                                required_fields=tuple(required_fields),
                                config=config or {}),),
        plays=tuple(PlayDefinition(play_id=play, version="1", label=play.replace("_", " "),
                                   steps=("Do the thing",)) for play in PLAYS),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=21,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=facts if facts is not None else {"deal.status": "open"},
    )
    return ReasoningRequest(
        org_id="org_1", capability=capability, context=context, evaluation_time=NOW,
        trigger_kind="email.received", config_snapshot_id="cfg_1")


def _completed(reasoner_id: str, **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1.0.0",
                          status=ResultStatus.COMPLETED, metrics=metrics)


def _prior(*results: ReasonerResult) -> dict[str, ReasonerResult]:
    return {item.reasoner_id: item for item in results}


def _view(prior=None, *, config=None) -> UnitView:
    request = _request(config=config)
    return UnitView(request=request, spec=request.capability.reasoners[0],
                    prior=_prior(*(prior or ())))


def _run(prior=None, *, config=None, required_fields=(), facts=None) -> ReasonerResult:
    return RiskUnit().evaluate(_request(config=config, required_fields=required_fields,
                                        facts=facts), _prior(*(prior or ())))


# ---------------------------------------------------------------------------------------------
# The differential: old and new must be indistinguishable
# ---------------------------------------------------------------------------------------------

#: (label, prior results, config) — chosen to cover every branch the old unit had: both
#: dependencies present / absent / partial, the default and an authored base, redirected dependency
#: ids, the clamp ceiling and floor, a rounding case that is not a clean division, an empty and a
#: populated mitigation table, and the real shipped config.
CASES = (
    ("nothing_ran_before_it", (), {}),
    ("temporal_only", (_completed("core.temporal", drop_bp=6_200),), {}),
    ("relationship_only", (_completed("core.relationship", relationship_risk_bp=7_500),), {}),
    ("both_dependencies",
     (_completed("core.temporal", drop_bp=6_200),
      _completed("core.relationship", relationship_risk_bp=7_500)), {}),
    ("dependency_ran_without_the_metric",
     (_completed("core.temporal", urgency_bp=4_000),), {}),
    ("dependency_was_skipped",
     (ReasonerResult("core.temporal", "1.0.0", ResultStatus.SKIPPED),), {}),
    ("redirected_dependency_ids",
     (_completed("sales.decay", drop_bp=9_000),
      _completed("sales.coverage", relationship_risk_bp=1_000)),
     {"temporal_reasoner": "sales.decay", "relationship_reasoner": "sales.coverage"}),
    ("authored_base_floor", (), {"base_risk_bp": 4_200}),
    ("zero_base_floor", (_completed("core.temporal", drop_bp=1_000),), {"base_risk_bp": 0}),
    ("clamp_ceiling",
     (_completed("core.temporal", drop_bp=10_000),
      _completed("core.relationship", relationship_risk_bp=10_000)),
     {"base_risk_bp": 9_000}),
    ("rounds_half_up",
     (_completed("core.temporal", drop_bp=1),
      _completed("core.relationship", relationship_risk_bp=2)), {}),
    ("empty_mitigation_table", (), {"play_risk_reduction_bp": {}}),
    ("zero_valued_mitigation", (), {"play_risk_reduction_bp": {"restore_momentum": 0}}),
    ("mitigations_only", (), {"play_risk_reduction_bp": {
        "restore_momentum": 1_800, "clarify_next_step": 1_200}}),
    ("shipped_deal_cooling_config",
     (_completed("core.temporal", drop_bp=6_000),
      _completed("core.relationship", relationship_risk_bp=6_667)), SHIPPED_CONFIG),
)


@pytest.mark.parametrize("label,prior,config", CASES, ids=[case[0] for case in CASES])
def test_the_migrated_unit_hashes_identically_to_the_one_it_replaced(label, prior, config):
    """The whole point of the exercise. Anything but equality here breaks replay."""
    request = _request(config=config)
    prior_results = _prior(*prior)

    old = _LegacyRiskReasoner().evaluate(request, prior_results)
    new = RiskUnit().evaluate(request, prior_results)

    assert new.semantic_hash == old.semantic_hash, label


@pytest.mark.parametrize("label,prior,config", CASES, ids=[case[0] for case in CASES])
def test_every_visible_field_matches_field_by_field(label, prior, config):
    """The hash proves equality; this names *which* field moved when it ever fails."""
    request = _request(config=config)
    prior_results = _prior(*prior)

    old = _LegacyRiskReasoner().evaluate(request, prior_results)
    new = RiskUnit().evaluate(request, prior_results)

    assert new.status == old.status
    assert new.matched == old.matched
    assert dict(new.metrics) == dict(old.metrics)
    assert new.findings == old.findings
    assert new.adjustments == old.adjustments
    assert new.checks == old.checks == ()
    assert new.evidence_ids == old.evidence_ids == ()
    assert new.missing_fields == old.missing_fields == ()
    assert new.reason_codes == old.reason_codes


def test_the_shipped_case_is_not_vacuous():
    """Guards the guard: the shipped case proves nothing if the pack stops authoring config."""
    assert len(dict(SHIPPED_CONFIG.get("play_risk_reduction_bp") or {})) > 1
    assert "base_risk_bp" in SHIPPED_CONFIG

    result = _run((_completed("core.temporal", drop_bp=6_000),
                   _completed("core.relationship", relationship_risk_bp=6_667)),
                  config=SHIPPED_CONFIG)

    assert len(result.adjustments) == 3


# ---------------------------------------------------------------------------------------------
# The arithmetic, stated as numbers rather than as a re-implementation
# ---------------------------------------------------------------------------------------------

def test_the_blend_is_sixty_forty_over_the_authored_floor():
    """1000 + round((6200*60 + 7500*40)/100) = 1000 + round(6720) = 7720."""
    result = _run((_completed("core.temporal", drop_bp=6_200),
                   _completed("core.relationship", relationship_risk_bp=7_500)))

    assert result.metrics["risk_bp"] == 7_720


def test_rounding_is_half_up_on_the_summed_numerator_not_per_term():
    """(1*60 + 2*40)/100 = 1.4 -> 1. Rounding each term first would have given 1+1 = 2."""
    result = _run((_completed("core.temporal", drop_bp=1),
                   _completed("core.relationship", relationship_risk_bp=2)))

    assert result.metrics["risk_bp"] == 1_001


def test_risk_saturates_rather_than_overflowing_the_scale():
    result = _run((_completed("core.temporal", drop_bp=10_000),
                   _completed("core.relationship", relationship_risk_bp=10_000)),
                  config={"base_risk_bp": 9_000})

    assert result.metrics["risk_bp"] == 10_000


def test_a_quiet_situation_still_carries_the_authored_floor():
    """A deal that looks perfect is still a deal that can be lost."""
    assert _run(config={"base_risk_bp": 4_200}).metrics["risk_bp"] == 4_200
    assert _run().metrics["risk_bp"] == 1_000
    assert _run(config={"base_risk_bp": 0}).metrics["risk_bp"] == 0


@pytest.mark.parametrize("bad", [10_001, -1, "high", 1.5, True, None])
def test_a_malformed_floor_is_an_authoring_fault_not_a_silent_default(bad):
    with pytest.raises(ValueError):
        _run(config={"base_risk_bp": bad})


# ---------------------------------------------------------------------------------------------
# Each plugin, alone
# ---------------------------------------------------------------------------------------------

def test_momentum_decay_reads_the_temporal_unit_rather_than_the_clock():
    observation, = MomentumDecayPlugin().contribute(
        _view([_completed("core.temporal", drop_bp=6_200)]))

    assert observation.plugin_id == "momentum_decay"
    assert observation.metrics["drop_bp"] == 6_200


def test_momentum_decay_follows_the_authored_dependency_id():
    view = _view([_completed("sales.decay", drop_bp=4_400)],
                 config={"temporal_reasoner": "sales.decay"})

    observation, = MomentumDecayPlugin().contribute(view)

    assert observation.metrics["drop_bp"] == 4_400


def test_a_dependency_that_did_not_run_contributes_zero_not_silence():
    """The documented asymmetry with core.impact: risk_bp must always be publishable, because a
    missing risk_bp reads downstream as 'unknown' rather than 'low'."""
    decay, = MomentumDecayPlugin().contribute(_view())
    health, = RelationshipHealthPlugin().contribute(_view())

    assert decay.metrics["drop_bp"] == 0
    assert health.metrics["relationship_risk_bp"] == 0


def test_relationship_health_reads_the_relationship_unit():
    observation, = RelationshipHealthPlugin().contribute(
        _view([_completed("core.relationship", relationship_risk_bp=7_500)],
              config={"relationship_reasoner": "core.relationship"}))

    assert observation.plugin_id == "relationship_health"
    assert observation.metrics["relationship_risk_bp"] == 7_500


def test_an_unauthored_mitigation_table_produces_no_observation():
    assert PlayMitigationPlugin().contribute(_view()) == ()
    assert PlayMitigationPlugin().contribute(_view(config={"play_risk_reduction_bp": {}})) == ()


def test_the_mitigation_plugin_reports_the_whole_authored_table_validated():
    observation, = PlayMitigationPlugin().contribute(_view(config={
        "play_risk_reduction_bp": {"restore_momentum": 1_800, "clarify_next_step": 1_200}}))

    assert observation.plugin_id == "risk_mitigation"
    assert dict(observation.metrics) == {"restore_momentum": 1_800, "clarify_next_step": 1_200}


@pytest.mark.parametrize("bad", [10_001, -1, 1.5, True, None])
def test_a_malformed_mitigation_is_an_authoring_fault(bad):
    with pytest.raises(ValueError):
        PlayMitigationPlugin().contribute(
            _view(config={"play_risk_reduction_bp": {"restore_momentum": bad}}))


# ---------------------------------------------------------------------------------------------
# Adjustments: authored mitigation, never a choice
# ---------------------------------------------------------------------------------------------

def test_authored_mitigations_become_negative_risk_adjustments():
    result = _run(config={"play_risk_reduction_bp": {
        "restore_momentum": 1_800, "multithread_account": 1_600}})

    assert [(item.play_id, item.component, item.delta_bp) for item in result.adjustments] == [
        ("multithread_account", "risk", -1_600), ("restore_momentum", "risk", -1_800)]
    assert {item.reason_code for item in result.adjustments} == {"play_mitigates_detected_risk"}


def test_adjustment_order_is_alphabetical_by_play_not_arrival_order():
    """The bug this ordering was fixed for: the audit store returns config keys re-sorted, so an
    insertion-ordered scan made a replayed run hash differently from the original."""
    forward = _run(config={"play_risk_reduction_bp": {
        "restore_momentum": 1_800, "clarify_next_step": 1_200, "multithread_account": 1_600}})
    reverse = _run(config={"play_risk_reduction_bp": {
        "multithread_account": 1_600, "clarify_next_step": 1_200, "restore_momentum": 1_800}})

    assert [item.play_id for item in forward.adjustments] == [
        "clarify_next_step", "multithread_account", "restore_momentum"]
    assert forward.semantic_hash == reverse.semantic_hash


def test_a_config_key_permutation_cannot_move_the_result_hash():
    """The same assertion driven from the real shipped config, in two different key orders."""
    forward = dict(SHIPPED_CONFIG)
    reverse = {key: SHIPPED_CONFIG[key] for key in reversed(list(SHIPPED_CONFIG))}
    reverse["play_risk_reduction_bp"] = {
        key: dict(SHIPPED_CONFIG["play_risk_reduction_bp"])[key]
        for key in reversed(list(dict(SHIPPED_CONFIG["play_risk_reduction_bp"])))}
    prior = (_completed("core.temporal", drop_bp=6_000),
             _completed("core.relationship", relationship_risk_bp=6_667))

    assert _run(prior, config=forward).semantic_hash == _run(prior, config=reverse).semantic_hash


def test_the_unit_emits_no_checks_and_selects_nothing():
    """A unit analyses. Emitting a check or an elimination would make it a decision authority."""
    result = _run((_completed("core.temporal", drop_bp=9_500),), config=SHIPPED_CONFIG)

    assert result.checks == ()
    assert result.matched is None


# ---------------------------------------------------------------------------------------------
# The finding and the shape of the result
# ---------------------------------------------------------------------------------------------

def test_the_single_finding_names_the_do_nothing_branch():
    result = _run((_completed("core.temporal", drop_bp=6_200),))
    finding, = result.findings

    assert finding.finding_id == "risk.do_nothing"
    assert finding.kind == "risk"
    assert finding.matched is None
    assert dict(finding.metrics) == {"risk_bp": result.metrics["risk_bp"]}
    assert finding.reason_codes == ("deal_momentum_risk",)


def test_the_unit_cites_no_evidence_of_its_own():
    """Every claim is downstream of a metric another unit already evidenced; re-attaching that
    unit's evidence ids here would double-count them in the audit trail."""
    result = _run((_completed("core.temporal", drop_bp=6_200),),
                  facts={"deal.status": "open", "derived.engagement": {"value_bp": 3_800}})

    assert result.evidence_ids == ()


def test_the_unit_never_returns_insufficient_context():
    """It reads no facts, so a declared required field it happens not to have cannot stop it.

    The default validator would raise MissingContextError here and terminate the capability at its
    required failure policy — a status this unit has never returned.
    """
    result = _run((_completed("core.temporal", drop_bp=6_200),),
                  required_fields=("deal.absent_field",))

    assert result.status == ResultStatus.COMPLETED
    assert result.missing_fields == ()


def test_only_risk_bp_is_published():
    result = _run((_completed("core.temporal", drop_bp=6_200),))

    assert set(result.metrics) == {"risk_bp"}
    assert RiskUnit.publishes == ("risk_bp",)


# ---------------------------------------------------------------------------------------------
# Identity, framework conformance, determinism
# ---------------------------------------------------------------------------------------------

def test_identity_is_frozen_because_capabilities_pin_it():
    unit = RiskUnit()

    assert unit.spec.reasoner_id == "core.risk"
    assert unit.spec.version == "1.0.0"
    assert unit.category is UnitCategory.BUSINESS_EVALUATION
    assert isinstance(unit, Reasoner)
    assert isinstance(unit, ReasoningUnit)


def test_the_legacy_class_name_still_resolves():
    """`reasoners/__init__.py` and the roster import `RiskReasoner` by name."""
    assert RiskReasoner is RiskUnit
    assert RiskReasoner().spec == RiskUnit().spec


def test_the_capability_still_declares_the_version_this_unit_answers_to():
    spec = next(item for item in DEAL_COOLING_V1.reasoners if item.reasoner_id == "core.risk")

    assert (spec.reasoner_id, spec.version) == (RiskUnit.unit_id, RiskUnit.version)


def test_the_same_input_twice_gives_the_same_hash():
    prior = (_completed("core.temporal", drop_bp=6_200),
             _completed("core.relationship", relationship_risk_bp=7_500))

    assert _run(prior, config=SHIPPED_CONFIG).semantic_hash == \
        _run(prior, config=SHIPPED_CONFIG).semantic_hash


def test_prior_result_arrival_order_cannot_move_the_hash():
    temporal = _completed("core.temporal", drop_bp=6_200)
    relationship = _completed("core.relationship", relationship_risk_bp=7_500)
    request = _request(config=SHIPPED_CONFIG)

    forward = RiskUnit().evaluate(request, {"core.temporal": temporal,
                                            "core.relationship": relationship})
    reverse = RiskUnit().evaluate(request, {"core.relationship": relationship,
                                            "core.temporal": temporal})

    assert forward.semantic_hash == reverse.semantic_hash


def test_a_capability_that_does_not_declare_this_unit_is_a_deployment_fault():
    request = _request()
    other = CapabilityManifest(
        capability_id="sales.other", version="1.0.0", domain="sales", root_entity_type="deal",
        goal=Goal("g1", "Something else"),
        reasoners=(ReasonerSpec("core.temporal", "1.0.0"),),
        plays=(PlayDefinition(play_id="p1", version="1", label="P", steps=("s",)),),
        policies=())
    request = ReasoningRequest(org_id="org_1", capability=other, context=request.context,
                               evaluation_time=NOW, trigger_kind="email.received")

    with pytest.raises(ValueError):
        RiskUnit().evaluate(request, {})
