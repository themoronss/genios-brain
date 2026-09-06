"""G1 · ALG-13 (L1.5.7-U1) — Rule 11 composition.

*A layer may lower confidence; it may only raise it by adding independent evidence, and it must
name that evidence.* Everything below tests one of five properties, and each maps to a way the
rule is broken in practice rather than in theory:

* **Composition can only fall, unless something new was named.** The load-bearing test is the
  generated one: over hundreds of random integer input sets, ``composed <= min(sources)``
  whenever no independent evidence came out of the fold. Five sources echoing one weak
  recollection must not compose into an 8900 — that failure "looks exactly like rigour", which
  is why a table of hand-picked rows is not enough to catch it.
* **The carve-out needs a NAME.** It raises the result, and it does so only when a genuinely
  separate origin was asserted AND that origin can be named. A boolean would let a caller waive
  Rule 11 by writing ``True``; a repeated name is an echo and is refused as one.
* **Authority orders it.** ALG-14's ladder decides which source is the base and how much a
  corroborator may lift it, so the composed value moves in the direction ``authority.py``
  orders and in no other.
* **W1 and W0 agree.** Every composed confidence is run through ``validate_publication`` and
  must never be rejected on V-6. Asserting that here rather than assuming it is the point: a
  composer that violated Rule 11 would not produce a wrong number, it would produce signals the
  publication gate drops three layers downstream from the cause.
* **Integers, end to end.** Asserted on the returned values AND over the module's own syntax
  tree, because "no float" is a property of the arithmetic, not of the outputs it happened to
  produce for the inputs a test chose.

MUTATION CHECK — deleting the ``min()`` clamp in ``enforce_rule_11`` fails
``test_a_prior_belief_caps_a_stronger_source_when_nothing_new_is_named``,
``test_the_clamp_is_recorded_rather_than_silent`` and the generated property test
``test_composition_never_exceeds_the_weakest_source_it_was_composed_from``. Deleting the
``min()`` in ``rule_11_ceiling`` fails ``test_the_ceiling_is_the_weakest_source``. Moving that
clamp back BEHIND the age decay — clamping the scalar and publishing the raw fold on the
``evidence`` axis, which is the shape this module shipped with — fails
``test_the_evidence_axis_of_an_echo_corpus_cannot_exceed_its_weakest_member``,
``test_the_evidence_axis_respects_the_ceiling_a_weak_aside_imposes``,
``test_the_scalar_really_is_the_evidence_axis_aged_by_the_freshness_axis``,
``test_every_published_axis_is_bounded_over_the_generated_corpus`` and the load-bearing
property above, and NOTHING else in the repository: `confidence_vector` is published on the
QES and V-6 reads only `confidence_bp`, which is why the axis escaped a green suite.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from genios_engine.capture.validate import confidence as confidence_module
from genios_engine.capture.validate.authority import Authority, multiplier_bp_of, rank_of
from genios_engine.capture.validate.confidence import (DEFAULT_AGE_DECAY_BP_PER_DAY,
                                                       ComposedConfidence, ConfidenceSource,
                                                       ConfidenceViolation, age_in_days,
                                                       combine, compose_confidence, corroborate,
                                                       decay, enforce_rule_11,
                                                       freshness_retained_bp, rule_11_ceiling)
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.publication import (PublicationOutcome, PublicationRule,
                                                 validate_publication)
from genios_engine.contracts.signal import (CONFIDENCE_COMPONENTS, QualifiedEnterpriseSignal,
                                            SignalType)
from genios_engine.contracts.visibility import Visibility

WAVE = "W1"
GATE = "G1"

#: The frozen instant every age computation here resolves against. A parameter, never a clock:
#: a test that decayed against "today" would pass on the day it was written and drift by one
#: basis point a day thereafter.
EVAL_TIME = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

#: Every provenance class, weakest first — used to assert that composition moves in the
#: direction ALG-14 orders. Derived from `rank_of` rather than restated, because THIS file is
#: not the authority on the ladder; `test_authority.py` is, and it asserts the ladder against
#: the document.
LADDER_WEAKEST_FIRST: tuple[Authority, ...] = tuple(sorted(Authority, key=rank_of))


def source(name: str, confidence_bp: int, *, independence_key: str | None,
           authority: Authority = Authority.EMAIL_PROSE,
           days_old: int = 0) -> ConfidenceSource:
    """A source with the defaults a test does not care about already chosen.

    `independence_key` is NOT one of them, and has no default here for the same reason it has
    none on `ConfidenceSource`: a helper that quietly answered the independence question would
    reintroduce inside the suite exactly the silence the field exists to remove. A test that
    wants the unstated group says `unstated(...)`.
    """
    return ConfidenceSource(name=name, confidence_bp=confidence_bp, authority=authority,
                            independence_key=independence_key, days_old=days_old)


def unstated(name: str, confidence_bp: int, **kwargs: Any) -> ConfidenceSource:
    """A source whose origin the caller explicitly declines to vouch for — combine-only."""
    return source(name, confidence_bp, independence_key=None, **kwargs)


# ============================================================================================
# COMBINE — same source. Doc 05's headline acceptance.
# ============================================================================================

#: `(a, b, expected)`. The first row is the doc's own acceptance, spelled out because it is the
#: one number in ALG-13 that a reader can check against the plan without doing arithmetic.
COMBINE_ROWS: tuple[tuple[int, int, int], ...] = (
    (8_000, 8_000, 6_400),      # doc 05: "combining two 8000s gives 6400"
    (10_000, 8_000, 8_000),     # certainty is the identity: it cannot dilute
    (8_000, 10_000, 8_000),     # ... from either side
    (0, 9_900, 0),              # nothing multiplied by anything is nothing
    (9_999, 9_999, 9_998),      # truncation rounds against the claim, never up
    (5_000, 5_000, 2_500),
    (3_333, 3_333, 1_110),      # 11108889 // 10000 -> 1110, not 1111
)


@pytest.mark.parametrize(("a", "b", "expected"), COMBINE_ROWS,
                         ids=[f"{a}x{b}" for a, b, _ in COMBINE_ROWS])
def test_combining_two_readings_of_one_source_multiplies(a: int, b: int, expected: int) -> None:
    assert combine(a, b) == expected


def test_the_doc_acceptance_is_neither_of_the_two_wrong_answers() -> None:
    """8000 would make the second reading free; 9000 would make it evidence. It is 6400."""
    result = combine(8_000, 8_000)
    assert result == 6_400
    assert result != 8_000
    assert result != 9_000


@pytest.mark.parametrize(("a", "b"), [(a, b) for a, b, _ in COMBINE_ROWS],
                         ids=[f"{a}x{b}" for a, b, _ in COMBINE_ROWS])
def test_combining_never_rises_above_either_input(a: int, b: int) -> None:
    """Re-reading a weak source cannot make it a strong one. This is Rule 11 in one line."""
    assert combine(a, b) <= min(a, b)


def test_combining_is_order_independent() -> None:
    assert combine(7_777, 3_333) == combine(3_333, 7_777)


@pytest.mark.parametrize("bad", [10_001, -1, 0.8, True],
                         ids=["above-range", "negative", "ratio", "bool"])
def test_combine_refuses_anything_that_is_not_basis_points(bad: Any) -> None:
    """A 0.8 that pydantic's lax mode would round to 0 is refused as the ratio it is."""
    with pytest.raises((TypeError, ValueError)):
        combine(bad, 5_000)


