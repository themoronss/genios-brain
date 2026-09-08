"""Executable contract for Rule 11 at Layer 4, and for the confidence floor that gates silence.

Two laws are pinned here, and they are the same law seen from two ends.

**Rule 11 — confidence falls freely; it rises only with named independent evidence.** What this
replaced was a last-writer scan: every unit that published `confidence_bp` overwrote the previous
one, so the decision's confidence was whatever the last unit to speak happened to say, and a unit
late in the DAG could raise it with nothing named at all. The refusal is an EXCEPTION rather than
a receipt because a warn ships — `capture/validate/confidence.py` drew that line one layer down
and this is the same class raised for the same reason.

**Law 3 — silence is operational on every live lane.** `confidence_floor_bp` used to default to
0, so on the compiled lane — the lane the whole v2 plan depends on — `confidence_bp < 0` was never
true and the system had never once abstained. A floor that defaults to 0 is not a floor. Floors
are now declared per LANE, seeded at 4500 bp, and a below-floor decision becomes a reason-coded
DEFER that names *what would resolve it* — an absence the run actually recorded, never the fact
it is missing.

The two meet at one point worth stating: confidence gates silence, so a fabricated raise does not
merely mis-score a card, it pushes a card past the floor that should have suppressed it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.contracts.reasoning import (
    CONFIDENCE_VECTOR_KEYS,
    CapabilityManifest,
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.decision_maker import (
    BELOW_FLOOR_ABSENT_UNIT,
    BELOW_FLOOR_MISSING_FIELD,
    BELOW_FLOOR_REASON,
    BELOW_FLOOR_RESOLVER_CAP,
    BELOW_FLOOR_WEAK_INPUT,
    CONFIDENCE_AUTHORITY,
    CONFIDENCE_AUTHORITY_KEY,
    CONFIDENCE_BASE_REASON,
    CONFIDENCE_CAPPED_REASON,
    CONFIDENCE_FLOOR_BY_LANE,
    CONFIDENCE_FLOOR_KEY,
    CONFIDENCE_LOWERED_REASON,
    CONFIDENCE_RAISED_REASON,
    DEFAULT_CONFIDENCE_FLOOR_BP,
    FLOOR_SOURCE_DECLARED,
    FLOOR_SOURCE_LANE,
    FLOOR_SOURCE_LANE_OVER_ZERO,
    LANE_KEY,
    UNATTRIBUTED_GROUP,
    UNDECLARED_LANE,
    ConfidenceViolation,
    DecisionMaker,
    RaiseClaim,
    bounded_raise,
    calculate_confidence,
    compose_confidence,
    raise_claim,
    resolve_confidence_floor,
)
from genios_engine.reason.protocols import OrchestrationError

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
COMPILED_LANE = "expertise_to_capability"


# ── scaffolding ──────────────────────────────────────────────────────────────────────────────

#: The facts every test snapshot carries. Evidence must resolve to a fact that is actually in the
#: frozen context — the contract enforces it — so the two live together.
FACTS = {"deal.status": "open", "deal.owner": "ana"}


def _evidence(evidence_id: str, *, group: str | None, confidence_bp: int = 8_000,
              field: str = "deal.status") -> EvidenceRef:
    return EvidenceRef(evidence_id=evidence_id, field=field, value=FACTS[field],
                       confidence_bp=confidence_bp, independence_group=group)


def _request(*, metadata=None, specs=None, evidence=(), missing_fields=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(specs or (ReasonerSpec("core.confidence", "1"),)),
        plays=(PlayDefinition(play_id="restore_momentum", version="1", label="Restore",
                              steps=("Prepare a grounded draft",), impact_bp=6_000,
                              success_probability_bp=6_000, effort_bp=2_000, risk_bp=1_000),),
        policies=(),
        metadata=metadata or {},
    )
    context = ContextSnapshot(
        org_id="org_1", graph_version=17, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="selector.v1",
        facts=dict(FACTS),
        evidence=tuple(evidence),
        missing_fields=tuple(missing_fields),
    )
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


def _completed(reasoner_id: str, *, evidence_ids=(), findings=(), **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=True, metrics=metrics,
                          evidence_ids=tuple(evidence_ids), findings=tuple(findings))


# ── Rule 11 · the starting point ─────────────────────────────────────────────────────────────

def test_the_named_authority_settles_the_composition_and_observers_do_not_compose_against_it():
    """Exactly one unit publishes this metric, and Rule 11 does not repeal that.

    `core.confidence` computes its number FROM Rule 11's own inputs — independent evidence groups,
    coverage, corroboration, source quality — so its publication is the composed belief, not a
    transition applied to somebody else's. If earlier observers were folded in on top of it,
    appending a unit to the roster would silently re-score every decision in the system, which is
    the property the metric-authority rule exists to hold.
    """
    results = [_completed("legacy.rule", confidence_bp=3_000),
               _completed("legacy.score_gate", confidence_bp=4_000),
               _completed(CONFIDENCE_AUTHORITY, confidence_bp=9_100),
               _completed("core.planning", confidence_bp=100)]

    composed = compose_confidence(results, _request(), False)

    assert composed.confidence_bp == 9_100
    assert composed.settled_by == "confidence_authority"
    assert composed.receipts[0] == f"{CONFIDENCE_BASE_REASON}:{CONFIDENCE_AUTHORITY}:9100"


def test_the_first_publication_is_the_belief_and_not_a_raise_against_the_default():
    """A measurement is not a transition. The manifest default holds only until one arrives.

    Treating the first published confidence as a raise against `default_confidence_bp` would refuse
    every capability whose appointed authority is not scheduled — a manifest shape, not a Rule 11
    violation. L1 draws the same line: it takes an incumbent belief as the base only when a
    previous layer actually held one.
    """
    composed = compose_confidence([_completed("gate", confidence_bp=9_000)], _request(), False)

    assert composed.confidence_bp == 9_000
    assert composed.settled_by == "rule_11_composition"
    assert composed.receipts == (f"{CONFIDENCE_BASE_REASON}:gate:9000",)


def test_the_capability_default_holds_only_when_nobody_publishes_anything():
    composed = compose_confidence([], _request(metadata={"default_confidence_bp": 2_500}), False)

    assert composed.confidence_bp == 2_500
    assert composed.receipts == (f"{CONFIDENCE_BASE_REASON}:capability_default:2500",)


def test_a_failed_authority_has_no_opinion_and_the_observers_compose():
    results = [_completed("legacy.rule", confidence_bp=3_000),
               ReasonerResult(CONFIDENCE_AUTHORITY, "1", ResultStatus.FAILED,
                              reason_codes=("reasoner_failure",))]

    assert compose_confidence(results, _request(), False).confidence_bp == 3_000


# ── Rule 11 · falling is free, rising is not ─────────────────────────────────────────────────

def test_a_unit_may_lower_confidence_freely_and_the_movement_is_receipted():
    results = [_completed("gate", confidence_bp=9_000),
               _completed("core.risk", confidence_bp=2_500)]

    composed = compose_confidence(results, _request(), False)

    assert composed.confidence_bp == 2_500
    assert f"{CONFIDENCE_LOWERED_REASON}:core.risk:9000->2500" in composed.receipts


def test_an_uncited_raise_throws_rather_than_being_receipted():
    """The acceptance row is an EXCEPTION, not a count. A warn ships.

    This is the verified defect in one line: a unit later in the DAG raising the number with
    nothing named at all, and the old scan accepting it silently because it was simply the last to
    speak.
    """
    results = [_completed("legacy.rule", confidence_bp=3_000),
               _completed("legacy.score_gate", confidence_bp=4_200)]

    with pytest.raises(ConfidenceViolation, match="no independent evidence named"):
        compose_confidence(results, _request(), False)


def test_a_raise_citing_a_new_independence_group_is_allowed_and_bounded():
    """What naming buys is a bounded raise, never an exemption.

    L1 shipped the exemption first and one 100 bp Slack aside lifted a ceiling of 100 to 9003.
    Here the raise is at most half the remaining headroom, damped by the weakest new witness, and
    never past what the unit itself claimed.
    """
    evidence = (_evidence("ev_base", group="crm"), _evidence("ev_new", group="signed_contract"))
    results = [_completed("gate", confidence_bp=4_000, evidence_ids=("ev_base",)),
               _completed("core.recommendation", confidence_bp=9_000,
                          evidence_ids=("ev_new",))]

    composed = compose_confidence(results, _request(evidence=evidence), False)

    assert 4_000 < composed.confidence_bp < 9_000
    assert composed.confidence_bp == bounded_raise(4_000, RaiseClaim(
        unit_id="core.recommendation", claimed_bp=9_000, groups=("signed_contract",),
        witness_bp=8_000, evidence_ids=("ev_new",)))
    assert any(item.startswith(f"{CONFIDENCE_RAISED_REASON}:core.recommendation:4000->")
               and item.endswith(":signed_contract") for item in composed.receipts)
    assert composed.counted_groups == ("crm", "signed_contract")


def test_the_same_origin_cannot_corroborate_twice():
    """A forwarded copy of an email is not a second witness — that is what re-counting is."""
    evidence = (_evidence("ev_a", group="crm"), _evidence("ev_b", group="crm"))
    results = [_completed("gate", confidence_bp=3_000, evidence_ids=("ev_a",)),
               _completed("core.recommendation", confidence_bp=8_000, evidence_ids=("ev_b",))]

    with pytest.raises(ConfidenceViolation, match="not already counted"):
        compose_confidence(results, _request(evidence=evidence), False)


@pytest.mark.parametrize("group", [None, "", UNATTRIBUTED_GROUP])
def test_evidence_that_asserted_no_origin_can_lower_but_never_raise(group):
    """Independence is asserted, never inferred: the unstated pool is one group that only lowers.

    Two refs that look independent because they came from two rows are exactly the echo Rule 11
    exists to stop, and `legacy_context.py` writes the literal `unattributed` for every fact that
    carries no group at all.
    """
    evidence = (_evidence("ev_a", group="crm"), _evidence("ev_b", group=group))
    results = [_completed("gate", confidence_bp=3_000, evidence_ids=("ev_a",)),
               _completed("core.recommendation", confidence_bp=8_000, evidence_ids=("ev_b",))]

    with pytest.raises(ConfidenceViolation):
        compose_confidence(results, _request(evidence=evidence), False)


def test_a_citation_that_does_not_resolve_in_the_frozen_snapshot_cannot_license_a_raise():
    """A raise may only rest on evidence the selector actually froze into this run."""
    results = [_completed("gate", confidence_bp=3_000),
               _completed("core.recommendation", confidence_bp=8_000,
                          evidence_ids=("ev_from_nowhere",))]

    with pytest.raises(ConfidenceViolation):
        compose_confidence(results, _request(), False)


def test_a_raise_may_be_licensed_by_evidence_a_finding_named():
    """Rule 11 reads what THIS unit stood behind — result, findings and adjustments alike."""
    evidence = (_evidence("ev_base", group="crm"), _evidence("ev_new", group="email"))
    finding = Finding(finding_id="momentum", kind="momentum", evidence_ids=("ev_new",))
    results = [_completed("gate", confidence_bp=4_000, evidence_ids=("ev_base",)),
               _completed("core.recommendation", confidence_bp=6_000, findings=(finding,))]

    assert compose_confidence(results, _request(evidence=evidence), False).confidence_bp > 4_000


def test_a_unit_cannot_borrow_a_neighbours_citation_to_license_its_own_raise():
    """The union is per unit. A run-wide union would let any raise stand on somebody else's work."""
    evidence = (_evidence("ev_base", group="crm"), _evidence("ev_new", group="email"))
    results = [_completed("gate", confidence_bp=4_000, evidence_ids=("ev_base", "ev_new")),
               _completed("core.recommendation", confidence_bp=6_000)]

    with pytest.raises(ConfidenceViolation):
        compose_confidence(results, _request(evidence=evidence), False)


