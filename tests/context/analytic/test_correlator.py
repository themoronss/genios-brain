"""H4 · L2.4.7 — the METRIC CORRELATOR (BLG-12). The gate for `context/analytic/correlator.py`.

**Gate H4** (`02-Layer-2-Plan/09-Build-Order-and-Acceptance.md`):

    pytest tests/context/analytic/test_correlator.py tests/context/analytic/test_anomaly.py -q

Doc 09's four requirements for this file are each a test below, in its order: `n < 20` refuses;
`is_causal` is False on every object and cannot be set; `cohort_id` is mandatory; and `rho_bp` is
integer basis points with the NONE/WEAK/MODERATE/STRONG bands computed from it deterministically.

THE TWO TESTS THAT MATTER MOST ARE NOT IN THAT LIST.

`test_zero_filling_the_holes_invents_a_strong_correlation` is the defect this component exists to
avoid. It builds forty members where twenty have no reading of the second metric, computes the
coefficient the naive implementation would produce (STRONG, 8008) and the one the correct
implementation produces (NONE, 1023) from the SAME data, and asserts the correlator returns the
second. An unknown is not a zero; two metrics that are each missing on the same quiet accounts
correlate at nearly 10000 on the holes alone, and the finding would be entirely an artefact of
which mailbox the tenant connected.

`test_the_route_reaches_the_correlator` drives `GET /api/org/{org}/cohorts/{id}/correlations`
through the FastAPI app against a real Postgres. Layer 1 shipped six units that were built, green
and called by nothing on a real request path. Every other test in this file constructs the
correlator itself and would pass in a build where `main.py` never included the router.
"""

from __future__ import annotations

import ast
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.correlator import (MODERATE_FLOOR_BP, REGISTERED_PAIRS,
                                                       STRONG_FLOOR_BP, WEAK_FLOOR_BP,
                                                       CorrelationRefusal,
                                                       CorrelationRefusalReason, RegisteredPair,
                                                       _validated_registry,
                                                       correlate_pair_for_node,
                                                       correlate_pair_in_cohort, correlate_series,
                                                       correlate_values, correlations_for_org,
                                                       correlations_in_cohort, is_registered,
                                                       outcome_payload, paired_periods,
                                                       registered_pair, spearman_rho_bp,
                                                       strength_for)
from genios_engine.context.analytic.history import MetricGrain, period_start
from genios_engine.context.analytic.peer_baseline import staleness_floor
from genios_engine.contracts.analytic import (MIN_CORRELATION_SAMPLES, CorrelationStrength,
                                              MetricPoint, MetricUnit, MetricCorrelation)

UTC = timezone.utc

#: Every instant in this file is a parameter. Nothing here reads a clock.
AT = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)

_SOURCE = (Path(__file__).resolve().parents[3] / "genios_engine" / "context" / "analytic"
           / "correlator.py").read_text()

COHORT = "coh_growth_accounts"
BREADTH = "account.contact_breadth"
TOUCHES = "engagement.touch_count_28d"

#: A fixed permutation of 0..19 whose rank correlation with the identity is 1023 bp — inside the
#: NONE band, and stated as data so the "no association" case is a REAL number rather than a
#: shuffle that happens to be near zero on the day.
SCRAMBLE = (7, 3, 15, 1, 18, 11, 6, 19, 0, 13, 4, 17, 9, 2, 16, 8, 12, 5, 14, 10)


def _members(values, *, prefix: str = "n") -> dict[str, int]:
    return {f"{prefix}_{i:02d}": int(v) for i, v in enumerate(values)}


def _correlate(values_a, values_b, *, metric_a: str = BREADTH, metric_b: str = TOUCHES):
    return correlate_values(metric_a=metric_a, metric_b=metric_b, cohort_id=COHORT,
                            values_a=_members(values_a), values_b=_members(values_b),
                            eval_time=AT)


# =================================================================================================
# U1 · THE COEFFICIENT
# =================================================================================================

def test_perfect_positive_is_ten_thousand_and_strong() -> None:
    outcome = _correlate(range(20), range(20))
    assert isinstance(outcome, MetricCorrelation)
    assert outcome.rho_bp == 10_000
    assert outcome.strength is CorrelationStrength.STRONG
    assert outcome.n == 20
    assert outcome.cohort_id == COHORT


def test_perfect_negative_keeps_its_sign_and_its_strength() -> None:
    """The SIGN travels in `rho_bp`; the LABEL is on the magnitude. A strong inverse association
    is as strong as a strong positive one, and folding the sign into the word would leave a
    renderer no way to say which way it went."""
    outcome = _correlate(range(20), reversed(range(20)))
    assert isinstance(outcome, MetricCorrelation)
    assert outcome.rho_bp == -10_000
    assert outcome.strength is CorrelationStrength.STRONG