# ============================================================================================
# CORROBORATE — independent source, and the GUARD doc 05 states literally
# ============================================================================================


def test_a_named_independent_source_raises_the_value() -> None:
    assert corroborate(6_000, 8_000, evidence="chunk:msa_2026:3",
                       authority=Authority.SIGNED_DOCUMENT) > 6_000


@pytest.mark.parametrize("unnamed", ["", "   ", None], ids=["empty", "whitespace", "none"])
def test_a_raise_without_a_named_source_raises_confidence_violation(unnamed: Any) -> None:
    """Doc 05's GUARD verbatim: it raises, it does not warn."""
    with pytest.raises(ConfidenceViolation, match="Rule 11"):
        corroborate(6_000, 8_000, evidence=unnamed, authority=Authority.SIGNED_DOCUMENT)


def test_a_source_that_already_corroborated_cannot_corroborate_again() -> None:
    """A forwarded copy of an email is the same witness reading its own words back."""
    with pytest.raises(ConfidenceViolation, match="echo"):
        corroborate(7_000, 8_000, evidence="thread_8f2a", authority=Authority.EMAIL_PROSE,
                    already_named=("thread_8f2a",))


@pytest.mark.parametrize(("base", "other"),
                         [(0, 10_000), (5_000, 10_000), (9_000, 10_000), (9_999, 10_000),
                          (6_000, 3_000), (100, 100)],
                         ids=lambda v: str(v))
def test_corroboration_is_bounded_by_half_the_remaining_headroom(base: int,
                                                                 other: int) -> None:
    """Ten agreeing sources is very good and is still not certainty.

    The bound is what stops a chain of corroborations from walking to 10000: each step may take
    at most half of what is left, so the sequence converges below the ceiling instead of
    reaching it.
    """
    result = corroborate(base, other, evidence="doc_a", authority=Authority.SIGNED_DOCUMENT)
    assert base <= result <= base + (10_000 - base) // 2
    assert result <= 10_000


def test_a_weak_witness_lifts_almost_nothing() -> None:
    """Agreeing weakly is not the same as agreeing: the lift is proportional to the witness."""
    strong = corroborate(6_000, 9_000, evidence="doc_a", authority=Authority.SIGNED_DOCUMENT)
    weak = corroborate(6_000, 1_000, evidence="doc_a", authority=Authority.SIGNED_DOCUMENT)
    assert weak < strong
    assert weak - 6_000 <= 200


@pytest.mark.parametrize("authority", LADDER_WEAKEST_FIRST,
                         ids=[a.value for a in LADDER_WEAKEST_FIRST])
def test_the_lift_is_damped_by_the_corroborator_s_own_authority(authority: Authority) -> None:
    """A Slack aside corroborating a contract lifts it less than a second contract does."""
    lifted = corroborate(6_000, 8_000, evidence="doc_a", authority=authority)
    ceiling = corroborate(6_000, 8_000, evidence="doc_a", authority=Authority.SIGNED_DOCUMENT)
    assert lifted <= ceiling
    assert lifted - 6_000 == (ceiling - 6_000) * multiplier_bp_of(authority) // 10_000


def test_the_lift_rises_monotonically_with_the_ladder() -> None:
    lifts = [corroborate(6_000, 8_000, evidence="doc_a", authority=a)
             for a in LADDER_WEAKEST_FIRST]
    assert lifts == sorted(lifts)
    assert lifts[0] < lifts[-1]


# ============================================================================================
# AGE DECAY and the freshness axis
# ============================================================================================


@pytest.mark.parametrize(("days", "expected"),
                         [(0, 10_000), (1, 9_980), (30, 9_400), (180, 6_400), (500, 0),
                          (10_000, 0)],
                         ids=["today", "yesterday", "a-month", "six-months", "the-floor",
                              "long-dead"])
def test_freshness_is_the_retained_share_and_floors_at_zero(days: int, expected: int) -> None:
    assert freshness_retained_bp(days) == expected


def test_decay_is_monotonically_decreasing_over_age() -> None:
    values = [decay(9_000, days_old=days) for days in range(0, 260, 5)]
    assert values == sorted(values, reverse=True)
    assert values[0] == 9_000
    assert values[-1] < values[0]


@pytest.mark.parametrize("days", [0, 1, 7, 45, 365, 900], ids=lambda v: f"{v}d")
def test_decay_never_raises_a_confidence(days: int) -> None:
    assert decay(7_400, days_old=days) <= 7_400


def test_decay_composes_from_the_freshness_axis_rather_than_recomputing_it() -> None:
    """The displayed freshness and the applied freshness are the same number, by construction."""
    assert decay(8_000, days_old=90) == 8_000 * freshness_retained_bp(90) // 10_000


def test_the_decay_rate_is_the_one_constant_every_axis_reads() -> None:
    """The documented shape: nothing survives 10000/RATE days, and the day before it still does.

    Tied to the constant rather than to the literal 20 so that re-tuning the rate re-tunes this
    assertion with it — a test that restated 500 would have to be edited by whoever changes the
    rate, and the one they forget is the one that stops meaning anything.
    """
    dead = 10_000 // DEFAULT_AGE_DECAY_BP_PER_DAY
    assert freshness_retained_bp(dead) == 0
    assert freshness_retained_bp(dead - 1) > 0
    assert freshness_retained_bp(30) == freshness_retained_bp(
        30, decay_bp_per_day=DEFAULT_AGE_DECAY_BP_PER_DAY)


def test_the_decay_rate_is_a_parameter_not_a_constant_in_the_arithmetic() -> None:
    assert decay(8_000, days_old=10, decay_bp_per_day=100) < decay(8_000, days_old=10)
    assert freshness_retained_bp(10, decay_bp_per_day=0) == 10_000


