"""Executable contract for the Priority Unit (`core.priority`).

`core.priority` is the system's *priority authority*: the only unit permitted to publish
`urgency_bp` and `priority_override_bp`. Those two numbers feed the orchestrator's ranking math,
so a one-basis-point drift here re-scores every ranked decision the product has ever made and
invalidates stored replay hashes. These tests therefore pin behaviour at the hash level, not just
at the value level.

**How equivalence is proved.** The pre-migration implementation is kept below as a frozen
reference copy (`_LegacyPriorityReasoner`), copied verbatim from the module before the rewrite,
rather than imported. Importing was not an option: the migration rewrites `priority.py` in place
and must keep the class name `PriorityReasoner`, so the old code no longer exists anywhere to
import from. A frozen copy also makes the test self-contained — it keeps proving the contract even
if the module is refactored again, because the reference cannot drift with the implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    FailurePolicy,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.decision_maker import PRIORITY_AUTHORITY
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.common import active_spec, clamp_bp, integer
from genios_engine.reason.reasoners.priority import (
    NEUTRAL_URGENCY_BP,
    PRIORITY_READY_REASON,
    DeclaredOverridePlugin,
    DeclaredUrgencyPlugin,
    MaximumUrgencyPlugin,
    PriorityReasoner,
)
from genios_engine.reason.unit import ReasoningUnit, UnitCategory, Verdict

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)

#: The config the shipped `sales.deal_cooling` capability declares for this reasoner. Anything
#: that changes the result under this exact config changes production decision hashes.
DEAL_COOLING_V1_CONFIG = {"source_reasoner": "core.temporal"}


# ---------------------------------------------------------------------------------------------
# Frozen reference: the implementation as it stood before the migration, byte for byte.
# ---------------------------------------------------------------------------------------------


class _LegacyPriorityReasoner:
    """Produces global priority inputs; the orchestrator's math stage ranks actual candidates."""

    _descriptor = ReasonerSpec(reasoner_id="core.priority", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        source = str(spec.config.get("source_reasoner") or "")
        if source and source in prior_results:
            metrics = prior_results[source].metrics
            override = metrics.get("priority_bp")
            urgency = metrics.get("urgency_bp", 5_000)
        else:
            override = None
            urgency = max((integer(result.metrics.get("urgency_bp", 0), "urgency_bp")
                           for result in prior_results.values()), default=5_000)
        output = {"urgency_bp": clamp_bp(integer(urgency, "urgency_bp"))}
        if override is not None:
            output["priority_override_bp"] = clamp_bp(integer(
                override, "priority_override_bp"))
        finding = Finding("priority.inputs", "priority", metrics=output,
                          reason_codes=("priority_inputs_ready",))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              metrics=output, findings=(finding,),
                              reason_codes=finding.reason_codes)


# ---------------------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------------------


def _request(*, config=None, required_fields=(), facts=None, evidence=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("recover_stalled_pipeline", "Recover stalled pipeline"),
        reasoners=(ReasonerSpec("core.priority", "1.0.0",
                                input_kind="reasoner_results",
                                output_kind="priority_inputs",
                                required_fields=tuple(required_fields),
                                failure_policy=FailurePolicy.REQUIRED,
                                config=config if config is not None else {}),),
        plays=(PlayDefinition(play_id="nudge_buyer", version="1", label="Nudge the buyer",
                              steps=("Send a short check-in",)),),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=4,
        root_entity_id="deal_northwind",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=facts or {},
        evidence=tuple(evidence),
    )
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="crm.deal_updated")


def _completed(reasoner_id: str, **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id, "1.0.0", ResultStatus.COMPLETED, metrics=metrics)


def _skipped(reasoner_id: str) -> ReasonerResult:
    return ReasonerResult(reasoner_id, "1.0.0", ResultStatus.SKIPPED)


def _view(request: ReasoningRequest, prior=None):
    unit = PriorityReasoner()
    return unit.retrieve(request, request.capability.reasoners[0], prior or {})


