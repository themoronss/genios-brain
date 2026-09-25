"""L2-5 · the Context Reasoner — one call per SITUATION, behind the gate that already exists.

⛔ **IT REGISTERS AS AN R-SITE AND BUILDS NO METERING.** `reason/llm_sites.py`:

    THERE IS EXACTLY ONE C5 GATE, AND IT IS `reason/bundle/gate.RSiteGate`. This module does not
    re-implement activation, budget, retry or receipting; it delegates all four, so a tenant's
    spend is one number measured against one ledger.

And R-1 already holds the contract, in `reason/interpretation.py`:

    The model returns `{classification, confidence_bp}` AS EVIDENCE; a unit reads it like any
    other input; THE FORMULA DECIDES. The model never says "this is urgent."
    ⛔ IT CANNOT RAISE CONFIDENCE.

⛔ **THE COST CHECK RAN FIRST AND CORRECTED THE PLAN TWICE.** §2 claims *"same month → ~40 calls"*
and a **10×** saving from attaching the call to the situation. Measured: the pilot carries **159
active situations** (`situation_bso.l1_refusal`), against 465 events — **2.9×, not 10×**.

And §2 calls *"low confidence + low importance = unknown, do not spend"* **the largest saving in
the plan**. At the measured shape it saves **$0.10 a sweep — about $3 a month.** The rule is still
right, and **for a quality reason, not a cost one**: a low-confidence reading of a low-importance
situation is a wrong answer nobody needed. Saying that out loud is what stops the next person
defending it with a number that does not exist.
"""
from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


# =================================================================================================
# U2 · register the site — do not build a gate
# =================================================================================================

def test_the_site_is_registered_with_a_tier_and_a_ceiling():
    """⛔ `R_SITES` is a CLOSED vocabulary: *"a typo must be a refusal rather than a ledger row
    under `R-6` that reads as an activated site right up until the month's bill."*"""
    from genios_engine.reason.bundle.sites import (
        R_SITES, SITE_MAX_OUTPUT_TOKENS, SITE_SITUATION, SITE_TIERS, TIER_T1, require_site,
    )

    assert SITE_SITUATION in R_SITES
    assert require_site(SITE_SITUATION) == SITE_SITUATION
    assert SITE_TIERS[SITE_SITUATION] is TIER_T1 or SITE_TIERS[SITE_SITUATION] == TIER_T1, (
        "the reasoner is Haiku by default; Sonnet is the escalation, not the tier")
    assert SITE_MAX_OUTPUT_TOKENS[SITE_SITUATION] <= 600, (
        "structured output, not prose — a model that writes an essay is a cost incident and a "
        "V-8 failure at the same time")


def test_the_site_brings_its_own_activation_or_it_is_a_ninth_dark_thing():
    """⛔ L2-4 declined to add an R-site for exactly this reason: an unactivated site is a ninth
    thing built and never switched on. `L4_FEATURES` and `FEATURE_WAVES` are both closed."""
    from genios_engine.platform.l4_activation import (
        FEATURE_SITUATION_REASONER, FEATURE_WAVES, L4_FEATURES,
    )

    assert FEATURE_SITUATION_REASONER in L4_FEATURES
    assert FEATURE_WAVES[FEATURE_SITUATION_REASONER], "a feature with no wave is unroutable"


def test_the_reasoner_builds_no_metering_caching_or_budget():
    """⛔ *"A parallel gate would split the tenant's spend across two ledgers — the one thing
    `llm_sites.py` says it exists to prevent."* Asserted over the AST, because L2-6 learned that a
    grep matches the docstring that explains the rule."""
    import ast

    from genios_engine.reason import situation_reasoner

    tree = ast.parse(inspect.getsource(situation_reasoner))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    forbidden = {"NarrativeBudget", "record_call", "RSiteGate", "call", "cache_key"}
    assert not (names & forbidden), f"the reasoner re-implements {sorted(names & forbidden)}"
    assert "run_site" in names, "it does not delegate to the shared runner"


def test_it_hands_the_l2_6_validator_rather_than_writing_a_second_one():
    """L2-6 exists for this caller. A second copy of the six checks is a second answer."""
    from genios_engine.reason import situation_reasoner

    src = inspect.getsource(situation_reasoner)
    assert "proposal_gate" in src or "as_gate_validator" in src or "validate_proposal" in src


# =================================================================================================
# U3 · escalation, on the two numbers — and low+low never calls
# =================================================================================================

@pytest.mark.parametrize("confidence_bp,importance_bp,expected", [
    (9000, 9000, "accept"),
    (9000, 1000, "accept"),
    (1000, 9000, "escalate"),
    (1000, 1000, "unknown"),
])
def test_the_quadrant_decides_before_anything_is_spent(confidence_bp, importance_bp, expected):
    from genios_engine.reason.situation_reasoner import next_step

    assert next_step(confidence_bp=confidence_bp, importance_bp=importance_bp).value == expected