def test_no_association_is_an_answer_not_an_absence() -> None:
    outcome = _correlate(range(20), SCRAMBLE)
    assert isinstance(outcome, MetricCorrelation)
    assert outcome.rho_bp == 1_023
    assert outcome.strength is CorrelationStrength.NONE
    assert outcome.n == 20, "NONE still carries the population it was measured on"


def test_a_monotone_but_uneven_relationship_is_still_perfect_by_RANK() -> None:
    """Why rank correlation and not Pearson, in one assertion: one member's deal is a thousand
    times the median and the coefficient does not care, because rank sees "the largest one",
    which is all it actually is."""
    outsized = list(range(19)) + [19_000_000]
    assert _correlate(range(20), outsized).rho_bp == 10_000


@pytest.mark.parametrize("rho_bp,expected", [
    (0, CorrelationStrength.NONE),
    (2_999, CorrelationStrength.NONE),
    (WEAK_FLOOR_BP, CorrelationStrength.WEAK),
    (4_999, CorrelationStrength.WEAK),
    (MODERATE_FLOOR_BP, CorrelationStrength.MODERATE),
    (STRONG_FLOOR_BP, CorrelationStrength.MODERATE),      # doc 04's top band is `> 7000`
    (7_001, CorrelationStrength.STRONG),
    (10_000, CorrelationStrength.STRONG),
    (-2_999, CorrelationStrength.NONE),
    (-WEAK_FLOOR_BP, CorrelationStrength.WEAK),
    (-MODERATE_FLOOR_BP, CorrelationStrength.MODERATE),
    (-7_001, CorrelationStrength.STRONG),
])
def test_the_bands_are_on_the_magnitude_and_are_symmetric(rho_bp, expected) -> None:
    assert strength_for(rho_bp) is expected


def test_ties_average_their_ranks_and_stay_inside_the_signed_range() -> None:
    """Averaged ranks are halves; every rank in the module is held DOUBLED so no float appears.
    A tie-heavy pair is also where the `d^2` shortcut can overshoot, so the range is asserted."""
    tied_a = [0] * 10 + [1] * 10
    tied_b = [0] * 10 + [1] * 10
    outcome = _correlate(tied_a, [v + 1 for v in tied_b])
    assert isinstance(outcome, MetricCorrelation)
    assert -10_000 <= outcome.rho_bp <= 10_000
    assert outcome.strength is CorrelationStrength.STRONG
    # and the raw kernel never leaves the range either, on the worst tie pattern available
    assert -10_000 <= spearman_rho_bp(tied_a, list(reversed(tied_b))) <= 10_000


def test_a_metric_never_correlates_with_itself() -> None:
    outcome = _correlate(range(20), range(20), metric_a=BREADTH, metric_b=BREADTH)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.SAME_METRIC


def test_a_constant_metric_refuses_instead_of_reporting_a_perfect_association() -> None:
    """The single most dangerous arithmetic accident in the file. Every rank of a constant series
    ties, so every `d` is zero and the formula returns 10000 — a metric no tenant has ever varied
    would be STRONGLY correlated with everything on the page."""
    outcome = _correlate([4] * 20, range(20))
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.DEGENERATE_SERIES
    assert outcome.n == 20 and BREADTH in outcome.detail
    # These are the numbers the refusal exists to suppress. Two constants rank-tie perfectly and
    # score 10000; a constant against a real ramp still scores a confident MODERATE, purely
    # because every `d` on the tied side is measured from the same average rank.
    assert spearman_rho_bp([4] * 20, [9] * 20) == 10_000
    assert strength_for(spearman_rho_bp([4] * 20, list(range(20)))) is \
        CorrelationStrength.MODERATE
    both_constant = _correlate([4] * 20, [9] * 20)
    assert isinstance(both_constant, CorrelationRefusal)
    assert both_constant.reason is CorrelationRefusalReason.DEGENERATE_SERIES


# =================================================================================================
# THE SAMPLE FLOOR — doc 09's first requirement
# =================================================================================================

def test_at_the_floor_it_answers_and_one_below_it_refuses() -> None:
    assert MIN_CORRELATION_SAMPLES == 20
    at_floor = _correlate(range(20), range(20))
    assert isinstance(at_floor, MetricCorrelation) and at_floor.n == 20

    below = _correlate(range(19), range(19))
    assert isinstance(below, CorrelationRefusal)
    assert below.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS
    assert below.n == 19, "the refusal carries how close it was — 19 of the 20 this needs"
    assert "20" in below.detail


def test_six_perfectly_correlated_points_are_refused_not_reported() -> None:
    """A correlation over six points is noise wearing a coefficient. The data here is a PERFECT
    positive association and the answer is still no."""
    outcome = _correlate(range(6), range(6))
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS


def test_only_members_with_BOTH_readings_count_toward_the_floor() -> None:
    """Twenty-five members, twenty-five readings of A, six of B — the floor is measured on the
    PAIRS, not on the larger of the two sides."""
    values_a = _members(range(25))
    values_b = {f"n_{i:02d}": i for i in range(6)}
    outcome = correlate_values(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                               values_a=values_a, values_b=values_b, eval_time=AT)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS and outcome.n == 6


# =================================================================================================
# A GAP IS NOT A ZERO
# =================================================================================================

def _series(metric: str, values, *, first_period: datetime = AT,
            node: str = "n_00") -> list[MetricPoint]:
    """A dense weekly series. `None` is a HOLE — `known=False`, `value_bp=None` — which is exactly
    what `MetricHistoryStore.read_series` materialises for a period with no row."""
    points = []
    for offset, value in enumerate(values):
        period = first_period + timedelta(days=7 * offset)
        points.append(MetricPoint(subject_node_id=node, metric=metric,
                                  value_bp=None if value is None else int(value),
                                  unit=MetricUnit.COUNT, observed_at=period,
                                  known=value is not None))
    return points


def test_two_series_with_disjoint_gaps_pair_only_where_both_are_known() -> None:
    a_values = [None if i % 2 else i for i in range(48)]        # known on even periods
    b_values = [None if i % 3 else i for i in range(48)]        # known on periods divisible by 3
    xs, ys = paired_periods(_series(BREADTH, a_values), _series(TOUCHES, b_values))
    assert len(xs) == len(ys) == len([i for i in range(48) if i % 2 == 0 and i % 3 == 0])
    assert xs == ys == [i for i in range(48) if i % 6 == 0]
    assert None not in xs and None not in ys


def test_the_period_form_refuses_when_the_overlap_is_under_the_floor() -> None:
    """Each series has 24 known periods; they overlap on eight. Eight is the `n`."""
    a_values = [i if i % 2 == 0 else None for i in range(48)]
    b_values = [i if i % 3 == 0 else None for i in range(48)]
    outcome = correlate_series(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                               series_a=_series(BREADTH, a_values),
                               series_b=_series(TOUCHES, b_values), eval_time=AT)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS and outcome.n == 8


def test_the_period_form_answers_on_a_full_overlap() -> None:
    outcome = correlate_series(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                               series_a=_series(BREADTH, range(24)),
                               series_b=_series(TOUCHES, range(24)), eval_time=AT)
    assert isinstance(outcome, MetricCorrelation)
    assert outcome.n == 24 and outcome.rho_bp == 10_000


def test_a_hole_is_never_read_as_a_zero_by_the_period_form() -> None:
    """The same 24 periods twice: once with the holes as holes, once with the holes filled in as
    zeros. The honest read REFUSES on twelve pairs; the zero-filled read would have answered."""
    holed = [i if i % 2 == 0 else None for i in range(24)]
    filled = [i if i % 2 == 0 else 0 for i in range(24)]
    honest = correlate_series(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                              series_a=_series(BREADTH, holed),
                              series_b=_series(TOUCHES, range(24)), eval_time=AT)
    assert isinstance(honest, CorrelationRefusal) and honest.n == 12
    dishonest = correlate_series(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                                 series_a=_series(BREADTH, filled),
                                 series_b=_series(TOUCHES, range(24)), eval_time=AT)
    assert isinstance(dishonest, MetricCorrelation), "the difference is the `known` flag alone"


def test_zero_filling_the_holes_invents_a_strong_correlation() -> None:
    """THE TEST THIS COMPONENT EXISTS FOR.

    Forty accounts. `account.contact_breadth` is known for all of them. `engagement.touch_count`
    is known only for the twenty with the higher breadth — the shape a half-connected mailbox
    produces, not a coincidence. Zero-filling the other twenty yields 8008 bp, STRONG, and the
    sentence "the accounts we know more people at are the accounts we hear from more" — which is
    a statement about the connector. Intersecting yields 1023 bp, NONE, which is the truth.
    """
    breadth = _members(range(40))
    touches = {f"n_{i + 20:02d}": SCRAMBLE[i] for i in range(20)}

    naive_a = [breadth[f"n_{i:02d}"] for i in range(40)]
    naive_b = [touches.get(f"n_{i:02d}", 0) for i in range(40)]
    assert spearman_rho_bp(naive_a, naive_b) == 8_008
    assert strength_for(8_008) is CorrelationStrength.STRONG, "what zero-filling would report"

    outcome = correlate_values(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                               values_a=breadth, values_b=touches, eval_time=AT)
    assert isinstance(outcome, MetricCorrelation)
    assert outcome.n == 20, "only the members with both readings"
    assert outcome.rho_bp == 1_023
    assert outcome.strength is CorrelationStrength.NONE


