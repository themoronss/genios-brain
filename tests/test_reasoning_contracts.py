from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateDisposition,
    CapabilityManifest,
    ContextSnapshot,
    DecisionCandidate,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    FailurePolicy,
    Finding,
    Goal,
    IntelligenceObject,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningDecision,
    ReasoningRequest,
    ReasoningTrace,
    ResultStatus,
    StepTrace,
)
from genios_engine.reason.canonical import (
    CanonicalizationError,
    canonical_dumps,
    canonicalize,
    semantic_hash,
    stable_id,
)
from genios_engine.reason.protocols import MissingContextError, Reasoner
from genios_engine.reason.registry import (
    ReasonerDependencyError,
    ReasonerRegistry,
    ReasonerRegistryError,
    UnknownReasoner,
)


UTC_NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
IST = timezone(timedelta(hours=5, minutes=30))


def _spec(reasoner_id: str = "risk", *, dependencies=(), version: str = "1") -> ReasonerSpec:
    return ReasonerSpec(reasoner_id=reasoner_id, version=version,
                        dependencies=tuple(dependencies))


def _play(play_id: str = "restore_momentum", *, impact_bp: int = 7_000) -> PlayDefinition:
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=("Prepare a grounded draft", "Ask for a specific next step"),
        impact_bp=impact_bp,
        success_probability_bp=5_500,
        effort_bp=2_000,
        risk_bp=1_000,
        success_events=("prospect_reply",),
        window_days=14,
        metadata={"external_recipient_required": False},
    )


def _capability(*, reasoners=None, plays=None, ranking_weights=None,
                intelligence_objects=()) -> CapabilityManifest:
    kwargs = {}
    if ranking_weights is not None:
        kwargs["ranking_weights"] = ranking_weights
    return CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(reasoners or (
            _spec("temporal"),
            _spec("risk", dependencies=("temporal",)),
            ReasonerSpec("core.constraint", "1", dependencies=("risk",)),
        )),
        plays=tuple(plays or (_play(),)),
        required_fields=("deal.status", "thread.last_inbound"),
        intelligence_objects=tuple(intelligence_objects),
        policies=("read_only", "no_unverified_recipient"),
        **kwargs,
    )


def _context(*, org_id: str = "org_1", root_entity_type: str = "deal",
             evaluation_time: datetime = UTC_NOW, graph_version: int = 7,
             edge_count: int = 2, evidence=()) -> ContextSnapshot:
    return ContextSnapshot(
        org_id=org_id,
        graph_version=graph_version,
        root_entity_id="deal_1",
        root_entity_type=root_entity_type,
        evaluation_time=evaluation_time,
        selector_version="selector.v1",
        facts={"deal.status": "open", "deal.value": 500_000},
        neighbor_facts={"contact": {"verified": True}},
        neighbor_observations=("pricing_discussed", "buying_intent"),
        edge_count=edge_count,
        evidence=tuple(evidence),
        missing_fields=("deal.next_step",),
    )


def test_canonical_mapping_and_set_order_do_not_change_bytes_or_hash():
    left = {"z": {"beta", "alpha"}, "a": {"inner": 1}}
    right = {"a": {"inner": 1}, "z": {"alpha", "beta"}}

    assert canonical_dumps(left) == canonical_dumps(right)
    assert semantic_hash(left) == semantic_hash(right)
    assert canonicalize(left)["z"] == ["alpha", "beta"]


def test_canonical_datetime_normalizes_equal_instants_to_utc():
    utc_value = datetime(2026, 8, 6, 6, 30, tzinfo=timezone.utc)
    ist_value = datetime(2026, 8, 6, 12, 0, tzinfo=IST)

    assert canonical_dumps(utc_value) == canonical_dumps(ist_value)
    assert canonicalize(ist_value) == {"$datetime": "2026-08-06T06:30:00.000000Z"}
    with pytest.raises(CanonicalizationError, match="timezone-aware"):
        canonicalize(datetime(2026, 8, 6, 6, 30))


