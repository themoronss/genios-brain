"""The selector seam and the registration check — wave Z1's two structural changes.

Two defects, one shape. The Unit Selector dropped a dependent the moment ANY of its declared
sources was dropped, while dropping a unit for want of a FACT only when every declared field was
gone; and nothing anywhere checked that a source a unit reads is a unit that exists. Both let a
roster look scheduled and reason on less than it declared, and both are invisible at run time
because a source that never ran and a source that is not real read identically.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.plan import CONTEXT_AWARE_SELECTION_KEY, ReasoningPlanner
from genios_engine.reason.protocols import OrchestrationError
from genios_engine.reason.registry import (
    ReasonerRegistry,
    UnknownReasoner,
    UnregisteredSourceUnit,
    named_source_units,
)

from datetime import datetime, timezone

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _capability(specs, metadata=None) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="test.selection", version="1.0.0", domain="test",
        root_entity_type="deal",
        goal=Goal("test.goal", "Decide something", constraints=("none",)),
        reasoners=tuple(specs),
        plays=(PlayDefinition("play_a", "1.0.0", "A play", steps=("do the thing",)),),
        policies=(),
        metadata=metadata or {},
    )


def _request(capability, facts) -> ReasoningRequest:
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="selector.v1", facts=facts)
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


class _Stub:
    def __init__(self, spec: ReasonerSpec, sources: tuple[str, ...] = ()) -> None:
        self._spec = ReasonerSpec(spec.reasoner_id, spec.version)
        if sources:
            self.source_units = sources

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    def evaluate(self, request, prior_results):      # pragma: no cover - never run here
        raise AssertionError("planning must not execute a unit")


# ── the starvation rule ──────────────────────────────────────────────────────────────────────

_FOUR_SOURCE_DEPENDENT = (
    ReasonerSpec("core.anchor", "1"),
    ReasonerSpec("core.money", "1", required_fields=("deal.value",),
                 failure_policy=FailurePolicy.OPTIONAL),
    ReasonerSpec("core.clock", "1", required_fields=("deal.last_inbound",),
                 failure_policy=FailurePolicy.OPTIONAL),
    ReasonerSpec("core.tension", "1", dependencies=("core.anchor", "core.money", "core.clock"),
                 failure_policy=FailurePolicy.OPTIONAL),
)


def test_a_unit_that_lost_one_of_three_sources_still_runs_on_the_two_it_kept():
    """The cascade rule now matches the field rule: only total starvation drops a unit.

    Under the any-rule this plan kept three units. `core.tension` reads risk, opportunity, impact
    and cost in the real roster, and a single moneyless situation removed it — and then everything
    that depended on it.
    """
    capability = _capability(_FOUR_SOURCE_DEPENDENT,
                             metadata={CONTEXT_AWARE_SELECTION_KEY: True})
    plan = ReasoningPlanner().plan(
        capability, _request(capability, {"deal.last_inbound": "2026-08-01T00:00:00+00:00"}))

    assert "core.tension" in plan.reasoner_plan
    assert [step.reasoner_id for step in plan.skipped] == ["core.money"]


def test_a_unit_whose_every_source_went_is_dropped_and_names_all_of_them():
    """Nothing left to read is still a drop, and the receipt names every source that went."""
    specs = (
        ReasonerSpec("core.money", "1", required_fields=("deal.value",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core.clock", "1", required_fields=("deal.last_inbound",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core.tension", "1", dependencies=("core.money", "core.clock"),
                     failure_policy=FailurePolicy.OPTIONAL),
    )
    capability = _capability(specs, metadata={CONTEXT_AWARE_SELECTION_KEY: True})

    plan = ReasoningPlanner().plan(capability, _request(capability, {"deal.status": "open"}))

    assert plan.reasoner_plan == ()
    dropped = {step.reasoner_id: step for step in plan.skipped}
    assert dropped["core.tension"].reason_code == "dependency_not_scheduled"
    assert dropped["core.tension"].missing_fields == ("core.clock", "core.money")


def test_a_required_dependent_survives_the_loss_of_every_source():
    """Required is required: a starved required unit must fail the run loudly, not vanish."""
    specs = (
        ReasonerSpec("core.money", "1", required_fields=("deal.value",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core.risk", "1", dependencies=("core.money",)),
    )
    capability = _capability(specs, metadata={CONTEXT_AWARE_SELECTION_KEY: True})

    plan = ReasoningPlanner().plan(capability, _request(capability, {"deal.status": "open"}))

    assert plan.reasoner_plan == ("core.risk",)


# ── the registration check: a source must be a real, declared, visible unit ───────────────────

def test_a_manifest_naming_an_unregistered_source_unit_is_refused_with_the_unit_named():
    """`core.effort` — the ghost. Declared, resolvable, and not a unit anybody ever wrote."""
    specs = (ReasonerSpec("core.tradeoff", "1", dependencies=("core.effort",),
                          config={"cost_source": "core.effort"}),
             ReasonerSpec("core.effort", "1"))
    capability = _capability(specs)
    registry = ReasonerRegistry((_Stub(specs[0]),))
    plan = ReasoningPlanner().plan(capability)

    with pytest.raises(UnregisteredSourceUnit, match="core.effort"):
        ReasoningPlanner().resolve(plan, registry, capability)


def test_a_declared_unit_the_registry_cannot_supply_is_refused_even_when_selection_dropped_it():
    """Selection must not be able to hide a broken deployment until a tenant's facts reveal it."""
    specs = (ReasonerSpec("core.anchor", "1"),
             ReasonerSpec("core.ghost", "1", required_fields=("deal.value",),
                          failure_policy=FailurePolicy.OPTIONAL))
    capability = _capability(specs, metadata={CONTEXT_AWARE_SELECTION_KEY: True})
    registry = ReasonerRegistry((_Stub(specs[0]),))
    request = _request(capability, {"deal.status": "open"})
    plan = ReasoningPlanner().plan(capability, request)

    assert "core.ghost" not in plan.reasoner_plan          # dropped, and still checked
    with pytest.raises(UnknownReasoner, match="core.ghost"):
        ReasoningPlanner().resolve(plan, registry, capability)


