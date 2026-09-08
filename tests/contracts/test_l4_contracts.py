"""K0 · wave Z0 — the Layer 4 v2 contract extensions.

Doc 07's gate, in one file: *round-trip of old shapes · topology green · `advisory` unfalsifiable ·
weights validated to 10000 · V-3 rejects a mismatched bundle AT CONSTRUCTION.* (Topology is
`tests/test_layer_topology.py`; everything else is here.)

WHY THE GOLDEN HASHES ARE HARDCODED. Four of these constants were computed by running
`git show HEAD:genios_engine/contracts/reasoning.py` — the file as it stood before this wave —
against the same object graph the fixtures below build. That is the only form of "old shapes still
construct" that means anything: a round-trip through the NEW code proves the new code is
self-consistent, and would keep passing if every stored hash in `reasoning_runs` had been
invalidated on the way. `reasoning_capability_snapshots` and `reasoning_runs` hold these strings
today; a diff here is a replay that fails on live data, not a test that needs updating.

NO DATABASE. Every test in this file is pure, so the gate's "0 skips" is unconditional rather than
a property of whoever set GENIOS_TEST_DATABASE_URL. The `l4_activation` table, its reader/writer and
its admin routes are exercised in `tests/test_l4_pilot_activation.py`, which needs Postgres.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from genios_engine.contracts.reasoning import (
    BUNDLE_FIELD_CAPS,
    CONFIDENCE_VECTOR_KEYS,
    CRITIQUE_VERDICTS,
    DO_NOTHING_SOURCES,
    EXTERNAL_CANDIDATE_KINDS,
    FORMULA_UTILITY_COMPONENT,
    RANKING_WEIGHTS_V1,
    RANKING_WEIGHTS_V1_SCALE,
    RANKING_WEIGHTS_V1_VERSION,
    RANKING_WEIGHTS_V2,
    RANKING_WEIGHTS_V2_SCALE,
    RANKING_WEIGHTS_V2_VERSION,
    TEMPLATE_FALLBACK,
    UTILITY_COMPONENTS,
    BriefEntry,
    BriefRanking,
    CandidateAdjustment,
    CandidateDisposition,
    CapabilityManifest,
    CritiqueVerdict,
    DecisionCandidate,
    DecisionOutcome,
    ExternalCandidate,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasonerResult,
    ReasoningBundle,
    ReasoningDecision,
    ResultStatus,
    RevalidatedModel,
    bare_numbers,
    placeholders,
    ranking_weight_scale,
    require_confidence_vector,
    require_do_nothing,
    require_generation,
    require_ranking_weights,
    unit_ref,
)

T = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

# ── the golden hashes, computed against the pre-wave file. See the module docstring. ──────────
HEAD_RESULT_HASH = "91f6e2c08dbdc1a5f82b4d072adde49c62f9a8d3c17404bc664d57c3c34ec9e7"
HEAD_CAPABILITY_ID = "cap_99b502723f2e2401d24f5faced5c9a7f2e9845140b9d5c770930c396ee37865b"
HEAD_CANDIDATE_ID = "cand_fd18bfa200facb72569e86a7bc96674fb972c157bc350b9355c8aba370670f81"
HEAD_DECISION_HASH = "3f1a218ac4bf7ee74483083d8b4de4f360d1595796ac5ae4c67bea1bfc7139f4"


# ── fixtures: the OLD shapes, spelled exactly as they were before this wave ───────────────────

def old_finding() -> Finding:
    return Finding(finding_id="f_1", kind="momentum_drop", matched=True,
                   metrics={"gap_bp": 2_500}, evidence_ids=("ev_1",),
                   reason_codes=("cooling",))


def old_result(finding: Finding | None = None) -> ReasonerResult:
    return ReasonerResult(reasoner_id="core.risk", reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=True,
                          metrics={"risk_bp": 4_000}, findings=(finding or old_finding(),),
                          evidence_ids=("ev_1",))


def old_capability(**overrides) -> CapabilityManifest:
    kwargs = dict(
        capability_id="sales.cooling", version="1", domain="sales", root_entity_type="deal",
        goal=Goal("g", "Restore momentum"),
        reasoners=(ReasonerSpec(reasoner_id="core.constraint", version="1"),),
        plays=(PlayDefinition(play_id="play.outreach", version="1", label="Outreach",
                              steps=("send",)),),
    )
    kwargs.update(overrides)
    return CapabilityManifest(**kwargs)


def old_candidate(**overrides) -> DecisionCandidate:
    kwargs = dict(play_id="play.outreach", play_version="1",
                  disposition=CandidateDisposition.ELIGIBLE, utility_bp=6_000,
                  confidence_bp=7_000,
                  score_components={"impact": 5_000, FORMULA_UTILITY_COMPONENT: 5_500},
                  rank_position=1, evidence_ids=("ev_1",))
    kwargs.update(overrides)
    return DecisionCandidate(**kwargs)


def old_decision(**overrides) -> ReasoningDecision:
    candidate = overrides.pop("candidate", None) or old_candidate()
    kwargs = dict(outcome=DecisionOutcome.DECISION, capability_id="sales.cooling",
                  capability_version="1", context_snapshot_id="ctx_1",
                  candidates=(candidate,), selected_candidate_id=candidate.candidate_id,
                  confidence_bp=7_000, uncertainty=(),
                  do_nothing_consequence="It stays unresolved.", expires_at=T)
    kwargs.update(overrides)
    return ReasoningDecision(**kwargs)


def bundle_for(decision: ReasoningDecision, **overrides) -> ReasoningBundle:
    kwargs = dict(headline="RENEWAL AT RISK",
                  situation_summary="The renewal window is closing and the committee is quiet.",
                  why_it_matters="{arr_exposed_bp} of ARR is exposed.",
                  root_cause="Engagement dropped after the pricing thread.",
                  recommendation_rationale="Outreach beats the discount play on the cost axis.",
                  expected_effect="Doing nothing costs {do_nothing_cost} a day.",
                  evidence_refs=("ev_1",),
                  numbers_used={"arr_exposed_bp": 8_400, "do_nothing_cost": 2_800},
                  generation="llm:claude-opus-5@2026-05-01")
    kwargs.update(overrides)
    return ReasoningBundle.for_decision(decision, **kwargs)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# K0 (1) · ROUND-TRIP OF OLD SHAPES — additive means additive
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_pre_wave_finding_hashes_to_exactly_what_it_hashed_to_before():
    """`Finding.value_bp` is a NEW FIELD ON A HASHED OBJECT, which is the dangerous kind.

    Without `Finding.to_semantic_dict` omitting it when unmeasured, `canonicalize` walks the
    dataclass fields, `"value_bp": null` enters the canonical JSON of every finding ever emitted,
    and that propagates through `ReasonerResult.semantic_hash` into `StepTrace.output_hash` — so
    every trace in `reasoning_runs` would fail replay verification against a run that computed the
    identical result. The golden string is the pre-wave answer.
    """
    assert old_result().semantic_hash == HEAD_RESULT_HASH


def test_pre_wave_capabilities_candidates_and_decisions_keep_their_content_addresses():
    """The other three stored addresses. `reasoning_capability_snapshots` is keyed on the first."""
    assert old_capability().capability_snapshot_id == HEAD_CAPABILITY_ID
    assert old_candidate().candidate_id == HEAD_CANDIDATE_ID
    assert old_decision().semantic_hash == HEAD_DECISION_HASH
    assert old_decision().decision_id == f"decision_{HEAD_DECISION_HASH}"


def test_every_new_decision_field_is_absent_from_the_hash_until_it_carries_something():
    """Defaults are not enough on their own: a defaulted field that still enters the semantic dict
    changes the hash of every old object. Each of the three must be conditionally included."""
    plain = old_decision()
    assert "confidence_vector" not in plain.to_semantic_dict()
    assert "ranking_weights_version" not in plain.to_semantic_dict()
    assert "do_nothing" not in plain.to_semantic_dict()
    assert plain.confidence_vector == {} and plain.do_nothing == {}
    assert plain.ranking_weights_version is None and plain.reasoning_bundle is None


def test_carrying_the_new_content_does_change_the_hash():
    """The complement, and it is the half that makes the test above meaningful rather than vacuous:
    'omitted when empty' must not mean 'ignored when present'."""
    assert old_decision(confidence_vector={"corroboration_bp": 6_000}).semantic_hash != \
        HEAD_DECISION_HASH
    assert old_decision(ranking_weights_version=RANKING_WEIGHTS_V2_VERSION).semantic_hash != \
        HEAD_DECISION_HASH
    assert old_decision(do_nothing={"cost_bp": 1, "horizon": None, "statement": "s",
                                   "source": "computed"}).semantic_hash != HEAD_DECISION_HASH


# ═════════════════════════════════════════════════════════════════════════════════════════════
# K0 (2) · V-3 — THE BUNDLE'S ACTION IS THE DECISION'S ACTION, AT CONSTRUCTION
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_bundle_whose_action_contradicts_its_decision_cannot_be_attached():
    """Law 2, verbatim: *a bundle whose action does not id-match the decision is a CONSTRUCTOR
    ERROR, not a review nit.* Raised by `ReasoningDecision.__post_init__`, so no publication path
    can reach a contradicting pair by skipping a later validation pass."""
    decision = old_decision()
    liar = ReasoningBundle(decision_id=decision.decision_id, action_id="play.discount",
                           headline="H", situation_summary="S", why_it_matters="W",
                           root_cause="R", recommendation_rationale="RR", expected_effect="E",
                           evidence_refs=("ev_1",))
    with pytest.raises(ValueError, match="does not match the decision's action"):
        decision.with_bundle(liar)


def test_a_bundle_minted_for_another_decision_cannot_be_moved_onto_this_one():
    """The second half of V-3. Same action id, different decision — a regenerated narrative
    attached to a decision that has since been recomputed."""
    first = old_decision()
    second = old_decision(confidence_bp=6_000)
    assert first.decision_id != second.decision_id
    with pytest.raises(ValueError, match="belongs to another decision"):
        second.with_bundle(bundle_for(first))


def test_for_decision_derives_both_ids_and_refuses_to_be_told_them():
    """A caller that never gets to type either id cannot violate V-3 by typing one wrong. Supplying
    one anyway is REFUSED rather than silently overruled — a caller who believes it is setting the
    action id will eventually be right and unheard."""
    decision = old_decision()
    bundle = bundle_for(decision)
    assert bundle.action_id == decision.action_id == "play.outreach"
    assert bundle.decision_id == decision.decision_id
    with pytest.raises(ValueError, match="derived from the decision"):
        bundle_for(decision, action_id="play.discount")


def test_a_decision_that_chose_nothing_has_no_action_and_gets_no_narrative():
    """Doc 05 §7: bundles are generated only for published decisions that chose something. A DEFER
    has no action for a narrative to be *about*, so narrating one would mean inventing an action
    id — the one thing Law 2 exists to prevent. Silence stays reason-coded and unnarrated."""
    deferred = ReasoningDecision(
        outcome=DecisionOutcome.DEFER, capability_id="sales.cooling", capability_version="1",
        context_snapshot_id="ctx_1", candidates=(), selected_candidate_id=None,
        confidence_bp=2_000, uncertainty=("thin_evidence",),
        do_nothing_consequence="It stays unresolved.", expires_at=T)
    assert deferred.action_id is None
    with pytest.raises(ValueError, match="committed to no action"):
        bundle_for(deferred)


def test_the_action_id_is_the_play_not_the_candidate_address():
    """`candidate_id` is a content address over scores and checks, so it changes when a re-run
    scores the same action differently. An action id that changes when nothing about the action
    changed is not an action id — and a bundle keyed on one would contradict its decision after a
    rescore that chose the identical play."""
    decision = old_decision()
    rescored = old_decision(candidate=old_candidate(utility_bp=6_100))
    assert decision.action_id == rescored.action_id == "play.outreach"
    assert decision.selected_candidate_id != rescored.selected_candidate_id


def test_attaching_a_narrative_does_not_change_the_decision_it_narrates():
    """The decision is FIXED before any narrative exists (Law 2), and that is expressed in the hash:
    the bundle is excluded from `to_semantic_dict` unconditionally. If it were not, the bundle would
    change the `decision_id` it names, and no bundle could ever be attached at all."""
    decision = old_decision()
    narrated = decision.with_bundle(bundle_for(decision))
    assert narrated.decision_id == decision.decision_id == f"decision_{HEAD_DECISION_HASH}"
    assert narrated.reasoning_bundle is not None
    assert "reasoning_bundle" not in narrated.to_semantic_dict()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# K0 (3) · numbers_used IS THE MECHANISM — V-4, V-5, V-7 and the substitution
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_model_that_types_a_digit_is_refused_and_told_which_digits():
    """V-4. There is no way to tell from a finished string whether `84,000` was computed or
    invented, so the string is refused: numbers are TEMPLATED, never generated."""
    decision = old_decision()
    with pytest.raises(ValueError, match=r"bare number"):
        bundle_for(decision, why_it_matters="$84,000 of ARR is exposed.")
    assert bare_numbers("$84,000 exposed") == ("84", "000")
    assert bare_numbers("{arr_exposed_bp} exposed") == ()


def test_a_placeholder_with_no_computed_value_is_refused():
    """V-5. A placeholder nothing resolves renders as a literal brace on a customer's card."""
    with pytest.raises(ValueError, match=r"no entry in numbers_used"):
        bundle_for(old_decision(), expected_effect="Doing nothing costs {mystery} a day.")


