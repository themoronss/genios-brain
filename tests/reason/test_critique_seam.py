"""Wave Z6 · E1 — the critique seam, proved against the SHIPPED corpus (doc 06 OUT-1, gate K6).

The gate row this file exists for is one line: *a corpus rule eliminates an AGENT'S proposed action
via critique*. Everything else here defends the two properties that make that claim worth anything —
that the elimination happens BEFORE the score is looked at, and that an agent cannot improve its own
verdict by declaring anything about the situation it is acting on.

Built from `Domain Expertise/` and never from a mock. The fixture is doc 03's own:
`sales.rule.closing.urgency_must_belong_to_the_buyer`, `severity: blocking`,
`enforced_by: L4_constraint`, whose `when` is TRUE only when `commitment.due_at` is typed absent —
so the same file tests both states of one authored rule by changing one input, and neither state is
a fixture the test wrote for itself.

Hermetic: no database, no network, no model, no clock. The instant is `NOW`.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.reasoning import (
    RANKING_WEIGHTS_V2,
    CapabilityManifest,
    ContextSnapshot,
    CritiqueVerdict,
    ExecutionMode,
    ExternalCandidate,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason import critique as C
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.decision_maker import score_candidate
from genios_engine.reason.engine import NodeContext

from .adapters.conftest import (CLOSING_PLAY, DEAL_FACTS, DEAL_OBSERVATIONS, NOW, URGENCY_RULE,
                                compile_situation)

pytestmark = pytest.mark.unit


# ── the fixture: one real compiled situation, reasoned by the real kernel ────────────────────

def _execution(compiled):
    """The manifest and the decision the compiled lane actually produces for this situation.

    `ranking_v2=True` because critique's declared precondition is the six-weight model (doc 07's
    `PRECONDITIONS`): the five-weight scorer reads all five components directly and cannot express
    an absent one, so it could only score a proposal by inventing the numbers the agent did not
    declare. The seam refuses that lane, and `test_a_five_weight_capability_is_refused` proves it.
    """
    manifest = expertise_capability_manifest(
        compiled.package, root_entity_type="company", situation=compiled.situation,
        context=compiled.context, ranking_v2=True)
    context = NodeContext(
        node_id="node_1", node_type="company",
        facts={path: {"value": value, "confidence": 900, "authority_rank": 3}
               for path, value in DEAL_FACTS.items()},
        obs=[{"kind": kind, "occurred_at": NOW} for kind in DEAL_OBSERVATIONS])
    return reason_native_capability(
        org_id="org_weld", context=context, capability=manifest, evaluation_time=NOW,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW)


@pytest.fixture(scope="module")
def blocked():
    """The situation where the authored blocking rule FIRES: `commitment.due_at` typed absent."""
    return _execution(compile_situation(absent=("commitment.due_at",)))


@pytest.fixture(scope="module")
def unbound():
    """The same situation with the absence untyped — the rule is UNKNOWN and abstains."""
    return _execution(compile_situation())


def proposal(**overrides) -> ExternalCandidate:
    """An agent's email draft against this situation. The draft is the one the doctrine is about."""
    body = {
        "proposal_id": "prop_1", "agent_id": "agent_x", "kind": "email_draft",
        "draft": "Our quarter closes Friday — can we get this signed before then?",
        "params": {"impact_bp": 6_000, "effort_bp": 2_000}, "target_ref": "node_1",
    }
    body.update(overrides)
    return ExternalCandidate(**body)


def _critique(execution, **overrides):
    return C.critique_proposal(
        request=execution.request, candidates=execution.decision.candidates,
        confidence_bp=execution.decision.confidence_bp, proposal=proposal(**overrides))


# =================================================================================================
# K6 · THE ROW: authored doctrine binds something GeniOS did not generate
# =================================================================================================