# ── Rule 11 · the arithmetic of a lawful raise ───────────────────────────────────────────────

def _claim(claimed_bp: int, witness_bp: int) -> RaiseClaim:
    return RaiseClaim(unit_id="u", claimed_bp=claimed_bp, groups=("g",),
                      witness_bp=witness_bp, evidence_ids=("ev",))


def test_a_bounded_raise_never_passes_what_the_unit_itself_claimed():
    assert bounded_raise(5_900, _claim(6_000, 10_000)) == 6_000


def test_a_bounded_raise_is_proportional_to_its_weakest_new_witness():
    """Agreeing weakly is not the same as agreeing."""
    strong = bounded_raise(2_000, _claim(9_000, 9_000))
    weak = bounded_raise(2_000, _claim(9_000, 1_000))

    assert 2_000 < weak < strong < 9_000


def test_no_chain_of_agreeing_units_ever_reaches_certainty():
    value = 1_000
    for _ in range(50):
        value = bounded_raise(value, _claim(10_000, 10_000))

    assert value < 10_000


def test_the_raise_is_integer_basis_points_end_to_end():
    """A float here would make the decision hash machine-dependent and destroy replay."""
    assert isinstance(bounded_raise(3_333, _claim(7_777, 6_666)), int)


def test_a_claim_is_only_built_from_origins_not_already_counted():
    request = _request(evidence=(_evidence("ev_a", group="crm"),))
    result = _completed("u", confidence_bp=9_000, evidence_ids=("ev_a",))

    assert raise_claim(result, request, frozenset()) is not None
    assert raise_claim(result, request, frozenset({"crm"})) is None