def test_a_computed_number_no_sentence_shows_is_refused_too():
    """The reverse direction, which V-5 alone does not cover: a number computed and never shown is
    either a missing sentence or a stale substitution, and the record cannot say which."""
    with pytest.raises(ValueError, match="which no prose field references"):
        bundle_for(old_decision(),
                   numbers_used={"arr_exposed_bp": 1, "do_nothing_cost": 2, "orphan": 3})


@pytest.mark.parametrize("prose", ["{ do_nothing_cost }", "{Do_Nothing_Cost}", "{do_nothing_cost"])
def test_a_malformed_placeholder_is_refused_rather_than_rendered(prose):
    """`{ cost }` is not a placeholder under the grammar, so treating it as prose would let V-5 pass
    over a number that never resolves — and rendering it would ship a brace to a card."""
    with pytest.raises(ValueError, match="malformed placeholder"):
        bundle_for(old_decision(), expected_effect=f"Doing nothing costs {prose} a day.")


def test_render_substitutes_the_computed_values_and_only_those():
    """The mechanism itself: substitution happens in CODE, after generation, over a mapping the
    deterministic half filled. There is no path by which a model's digits reach a card."""
    rendered = bundle_for(old_decision()).render()
    assert rendered["why_it_matters"] == "8400 of ARR is exposed."
    assert rendered["expected_effect"] == "Doing nothing costs 2800 a day."
    assert rendered["alternatives_narrative"] is None


