"""H3 · H4 — the GATE's own probes, written against the built modules rather than beside them.

`test_comparator.py`, `test_correlator.py` and `test_anomaly.py` are the components' suites: they
were written by the waves that built them and they assert what those waves set out to do. This
file is the gate's, and it exists for the failure a component suite structurally cannot catch —
the one where the code does exactly what its author intended and the intention leaves a hole.

Each section below is one probe stated as a question that had a wrong answer available, and the
wrong answers are not hypothetical:

* a BAND BOUNDARY is a threshold, and a threshold computed with `//` on one side and `round()` on
  the other reclassifies everybody standing on it. Both sides are asserted at the exact basis
  point, from both directions.
* a TIE is where two members of one cohort learn their rank. Two accounts on the same number that
  are told "31st" and "38th" is a comparison engine contradicting itself in public.
* a PEER BASELINE over a small population **is** the sorted population. The probe here is an
  attack, not an assertion: it tries to read an individual member's value back out of a published
  ladder through the module's own public API. It succeeded, once — see
  `test_a_caller_cannot_narrow_the_window_until_a_rung_is_one_members_reading`.
* `n < 20` and `is_causal` are the two rows H4 states, and the second one is a class of finding
  rather than a field: a correlation object that could be talked into implying direction is the
  whole reason doc 04 refuses causal language.
* ZERO-FILLING is the failure that makes correlation LOOK like it works: two metrics missing on
  the same quiet accounts correlate at nearly 10000 on the holes alone.
* MAD versus a standard deviation is not a preference. The probe builds the series where the
  outlier inflates the standard deviation far enough to hide ITSELF, and asserts the flag fires.
* an EXTREME anomaly must report the ratio it measured. A magnitude clamped at 10000 is a
  40x collapse and a 1.001x wobble printing the same number.

Nothing here reads a clock, a database or a model. Every measure is an integer basis point.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import timedelta

import pytest

from genios_engine.contracts.analytic import (MIN_COHORT_POPULATION, MIN_CORRELATION_SAMPLES,
                                              Anomaly, CohortBand, MetricCorrelation, MetricPoint,
                                              MetricUnit)
from genios_engine.context.analytic.anomaly import detect_anomaly
from genios_engine.context.analytic.cohort import (CohortRefusal, CohortRefusalReason,
                                                   percentile_bp as nearest_rank_percentile_bp)
from genios_engine.context.analytic.comparator import compare_reading
from genios_engine.context.analytic.correlator import (CorrelationRefusal,
                                                       CorrelationRefusalReason, correlate_series,
                                                       correlate_values, spearman_rho_bp)
from genios_engine.context.support_situations import (
    percentile_bp as mid_rank_percentile_bp)
from genios_engine.context.analytic.peer_baseline import (BASELINE_SMOOTHING_WINDOW,
                                                          MIN_BASELINE_POPULATION,
                                                          BaselineRefusal,
                                                          BaselineRefusalReason, compute_baseline,
                                                          smoothed_rung)

COHORT = "cohort_growth_plan"


def point(node: str, metric: str, *, at, value: int | None, known: bool = True) -> MetricPoint:
    """One reading. `known=False` carries no value, by contract — which is the whole subject of
    the two gap probes below."""
    return MetricPoint(subject_node_id=node, metric=metric, value_bp=value,
                       unit=MetricUnit.COUNT, observed_at=at, known=known)


# =================================================================================================
# H3 · "every cohort band boundary is exact; a tie gives both tenants the same percentile"
# =================================================================================================

#: Every decile edge, from both sides. The low edge of D_k is `(k-1)*1000` and it BELONGS to D_k;
#: one basis point below it belongs to D_(k-1). Written out rather than generated because a
#: generated table computes the boundary with the same expression as the code and would agree
#: with a wrong one.
_DECILE_EDGES = [
    (0, CohortBand.D1), (999, CohortBand.D1),
    (1_000, CohortBand.D2), (1_999, CohortBand.D2),
    (2_000, CohortBand.D3), (2_999, CohortBand.D3),
    (3_000, CohortBand.D4), (3_999, CohortBand.D4),
    (4_000, CohortBand.D5), (4_999, CohortBand.D5),
    (5_000, CohortBand.D6), (5_999, CohortBand.D6),
    (6_000, CohortBand.D7), (6_999, CohortBand.D7),
    (7_000, CohortBand.D8), (7_999, CohortBand.D8),
    (8_000, CohortBand.D9), (8_999, CohortBand.D9),
    (9_000, CohortBand.D10), (10_000, CohortBand.D10),
]


@pytest.mark.parametrize("percentile_bp,band", _DECILE_EDGES)
def test_a_decile_boundary_lands_on_the_same_side_from_both_directions(percentile_bp, band):
    assert CohortBand.for_percentile(percentile_bp, divisions=10) is band
    assert band.contains(percentile_bp), "the label must contain the number printed beside it"


@pytest.mark.parametrize("percentile_bp,band", [
    (0, CohortBand.Q1), (2_499, CohortBand.Q1),
    (2_500, CohortBand.Q2), (4_999, CohortBand.Q2),
    (5_000, CohortBand.Q3), (7_499, CohortBand.Q3),
    (7_500, CohortBand.Q4), (10_000, CohortBand.Q4),
])
def test_a_quartile_boundary_lands_on_the_same_side_from_both_directions(percentile_bp, band):
    assert CohortBand.for_percentile(percentile_bp, divisions=4) is band
    assert band.contains(percentile_bp)


def test_the_top_of_the_range_is_the_top_band_and_not_an_eleventh_one():
    """10000 is a real percentile — the largest value in any cohort scores it — and `// width`
    lands it on index 10, one past the last decile. The clamp is the only thing between that and
    a `ValueError` on every cohort's best account."""
    assert CohortBand.for_percentile(10_000, divisions=10) is CohortBand.D10
    assert CohortBand.D10.contains(10_000)