def test_a_group_is_worth_its_weakest_member():
    """Taking the strongest would let one strong ref carry a group full of weak ones."""
    request = _request(evidence=(_evidence("ev_a", group="crm", confidence_bp=9_000),
                                 _evidence("ev_b", group="crm", confidence_bp=1_200,
                                           field="deal.owner")))
    result = _completed("u", confidence_bp=9_000, evidence_ids=("ev_a", "ev_b"))

    assert raise_claim(result, request, frozenset()).witness_bp == 1_200


# ── preserved behaviour ──────────────────────────────────────────────────────────────────────

def test_the_degraded_cap_still_binds_after_a_lawful_raise():
    """A decision reached with a blind spot must never present itself as well-evidenced."""
    evidence = (_evidence("ev_base", group="crm"), _evidence("ev_new", group="email"))
    results = [_completed("gate", confidence_bp=4_000, evidence_ids=("ev_base",)),
               _completed("core.recommendation", confidence_bp=9_000, evidence_ids=("ev_new",))]

    composed = compose_confidence(results, _request(evidence=evidence), True)

    assert composed.confidence_bp == 5_000
    assert any(item.startswith(CONFIDENCE_CAPPED_REASON) for item in composed.receipts)


def test_a_non_integer_confidence_is_still_a_manifest_fault():
    """Preserved from the scan this replaced, and reached through a duck-typed result on purpose.

    `ReasonerResult` already refuses a non-integer metric at construction, so a typed result can
    never carry one — but the composition is handed `Any` (the replay verifier passes a
    `SimpleNamespace` request, and a future adapter could pass a stub result), and a guard that
    only holds when another guard already held is not a guard. The message is the one this module
    has always raised.
    """
    stub = SimpleNamespace(reasoner_id="gate", status=ResultStatus.COMPLETED,
                           metrics={"confidence_bp": True}, evidence_ids=(), findings=(),
                           adjustments=())

    with pytest.raises(OrchestrationError, match="confidence_bp must be an integer"):
        compose_confidence([stub], _request(), False)


def test_a_capability_may_still_appoint_its_own_confidence_authority():
    results = [_completed("core.momentum", confidence_bp=7_777),
               _completed(CONFIDENCE_AUTHORITY, confidence_bp=1_000)]
    request = _request(specs=(ReasonerSpec("core.momentum", "1"),
                              ReasonerSpec("core.confidence", "1")),
                       metadata={CONFIDENCE_AUTHORITY_KEY: "core.momentum"})

    assert compose_confidence(results, request, False).confidence_bp == 7_777


def test_the_integer_seam_the_replay_verifier_uses_agrees_with_the_composition():
    """`reason.store` re-runs the candidate pipeline to verify a persisted row; it must not have
    to reconstruct a receipt in order to check a number."""
    results = [_completed("gate", confidence_bp=6_100)]

    assert calculate_confidence(results, _request(), False) == \
        compose_confidence(results, _request(), False).confidence_bp


def test_the_composition_is_pure_and_repeats_itself_exactly():
    results = [_completed("gate", confidence_bp=6_100),
               _completed("core.risk", confidence_bp=4_100)]
    request = _request()

    first = compose_confidence(results, request, False)
    second = compose_confidence(results, request, False)

    assert first == second