def test_numbers_used_refuses_a_float_and_an_unreferenceable_key():
    """Integer basis points and whole units, per the doctrine — a float here is a rounded number on
    a customer's card. A key that is not a legal placeholder name is a value nothing can reference."""
    with pytest.raises(TypeError, match="must be an integer"):
        bundle_for(old_decision(), numbers_used={"arr_exposed_bp": 8_400,
                                                 "do_nothing_cost": 2_800.0})
    with pytest.raises(ValueError, match="not a legal placeholder name"):
        bundle_for(old_decision(), why_it_matters="ARR is exposed.",
                   expected_effect="Nothing changes.", numbers_used={"Cost": 1})


@pytest.mark.parametrize("field_name,cap", sorted(BUNDLE_FIELD_CAPS.items()))
def test_every_prose_field_has_an_enforced_cap(field_name, cap):
    """V-7, walked, so a field added later is covered the day it is written. `headline` is doc 05's
    own 90 and is the one a card title depends on."""
    with pytest.raises(ValueError, match=f"cap is {cap}"):
        bundle_for(old_decision(), **{field_name: "a" * (cap + 1)})
    assert BUNDLE_FIELD_CAPS["headline"] == 90


def test_a_required_prose_field_cannot_be_empty_and_alternatives_may_be_absent():
    """R-3 is an on-demand site (card expand), so a bundle without an alternatives narrative is a
    complete bundle rather than a degraded one. The other six are the founder's card."""
    with pytest.raises(ValueError, match="root_cause is required"):
        bundle_for(old_decision(), root_cause="   ")
    assert bundle_for(old_decision()).alternatives_narrative is None