def test_a_corpus_rule_eliminates_an_agents_proposed_action_and_names_itself(blocked):
    """The whole product claim, from the authored YAML to the verdict an agent reads.

    Not "a rule fired somewhere": the verdict is `hold`, the failing check is the rule's own id, and
    the rationale carries the authored sentence rather than a paraphrase of it — because an agent
    author who disagrees has to be able to go and read the rule.
    """
    outcome = _critique(blocked)

    assert outcome.verdict.verdict == "hold"
    assert outcome.verdict.failing_checks == (URGENCY_RULE,)
    assert "A closing recommendation MUST rest on a date the BUYER owns" in outcome.verdict.rationale
    applied = [row for row in outcome.receipt["rules_consulted"] if row["applies"]]
    urgency = next(row for row in applied if row["rule_id"] == URGENCY_RULE)
    assert urgency["severity"] == "blocking" and urgency["outcome"] == "fired"
    assert urgency["reason"] == C.SCOPE_REASON
    # The scope is the plays the doctrine governs, and the play it removed from OUR field is named,
    # so "why did this rule reach my action" is answerable from the response alone.
    assert CLOSING_PLAY in urgency["scope_play_ids"]


def test_the_elimination_is_performed_by_the_decision_makers_own_evaluator(blocked):
    """The same event, produced by the same code, as an elimination on a decision.

    A second implementation of "a blocking check removes a candidate" would drift from the first,
    and the first is `preserve hard`. The check this seam builds carries the SAME reason code
    `core.constraint` stamps, at the same stage, and is applied by `evaluate_candidates` itself.
    """
    from genios_engine.reason.adapters.rule_compiler import POLICY_BLOCK_REASON

    check = _critique(blocked).receipt["eliminating_checks"][0]
    assert check["reason_code"] == POLICY_BLOCK_REASON
    assert check["stage"] == "policy"
    # ...and it is stamped by the seam, not by a unit that never ran for this proposal.
    assert check["evaluator_id"] == C.CRITIQUE_EVALUATOR_ID


def test_an_unevaluable_rule_neither_holds_nor_passes_and_says_so(unbound):
    """L3-Y1's three-state law, honoured at this consumer.

    The identical proposal against the identical situation with ONE input untyped: the rule cannot
    be read, so it does not block — and it does not silently vanish either. `rule_unevaluable` is on
    the record with what could not be read, which is the difference between "doctrine cleared you"
    and "doctrine could not look".
    """
    outcome = _critique(unbound)

    assert URGENCY_RULE not in outcome.verdict.failing_checks
    unevaluable = {row["rule_id"] for row in outcome.receipt["rules_consulted"]
                   if row["reason"] == C.UNEVALUABLE_REASON}
    assert URGENCY_RULE in unevaluable
    named = next(row for row in outcome.receipt["rules_consulted"]
                 if row["rule_id"] == URGENCY_RULE)
    assert named["missing"], "an unevaluable rule must name what it could not read"


def test_the_check_runs_before_the_score_so_a_high_scoring_draft_is_still_held(blocked):
    """The Decision Evaluator's ordering, which is the safety property and not an implementation
    detail: a proposal the corpus forbids may never be recommended and then quietly demoted.

    The draft is deliberately scored ABOVE every authored play — the state in which a rank-first
    implementation would answer `proceed`, because nothing would outrank it — and the elimination
    still decides. Held AND out-scoring is the pair that makes the ordering visible.
    """
    outcome = _critique(blocked, params={"impact_bp": 10_000, "success_probability_bp": 10_000,
                                         "effort_bp": 0, "risk_bp": 0})

    assert outcome.verdict.utility_bp > outcome.receipt["best_authored"]["utility_bp"]
    assert outcome.verdict.verdict == "hold"
    assert outcome.verdict.failing_checks == (URGENCY_RULE,)


# =================================================================================================
# what the agent may declare — and what it may not
# =================================================================================================

@pytest.mark.parametrize("key", ["urgency_bp", "importance_bp", "priority_override_bp",
                                 "confidence_bp"])
def test_an_agent_may_not_declare_the_situations_own_terms(blocked, key):
    """The one safety rule among the input checks. An agent that could declare its own urgency
    could raise its own score, so this is a refusal and never a silent drop."""
    with pytest.raises(C.CritiqueRefused) as refusal:
        _critique(blocked, params={key: 9_000})

    assert refusal.value.reason == C.AGENT_DECLARED_SITUATION_TERM
    assert key in refusal.value.detail