def test_two_members_holding_the_same_value_are_told_the_same_percentile(eval_time):
    """`rank = count(v <= value)`, so equal readings count each other. Two accounts on 22% cannot
    be told "31st" and "38th" — that is the comparison engine disagreeing with itself in public,
    and it is what a strict `<` in the rank would produce."""
    values = {"n1": 100, "n2": 220, "n3": 220, "n4": 300, "n5": 400, "n6": 500}
    first = compare_reading(metric="reply_rate", cohort_id=COHORT, values=values,
                            subject_node_id="n2", eval_time=eval_time)
    second = compare_reading(metric="reply_rate", cohort_id=COHORT, values=values,
                             subject_node_id="n3", eval_time=eval_time)
    assert first.percentile_bp == second.percentile_bp == 5_000
    assert first.band is second.band
    assert first.position.p50_bp == second.position.p50_bp


def test_a_whole_cohort_on_one_value_is_a_tie_at_the_top_and_not_a_ranking(eval_time):
    """The degenerate tie. Everybody counts everybody, so everybody is 10000 — the honest answer
    for "you are joint first of five" and NOT a spread invented out of sort order.

    CHANGED: the band assertion was `CohortBand.D10` and is now `Q4`. Six members cannot express a
    decile — the smallest percentile a cohort of n can produce is `10000 // n`, so D1 is empty
    below eleven members and `CohortPosition` narrows the scheme to quartiles. The probe's subject
    is the TIE, which is asserted unchanged at 10000; asserting a decile label here was asserting
    the resolution defect beside it.
    """
    values = {f"n{i}": 42 for i in range(6)}
    positions = [compare_reading(metric="reply_rate", cohort_id=COHORT, values=values,
                                 subject_node_id=node, eval_time=eval_time)
                 for node in values]
    assert {p.percentile_bp for p in positions} == {10_000}
    assert {p.band for p in positions} == {CohortBand.Q4}
    eleven = {f"n{i}": 42 for i in range(11)}
    wider = [compare_reading(metric="reply_rate", cohort_id=COHORT, values=eleven,
                             subject_node_id=node, eval_time=eval_time) for node in eleven]
    assert {p.band for p in wider} == {CohortBand.D10}, (
        "and the same degenerate tie IS a decile once the population can express one")


def test_every_returned_position_carries_its_cohort_and_its_population(eval_time):
    """Doc 09's H3 row, asserted on the object rather than trusted from the docstring: a
    percentile without a stated population is not returned at all."""
    values = {f"n{i}": i * 10 for i in range(1, 8)}
    reading = compare_reading(metric="reply_rate", cohort_id=COHORT, values=values,
                              subject_node_id="n3", eval_time=eval_time)
    assert reading.cohort_id == COHORT
    assert reading.population_size == 7
    assert reading.position.cohort_id == COHORT and reading.position.population_size == 7


# =================================================================================================
# H3 · the row doc 09 states about the OTHER percentile — "nearest-rank matches the existing
#      `support_situations.percentile_bp` exactly". It does not, it cannot, and this is the pin.
# =================================================================================================

def test_doc_04s_own_acceptance_figure_is_the_nearest_rank_one():
    """*"the lowest value in a cohort of 10 -> percentile_bp near 1000"* (doc 04, line 566). Only
    one of the two functions produces it, and that settles which statistic L2.4.5 owes."""
    population = [i * 10 for i in range(1, 11)]
    assert nearest_rank_percentile_bp(population, 10) == 1_000
    assert mid_rank_percentile_bp([float(v) for v in population], 10.0) == 500