# =================================================================================================
# THE CONTRACT — doc 09's requirements two and three
# =================================================================================================

def test_is_causal_is_false_on_every_object_and_cannot_be_set() -> None:
    outcome = _correlate(range(20), range(20))
    assert isinstance(outcome, MetricCorrelation) and outcome.is_causal is False
    with pytest.raises(Exception):
        MetricCorrelation(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT, rho_bp=9_000,
                          strength=CorrelationStrength.STRONG, n=20, is_causal=True)
    tree = ast.parse(_SOURCE)
    assigns_causal = [n for n in ast.walk(tree)
                      if isinstance(n, ast.keyword) and n.arg == "is_causal"]
    assert assigns_causal == [], "the correlator never supplies the field at all"


def test_the_cohort_is_mandatory_and_travels_with_the_finding() -> None:
    """Law 2. Two metrics that correlate across all accounts and not within a segment is the
    FINDING, and an unnamed population cannot tell those two apart."""
    with pytest.raises(Exception):
        correlate_values(metric_a=BREADTH, metric_b=TOUCHES, cohort_id="",
                         values_a=_members(range(20)), values_b=_members(range(20)),
                         eval_time=AT)
    refusal = _correlate(range(5), range(5))
    assert isinstance(refusal, CorrelationRefusal) and refusal.cohort_id == COHORT, (
        "the refusal names its population too")


def test_eval_time_is_a_parameter_and_the_module_reads_no_clock() -> None:
    with pytest.raises(ValueError):
        correlate_values(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                         values_a=_members(range(20)), values_b=_members(range(20)),
                         eval_time=datetime(2026, 3, 1, 9, 0))       # naive
    assert "datetime.now" not in _SOURCE and "utcnow" not in _SOURCE


def test_no_float_arithmetic_anywhere_in_the_module() -> None:
    tree = ast.parse(_SOURCE)
    assert [n for n in ast.walk(tree) if isinstance(n, ast.BinOp)
            and isinstance(n.op, ast.Div)] == [], "true division is how a score stops being exact"
    assert [n for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, float)] == []
    assert [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "float"] == []


def test_determinism_same_inputs_same_bytes() -> None:
    """Insertion order differs, the answer does not — the coefficient is computed over a sorted
    intersection, never over whatever order a mapping happened to be built in."""
    forward = {f"n_{i:02d}": v for i, v in enumerate(SCRAMBLE)}
    backward = {k: forward[k] for k in reversed(list(forward))}
    first = correlate_values(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                             values_a=_members(range(20)), values_b=forward, eval_time=AT)
    second = correlate_values(metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT,
                              values_a=_members(range(20)), values_b=backward, eval_time=AT)
    assert isinstance(first, MetricCorrelation)
    assert first.model_dump() == second.model_dump()
    for _ in range(5):
        assert spearman_rho_bp(list(range(20)), list(SCRAMBLE)) == 1_023


# =================================================================================================
# U2 · REGISTERED PAIRS — declared, never discovered
# =================================================================================================

def test_every_registered_pair_names_a_customer_question_and_a_sampled_metric() -> None:
    from genios_engine.context.analytic.sampler import sampler_registry
    registry = sampler_registry()
    assert REGISTERED_PAIRS, "a registry of no pairs is a component nothing can ask"
    for pair in REGISTERED_PAIRS:
        assert pair.metric_a in registry and pair.metric_b in registry
        assert pair.question.strip().endswith("?")
        assert is_registered(pair.metric_a, pair.metric_b)
        assert is_registered(pair.metric_b, pair.metric_a), "correlation is symmetric"


def test_an_undeclared_pair_is_refused_rather_than_measured() -> None:
    assert registered_pair(BREADTH, "support.ticket_count_28d") is None
    assert not is_registered(BREADTH, "support.ticket_count_28d")


@pytest.mark.parametrize("bad,reason", [
    ((RegisteredPair("account.contact_breadth", "not.a.metric", "?"),), "not a sampled metric"),
    ((RegisteredPair("account.contact_breadth", "account.contact_breadth", "?"),),
     "against itself"),
    ((RegisteredPair("account.contact_breadth", "engagement.touch_count_28d", "?"),
      RegisteredPair("engagement.touch_count_28d", "account.contact_breadth", "?")),
     "registered twice"),
    ((RegisteredPair("account.contact_breadth", "engagement.touch_count_28d", "  "),),
     "no customer question"),
])
def test_a_bad_registration_is_refused_at_import_not_at_the_request(bad, reason) -> None:
    with pytest.raises(ValueError) as err:
        _validated_registry(bad)
    assert reason in str(err.value)