def test_rule_11_inputs_are_carried_as_a_subset_and_a_missing_one_is_absent_not_zero():
    """Substituting a number for an input that does not exist scored every card exactly 50."""
    results = [_completed(CONFIDENCE_AUTHORITY, confidence_bp=8_000,
                          independent_evidence_groups=3, evidence_coverage_bp=7_500)]

    vector = compose_confidence(results, _request(), False).vector

    assert vector == {"independent_evidence_groups": 3, "evidence_coverage_bp": 7_500}
    assert set(vector) <= set(CONFIDENCE_VECTOR_KEYS)
    assert "corroboration_bp" not in vector


# ── the floor · declared per lane, never zero ────────────────────────────────────────────────

def test_a_lane_that_declares_no_floor_inherits_one_rather_than_an_exemption():
    floor, source = resolve_confidence_floor(_request())

    assert floor == DEFAULT_CONFIDENCE_FLOOR_BP
    assert source == f"{FLOOR_SOURCE_LANE}:{UNDECLARED_LANE}"


def test_the_compiled_lane_carries_the_seeded_floor():
    """doc 01 C6: 4500 bp on the lane v2 depends on, which declares no floor of its own."""
    floor, source = resolve_confidence_floor(_request(metadata={LANE_KEY: COMPILED_LANE}))

    assert floor == CONFIDENCE_FLOOR_BY_LANE[COMPILED_LANE] == 4_500
    assert source == f"{FLOOR_SOURCE_LANE}:{COMPILED_LANE}"


def test_a_manifest_that_declares_its_own_floor_keeps_it():
    floor, source = resolve_confidence_floor(
        _request(metadata={LANE_KEY: COMPILED_LANE, CONFIDENCE_FLOOR_KEY: 7_000}))

    assert floor == 7_000
    assert source == f"{FLOOR_SOURCE_DECLARED}:{COMPILED_LANE}"


def test_a_declared_zero_is_not_a_declaration_of_no_floor():
    """No live lane has one. A zero is a manifest that declined to choose, and the record says so.

    This is the exact shape the audit kept finding: `legacy_pack.py` writes 0 when a pack states no
    `gate.c_min`, and under the old default that silently disabled abstention for that tenant.
    """
    floor, source = resolve_confidence_floor(
        _request(metadata={LANE_KEY: COMPILED_LANE, CONFIDENCE_FLOOR_KEY: 0}))

    assert floor == DEFAULT_CONFIDENCE_FLOOR_BP
    assert source == f"{FLOOR_SOURCE_LANE_OVER_ZERO}:{COMPILED_LANE}"


def test_a_malformed_floor_is_still_a_manifest_fault():
    with pytest.raises(OrchestrationError, match="integer basis points"):
        resolve_confidence_floor(_request(metadata={CONFIDENCE_FLOOR_KEY: 20_000}))


def test_the_floor_is_read_from_the_capability_and_never_from_the_execution_mode():
    """`reason.store`'s replay verifier re-derives a decision from a capability and a context with
    no mode at all. A floor that varied by mode would make a replay disagree with the run it
    replays — and replay is what the entire audit story rests on."""
    full = _request(metadata={LANE_KEY: COMPILED_LANE})
    replay_view = SimpleNamespace(capability=full.capability, context=full.context)

    assert resolve_confidence_floor(replay_view) == resolve_confidence_floor(full)


# ── the floor · silence, and what would resolve it ───────────────────────────────────────────

def _decide(results, *, metadata=None, evidence=(), missing_fields=(), specs=None,
            degraded=False):
    return DecisionMaker().decide(
        _request(metadata=metadata, evidence=evidence, missing_fields=missing_fields,
                 specs=specs),
        results, terminal=None, uncertainty=(), degraded=degraded)


def test_a_below_floor_decision_on_the_compiled_lane_becomes_a_reason_coded_defer():
    """The K1 row: below-floor DEFERs on the compiled lane, where there have never been any."""
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900)],
                        metadata={LANE_KEY: COMPILED_LANE})

    assert synthesis.decision.outcome == DecisionOutcome.DEFER
    assert synthesis.decision.selected_candidate_id is None
    assert f"{BELOW_FLOOR_REASON}:3900<4500" in synthesis.decision.uncertainty


def test_an_ask_still_shows_the_field_that_was_considered():
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900)],
                        metadata={LANE_KEY: COMPILED_LANE})

    assert len(synthesis.candidates) == 1
    assert synthesis.candidates[0].rank_position == 1


def test_a_below_floor_defer_names_the_unit_that_never_ran_and_the_field_that_never_arrived():
    """Silence has to be ACTIONABLE. "Confidence too low" asks a human to re-derive the run."""
    specs = (ReasonerSpec("core.confidence", "1"), ReasonerSpec("core.risk", "1"))
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900)],
                        metadata={LANE_KEY: COMPILED_LANE}, specs=specs,
                        missing_fields=("deal.owner",))

    assert f"{BELOW_FLOOR_ABSENT_UNIT}:core.risk:not_run" in synthesis.decision.uncertainty
    assert f"{BELOW_FLOOR_MISSING_FIELD}:deal.owner" in synthesis.decision.uncertainty


def test_a_unit_that_ran_and_failed_is_named_with_its_status_not_merely_as_absent():
    """"Skipped by the selector" and "failed" are fixed by different people."""
    specs = (ReasonerSpec("core.confidence", "1"), ReasonerSpec("core.risk", "1"))
    results = [_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900),
               ReasonerResult("core.risk", "1", ResultStatus.FAILED,
                              reason_codes=("reasoner_failure",))]
    synthesis = _decide(results, metadata={LANE_KEY: COMPILED_LANE}, specs=specs)

    assert f"{BELOW_FLOOR_ABSENT_UNIT}:core.risk:failed" in synthesis.decision.uncertainty