def test_the_two_percentiles_are_pinned_apart_so_neither_drifts_onto_the_others_answer():
    """H3's row asks the two to agree exactly. They answer different questions and cannot: one is
    a statement about a VALUE (two accounts on 22% get one number, so a tie counts itself) and one
    asks whether a backlog item is unusually old for its desk (where a tie at the top would open a
    finding on every loop of a uniformly aged desk). The divergence is therefore ASSERTED, not
    tolerated silently — if either is ever changed, this fails instead of a card being wrong.
    """
    tied = [5.0, 5.0, 5.0]
    assert nearest_rank_percentile_bp([5, 5, 5], 5) == 10_000, "everyone counts everyone"
    assert mid_rank_percentile_bp(tied, 5.0) == 5_000, "a flat population sits in the middle"
    ranked = [1.0, 2.0, 3.0, 4.0]
    assert nearest_rank_percentile_bp([1, 2, 3, 4], 4) == 10_000
    assert mid_rank_percentile_bp(ranked, 4.0) == 8_750


def test_the_support_percentile_carries_no_float_in_its_measure_path():
    """The part of doc 04's complaint that WAS a defect: `ties / 2.0` and `round()` decided a
    threshold by binary expansion. The numerator is doubled instead, and the source is checked
    rather than the output, because a value that happens to be exact proves nothing."""
    source = inspect.getsource(mid_rank_percentile_bp)
    body = source.split('"""')[-1]
    assert "2.0" not in body and "round(" not in body and "float(" not in body
    assert "// (2 * len(population))" in body


def test_the_analytic_stratum_defines_exactly_one_percentile():
    """What H3's row is really protecting. A third copy — in the comparator, the baseline or the
    correlator — is the failure the doc calls "a second percentile that disagrees with the first
    by one rank", and it is invisible in every code review that does not go looking."""
    stratum = (pathlib.Path(__file__).resolve().parents[3] / "genios_engine" / "context"
               / "analytic")
    definitions: dict[str, list[str]] = {}
    for module in sorted(stratum.glob("*.py")):
        #: MODULE LEVEL only. `PositionedReading.percentile_bp` is an accessor that returns
        #: `self.position.percentile_bp` — a delegation, which is the opposite of the failure.
        for node in ast.parse(module.read_text()).body:
            if isinstance(node, ast.FunctionDef) and "percentile" in node.name:
                definitions.setdefault(node.name, []).append(module.name)
    assert definitions == {"percentile_bp": ["cohort.py"]}, definitions
    #: And the arithmetic itself appears exactly once, so a copy under another name is caught too.
    ranked = [module.name for module in sorted(stratum.glob("*.py"))
              if "for v in values if v <= value" in module.read_text()]
    assert ranked == ["cohort.py"], ranked


# =================================================================================================
# H3 · "a population below the floor REFUSES rather than returning a weak comparison"
# =================================================================================================

@pytest.mark.parametrize("population", list(range(0, MIN_COHORT_POPULATION)))
def test_every_population_under_the_floor_refuses_and_names_the_number_it_refused_on(
        population, eval_time):
    values = {f"n{i}": i * 10 for i in range(population)}
    subject = "n0" if population else "nobody"
    outcome = compare_reading(metric="reply_rate", cohort_id=COHORT, values=values,
                              subject_node_id=subject, eval_time=eval_time)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_POPULATION
    assert outcome.population_size == population, (
        "a refusal that hides how close it was is not usable")
    assert str(population) in outcome.detail


def test_the_floor_is_a_floor_and_not_a_gap(eval_time):
    """Exactly at the floor the answer is a position, one below it a refusal. A component that
    refused at five and answered at six would have moved the contract's number without saying so."""
    at_floor = {f"n{i}": i * 10 for i in range(MIN_COHORT_POPULATION)}
    assert not isinstance(
        compare_reading(metric="reply_rate", cohort_id=COHORT, values=at_floor,
                        subject_node_id="n0", eval_time=eval_time), CohortRefusal)
    below = dict(list(at_floor.items())[:-1])
    assert isinstance(
        compare_reading(metric="reply_rate", cohort_id=COHORT, values=below,
                        subject_node_id="n0", eval_time=eval_time), CohortRefusal)


def test_a_refusal_carries_no_percentile_for_a_caller_to_print_anyway(eval_time):
    """A refusal that also carried a number would be read, quoted and rendered — the "weak answer
    where the contract says refuse" this stratum exists to avoid."""
    outcome = compare_reading(metric="reply_rate", cohort_id=COHORT, values={"n0": 1, "n1": 2},
                              subject_node_id="n0", eval_time=eval_time)
    assert not hasattr(outcome, "percentile_bp")
    assert not hasattr(outcome, "band")


# =================================================================================================
# H3 · PEER BASELINE DISCLOSURE — the probe that is an attack
# =================================================================================================

def _ladder_of(values, eval_time, **kw):
    return compute_baseline(org_id="org_probe", cohort_id=COHORT, metric="arr",
                            values=values, unit=MetricUnit.COUNT, eval_time=eval_time, **kw)


