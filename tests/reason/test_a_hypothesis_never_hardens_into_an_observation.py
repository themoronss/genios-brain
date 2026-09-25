"""L2-8-U4 · the F20 rows — the one failure this whole layer's three-way split exists to prevent.

⛔ L1's **F20** is *"unknown → true"*. In Layer 2 it takes a specific and dangerous shape:

    A HYPOTHESIS THAT HARDENED INTO AN OBSERVATION.

Four ways it happens, and the step file names all four. Each one is attacked here directly, and
each is refused by a rule that already exists — because a layer that needed NEW code to stop this
would be a layer that had not actually built the split.

    a hypothesis with low confidence rendered as fact      → the claim state, and V-9
    an inference whose only citation is another inference  → the resolver, L2-6
    `unknowns` emptied by a confident model on thin cover  → V-10, and L2-6's check 5
    an interpretation that outlived `valid_until`          → the envelope rule: a model may not
                                                              write its own expiry
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_RESOLVES_ALL = lambda refs: frozenset(refs)     # noqa: E731
_RESOLVES_NONE = lambda refs: frozenset()        # noqa: E731


def _validate(proposal, **kw):
    from genios_engine.context.proposal_gate import validate_proposal

    kw.setdefault("resolve_refs", _RESOLVES_ALL)
    kw.setdefault("coverage_ready", True)
    kw.setdefault("expected_facts", ())
    return validate_proposal(proposal, **kw)


# =================================================================================================
# F20-a · a hypothesis rendered as a statement of fact
# =================================================================================================

def test_a_hypothesis_is_a_different_claim_state_from_everything_else():
    """⛔ It cannot be rendered as an observation by ACCIDENT, because nothing else shares its
    state — a renderer that treats `HYPOTHESISED` as `OBSERVED` has to say so."""
    from genios_engine.contracts.claim_state import ClaimState, fields_in

    assert fields_in(ClaimState.HYPOTHESISED) == frozenset({"hypotheses"})
    assert "hypotheses" not in fields_in(ClaimState.OBSERVED)


def test_a_model_may_propose_a_hypothesis_and_may_never_propose_an_observation():
    """The hardening path, closed at the source: it cannot write the thing it would harden into."""
    from genios_engine.contracts.claim_state import ClaimState, model_may_write

    assert model_may_write(ClaimState.HYPOTHESISED) is True
    assert model_may_write(ClaimState.OBSERVED) is False


def test_a_hypothesis_that_cites_nothing_is_refused_before_it_is_stored():
    verdict = _validate({"hypotheses": ({"claim": "they are stalling", "confidence_bp": 2000},)})
    assert "l2_receipt:hypotheses[0]" in verdict.reason_codes


def test_the_same_claim_as_an_observation_is_refused_outright():
    """Sensitivity — the probe must distinguish the two, or it is refusing everything."""
    from genios_engine.context.proposal_gate import Outcome

    verdict = _validate({"evidence": ({"quote": "they are stalling"},)})
    assert verdict.outcome is Outcome.REFUSE
    assert "l2_authority:evidence" in verdict.reason_codes


# =================================================================================================
# F20-b · an inference whose only citation is another inference
# =================================================================================================

def test_a_citation_that_does_not_resolve_in_the_evidence_graph_is_refused():
    """⛔ **THIS IS THE CIRCULAR-CITATION DEFENCE.** A hypothesis citing another hypothesis cites
    an id the Evidence Graph has never heard of — `resolve_refs` asks the graph, not the payload.

    *"An unanchorable claim is kept and flagged, never invented."* A ref that resolves to nothing
    is worse than no ref: it looks like proof.
    """
    proposal = {"hypotheses": ({"claim": "stalling", "evidence_refs": ("hyp-other",)},)}
    assert "l2_unresolved:hypotheses[0]" in _validate(
        proposal, resolve_refs=_RESOLVES_NONE).reason_codes


def test_the_resolver_is_asked_the_graph_and_not_the_proposal():
    """A resolver reading the payload would accept a claim that cites itself."""
    seen: list = []

    def resolver(refs):
        seen.append(tuple(refs))
        return frozenset()

    _validate({"hypotheses": ({"claim": "x", "evidence_refs": ("a", "b")},)},
              resolve_refs=resolver)
    assert seen == [("a", "b")], "the refs never reached a resolver"


# =================================================================================================
# F20-c · `unknowns` emptied by a confident model on thin coverage
# =================================================================================================

def test_a_model_cannot_empty_the_unknowns_when_coverage_says_nobody_looked():
    verdict = _validate({"missing_facts": ()}, coverage_ready=False,
                        expected_facts=("thread.ball_in_court",))
    assert "l2_completeness:missing_facts" in verdict.reason_codes


def test_and_the_same_rule_holds_one_layer_up_as_v10():
    """⛔ Two enforcement points on one rule, deliberately — L2-6 refuses the PROPOSAL, V-10
    observes the assembled SITUATION. `validate_situation`'s own docstring says why the
    duplication exists: *"for the objects that did not go through a constructor."*"""
    from genios_engine.contracts.situation import L2Law, validate_situation
    from tests.contracts.l2_situation_fixture import minimal_situation

    decision = validate_situation(
        minimal_situation(type="support_case", coverage_ready=False, missing_facts=()),
        expected_facts=("thread.ball_in_court",))
    assert [f for f in decision.failures if f.law is L2Law.V10]


# =================================================================================================
# F20-d · an interpretation that outlived its expiry and was read as current
# =================================================================================================

def test_a_model_may_not_write_its_own_expiry():
    """⛔ **THE HARDENING THAT NEEDS NO BAD INTENT.** A model that could set `valid_until` could
    set it far enough out that a reading never expires — and an interpretation that never expires
    is an observation in everything but name."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, ClaimState, model_writable_fields

    assert FIELD_CLAIMS["valid_until"].state is ClaimState.ENVELOPE
    assert "valid_until" not in model_writable_fields()


def test_a_proposal_that_names_the_expiry_is_refused_with_its_check():
    from genios_engine.context.proposal_gate import Outcome

    verdict = _validate({"valid_until": "2099-01-01T00:00:00Z"})
    assert verdict.outcome is Outcome.REFUSE
    assert "l2_authority:valid_until" in verdict.reason_codes


def test_a_model_may_not_mint_its_own_trace_either():
    """The same shape: `EvidenceSpan.verified` records what a self-set receipt costs — *"the
    moment another caller can set that flag, it stops meaning 'checked' and starts meaning
    'claimed'."*"""
    from genios_engine.contracts.claim_state import model_writable_fields

    assert "reasoning_trace" not in model_writable_fields()


def test_the_reading_is_stored_with_an_expiry_column_that_is_nullable_and_visible():
    """An expiry nobody can see is an expiry nobody enforces. It is a column, not a jsonb key."""
    import pathlib

    sql = pathlib.Path("migrations/0183_situation_interpretations.sql").read_text().lower()
    assert "valid_until       timestamptz" in sql or "valid_until timestamptz" in sql


# =================================================================================================
# And the rule R-1 wrote, which is the hardening defence at the number level
# =================================================================================================

def test_a_model_can_never_make_us_more_certain_than_we_were():
    """⛔ *"IT CANNOT RAISE CONFIDENCE."* A hypothesis that arrives at 9500 bp against a situation
    we scored 4000 does not make the situation 9500."""
    from genios_engine.reason.situation_reasoner import clamp_confidence

    assert clamp_confidence(proposed_bp=9500, current_bp=4000) == 4000
    assert clamp_confidence(proposed_bp=9500, current_bp=None) is None