def test_when_nothing_is_absent_the_defer_names_the_weakest_rule_11_input():
    """The evidence is present and thin rather than missing, so the axis to strengthen is named."""
    results = [_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900,
                          evidence_coverage_bp=2_500, source_quality_bp=8_000)]
    synthesis = _decide(results, metadata={LANE_KEY: COMPILED_LANE})

    assert f"{BELOW_FLOOR_WEAK_INPUT}:evidence_coverage_bp:2500" in synthesis.decision.uncertainty


def test_a_snapshot_with_no_independent_origins_at_all_says_exactly_that():
    """Nothing in such a snapshot could ever lawfully raise a confidence — that is the one fact."""
    results = [_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900,
                          independent_evidence_groups=0, evidence_coverage_bp=1_000)]
    synthesis = _decide(results, metadata={LANE_KEY: COMPILED_LANE})

    assert (f"{BELOW_FLOOR_WEAK_INPUT}:independent_evidence_groups:0"
            in synthesis.decision.uncertainty)


def test_a_below_floor_defer_never_invents_the_missing_fact():
    """Invariant 8. Every resolver names an ABSENCE this run recorded, and nothing else.

    A DEFER that supplied the fact it lacks would be the exact fabrication the floor exists to
    prevent, and it would be invisible: the card would read like a decision.
    """
    specs = (ReasonerSpec("core.confidence", "1"), ReasonerSpec("core.risk", "1"))
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900)],
                        metadata={LANE_KEY: COMPILED_LANE}, specs=specs,
                        missing_fields=("deal.owner",))
    named = [item for item in synthesis.decision.uncertainty
             if item.startswith(("below_floor_", BELOW_FLOOR_REASON))]

    assert named, "a below-floor DEFER that names nothing is not actionable"
    for item in named:
        assert item.startswith((BELOW_FLOOR_REASON, BELOW_FLOOR_ABSENT_UNIT,
                                BELOW_FLOOR_MISSING_FIELD, BELOW_FLOOR_WEAK_INPUT))
    assert "deal.status" not in " ".join(named), "a present fact was reported as an absence"


def test_the_named_resolvers_are_capped_and_deterministic():
    """`uncertainty` is rendered on the card a human reads; forty absences bury the two that
    matter, and which ones survive must not depend on dict order."""
    specs = (ReasonerSpec("core.confidence", "1"),) + tuple(
        ReasonerSpec(f"core.unit_{index:02d}", "1") for index in range(20))
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=3_900)],
                        metadata={LANE_KEY: COMPILED_LANE}, specs=specs,
                        missing_fields=tuple(f"deal.field_{index}" for index in range(20)))
    named = [item for item in synthesis.decision.uncertainty
             if item.startswith((BELOW_FLOOR_ABSENT_UNIT, BELOW_FLOOR_MISSING_FIELD))]

    assert len(named) == BELOW_FLOOR_RESOLVER_CAP
    assert named == sorted(set(named))


def test_confidence_at_the_floor_still_decides():
    """The floor is a minimum, not a margin — exactly meeting it is meeting it."""
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=4_500)],
                        metadata={LANE_KEY: COMPILED_LANE})

    assert synthesis.decision.outcome == DecisionOutcome.DECISION


def test_the_floor_cannot_manufacture_a_decision_from_a_terminal_run():
    synthesis = DecisionMaker().decide(
        _request(metadata={LANE_KEY: COMPILED_LANE}), [],
        terminal=DecisionOutcome.NO_ACTION, uncertainty=(), degraded=False)

    assert synthesis.decision.outcome == DecisionOutcome.NO_ACTION
    assert not any(item.startswith(BELOW_FLOOR_REASON) for item in synthesis.decision.uncertainty)


def test_a_fabricated_raise_would_have_pushed_a_card_past_the_floor_that_suppressed_it():
    """Why Rule 11 and the floor are one law seen from two ends.

    The same run, twice: the uncited raise the old scan accepted would have carried the decision
    from 3900 to 6000 — over the compiled lane's floor — and shipped as a recommendation. Refused,
    the run says it does not know.
    """
    results = [_completed("legacy.rule", confidence_bp=3_900),
               _completed("legacy.score_gate", confidence_bp=6_000)]

    with pytest.raises(ConfidenceViolation):
        compose_confidence(results, _request(metadata={LANE_KEY: COMPILED_LANE}), False)

    lawful = _decide([results[0]], metadata={LANE_KEY: COMPILED_LANE})
    assert lawful.decision.confidence_bp == 3_900
    assert lawful.decision.outcome == DecisionOutcome.DEFER


def test_the_synthesis_carries_the_receipt_for_the_number_it_decided_on():
    """A lawful raise and an unlawful one are indistinguishable once only the integer survives."""
    synthesis = _decide([_completed(CONFIDENCE_AUTHORITY, confidence_bp=8_000)])

    assert synthesis.confidence is not None
    assert synthesis.confidence.confidence_bp == synthesis.decision.confidence_bp
    assert synthesis.confidence.receipts


# ── the measurement · a floor nothing trips and a floor everything trips are both wrong ──────