def test_the_situation_terms_come_from_the_run_and_not_from_the_proposal(blocked):
    """Urgency and the authored priority prior are the RUN's, identical to what its own candidates
    were scored with."""
    outcome = _critique(blocked)
    ours = {name: value for name, value in
            (blocked.decision.candidates[0].score_components or {}).items()}

    assert outcome.receipt["components"]["urgency"] == ours["urgency"]
    assert outcome.receipt["priority_override_bp"] == ours.get("priority_override")


def test_an_undeclared_component_is_absent_and_reweighed_never_defaulted(blocked):
    """doc 04 E1's honesty guard, applied to a proposal.

    The proposal declares impact and effort and says nothing about success or risk. A neutral 5,000
    for the two it did not declare is the "every card scores 50" defect through a new door, so the
    weights are REDISTRIBUTED — the surviving four still sum to the full scale, and the absence is
    named rather than inferred from a suspiciously middling number.
    """
    outcome = _critique(blocked)
    weights = outcome.receipt["effective_weights"]

    assert set(outcome.receipt["absent_components"]) == {
        f"{C.ABSENT_COMPONENT_REASON}:success", f"{C.ABSENT_COMPONENT_REASON}:risk"}
    assert "success" not in weights and "risk" not in weights
    assert sum(weights.values()) == 10_000
    # And the answer differs from what a neutral default would have produced — the guard is doing
    # arithmetic, not just writing a reason code.
    defaulted = C.critique_proposal(
        request=blocked.request, candidates=blocked.decision.candidates,
        confidence_bp=blocked.decision.confidence_bp,
        proposal=proposal(params={"impact_bp": 6_000, "effort_bp": 2_000,
                                  "success_probability_bp": 5_000, "risk_bp": 5_000}))
    assert defaulted.verdict.utility_bp != outcome.verdict.utility_bp


def test_a_float_never_reaches_the_scorer(blocked):
    """Refused at the contract boundary, which is where the doctrine says integers begin. A `0.87`
    coerced three frames later is a silently wrong parameter on somebody else's email."""
    with pytest.raises(ValueError):
        proposal(params={"impact_bp": 0.87})


def test_a_declared_component_out_of_range_is_refused(blocked):
    with pytest.raises(C.CritiqueRefused) as refusal:
        _critique(blocked, params={"impact_bp": 20_000})
    assert refusal.value.reason == C.AGENT_DECLARED_SITUATION_TERM


# =================================================================================================
# the score is the decision maker's, not a second one
# =================================================================================================

def test_the_utility_is_the_decision_makers_own_scorer_on_the_same_weights(blocked):
    """Byte-for-byte the same function on the same manifest. A second scorer for external
    candidates would drift from the first, and "GeniOS scored your action the way it scores its
    own" would stop being true without anything failing."""
    outcome = _critique(blocked)
    components = {name: value for name, value in outcome.receipt["components"].items()
                  if name not in ("formula_utility", "priority_override")}

    assert score_candidate(blocked.request, dict(components),
                           outcome.receipt["priority_override_bp"]) == outcome.verdict.utility_bp


def test_the_winning_alternative_is_never_a_candidate_the_corpus_removed(blocked):
    """Offering the eliminated play back to the agent would be this seam handing over the exact
    action Layer 3 refused."""
    outcome = _critique(blocked)
    eliminated = {candidate.play_id for candidate in blocked.decision.candidates
                  if candidate.disposition.value == "eliminated"}

    assert CLOSING_PLAY in eliminated
    assert outcome.verdict.winning_alternative not in eliminated


def test_an_eliminated_play_is_skipped_even_when_it_carried_the_highest_utility():
    """The corpus fixture cannot prove this on its own — every compiled play there scores the same,
    so a scorer that ignored disposition would still pick an eligible one by tie-break and the test
    above would pass while the property was gone. Here the removed play outscores everything.
    """
    request = _bare_request(PlayDefinition(play_id="kept", version="1.0.0", label="Kept",
                                           steps=("step",)))
    field = [{"play_id": "removed", "disposition": "eliminated", "final_utility_bp": 9_500,
              "score_components": {"urgency": 5_000}},
             {"play_id": "kept", "disposition": "eligible", "final_utility_bp": 9_000,
              "score_components": {"urgency": 5_000}}]

    assert C.best_authored(field)["play_id"] == "kept"
    outcome = C.critique_proposal(request=request, candidates=field, confidence_bp=7_000,
                                  proposal=proposal(params={"impact_bp": 1_000}))
    assert outcome.verdict.winning_alternative == "kept"
    assert outcome.receipt["best_authored"] == {"play_id": "kept", "utility_bp": 9_000}