@pytest.mark.parametrize("bad", [-1, 0.5, True], ids=["negative", "ratio", "bool"])
def test_age_must_be_a_whole_non_negative_number_of_days(bad: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        decay(8_000, days_old=bad)


# ============================================================================================
# age_in_days — the clock arrives as a parameter
# ============================================================================================


@pytest.mark.parametrize(("delta", "expected"),
                         [(timedelta(0), 0), (timedelta(hours=23), 0), (timedelta(days=1), 1),
                          (timedelta(days=1, hours=23), 1), (timedelta(days=180), 180)],
                         ids=["same-instant", "under-a-day", "a-day", "nearly-two", "half-year"])
def test_age_counts_whole_elapsed_days(delta: timedelta, expected: int) -> None:
    assert age_in_days(EVAL_TIME - delta, eval_time=EVAL_TIME) == expected


def test_evidence_stamped_in_the_future_floors_at_zero_rather_than_going_negative() -> None:
    """A clock-skewed connector must not be able to multiply a confidence above itself."""
    assert age_in_days(EVAL_TIME + timedelta(days=3), eval_time=EVAL_TIME) == 0
    assert decay(8_000, days_old=age_in_days(EVAL_TIME + timedelta(days=3),
                                             eval_time=EVAL_TIME)) == 8_000


def test_a_naive_datetime_is_refused_rather_than_assumed_utc() -> None:
    with pytest.raises(ValueError):
        age_in_days(datetime(2026, 1, 1), eval_time=EVAL_TIME)


def test_the_module_reads_no_clock() -> None:
    """G1's group law, asserted on the syntax tree rather than on a grep of the file text.

    A deliberate purity check: `datetime.now()` in this module would resolve last March's
    evidence against today on every replay, and no output assertion can see that.
    """
    tree = ast.parse(inspect.getsource(confidence_module))
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert "now" not in called
    assert "today" not in called
    assert "utcnow" not in called


# ============================================================================================
# Rule 11's ceiling — the same arithmetic V-6 runs
# ============================================================================================


@pytest.mark.parametrize(("sources", "expected"),
                         [((8_000,), 8_000), ((8_000, 3_000), 3_000),
                          ((3_000, 8_000, 9_900), 3_000), ((), None), ((0, 9_000), 0)],
                         ids=["one", "two", "three", "none", "zero-floors-it"])
def test_the_ceiling_is_the_weakest_source(sources: tuple[int, ...],
                                           expected: int | None) -> None:
    assert rule_11_ceiling(sources) == expected


def test_an_empty_source_list_means_the_rule_did_not_apply_not_that_it_passed() -> None:
    """`None`, not 10000 and not 0 — the distinction W0 draws in the same words."""
    assert rule_11_ceiling(()) is None
    assert enforce_rule_11(9_900, ceiling_bp=None) == 9_900


def test_the_ceiling_clamps_a_value_that_exceeds_the_weakest_source() -> None:
    assert enforce_rule_11(9_000, ceiling_bp=4_000) == 4_000


def test_a_value_under_the_ceiling_is_untouched() -> None:
    assert enforce_rule_11(3_000, ceiling_bp=4_000) == 3_000


def test_naming_independent_evidence_raises_the_ceiling_by_what_it_earned() -> None:
    """This test used to read, in full:

        def test_naming_independent_evidence_lifts_the_ceiling() -> None:
            assert enforce_rule_11(9_000, ceiling_bp=4_000,
                                   independent_evidence=("chunk:msa_2026:3",)) == 9_000

    which asserted the defect. `== 9_000` is the ceiling not merely lifted but DELETED: the
    value comes back exactly as it went in, so the 4000 had no effect at all. Doc 05 says the
    named-source case "raises but stays bounded", and Rule 11 says a layer may raise a
    confidence *by adding* independent evidence — by the size of the addition. The bound is
    therefore one `corroborate` step with the ceiling as its base, and the assertions below
    pin all three of its properties: it raises, it is exactly that step, and it lands short of
    the unbounded value the old line demanded.
    """
    lifted = enforce_rule_11(9_000, ceiling_bp=4_000,
                             independent_evidence=("chunk:msa_2026:3",), lift_bp=9_000,
                             lift_authority=Authority.SIGNED_DOCUMENT)
    assert lifted > 4_000
    assert lifted == corroborate(4_000, 9_000, evidence="chunk:msa_2026:3",
                                 authority=Authority.SIGNED_DOCUMENT)
    assert lifted < 9_000


def test_a_named_source_that_earned_nothing_lifts_the_ceiling_by_nothing() -> None:
    """The fail-closed end of the same seam: a name with no stated worth buys no headroom, so
    an omitted `lift_bp` yields the unwaived ceiling rather than an exemption."""
    assert enforce_rule_11(9_000, ceiling_bp=4_000,
                           independent_evidence=("chunk:msa_2026:3",)) == 4_000


@pytest.mark.parametrize("empty", [(), ("",), ("   ",)],
                         ids=["nothing", "empty-name", "whitespace-name"])
def test_an_unnameable_waiver_is_not_a_waiver(empty: tuple[str, ...]) -> None:
    """A boolean could be set to True. A name is a thing a human can go and check — so a blank
    one is refused rather than accepted as a waiver nobody can follow up."""
    if empty == ():
        assert enforce_rule_11(9_000, ceiling_bp=4_000, independent_evidence=empty) == 4_000
    else:
        with pytest.raises(ValueError):
            enforce_rule_11(9_000, ceiling_bp=4_000, independent_evidence=empty)


# ============================================================================================
# compose_confidence — the unit entry point
# ============================================================================================


def test_two_readings_of_one_unstated_source_compose_downward() -> None:
    result = compose_confidence([unstated("a", 8_000), unstated("b", 8_000)])
    assert result.confidence_bp == 6_400
    assert result.independent_evidence == ()
    assert result.ceiling_bp == 8_000


def test_two_named_independent_sources_compose_upward() -> None:
    result = compose_confidence([
        source("msa.pdf", 8_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
        source("thread_8f2a", 8_000, authority=Authority.SIGNED_DOCUMENT,
               independence_key="mail")])
    assert result.confidence_bp > 8_000
    assert result.independent_evidence == ("thread_8f2a",)
    assert result.confidence_bp == corroborate(8_000, 8_000, evidence="thread_8f2a",
                                               authority=Authority.SIGNED_DOCUMENT)


def test_the_carve_out_fires_only_when_a_separate_origin_is_actually_asserted() -> None:
    """Same numbers, same authorities, same names. The ONLY difference is the stated origin."""
    echoed = compose_confidence([source("a", 8_000, independence_key="one"),
                                 source("b", 8_000, independence_key="one")])
    corroborated = compose_confidence([source("a", 8_000, independence_key="one"),
                                       source("b", 8_000, independence_key="two")])
    assert echoed.independent_evidence == ()
    assert echoed.confidence_bp == 6_400
    assert corroborated.independent_evidence == ("b",)
    assert corroborated.confidence_bp > echoed.confidence_bp


def test_the_same_source_named_twice_under_two_keys_is_still_an_echo() -> None:
    """The defence against relabelling one witness as two: the NAMES must be new, not the key."""
    result = compose_confidence([source("thread_8f2a", 8_000, independence_key="one"),
                                 source("thread_8f2a", 7_000, independence_key="two")])
    assert result.independent_evidence == ()
    assert result.confidence_bp <= 7_000


def test_an_unstated_source_can_only_ever_cost_confidence() -> None:
    """Fail-closed: what the caller did not vouch for lowers, and can never lift."""
    alone = compose_confidence([source("msa.pdf", 9_000,
                                       authority=Authority.SIGNED_DOCUMENT,
                                       independence_key="doc")])
    with_echo = compose_confidence([
        source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
        unstated("slack_aside", 3_000, authority=Authority.CHAT_ASIDE)])
    assert with_echo.confidence_bp < alone.confidence_bp
    assert with_echo.confidence_bp <= 3_000


def test_composition_is_invariant_under_permutation_of_the_input() -> None:
    """The fold chooses its own order, so the caller's list order cannot change the answer."""
    sources = [source("a", 8_100, authority=Authority.SIGNED_DOCUMENT, independence_key="k1"),
               source("b", 6_200, authority=Authority.EMAIL_PROSE, independence_key="k2"),
               source("c", 4_400, authority=Authority.CHAT_ASIDE, independence_key="k3"),
               unstated("d", 7_300, authority=Authority.ATTACHMENT)]
    expected = compose_confidence(sources)
    rng = random.Random(20260905)
    for _ in range(50):
        shuffled = sources[:]
        rng.shuffle(shuffled)
        assert compose_confidence(shuffled).confidence_bp == expected.confidence_bp


def test_the_strongest_authority_is_the_base_and_the_weaker_source_corroborates_it() -> None:
    """Order is a choice this module makes, and the choice is ALG-14's own ordering.

    Asserted against BOTH candidate folds: the composed value equals corroborating the signed
    document with the chat aside, and is not the value the reverse fold would have produced.
    """
    signed = source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT,
                    independence_key="doc")
    aside = source("slack_1", 6_000, authority=Authority.CHAT_ASIDE, independence_key="chat")
    result = compose_confidence([aside, signed])
    authority_first = corroborate(9_000, 6_000, evidence="slack_1",
                                  authority=Authority.CHAT_ASIDE)
    reversed_fold = corroborate(6_000, 9_000, evidence="msa.pdf",
                                authority=Authority.SIGNED_DOCUMENT)
    assert result.fold_bp == authority_first
    assert result.fold_bp != reversed_fold
    # ...and BOTH published numbers are that fold clamped to the bounded raise, because 9195 is
    # above every source this rests on and a 6000-bp chat aside does not buy 3195 bp of lift.
    # `evidence_bp` is asserted alongside the scalar rather than against the raw fold: it is a
    # key of the published `confidence_vector`, so the ceiling has to reach it too. The raw
    # fold stays visible on `fold_bp`, which is audit and is not published anywhere.
    sanctioned = corroborate(6_000, 6_000, evidence="slack_1", authority=Authority.CHAT_ASIDE)
    assert result.confidence_bp == sanctioned
    assert result.evidence_bp == sanctioned
    assert result.vector["evidence"] == sanctioned
    assert result.clamped is True


@pytest.mark.parametrize("authority", LADDER_WEAKEST_FIRST,
                         ids=[a.value for a in LADDER_WEAKEST_FIRST])
def test_a_stronger_corroborator_composes_to_a_higher_confidence(authority: Authority) -> None:
    """Authority weighting moves the result in the direction `authority.py` orders."""
    base = source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc")
    weakest = compose_confidence([base, source("w", 5_000, authority=LADDER_WEAKEST_FIRST[0],
                                               independence_key="other")])
    tested = compose_confidence([base, source("w", 5_000, authority=authority,
                                              independence_key="other")])
    strongest = compose_confidence([base, source("w", 5_000,
                                                 authority=LADDER_WEAKEST_FIRST[-1],
                                                 independence_key="other")])
    assert weakest.confidence_bp <= tested.confidence_bp <= strongest.confidence_bp


def test_the_ladder_ordering_is_strict_across_the_whole_ladder() -> None:
    base = source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc")
    composed = [compose_confidence([base, source("w", 5_000, authority=a,
                                                 independence_key="other")]).confidence_bp
                for a in LADDER_WEAKEST_FIRST]
    assert composed == sorted(composed)
    assert composed[0] < composed[-1]


def test_age_decays_by_the_newest_supporting_source_not_the_oldest() -> None:
    """Doc 05 defines the freshness axis on the newest evidence: one ancient source must not
    bury a claim that fresher evidence still supports."""
    result = compose_confidence([unstated("old", 9_000, days_old=200),
                                 source("new", 9_000, days_old=10, independence_key="k")])
    assert result.freshness_bp == freshness_retained_bp(10)


def test_a_stale_signal_reads_as_stale_in_both_the_scalar_and_the_vector() -> None:
    fresh = compose_confidence([unstated("a", 9_000, days_old=0)])
    stale = compose_confidence([unstated("a", 9_000, days_old=120)])
    assert stale.confidence_bp < fresh.confidence_bp
    assert stale.freshness_bp < fresh.freshness_bp
    assert stale.evidence_bp == fresh.evidence_bp        # the TEXT support did not change


# --- the prior: Rule 11 read literally, and the clamp's live path ---------------------------


def test_a_prior_belief_caps_a_stronger_source_when_nothing_new_is_named() -> None:
    """*A layer may lower confidence; it may only raise it by adding independent evidence.*

    The previous layer believed 4000. Re-reading the same corpus and arriving at 9000 is not
    new evidence, it is a different opinion — and Rule 11 does not let an opinion raise a
    number.
    """
    result = compose_confidence([unstated("a", 9_000)], prior_bp=4_000)
    assert result.confidence_bp == combine(4_000, 9_000)
    assert result.confidence_bp < 4_000
    assert result.independent_evidence == ()


def test_the_clamp_is_recorded_rather_than_silent() -> None:
    """A clamp nobody can see is indistinguishable from a composer that never overshoots."""
    clamped = compose_confidence(
        [source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
         source("hubspot_deal", 9_000, authority=Authority.STRUCTURED_SOURCE,
                independence_key="crm")],
        prior_bp=1_000)
    clear = compose_confidence([unstated("a", 3_000)], prior_bp=4_000)
    assert clamped.clamped is True
    assert clamped.ceiling_bp == 1_000
    # The ceiling bound the EVIDENCE — that is what a Rule 11 clamp is — and `fold_bp` records
    # what the arithmetic wanted, so the clamp is visible in magnitude and not only as a flag.
    # This used to read `confidence_bp < evidence_bp`, which described a composer that clamped
    # the aged scalar and published the unclamped axis beside it.
    assert clamped.evidence_bp < clamped.fold_bp
    assert clamped.confidence_bp < clamped.fold_bp
    assert clear.clamped is False
    assert clear.confidence_bp == combine(4_000, 3_000)


def test_named_independent_evidence_lets_a_composition_exceed_the_prior() -> None:
    """The exception the rule itself names — and the only way past the prior."""
    result = compose_confidence(
        [source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
         source("hubspot_deal", 9_000, authority=Authority.STRUCTURED_SOURCE,
                independence_key="crm")],
        prior_bp=4_000)
    assert result.confidence_bp > 4_000
    # Both sources are named now, and that is the fix rather than a side effect: with the prior
    # as the base of the fold, the signed document CORROBORATES the incumbent 4000 instead of
    # replacing it, so it is independent evidence that lifted the value and V-6 must be told so.
    assert result.independent_evidence == ("msa.pdf", "hubspot_deal")
    assert result.confidence_bp == corroborate(4_000, 9_000, evidence="msa.pdf",
                                               authority=Authority.SIGNED_DOCUMENT)
    assert result.clamped is True


def test_the_prior_is_reported_as_a_source_so_v6_computes_the_same_ceiling() -> None:
    result = compose_confidence([unstated("a", 9_000)], prior_bp=4_000)
    assert result.source_confidences == (4_000, 9_000)
    assert rule_11_ceiling(result.source_confidences) == result.ceiling_bp


def test_the_composed_value_is_never_reported_as_its_own_source() -> None:
    """Passing the result back in as a source would make V-6 trivially true."""
    result = compose_confidence([unstated("a", 8_000), unstated("b", 8_000)])
    assert result.confidence_bp not in result.source_confidences


# --- the vector -----------------------------------------------------------------------------


def test_the_vector_carries_exactly_the_four_components_the_contract_names() -> None:
    vector = compose_confidence([unstated("a", 8_000)], expertise_bp=5_500,
                                coverage_bp=4_100).vector
    assert set(vector) == set(CONFIDENCE_COMPONENTS)
    assert all(isinstance(value, int) and not isinstance(value, bool)
               for value in vector.values())


def test_layer_1_leaves_expertise_at_zero() -> None:
    """Doc 05 assigns the expertise axis to L3. L1 must not invent a number for it."""
    assert compose_confidence([unstated("a", 8_000)]).expertise_bp == 0


@pytest.mark.parametrize(("expertise", "coverage"), [(0, 0), (9_900, 0), (0, 9_900),
                                                     (9_900, 9_900)],
                         ids=["neither", "expertise", "coverage", "both"])
def test_expertise_and_coverage_are_never_collapsed_into_the_scalar(expertise: int,
                                                                    coverage: int) -> None:
    """Globe's open blocker is the collapse itself: folding coverage in would express "we have
    no domain pack loaded" as "this contract value is probably wrong"."""
    baseline = compose_confidence([unstated("a", 8_000)]).confidence_bp
    result = compose_confidence([unstated("a", 8_000)], expertise_bp=expertise,
                                coverage_bp=coverage)
    assert result.confidence_bp == baseline
    assert result.expertise_bp == expertise
    assert result.coverage_bp == coverage


# --- refusals --------------------------------------------------------------------------------


def test_a_confidence_composed_from_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        compose_confidence([])


@pytest.mark.parametrize(("field", "bad"),
                         [("name", ""), ("name", "   "), ("confidence_bp", 10_001),
                          ("confidence_bp", -1), ("confidence_bp", 0.8),
                          ("independence_key", ""), ("days_old", -1)],
                         ids=["blank-name", "whitespace-name", "above-range", "negative",
                              "ratio", "blank-key", "negative-age"])
def test_a_source_refuses_the_input_that_would_make_it_unnameable_or_unrankable(
        field: str, bad: Any) -> None:
    kwargs: dict[str, Any] = {"name": "a", "confidence_bp": 8_000, "independence_key": "k"}
    kwargs[field] = bad
    with pytest.raises((TypeError, ValueError)):
        ConfidenceSource(**kwargs)


def test_a_source_is_frozen_so_one_claim_cannot_acquire_two_confidences() -> None:
    """A caller that edits a source between two calls is how one signal gets two confidences."""
    built = unstated("a", 8_000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        built.confidence_bp = 9_000                                    # type: ignore[misc]


# ============================================================================================
# THE PROPERTY — over generated integer input sets
# ============================================================================================

#: Deterministic by seed: a property test that generates a different corpus every run reports a
#: failure nobody can reproduce, which is worse than a smaller corpus that always can be.
_SEED = 20_260_905
_CASES = 400

_KEYS: tuple[str | None, ...] = (None, None, "k1", "k2", "k3")


def _random_sources(rng: random.Random) -> list[ConfidenceSource]:
    return [ConfidenceSource(name=f"src_{index}_{rng.randrange(3)}",
                             confidence_bp=rng.randrange(0, 10_001),
                             authority=rng.choice(list(Authority)),
                             independence_key=rng.choice(_KEYS),
                             days_old=rng.randrange(0, 400))
            for index in range(rng.randrange(1, 6))]


def sanctioned_raise(ceiling_bp: int, sources: list[ConfidenceSource],
                     named: tuple[str, ...]) -> int:
    """The highest Rule 11 permits above `ceiling_bp`: ONE corroborate step, by the best of the
    sources the fold actually named.

    Computed here from the raw inputs rather than read off the result, so the assertion does
    not simply restate whatever the module decided. It is an UPPER bound on the module's own
    figure — the module corroborates with a group's folded confidence, which `combine` can only
    have pushed at or below the strongest member's, and that member is always among the names.
    A test that is loose in this direction still catches an exemption, which is unbounded.
    """
    return max(corroborate(ceiling_bp, item.confidence_bp, evidence=item.name,
                           authority=item.authority)
               for item in sources if item.name in named)


def test_composition_never_exceeds_the_weakest_source_it_was_composed_from() -> None:
    """THE load-bearing test. Rule 11, over 400 generated integer input sets.

    Three assertions, and the third is new. This test used to end at the second:

        if result.confidence_bp > ceiling:
            above_ceiling += 1
            assert result.independent_evidence, (...)

    — i.e. it asserted only that SOMETHING was named whenever the value sat above the ceiling,
    and never how far above. That is true of a correct composer and equally true of one that
    treats any single name as an exemption and returns the raw fold, so the property passed
    against a module in which one 100-bp Slack aside lifted a ceiling of 100 to 9003. The
    unbounded case is exactly the failure doc 05 calls out as looking "exactly like rigour",
    and an unbounded implementation is what a corpus with no bound assertion cannot see.

    So: below the ceiling by default; above it only with a name; and above it by no more than
    that name earned.
    """
    rng = random.Random(_SEED)
    above_ceiling = 0
    for _ in range(_CASES):
        sources = _random_sources(rng)
        prior = rng.choice([None, rng.randrange(0, 10_001)])
        result = compose_confidence(sources, prior_bp=prior)
        ceiling = min(result.source_confidences)
        if result.confidence_bp > ceiling:
            above_ceiling += 1
            assert result.independent_evidence, (
                f"composed {result.confidence_bp} above the ceiling {ceiling} with no "
                f"independent evidence named: {sources}")
            bound = sanctioned_raise(ceiling, sources, result.independent_evidence)
            assert result.confidence_bp <= bound, (
                f"composed {result.confidence_bp} above the sanctioned raise {bound} from a "
                f"ceiling of {ceiling}: naming bought an exemption, not a raise: {sources}")
        else:
            assert result.confidence_bp <= ceiling

        # The same bound on the PUBLISHED axis, and asked SEPARATELY rather than inside the
        # branch above: `confidence_vector` is a field on the QES and V-6 reads only
        # `confidence_bp`, so an evidence axis that escapes the ceiling escapes onto a card
        # with nothing downstream to catch it — including in the cases where age happened to
        # pull the scalar back under the ceiling and hid the escape.
        axis_bound = (sanctioned_raise(ceiling, sources, result.independent_evidence)
                      if result.independent_evidence else ceiling)
        assert result.vector["evidence"] <= axis_bound, (
            f"the evidence AXIS is {result.vector['evidence']}, above the bound {axis_bound} "
            f"for a ceiling of {ceiling}: the clamp reached the scalar and not the vector, "
            f"and the vector is what gets published: {sources}")
    assert above_ceiling > 0, ("no generated case exercised the carve-out — the corpus is not "
                               "testing the branch it was written for")


def test_every_generated_composition_is_integer_basis_points() -> None:
    """No float, no bool, no out-of-range — on the scalar and on all four vector axes."""
    rng = random.Random(_SEED + 1)
    for _ in range(_CASES):
        result = compose_confidence(_random_sources(rng))
        values = [result.confidence_bp, *result.vector.values(), *result.source_confidences]
        for value in values:
            assert type(value) is int, f"{value!r} is {type(value).__name__}, not int"
            assert 0 <= value <= 10_000


def test_composition_with_no_stated_origin_can_only_fall() -> None:
    """The echo case in isolation: every source unstated, so the ceiling must always bind."""
    rng = random.Random(_SEED + 2)
    for _ in range(_CASES):
        sources = [ConfidenceSource(name=f"src_{index}",
                                    confidence_bp=rng.randrange(0, 10_001),
                                    independence_key=None,
                                    authority=rng.choice(list(Authority)),
                                    days_old=rng.randrange(0, 400))
                   for index in range(rng.randrange(1, 6))]
        result = compose_confidence(sources)
        assert result.independent_evidence == ()
        assert result.confidence_bp <= min(source.confidence_bp for source in sources)


def test_the_module_computes_no_float_anywhere_not_even_transiently() -> None:
    """A deliberate purity check over the syntax tree — G1's group law, mechanised.

    Asserted on the AST rather than on the returned values because "integer arithmetic" is a
    property of the code: a single `/` that happened to divide evenly for the inputs a test
    chose would pass every output assertion in this file and still put a binary fraction into a
    confidence the day the numbers changed.
    """
    tree = ast.parse(inspect.getsource(confidence_module))
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)), \
            "true division in an integer basis-point module"
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), \
            f"float literal {node.value!r}"
        assert not (isinstance(node, ast.Name) and node.id == "float"), "a float conversion"