#: Every situation the unit can be in, as (label, request, prior_results). Used both by the
#: differential test and by the determinism test so the two can never cover different ground.
def _scenarios() -> tuple[tuple[str, ReasoningRequest, dict], ...]:
    return (
        ("no config, no priors",
         _request(), {}),
        ("no config, priors with urgency",
         _request(), {"core.temporal": _completed("core.temporal", urgency_bp=7_200),
                      "core.risk": _completed("core.risk", urgency_bp=3_100)}),
        ("no config, priors without any urgency",
         _request(), {"core.relationship": _completed("core.relationship", coverage_bp=4_000)}),
        ("no config, a skipped prior only",
         _request(), {"core.temporal": _skipped("core.temporal")}),
        ("shipped deal_cooling config, source ran with urgency",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.temporal": _completed("core.temporal", urgency_bp=8_800, drop_bp=6_000),
          "core.risk": _completed("core.risk", urgency_bp=9_900)}),
        ("shipped deal_cooling config, source ran with urgency and priority",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.temporal": _completed("core.temporal", urgency_bp=8_800, priority_bp=6_500)}),
        ("shipped deal_cooling config, source ran with priority only",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.temporal": _completed("core.temporal", priority_bp=6_500)}),
        ("shipped deal_cooling config, source absent from priors",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.risk": _completed("core.risk", urgency_bp=9_900)}),
        ("shipped deal_cooling config, source skipped",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.temporal": _skipped("core.temporal"),
          "core.risk": _completed("core.risk", urgency_bp=9_900)}),
        ("empty source_reasoner falls back to the maximum",
         _request(config={"source_reasoner": ""}),
         {"core.risk": _completed("core.risk", urgency_bp=2_500)}),
        ("null source_reasoner falls back to the maximum",
         _request(config={"source_reasoner": None}),
         {"core.risk": _completed("core.risk", urgency_bp=2_500)}),
        ("boundary: zero urgency from the declared source",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.temporal": _completed("core.temporal", urgency_bp=0, priority_bp=0)}),
        ("boundary: maximal urgency and override",
         _request(config=DEAL_COOLING_V1_CONFIG),
         {"core.temporal": _completed("core.temporal", urgency_bp=10_000, priority_bp=10_000)}),
        ("boundary: zero across every prior on the derived path",
         _request(),
         {"core.temporal": _completed("core.temporal", urgency_bp=0),
          "core.risk": _completed("core.risk", urgency_bp=0)}),
        ("unrelated config keys are ignored",
         _request(config={"unused_knob_bp": 4_000}),
         {"core.temporal": _completed("core.temporal", urgency_bp=1_234)}),
        ("required_fields declared but no facts present",
         _request(required_fields=("deal.status", "deal.value")),
         {"core.temporal": _completed("core.temporal", urgency_bp=6_100)}),
        ("facts and evidence present are never consulted",
         _request(config=DEAL_COOLING_V1_CONFIG,
                  required_fields=("deal.status",),
                  facts={"deal.status": "open"},
                  evidence=(EvidenceRef("ev_1", "deal.status", "open"),)),
         {"core.temporal": _completed("core.temporal", urgency_bp=4_400)}),
    )


# ---------------------------------------------------------------------------------------------
# The differential test — the deliverable
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("label, request_, prior", _scenarios(),
                         ids=[case[0] for case in _scenarios()])
def test_migrated_unit_is_hash_identical_to_the_frozen_legacy_implementation(label, request_,
                                                                            prior):
    """The absolute constraint: same inputs, same `semantic_hash`.

    A changed hash is not a cosmetic difference — it breaks stored replay and the legacy-parity
    ratchet, because the hash covers status, matched, metrics, findings, adjustments, checks,
    evidence ids, missing fields and reason codes together.
    """
    old = _LegacyPriorityReasoner().evaluate(request_, prior)
    new = PriorityReasoner().evaluate(request_, prior)

    assert new.semantic_hash == old.semantic_hash, label
    assert new.to_semantic_dict() == old.to_semantic_dict(), label


def test_the_two_implementations_reject_the_same_malformed_readings():
    """Equivalence includes refusal: a non-integer urgency must still be a loud fault."""
    request_ = _request(config=DEAL_COOLING_V1_CONFIG)
    prior = {"core.temporal": _completed("core.temporal")}
    # Bypass the contract's own bp validation to construct the malformed reading the reasoners
    # are defending against.
    object.__setattr__(prior["core.temporal"], "metrics", {"urgency_bp": "not a number"})

    with pytest.raises(ValueError) as legacy:
        _LegacyPriorityReasoner().evaluate(request_, prior)
    with pytest.raises(ValueError) as migrated:
        PriorityReasoner().evaluate(request_, prior)

    assert str(migrated.value) == str(legacy.value)


def test_a_malformed_urgency_is_reported_before_a_malformed_override():
    """Plugin ordering must preserve which fault surfaces first, or an operator chasing a bad
    deploy is sent to the wrong reasoner."""
    request_ = _request(config=DEAL_COOLING_V1_CONFIG)
    prior = {"core.temporal": _completed("core.temporal")}
    object.__setattr__(prior["core.temporal"], "metrics",
                       {"urgency_bp": "bad", "priority_bp": "also bad"})

    with pytest.raises(ValueError, match="urgency_bp must be an integer"):
        PriorityReasoner().evaluate(request_, prior)


# ---------------------------------------------------------------------------------------------
# Identity and roster obligations
# ---------------------------------------------------------------------------------------------


def test_identity_is_frozen():
    """The capability packs declare `ReasonerSpec("core.priority", "1.0.0")`; a bumped version
    fails registry resolution at deploy time, not at test time."""
    unit = PriorityReasoner()

    assert unit.unit_id == "core.priority" == PRIORITY_AUTHORITY
    assert unit.version == "1.0.0"
    assert unit.spec == ReasonerSpec("core.priority", "1.0.0")
    assert unit.category is UnitCategory.BUSINESS_EVALUATION
    assert isinstance(unit, ReasoningUnit)
    assert isinstance(unit, Reasoner)


def test_it_declares_the_two_reserved_metrics_and_nothing_else():
    """The priority authority owns exactly this pair. Declaring a third metric would let this unit
    write something another unit owns; declaring fewer would make the framework reject its own
    output."""
    assert set(PriorityReasoner().publishes) == {"urgency_bp", "priority_override_bp"}


def test_publishing_an_undeclared_metric_is_refused_by_the_framework():
    class Leaky(PriorityReasoner):
        def evaluate_meaning(self, view, metrics, observations):
            return Verdict(metrics={"urgency_bp": 1_000, "confidence_bp": 9_000})

    with pytest.raises(ValueError, match="undeclared metrics"):
        Leaky().evaluate(_request(), {})


def test_a_capability_that_does_not_declare_this_reasoner_is_a_deployment_fault():
    capability = CapabilityManifest(
        capability_id="sales.other", version="1.0.0", domain="sales", root_entity_type="deal",
        goal=Goal("g", "Goal"), reasoners=(ReasonerSpec("core.risk", "1.0.0"),),
        plays=(PlayDefinition(play_id="p", version="1", label="Play", steps=("step",)),),
        policies=())
    context = ContextSnapshot(org_id="org_1", graph_version=1, root_entity_id="deal_1",
                              root_entity_type="deal", evaluation_time=NOW,
                              selector_version="selector.v1")
    request_ = ReasoningRequest(org_id="org_1", capability=capability, context=context,
                                evaluation_time=NOW, trigger_kind="crm.deal_updated")

    with pytest.raises(ValueError, match="does not declare reasoner core.priority"):
        PriorityReasoner().evaluate(request_, {})


# ---------------------------------------------------------------------------------------------
# Plugins in isolation
# ---------------------------------------------------------------------------------------------


def test_declared_urgency_reads_the_named_source():
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.temporal": _completed("core.temporal", urgency_bp=7_700)})

    observations = DeclaredUrgencyPlugin().contribute(view)

    assert len(observations) == 1
    assert observations[0].kind == "priority.declared_urgency"
    assert observations[0].metrics["urgency_bp"] == 7_700


def test_declared_urgency_falls_back_to_neutral_when_the_source_reported_none():
    """A source that ran but published no urgency is "no opinion", not "no pressure"."""
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.temporal": _completed("core.temporal", drop_bp=3_000)})

    assert DeclaredUrgencyPlugin().contribute(view)[0].metrics["urgency_bp"] == NEUTRAL_URGENCY_BP


def test_declared_urgency_stays_silent_without_a_declared_source():
    assert DeclaredUrgencyPlugin().contribute(
        _view(_request(), {"core.temporal": _completed("core.temporal", urgency_bp=9_000)})) == ()


def test_declared_urgency_stays_silent_when_the_named_source_did_not_run():
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.risk": _completed("core.risk", urgency_bp=9_000)})

    assert DeclaredUrgencyPlugin().contribute(view) == ()


def test_declared_urgency_accepts_the_integer_forms_the_contract_allows():
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.temporal": _completed("core.temporal")})
    object.__setattr__(view.prior["core.temporal"], "metrics", {"urgency_bp": Decimal("6100")})

    assert DeclaredUrgencyPlugin().contribute(view)[0].metrics["urgency_bp"] == 6_100


def test_maximum_urgency_takes_the_loudest_prior_reading():
    view = _view(_request(), {"core.temporal": _completed("core.temporal", urgency_bp=2_000),
                              "core.risk": _completed("core.risk", urgency_bp=8_400),
                              "core.impact": _completed("core.impact", impact_bp=9_000)})

    observations = MaximumUrgencyPlugin().contribute(view)

    assert observations[0].metrics["urgency_bp"] == 8_400
    assert observations[0].metrics["prior_reading_count"] == 3


def test_maximum_urgency_is_neutral_only_when_nothing_ran():
    """No priors at all is ignorance (neutral); priors that ran and said nothing is a real zero."""
    assert MaximumUrgencyPlugin().contribute(
        _view(_request(), {}))[0].metrics["urgency_bp"] == NEUTRAL_URGENCY_BP
    assert MaximumUrgencyPlugin().contribute(
        _view(_request(), {"core.impact": _completed("core.impact", impact_bp=9_000)})
    )[0].metrics["urgency_bp"] == 0


def test_maximum_urgency_yields_to_the_declared_source():
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.temporal": _completed("core.temporal", urgency_bp=1_000),
                  "core.risk": _completed("core.risk", urgency_bp=9_900)})

    assert MaximumUrgencyPlugin().contribute(view) == ()