def test_two_identical_critiques_are_byte_identical(blocked):
    """Determinism, at the level a caller can check: the verdict AND the argument for it."""
    first, second = _critique(blocked), _critique(blocked)

    assert first.verdict == second.verdict
    assert semantic_hash(dict(first.receipt)) == semantic_hash(dict(second.receipt))


# =================================================================================================
# proceed / modify, on a manifest with no doctrine at all
# =================================================================================================

def _bare_request(*plays: PlayDefinition) -> ReasoningRequest:
    """A six-weight capability carrying no weld, so the verdict is decided by score alone."""
    capability = CapabilityManifest(
        capability_id="test.bare", version="1.0.0", domain="test", root_entity_type="entity",
        goal=Goal(goal_id="g", statement="Compare a proposal with an authored play."),
        reasoners=(ReasonerSpec(reasoner_id="core.context", version="1.0.0"),),
        plays=plays, ranking_weights=dict(RANKING_WEIGHTS_V2),
        policies=(), live_delivery_enabled=False)
    return ReasoningRequest(
        org_id="org_1", capability=capability,
        context=ContextSnapshot(org_id="org_1", graph_version=1, root_entity_id="node_1",
                                root_entity_type="entity", evaluation_time=NOW,
                                selector_version="test.v1"),
        evaluation_time=NOW, trigger_kind="test.trigger")


def _authored(utility_bp: int, play_id: str = "authored_play"):
    return [{"play_id": play_id, "disposition": "eligible", "final_utility_bp": utility_bp,
             "score_components": {"urgency": 5_000}}]


def test_a_proposal_an_authored_play_outscores_is_modify_with_the_alternative_named():
    request = _bare_request(PlayDefinition(play_id="authored_play", version="1.0.0",
                                           label="Authored", steps=("step",)))
    outcome = C.critique_proposal(request=request, candidates=_authored(9_000),
                                  confidence_bp=7_000,
                                  proposal=proposal(params={"impact_bp": 1_000}))

    assert outcome.verdict.verdict == "modify"
    assert outcome.verdict.winning_alternative == "authored_play"
    assert outcome.verdict.failing_checks == ()


def test_a_proposal_nothing_blocks_and_nothing_outscores_is_proceed():
    request = _bare_request(PlayDefinition(play_id="authored_play", version="1.0.0",
                                           label="Authored", steps=("step",)))
    outcome = C.critique_proposal(request=request, candidates=_authored(1_000),
                                  confidence_bp=7_000,
                                  proposal=proposal(params={"impact_bp": 9_500,
                                                            "success_probability_bp": 9_500}))

    assert outcome.verdict.verdict == "proceed"
    assert outcome.verdict.winning_alternative is None


def test_a_five_weight_capability_is_refused_rather_than_scored_on_invented_numbers():
    """doc 07 makes `ranking_v2` this feature's precondition, and this is why: the legacy scorer
    reads all five components directly, so the only way to answer here is to make four of them up."""
    capability = CapabilityManifest(
        capability_id="test.legacy", version="1.0.0", domain="test", root_entity_type="entity",
        goal=Goal(goal_id="g", statement="Legacy."),
        reasoners=(ReasonerSpec(reasoner_id="core.context", version="1.0.0"),),
        plays=(PlayDefinition(play_id="p", version="1.0.0", label="P", steps=("s",)),),
        policies=(), live_delivery_enabled=False)
    request = ReasoningRequest(
        org_id="org_1", capability=capability,
        context=ContextSnapshot(org_id="org_1", graph_version=1, root_entity_id="node_1",
                                root_entity_type="entity", evaluation_time=NOW,
                                selector_version="test.v1"),
        evaluation_time=NOW, trigger_kind="test.trigger")

    with pytest.raises(C.CritiqueRefused) as refusal:
        C.critique_proposal(request=request, candidates=_authored(5_000, "p"),
                            confidence_bp=5_000, proposal=proposal())
    assert refusal.value.reason == C.RANKING_MODEL_V1