def _population_snapshot(present: int, fact_confidence_bp: int, src_count: int, groups: int):
    """One realistic compiled-lane run: N of 6 declared fields present, each stating its own
    confidence and source count, backed by N independent evidence groups."""
    fields = tuple(f"deal.field_{index}" for index in range(6))
    facts = {field: {"value": "open", "confidence_bp": fact_confidence_bp,
                     "src_count": src_count} for field in fields[:present]}
    evidence = tuple(EvidenceRef(evidence_id=f"ev_{index}", field=fields[0], value="open",
                                 confidence_bp=fact_confidence_bp,
                                 independence_group=f"origin_{index}")
                     for index in range(groups)) if present else ()
    capability = CapabilityManifest(
        capability_id="expertise.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal", goal=Goal("restore_momentum", "Restore momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1.0.0"),),
        plays=(PlayDefinition(play_id="restore_momentum", version="1", label="Restore",
                              steps=("Prepare a grounded draft",), impact_bp=6_000,
                              success_probability_bp=6_000, effort_bp=2_000, risk_bp=1_000),),
        required_fields=fields, policies=(), metadata={LANE_KEY: COMPILED_LANE})
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="selector.v1", facts=facts, evidence=evidence,
        missing_fields=tuple(fields[present:]))
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


def test_the_floor_is_tripped_by_some_of_a_real_population_and_not_by_all_of_it():
    """MEASURED, not asserted — and measured against the unit that produces the number.

    `core.confidence` is run over a grid of realistic snapshots (how much of the declared picture
    arrived, how confident each fact says it is, how many sources saw it, how many independent
    origins back the run) and every result is taken through the real `DecisionMaker` on the
    compiled lane. A floor nothing trips is decoration; a floor everything trips is an outage.
    The full grid and its distribution live in `scripts/confidence_floor_distribution.py`.
    """
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    unit = ConfidenceReasoner()
    maker = DecisionMaker()
    outcomes: list[DecisionOutcome] = []
    confidences: list[int] = []
    for present in range(0, 7):
        for fact_confidence_bp in (1_500, 4_500, 7_500, 9_000):
            for src_count in (1, 3):
                for groups in (0, 2):
                    request = _population_snapshot(present, fact_confidence_bp, src_count, groups)
                    result = unit.evaluate(request, {})
                    synthesis = maker.decide(request, [result], terminal=None, uncertainty=(),
                                             degraded=False)
                    outcomes.append(synthesis.decision.outcome)
                    confidences.append(synthesis.decision.confidence_bp)

    below = [item for item in outcomes if item == DecisionOutcome.DEFER]
    assert below, "the floor never fires on the compiled lane — this is the defect, restored"
    assert len(below) < len(outcomes), "the floor suppresses everything — that is an outage"
    assert min(confidences) < DEFAULT_CONFIDENCE_FLOOR_BP <= max(confidences)
    assert len(set(confidences)) > 20, "a floor applied to one constant is not a measurement"


def test_every_below_floor_defer_in_that_population_names_what_would_resolve_it():
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    unit = ConfidenceReasoner()
    maker = DecisionMaker()
    deferred = 0
    for present in range(0, 7):
        for fact_confidence_bp in (1_500, 4_500, 9_000):
            request = _population_snapshot(present, fact_confidence_bp, 1, 2)
            synthesis = maker.decide(request, [unit.evaluate(request, {})], terminal=None,
                                     uncertainty=(), degraded=False)
            if synthesis.decision.outcome != DecisionOutcome.DEFER:
                continue
            deferred += 1
            assert any(item.startswith("below_floor_")
                       for item in synthesis.decision.uncertainty)
    assert deferred


def test_a_completed_authority_ends_the_scan_even_when_it_publishes_no_number():
    """The authority's silence is still authority: nothing downstream of it re-opens the metric.

    This is the boundary that makes appending a unit safe. When the owner publishes, the number is
    settled and later units are observations; when the owner completes and says nothing, the belief
    the run had reached at that point is what stands — a unit scheduled after it does not get to
    lower (or, with evidence, lift) a value the owner has already declined to revise.
    """
    results = [_completed("gate", confidence_bp=7_000),
               ReasonerResult(CONFIDENCE_AUTHORITY, "1", ResultStatus.COMPLETED, matched=True),
               _completed("core.planning", confidence_bp=2_000)]

    assert compose_confidence(results, _request(), False).confidence_bp == 7_000


# ── the seam that made the number a constant · Layer 2's vector reaching the composition ─────
#
# MEASURED, on the K1 pilot, before any of this existed: `core.confidence` published
# {"confidence_bp": 6250, "completeness_bp": 10000, "corroboration_bp": 5000,
#  "source_quality_bp": 5000, "evidence_coverage_bp": 2500, "independent_evidence_groups": 1}
# on 60 of 60 decisions — one distinct row in `select output->'metrics', count(*)`. Not a
# distribution that happened to be narrow: the same six numbers, by construction. The compiled
# lane's manifest declares `required_fields: []`, so completeness takes its "asked for nothing and
# got all of it" branch, no fact is inspected at all and both fact-derived axes fall to the neutral
# midpoint; and the projection mints every situation fact into ONE independence group, so the
# fourth axis is a constant 2,500 too. 40x5000 + 30x10000 + 20x5000 + 10x2500 = 6,250, always.
#
# A confidence that cannot move cannot trip a floor. Law 3 says a floor that never fires is not a
# floor, so this is the defect, and it is a SEAM defect: Layer 2 had already published the varying
# reading into the same snapshot, one axis at a time, and nothing read it.

def _axis_fact(value_bp: int, axis: str) -> dict:
    """A `situation.confidence.<axis>` fact exactly as `situation_projection._fact` mints it."""
    return {"value": {"value_bp": value_bp, "axis": axis}, "source": "l2.situation",
            "projection": "l4-situation-projection.v1", "kind": "confidence_axis",
            "reading": f"Layer 2's {axis} confidence axis, in basis points"}