def test_a_narrative_grounded_in_nothing_is_refused():
    """V-1's structural half. The per-claim check needs the situation and belongs to Z4's gauntlet;
    'grounded by nothing at all' is checkable from the object and so is checked by the object."""
    with pytest.raises(ValueError, match="at least one evidence_ref or citation"):
        bundle_for(old_decision(), evidence_refs=())


@pytest.mark.parametrize("generation,ok", [
    ("llm:claude-opus-5@2026-05-01", True),
    (TEMPLATE_FALLBACK, True),
    ("llm:claude-opus-5", False),
    ("template-fallback", False),
    ("gpt", False),
])
def test_generation_is_a_closed_vocabulary(generation, ok):
    """K4 measures the `template_fallback` RATE, and a rate over a free-text column is a rate over
    whatever strings happened to be typed."""
    if ok:
        assert require_generation(generation) == generation
    else:
        with pytest.raises(ValueError, match="template_fallback"):
            require_generation(generation)


def test_the_bundle_hash_is_verified_when_supplied():
    """A bundle rehydrated from a store cannot come back with prose that does not match its hash."""
    bundle = bundle_for(old_decision())
    assert bundle.bundle_hash == bundle.semantic_hash and len(bundle.bundle_hash) == 64
    with pytest.raises(ValueError, match="bundle_hash does not match"):
        ReasoningBundle(decision_id=bundle.decision_id, action_id=bundle.action_id,
                        headline="A DIFFERENT HEADLINE", situation_summary=bundle.situation_summary,
                        why_it_matters=bundle.why_it_matters, root_cause=bundle.root_cause,
                        recommendation_rationale=bundle.recommendation_rationale,
                        expected_effect=bundle.expected_effect,
                        evidence_refs=bundle.evidence_refs, numbers_used=dict(bundle.numbers_used),
                        generation=bundle.generation, bundle_hash=bundle.bundle_hash)


