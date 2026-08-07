"""Migration proof for the Constraint Unit (``core.constraint``).

The unit was rewritten onto the ReasoningUnit framework.  Its output is re-verified outside Layer 4
— `reason/store.py` refuses to persist a decision whose selected play lacks exactly one passing
check per declared policy, and `reason/authority.py` re-proves the same rows in SQL on every
downstream read — so "the behaviour is the same" is not a claim that can be made by inspection.

**Equivalence approach: a frozen reference copy.**  `_LegacyConstraintReasoner` below is a verbatim
transcription of the pre-migration `genios_engine/reason/reasoners/constraint.py`, taken before it
was replaced.  Importing the old class was not an option — the migration rewrites that module in
place, and `reasoners/__init__.py` imports `ConstraintReasoner` by name, so there is no old module
left to import from.  A frozen copy also outlives the migration: it keeps proving parity against the
*shipped* semantics rather than against whatever the module happens to say next month, and it will
fail loudly if someone edits the new unit's arithmetic without intending to.

The differential test asserts `semantic_hash` equality, not field-by-field equality, because the
hash is what replay, the legacy-parity ratchet, and the persisted decision id all key on.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateCheck,
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
from genios_engine.packs.capabilities.deal_cooling import DEAL_COOLING_V1
from genios_engine.reason.reasoners import ConstraintReasoner as RegisteredConstraint
from genios_engine.reason.reasoners.common import active_spec, decimal, fact_value
from genios_engine.reason.reasoners.constraint import (
    CONSTRAINT_UNIT_ID,
    CONSTRAINT_UNIT_VERSION,
    ConstraintReasoner,
    ConstraintUnit,
    PermissionVerificationPlugin,
    PolicyEnforcementPlugin,
    PreconditionPlugin,
)
from genios_engine.reason.unit import Observation, UnitCategory, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


# ==================================================================================================
# Frozen reference: the pre-migration implementation, transcribed verbatim.
# ==================================================================================================


def _legacy_compare(actual, operator: str, expected) -> bool:
    if operator in {"=", "==", "eq"}:
        return actual == expected
    if operator in {"!=", "ne"}:
        return actual != expected
    if operator == "in":
        return actual in expected if isinstance(expected, (tuple, list, set, frozenset)) else False
    if operator in {">", ">=", "<", "<="}:
        try:
            left, right = decimal(actual, "precondition actual"), decimal(expected, "precondition expected")
        except ValueError:
            return False
        return {">": left > right, ">=": left >= right,
                "<": left < right, "<=": left <= right}[operator]
    raise ValueError(f"unsupported precondition operator: {operator}")


class _LegacyConstraintReasoner:
    """Verbatim copy of the shipped pre-migration unit. Do not 'improve'."""

    _descriptor = ReasonerSpec(reasoner_id="core.constraint", version="1.0.0")

    @property
    def spec(self) -> ReasonerSpec:
        return self._descriptor

    def evaluate(self, request: ReasoningRequest, prior_results: Mapping[str, ReasonerResult]
                 ) -> ReasonerResult:
        spec = active_spec(request, self.spec.reasoner_id)
        checks = []
        policies = set(request.capability.policies)
        context_evidence_ids = {item.evidence_id for item in request.context.evidence}
        used_evidence_ids = {
            evidence_id
            for result in prior_results.values()
            for evidence_id in (
                result.evidence_ids
                + tuple(evidence_id for finding in result.findings
                        for evidence_id in finding.evidence_ids)
                + tuple(evidence_id for adjustment in result.adjustments
                        for evidence_id in adjustment.evidence_ids)
            )
            if evidence_id in context_evidence_ids
        }
        for play in request.capability.plays:
            if "read_only" in policies:
                checks.append(CandidateCheck(
                    play.play_id, "policy",
                    CheckOutcome.PASS if play.read_only else CheckOutcome.ELIMINATE,
                    "read_only_policy_pass" if play.read_only else "read_only_policy",
                    self.spec.reasoner_id, self.spec.version,
                    detail={"required": True, "play_read_only": play.read_only}))

            if "human_approval_required" in policies:
                boundary = play.metadata.get("execution_boundary")
                approval_declared = (
                    boundary == "human_approval_required"
                    or "human_approval" in play.tags
                )
                checks.append(CandidateCheck(
                    play.play_id, "permission",
                    CheckOutcome.PASS if approval_declared else CheckOutcome.ELIMINATE,
                    ("human_approval_boundary_pass" if approval_declared
                     else "human_approval_boundary_missing"),
                    self.spec.reasoner_id, self.spec.version,
                    detail={"execution_boundary": boundary,
                            "human_approval_tag": "human_approval" in play.tags}))

            if "evidence_required" in policies:
                evidence_present = bool(used_evidence_ids)
                checks.append(CandidateCheck(
                    play.play_id, "policy",
                    CheckOutcome.PASS if evidence_present else CheckOutcome.ELIMINATE,
                    "evidence_policy_pass" if evidence_present else "evidence_required",
                    self.spec.reasoner_id, self.spec.version,
                    detail={"context_evidence_count": len(request.context.evidence),
                            "used_evidence_count": len(used_evidence_ids)}))

            if "no_unverified_recipient" in policies:
                recipient_required = play.metadata["external_recipient_required"]
                verification_guards = tuple(condition for condition in play.preconditions
                                            if str(condition.get("field") or "").endswith((
                                                ".verified_recipient",
                                                ".recipient_verified",
                                                ".stakeholder_verified",
                                                "_stakeholder_verified",
                                            ))
                                            and condition.get("value") is True
                                            and str(condition.get("op") or "") in
                                            {"=", "==", "eq"})
                guarded = not recipient_required or bool(verification_guards)
                checks.append(CandidateCheck(
                    play.play_id, "permission",
                    CheckOutcome.PASS if guarded else CheckOutcome.ELIMINATE,
                    ("verified_recipient_guard_pass" if guarded
                     else "verified_recipient_guard_missing"),
                    self.spec.reasoner_id, self.spec.version,
                    detail={"external_recipient_required": recipient_required,
                            "guard_count": len(verification_guards)}))
            for index, condition in enumerate(play.preconditions):
                field = str(condition.get("field") or "")
                neighbor = bool(condition.get("neighbor", False))
                exists = field in (request.context.neighbor_facts if neighbor
                                   else request.context.facts)
                operator = str(condition.get("op") or "exists")
                expected = condition.get("value")
                if operator == "exists":
                    passed = exists
                    actual = fact_value(request, field, neighbor=neighbor) if exists else None
                elif operator == "absent":
                    passed = not exists
                    actual = fact_value(request, field, neighbor=neighbor) if exists else None
                elif not exists:
                    passed, actual = False, None
                else:
                    actual = fact_value(request, field, neighbor=neighbor)
                    passed = _legacy_compare(actual, operator, expected)
                checks.append(CandidateCheck(
                    play.play_id, "precondition",
                    CheckOutcome.PASS if passed else CheckOutcome.ELIMINATE,
                    "precondition_pass" if passed else "precondition_failed",
                    self.spec.reasoner_id, self.spec.version,
                    detail={"index": index, "field": field, "neighbor": neighbor,
                            "operator": operator, "expected": expected, "actual": actual}))
        for play_id in tuple(spec.config.get("blocked_play_ids") or ()):
            checks.append(CandidateCheck(str(play_id), "policy", CheckOutcome.ELIMINATE,
                                         "tenant_policy_block", self.spec.reasoner_id,
                                         self.spec.version))
        return ReasonerResult(self.spec.reasoner_id, self.spec.version, ResultStatus.COMPLETED,
                              checks=tuple(checks), reason_codes=("constraints_evaluated",))


# ==================================================================================================
# Builders
# ==================================================================================================


def _capability(*, plays, policies=("read_only",), constraint_config=None,
                extra_reasoners=()) -> CapabilityManifest:
    constraint = ReasonerSpec("core.constraint", "1.0.0",
                              config=constraint_config if constraint_config is not None else {})
    return CapabilityManifest(
        capability_id="sales.gate_probe", version="1.0.0", domain="sales",
        root_entity_type="deal",
        goal=Goal("gate_probe", "Probe the gate"),
        reasoners=(constraint,) + tuple(extra_reasoners),
        plays=plays, policies=policies)


def _request(capability, *, facts=None, neighbor_facts=None, evidence=()) -> ReasoningRequest:
    context = ContextSnapshot(
        org_id="org_1", graph_version=7, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="sales.v1",
        facts=facts or {}, neighbor_facts=neighbor_facts or {}, evidence=evidence)
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="schedule.sweep")


def _play(play_id, *, preconditions=(), read_only=True, tags=(), metadata=None) -> PlayDefinition:
    return PlayDefinition(play_id=play_id, version="1.0.0", label=f"Play {play_id}",
                          steps=("Do the thing",), preconditions=preconditions,
                          read_only=read_only, tags=tags, metadata=metadata or {})


def _view(request, prior=None) -> UnitView:
    return UnitView(request=request, spec=active_spec(request, CONSTRAINT_UNIT_ID),
                    prior=prior or {})


def _cooling_request(*, status="open", verified=True, alternate=True,
                     next_step=None, with_evidence=True) -> ReasoningRequest:
    """The shipped `sales.deal_cooling` capability, which declares all four policies."""
    facts = {"deal.status": status, "deal.value": 250_000, "derived.engagement": 1_800,
             "thread.last_inbound": "2026-07-28T12:00:00+00:00"}
    if next_step is not None:
        facts["deal.next_step"] = next_step
    neighbor = {"contact.verified_recipient": verified,
                "account.alternate_stakeholder_verified": alternate}
    evidence = (EvidenceRef("ev_status", "deal.status", status),) if with_evidence else ()
    return _request(DEAL_COOLING_V1, facts=facts, neighbor_facts=neighbor, evidence=evidence)


def _prior(evidence_ids=(), finding_evidence=(), adjustment_evidence=()) -> dict:
    return {"core.temporal": ReasonerResult(
        "core.temporal", "1.0.0", ResultStatus.COMPLETED,
        evidence_ids=evidence_ids,
        findings=(Finding("f1", "probe", True, evidence_ids=finding_evidence),)
        if finding_evidence else (),
        adjustments=(CandidateAdjustment("restore_momentum", "risk", -100, "probe",
                                         evidence_ids=adjustment_evidence),)
        if adjustment_evidence else ())}


# ==================================================================================================
# Identity — the things the registry, the manifests and the SQL re-provers name
# ==================================================================================================


def test_identity_is_unchanged():
    unit = ConstraintReasoner()
    assert unit.unit_id == "core.constraint"
    assert unit.version == "1.0.0"
    assert unit.category == UnitCategory.SITUATION_UNDERSTANDING
    assert unit.spec == ReasonerSpec("core.constraint", "1.0.0")


def test_the_registered_name_still_resolves_to_this_unit():
    assert RegisteredConstraint is ConstraintUnit
    assert ConstraintReasoner is ConstraintUnit


def test_the_gate_publishes_no_metrics():
    """A scalar summary of the rows would be something downstream could weigh — and a weighed
    constraint is a soft penalty, not a gate.  `publishes` reserves the names against collision;
    the shipped v1.0.0 result carries none of them."""
    assert set(ConstraintUnit.publishes) == {"constraint_check_count",
                                             "constraint_elimination_count"}
    result = ConstraintUnit().evaluate(_cooling_request(), _prior(("ev_status",)))
    assert dict(result.metrics) == {}
    assert result.matched is None
    assert result.evidence_ids == ()
    assert result.reason_codes == ("constraints_evaluated",)
    assert result.status == ResultStatus.COMPLETED


# ==================================================================================================
# The differential test — the deliverable
# ==================================================================================================


def _scenarios() -> list[tuple[str, ReasoningRequest, dict]]:
    """Representative requests, chosen to reach every branch of the pre-migration unit."""
    scenarios: list[tuple[str, ReasoningRequest, dict]] = []

    # -- the shipped capability, all four policies live -----------------------------------------
    scenarios.append(("deal_cooling_all_clear",
                      _cooling_request(), _prior(("ev_status",))))
    scenarios.append(("deal_cooling_ungrounded",
                      _cooling_request(), {}))
    scenarios.append(("deal_cooling_no_prior_results",
                      _cooling_request(), {}))
    scenarios.append(("deal_cooling_grounded_via_finding",
                      _cooling_request(), _prior(finding_evidence=("ev_status",))))
    scenarios.append(("deal_cooling_grounded_via_adjustment",
                      _cooling_request(), _prior(adjustment_evidence=("ev_status",))))
    scenarios.append(("deal_cooling_stale_citation_is_not_grounding",
                      _cooling_request(), _prior(("ev_from_another_run",))))
    scenarios.append(("deal_cooling_closed_deal",
                      _cooling_request(status="closed"), _prior(("ev_status",))))
    scenarios.append(("deal_cooling_unverified_recipient",
                      _cooling_request(verified=False), _prior(("ev_status",))))
    scenarios.append(("deal_cooling_no_alternate_stakeholder",
                      _cooling_request(alternate=False), _prior(("ev_status",))))
    scenarios.append(("deal_cooling_next_step_present",
                      _cooling_request(next_step="demo on friday"), _prior(("ev_status",))))
    scenarios.append(("deal_cooling_no_snapshot_evidence",
                      _cooling_request(with_evidence=False), _prior(("ev_status",))))

    # -- read-only policy against a mutating play ------------------------------------------------
    mutating = _capability(plays=(_play("observe"), _play("auto_send", read_only=False)))
    scenarios.append(("read_only_blocks_a_mutating_play", _request(mutating), {}))

    # -- no policies at all, preconditions only --------------------------------------------------
    bare = _capability(
        plays=(_play("p1", preconditions=({"field": "deal.status", "op": "=", "value": "open"},)),),
        policies=())
    scenarios.append(("no_policies_preconditions_only",
                      _request(bare, facts={"deal.status": "open"}), {}))

    # -- nothing declared at all: zero rows ------------------------------------------------------
    empty = _capability(plays=(_play("p1"),), policies=())
    scenarios.append(("no_policies_no_preconditions", _request(empty), {}))

    # -- human approval, both spellings and neither ----------------------------------------------
    approval = _capability(
        plays=(_play("by_metadata", metadata={"execution_boundary": "human_approval_required"}),
               _play("by_tag", tags=("human_approval",)),
               _play("undeclared", metadata={"execution_boundary": "autonomous"}),
               _play("no_metadata")),
        policies=("human_approval_required",))
    scenarios.append(("human_approval_all_shapes", _request(approval), {}))

    # -- recipient guards: trivial pass, guarded, unguarded, wrong operator, wrong value ---------
    guard = {"field": "contact.verified_recipient", "neighbor": True, "op": "=", "value": True}
    weak_operator = dict(guard, op=">=")
    weak_value = dict(guard, value="yes")
    odd_suffix = {"field": "account.alternate_stakeholder_verified", "op": "eq", "value": True}
    recipient = _capability(
        plays=(_play("internal", metadata={"external_recipient_required": False}),
               _play("guarded", preconditions=(guard,),
                     metadata={"external_recipient_required": True}),
               _play("unguarded", metadata={"external_recipient_required": True}),
               _play("weak_operator", preconditions=(weak_operator,),
                     metadata={"external_recipient_required": True}),
               _play("weak_value", preconditions=(weak_value,),
                     metadata={"external_recipient_required": True}),
               _play("suffix_variant", preconditions=(odd_suffix,),
                     metadata={"external_recipient_required": True})),
        policies=("no_unverified_recipient",))
    scenarios.append(("recipient_guard_shapes",
                      _request(recipient, facts={"account.alternate_stakeholder_verified": True},
                               neighbor_facts={"contact.verified_recipient": True}), {}))

    # -- every precondition operator, on present, absent and unparseable facts -------------------
    operators = _capability(
        plays=(_play("ops", preconditions=(
            {"field": "deal.value", "op": ">", "value": 100_000},
            {"field": "deal.value", "op": ">=", "value": 250_000},
            {"field": "deal.value", "op": "<", "value": 100_000},
            {"field": "deal.value", "op": "<=", "value": 250_000},
            {"field": "deal.stage", "op": "in", "value": ("discovery", "negotiation")},
            {"field": "deal.stage", "op": "in", "value": "negotiation"},
            {"field": "deal.stage", "op": "!=", "value": "closed"},
            {"field": "deal.stage", "op": "ne", "value": "negotiation"},
            {"field": "deal.stage", "op": "=="},
            {"field": "deal.owner", "op": "exists"},
            {"field": "deal.owner", "op": "absent"},
            {"field": "deal.next_step", "op": "exists"},
            {"field": "deal.next_step", "op": "absent"},
            {"field": "deal.next_step", "op": ">", "value": 1},
            {"field": "deal.label", "op": ">", "value": 1},
            {"field": "deal.value", "op": ">", "value": "not-a-number"},
            {"field": "contact.title", "neighbor": True, "op": "=", "value": "VP"},
            {"field": "contact.title", "op": "=", "value": "VP"},
            {"op": "exists"},
            {"field": "deal.owner"},
        )),),
        policies=())
    scenarios.append(("every_operator", _request(
        operators,
        facts={"deal.value": 250_000, "deal.stage": "negotiation", "deal.owner": "rohit",
               "deal.label": "flagship"},
        neighbor_facts={"contact.title": "VP"}), {}))

    # -- a wrapped fact record, which fact_value unwraps ----------------------------------------
    wrapped = _capability(
        plays=(_play("p1", preconditions=({"field": "deal.status", "op": "=", "value": "open"},)),),
        policies=())
    scenarios.append(("wrapped_fact_record", _request(
        wrapped, facts={"deal.status": {"value": "open", "confidence_bp": 9_000}}), {}))

    # -- tenant block list, including a duplicate and an id no play carries ----------------------
    blocked = _capability(
        plays=(_play("p1"), _play("p2")),
        constraint_config={"blocked_play_ids": ("p2", "p2", "retired_play")})
    scenarios.append(("tenant_block_list", _request(blocked), {}))

    # -- an empty block list is not a block ------------------------------------------------------
    unblocked = _capability(plays=(_play("p1"),), constraint_config={"blocked_play_ids": ()})
    scenarios.append(("empty_block_list", _request(unblocked), {}))

    # -- config absent entirely ------------------------------------------------------------------
    no_config = _capability(plays=(_play("p1"),))
    scenarios.append(("config_absent", _request(no_config), {}))

    return scenarios


@pytest.mark.parametrize("name,request_,prior", _scenarios(),
                         ids=[item[0] for item in _scenarios()])
def test_migrated_unit_is_hash_identical_to_the_frozen_reference(name, request_, prior):
    old = _LegacyConstraintReasoner().evaluate(request_, prior)
    new = ConstraintUnit().evaluate(request_, prior)
    assert new.semantic_hash == old.semantic_hash, name
    # The hash is the contract, but a mismatch in it is easier to diagnose row by row.
    assert [c.play_id for c in new.checks] == [c.play_id for c in old.checks]
    assert [(c.stage, c.outcome, c.reason_code, c.evaluator_id, c.evaluator_version,
             dict(c.detail)) for c in new.checks] == \
           [(c.stage, c.outcome, c.reason_code, c.evaluator_id, c.evaluator_version,
             dict(c.detail)) for c in old.checks]


def test_unsupported_operator_still_raises_in_both_implementations():
    capability = _capability(
        plays=(_play("p1", preconditions=({"field": "deal.status", "op": "~=", "value": "x"},)),),
        policies=())
    request = _request(capability, facts={"deal.status": "open"})
    with pytest.raises(ValueError, match="unsupported precondition operator"):
        _LegacyConstraintReasoner().evaluate(request, {})
    with pytest.raises(ValueError, match="unsupported precondition operator"):
        ConstraintUnit().evaluate(request, {})


def test_missing_recipient_effect_declaration_still_fails_closed_in_both():
    """The metadata is indexed, not `.get()`-ed: a malformed play must fail loudly rather than be
    read as 'reaches nobody'.  Built by hand because the manifest validator normally forbids it."""
    capability = _capability(plays=(_play("p1"),), policies=("read_only",))
    object.__setattr__(capability, "policies", ("no_unverified_recipient", "read_only"))
    request = _request(capability)
    with pytest.raises(KeyError):
        _LegacyConstraintReasoner().evaluate(request, {})
    with pytest.raises(KeyError):
        ConstraintUnit().evaluate(request, {})


def test_a_capability_that_does_not_declare_this_unit_is_rejected_identically():
    capability = CapabilityManifest(
        capability_id="sales.other", version="1.0.0", domain="sales", root_entity_type="deal",
        goal=Goal("g", "g"), reasoners=(ReasonerSpec("core.temporal", "1.0.0"),),
        plays=(_play("p1"),), policies=())
    request = _request(capability)
    with pytest.raises(ValueError, match="does not declare reasoner core.constraint"):
        _LegacyConstraintReasoner().evaluate(request, {})
    with pytest.raises(ValueError, match="does not declare reasoner core.constraint"):
        ConstraintUnit().evaluate(request, {})


# ==================================================================================================
# Determinism and config ordering
# ==================================================================================================


def test_identical_input_produces_an_identical_hash():
    request, prior = _cooling_request(), _prior(("ev_status",))
    first = ConstraintUnit().evaluate(request, prior)
    second = ConstraintUnit().evaluate(request, prior)
    assert first.semantic_hash == second.semantic_hash


def test_config_key_order_cannot_change_the_result():
    """Config round-trips through JSON in the audit store and comes back re-ordered.  A unit that
    iterated a config mapping unsorted would hash differently after a replay."""
    plays = (_play("p1"), _play("p2"))
    forward = _capability(plays=plays, constraint_config={
        "blocked_play_ids": ("p2",), "unused_a": 1, "unused_b": 2, "unused_c": 3})
    reverse = _capability(plays=plays, constraint_config={
        "unused_c": 3, "unused_b": 2, "unused_a": 1, "blocked_play_ids": ("p2",)})
    first = ConstraintUnit().evaluate(_request(forward), {})
    second = ConstraintUnit().evaluate(_request(reverse), {})
    assert first.semantic_hash == second.semantic_hash


def test_prior_result_insertion_order_cannot_change_the_result():
    """`evidence_required` folds every dependency's citations into a set; the fold must not depend
    on which unit happened to be inserted into the mapping first."""
    request = _cooling_request()
    a = ReasonerResult("core.temporal", "1.0.0", ResultStatus.COMPLETED,
                       evidence_ids=("ev_status",))
    b = ReasonerResult("core.relationship", "1.0.0", ResultStatus.COMPLETED)
    forward = ConstraintUnit().evaluate(request, {"core.temporal": a, "core.relationship": b})
    reverse = ConstraintUnit().evaluate(request, {"core.relationship": b, "core.temporal": a})
    assert forward.semantic_hash == reverse.semantic_hash


def test_emission_order_is_grouped_by_play_then_slot_then_authored_index():
    """The row sequence is part of the semantic hash, so it must be a property of the claim rather
    than of which plugin ran first."""
    result = ConstraintUnit().evaluate(_cooling_request(), _prior(("ev_status",)))
    play_ids = [check.play_id for check in result.checks]
    assert play_ids == sorted(play_ids, key=lambda item: [
        p.play_id for p in DEAL_COOLING_V1.plays].index(item))
    first_play = [check for check in result.checks if check.play_id == "restore_momentum"]
    assert [check.reason_code for check in first_play] == [
        "read_only_policy_pass", "human_approval_boundary_pass", "evidence_policy_pass",
        "verified_recipient_guard_pass", "precondition_pass", "precondition_pass"]


def test_tenant_blocks_are_emitted_after_every_play_row():
    capability = _capability(plays=(_play("p1"), _play("p2")),
                             constraint_config={"blocked_play_ids": ("p2", "p1")})
    result = ConstraintUnit().evaluate(_request(capability), {})
    codes = [check.reason_code for check in result.checks]
    assert codes == ["read_only_policy_pass", "read_only_policy_pass",
                     "tenant_policy_block", "tenant_policy_block"]
    assert [c.play_id for c in result.checks[-2:]] == ["p2", "p1"]


# ==================================================================================================
# Plugins in isolation
# ==================================================================================================


def test_policy_plugin_emits_read_only_and_evidence_rows_only_when_declared():
    plugin = PolicyEnforcementPlugin()
    capability = _capability(plays=(_play("p1"),), policies=("read_only",))
    rows = plugin.checks(_view(_request(capability)))
    assert [check.reason_code for _, check in rows] == ["read_only_policy_pass"]

    silent = _capability(plays=(_play("p1"),), policies=())
    assert plugin.checks(_view(_request(silent))) == ()


def test_policy_plugin_eliminates_a_mutating_play_under_read_only():
    plugin = PolicyEnforcementPlugin()
    capability = _capability(plays=(_play("auto_send", read_only=False),))
    (_, check), = plugin.checks(_view(_request(capability)))
    assert check.outcome == CheckOutcome.ELIMINATE
    assert check.reason_code == "read_only_policy"
    assert dict(check.detail) == {"required": True, "play_read_only": False}
    assert (check.evaluator_id, check.evaluator_version) == (CONSTRAINT_UNIT_ID,
                                                             CONSTRAINT_UNIT_VERSION)


def test_policy_plugin_requires_grounding_in_this_exact_snapshot():
    plugin = PolicyEnforcementPlugin()
    request = _cooling_request()
    grounded = [c for _, c in plugin.checks(_view(request, _prior(("ev_status",))))
                if c.stage == "policy" and c.reason_code.startswith("evidence")]
    stale = [c for _, c in plugin.checks(_view(request, _prior(("ev_elsewhere",))))
             if c.stage == "policy" and c.reason_code.startswith("evidence")]
    assert {c.outcome for c in grounded} == {CheckOutcome.PASS}
    assert {c.outcome for c in stale} == {CheckOutcome.ELIMINATE}
    assert dict(stale[0].detail) == {"context_evidence_count": 1, "used_evidence_count": 0}


def test_policy_plugin_blocks_ids_the_capability_never_declared():
    """A tenant block is an id-level retirement; it does not have to correspond to a live play."""
    plugin = PolicyEnforcementPlugin()
    capability = _capability(plays=(_play("p1"),), policies=(),
                             constraint_config={"blocked_play_ids": ("retired",)})
    (_, check), = plugin.checks(_view(_request(capability)))
    assert (check.play_id, check.outcome, check.reason_code) == (
        "retired", CheckOutcome.ELIMINATE, "tenant_policy_block")
    assert dict(check.detail) == {}


def test_permission_plugin_accepts_both_approval_spellings_and_rejects_silence():
    plugin = PermissionVerificationPlugin()
    capability = _capability(
        plays=(_play("by_metadata", metadata={"execution_boundary": "human_approval_required"}),
               _play("by_tag", tags=("human_approval",)),
               _play("silent",)),
        policies=("human_approval_required",))
    rows = [check for _, check in plugin.checks(_view(_request(capability)))]
    assert [check.outcome for check in rows] == [
        CheckOutcome.PASS, CheckOutcome.PASS, CheckOutcome.ELIMINATE]
    assert rows[2].reason_code == "human_approval_boundary_missing"
    assert dict(rows[1].detail) == {"execution_boundary": None, "human_approval_tag": True}


def test_permission_plugin_only_counts_an_equality_guard_on_a_true_value():
    plugin = PermissionVerificationPlugin()
    guard = {"field": "contact.verified_recipient", "op": "=", "value": True}
    capability = _capability(
        plays=(_play("guarded", preconditions=(guard,),
                     metadata={"external_recipient_required": True}),
               _play("wrong_op", preconditions=(dict(guard, op=">="),),
                     metadata={"external_recipient_required": True}),
               _play("wrong_value", preconditions=(dict(guard, value=1),),
                     metadata={"external_recipient_required": True}),
               _play("internal", metadata={"external_recipient_required": False})),
        policies=("no_unverified_recipient",))
    rows = [check for _, check in plugin.checks(_view(_request(capability)))]
    assert [check.outcome for check in rows] == [
        CheckOutcome.PASS, CheckOutcome.ELIMINATE, CheckOutcome.ELIMINATE, CheckOutcome.PASS]
    assert dict(rows[0].detail) == {"external_recipient_required": True, "guard_count": 1}
    assert dict(rows[3].detail) == {"external_recipient_required": False, "guard_count": 0}


def test_precondition_plugin_distinguishes_absent_from_smaller():
    plugin = PreconditionPlugin()
    capability = _capability(
        plays=(_play("p1", preconditions=(
            {"field": "deal.value", "op": ">=", "value": 100_000},
            {"field": "deal.missing", "op": ">=", "value": 100_000},
        )),), policies=())
    request = _request(capability, facts={"deal.value": 50_000})
    rows = [check for _, check in plugin.checks(_view(request))]
    assert [check.outcome for check in rows] == [CheckOutcome.ELIMINATE, CheckOutcome.ELIMINATE]
    assert dict(rows[0].detail)["actual"] == 50_000
    assert dict(rows[1].detail)["actual"] is None


def test_precondition_plugin_reads_the_neighbour_space_when_asked():
    plugin = PreconditionPlugin()
    condition = {"field": "contact.verified_recipient", "neighbor": True, "op": "=", "value": True}
    capability = _capability(plays=(_play("p1", preconditions=(condition,)),), policies=())
    present = _request(capability, neighbor_facts={"contact.verified_recipient": True})
    misplaced = _request(capability, facts={"contact.verified_recipient": True})
    assert plugin.checks(_view(present))[0][1].outcome == CheckOutcome.PASS
    assert plugin.checks(_view(misplaced))[0][1].outcome == CheckOutcome.ELIMINATE


def test_precondition_plugin_records_the_authored_index_on_every_row():
    plugin = PreconditionPlugin()
    capability = _capability(plays=(_play("p1", preconditions=(
        {"field": "a", "op": "absent"}, {"field": "b", "op": "absent"},
        {"field": "c", "op": "absent"})),), policies=())
    rows = [check for _, check in plugin.checks(_view(_request(capability)))]
    assert [dict(check.detail)["index"] for check in rows] == [0, 1, 2]


def test_every_plugin_summarises_its_own_rows_as_an_observation():
    view = _view(_cooling_request(verified=False), _prior(("ev_status",)))
    for plugin in ConstraintUnit().plugins:
        observations = plugin.contribute(view)
        assert len(observations) == 1
        observation = observations[0]
        assert isinstance(observation, Observation)
        assert observation.plugin_id == plugin.plugin_id
        rows = plugin.checks(view)
        assert observation.metrics["checks_emitted"] == len(rows)
        assert observation.metrics["eliminated"] == sum(
            1 for _, check in rows if check.outcome == CheckOutcome.ELIMINATE)


def test_a_plugin_with_nothing_to_say_contributes_no_observation():
    view = _view(_request(_capability(plays=(_play("p1"),), policies=())))
    assert PermissionVerificationPlugin().contribute(view) == ()
    assert PreconditionPlugin().contribute(view) == ()


# ==================================================================================================
# The gate never abstains
# ==================================================================================================


def test_thin_context_produces_eliminations_rather_than_insufficient_context():
    """The base validator would raise MissingContextError for absent required_fields.  For a gate
    that inverts the meaning: removing the gate because the room is dark is not fail-closed."""
    constraint = ReasonerSpec("core.constraint", "1.0.0",
                              required_fields=("deal.status", "deal.value"))
    capability = CapabilityManifest(
        capability_id="sales.thin", version="1.0.0", domain="sales", root_entity_type="deal",
        goal=Goal("g", "g"), reasoners=(constraint,),
        plays=(_play("p1", preconditions=({"field": "deal.status", "op": "exists"},)),),
        policies=("read_only",))
    result = ConstraintUnit().evaluate(_request(capability), {})
    assert result.status == ResultStatus.COMPLETED
    assert result.missing_fields == ()
    assert [check.reason_code for check in result.checks] == [
        "read_only_policy_pass", "precondition_failed"]


def test_declared_required_fields_never_leak_evidence_into_the_result():
    """The unit cites nothing: its rows are re-proved directly, so unproven provenance would only
    weaken the audit trail — and would change the semantic hash."""
    constraint = ReasonerSpec("core.constraint", "1.0.0", required_fields=("deal.status",))
    capability = CapabilityManifest(
        capability_id="sales.cited", version="1.0.0", domain="sales", root_entity_type="deal",
        goal=Goal("g", "g"), reasoners=(constraint,), plays=(_play("p1"),), policies=("read_only",))
    request = _request(capability, facts={"deal.status": "open"},
                       evidence=(EvidenceRef("ev_status", "deal.status", "open"),))
    new = ConstraintUnit().evaluate(request, {})
    old = _LegacyConstraintReasoner().evaluate(request, {})
    assert new.evidence_ids == ()
    assert new.semantic_hash == old.semantic_hash