def test_semantic_hash_and_stable_id_retain_the_full_sha256_digest():
    digest = semantic_hash({"decision": "restore_momentum"})

    assert len(digest) == 64
    int(digest, 16)
    assert stable_id("decision", {"decision": "restore_momentum"}) == f"decision_{digest}"


@pytest.mark.parametrize("value", [0.0, 1.5, float("nan"), float("inf"), -float("inf")])
def test_canonical_semantics_reject_all_floats(value):
    with pytest.raises(CanonicalizationError, match="floats are forbidden"):
        canonicalize({"value": value})


@pytest.mark.parametrize("key", ("$decimal", "$datetime", "$date", "$uuid"))
def test_canonical_semantics_reject_literal_reserved_scalar_tags(key):
    with pytest.raises(CanonicalizationError, match="reserved"):
        canonicalize({key: "literal_business_value"})


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_canonical_semantics_reject_non_finite_decimals(value):
    with pytest.raises(CanonicalizationError, match="must be finite"):
        canonicalize(value)


def test_context_configuration_is_frozen_deeply_and_copied_from_the_caller():
    source = {"deal": {"labels": ["enterprise"], "status": "open"}}
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="deal_1",
        root_entity_type="deal", evaluation_time=UTC_NOW, selector_version="selector.v1",
        facts=source,
    )
    source["deal"]["labels"].append("mutated-after-construction")

    assert context.facts["deal"]["labels"] == ("enterprise",)
    with pytest.raises(TypeError):
        context.facts["new"] = "blocked"
    with pytest.raises(TypeError):
        context.facts["deal"]["status"] = "lost"
    with pytest.raises(AttributeError):
        context.facts["deal"]["labels"].append("blocked")
    with pytest.raises(FrozenInstanceError):
        context.edge_count = 10


def test_evidence_value_is_deeply_immutable():
    source = {"quote": {"tokens": ["deal", "open"]}}
    evidence = EvidenceRef("ev_1", "deal.status", source)
    source["quote"]["tokens"].append("caller-mutation")

    assert evidence.value["quote"]["tokens"] == ("deal", "open")
    with pytest.raises(TypeError):
        evidence.value["quote"]["new"] = "blocked"


def test_reasoner_result_sequence_inputs_are_frozen_and_copied():
    source = [Finding("finding_1", "risk")]
    result = ReasonerResult("risk", "1", ResultStatus.COMPLETED, findings=source)
    source.clear()

    assert isinstance(result.findings, tuple)
    assert len(result.findings) == 1


@pytest.mark.parametrize("matched", [0, 1, "false", Decimal("1")])
def test_reasoner_and_finding_matches_accept_only_real_booleans(matched):
    with pytest.raises(TypeError, match="boolean"):
        ReasonerResult("risk", "1", ResultStatus.COMPLETED, matched=matched)
    with pytest.raises(TypeError, match="boolean"):
        Finding("finding_1", "risk", matched=matched)


def test_context_rejects_duplicate_evidence_ids():
    evidence = EvidenceRef("ev_1", "deal.status", "open")
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        _context(evidence=(evidence, evidence))


def test_context_rejects_evidence_not_bound_to_the_frozen_fact_value():
    with pytest.raises(ValueError, match="does not match"):
        _context(evidence=(EvidenceRef("ev_1", "deal.status", "won"),))


def test_context_rejects_evidence_from_an_undeclared_context_partition():
    with pytest.raises(ValueError, match="absent from its context scope"):
        _context(evidence=(EvidenceRef(
            "ev_1", "deal.status", "open", context_scope="neighbor"),))


@pytest.mark.parametrize(
    "reasoners,plays,objects,error",
    [
        ((_spec("risk"), _spec("risk")), (_play(),), (), "duplicate reasoner"),
        ((_spec(),), (_play("restore"), _play("restore")), (), "duplicate play"),
        ((_spec(),), (_play(),), (
            IntelligenceObject("cadence", "1", "sales.deal_cooling", "Measure cadence"),
            IntelligenceObject("cadence", "2", "sales.deal_cooling", "Measure cadence"),
        ), "duplicate intelligence object"),
    ],
)
def test_capability_rejects_duplicate_semantic_ids(reasoners, plays, objects, error):
    with pytest.raises(ValueError, match=error):
        _capability(reasoners=reasoners, plays=plays, intelligence_objects=objects)