def test_placeholders_reports_first_occurrence_order_without_duplicates():
    assert placeholders("{a} then {b} then {a}") == ("a", "b")


# ═════════════════════════════════════════════════════════════════════════════════════════════
# K0 (4) · THE WEIGHTS — six keys, 10000, integer bp, versioned
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_six_weights_are_the_plans_numbers_and_importance_is_the_largest():
    """G-06. importance 2500 is the point of the whole wave: L1 spent ALG-17 computing a number and
    L2 spent H5 composing it, and `importance_bp` has had zero readers in `reason/`."""
    assert dict(RANKING_WEIGHTS_V2) == {"importance": 2_500, "impact": 2_000, "urgency": 2_000,
                                        "success": 1_500, "effort": 1_000, "risk": 1_000}
    assert sum(RANKING_WEIGHTS_V2.values()) == 10_000
    assert max(RANKING_WEIGHTS_V2, key=RANKING_WEIGHTS_V2.get) == "importance"
    assert tuple(RANKING_WEIGHTS_V2) == UTILITY_COMPONENTS


def test_both_weight_shapes_construct_and_report_their_own_version_and_scale():
    """The legacy five (percentage points, 100) and G-06's six (basis points, 10000), told apart by
    KEY SET. Deriving the version from the keys is what keeps every old capability's snapshot id."""
    legacy = old_capability()
    assert legacy.ranking_weights_version == RANKING_WEIGHTS_V1_VERSION
    assert legacy.ranking_weight_scale == RANKING_WEIGHTS_V1_SCALE == 100
    modern = old_capability(ranking_weights=dict(RANKING_WEIGHTS_V2))
    assert modern.ranking_weights_version == RANKING_WEIGHTS_V2_VERSION
    assert modern.ranking_weight_scale == RANKING_WEIGHTS_V2_SCALE == 10_000
    assert ranking_weight_scale(RANKING_WEIGHTS_V1) == 100


def test_six_weights_that_do_not_sum_to_ten_thousand_are_refused_at_construction():
    """The constructor check doc 04 names under FAILURE MODES: *weights drifting out of 10000*."""
    drifted = dict(RANKING_WEIGHTS_V2) | {"importance": 2_501}
    with pytest.raises(ValueError, match="sum to 10000"):
        old_capability(ranking_weights=drifted)