def _situation_request(axes: dict[str, int], *, required=(), facts=None) -> ReasoningRequest:
    """A compiled-lane request shaped like the one the K1 pilot actually produces: no declared
    required fields, one independence group, and Layer 2's axes projected as snapshot facts."""
    from genios_engine.reason.reasoners.confidence import SITUATION_CONFIDENCE_PREFIX

    # One non-confidence situation fact, always, so the evidence ref has something in the frozen
    # context to resolve against even when no axis is projected at all — which is itself one of
    # the cases under test.
    body = dict(facts if facts is not None else {})
    body["situation.importance"] = {"value": {"importance_bp": 6_000}, "source": "l2.situation",
                                    "kind": "importance", "reading": "the composed importance"}
    for axis, value_bp in axes.items():
        body[f"{SITUATION_CONFIDENCE_PREFIX}{axis}"] = _axis_fact(value_bp, axis)
    capability = CapabilityManifest(
        capability_id="expertise.account_admin", version="1.0.0", domain="admin",
        root_entity_type="situation", goal=Goal("resolve", "Resolve the situation"),
        reasoners=(ReasonerSpec("core.confidence", "1.0.0"),),
        plays=(PlayDefinition(play_id="resolve", version="1", label="Resolve",
                              steps=("Prepare a grounded draft",), impact_bp=6_000,
                              success_probability_bp=6_000, effort_bp=2_000, risk_bp=1_000),),
        required_fields=tuple(required), policies=(), metadata={LANE_KEY: COMPILED_LANE})
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="sit_1", root_entity_type="situation",
        evaluation_time=NOW, selector_version="selector.v1", facts=body,
        evidence=(EvidenceRef(evidence_id="ev_1", field="situation.importance",
                              value=body["situation.importance"]["value"], confidence_bp=5_000,
                              independence_group="l2:situation:sit_1"),))
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="situation.refreshed",
                            config_snapshot_id="cfg_1")


def _confidence_of(request: ReasoningRequest) -> int:
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    return ConfidenceReasoner().evaluate(request, {}).metrics["confidence_bp"]


def test_the_projected_prefix_is_the_one_the_projection_actually_mints():
    """The seam is two strings in two modules that may never be imported into one another.

    `reasoners/confidence.py` spells `situation.confidence.` itself because importing the
    projection would close an import cycle through the orchestrator. That is a legitimate reason to
    duplicate a constant and an illegitimate reason to let the two drift: a rename on either side
    would leave this unit reading a namespace nobody writes, silently, and the only symptom would
    be the constant confidence coming back.
    """
    from genios_engine.reason.adapters.situation_projection import CONFIDENCE_PREFIX
    from genios_engine.reason.reasoners.confidence import SITUATION_CONFIDENCE_PREFIX

    assert SITUATION_CONFIDENCE_PREFIX == CONFIDENCE_PREFIX


def test_layer_2s_axes_move_the_number_that_four_constant_axes_could_not():
    """The defect, restored as a measurement: same manifest shape, different situations.

    Every request here is the compiled lane's own shape — no declared required fields, one
    independence group — so all four of this unit's own axes are pinned to the constants that
    produced 6,250 sixty times. If the number still cannot move, Layer 2's vector is not reaching
    the composition.
    """
    readings = [_confidence_of(_situation_request(
        {"evidence": evidence_bp, "freshness": 10_000, "consistency": 10_000,
         "identity": 10_000}))
        for evidence_bp in (800, 2_500, 3_300, 4_100, 5_800, 7_400, 10_000)]

    assert readings[0] == 800, "Layer 2's weakest axis is not reaching the confidence"
    assert len(set(readings)) > 1, "the composition still reads nothing that varies"
    # BOUNDED ABOVE BY THE BLEND, and that is Rule 11 rather than a shortfall. Every projected
    # axis carries one independence group, so a strong Layer 2 reading names no evidence that
    # could license a raise; it can only decline to lower. The spread therefore runs from 0 up to
    # the four-axis blend and stops there — the last two readings are both 6,250 because 7,400 and
    # 10,000 are both above it. A spread bought by letting an uncited raise through would look
    # earned and would not be.
    assert readings == sorted(readings)
    assert readings[-1] == readings[-2] == 6_250


def test_the_ceiling_is_the_weakest_axis_and_never_the_average_of_them():
    """`context/situations.py`: *"averaging lets one strong dimension hide a fatal one: perfect
    evidence about an entity we cannot identify is not 60% confidence, it is unusable."*"""
    unidentifiable = _confidence_of(_situation_request(
        {"evidence": 10_000, "freshness": 10_000, "consistency": 10_000, "identity": 500}))

    assert unidentifiable == 500


def test_the_situation_ceiling_can_only_lower_and_never_raises_past_the_blend():
    """Rule 11, held by construction rather than by a check.

    Every projected axis carries the same independence group (`l2:situation:<id>`), so Layer 2's
    reading could never license a raise — and this seam never asks for one. A perfect vector leaves
    the four-axis blend exactly where it was; it does not lift it toward the perfect reading.
    """
    perfect = _situation_request({axis: 10_000 for axis in
                                 ("evidence", "freshness", "consistency", "identity", "analytic")})
    none_at_all = _situation_request({})

    assert _confidence_of(perfect) == _confidence_of(none_at_all) == 6_250


def test_an_unassessed_axis_is_excluded_from_the_minimum_and_never_scored_as_zero():
    """The -1 sentinel exists so "no comparison was made" stops reading as "the comparative
    evidence is bad". A composition that let it into the minimum would undo that at the seam —
    and it is the ONE axis most situations cannot assess, so a zero here would silence everything.
    """
    from genios_engine.contracts.situation_evidence import AXIS_UNKNOWN_BP

    with_sentinel = _confidence_of(_situation_request(
        {"evidence": 6_000, "freshness": 10_000, "consistency": 10_000, "identity": 10_000,
         "analytic": AXIS_UNKNOWN_BP}))
    without_it = _confidence_of(_situation_request(
        {"evidence": 6_000, "freshness": 10_000, "consistency": 10_000, "identity": 10_000}))

    assert with_sentinel == without_it == 6_000