@pytest.mark.parametrize("confidence_bp", [-1, 10_001])
def test_evidence_rejects_out_of_bounds_confidence(confidence_bp):
    with pytest.raises(ValueError, match="between 0 and 10000"):
        EvidenceRef("ev_1", "deal.status", "open", confidence_bp=confidence_bp)


@pytest.mark.parametrize("authority_rank", [0, 5])
def test_evidence_rejects_out_of_bounds_authority(authority_rank):
    with pytest.raises(ValueError, match="between 1 and 4"):
        EvidenceRef("ev_1", "deal.status", "open", authority_rank=authority_rank)


@pytest.mark.parametrize("latency_ms", [0, 60_001])
def test_reasoner_spec_rejects_out_of_bounds_latency(latency_ms):
    with pytest.raises(ValueError, match="between 1 and 60000"):
        ReasonerSpec("risk", "1", latency_budget_ms=latency_ms)


@pytest.mark.parametrize("window_days", [0, 366])
def test_play_rejects_out_of_bounds_window(window_days):
    with pytest.raises(ValueError, match="between 1 and 365"):
        PlayDefinition("restore", "1", "Restore", ("Draft",), window_days=window_days)


@pytest.mark.parametrize("impact_bp", [-1, 10_001])
def test_play_rejects_out_of_bounds_basis_points(impact_bp):
    with pytest.raises(ValueError, match="between 0 and 10000"):
        _play(impact_bp=impact_bp)


def test_capability_rejects_invalid_ranking_weights_and_expiry():
    with pytest.raises(ValueError, match="sum to 100"):
        _capability(ranking_weights={
            "impact": 50, "success": 30, "urgency": 20, "effort": 10, "risk": 5})
    with pytest.raises(ValueError, match="between 1 and 8760"):
        CapabilityManifest(
            capability_id="sales.cooling", version="1", domain="sales",
            root_entity_type="deal", goal=Goal("g", "Restore momentum"),
            reasoners=(_spec(),), plays=(_play(),), policies=(), expiry_hours=0,
        )


def test_gating_reasoner_cannot_be_optional():
    with pytest.raises(ValueError, match="fail-closed"):
        ReasonerSpec("unsafe_gate", "1", gating=True,
                     failure_policy=FailurePolicy.OPTIONAL)


def test_capability_rejects_unknown_policy_instead_of_silently_ignoring_it():
    with pytest.raises(ValueError, match="unsupported capability policies"):
        replace(_capability(), policies=("read_only", "evidence_requried"))


def test_capability_cannot_omit_the_required_constraint_authority():
    with pytest.raises(ValueError, match="required core.constraint"):
        CapabilityManifest(
            capability_id="sales.unsafe", version="1", domain="sales",
            root_entity_type="deal", goal=Goal("g", "Stay safe"),
            reasoners=(_spec("core.relationship"),), plays=(_play(),),
            policies=("read_only",),
        )


def test_recipient_policy_requires_an_explicit_typed_play_effect():
    unsafe_play = replace(_play(), metadata={})
    with pytest.raises(ValueError, match="external_recipient_required"):
        _capability(plays=(unsafe_play,))


@pytest.mark.parametrize("field,value", [
    ("graph_version", -1), ("edge_count", -1),
    ("graph_version", True), ("edge_count", True),
    ("graph_version", 1.5), ("edge_count", 1.5),
])
def test_context_rejects_non_integer_or_negative_counters(field, value):
    kwargs = {field: value}
    with pytest.raises((TypeError, ValueError)):
        _context(**kwargs)