def test_the_legacy_five_still_have_to_sum_to_one_hundred():
    """The pre-existing law, unweakened — the whole point of 'additive'."""
    with pytest.raises(ValueError, match="sum to 100"):
        old_capability(ranking_weights=dict(RANKING_WEIGHTS_V1) | {"impact": 50})


@pytest.mark.parametrize("weights", [
    {"impact": 35, "success": 30, "urgency": 20, "effort": 10},                  # four
    dict(RANKING_WEIGHTS_V2) | {"novelty": 0},                                   # seven
    {"importance": 2_500, "impact": 2_000, "urgency": 2_000, "success": 1_500,
     "effort": 1_000, "danger": 1_000},                                          # six, misnamed
])
def test_a_key_set_that_is_neither_shape_is_refused(weights):
    with pytest.raises(ValueError, match="non-negative integer weights"):
        require_ranking_weights(weights)


def test_a_float_weight_is_refused_in_both_shapes():
    """`x*9//10`, never `x*0.9` — doc 04's float-creep failure mode, closed at the boundary."""
    with pytest.raises(ValueError, match="non-negative integer weights"):
        require_ranking_weights(dict(RANKING_WEIGHTS_V2) | {"risk": 1_000.0})


def test_the_scale_travels_with_the_weights_so_a_v2_manifest_cannot_reach_a_v1_scorer():
    """Six weights summing to 10000 fed to a scorer that divides by 100 produce a utility a hundred
    times too large, clamped to the ceiling, and every candidate ties — the same 'everything scores
    50' failure this wave exists to end, arriving from the other direction."""
    assert ranking_weight_scale(dict(RANKING_WEIGHTS_V2)) == 10_000
    assert ranking_weight_scale(dict(RANKING_WEIGHTS_V1)) == 100


def test_the_cost_components_are_named_rather_than_implied():
    assert set(UTILITY_COMPONENTS) == set(RANKING_WEIGHTS_V2)
    assert set(RANKING_WEIGHTS_V1) == set(UTILITY_COMPONENTS) - {"importance"}


# ═════════════════════════════════════════════════════════════════════════════════════════════
# K0 (5) · `advisory` IS UNFALSIFIABLE — the safety property of the critique seam
# ═════════════════════════════════════════════════════════════════════════════════════════════

def verdict(**overrides) -> CritiqueVerdict:
    kwargs = dict(verdict="proceed", utility_bp=6_000, confidence_bp=7_000,
                  rationale="The corpus rule the discount play violates does not apply here.")
    kwargs.update(overrides)
    return CritiqueVerdict(**kwargs)


def test_a_binding_verdict_cannot_be_constructed():
    """GeniOS scores; the agent executes. A verdict that could be made binding would make GeniOS the
    operator of somebody else's system, on evidence it does not own."""
    assert verdict().advisory is True
    with pytest.raises(ValidationError, match="advisory must be True"):
        verdict(advisory=False)


def test_a_binding_verdict_cannot_be_COPIED_into_existence_either():
    """The hole L2 found on `MetricCorrelation`: `model_copy(update=...)` runs NO validator in
    pydantic v2, so on a plain frozen model one line produces a well-typed object carrying the claim
    the law exists to make unconstructible. `RevalidatedModel` re-enters the constructor."""
    with pytest.raises(ValidationError, match="advisory must be True"):
        verdict().model_copy(update={"advisory": False})


def test_a_copy_with_no_update_is_still_the_same_object_s_fields():
    """The other half of the base's contract: a copy with no update skips the work rather than
    paying for a revalidation nothing changed."""
    original = verdict()
    assert original.model_copy() == original


def test_every_revalidated_model_re_enters_its_constructor_on_copy():
    """Walked rather than asserted on `CritiqueVerdict` alone, exactly as L2 walks `Measurement`:
    the hole was never specific to one field, and a sixth type added later is covered by this test
    the day it is written rather than the day it is reviewed."""
    subclasses = {cls.__name__ for cls in RevalidatedModel.__subclasses__()}
    assert subclasses == {"ExternalCandidate", "CritiqueVerdict", "BriefEntry", "BriefRanking"}
    for cls in RevalidatedModel.__subclasses__():
        assert cls.model_copy is RevalidatedModel.model_copy, f"{cls.__name__} overrides model_copy"