def test_the_payload_carries_the_question_and_never_a_because() -> None:
    payload = outcome_payload(correlate_values(
        metric_a=BREADTH, metric_b=TOUCHES, cohort_id=COHORT, values_a=_members(range(20)),
        values_b=_members(range(20)), eval_time=AT))
    assert payload["correlation"]["is_causal"] is False
    assert payload["refusal"] is None
    assert payload["question"] == registered_pair(BREADTH, TOUCHES).question
    refusal_payload = outcome_payload(_correlate(range(5), range(5)))
    assert refusal_payload["correlation"] is None
    assert refusal_payload["refusal"]["reason"] == "insufficient_pairs"


# =================================================================================================
# THE READ PATH, ON A REAL POSTGRES
# =================================================================================================

def _drop_org(store, org: str) -> None:
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    with store.engine.begin() as conn:
        for table in _ORG_SCOPED_TABLES:
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


def _seed(store, org: str, *, breadth, touches, at: datetime = AT,
          cohort_id: str = COHORT, stale_touches: frozenset[int] = frozenset()) -> None:
    """A cohort with members, and the readings behind them. `breadth`/`touches` map node index to
    a value; an index ABSENT from a map is a member with no reading — no row, which is how
    migration 0094 stores a gap.

    `stale_touches` names indices whose touch reading is written 300 days back instead of seven:
    a connector that died last winter and left its last row behind. That is NOT the same thing as
    an absent index — the row exists, so a read bounded only by `observed_at <= :at` finds it and
    pairs it against another member's reading from this week.
    """
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Correlator tests') "
                          "on conflict (id) do nothing"), {"o": org})
        conn.execute(text(
            "insert into cohort_definitions (cohort_id, org_id, name, node_type, predicate, "
            "  created_by, created_at, active) values (:c, :o, 'Growth accounts', 'company', "
            "  cast('{\"all\": []}' as jsonb), 'system:default', :at, true) "
            "on conflict (cohort_id) do nothing"), {"c": cohort_id, "o": org, "at": at})
        nodes = sorted(set(breadth) | set(touches))
        for index in nodes:
            node_id = f"n_{index:02d}"
            conn.execute(text(
                "insert into cohort_membership (org_id, cohort_id, node_id, joined_at) "
                "values (:o, :c, :n, :at) on conflict do nothing"),
                {"o": org, "c": cohort_id, "n": node_id, "at": at - timedelta(days=30)})
        for metric, values in ((BREADTH, breadth), (TOUCHES, touches)):
            for index, value in values.items():
                dark = metric == TOUCHES and index in stale_touches
                conn.execute(text(
                    "insert into metric_history (org_id, subject_node_id, metric, value_bp, unit, "
                    "  observed_at, sampled_at, sample_reason) "
                    "values (:o, :n, :m, :v, 'count', :obs, :obs, 'scheduled') "
                    "on conflict do nothing"),
                    {"o": org, "n": f"n_{index:02d}", "m": metric, "v": int(value),
                     "obs": at - timedelta(days=300 if dark else 7)})