def test_a_source_the_manifest_never_made_visible_is_refused_at_plan_time():
    """The orchestrator hands a unit only its declared dependencies, so a source that is not one
    configures a read that can never happen."""
    specs = (ReasonerSpec("core.risk", "1"),
             ReasonerSpec("core.tradeoff", "1", config={"risk_source": "core.risk"}))
    capability = _capability(specs)

    with pytest.raises(UnregisteredSourceUnit, match="without declaring it a dependency"):
        ReasoningPlanner().plan(capability)


def test_a_source_naming_a_unit_the_manifest_does_not_declare_is_refused_at_plan_time():
    specs = (ReasonerSpec("core.tradeoff", "1", config={"cost_source": "core.cost"}),)
    capability = _capability(specs)

    with pytest.raises(UnregisteredSourceUnit, match="a unit it never declares"):
        ReasoningPlanner().plan(capability)


def test_a_registry_cannot_be_built_holding_a_unit_that_reads_a_ghost():
    """The class of bug, cured where it is cheapest: at registration."""
    with pytest.raises(UnregisteredSourceUnit, match="core.effort"):
        ReasonerRegistry((_Stub(ReasonerSpec("core.tradeoff", "1"), sources=("core.effort",)),))


def test_a_registry_holding_both_the_reader_and_its_source_is_accepted():
    registry = ReasonerRegistry((
        _Stub(ReasonerSpec("core.tradeoff", "1"), sources=("core.cost",)),
        _Stub(ReasonerSpec("core.cost", "1")),
    ))
    assert registry.unit_ids == {"core.tradeoff", "core.cost"}


def test_the_shipped_registry_holds_no_ghost_sources():
    """The runtime roster itself, asked the question `core.effort` survived for want of asking."""
    from genios_engine.reason.reasoners import default_registry

    default_registry().validate_sources()


def test_a_config_key_that_merely_ends_in_source_is_not_mistaken_for_a_unit_reference():
    """`data_source: crm` is configuration. Only a value shaped like a unit id is a reference."""
    spec = ReasonerSpec("core.thing", "1", config={"data_source": "crm", "risk_source": "core.x"})

    assert named_source_units(spec) == (("risk_source", "core.x"),)


def test_the_planner_still_refuses_a_plan_that_cannot_meet_its_declared_ceiling():
    """PRESERVE HARD: the latency refusal is what makes a twenty-unit roster safe to switch on."""
    specs = (ReasonerSpec("core.a", "1", latency_budget_ms=900),
             ReasonerSpec("core.b", "1", latency_budget_ms=900))
    capability = _capability(specs, metadata={"latency_ceiling_ms": 1_500})

    with pytest.raises(OrchestrationError, match="1500ms ceiling"):
        ReasoningPlanner().plan(capability)


def test_selection_stays_off_for_a_capability_that_did_not_opt_in():
    """Every capability that predates the roster keeps its full declared list."""
    capability = _capability(_FOUR_SOURCE_DEPENDENT)

    plan = ReasoningPlanner().plan(capability, _request(capability, {}))

    assert len(plan.reasoner_plan) == 4 and plan.skipped == ()


def test_a_skipped_step_is_inside_the_plan_hash():
    """PRESERVE HARD: the receipt is part of the plan's content address, not a note beside it."""
    capability = _capability(_FOUR_SOURCE_DEPENDENT,
                             metadata={CONTEXT_AWARE_SELECTION_KEY: True})
    thin = ReasoningPlanner().plan(capability, _request(capability, {"deal.value": 10}))
    fed = ReasoningPlanner().plan(
        capability, _request(capability, {"deal.value": 10,
                                          "deal.last_inbound": "2026-08-01T00:00:00+00:00"}))

    assert thin.plan_hash != fed.plan_hash
    assert ReasoningPlanner().plan(
        capability, _request(capability, {"deal.value": 10})).plan_hash == thin.plan_hash
    assert ResultStatus.SKIPPED       # the contract this file's vocabulary depends on