# =================================================================================================
# the rationale, and R-3's seam
# =================================================================================================

def test_the_rationale_computes_no_number_it_does_not_also_type(blocked):
    """Every number in this answer is a typed field, so a digit in the prose can only restate one
    or contradict one. Digits inside a quoted rule id or an authored statement are allowed — the
    rationale's job is to quote doctrine accurately — and `unquoted_numbers` is the distinction."""
    outcome = _critique(blocked)
    grounds = ([row["rule_id"] for row in outcome.receipt["rules_consulted"]]
               + [row["statement"] for row in outcome.receipt["rules_consulted"]]
               + [outcome.verdict.winning_alternative or ""])

    assert C.unquoted_numbers(outcome.verdict.rationale, grounds) == ()


def test_a_narrator_that_invents_a_number_is_refused_and_labelled(blocked):
    def narrator(receipt):
        return f"Hold, because {URGENCY_RULE} applies with 42 percent certainty."

    outcome = C.critique_proposal(
        request=blocked.request, candidates=blocked.decision.candidates,
        confidence_bp=blocked.decision.confidence_bp, proposal=proposal(), narrator=narrator)

    assert outcome.receipt["rationale_source"] == "template_fallback"
    assert "42" not in outcome.verdict.rationale


def test_a_narrator_that_names_nothing_in_the_receipt_is_refused(blocked):
    outcome = C.critique_proposal(
        request=blocked.request, candidates=blocked.decision.candidates,
        confidence_bp=blocked.decision.confidence_bp, proposal=proposal(),
        narrator=lambda receipt: "This looks risky and I would not send it.")

    assert outcome.receipt["rationale_source"] == "template_fallback"


def test_a_narrator_that_raises_falls_back_rather_than_failing_the_critique(blocked):
    def narrator(receipt):
        raise RuntimeError("the model was unreachable")

    outcome = C.critique_proposal(
        request=blocked.request, candidates=blocked.decision.candidates,
        confidence_bp=blocked.decision.confidence_bp, proposal=proposal(), narrator=narrator)

    assert outcome.receipt["rationale_source"] == "template_fallback"
    assert outcome.verdict.verdict == "hold"


def test_a_grounded_narration_is_taken_and_labelled_as_generated(blocked):
    """R-3's seam works when the narrator behaves — and the label says a model wrote it, which is
    the whole of the honesty requirement here."""
    def narrator(receipt):
        return f"Hold: {URGENCY_RULE} blocks this in the situation as evidenced."
    narrator.generation = "claude@test"

    outcome = C.critique_proposal(
        request=blocked.request, candidates=blocked.decision.candidates,
        confidence_bp=blocked.decision.confidence_bp, proposal=proposal(), narrator=narrator)

    assert outcome.receipt["rationale_source"] == "llm:claude@test"
    assert outcome.verdict.rationale.startswith("Hold: ")
    # AND the narration did not touch the decision: the verdict, the checks and the score are the
    # same ones the deterministic path reached. The model narrates; it never decides.
    assert outcome.verdict.verdict == _critique(blocked).verdict.verdict
    assert outcome.verdict.utility_bp == _critique(blocked).verdict.utility_bp
    assert outcome.verdict.failing_checks == _critique(blocked).verdict.failing_checks


# =================================================================================================
# `advisory` — the attack surface, tried rather than asserted about
# =================================================================================================

def _verdict(**overrides) -> dict:
    body = {"verdict": "proceed", "failing_checks": (), "utility_bp": 5_000,
            "confidence_bp": 5_000, "rationale": "Proceed."}
    body.update(overrides)
    return body


def test_advisory_cannot_be_constructed_false():
    with pytest.raises(ValueError, match="advisory must be True"):
        CritiqueVerdict(**_verdict(advisory=False))