def test_the_two_urgency_plugins_are_mutually_exclusive():
    """Exactly one urgency reading must exist, or calculate would have to arbitrate."""
    for _, request_, prior in _scenarios():
        view = _view(request_, prior)
        firing = [plugin.plugin_id for plugin in (DeclaredUrgencyPlugin(), MaximumUrgencyPlugin())
                  if plugin.contribute(view)]

        assert len(firing) == 1, firing


def test_override_carries_the_declared_sources_priority():
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.temporal": _completed("core.temporal", urgency_bp=1_000,
                                              priority_bp=7_250)})

    observations = DeclaredOverridePlugin().contribute(view)

    assert observations[0].metrics["priority_override_bp"] == 7_250


def test_override_is_absent_when_the_source_did_not_rule():
    view = _view(_request(config=DEAL_COOLING_V1_CONFIG),
                 {"core.temporal": _completed("core.temporal", urgency_bp=1_000)})

    assert DeclaredOverridePlugin().contribute(view) == ()


def test_override_never_comes_from_the_derived_path():
    """An aggregate across units has no author, so there is nobody whose override it could be."""
    view = _view(_request(), {"core.temporal": _completed("core.temporal", priority_bp=7_250)})

    assert DeclaredOverridePlugin().contribute(view) == ()


def test_a_zero_override_is_published_and_an_absent_one_is_not():
    """Zero is an instruction to deprioritise; absence is silence. Collapsing them would let a
    source that never ruled quietly bury a candidate."""
    zeroed = PriorityReasoner().evaluate(
        _request(config=DEAL_COOLING_V1_CONFIG),
        {"core.temporal": _completed("core.temporal", urgency_bp=9_000, priority_bp=0)})
    silent = PriorityReasoner().evaluate(
        _request(config=DEAL_COOLING_V1_CONFIG),
        {"core.temporal": _completed("core.temporal", urgency_bp=9_000)})

    assert zeroed.metrics["priority_override_bp"] == 0
    assert "priority_override_bp" not in silent.metrics