@pytest.mark.pg
def test_the_cohort_read_pairs_only_members_with_both_readings(pg_store) -> None:
    org = "org_correlator_read"
    _drop_org(pg_store, org)
    _seed(pg_store, org, breadth={i: i for i in range(40)},
          touches={i + 20: SCRAMBLE[i] for i in range(20)})
    try:
        outcome = correlate_pair_in_cohort(pg_store, org_id=org, cohort_id=COHORT,
                                           metric_a=BREADTH, metric_b=TOUCHES, eval_time=AT)
        assert isinstance(outcome, MetricCorrelation)
        assert outcome.n == 20, "the twenty members with no touch reading are not zeros"
        assert outcome.rho_bp == 1_023 and outcome.strength is CorrelationStrength.NONE

        # POINT-IN-TIME: an instant before the readings were observed sees none of them.
        earlier = correlate_pair_in_cohort(pg_store, org_id=org, cohort_id=COHORT,
                                           metric_a=BREADTH, metric_b=TOUCHES,
                                           eval_time=AT - timedelta(days=14))
        assert isinstance(earlier, CorrelationRefusal)
        assert earlier.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS and earlier.n == 0

        # REPLAYABLE: the same instant, twice, byte-identical.
        again = correlate_pair_in_cohort(pg_store, org_id=org, cohort_id=COHORT,
                                         metric_a=BREADTH, metric_b=TOUCHES, eval_time=AT)
        assert again.model_dump() == outcome.model_dump()

        # An undeclared pair is refused before any query runs.
        undeclared = correlate_pair_in_cohort(pg_store, org_id=org, cohort_id=COHORT,
                                              metric_a=BREADTH, metric_b="support.ticket_count_28d",
                                              eval_time=AT)
        assert isinstance(undeclared, CorrelationRefusal)
        assert undeclared.reason is CorrelationRefusalReason.NOT_REGISTERED

        # An unknown cohort is a named refusal, not an empty answer.
        missing = correlate_pair_in_cohort(pg_store, org_id=org, cohort_id="coh_nope",
                                           metric_a=BREADTH, metric_b=TOUCHES, eval_time=AT)
        assert isinstance(missing, CorrelationRefusal)
        assert missing.reason is CorrelationRefusalReason.NO_SUCH_COHORT

        every = correlations_in_cohort(pg_store, org_id=org, cohort_id=COHORT, eval_time=AT)
        assert len(every) == len(REGISTERED_PAIRS), "refusals are returned, never filtered out"
        by_org = correlations_for_org(pg_store, org_id=org, eval_time=AT)
        assert set(by_org) == {COHORT}
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_one_tenants_readings_never_reach_another_tenants_correlation(pg_store) -> None:
    """Two orgs sharing node ids and a cohort id. The coefficient must be computed entirely from
    one of them — `metric_history` and `cohort_membership` are both keyed with `org_id` FIRST, and
    a missing `where` here would silently pool two tenants into one 'population'."""
    mine, theirs = "org_correlator_mine", "org_correlator_theirs"
    for org in (mine, theirs):
        _drop_org(pg_store, org)
    _seed(pg_store, mine, breadth={i: i for i in range(20)},
          touches={i: SCRAMBLE[i] for i in range(20)}, cohort_id=COHORT)
    _seed(pg_store, theirs, breadth={i: i for i in range(20)},
          touches={i: i for i in range(20)}, cohort_id=COHORT)
    try:
        outcome = correlate_pair_in_cohort(pg_store, org_id=mine, cohort_id=COHORT,
                                           metric_a=BREADTH, metric_b=TOUCHES, eval_time=AT)
        assert isinstance(outcome, MetricCorrelation)
        assert outcome.n == 20, "not 40: the other tenant's members are not in this population"
        assert outcome.rho_bp == 1_023, "and not the other tenant's perfect 10000"
    finally:
        for org in (mine, theirs):
            _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_route_reaches_the_correlator(pg_store) -> None:
    """THE WIRING TEST. `GET /api/org/{org}/cohorts/{cohort_id}/correlations` through the app.

    Every other test in this file constructs the correlator itself and would pass in a build where
    `main.py` never included the router — which is exactly the state six Layer 1 units shipped in.
    """
    from fastapi.testclient import TestClient

    from genios_engine.api import correlation_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.main import app
    from genios_engine.platform.auth import get_current_org

    org = "org_correlator_route"
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    previous = R._graph
    R._graph = GraphStore(url)
    app.dependency_overrides[get_current_org] = lambda: org
    _drop_org(pg_store, org)
    # SEEDED AGAINST THE CLOCK, not against `AT`. The route reads the clock at the process
    # boundary (`_now`), and a reading is only counted while it is inside the staleness horizon
    # (`peer_baseline.STALE_AFTER_PERIODS`) — so a fixture pinned to March 2026 is, from any later
    # month, correctly read as a population of dark members and the route correctly refuses.
    # Anchoring the seed to the same clock the route reads keeps this test about the WIRING,
    # which is what it is for; `test_a_member_whose_source_went_dark_is_not_a_pair` is the test
    # that asserts the horizon itself.
    _seed(pg_store, org, breadth={i: i for i in range(40)},
          touches={i + 20: SCRAMBLE[i] for i in range(20)},
          at=datetime.now(timezone.utc))
    try:
        client = TestClient(app)
        response = client.get(f"/api/org/{org}/cohorts/{COHORT}/correlations",
                              params={"metric_a": BREADTH, "metric_b": TOUCHES})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["cohort_id"] == COHORT
        [result] = body["results"]
        assert result["correlation"]["rho_bp"] == 1_023
        assert result["correlation"]["strength"] == "none"
        assert result["correlation"]["n"] == 20
        assert result["correlation"]["is_causal"] is False
        assert result["question"] == registered_pair(BREADTH, TOUCHES).question

        # the whole declared set, refusals included
        every = client.get(f"/api/org/{org}/cohorts/{COHORT}/correlations").json()
        assert len(every["results"]) == len(REGISTERED_PAIRS)
        assert any(r["refusal"] is not None for r in every["results"])

        # the declared list is readable, and an undeclared pair is a 422, not a polite result
        pairs = client.get(f"/api/org/{org}/correlations/pairs").json()["pairs"]
        assert len(pairs) == len(REGISTERED_PAIRS) and all(p["question"] for p in pairs)
        assert client.get(f"/api/org/{org}/cohorts/{COHORT}/correlations",
                          params={"metric_a": BREADTH,
                                  "metric_b": "support.ticket_count_28d"}).status_code == 422
        assert client.get(f"/api/org/{org}/cohorts/{COHORT}/correlations",
                          params={"metric_a": BREADTH}).status_code == 422
        assert client.get(f"/api/org/other_org/cohorts/{COHORT}/correlations"
                          ).status_code == 403, "the path org must match the credential"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        _drop_org(pg_store, org)
        R._graph = previous