def test_advisory_cannot_be_made_false_by_a_copy():
    """`model_copy(update=...)` runs no validator in pydantic v2 — L2 found that hole on
    `is_causal` and Z0 closed the same one here with `RevalidatedModel`. Driven, not assumed."""
    verdict = CritiqueVerdict(**_verdict())
    with pytest.raises(ValueError, match="advisory must be True"):
        verdict.model_copy(update={"advisory": False})
    with pytest.raises(ValueError, match="advisory must be True"):
        verdict.model_copy(update={"advisory": False}, deep=True)


def test_advisory_cannot_be_made_false_by_validation_of_hostile_input():
    # `0` and `"false"` are the shapes a jsonb column and a form post hand you, and both are
    # falsy: `require_bool` refuses the TYPE, so neither can become a binding verdict nobody typed.
    for payload in ({"advisory": False}, {"advisory": 0}, {"advisory": "false"},
                    {"advisory": None}):
        with pytest.raises((TypeError, ValueError)):
            CritiqueVerdict.model_validate(_verdict(**payload))
    with pytest.raises(ValueError):
        CritiqueVerdict.model_validate_json(
            '{"verdict":"proceed","advisory":false,"failing_checks":[],'
            '"utility_bp":5000,"confidence_bp":5000,"rationale":"x"}')


def test_a_frozen_verdict_cannot_be_reassigned():
    verdict = CritiqueVerdict(**_verdict())
    with pytest.raises(Exception):
        verdict.advisory = False


def test_model_construct_bypasses_validation_and_the_route_is_what_refuses_it():
    """THE ONE DOOR THAT IS STILL OPEN, named rather than hidden.

    `model_construct` is pydantic's documented "I know what I am doing" escape hatch: it runs no
    validator, by design, on every model in this codebase. So a caller INSIDE the process can build
    a `CritiqueVerdict` whose `advisory` is False — and no constructor can stop that without
    breaking the same door every other contract relies on.

    What closes it where it matters is that nothing reaches a client except through the route, and
    the route re-checks `advisory is True` before serialising. That check is asserted structurally
    in `tests/test_l4_seams_out.py`; this test exists so the hole is a KNOWN one with a named
    compensating control rather than a surprise found later.
    """
    forged = CritiqueVerdict.model_construct(**_verdict(advisory=False))

    assert forged.advisory is False, "model_construct still validates — update the route's guard"
    # and it cannot survive being re-validated, which is what any deserialisation does
    with pytest.raises(ValueError):
        CritiqueVerdict.model_validate(dict(forged.__dict__))


def test_a_hold_always_names_the_checks_that_failed():
    """A refusal whose reason cannot be shown to the agent that asked is not a refusal, it is a
    veto — and this seam has no authority to veto anything."""
    with pytest.raises(ValueError, match="hold"):
        CritiqueVerdict(**_verdict(verdict="hold"))


def test_every_verdict_this_seam_produces_is_advisory(blocked, unbound):
    for execution in (blocked, unbound):
        assert _critique(execution).verdict.advisory is True


# =================================================================================================
# the shapes the core accepts
# =================================================================================================

def test_persisted_rows_and_in_memory_candidates_reach_the_same_verdict(blocked):
    """The store hands back mappings and the orchestrator hands back dataclasses; a seam that only
    understood one would force a future in-process caller through Postgres to ask a question."""
    rows = C.candidate_rows(blocked.decision.candidates)
    from_rows = C.critique_proposal(request=blocked.request, candidates=rows,
                                    confidence_bp=blocked.decision.confidence_bp,
                                    proposal=proposal())

    assert from_rows.verdict == _critique(blocked).verdict


def test_a_run_whose_candidates_disagree_about_urgency_is_refused(blocked):
    """`synthesize_candidates` gives every candidate of a run the same situation terms. If that
    ever stops being true the assumption must fail loudly, not pick one candidate's urgency to
    judge a stranger's action by."""
    rows = [dict(row) for row in C.candidate_rows(blocked.decision.candidates)][:2]
    rows[0]["score_components"] = {**rows[0]["score_components"], "urgency": 100}

    with pytest.raises(C.CritiqueRefused) as refusal:
        C.critique_proposal(request=blocked.request, candidates=rows, confidence_bp=5_000,
                            proposal=proposal())
    assert refusal.value.reason == C.NO_FIELD