def test_capability_snapshot_is_content_addressed_and_mapping_order_invariant():
    first = _capability(ranking_weights={
        "impact": 35, "success": 30, "urgency": 20, "effort": 10, "risk": 5})
    second = _capability(ranking_weights={
        "risk": 5, "effort": 10, "urgency": 20, "success": 30, "impact": 35})

    assert first.semantic_hash == second.semantic_hash
    assert first.capability_snapshot_id == second.capability_snapshot_id
    assert first.capability_snapshot_id == f"cap_{first.semantic_hash}"
    assert len(first.semantic_hash) == 64
    assert _capability(plays=(_play(impact_bp=7_001),)).capability_snapshot_id != \
        first.capability_snapshot_id


def test_context_snapshot_normalizes_order_and_timezone_before_hashing():
    utc_context = _context(
        evaluation_time=UTC_NOW,
        evidence=(EvidenceRef("ev_b", "deal.value", 500_000),
                  EvidenceRef("ev_a", "deal.status", "open")),
    )
    ist_context = ContextSnapshot(
        org_id="org_1", graph_version=7, root_entity_id="deal_1",
        root_entity_type="deal", evaluation_time=UTC_NOW.astimezone(IST),
        selector_version="selector.v1",
        facts={"deal.value": 500_000, "deal.status": "open"},
        neighbor_facts={"contact": {"verified": True}},
        neighbor_observations=("buying_intent", "pricing_discussed"), edge_count=2,
        evidence=(EvidenceRef("ev_a", "deal.status", "open"),
                  EvidenceRef("ev_b", "deal.value", 500_000)),
        missing_fields=("deal.next_step",),
    )

    assert utc_context == ist_context
    assert utc_context.semantic_hash == ist_context.semantic_hash
    assert utc_context.context_snapshot_id == ist_context.context_snapshot_id


def test_reasoning_request_enforces_org_time_and_root_invariants():
    capability = _capability()
    context = _context()

    request = ReasoningRequest(
        org_id="org_1", capability=capability, context=context,
        evaluation_time=UTC_NOW.astimezone(IST), trigger_kind="email.received",
        mode=ExecutionMode.SHADOW,
    )
    duplicate = ReasoningRequest(
        org_id="org_1", capability=capability, context=context,
        evaluation_time=UTC_NOW, trigger_kind="email.received", mode="shadow",
    )
    assert request.request_id == duplicate.request_id
    assert request.semantic_hash == duplicate.semantic_hash
    assert request.policy_snapshot_id.startswith("policy_")
    assert len(request.policy_snapshot_id) == len("policy_") + 64

    with pytest.raises(ValueError, match="policy_snapshot_id"):
        ReasoningRequest(
            org_id="org_1", capability=capability, context=context,
            evaluation_time=UTC_NOW, trigger_kind="email.received",
            policy_snapshot_id="policy_opaque",
        )
    with pytest.raises(ValueError, match="request_id"):
        ReasoningRequest(
            org_id="org_1", capability=capability, context=context,
            evaluation_time=UTC_NOW, trigger_kind="email.received",
            request_id="req_not_content_addressed",
        )

    with pytest.raises(ValueError, match="org_id differ"):
        ReasoningRequest("org_2", capability, context, UTC_NOW, "email.received")
    with pytest.raises(ValueError, match="evaluation_time differ"):
        ReasoningRequest("org_1", capability, context, UTC_NOW + timedelta(seconds=1),
                         "email.received")
    with pytest.raises(ValueError, match="root type"):
        ReasoningRequest("org_1", capability, _context(root_entity_type="person"), UTC_NOW,
                         "email.received")


def _candidate(play_id: str = "restore") -> DecisionCandidate:
    return DecisionCandidate(
        play_id=play_id, play_version="1", disposition=CandidateDisposition.ELIGIBLE,
        utility_bp=7_000, confidence_bp=8_000,
        score_components={"impact": 7_000, "risk": 1_000}, rank_position=1,
    )