# =================================================================================================
# D6/D7 · A DEAD CONNECTOR IS NOT A PAIR
# =================================================================================================

@pytest.mark.pg
def test_a_member_whose_source_went_dark_is_not_a_pair(pg_store) -> None:
    """THE REFUSAL, PRODUCED BY THE PLUMBING. `MIN_CORRELATION_SAMPLES` was only ever exercised by
    handing the pure function a short list; the READ could not produce a short `n`, because it
    bounded `observed_at` from above only. Six of these twenty-five members last wrote a touch
    count 300 days ago — the row is still there, so without a lower bound they pair against
    breadth readings from this week and the coefficient describes two different years.

    The right `n` here is 19, and 19 is below the floor, so the honest answer is a refusal that
    tells the founder six sources are dead rather than a confident number over twenty-five.
    """
    org = "org_correlator_dark"
    _drop_org(pg_store, org)
    _seed(pg_store, org, breadth={i: i for i in range(25)},
          touches={i: SCRAMBLE[i % 20] + i for i in range(25)},
          stale_touches=frozenset(range(6)))
    try:
        outcome = correlate_pair_in_cohort(pg_store, org_id=org, cohort_id=COHORT,
                                           metric_a=BREADTH, metric_b=TOUCHES, eval_time=AT)
        assert isinstance(outcome, CorrelationRefusal), (
            "six members dark for ten months were counted as current readings")
        assert outcome.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS
        assert outcome.n == 19
        assert "19 members have both readings" in outcome.detail
    finally:
        _drop_org(pg_store, org)


# =================================================================================================
# D4 · THE TIME-SERIES FORM HAS A READ AND A ROUTE
# =================================================================================================

def test_a_mixed_grain_pair_is_refused_by_name_before_any_query_runs() -> None:
    """`engagement.touch_count_28d` is weekly and `deal.stage_age_days` is monthly (fixed there by
    `history.CORE_METRICS`), so their period boundaries almost never coincide and `paired_periods`
    has nothing to intersect. Left unnamed, that pair returns INSUFFICIENT_PAIRS for ever on every
    tenant, blaming the tenant's coverage for a fact about the registry.

    `store=None` is the assertion that the refusal happens before the database is touched.
    """
    outcome = correlate_pair_for_node(None, org_id="org_x", subject_node_id="n_01",
                                      metric_a="engagement.touch_count_28d",
                                      metric_b="deal.stage_age_days", eval_time=AT)
    assert isinstance(outcome, CorrelationRefusal)
    assert outcome.reason is CorrelationRefusalReason.MIXED_GRAIN
    assert outcome.cohort_id == "node:n_01", "the population is one node and it is named as one"
    assert "week" in outcome.detail and "month" in outcome.detail
    assert registered_pair("engagement.touch_count_28d", "deal.stage_age_days") is not None, (
        "this test is only meaningful while that pair is declared")


def _seed_series(store, org: str, node_id: str, *, at: datetime, periods: int,
                 values_a, values_b) -> None:
    """One node, `periods` weekly points of each metric, on exact period boundaries — which is
    what `read_series` walks, so an off-boundary row would read as a gap."""
    week = period_start(at, MetricGrain.WEEK)
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Correlator series') "
                          "on conflict (id) do nothing"), {"o": org})
        for k in range(periods):
            observed = week - timedelta(days=7 * k)
            for metric, values in ((BREADTH, values_a), (TOUCHES, values_b)):
                if values[k] is None:
                    continue                       # a period nobody measured: NO ROW
                conn.execute(text(
                    "insert into metric_history (org_id, subject_node_id, metric, value_bp, unit, "
                    "  observed_at, sampled_at, sample_reason) "
                    "values (:o, :n, :m, :v, 'count', :obs, :obs, 'scheduled') "
                    "on conflict do nothing"),
                    {"o": org, "n": node_id, "m": metric, "v": int(values[k]), "obs": observed})