def test_low_and_low_never_reaches_a_model():
    """⛔ **THE RULE, AND ITS REAL REASON.** §2 calls this *"the largest saving in the plan"*. At
    the measured shape it saves about **$3 a month** — that is not an argument.

    It is a QUALITY rule: a low-confidence reading of a low-importance situation is a wrong answer
    nobody needed, and a wrong card costs more than no card. L1 wrote the same sentence about
    promises: *"telling a founder they broke a promise they kept is the failure that loses trust
    rather than quality."*
    """
    from genios_engine.reason.situation_reasoner import Step, next_step, should_consult

    assert next_step(confidence_bp=1000, importance_bp=1000) is Step.UNKNOWN
    assert should_consult(Step.UNKNOWN) is False
    assert should_consult(Step.ACCEPT) is True
    assert should_consult(Step.ESCALATE) is True


def test_the_thresholds_are_declared_and_not_inlined():
    """A number nobody can find is a number nobody can change. And **integers** — V-8."""
    from genios_engine.reason.situation_reasoner import (
        CONFIDENCE_FLOOR_BP, IMPORTANCE_FLOOR_BP,
    )

    for value in (CONFIDENCE_FLOOR_BP, IMPORTANCE_FLOOR_BP):
        assert isinstance(value, int) and not isinstance(value, bool)
        assert 0 < value < 10_000


def test_a_missing_number_is_unknown_and_never_an_assumed_middle():
    """⛔ *"`None` is not a low number — it is nobody having measured."* L1 step 12's S22, one
    layer up: an unscored situation must not be read as a confident one."""
    from genios_engine.reason.situation_reasoner import Step, next_step

    assert next_step(confidence_bp=None, importance_bp=9000) is Step.UNKNOWN
    assert next_step(confidence_bp=9000, importance_bp=None) is Step.UNKNOWN


# =================================================================================================
# U1/U4 · the prompt, its own version, and a cache key the GATE uses
# =================================================================================================

def test_the_prompt_version_is_its_own_and_not_l1s():
    """⛔ *"A change here must not invalidate every extraction in the corpus."*"""
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint
    from genios_engine.reason.situation_reasoner import PROMPT_VERSION

    assert PROMPT_VERSION
    assert PROMPT_VERSION != vocabulary_fingerprint()


def test_the_seed_is_the_slice_digest_and_the_gate_keys_on_it():
    """U4 — *"the reasoner supplies a slice digest and the gate does the rest."* Two sweeps over
    an unchanged slice must not pay twice."""
    from genios_engine.reason.situation_reasoner import consult_seed

    a = consult_seed(situation_id="s1", slice_digest="abc")
    assert a == consult_seed(situation_id="s1", slice_digest="abc")
    assert a != consult_seed(situation_id="s1", slice_digest="def")


# =================================================================================================
# U5 · refusal is a valid answer · and R-1's law, copied verbatim
# =================================================================================================

def test_the_reasoner_cannot_raise_confidence():
    """⛔ **R-1's rule, and it is stronger than anything this plan wrote.** Copy it verbatim."""
    from genios_engine.reason.situation_reasoner import clamp_confidence

    assert clamp_confidence(proposed_bp=9500, current_bp=4000) == 4000
    assert clamp_confidence(proposed_bp=1500, current_bp=4000) == 1500
    assert clamp_confidence(proposed_bp=9500, current_bp=None) is None


def test_silence_is_the_fallback_and_not_a_neutral_reading():
    """R-1: *"a default reading would be a fact the model never stated, injected into the evidence
    layer where the formula would weigh it. The fallback for an interpretation is silence."*"""
    from genios_engine.reason.situation_reasoner import FALLBACK

    assert FALLBACK() == {}


# =================================================================================================
# ⛔ THE WIRE. A site nothing calls is the ninth "built and never switched on" — and L2-4 declined
# to register an R-site for exactly that reason.
# =================================================================================================

def test_the_sweep_calls_the_reasoner_where_the_slice_exists():
    """`shadow_compile` is the only place a situation and its slice are both in hand."""
    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow.shadow_compile)
    assert "reason_over_situation(" in src, "nothing on a real request path calls the reasoner"
    assert "context_slice" in src


def test_the_quadrant_runs_before_the_call_and_is_counted_either_way():
    """⛔ Both arms counted. *"A skip nobody can see is indistinguishable from one that had
    nothing to say"* — `domain_shadow`'s own sentence about the budget."""
    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow.shadow_compile)
    for key in ("reasoner_unknown", "reasoner_consulted"):
        assert key in src, f"{key} is never counted"


def test_the_reasoner_can_never_kill_the_sweep():
    """⛔ The rule L2-7's full-suite failure taught: a model consult that raises must cost a
    reading, never the compile. `shadow_compile` already catches per situation for exactly this."""
    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow.shadow_compile)
    head, sep, _tail = src.partition("reason_over_situation(")
    assert sep
    assert "try:" in head[-600:], "the consult is unguarded"


def test_it_proposes_and_does_not_commit():
    """§5: *"It does not write to the graph."* The sweep must not apply the payload to a
    situation — L2-6 validates, and the durable home is `situation_interpretations`."""
    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow.shadow_compile)
    window = src[src.index("reason_over_situation("):][:900]
    for forbidden in ("write_fact", "upsert_situation", "update context_situations"):
        assert forbidden not in window, f"the reasoner's payload reaches {forbidden}"