def test_the_analytic_axis_binds_here_though_layer_2_keeps_it_out_of_its_own_overall():
    """L2 excludes `analytic` from `overall` because *"a five-member cohort does not make the
    situation less true; it makes the IMPORTANCE that leaned on it less certain."* Layer 4 RANKS BY
    that importance, so at this layer the thin cohort is exactly a reason to trust the decision
    less. Two layers, two different claims, and both readings are right about their own claim.
    """
    five_member_cohort = _confidence_of(_situation_request(
        {"evidence": 10_000, "freshness": 10_000, "consistency": 10_000, "identity": 10_000,
         "analytic": 2_000}))
    two_hundred_member_cohort = _confidence_of(_situation_request(
        {"evidence": 10_000, "freshness": 10_000, "consistency": 10_000, "identity": 10_000,
         "analytic": 9_000}))

    assert five_member_cohort == 2_000
    assert two_hundred_member_cohort == 6_250      # the blend, i.e. the ceiling did not bind


def test_the_coverage_axis_is_deliberately_not_read_here():
    """L2 keeps `coverage` out of `overall` and says why: *"Folding coverage into overall would
    make absence read as doubt."* Reading it here would reverse that one layer up, and it would
    double-count — `CoverageCompletenessPlugin` already answers completeness against THIS
    capability's declared fields. The K1 pilot publishes `coverage: 0` on every situation, so a
    seam that read it would have silenced all sixty for a reason Layer 2 had already rejected.
    """
    from genios_engine.reason.reasoners.confidence import SITUATION_TRUST_AXES

    assert "coverage" not in SITUATION_TRUST_AXES
    assert _confidence_of(_situation_request(
        {"evidence": 9_000, "freshness": 10_000, "consistency": 10_000, "identity": 10_000,
         "coverage": 0})) == 6_250


def test_a_bound_ceiling_carries_a_receipt_naming_the_axis_it_was_taken_from():
    """No claim without a receipt. A ceiling that says only "3,300" makes a reader argue with a
    number; one that names `evidence` tells them what would move it. And the code appears only
    when the ceiling actually bound — a reason code on every run says nothing about any run.
    """
    from genios_engine.reason.reasoners.confidence import (
        CONFIDENCE_REASON,
        CONFIDENCE_SITUATION_CEILING_REASON,
        SITUATION_TRUST_WEAKEST_PREFIX,
        ConfidenceReasoner,
    )

    bound = ConfidenceReasoner().evaluate(_situation_request(
        {"evidence": 3_300, "freshness": 10_000, "consistency": 10_000, "identity": 10_000}), {})
    idle = ConfidenceReasoner().evaluate(_situation_request(
        {"evidence": 9_900, "freshness": 10_000, "consistency": 10_000, "identity": 10_000}), {})

    assert CONFIDENCE_SITUATION_CEILING_REASON in bound.reason_codes
    assert f"{SITUATION_TRUST_WEAKEST_PREFIX}evidence" in bound.reason_codes
    assert idle.reason_codes == (CONFIDENCE_REASON,)
    assert bound.metrics["situation_trust_bp"] == 3_300
    assert bound.metrics["situation_trust_axis_count"] == 4


def test_a_snapshot_with_no_situation_facts_publishes_exactly_the_metrics_it_always_did():
    """Purely additive, byte-for-byte. Every legacy audit row was written by this unit on a
    snapshot with no `situation.confidence.*` fact, and a replay verifier re-runs the unit and
    compares. A new key appearing on those runs would orphan every one of them.
    """
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    result = ConfidenceReasoner().evaluate(_request(), {})

    assert set(result.metrics) == {"confidence_bp", "completeness_bp", "corroboration_bp",
                                   "source_quality_bp", "evidence_coverage_bp",
                                   "independent_evidence_groups"}


def test_the_layer_2_ceiling_is_what_makes_the_floor_fire_on_the_compiled_lane():
    """Law 3, end to end and through the real `DecisionMaker`: the thin situation defers with a
    reason code, the well-evidenced one decides, and the floor is neither decoration nor an outage.
    """
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    unit, maker = ConfidenceReasoner(), DecisionMaker()
    outcomes = {}
    for label, evidence_bp in (("thin", 3_300), ("strong", 9_900)):
        request = _situation_request({"evidence": evidence_bp, "freshness": 10_000,
                                      "consistency": 10_000, "identity": 10_000})
        outcomes[label] = maker.decide(request, [unit.evaluate(request, {})], terminal=None,
                                       uncertainty=(), degraded=False).decision

    assert outcomes["thin"].outcome == DecisionOutcome.DEFER
    assert any(item.startswith(BELOW_FLOOR_REASON) for item in outcomes["thin"].uncertainty)
    assert outcomes["strong"].outcome != DecisionOutcome.DEFER
    assert outcomes["strong"].confidence_bp == 6_250


def test_the_degraded_cap_still_binds_over_a_situation_ceiling():
    """PRESERVED: a decision reached with a blind spot must never present itself as well-evidenced
    as one reached with every input intact — including when Layer 2's own reading was excellent.
    """
    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner

    request = _situation_request({axis: 10_000 for axis in
                                  ("evidence", "freshness", "consistency", "identity")})
    result = ConfidenceReasoner().evaluate(request, {})

    assert compose_confidence([result], request, True).confidence_bp == 5_000