# ============================================================================================
# CROSS-WAVE — W1's arithmetic against W0's gate
# ============================================================================================


def _signal(composed: ComposedConfidence, span: Any) -> QualifiedEnterpriseSignal:
    """A minimal valid C-12 carrying a composed confidence and its vector.

    Minimal on purpose: every field here that is not the confidence is the smallest value that
    passes its own validator, so a V-6 failure in the assertions below can only have come from
    the composition. The extraction is the shell C-09 requires and nothing more — this test is
    about the trust fields, and a fully-populated extraction would only add ways for it to fail
    for reasons that are not ALG-13's.
    """
    return QualifiedEnterpriseSignal(
        org_id="org_7173",
        trace_id="trace_alg13",
        visibility=Visibility(),
        signal_id="sig_alg13",
        event_id="evt_alg13",
        source="gmail",
        object_type="email_message",
        occurred_at=EVAL_TIME - timedelta(days=1),
        signal_type=SignalType.CONTRACT_RENEWAL,
        importance_bp=7_800,
        triage_lane="P1",
        extraction=ExtractionResult(intent="inform", stance="neutral",
                                    model_snapshot="claude-3-5-haiku-20241022",
                                    prompt_version="l1.s2.email.v3", schema_version="l1.v2.0",
                                    extraction_profile="email", input_tokens=10,
                                    output_tokens=5),
        evidence_refs=[span],
        conflicts=[],
        confidence_bp=composed.confidence_bp,
        confidence_vector=dict(composed.vector),
        coverage_ready=True,
        state="active",
        supersedes=None,
        expires_at=None,
        internal_kind=None,
        recipients=("rohit@antler.co",),
        versions={"prompt": "l1.s2.email.v3", "schema": "l1.v2.0"})