def test_a_truthy_non_bool_is_not_a_bool():
    """A `0` or a `1` out of a jsonb column is exactly how a binding verdict nobody typed appears."""
    with pytest.raises(TypeError, match="advisory"):
        verdict(advisory=1)


def test_a_hold_names_the_checks_that_failed():
    """A claim that something is wrong, with no receipt, is a refusal whose reason cannot be shown
    to the agent that asked."""
    with pytest.raises(ValidationError, match="names the checks that failed"):
        verdict(verdict="hold")
    assert verdict(verdict="hold", failing_checks=("adm_014",)).failing_checks == ("adm_014",)


def test_the_verdict_vocabulary_is_closed_and_says_nothing_binding():
    assert CRITIQUE_VERDICTS == ("proceed", "modify", "hold")
    with pytest.raises(ValidationError, match="verdict must be one of"):
        verdict(verdict="execute")


# ═════════════════════════════════════════════════════════════════════════════════════════════
# K0 (6) · the rest of the new vocabulary
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_an_external_candidate_is_scoped_typed_and_float_free():
    """A proposal with no target cannot be checked against the situation it claims to be about, and
    a float param reaches a scorer that is integer-only by doctrine."""
    proposal = ExternalCandidate(proposal_id="prop_1", agent_id="hermes", kind="email_draft",
                                 draft="Hi there", params={"send_after_hours": 24},
                                 target_ref="deal_9")
    assert proposal.kind in EXTERNAL_CANDIDATE_KINDS
    with pytest.raises(ValidationError, match="kind must be one of"):
        proposal.model_copy(update={"kind": "wire_transfer"})
    with pytest.raises(ValidationError, match="floats are forbidden"):
        ExternalCandidate(proposal_id="prop_1", agent_id="hermes", kind="task", draft="x",
                          params={"ratio": 0.87}, target_ref="deal_9")
    with pytest.raises(ValidationError, match="target_ref"):
        ExternalCandidate(proposal_id="prop_1", agent_id="hermes", kind="task", draft="x",
                          params={}, target_ref="")


def test_a_brief_entry_must_say_why_it_ranks_where_it_does():
    """G-05: *'why #1 today' is DATA, not narrative.* An entry carrying only a rank and a score can
    answer 'what is first' but not 'why', so the answer would have to be regenerated as prose — a
    model explaining a ranking it cannot see."""
    with pytest.raises(ValidationError, match="rank_components is required"):
        BriefEntry(decision_id="decision_1", rank=1, book_score_bp=9_000, rank_components={})


def test_a_brief_ranks_contiguously_and_names_each_decision_once():
    entry_one = BriefEntry(decision_id="decision_1", rank=1, book_score_bp=9_000,
                           rank_components={"importance": 2_500})
    entry_two = BriefEntry(decision_id="decision_2", rank=2, book_score_bp=8_000,
                           rank_components={"importance": 2_000})
    assert BriefRanking(org_id="org_1", brief_date_key="2026-09-07",
                        entries=(entry_one, entry_two)).entries[0].rank == 1
    with pytest.raises(ValidationError, match="contiguous from one"):
        BriefRanking(org_id="org_1", brief_date_key="2026-09-07", entries=(entry_two,))
    twin = entry_two.model_copy(update={"decision_id": "decision_1"})
    with pytest.raises(ValidationError, match="appears once in a brief"):
        BriefRanking(org_id="org_1", brief_date_key="2026-09-07", entries=(entry_one, twin))
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        BriefRanking(org_id="org_1", brief_date_key="7 September", entries=())