# ---------------------------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------------------------


def test_the_result_analyses_and_does_not_decide():
    result = PriorityReasoner().evaluate(
        _request(config=DEAL_COOLING_V1_CONFIG),
        {"core.temporal": _completed("core.temporal", urgency_bp=9_100, priority_bp=8_000)})

    assert result.status is ResultStatus.COMPLETED
    assert result.matched is None, "a unit that matched would be ranking"
    assert result.adjustments == ()
    assert result.checks == ()
    assert result.reason_codes == (PRIORITY_READY_REASON,)
    assert result.metrics == {"urgency_bp": 9_100, "priority_override_bp": 8_000}


def test_the_single_finding_mirrors_the_published_metrics():
    result = PriorityReasoner().evaluate(
        _request(config=DEAL_COOLING_V1_CONFIG),
        {"core.temporal": _completed("core.temporal", urgency_bp=9_100, priority_bp=8_000)})

    finding, = result.findings
    assert finding.finding_id == "priority.inputs"
    assert finding.kind == "priority"
    assert finding.matched is None
    assert dict(finding.metrics) == dict(result.metrics)
    assert finding.reason_codes == (PRIORITY_READY_REASON,)


def test_it_claims_no_fact_evidence():
    """The number was measured by the source reasoner; attaching a fact's evidence id here would
    be a false chain of custody."""
    result = PriorityReasoner().evaluate(
        _request(config=DEAL_COOLING_V1_CONFIG,
                 required_fields=("deal.status",),
                 facts={"deal.status": "open"},
                 evidence=(EvidenceRef("ev_1", "deal.status", "open"),)),
        {"core.temporal": _completed("core.temporal", urgency_bp=4_400)})

    assert result.evidence_ids == ()