def test_reasoning_decision_rejects_duplicate_candidate_ids():
    candidate = _candidate()
    with pytest.raises(ValueError, match="duplicate decision candidate"):
        ReasoningDecision(
            DecisionOutcome.DECISION, "sales.cooling", "1", "ctx_hash",
            (candidate, candidate), candidate.candidate_id, 8_000, (), "Deal may cool",
            UTC_NOW + timedelta(days=7),
        )


class _StubReasoner:
    def __init__(self, spec: ReasonerSpec):
        self._spec = spec

    @property
    def spec(self) -> ReasonerSpec:
        return self._spec

    def evaluate(self, request, prior_results):
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED)


def test_reasoner_protocol_is_runtime_checkable_and_missing_context_is_canonical():
    reasoner = _StubReasoner(_spec())
    assert isinstance(reasoner, Reasoner)

    error = MissingContextError("deal.value", "deal.status", "deal.value")
    assert error.fields == ("deal.status", "deal.value")
    assert str(error) == "missing required context: deal.status, deal.value"


def test_registry_rejects_unknown_duplicate_and_non_protocol_reasoners():
    spec = _spec("risk")
    first = _StubReasoner(spec)
    registry = ReasonerRegistry((first,))
    registry.register(first)  # the same instance is idempotent

    assert registry.get(spec) is first
    with pytest.raises(UnknownReasoner, match="unknown reasoner"):
        registry.get(_spec("missing"))
    with pytest.raises(ReasonerRegistryError, match="already registered"):
        registry.register(_StubReasoner(spec))
    with pytest.raises(TypeError, match="protocol"):
        registry.register(object())


def test_registry_rejects_duplicate_ids_missing_dependencies_self_edges_and_cycles():
    with pytest.raises(ReasonerDependencyError, match="duplicate reasoner id"):
        ReasonerRegistry.topological_order((_spec("risk", version="1"),
                                             _spec("risk", version="2")))
    with pytest.raises(ReasonerDependencyError, match="missing reasoner"):
        ReasonerRegistry.topological_order((_spec("risk", dependencies=("temporal",)),))
    with pytest.raises(ReasonerDependencyError, match="self dependency"):
        ReasonerRegistry.topological_order((_spec("risk", dependencies=("risk",)),))
    with pytest.raises(ReasonerDependencyError, match="dependency cycle"):
        ReasonerRegistry.topological_order((
            _spec("alpha", dependencies=("beta",)),
            _spec("beta", dependencies=("alpha",)),
        ))


def test_registry_dag_uses_a_lexical_tie_break_for_every_ready_reasoner():
    specs = (
        _spec("gamma", dependencies=("alpha",)),
        _spec("delta", dependencies=("beta",)),
        _spec("beta"),
        _spec("alpha"),
    )
    plan = ReasonerRegistry.topological_order(specs)
    assert tuple(spec.reasoner_id for spec in plan) == ("alpha", "beta", "delta", "gamma")

    reasoners = tuple(_StubReasoner(spec) for spec in specs)
    ordered = ReasonerRegistry(reasoners).ordered(specs)
    assert tuple(reasoner.spec.reasoner_id for reasoner in ordered) == \
        ("alpha", "beta", "delta", "gamma")


def test_trace_semantic_hash_excludes_run_id_but_remains_content_sensitive():
    step = StepTrace(1, "risk", "1", ResultStatus.COMPLETED, "a" * 64, "b" * 64)
    first = ReasoningTrace(
        "run_1", "c" * 64, "cap_hash", "ctx_hash", "orch.v1",
        ExecutionMode.REPLAY, ("risk",), (step,), "d" * 64,
    )
    second = ReasoningTrace(
        "run_2", "c" * 64, "cap_hash", "ctx_hash", "orch.v1",
        ExecutionMode.REPLAY, ("risk",), (step,), "d" * 64,
    )
    changed = ReasoningTrace(
        "run_2", "c" * 64, "cap_hash", "ctx_hash", "orch.v2",
        ExecutionMode.REPLAY, ("risk",), (step,), "d" * 64,
    )

    assert first.semantic_hash == second.semantic_hash
    assert first.semantic_hash != changed.semantic_hash