@pytest.fixture
def verified_span(span_of):
    """One verified receipt, so V-4 has something and V-5 has nothing to downgrade."""
    return span_of("the $84K annual contract", verified=True)


def test_a_clamped_composition_publishes_without_tripping_v6(verified_span) -> None:
    """W1 and W0 agree, asserted rather than assumed — the whole point of this block."""
    composed = compose_confidence([unstated("a", 8_000), unstated("b", 8_000)])
    decision = validate_publication(_signal(composed, verified_span),
                                    source_confidences=list(composed.source_confidences),
                                    independent_evidence=composed.independent_evidence)
    assert PublicationRule.V6 not in [failure.rule for failure in decision.failures]
    assert decision.outcome is PublicationOutcome.EMIT


def test_a_corroborated_composition_publishes_with_v6_recorded_as_waived(verified_span) -> None:
    """Above the ceiling, and legal — because the fold named what put it there, and the gate
    records the waiver rather than merely honouring it."""
    composed = compose_confidence([
        source("msa.pdf", 8_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
        source("hubspot_deal", 8_000, authority=Authority.STRUCTURED_SOURCE,
               independence_key="crm")])
    assert composed.confidence_bp > min(composed.source_confidences)
    decision = validate_publication(_signal(composed, verified_span),
                                    source_confidences=list(composed.source_confidences),
                                    independent_evidence=composed.independent_evidence)
    assert PublicationRule.V6 not in [failure.rule for failure in decision.failures]
    assert PublicationRule.V6 in decision.waived
    assert decision.outcome is PublicationOutcome.EMIT


def test_the_gate_rejects_the_composition_this_module_refuses_to_produce(verified_span) -> None:
    """The negative control: V-6 is a live rule, not a check that never fires.

    Hand the gate the value the fold would have produced WITHOUT the ceiling — the same
    arithmetic with the clamp removed — and it is rejected. That is what the clamp is buying,
    and a suite that never showed the rejection would be asserting against a dead rule.
    """
    composed = compose_confidence(
        [source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
         source("hubspot_deal", 9_000, authority=Authority.STRUCTURED_SOURCE,
                independence_key="crm")],
        prior_bp=1_000)
    assert composed.fold_bp > composed.confidence_bp
    unclamped = _signal(composed, verified_span).model_copy(
        update={"confidence_bp": composed.fold_bp})
    decision = validate_publication(unclamped,
                                    source_confidences=list(composed.source_confidences))
    assert PublicationRule.V6 in [failure.rule for failure in decision.failures]
    assert decision.outcome is PublicationOutcome.REJECT


def test_every_generated_composition_survives_the_publication_gate(verified_span) -> None:
    """The property, carried across the wave seam: no generated input set produces a signal the
    V-6 rule drops. A composer that violated Rule 11 would not return a wrong number here — it
    would return one that dies at a gate three layers downstream from the cause."""
    rng = random.Random(_SEED + 3)
    for _ in range(60):
        sources = _random_sources(rng)
        composed = compose_confidence(sources,
                                      prior_bp=rng.choice([None, rng.randrange(0, 10_001)]))
        decision = validate_publication(
            _signal(composed, verified_span),
            source_confidences=list(composed.source_confidences),
            independent_evidence=composed.independent_evidence)
        assert PublicationRule.V6 not in [failure.rule for failure in decision.failures], (
            f"V-6 rejected a composition this module produced: {composed}")


# ============================================================================================
# THE BOUND — Rule 11's carve-out is a bounded RAISE, never an exemption (D2)
# ============================================================================================
#
# Doc 05, L1.5.7-U1: *"corroboration from a named independent source raises but stays bounded"*.
# The three tests below are the ones the suite was missing: the original generated property only
# ever asserted that `independent_evidence` was NON-EMPTY when the value sat above the ceiling,
# which is true of a correct composer AND of one that discards the ceiling entirely the moment
# any single name appears. A ceiling that one Slack aside can delete "looks exactly like rigour"
# — the module docstring's own words for the failure this unit exists to prevent.


def test_a_single_named_corroborator_buys_a_bounded_raise_not_an_exemption() -> None:
    """One named corroborator must not waive the ceiling wholesale.

    The numbers are chosen so the gap is impossible to read as rounding: a prior of 2000, a
    signed document at 9000 from one origin, a Slack aside at 100 from another. The weakest
    thing this belief rests on is the 100, and what the CORROBORATE arithmetic actually earns
    on top of it is a few hundred basis points. An exemption hands back the whole 9000.
    """
    composed = compose_confidence(
        [source("signed.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT,
                independence_key="docA"),
         source("slack", 100, authority=Authority.CHAT_ASIDE, independence_key="slackB")],
        prior_bp=2_000)
    assert composed.ceiling_bp == 100
    assert composed.independent_evidence, "the carve-out did fire — that is not the defect"
    sanctioned = max(corroborate(100, bp, evidence=name, authority=auth)
                     for name, bp, auth in (("signed.pdf", 9_000, Authority.SIGNED_DOCUMENT),
                                            ("slack", 100, Authority.CHAT_ASIDE)))
    assert composed.confidence_bp <= sanctioned, (
        f"composed {composed.confidence_bp} from a ceiling of {composed.ceiling_bp}: the "
        f"sanctioned raise is {sanctioned}, everything above it is an exemption")


def test_a_prior_that_lowered_belief_is_the_base_the_new_evidence_lifts() -> None:
    """*A layer may lower confidence.* A layer that did must not be silently overridden.

    The prior is 1000 — some layer looked at this claim and qualified it hard. Two strong,
    genuinely independent sources then arrive. Rule 11 lets them RAISE that 1000 by the bounded
    corroborate step; it does not let them restart the fold from 9000 and hand the 1000 back as
    a ceiling that the very same corroboration then waives.
    """
    composed = compose_confidence(
        [source("msa.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT, independence_key="doc"),
         source("hubspot_deal", 9_000, authority=Authority.STRUCTURED_SOURCE,
                independence_key="crm")],
        prior_bp=1_000)
    # The fold itself starts at the incumbent 1000 and is lifted from there. If it restarted at
    # the strongest source instead, its own output would still be at or above that 9000 — and
    # the prior would be doing nothing but supplying a ceiling that the corroboration waives.
    assert composed.fold_bp < 9_000, (
        f"the fold produced {composed.fold_bp} from a prior of 1000: it restarted from the "
        f"evidence rather than lifting the incumbent belief")
    ceiling_lift = corroborate(1_000, 9_000, evidence="msa.pdf",
                               authority=Authority.SIGNED_DOCUMENT)
    assert composed.confidence_bp <= ceiling_lift, (
        f"a prior of 1000 was overridden to {composed.confidence_bp}; the most corroboration "
        f"can lift it to is {ceiling_lift}")


# ============================================================================================
# INDEPENDENCE IS A DECISION, NOT A DEFAULT (D6)
# ============================================================================================


def test_independence_must_be_stated_by_the_caller_and_has_no_default() -> None:
    """`independence_key` defaulting to `None` put every caller who did not think about it into
    the ONE group that can only `combine` — where five agreeing sources (3276) are less
    believable than one (8000). Fail-closed is the right direction; arriving there by accident,
    silently, is not. The field is required so the caller has to decide.
    """
    with pytest.raises(TypeError):
        ConfidenceSource(name="a", confidence_bp=8_000)          # type: ignore[call-arg]
    field = {item.name: item for item in dataclasses.fields(ConfidenceSource)}["independence_key"]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


def test_the_unstated_group_is_still_reachable_when_the_caller_asks_for_it() -> None:
    """Required is not the same as non-null: a caller that genuinely has no separate origin
    says so explicitly, and gets the fail-closed combine-only behaviour it asked for."""
    result = compose_confidence([ConfidenceSource(name="a", confidence_bp=8_000,
                                                  independence_key=None),
                                 ConfidenceSource(name="b", confidence_bp=8_000,
                                                  independence_key=None)])
    assert result.independent_evidence == ()
    assert result.confidence_bp == 6_400


def test_the_bounded_raise_carries_a_prior_across_the_wave_seam_without_tripping_v6(
        verified_span) -> None:
    """Cross-wave, on the shape the two defects lived in: a lowered prior, a strong document and
    a weak aside from separate origins. The composed value sits above the ceiling — legally,
    because the fold named what lifted it — and W0's gate must record a waiver rather than a
    rejection. A composer whose ceiling and V-6's ceiling had drifted apart would show up here.
    """
    composed = compose_confidence(
        [source("signed.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT,
                independence_key="docA"),
         source("slack", 100, authority=Authority.CHAT_ASIDE, independence_key="slackB")],
        prior_bp=2_000)
    assert composed.confidence_bp > min(composed.source_confidences)
    assert composed.confidence_bp <= corroborate(
        composed.ceiling_bp, 9_000, evidence="signed.pdf",
        authority=Authority.SIGNED_DOCUMENT)
    decision = validate_publication(_signal(composed, verified_span),
                                    source_confidences=list(composed.source_confidences),
                                    independent_evidence=composed.independent_evidence)
    assert PublicationRule.V6 not in [failure.rule for failure in decision.failures]
    assert PublicationRule.V6 in decision.waived
    assert decision.outcome is PublicationOutcome.EMIT


# ============================================================================================
# THE VECTOR IS PUBLISHED TOO — every axis obeys the bound the scalar obeys (D2, second half)
# ============================================================================================
#
# `confidence_vector` is a PUBLISHED field on the QES (contracts/signal.py:351), and V-6
# (`confidence_respects_sources`, contracts/signal.py:654) reads ONLY `confidence_bp`. An axis
# that escapes the Rule 11 ceiling therefore escapes onto a card with nothing downstream to
# catch it. The clamp used to run on the composed SCALAR alone while `evidence_bp` was handed
# out as the raw fold — which is word for word the failure this module's own docstring names:
# "five sources all repeating one weak recollection ... composed upward into an 8900".
#
# The two rows below are measured, not invented: they are what the module returned before the
# clamp moved ahead of the decay.


def test_the_evidence_axis_of_an_echo_corpus_cannot_exceed_its_weakest_member() -> None:
    """50 sources, every one worth 1000 bp, every one a separately named origin.

    Fifty witnesses each 10% sure is not certainty, and the ceiling says so: the weakest thing
    this belief rests on is a 1000, and one bounded corroborate step from a 1000-bp email lifts
    it to 1360. The scalar came out at 1360. The published `evidence` axis came out at 8765 —
    an 8765 assembled out of a corpus whose strongest member is a 1000.
    """
    composed = compose_confidence(
        [source(f"src_{index}", 1_000, independence_key=f"k{index}") for index in range(50)])
    bound = corroborate(1_000, 1_000, evidence="src_0", authority=Authority.EMAIL_PROSE)
    assert composed.ceiling_bp == 1_000
    assert bound == 1_360
    assert composed.confidence_bp <= bound
    assert composed.vector["evidence"] <= bound, (
        f"the PUBLISHED evidence axis is {composed.vector['evidence']} from a corpus whose "
        f"weakest member is {composed.ceiling_bp}; Rule 11 permits {bound}. V-6 reads only "
        f"confidence_bp, so nothing downstream catches this")


def test_the_evidence_axis_respects_the_ceiling_a_weak_aside_imposes() -> None:
    """The D2 fixture, one axis further in: prior 2000, a signed 9000, a 100-bp Slack aside.

    `test_a_single_named_corroborator_buys_a_bounded_raise_not_an_exemption` already pins the
    SCALAR here at or below 4555. The vector was never asserted, and it left at 5614.
    """
    composed = compose_confidence(
        [source("signed.pdf", 9_000, authority=Authority.SIGNED_DOCUMENT,
                independence_key="docA"),
         source("slack", 100, authority=Authority.CHAT_ASIDE, independence_key="slackB")],
        prior_bp=2_000)
    bound = max(corroborate(100, bp, evidence=name, authority=auth)
                for name, bp, auth in (("signed.pdf", 9_000, Authority.SIGNED_DOCUMENT),
                                       ("slack", 100, Authority.CHAT_ASIDE)))
    assert composed.ceiling_bp == 100
    assert bound == 4_555
    assert composed.confidence_bp <= bound
    assert composed.vector["evidence"] <= bound, (
        f"the PUBLISHED evidence axis is {composed.vector['evidence']} above a ceiling of "
        f"{composed.ceiling_bp}; the sanctioned raise is {bound}")


def test_the_scalar_really_is_the_evidence_axis_aged_by_the_freshness_axis() -> None:
    """`ComposedConfidence`'s own stated invariant, asserted for the first time.

    The class docstring: *"the scalar is evidence aged by freshness"*. It held in the clear
    case and broke in exactly the case that matters — clamped — because the clamp ran on the
    aged scalar and never on the axis: 8765 * 10000 // 10000 is 8765, and the scalar was 1360.
    An invariant that holds only when nothing was clamped is not an invariant; it is a
    coincidence of the unclamped path.
    """
    rng = random.Random(_SEED + 11)
    clamped_cases = 0
    for _ in range(_CASES):
        sources = _random_sources(rng)
        result = compose_confidence(sources,
                                    prior_bp=rng.choice([None, rng.randrange(0, 10_001)]))
        clamped_cases += int(result.clamped)
        assert result.confidence_bp == result.evidence_bp * result.freshness_bp // 10_000, (
            f"scalar {result.confidence_bp} is not evidence {result.evidence_bp} aged by "
            f"freshness {result.freshness_bp}: {sources}")
    assert clamped_cases > 0, "the corpus never exercised the clamped path it was written for"


def test_every_published_axis_is_bounded_over_the_generated_corpus() -> None:
    """The vector, axis by axis, over the same 400 generated input sets as the scalar.

    * `evidence` is the fold, so Rule 11's ceiling binds it exactly as it binds the scalar;
    * `freshness` is `max(0, 10000 - days * rate)` on the NEWEST source and can be nothing else;
    * `expertise` and `coverage` are caller-supplied and are deliberately NOT ceiling-bound —
      they answer different questions ("do we know this domain", "did we see enough") — but
      they are still basis points and must arrive back exactly as they were handed in.
    """
    rng = random.Random(_SEED + 12)
    bounded_above_ceiling = 0
    for _ in range(_CASES):
        sources = _random_sources(rng)
        expertise = rng.randrange(0, 10_001)
        coverage = rng.randrange(0, 10_001)
        result = compose_confidence(sources,
                                    prior_bp=rng.choice([None, rng.randrange(0, 10_001)]),
                                    expertise_bp=expertise, coverage_bp=coverage)
        vector = result.vector
        assert set(vector) == set(CONFIDENCE_COMPONENTS)
        for axis, value in vector.items():
            assert type(value) is int, f"{axis} is {type(value).__name__}, not int"
            assert 0 <= value <= 10_000, f"{axis} is {value}, outside basis points"

        ceiling = min(result.source_confidences)
        if vector["evidence"] > ceiling:
            bounded_above_ceiling += 1
            assert result.independent_evidence, (
                f"the evidence axis is {vector['evidence']}, above the ceiling {ceiling}, with "
                f"no independent evidence named: {sources}")
            bound = sanctioned_raise(ceiling, sources, result.independent_evidence)
            assert vector["evidence"] <= bound, (
                f"the evidence axis is {vector['evidence']} above a ceiling of {ceiling}; the "
                f"sanctioned raise is {bound}. Naming bought the AXIS an exemption: {sources}")

        assert vector["freshness"] == freshness_retained_bp(
            min(item.days_old for item in sources))
        assert vector["expertise"] == expertise
        assert vector["coverage"] == coverage
    assert bounded_above_ceiling > 0, ("no generated case put the evidence axis above the "
                                       "ceiling — the corpus is not testing the carve-out")