def test_declared_required_fields_never_produce_insufficient_context():
    """This unit reads no facts, so a missing fact cannot undermine its answer — and refusing
    would strip the Decision Maker of the authority it resolves urgency against."""
    result = PriorityReasoner().evaluate(
        _request(required_fields=("deal.status", "deal.value")),
        {"core.temporal": _completed("core.temporal", urgency_bp=6_100)})

    assert result.status is ResultStatus.COMPLETED
    assert result.missing_fields == ()
    assert result.metrics["urgency_bp"] == 6_100


# ---------------------------------------------------------------------------------------------
# Determinism and ordering
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("label, request_, prior", _scenarios(),
                         ids=[case[0] for case in _scenarios()])
def test_the_same_situation_evaluates_identically_twice(label, request_, prior):
    unit = PriorityReasoner()

    assert unit.evaluate(request_, prior).semantic_hash == \
        unit.evaluate(request_, prior).semantic_hash


def test_config_key_order_cannot_move_the_result():
    """Config round-trips through JSON in the audit store and comes back re-ordered. A unit that
    iterated it unsorted would produce a different hash on replay than it did in production."""
    forwards = _request(config={"source_reasoner": "core.temporal", "unused_a": 1, "unused_z": 2})
    backwards = _request(config={"unused_z": 2, "unused_a": 1, "source_reasoner": "core.temporal"})
    prior = {"core.temporal": _completed("core.temporal", urgency_bp=7_700, priority_bp=6_000)}

    assert PriorityReasoner().evaluate(forwards, prior).semantic_hash == \
        PriorityReasoner().evaluate(backwards, prior).semantic_hash


def test_prior_result_order_cannot_move_the_derived_maximum():
    request_ = _request()
    forwards = {"core.temporal": _completed("core.temporal", urgency_bp=2_000),
                "core.risk": _completed("core.risk", urgency_bp=8_400)}
    backwards = {"core.risk": _completed("core.risk", urgency_bp=8_400),
                 "core.temporal": _completed("core.temporal", urgency_bp=2_000)}

    assert PriorityReasoner().evaluate(request_, forwards).semantic_hash == \
        PriorityReasoner().evaluate(request_, backwards).semantic_hash


def test_plugin_ids_are_unique_and_order_the_analysis_deterministically():
    unit = PriorityReasoner()
    ids = [plugin.plugin_id for plugin in unit.plugins]

    assert len(ids) == len(set(ids))
    # Alphabetical plugin order is what makes the declared urgency validate before the override.
    assert sorted(ids) == ["declared_urgency", "maximum_urgency", "override_priority"]
