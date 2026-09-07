"""H6 — the pattern registry (L2.6), its registration-time refusals, and the fire-rate guard.

**Gate H6**, invoked by `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` as:

    pytest tests/context/patterns tests/context/quality -q
    python scripts/pattern_fire_report.py --org <pilot> --since 30d

This file was a placeholder until X6. It is now the gate itself. The rows it owns:

| gate row | where |
|---|---|
| >= 6 patterns registered | `test_the_registry_ships_at_least_six_patterns` |
| 0 patterns activated over 10x their expected rate | `test_a_pattern_over_its_ceiling_cannot_activate` |
| a condition kind nobody implements fails at REGISTRATION | `test_an_unimplemented_condition_kind_is_refused_at_registration` |
| per-condition evidence on every match | `tests/context/patterns/test_matcher.py`, `test_candidate.py` |
| `UNKNOWABLE` never satisfies an absence | `tests/context/patterns/test_matcher.py` |

The other two rows on the H6 table — M-6 fabricated facts and M-6 visibility leaks, both HARD FAIL
— are in `tests/context/test_framing.py`, adversarially rather than by assertion.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genios_engine.context.patterns.contract import ConditionKind, PatternError
from genios_engine.context.patterns.matcher import IMPLEMENTED_KINDS
from genios_engine.context.patterns.registry import (FIRE_RATE_CAP_MULTIPLIER, SEED_DIR,
                                                     ActivationDecision, FireObservation,
                                                     PatternRegistry, RegistrationError,
                                                     activation_decision, breaching_patterns,
                                                     exceeds_expected, load_pattern,
                                                     observed_rate_per_100_anchors_30d,
                                                     seed_registry, silent_patterns,
                                                     validate_pattern)

#: The six doc 06 names in its reverse prompt: *"SHIP these patterns first (they are Globe's
#: V1-reachable surfaces)"*.
REQUIRED_PATTERNS = {"commitment_unresolved", "relationship_going_cold", "meeting_preparation_gap",
                     "founder_bottleneck", "condition_now_satisfied", "vendor_renewal_unowned"}


# =================================================================================================
# The gate row: >= 6 patterns registered
# =================================================================================================

def test_the_registry_ships_at_least_six_patterns():
    """H6's first row. A registry with no entries is the Layer 1 defect at data scope: registry
    and matcher both green, both reachable, and the product detects nothing."""
    registry = seed_registry()
    assert len(registry) >= 6
    assert REQUIRED_PATTERNS.issubset({p.pattern_id for p in registry.all()})


def test_every_shipped_pattern_declares_a_rate_and_an_owner():
    """A pattern with no declared rate activates unmeasured, and the 10x guard has nothing to
    compare against. An owner is who reviews it when it misfires."""
    for pattern in seed_registry().all():
        assert pattern.expected_fire_rate.per_100_anchors_per_30d > 0
        assert "@" in pattern.owner, "the owner is a person, not a team alias nobody reads"
        assert pattern.first_evidence.positive and pattern.first_evidence.negative


def test_the_registry_is_data_on_disk_and_not_python():
    """Adding a detectable situation must be a registry entry, not an engineering change. If the
    seed patterns ever move into a `.py`, this is what says so."""
    files = sorted(p.name for p in SEED_DIR.glob("*.yaml"))
    assert len(files) >= 6
    assert not list(SEED_DIR.glob("*.py")), "patterns are declarative; a .py here is logic"


def test_reading_the_registry_twice_gives_the_same_order():
    a = [p.pattern_id for p in seed_registry().all()]
    b = [p.pattern_id for p in PatternRegistry(
        __import__("genios_engine.context.patterns.registry", fromlist=["x"])
        .load_directory(SEED_DIR)).all()]
    assert a == b == sorted(a)


# =================================================================================================
# Registration REFUSES, loudly, and that is the point of registration
# =================================================================================================

def test_an_unimplemented_condition_kind_is_refused_at_registration(pattern):
    """Doc 06's fourth failure mode: *"a condition references a missing capability → silent
    non-fire"*. A pattern that loads and can never hold is indistinguishable from a working one
    that found nothing, and nobody goes looking for it — which is exactly how Layer 1 shipped
    fifteen dead rules with a green suite.

    Proven by TAKING A KIND AWAY rather than by naming a fictional one: a guard nobody can
    demonstrate failing is a guard nobody can trust.
    """
    p = pattern(conditions=[{"kind": "cohort", "metric": "m", "op": "percentile_lte",
                             "value": 2500}])
    without_cohort = IMPLEMENTED_KINDS - {ConditionKind.COHORT}
    with pytest.raises(RegistrationError) as exc:
        validate_pattern(p, implemented=without_cohort)
    assert "no evaluator implements" in str(exc.value)
    validate_pattern(p)                       # and it passes against the real set


def test_a_fact_condition_may_not_claim_something_is_missing(pattern):
    """The single most important refusal in the schema. "There is no row" and "no connected source
    could have carried one" are the same empty result and opposite claims; absence is expressible
    only through `kind: absence`, which consumes the typed answer."""
    with pytest.raises(Exception):
        pattern(conditions=[{"kind": "fact", "field": "commitment.delivered_at",
                             "op": "missing"}])


def test_an_absence_condition_may_only_require_genuinely_absent(pattern):
    for refused in ("unknowable", "stale", "not_expected", "present"):
        with pytest.raises(PatternError):
            pattern(conditions=[{"kind": "absence", "field": "decision.scheduled",
                                 "type": refused}])


def test_an_unknown_reference_is_refused_rather_than_compared_as_a_string(pattern):
    """`@nonsense` would otherwise be compared as the literal string and never equal anything —
    the silent non-fire again, this time spelled as a typo.

    Written with `eq` rather than `gte` deliberately: a magnitude operator rejects an unknown
    reference one layer earlier (it is not a number), so `eq` is the spelling that actually
    reaches the reference check and proves it rather than the arity check standing in for it.
    """
    p = pattern(conditions=[{"kind": "fact", "field": "contract.tier", "op": "eq",
                             "value": "@budget_threshold"}])
    with pytest.raises(RegistrationError) as exc:
        validate_pattern(p)
    assert "unknown reference" in str(exc.value)

    with pytest.raises(PatternError):
        pattern(conditions=[{"kind": "fact", "field": "contract.value", "op": "gte",
                             "value": "@budget_threshold"}])


def test_the_authority_reference_is_refused_where_it_means_nothing(pattern):
    """A threshold compared with `eq` is not a threshold."""
    p = pattern(conditions=[{"kind": "fact", "field": "contract.value", "op": "eq",
                             "value": "@authority_threshold"}])
    with pytest.raises(RegistrationError):
        validate_pattern(p)


def test_a_pattern_with_no_conditions_is_refused(pattern):
    """A pattern with no conditions matches every anchor of its type — the "fires on everything"
    failure, with no way to measure it because it has nothing to be wrong about."""
    with pytest.raises(Exception):
        pattern(conditions=[])


def test_a_float_anywhere_in_a_pattern_is_refused(pattern):
    with pytest.raises(PatternError):
        pattern(conditions=[{"kind": "fact", "field": "contract.value", "op": "gte",
                             "value": 84_000.5}])
    # And in a field where NOTHING ELSE would catch it. `domain` is a list of strings and
    # `str(1.5)` is a perfectly good string, so without the recursive float sweep at the top of
    # `load_pattern` this one is accepted silently — which is how a float gets into a pattern
    # file in the first place: not in the threshold, where somebody is looking.
    with pytest.raises(PatternError):
        pattern(domain=[1.5])


def test_the_float_sweep_reaches_every_depth():
    """`no_float` is the doctrine, and it is recursive on purpose: a pattern is nested data and a
    float three levels down compares exactly as badly as one at the top."""
    from genios_engine.context.patterns.contract import no_float
    for nested in (1.5, [1, 2.5], {"a": {"b": [0.1]}}, ({"weights": [3.3]},)):
        with pytest.raises(PatternError):
            no_float(nested, "value")
    assert no_float({"a": [1, 2, {"b": "3"}]}, "value") == {"a": [1, 2, {"b": "3"}]}


def test_a_yaml_float_is_refused_at_load(tmp_path: Path):
    """`yaml.safe_load` turns `0.3` into a float without comment, and a float threshold compares
    differently on two machines. The loader refuses rather than converting."""
    from genios_engine.context.patterns.registry import load_pattern_file
    bad = tmp_path / "bad.yaml"
    bad.write_text("pattern_id: bad\nversion: 1\nanchor: {node_type: deal}\n"
                   "conditions: [{kind: fact, field: deal.amount, op: gte, value: 1.5}]\n"
                   "emits: {situation_type: x}\nowner: a@b.c\n"
                   "expected_fire_rate: {per_100_anchors_per_30d: 5}\n"
                   "first_evidence: {positive: x, negative: y}\n")
    with pytest.raises(PatternError):
        load_pattern_file(bad)


def test_a_misspelled_key_is_refused_rather_than_ignored(pattern):
    """A condition with an unread key is a condition that quietly does not do what it says. A
    pattern with four of its five conditions is not tighter, it is LOOSER, and it reads correctly
    in review."""
    with pytest.raises(Exception):
        pattern(conditions=[{"kind": "fact", "feild": "subscription.status", "op": "eq",
                             "value": "active"}])


def test_an_optional_signal_without_a_weight_is_refused():
    with pytest.raises(RegistrationError):
        load_pattern({"pattern_id": "p", "anchor": {"node_type": "deal"},
                      "conditions": [{"kind": "fact", "field": "deal.stage", "op": "exists"}],
                      "optional_signals": [{"kind": "observation", "kind_name": "verbal_yes"}],
                      "emits": {"situation_type": "x"}, "owner": "a@b.c",
                      "expected_fire_rate": {"per_100_anchors_per_30d": 5},
                      "first_evidence": {"positive": "x", "negative": "y"}})


def test_changing_a_pattern_without_a_new_version_is_refused(pattern):
    """A changed pattern needs a new version, or the situations it produced cannot be traced to
    what produced them."""
    registry = PatternRegistry([pattern()])
    with pytest.raises(RegistrationError):
        registry.register(pattern(conditions=[
            {"kind": "fact", "field": "subscription.status", "op": "eq", "value": "canceled"}]))
    registry.register(pattern(version=2, conditions=[
        {"kind": "fact", "field": "subscription.status", "op": "eq", "value": "canceled"}]))
    assert registry.get("test_pattern").version == 2


# =================================================================================================
# The gate row that matters: a pattern that fires on everything MAY NOT ACTIVATE
# =================================================================================================

def test_a_pattern_over_its_ceiling_cannot_activate():
    """H6: *"0 patterns activated while exceeding their expected fire rate 10x"*.

    `vendor_renewal_unowned` declares 3 per 100 anchors per 30 days, so its ceiling is 30. Firing
    on 90 of 100 anchors in a 30-day window is 90 per 100 per 30d — three times the ceiling and
    thirty times the declared rate — and activation is refused with the numbers in the refusal
    rather than a bare no.
    """
    pattern = seed_registry().get("vendor_renewal_unowned")
    loose = FireObservation("vendor_renewal_unowned", fires=90, anchors=100, window_days=30)
    decision = activation_decision(pattern, loose)
    assert isinstance(decision, ActivationDecision)
    assert decision.allowed is False
    assert decision.observed_rate == 90
    assert decision.ceiling_rate == 3 * FIRE_RATE_CAP_MULTIPLIER
    assert "matches everything is noise" in decision.reason


def test_a_pattern_inside_its_ceiling_activates():
    pattern = seed_registry().get("vendor_renewal_unowned")
    calm = FireObservation("vendor_renewal_unowned", fires=4, anchors=100, window_days=30)
    assert activation_decision(pattern, calm).allowed is True


def test_the_breach_test_does_not_divide_and_cannot_round_a_breach_away():
    """The arithmetic row. Two fires over three anchors in a WEEK is ~950 per 100 per 30 days
    against a declared 3 — a plain `fires // anchors` is 0, and an intermediate floor division at
    the wrong step reports no breach at all. `exceeds_expected` cross-multiplies instead.
    """
    pattern = seed_registry().get("vendor_renewal_unowned")
    tiny = FireObservation("vendor_renewal_unowned", fires=2, anchors=3, window_days=7)
    assert tiny.fires // tiny.anchors == 0, "the naive rate that would hide this"
    assert exceeds_expected(pattern, tiny) is True
    assert observed_rate_per_100_anchors_30d(tiny) > 0


def test_an_unobserved_pattern_may_still_activate():
    """A pattern must be able to run before anybody can know its rate. Refusing activation for
    want of evidence nobody could have collected makes the guard unfalsifiable."""
    pattern = seed_registry().get("founder_bottleneck")
    unseen = FireObservation("founder_bottleneck", fires=0, anchors=0, window_days=30)
    assert activation_decision(pattern, unseen).allowed is True


def test_the_registry_makes_both_failures_visible():
    """A pattern that never fires and a pattern that fires on everything are both defects, and a
    surface that reported only one of them would make the other one worse."""
    registry = seed_registry()
    observations = [
        FireObservation("vendor_renewal_unowned", fires=95, anchors=100, window_days=30),
        FireObservation("commitment_unresolved", fires=0, anchors=400, window_days=30)]
    breaching = breaching_patterns(registry, observations)
    assert [d.pattern_id for d in breaching] == ["vendor_renewal_unowned"]

    silent = silent_patterns(registry, observations)
    assert "commitment_unresolved" in silent, "fired zero times over 400 anchors"
    assert "founder_bottleneck" in silent, "no observation at all is the loudest silence"
    assert "vendor_renewal_unowned" not in silent