def test_the_published_ladder_is_not_the_sorted_population(eval_time):
    """The disclosure this component exists to refuse, stated as what it actually is: five
    NEAREST-RANK rungs over ten members ARE five of those members' readings, in order, and a
    reader who knows the population size can name which rank each one belongs to. The published
    ladder must not be that list.

    Note what is NOT claimed. On an evenly spaced population the mean of three adjacent readings
    equals the middle one, so a rung can coincide with a member's number — coincide with, not
    disclose: nothing in the ladder says whether it did. The guarantee is that the rung is the
    WINDOW's number rather than the rank-holder's, and that is asserted here against the order
    statistics the ladder would otherwise have been.
    """
    readings = {f"n{i}": 100 + (i * i * 13) % 900 for i in range(MIN_BASELINE_POPULATION + 4)}
    ordered = sorted(readings.values())
    ladder = _ladder_of(readings, eval_time)
    assert ladder.is_baseline
    order_statistics = tuple(ordered[(q * (len(ordered) - 1)) // 10_000]
                             for q in (1_000, 2_500, 5_000, 7_500, 9_000))
    assert ladder.ladder != order_statistics, (
        "the ladder IS the sorted population at those five ranks — every rung names a member")


def test_the_extremes_are_never_published_so_the_two_easiest_leaks_are_not_available(eval_time):
    """The minimum and the maximum are the two readings a peer baseline discloses first: the
    lowest and the highest account in the cohort are individually identifiable to anyone who
    knows the population. Neither may be a rung."""
    readings = {f"n{i}": i * 37 for i in range(1, MIN_BASELINE_POPULATION + 3)}
    ladder = _ladder_of(readings, eval_time)
    assert min(readings.values()) not in ladder.ladder
    assert max(readings.values()) not in ladder.ladder
    assert ladder.p10_bp > min(readings.values())
    assert ladder.p90_bp < max(readings.values())


def test_a_rung_moves_by_a_third_of_a_members_change_so_the_guarantee_is_bounded_not_absolute(
        eval_time):
    """**THE SECOND FINDING, and it is a claim rather than a crash.** `peer_baseline.py` said the
    ladder was *"byte-identical"* under a change to one member's reading, *"so no arithmetic
    recovers that member from it"*, and `test_a_members_reading_cannot_be_recovered_from_the_ladder`
    demonstrated it — on index 6 of twenty, which is the one index that falls outside all five
    windows. It is a true statement about that member and a false one about the population.

    A member INSIDE a window moves that rung by their delta divided by the window. The probe runs
    the recovery: two ladders a week apart, subtract, multiply by three, and the change to n9 is
    read back to within the floor division. That does not make the ladder unsafe — it makes it an
    aggregate, and an aggregate is a channel of exactly this width. What it makes unsafe is the
    SENTENCE, which is why the module docstring now states the bound instead of the impossibility.
    """
    base = {f"n{i}": 1_000 + i * 50 for i in range(MIN_BASELINE_POPULATION + 10)}
    outside = dict(base, n0=base["n0"] - 400)          # below every window's reach after sorting
    inside = dict(base, n9=base["n9"] + 90)

    quiet = _ladder_of(base, eval_time)
    assert _ladder_of(outside, eval_time).ladder[1:] == quiet.ladder[1:], (
        "a member outside a window cannot move the rungs it is not in — this is the property "
        "the existing suite demonstrates")
    moved = _ladder_of(inside, eval_time)
    deltas = [after - before for before, after in zip(quiet.ladder, moved.ladder)]
    assert any(deltas), "a member inside a window DOES move it — the absolute claim was wrong"
    assert max(deltas) * BASELINE_SMOOTHING_WINDOW == 90, (
        "and the recovery is exact to the floor division: rung delta * window = the member's")


def test_a_caller_cannot_narrow_the_window_until_a_rung_is_one_members_reading(eval_time):
    """**THE FINDING.** `smoothed_rung` takes a `window` and so did `compute_baseline`, and at
    `window=1` every rung is an order statistic — the exact reading of the member standing at that
    rank. The module's whole disclosure argument ("no rung is any one member's number") was a
    property of the DEFAULT, and a default is not a control: one keyword away, a published ladder
    over ten accounts was five of those accounts' numbers.

    The primitive keeps the parameter — `test_peer_baseline.py` uses `window=1` to demonstrate
    exactly what is being avoided — and the PUBLISHING path no longer accepts a window under the
    floor. A caller may make the window wider (a noisier metric legitimately wants more
    smoothing); narrower is a disclosure and is refused where the ladder is built."""
    readings = {f"n{i}": 1_000 + i * 100 for i in range(MIN_BASELINE_POPULATION + 2)}
    # The primitive still does what it is asked, and what it is asked for at window=1 is a member.
    assert smoothed_rung(sorted(readings.values()), 5_000, window=1) in set(readings.values())
    for narrow in (1, 2):
        with pytest.raises(ValueError, match="window"):
            _ladder_of(readings, eval_time, window=narrow)
    wider = _ladder_of(readings, eval_time, window=BASELINE_SMOOTHING_WINDOW + 2)
    assert wider.is_baseline, "a WIDER window smooths harder and discloses less — it is allowed"


@pytest.mark.parametrize("population", [0, 1, 4, MIN_COHORT_POPULATION,
                                        MIN_BASELINE_POPULATION - 1])
def test_a_ladder_under_the_k_anonymity_floor_refuses(population, eval_time):
    """The k-floor is higher than the percentile floor and that difference is deliberate: a
    percentile hands a subject their own rank, a ladder hands every reader five order statistics
    of the population."""
    outcome = _ladder_of({f"n{i}": i * 11 for i in range(population)}, eval_time)
    assert isinstance(outcome, BaselineRefusal)
    assert outcome.reason is BaselineRefusalReason.INSUFFICIENT_POPULATION
    assert outcome.population == population


def test_a_ladder_at_the_floor_is_published_so_the_floor_is_not_a_dead_letter(eval_time):
    ladder = _ladder_of({f"n{i}": i * 11 for i in range(MIN_BASELINE_POPULATION)}, eval_time)
    assert ladder.is_baseline and ladder.population == MIN_BASELINE_POPULATION


def test_the_differencing_attack_at_the_k_floor_recovers_a_member_to_the_floor_divisions_width(
        eval_time):
    """**THE DISCLOSURE PROBE, run as the attack rather than asserted as a property.** One
    published ladder, no time series, and an adversary holding the other nine readings of a
    ten-member cohort — the smallest population this module will publish for. How much of the
    tenth does the ladder hand over?

    The answer is measured here rather than argued: the attack brute-forces every value the
    unknown member could hold and keeps the ones that reproduce the published ladder exactly. It
    comes back with THREE candidates, spanning two units — the remainder that `sum // 3` discards
    and nothing more. For a metric measured in thousands that is, in effect, the member's number.

    **This is not a bug and it is not fixable by an arithmetic that stays deterministic.** Any
    published aggregate over a known population is solvable by an adversary who knows n-1 of it
    (Dinur-Nissim); the only mitigations are noise, which this stratum forbids because a measure
    that changes per machine is not a measuring instrument, and a bigger k, which raises the cost
    of holding n-1 without changing the algebra. What the probe pins down is the WIDTH of the
    channel, so the module's docstring can state it and no later reader can upgrade "an aggregate"
    into "anonymous". The claim in `peer_baseline.py` is already the bounded one; this test is
    what makes it a measured bound rather than a careful sentence.
    """
    known = {f"n{i}": 1_000 + i * 137 for i in range(MIN_BASELINE_POPULATION - 1)}
    secret = 9_311                                    # the target, and the cohort's maximum
    published = _ladder_of(dict(known, target=secret), eval_time)
    assert published.is_baseline and published.population == MIN_BASELINE_POPULATION

    solutions = [candidate for candidate in range(max(known.values()) + 1, secret + 5_000)
                 if _ladder_of(dict(known, target=candidate), eval_time).ladder
                 == published.ladder]
    assert secret in solutions, "the attack must at least find the true value, or it is not one"
    assert len(solutions) == BASELINE_SMOOTHING_WINDOW, (
        f"{len(solutions)} candidates reproduce the ladder — the recovery interval is the "
        "floor division's remainder and nothing else, and that is what the docstring must say")
    assert max(solutions) - min(solutions) == BASELINE_SMOOTHING_WINDOW - 1


def test_the_module_states_the_bound_rather_than_claiming_an_impossibility(eval_time):
    """The probe above is only worth running if the code does not claim the opposite. A module
    docstring that said a member "cannot be recovered" would be a sentence a reader trusts in
    place of the floors that are actually doing the work."""
    from genios_engine.context.analytic import peer_baseline

    doc = (peer_baseline.__doc__ or "").lower()
    assert "cannot be recovered" not in doc
    assert "bound the twentieth" in doc or "can bound" in doc, (
        "the disclosure paragraph must state what a reader holding the other readings CAN do")


def test_a_ladder_is_monotone_so_a_card_never_prints_p25_above_p75(eval_time):
    readings = {f"n{i}": (i * 7919) % 5_000 for i in range(40)}
    ladder = _ladder_of(readings, eval_time)
    assert list(ladder.ladder) == sorted(ladder.ladder)


# =================================================================================================
# H4 · "correlation refuses below 20 samples; `is_causal` cannot be set True"
# =================================================================================================

@pytest.mark.parametrize("n", list(range(0, MIN_CORRELATION_SAMPLES)))
def test_every_sample_count_under_twenty_refuses_and_says_how_many_it_had(n, eval_time):
    a = {f"n{i}": i for i in range(n)}
    b = {f"n{i}": i * 3 + (i % 5) for i in range(n)}
    outcome = correlate_values(metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
                               values_a=a, values_b=b, eval_time=eval_time)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS
    assert outcome.n == n and str(n) in outcome.detail


def test_twenty_pairs_is_the_first_count_that_answers(eval_time):
    a = {f"n{i}": i for i in range(MIN_CORRELATION_SAMPLES)}
    b = {f"n{i}": i * 3 + (i % 5) for i in range(MIN_CORRELATION_SAMPLES)}
    outcome = correlate_values(metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
                               values_a=a, values_b=b, eval_time=eval_time)
    assert isinstance(outcome, MetricCorrelation) and outcome.n == MIN_CORRELATION_SAMPLES


def test_a_correlation_cannot_be_told_it_is_causal_at_construction():
    """V-7, from the outside. `is_causal` is not a field a caller may supply — an object that
    accepted it would let one honest module hand Layer 3 a causal claim nobody computed."""
    with pytest.raises(Exception) as raised:
        MetricCorrelation(metric_a="a", metric_b="b", cohort_id=COHORT, rho_bp=9_000,
                          strength="strong", n=40, is_causal=True)
    assert "is_causal" in str(raised.value)


def test_a_correlation_cannot_be_told_it_is_causal_afterwards(eval_time):
    """Frozen, and re-validated on copy. A `model_copy(update=...)` that slipped past the
    validator is the same leak arriving one line later."""
    correlation = correlate_values(
        metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
        values_a={f"n{i}": i for i in range(24)},
        values_b={f"n{i}": i * 2 for i in range(24)}, eval_time=eval_time)
    assert correlation.is_causal is False
    with pytest.raises(Exception):
        correlation.is_causal = True
    assert correlation.is_causal is False


def test_a_correlation_cannot_be_told_it_is_causal_by_copying_one(eval_time):
    """**THE FINDING.** `model_copy(update=...)` is pydantic's ordinary way to derive one frozen
    model from another and it runs NO validator, so before this probe the single line

        correlation.model_copy(update={"is_causal": True})

    produced a well-typed `MetricCorrelation` carrying the causal claim V-7 exists to make
    unconstructible. `situation.py`'s own V-7 catch would have found it — but only if the object
    were later attached to a BSO and put through `validate_situation`; one published straight out
    of `api/correlation_routes.py` would not be. And the test that was meant to cover this named
    `model_copy` in its docstring while only exercising `setattr`, which is the exact shape of a
    guarantee nobody is checking.

    The fix is in the contract, not here: `Measurement.model_copy` re-enters the constructor
    whenever it is given an update. `model_construct` is deliberately still a bypass — it is the
    documented "I know what I am doing" door, and `validate_situation` is what stands behind it.
    """
    correlation = correlate_values(
        metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
        values_a={f"n{i}": i for i in range(24)},
        values_b={f"n{i}": i * 2 for i in range(24)}, eval_time=eval_time)
    with pytest.raises(Exception, match="is_causal"):
        correlation.model_copy(update={"is_causal": True})
    #: and an honest copy still works, or the fix would have cost the caller the operation
    assert correlation.model_copy(update={"rho_bp": -4_000}).rho_bp == -4_000
    assert correlation.model_copy().is_causal is False


def test_no_analytic_measure_can_be_copied_past_the_law_that_owns_it(eval_time):
    """The same door, on every measure in the stratum — the sample floor, the cohort floor and
    the gap rule are each one `model_copy` from being edited out of an object that already
    typechecks, and a fix applied only to the field that happened to be probed is a fix that
    lasts until the next reader needs a different one."""
    correlation = MetricCorrelation(metric_a="a", metric_b="b", cohort_id=COHORT, rho_bp=6_000,
                                    strength="moderate", n=MIN_CORRELATION_SAMPLES)
    with pytest.raises(Exception, match="at least"):
        correlation.model_copy(update={"n": MIN_CORRELATION_SAMPLES - 1})

    reading = point("n1", "engagement", at=eval_time, value=4_200)
    with pytest.raises(Exception):
        reading.model_copy(update={"known": False})          # a gap that kept its value
    with pytest.raises(Exception):
        reading.model_copy(update={"value_bp": 42.5})        # a float in the measure path


def test_a_constant_metric_is_refused_rather_than_reported_as_a_perfect_association(eval_time):
    """The `d^2` shortcut returns 10000 when every rank ties, so a metric no tenant has ever
    varied would come back STRONGLY correlated with everything on the platform."""
    outcome = correlate_values(
        metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
        values_a={f"n{i}": 7 for i in range(30)},
        values_b={f"n{i}": i for i in range(30)}, eval_time=eval_time)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.DEGENERATE_SERIES


def test_the_coefficient_stays_inside_the_signed_basis_point_range_on_heavily_tied_ranks():
    """The tie correction the `d^2` form does not carry can push the raw number past -10000, and
    the contract would reject the row. Probed at the shape that produces it — many ties, ordered
    against each other — rather than trusted from the docstring."""
    xs = [i // 4 for i in range(40)]
    ys = [(39 - i) // 4 for i in range(40)]
    assert -10_000 <= spearman_rho_bp(xs, ys) <= 10_000


# =================================================================================================
# H4 · "two series with disjoint gaps correlate on shared periods only — zero-filling must not
#       invent one"
# =================================================================================================

def _series(metric: str, readings, eval_time):
    """A dense series: one point per period, `known=False` where the reading is None — which is
    exactly the shape `MetricHistoryStore.read_series` returns."""
    return [point("acct_1", metric, at=eval_time - timedelta(days=7 * (len(readings) - i - 1)),
                  value=value, known=value is not None)
            for i, value in enumerate(readings)]


def test_two_series_with_disjoint_gaps_are_refused_on_the_periods_they_actually_share(eval_time):
    """Thirty periods each, both well past the floor if the holes counted. They alternate, so the
    two are known together on NO period at all — and zero-filling would have produced thirty
    pairs of (value, 0) and (0, value), which correlate almost perfectly on the holes alone."""
    a = _series("reply_rate", [i * 3 if i % 2 == 0 else None for i in range(30)], eval_time)
    b = _series("deal_value", [i * 5 if i % 2 == 1 else None for i in range(30)], eval_time)
    outcome = correlate_series(metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
                               series_a=a, series_b=b, eval_time=eval_time)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS
    assert outcome.n == 0, "a period nobody measured on either side is not a pair"


def test_the_shared_periods_are_the_only_ones_counted_and_the_count_is_the_overlap(eval_time):
    """Twenty-two shared periods inside two longer series with different holes. `n` must be the
    overlap and not either series' length."""
    a = _series("reply_rate", [None if i < 6 else i for i in range(28)], eval_time)
    b = _series("deal_value", [None if i >= 28 - 0 else i * 2 for i in range(28)], eval_time)
    b = _series("deal_value", [None if i in (26, 27) else i * 2 for i in range(28)], eval_time)
    outcome = correlate_series(metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
                               series_a=a, series_b=b, eval_time=eval_time)
    assert isinstance(outcome, MetricCorrelation)
    assert outcome.n == 20, "6 leading holes on one side, 2 trailing on the other, of 28"


def test_a_member_missing_one_of_the_two_metrics_is_not_a_member_with_a_zero(eval_time):
    """The population form of the same rule. Nineteen members read both metrics and eleven read
    only one; zero-filling would report thirty pairs and a coefficient carried by the fill."""
    both = {f"n{i}": i * 4 for i in range(19)}
    outcome = correlate_values(
        metric_a="reply_rate", metric_b="deal_value", cohort_id=COHORT,
        values_a=dict(both, **{f"m{i}": i for i in range(11)}),
        values_b=dict(both), eval_time=eval_time)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.n == 19


# =================================================================================================
# H4 · MAD, the outlier, and the unsaturated ratio
# =================================================================================================

def _stdev_bp(values):
    """A standard deviation, computed HERE and only here, to show what it would have done. The
    module under test contains no float; this probe is the argument for that."""
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5


def test_mad_catches_an_outlier_that_inflates_a_standard_deviation_enough_to_hide_itself(
        eval_time):
    """Five quiet periods and one spike. The spike widens the standard deviation so far that the
    NEXT spike sits well inside three of them and reads as normal — the failure mode doc 04 names
    when it prescribes MAD. The MAD is unmoved by one outlier in six, so the same reading is 200x
    out and flagged.

    Both numbers are asserted: the standard deviation the module refuses to use, so the probe
    fails loudly if the two measures ever stop disagreeing here, and the verdict it does produce.
    """
    baseline_values = [100, 100, 100, 100, 100, 9_000]
    series = [point("acct_1", "tickets", at=eval_time - timedelta(days=7 * (6 - i)),
                    value=value) for i, value in enumerate(baseline_values)]
    current = point("acct_1", "tickets", at=eval_time, value=700)
    stdev = _stdev_bp(baseline_values)
    mean = sum(baseline_values) / len(baseline_values)
    assert abs(700 - mean) < 3 * stdev, (
        "the probe is only meaningful while a 3-sigma rule would MISS this reading")

    verdict = detect_anomaly([*series, current])
    assert verdict.answered and verdict.flagged
    assert verdict.baseline_bp == 100, "the median ignores the one big month"
    assert verdict.mad_bp == 0, "five identical quiet periods have no dispersion at all"
    assert verdict.z_like_bp == 6_000_000
    assert verdict.anomaly is not None and verdict.anomaly.mad_bp == 0


def test_the_outlier_itself_does_not_become_the_normal(eval_time):
    """The complement: with the spike in the baseline, a return to the quiet level is not itself
    flagged as a collapse. A mean-based baseline of 1583 would have called 100 a 94% drop."""
    values = [100, 100, 100, 100, 100, 9_000]
    series = [point("acct_1", "tickets", at=eval_time - timedelta(days=7 * (6 - i)), value=v)
              for i, v in enumerate(values)]
    verdict = detect_anomaly([*series, point("acct_1", "tickets", at=eval_time, value=100)])
    assert verdict.answered and not verdict.flagged
    assert verdict.deviation_bp == 0


@pytest.mark.parametrize("current,expected_deviation_bp", [
    (400, 30_000),          # 4x the baseline — three times off, not "100%"
    (10_000, 990_000),      # 100x
    (0, 10_000),            # gone to nothing: exactly one baseline's worth of movement
])
def test_an_extreme_anomaly_reports_an_unsaturated_ratio(current, expected_deviation_bp,
                                                         eval_time):
    """A deviation clamped at 10000 would print the same number for a metric that doubled and a
    metric that fell off a cliff, and the ratio is the only thing on the card that says which. The
    contract types both ratios with `require_ratio_bp` precisely so they may exceed a proportion.
    """
    series = [point("acct_1", "tickets", at=eval_time - timedelta(days=7 * (6 - i)), value=100)
              for i in range(6)]
    verdict = detect_anomaly([*series, point("acct_1", "tickets", at=eval_time, value=current)])
    assert verdict.deviation_bp == expected_deviation_bp
    assert verdict.deviation_bp > 10_000 or current == 0
    if verdict.flagged:
        assert verdict.anomaly.deviation_bp == expected_deviation_bp


def test_the_ratio_survives_the_contract_that_carries_it():
    """The clamp could also live in the type. `Anomaly` is constructed here directly with the
    magnitudes an extreme reading produces, so a `require_bp` slipped into either field would
    fail this probe rather than silently flatten every large finding."""
    anomaly = Anomaly(metric="tickets", current_bp=10_000, baseline_bp=100, mad_bp=0,
                      deviation_bp=990_000, z_like_bp=99_000_000, direction="above",
                      periods_used=6)
    assert anomaly.deviation_bp == 990_000 and anomaly.z_like_bp == 99_000_000


# =================================================================================================
# "gaps are never zeros, anywhere in the stratum"
# =================================================================================================

def test_a_trailing_gap_is_not_a_reading_of_nought(eval_time):
    """The most valuable of the anomaly refusals: a series ending on an unmeasured period has
    nothing to judge, and a zero there is a 100% collapse reported on every account whose
    connector went quiet."""
    series = [point("acct_1", "tickets", at=eval_time - timedelta(days=7 * (6 - i)), value=500)
              for i in range(6)]
    verdict = detect_anomaly([*series, point("acct_1", "tickets", at=eval_time, value=None,
                                             known=False)])
    assert not verdict.answered and not verdict.flagged
    assert verdict.refusal is not None and verdict.refusal.value == "no_current_reading"
    assert verdict.current_bp is None and verdict.baseline_bp is None


def test_gaps_inside_the_baseline_shrink_the_sample_rather_than_dragging_it_to_zero(eval_time):
    """Three known readings and three holes is INSUFFICIENT_HISTORY. Counting the holes as zeros
    would have produced a baseline of 250 from readings of 500 and called every quiet week a
    finding."""
    values = [500, None, 500, None, 500, None]
    series = [point("acct_1", "tickets", at=eval_time - timedelta(days=7 * (6 - i)), value=v,
                    known=v is not None) for i, v in enumerate(values)]
    verdict = detect_anomaly([*series, point("acct_1", "tickets", at=eval_time, value=500)])
    assert verdict.refusal is not None and verdict.refusal.value == "insufficient_history"
    assert verdict.periods_used == 3


def test_a_cohort_where_most_members_were_never_measured_refuses(eval_time):
    """The comparator's half of the rule. Six readings and twelve members with none is not a
    distribution over eighteen accounts — and the twelve are not twelve zeros."""
    outcome = compare_reading(metric="reply_rate", cohort_id=COHORT,
                              values={f"n{i}": i * 10 for i in range(1, 7)},
                              subject_node_id="n1", eval_time=eval_time, unknown=12)
    assert isinstance(outcome, CohortRefusal)
    assert outcome.reason is CohortRefusalReason.INSUFFICIENT_COVERAGE


def test_a_baseline_where_most_members_were_never_measured_refuses(eval_time):
    outcome = _ladder_of({f"n{i}": i * 10 for i in range(MIN_BASELINE_POPULATION)}, eval_time,
                         unknown=40)
    assert isinstance(outcome, BaselineRefusal)
    assert outcome.reason is BaselineRefusalReason.INSUFFICIENT_COVERAGE


def test_a_gap_cannot_be_given_a_value_at_all(eval_time):
    """V-3, the root of every row above: `known=False` carries no value, so there is no way to
    write the zero this section keeps refusing to infer."""
    with pytest.raises(Exception):
        MetricPoint(subject_node_id="acct_1", metric="tickets", value_bp=0,
                    unit=MetricUnit.COUNT, observed_at=eval_time, known=False)