def test_do_nothing_always_records_whether_it_was_computed():
    """E4. Today `decision_maker.py:426` copies the manifest sentence verbatim, so every card says
    the same thing and nothing distinguishes that from a computation. `source` is mandatory."""
    assert DO_NOTHING_SOURCES == ("computed", "manifest_fallback")
    computed = {"cost_bp": 2_800, "horizon": T, "statement": "Exposure compounds.",
                "source": "computed"}
    assert require_do_nothing(computed)["source"] == "computed"
    with pytest.raises(ValueError, match="carries exactly"):
        require_do_nothing({k: v for k, v in computed.items() if k != "source"})
    with pytest.raises(ValueError, match="source must be one of"):
        require_do_nothing(computed | {"source": "estimated"})
    assert require_do_nothing(computed | {"horizon": None})["horizon"] is None


def test_the_confidence_vector_is_a_closed_set_of_named_inputs():
    """Rule 11 composes NAMED inputs. A vector that accepted any key would let a fifth name be
    invented at a call site and composed into a raise nobody can trace."""
    assert CONFIDENCE_VECTOR_KEYS == ("independent_evidence_groups", "evidence_coverage_bp",
                                      "corroboration_bp", "source_quality_bp")
    assert require_confidence_vector({"corroboration_bp": 6_000}) == {"corroboration_bp": 6_000}
    assert require_confidence_vector({"independent_evidence_groups": 3})
    with pytest.raises(ValueError, match="accepts only"):
        require_confidence_vector({"vibes_bp": 9_000})
    with pytest.raises(ValueError, match="between 0 and 10000"):
        require_confidence_vector({"corroboration_bp": 10_001})


def test_a_decision_refuses_a_ranking_weights_version_it_does_not_know():
    assert old_decision(ranking_weights_version=RANKING_WEIGHTS_V2_VERSION) \
        .ranking_weights_version == RANKING_WEIGHTS_V2_VERSION
    with pytest.raises(ValueError, match="ranking_weights_version must be one of"):
        old_decision(ranking_weights_version="ranking_weights@9")


def test_a_findings_magnitude_is_optional_signed_and_bounded():
    """G-03. Optional because plenty of findings are pure predicates with no magnitude, and a
    magnitude defaulted to 0 would read as 'found nothing' rather than 'measured nothing'."""
    assert old_finding().value_bp is None
    assert Finding(finding_id="f_1", kind="drop", value_bp=-2_500).value_bp == -2_500
    with pytest.raises(ValueError, match="between -10000 and 10000"):
        Finding(finding_id="f_1", kind="drop", value_bp=10_001)
    with pytest.raises(ValueError, match="between -10000 and 10000"):
        Finding(finding_id="f_1", kind="drop", value_bp=1.5)


def test_an_adjustments_delta_still_answers_exactly_as_it_did():
    """`_signed_bp` was lifted out of `CandidateAdjustment.delta_bp`; changing the exception type of
    an existing field would be a behaviour change wearing a cleanup's clothes."""
    assert CandidateAdjustment(play_id="p", component="impact", delta_bp=-3_000,
                               reason_code="r").delta_bp == -3_000
    with pytest.raises(ValueError, match="delta_bp must be between -10000 and 10000"):
        CandidateAdjustment(play_id="p", component="impact", delta_bp=10_001, reason_code="r")


def test_unit_ref_derives_from_the_result_and_refuses_a_pair_that_never_happened():
    """Globe's third evidence column, derived rather than stored: a second copy can disagree with
    the first, and a disagreement between an evidence row and the unit that wrote it is unresolvable
    after the fact. Membership is checked, so the derivation cannot be turned into a rubber stamp."""
    finding = old_finding()
    result = old_result(finding)
    assert unit_ref(result, finding) == "core.risk" == result.unit_ref_for("f_1")
    with pytest.raises(ValueError, match="was not emitted by"):
        unit_ref(result, Finding(finding_id="f_other", kind="drop"))
    with pytest.raises(ValueError, match="was not emitted by"):
        result.unit_ref_for("f_other")


def test_the_formula_s_answer_is_readable_beside_the_override_that_replaced_it():
    """G-02 / K1. `score_candidate` already writes `formula_utility` on every branch — the number
    the gate needs has been on the record all along with no typed way to ask for it."""
    decision = old_decision()
    assert decision.formula_utility_bp == 5_500
    assert decision.utility_divergence_bp == 6_000 - 5_500
    blind = old_candidate(score_components={"impact": 5_000})
    assert blind.formula_utility_bp is None and blind.utility_divergence_bp is None