@pytest.mark.pg
def test_the_period_form_reads_one_nodes_own_history(pg_store) -> None:
    """`correlate_series` and `paired_periods` were built, tested and reached by nothing — no
    route, no sweep. This is the read behind them, over one account's two years of weekly points.

    The holes matter as much as the points: two of these twenty-six periods have no touch reading
    at all, and `paired_periods` must drop those periods rather than pair a known breadth against
    an invented zero.
    """
    org = "org_correlator_series"
    node = "n_series_01"
    now = datetime.now(timezone.utc)
    _drop_org(pg_store, org)
    breadth = list(range(26))
    touches = [None if k in (3, 11) else 100 - 3 * k for k in range(26)]
    _seed_series(pg_store, org, node, at=now, periods=26, values_a=breadth, values_b=touches)
    try:
        outcome = correlate_pair_for_node(pg_store, org_id=org, subject_node_id=node,
                                          metric_a=BREADTH, metric_b=TOUCHES, eval_time=now)
        assert isinstance(outcome, MetricCorrelation), getattr(outcome, "detail", "")
        assert outcome.n == 24, "the two unmeasured periods were paired against something"
        assert outcome.rho_bp == -10_000, "breadth rises exactly as touches fall"
        assert outcome.strength is CorrelationStrength.STRONG
        assert outcome.cohort_id == f"node:{node}"
        assert outcome.is_causal is False

        # POINT-IN-TIME: an instant before any of it existed has nothing to pair.
        earlier = correlate_pair_for_node(pg_store, org_id=org, subject_node_id=node,
                                          metric_a=BREADTH, metric_b=TOUCHES,
                                          eval_time=now - timedelta(days=365))
        assert isinstance(earlier, CorrelationRefusal)
        assert earlier.reason is CorrelationRefusalReason.INSUFFICIENT_PAIRS

        # TENANT ISOLATION: the same node id under another org reads nothing.
        other = correlate_pair_for_node(pg_store, org_id="org_correlator_series_other",
                                        subject_node_id=node, metric_a=BREADTH, metric_b=TOUCHES,
                                        eval_time=now)
        assert isinstance(other, CorrelationRefusal) and other.n == 0
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_org_and_node_routes_reach_the_two_unwired_callables(pg_store) -> None:
    """THE WIRING TEST for `correlations_for_org` and `correlate_pair_for_node`. Both were public,
    both were green, neither was on a request path — the shape six Layer 1 units shipped in.

    Seeded against the clock, because both routes read it at the process boundary.
    """
    from fastapi.testclient import TestClient

    from genios_engine.api import correlation_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.main import app
    from genios_engine.platform.auth import get_current_org

    org = "org_correlator_wiring"
    node = "n_series_01"
    now = datetime.now(timezone.utc)
    previous = R._graph
    R._graph = GraphStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    app.dependency_overrides[get_current_org] = lambda: org
    _drop_org(pg_store, org)
    _seed(pg_store, org, breadth={i: i for i in range(20)},
          touches={i: SCRAMBLE[i] for i in range(20)}, at=now)
    _seed_series(pg_store, org, node, at=now, periods=26, values_a=list(range(26)),
                 values_b=[100 - 3 * k for k in range(26)])
    try:
        client = TestClient(app)

        # `correlations_for_org` — every cohort, with the truncation stated rather than silent.
        body = client.get(f"/api/org/{org}/correlations").json()
        assert [c["cohort_id"] for c in body["cohorts"]] == [COHORT]
        assert len(body["cohorts"][0]["results"]) == len(REGISTERED_PAIRS)
        assert body["truncated"] is False
        assert client.get(f"/api/org/{org}/correlations",
                          params={"limit": 0}).status_code == 422

        # `correlate_pair_for_node` — the period form, on one account.
        node_body = client.get(f"/api/org/{org}/nodes/{node}/correlations",
                               params={"metric_a": BREADTH, "metric_b": TOUCHES}).json()
        [result] = node_body["results"]
        assert result["correlation"]["rho_bp"] == -10_000
        assert result["correlation"]["n"] == 26
        assert result["correlation"]["cohort_id"] == f"node:{node}"
        assert result["correlation"]["is_causal"] is False
        assert result["question"] == registered_pair(BREADTH, TOUCHES).question

        # A declared-but-unanswerable pair is a 200 with its reason; an UNDECLARED one is a 422.
        mixed = client.get(f"/api/org/{org}/nodes/{node}/correlations",
                           params={"metric_a": "engagement.touch_count_28d",
                                   "metric_b": "deal.stage_age_days"})
        assert mixed.status_code == 200
        assert mixed.json()["results"][0]["refusal"]["reason"] == "mixed_grain"
        assert client.get(f"/api/org/{org}/nodes/{node}/correlations",
                          params={"metric_a": BREADTH,
                                  "metric_b": "support.ticket_count_28d"}).status_code == 422
        assert client.get(f"/api/org/other_org/correlations").status_code == 403
        assert client.get(f"/api/org/other_org/nodes/{node}/correlations",
                          params={"metric_a": BREADTH, "metric_b": TOUCHES}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        _drop_org(pg_store, org)
        R._graph = previous
