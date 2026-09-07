"""X0 · the Layer 2 v2 contract surface — the acceptance gate for this wave.

Doc 08's acceptance is two commands::

    pytest tests/contracts/test_l2_contracts.py -q     # 0 skips
    pytest tests/test_layer_topology.py -q

What is actually being asserted is not "the nine types exist" — an import proves that. It is
that each one REFUSES the object it was written to refuse, that the refusal survives a
serialize/reparse cycle (every one of these becomes a stored row: `context_situations`,
`metric_history`, `authority_rules`), and that the eight laws produce the exact outcome doc 08
assigns them.

Five properties run through the file:

* **Every number is an integer.** Asserted structurally by walking the JSON of a fully-populated
  `BusinessSituationObject`, because the `Any`-typed lanes (`metadata`, a conflict's claim values)
  are exactly where an annotation proves nothing.
* **The 5000 constant is unconstructible.** `context/situation_bso.py:39` stamps
  `DEFAULT_IMPORTANCE_BP` on every situation ever produced, which is the defect wave X5 exists to
  fix. This file proves the v2 contract will not let a midpoint arrive by omission and will not
  let an unscored situation carry one at all.
* **Every claim carries evidence.** A situation with no receipt, a matched condition with no span,
  a dependency link with no quote: all refused at construction.
* **The eight laws reject — all of them.** Unlike L1, where V-1 parks and V-5 downgrades. That
  difference is asserted directly, because getting a failure action backwards silently changes
  what reaches the layer above rather than failing loudly.
* **The v2 contract can express everything the v1 dataclass carries.** Asserted by porting a
  realistic v1 object field by field, with the field NAMES checked against
  `dataclasses.fields` so a lane that was quietly dropped fails the test rather than the cutover.

The law fixtures use `model_construct`, pydantic's documented way past a validator, because that
is precisely the route `validate_situation` exists to catch — an object that skipped its
constructor, or a row rehydrated by something that is not this class.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from genios_engine.contracts.analytic import (BAND_SCHEMES, MAX_TREND_CONFIDENCE_BP,
                                              MIN_ANOMALY_PERIODS, MIN_COHORT_POPULATION,
                                              MIN_CORRELATION_SAMPLES, MIN_TREND_POINTS, Anomaly,
                                              AnomalyDirection, CohortBand, CohortPosition,
                                              CorrelationStrength, Measurement, MetricCorrelation,
                                              MetricPoint, MetricUnit, Trend, TrendDirection,
                                              expressible_divisions)
from genios_engine.contracts.authority import (NO_AUTHORITY_RULE, AuthorityRule, AuthoritySource)
from genios_engine.contracts.conflict import (Authority, Conflict, ConflictClaim,
                                              ConflictResolution)
from genios_engine.contracts.dependency import (MAX_DEPENDENCY_DEPTH, DependencyChain,
                                                DependencyLink)
from genios_engine.contracts.domain_expertise import (BUSINESS_SITUATION_VERSION,
                                                      BusinessSituationObject as SituationV1)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.quality import AbsenceType, MissingFact
from genios_engine.contracts.situation import (BUSINESS_SITUATION_V2_VERSION, CONFIDENCE_AXES,
                                               LAW_ACTIONS, SITUATION_STATES,
                                               BusinessSituationObject, ConfidenceVector,
                                               ImportanceAttribution, ImportanceBasis, L2Law,
                                               LawAction, MatchedCondition, SituationEntity,
                                               SituationOutcome, SituationRelationship,
                                               TimelinePoint, validate_situation)
from genios_engine.contracts.units import Money
from genios_engine.contracts.visibility import Visibility

#: The two shapes a contract refusal takes here. The shared helpers in `contracts/validators.py`
#: fail closed by raising TypeError for a wrong TYPE (a float where basis points belong, a string
#: where a bool belongs) and ValueError for a wrong VALUE (out of range, outside a closed set) —
#: and pydantic wraps only the second into a `ValidationError`. A test naming only one of them
#: would pass for the wrong reason on half the rules, which is why
#: `tests/contracts/test_l1_contracts.py` parametrizes the same distinction. Construction
#: SUCCEEDING still fails every test below, so the tuple costs no strength.
REFUSED = (ValidationError, TypeError)

#: One frozen instant for the whole file. Every evaluation in these contracts takes its instant
#: as a parameter, so a test that read the clock would be testing a different object each run.
EVAL_TIME = datetime(2026, 3, 14, 9, 30, tzinfo=timezone.utc)


# ------------------------------------------------------------------------------ builders

def span(quote: str, *, start: int = 310, source_ref: str = "prepared_content:evt_7f31",
         verified: bool = True) -> EvidenceSpan:
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=verified)


def point(*, value: int | None = 42, known: bool = True, days_ago: int = 0,
          metric: str = "account.reply_count", unit: MetricUnit = MetricUnit.COUNT,
          currency: str | None = None, coverage_ready: bool | None = True,
          subject_node_id: str = "node_acc_42") -> MetricPoint:
    return MetricPoint(subject_node_id=subject_node_id, metric=metric, value_bp=value, unit=unit,
                       currency=currency, observed_at=EVAL_TIME - timedelta(days=days_ago),
                       known=known, coverage_ready=coverage_ready)


def series(count: int = 6, *, gaps: int = 0) -> tuple[MetricPoint, ...]:
    """A declining series, oldest first, with `gaps` unknown periods at the end."""
    known = tuple(point(value=100 - index * 10, days_ago=(count - index) * 30)
                  for index in range(count))
    missing = tuple(point(value=None, known=False, days_ago=index) for index in range(gaps))
    return known + missing


def trend(**overrides: Any) -> Trend:
    base: dict[str, Any] = dict(
        metric="account.reply_count", direction=TrendDirection.DECLINING,
        relative_slope_bp=-1_200, streak_periods=6, point_count=6,
        coverage_ratio_bp=10_000, trend_confidence_bp=6_400, evidence_points=series())
    base.update(overrides)
    return Trend(**base)


def cohort(**overrides: Any) -> CohortPosition:
    base: dict[str, Any] = dict(
        metric="account.reply_count", cohort_id="accounts_by_arr_quartile:q4",
        population_size=37, percentile_bp=800, band=CohortBand.D1,
        p25_bp=12, p50_bp=40, p75_bp=95, computed_at=EVAL_TIME)
    base.update(overrides)
    return CohortPosition(**base)


def correlation(**overrides: Any) -> MetricCorrelation:
    base: dict[str, Any] = dict(
        metric_a="account.reply_count", metric_b="account.meeting_count",
        cohort_id="all_active_accounts", rho_bp=6_200,
        strength=CorrelationStrength.MODERATE, n=24, is_causal=False)
    base.update(overrides)
    return MetricCorrelation(**base)


def anomaly(**overrides: Any) -> Anomaly:
    base: dict[str, Any] = dict(
        metric="account.reply_count", current_bp=12, baseline_bp=94, mad_bp=9,
        deviation_bp=8_723, z_like_bp=91_111, direction=AnomalyDirection.BELOW,
        periods_used=9)
    base.update(overrides)
    return Anomaly(**base)


def missing_fact(**overrides: Any) -> MissingFact:
    base: dict[str, Any] = dict(
        subject_node_id="deepthi+renewals@globeworked.com",
        expected_fact="contract.owner_node_id", absence_type=AbsenceType.GENUINELY_ABSENT,
        coverage_ready=True, coverage_basis=("gmail", "gdrive"))
    base.update(overrides)
    return MissingFact(**base)


def authority_rule(**overrides: Any) -> AuthorityRule:
    base: dict[str, Any] = dict(
        rule_id="rule_contract_5cr", subject_type="contract",
        threshold_minor_units=500_000_000, currency="INR",
        approver_node_id="rohit+approvals@antler.co", delegate_node_id=None,
        source=AuthoritySource.ADMIN_DECLARED, evidence_ref=None,
        valid_from=EVAL_TIME - timedelta(days=90), valid_until=None)
    base.update(overrides)
    return AuthorityRule(**base)


def link(blocker: str, blocked: str, **overrides: Any) -> DependencyLink:
    base: dict[str, Any] = dict(
        blocker=blocker, blocked=blocked, dependency_type="approval",
        evidence=(span("we cannot ship until legal signs off"),), resolved=False)
    base.update(overrides)
    return DependencyLink(**base)


def chain(**overrides: Any) -> DependencyChain:
    base: dict[str, Any] = dict(
        chain_id="chain_7f31",
        links=(link("legal@globeworked.com", "deepthi@globeworked.com"),
               link("deepthi@globeworked.com", "renewal_msa_2026")),
        circular_wait=False, truncated=False, blocked_count=4)
    base.update(overrides)
    return DependencyChain(**base)


def importance(**overrides: Any) -> ImportanceAttribution:
    base: dict[str, Any] = dict(
        basis=ImportanceBasis.COMPOSED, score_bp=7_400, base_bp=8_100,
        version="l2.blg18.v1",
        components={"base": 8_100, "corroboration": 1_000, "trend": 1_000,
                    "staleness": -1_500, "coverage_penalty": -1_300})
    base.update(overrides)
    return ImportanceAttribution(**base)


def confidence(**overrides: Any) -> ConfidenceVector:
    base: dict[str, Any] = dict(
        evidence_bp=9_000, freshness_bp=8_800, consistency_bp=7_200, identity_bp=6_400,
        coverage_bp=None, analytic_bp=5_000, overall_bp=6_400,
        composed_from=("evidence", "freshness", "consistency", "identity"))
    base.update(overrides)
    return ConfidenceVector(**base)


def conflict_74k_vs_84k() -> Conflict:
    return Conflict(
        field="contract.value",
        claims=[
            ConflictClaim(value=Money(minor_units=7_400_000, currency="USD",
                                      as_written="$74,000"),
                          authority=Authority.SIGNED_DOCUMENT, authority_rank=6,
                          evidence=[span("Total annual commitment: $74,000",
                                         source_ref="chunk:doc_msa_2026:3")]),
            ConflictClaim(value=Money(minor_units=8_400_000, currency="USD",
                                      as_written="$84K"),
                          authority=Authority.EMAIL_PROSE, authority_rank=2,
                          evidence=[span("the $84K annual contract")]),
        ],
        resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
        resolved_value=Money(minor_units=7_400_000, currency="USD", as_written="$74,000"),
        detected_at=EVAL_TIME)


def situation_kwargs(**overrides: Any) -> dict[str, Any]:
    """Every v2 field, valid, as kwargs — so a fixture can break exactly one of them.

    Returned as kwargs rather than as a built object because the law fixtures need
    `model_construct`, which does not run validators but also does not invent the fields it was
    not given: a partially constructed situation raises `AttributeError` inside V-8's walk
    instead of being rejected as the malformed object the gate is meant to record.
    """
    base: dict[str, Any] = dict(
        org_id="org_7173",
        trace_id="trace_9c2a1f",
        visibility=Visibility(scope="participants",
                              principals=["deepthi@globeworked.com", "rohit@antler.co"],
                              derived_from="l2:narrowest_of_members"),
        schema_version=BUSINESS_SITUATION_V2_VERSION,
        id="sit_0f21ab",
        type="renewal_at_risk",
        state="active",
        domain_ids=("sales", "legal"),
        signal_ids=("sig_0e88cd", "sig_0f21ab"),
        entities=(SituationEntity(id="deepthi@globeworked.com", type="external_contact",
                                  name="Deepthi", event_count=12),
                  SituationEntity(id="globeworked.com", type="organization",
                                  name="Globe Worked")),
        relationships=(SituationRelationship(source_id="deepthi@globeworked.com",
                                             target_id="globeworked.com", kind="works_at",
                                             confidence_bp=9_100),),
        timeline=(TimelinePoint(at=EVAL_TIME - timedelta(days=61), label="first_seen",
                                ref="evt_7f31"),
                  TimelinePoint(at=EVAL_TIME - timedelta(days=2), label="last_seen")),
        dependencies=(chain(),),
        evidence=(span("the $84K annual contract"),
                  span("Total annual commitment: $74,000", source_ref="chunk:doc_msa_2026:3")),
        provenance_refs=("evt_7f31", "graph_ref:node_991"),
        confidence=confidence(),
        coverage_ready=True,
        conflicts=(conflict_74k_vs_84k(),),
        conflict_ids=("cf_0021",),
        missing_facts=(missing_fact(),
                       missing_fact(expected_fact="contract.amendment_ref",
                                    absence_type=AbsenceType.UNKNOWABLE,
                                    coverage_ready=None, coverage_basis=())),
        importance=importance(),
        trends=(trend(),),
        cohort_positions=(cohort(),),
        anomalies=(anomaly(),),
        correlations=(correlation(),),
        pattern_id="renewal_no_owner_v3",
        matched_conditions=(MatchedCondition(field_path="contract.renewal_date",
                                             operator="within_days", expected=30, observed=17,
                                             evidence=(span("renews on 31 March"),)),
                            MatchedCondition(field_path="contract.owner_node_id",
                                             operator="exists", expected=True, observed=False,
                                             evidence=(span("nobody has picked this up"),))),
        metadata={"shadow": True, "l1_signal_count": 2, "split_required": False},
    )
    base.update(overrides)
    return base


def situation(**overrides: Any) -> BusinessSituationObject:
    return BusinessSituationObject(**situation_kwargs(**overrides))


def bypassed(**overrides: Any) -> BusinessSituationObject:
    """A situation that skipped its constructor. Not contrived: `model_construct` is pydantic's
    documented way past a validator, and a row rehydrated by anything that is not this class
    takes the same route. V-1..V-8 exist so an object that took it is refused rather than read."""
    return BusinessSituationObject.model_construct(**situation_kwargs(**overrides))


def assert_round_trips(obj: Any) -> Any:
    """Serialize, reparse, and prove BOTH directions.

    Object equality alone is not enough: a field that rehydrated as a near-equal value would still
    pass it. Re-dumping and comparing the bytes is what proves a stored row is stable under the
    read-modify-write cycle every one of these types actually undergoes.
    """
    raw = obj.model_dump_json()
    back = type(obj).model_validate_json(raw)
    assert back == obj, f"{type(obj).__name__} did not survive a JSON round-trip"
    assert back.model_dump_json() == raw, f"{type(obj).__name__} re-serialized differently"
    from_dict = type(obj).model_validate(json.loads(raw))
    assert from_dict == obj, f"{type(obj).__name__} did not survive model_validate(dict)"
    return back


def walk_json(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    """Every scalar in a decoded JSON document, with the path that reaches it."""
    if isinstance(value, dict):
        return [leaf for key, item in value.items() for leaf in walk_json(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [leaf for index, item in enumerate(value)
                for leaf in walk_json(item, f"{path}[{index}]")]
    return [(path, value)]


# ------------------------------------------------------- the nine types construct + round-trip

NINE_TYPES = [
    ("D-01 BusinessSituationObject", situation),
    ("D-02 MetricPoint", point),
    ("D-03 Trend", trend),
    ("D-04 CohortPosition", cohort),
    ("D-05 MetricCorrelation", correlation),
    ("D-06 Anomaly", anomaly),
    ("D-07 MissingFact", missing_fact),
    ("D-08 AuthorityRule", authority_rule),
    ("D-09 DependencyChain", chain),
]


@pytest.mark.parametrize("contract_id,build", NINE_TYPES, ids=[row[0] for row in NINE_TYPES])
def test_every_l2_type_constructs_and_round_trips(contract_id, build):
    """Each type becomes a stored row; a contract that validates on the way in and not on the way
    back out holds for exactly as long as the process that built the object."""
    assert_round_trips(build())


def test_the_inventory_is_nine_types():
    """Doc 08's inventory is D-01..D-09. Pinned so a tenth type added without a doc change fails
    here rather than arriving unreviewed at the seam."""
    assert len(NINE_TYPES) == 9


# ------------------------------------------------------------------- D-02 · MetricPoint

@pytest.mark.parametrize("label,kwargs,message", [
    ("interpolated", dict(known=False, value=4_200), "known=False"),
    ("claimed but empty", dict(known=True, value=None), "must carry a value"),
    ("money with no currency", dict(unit=MetricUnit.MINOR_UNITS, currency=None), "currency"),
    ("currency on a count", dict(unit=MetricUnit.COUNT, currency="USD"), "meaningless"),
])
def test_metric_point_refuses_incoherent_readings(label, kwargs, message):
    with pytest.raises(ValidationError) as caught:
        point(**kwargs)
    assert message in str(caught.value)


@pytest.mark.parametrize("label,kwargs", [
    ("absent", dict(subject_node_id=None)),
    ("blank", dict(subject_node_id="   ")),
    ("unsupported characters", dict(subject_node_id="node 42; drop table")),
])
def test_metric_point_must_name_the_subject_it_was_measured_on(label, kwargs):
    """`metric_history`'s primary key is `(org_id, subject_node_id, metric, observed_at)`. A
    point that does not name its subject cannot be written to that table, cannot be read back,
    and cannot answer "where did this percentile come from" — and a DEFAULTED subject is worse
    than a missing one, because two accounts' readings then share one column and every trend
    computed over them typechecks."""
    with pytest.raises(ValidationError):
        point(**kwargs)


def test_a_trend_carries_one_subjects_series_and_not_two():
    """The `metric` agreement check's other half. Interleaving two accounts' readings produces a
    slope neither account has, and nothing downstream could detect it: every point is genuine."""
    mine = point(value=100, days_ago=60)
    theirs = point(value=10, days_ago=30, subject_node_id="node_acc_99")
    with pytest.raises(ValidationError) as caught:
        trend(evidence_points=series() + (theirs,), point_count=7)
    assert "one subject" in str(caught.value)
    assert trend(evidence_points=series() + (mine,), point_count=7).point_count == 7


def test_metric_point_accepts_money_with_a_currency():
    """The positive of the rule above — the shape a real ARR sample takes."""
    money = point(unit=MetricUnit.MINOR_UNITS, currency="INR", value=8_400_000)
    assert assert_round_trips(money).currency == "INR"


@pytest.mark.parametrize("bad", [0.42, True, "42"])
def test_metric_point_refuses_a_non_integer_measurement(bad):
    """A float rounds to an integer in pydantic's lax mode and is stored as a measurement; a
    bool is an int the annotation would happily accept as 1. All three are TYPE refusals."""
    with pytest.raises(TypeError):
        point(value=bad)


def test_metric_point_coverage_is_tri_state():
    assert point(coverage_ready=None).coverage_ready is None
    with pytest.raises(TypeError):
        point(coverage_ready="")


# ------------------------------------------------------------------------ D-03 · Trend

def test_trend_refuses_certainty_v4():
    with pytest.raises(ValidationError) as caught:
        trend(trend_confidence_bp=MAX_TREND_CONFIDENCE_BP + 1)
    assert "never certain" in str(caught.value)


def test_trend_at_the_cap_is_legal():
    """The boundary is inclusive — a rule that rejected 8000 would be a different rule."""
    assert trend(trend_confidence_bp=MAX_TREND_CONFIDENCE_BP).trend_confidence_bp == 8_000


@pytest.mark.parametrize("direction", [TrendDirection.RISING, TrendDirection.DECLINING])
def test_trend_refuses_a_direction_on_too_few_points_v5(direction):
    with pytest.raises(ValidationError) as caught:
        trend(direction=direction, point_count=MIN_TREND_POINTS - 1,
              relative_slope_bp=900 if direction is TrendDirection.RISING else -900)
    assert "no series" in str(caught.value)


def test_trend_flat_on_three_points_is_legal():
    """V-5 names RISING and DECLINING. FLAT on a short series is a legitimate answer and must
    not be swept up by a rule written for the other two."""
    assert trend(direction=TrendDirection.FLAT, point_count=3, relative_slope_bp=0,
                 streak_periods=0).direction is TrendDirection.FLAT


@pytest.mark.parametrize("direction", [TrendDirection.INSUFFICIENT_HISTORY,
                                       TrendDirection.INSUFFICIENT_COVERAGE])
def test_a_refusal_carries_no_confidence_and_no_streak(direction):
    with pytest.raises(ValidationError) as caught:
        trend(direction=direction, relative_slope_bp=0, streak_periods=2,
              trend_confidence_bp=3_000)
    assert "refusal to answer" in str(caught.value)


def test_a_refusal_with_zeroed_strength_is_legal():
    honest = trend(direction=TrendDirection.INSUFFICIENT_COVERAGE, relative_slope_bp=0,
                   streak_periods=0, trend_confidence_bp=0, point_count=2,
                   coverage_ratio_bp=3_300, evidence_points=series(2, gaps=4))
    assert assert_round_trips(honest).known_points == 2


@pytest.mark.parametrize("direction,slope", [(TrendDirection.RISING, -100),
                                             (TrendDirection.DECLINING, 100)])
def test_trend_direction_and_slope_must_agree(direction, slope):
    with pytest.raises(ValidationError) as caught:
        trend(direction=direction, relative_slope_bp=slope)
    assert "slope" in str(caught.value)


def test_trend_requires_points_and_refuses_a_receipt_for_another_metric():
    with pytest.raises(ValidationError) as caught:
        trend(evidence_points=())
    assert "no series" in str(caught.value) or "receipt" in str(caught.value)
    with pytest.raises(ValidationError) as caught:
        trend(evidence_points=(point(metric="account.meeting_count"),))
    assert "different metric" in str(caught.value)


# ---------------------------------------------------------------- D-04 · CohortPosition

def test_cohort_position_requires_its_population_v1():
    """Law 2 as a TYPE property: `cohort_id` is non-optional with no default, so an unnamed
    population is unconstructible rather than merely discouraged."""
    with pytest.raises(ValidationError):
        cohort(cohort_id="")
    with pytest.raises(ValidationError):
        cohort(population_size=None)


def test_cohort_position_refuses_a_population_under_five_v2():
    with pytest.raises(ValidationError) as caught:
        cohort(population_size=MIN_COHORT_POPULATION - 1)
    assert "ranks individuals" in str(caught.value)
    assert cohort(population_size=MIN_COHORT_POPULATION).population_size == 5


def test_the_band_must_contain_the_percentile():
    """"Bottom decile" beside a median is the single most quotable dishonest thing this system
    could say. The label and the number are checked against each other."""
    with pytest.raises(ValidationError) as caught:
        cohort(percentile_bp=5_000, band=CohortBand.D1)
    assert "must agree" in str(caught.value)


@pytest.mark.parametrize("percentile,divisions,expected", [
    (0, 10, CohortBand.D1), (999, 10, CohortBand.D1), (1_000, 10, CohortBand.D2),
    (10_000, 10, CohortBand.D10), (2_499, 4, CohortBand.Q1), (2_500, 4, CohortBand.Q2),
    (10_000, 4, CohortBand.Q4),
])
def test_band_for_percentile_is_deterministic_integer_arithmetic(percentile, divisions, expected):
    band = CohortBand.for_percentile(percentile, divisions=divisions)
    assert band is expected
    assert band.contains(percentile)


def test_cohort_distribution_must_be_ordered():
    with pytest.raises(ValidationError) as caught:
        cohort(p25_bp=90, p50_bp=40, p75_bp=95)
    assert "ordered" in str(caught.value)


# ------------------------------------------- D-04 · V-8, the band the population can REACH
#
# The defect: `for_percentile` bands on left-closed `[low, high)`, but nearest rank counts the
# subject itself — `percentile_bp = rank * 10000 // n` with `rank` in 1..n — so the smallest
# percentile a cohort of n can produce is `10000 // n`, never 0. Every decile below that is
# arithmetically empty, which made "bottom decile" — the phrase the product promises, and the one
# `comparator.py:129` says a quartile cannot express — unsayable for every cohort of ten or fewer.
# The sweep's `most_specific` publishes the SMALLEST population on purpose, so those are exactly
# the cohorts it selects.
#
# WHY A GREEN SUITE NEVER NOTICED: every D1 assertion in this repository was on `for_percentile(0)`
# or on a hand-built `CohortPosition(percentile_bp=800)`. Not one went through the arithmetic that
# actually produces a percentile. So the two tests below are computed from `position_from_values`
# over real populations, and the band table is PINNED per population size.


def _published_bands(size: int, divisions: int) -> set[str]:
    """Every band `position_from_values` can actually publish over a population of `size`.

    Imports the producer rather than reproducing its arithmetic: the contract is what has to stop
    an unreachable label, and a test that recomputed the percentile here would be pinning its own
    copy of the rule instead of the one that ships.
    """
    from genios_engine.context.analytic.cohort import position_from_values
    values = {f"node_{index:03d}": index * 7 for index in range(size)}
    published = set()
    for node_id in values:
        outcome = position_from_values(metric="engagement.touch_count_28d", cohort_id="coh",
                                       values=values, subject_node_id=node_id,
                                       eval_time=EVAL_TIME, divisions=divisions)
        assert isinstance(outcome, CohortPosition)
        assert outcome.band.contains(outcome.percentile_bp)
        published.add(outcome.band.value)
    return published


@pytest.mark.parametrize("size", list(range(5, 13)))
def test_the_published_band_table_has_no_empty_bands(size: int):
    """THE TABLE, for n = 5..12, computed from the producer. Every band of the scheme a position
    is labelled in must be reachable by SOME member of the population — otherwise a card's
    vocabulary contains a word the arithmetic can never say.

    Below eleven the scheme degrades to quartiles, which the floor of five already supports
    (`10000 // 5 = 2000 < 2500`), and all four are produced. At eleven, deciles become expressible
    and all ten are produced.
    """
    expected_divisions = 10 if size > 10 else 4
    letter = "D" if expected_divisions == 10 else "Q"
    assert _published_bands(size, 10) == {f"{letter}{i}" for i in range(1, expected_divisions + 1)}
    # and a caller that explicitly asks for quartiles gets all four at every size in the range
    assert _published_bands(size, 4) == {"Q1", "Q2", "Q3", "Q4"}


@pytest.mark.parametrize("size,reachable", [
    (5, {3, 5, 7, 9, 10}), (6, {2, 4, 6, 7, 9, 10}), (7, {2, 3, 5, 6, 8, 9, 10}),
    (8, {2, 3, 4, 6, 7, 8, 9, 10}), (9, set(range(2, 11))), (10, set(range(2, 11))),
    (11, set(range(1, 11))), (12, set(range(1, 11))),
])
def test_the_raw_decile_arithmetic_is_what_forced_the_degrade(size: int, reachable: set[int]):
    """The measurement that made V-8 necessary, pinned so the reason cannot be lost: asked for
    deciles WITHOUT the population, the nearest-rank percentile can only ever land in these bands.

    The worst account in a five-member cohort published as `D3` — which reads as "below average,
    not alarming" — and D1 first appears at n=11. Note the off-by-one against the obvious rule:
    at n=10 the smallest reachable percentile is exactly 1000, the FIRST basis point of D2, so
    `population_size >= divisions` is NOT the condition. It is strictly greater.
    """
    landed = {CohortBand.for_percentile(min(rank * 10_000 // size, 10_000), divisions=10).index
              for rank in range(1, size + 1)}
    assert landed == reachable
    assert (1 in landed) is (size > 10)


@pytest.mark.parametrize("size,requested,expected", [
    (5, 10, 4), (10, 10, 4), (11, 10, 10), (5, 4, 4), (100, 4, 4), (10_000, 10, 10),
])
def test_expressible_divisions_is_strictly_greater_than_the_scheme(size, requested, expected):
    assert expressible_divisions(size, requested=requested) == expected
    assert BAND_SCHEMES == (10, 4)


def test_a_population_that_can_express_nothing_is_refused_rather_than_relabelled():
    """Below five there is no scheme to degrade TO, and V-2 already refuses the position — so this
    raises rather than inventing a two-band vocabulary nobody renders."""
    with pytest.raises(ValueError) as caught:
        expressible_divisions(4, requested=10)
    assert "can express no band scheme" in str(caught.value)


def test_a_decile_label_over_a_cohort_that_cannot_produce_one_is_narrowed_to_a_quartile():
    """V-8 at the constructor: the caller stated `D3` for the worst member of a five-member cohort
    — truthful in its own scheme, unreachable in that population — and gets back the quartile the
    population can actually produce. The percentile is untouched; only the WORD changes, to one
    the arithmetic can say."""
    narrowed = cohort(population_size=5, percentile_bp=2_000, band=CohortBand.D3)
    assert narrowed.band is CohortBand.Q1
    assert narrowed.percentile_bp == 2_000
    assert narrowed.band.contains(narrowed.percentile_bp)
    # eleven members, and the same call keeps the decile it asked for
    assert cohort(population_size=11, percentile_bp=909, band=CohortBand.D1).band is CohortBand.D1


def test_narrowing_never_launders_a_band_that_disagrees_with_its_number():
    """The repair is scoped to the SCHEME. A band that does not contain its percentile is passed
    through untouched so the "must agree" refusal still fires — recomputing the band from the
    percentile would silently fix every mismatched pair that check exists to catch."""
    with pytest.raises(ValidationError) as caught:
        cohort(population_size=5, percentile_bp=9_000, band=CohortBand.D3)
    assert "must agree" in str(caught.value)


def test_the_narrowed_band_survives_the_round_trip_and_a_copy():
    """It is a stored row and a copied object, not just a constructor outcome."""
    narrowed = cohort(population_size=6, percentile_bp=3_333, band=CohortBand.D4)
    assert narrowed.band is CohortBand.Q2
    assert CohortPosition.model_validate(json.loads(narrowed.model_dump_json())).band is (
        CohortBand.Q2)
    assert narrowed.model_copy(update={"cohort_id": "coh_other"}).band is CohortBand.Q2


# ------------------------------------------------------------- Measurement · revalidation on copy
#
# `model_copy(update=...)` runs NO validator in pydantic v2, and it is a live idiom in this
# codebase (`authority_view.py:456`), so on a plain frozen model one line —
# `correlation.model_copy(update={"is_causal": True})` — produced a well-typed object carrying the
# causal claim V-7 exists to make unconstructible. `Measurement` re-enters the constructor on any
# copy WITH an update. Asserted across every subclass rather than on `MetricCorrelation` alone,
# because the hole was never specific to `is_causal`: it widened every law in the module.


def test_every_measurement_subclass_re_enters_its_constructor_on_copy():
    """The base is only worth having if nothing inherits around it. Walked, so a ninth type added
    later is covered by this test the day it is written rather than the day it is reviewed."""
    subclasses = {cls.__name__ for cls in Measurement.__subclasses__()}
    assert subclasses == {"MetricPoint", "Trend", "CohortPosition", "MetricCorrelation", "Anomaly"}
    for cls in Measurement.__subclasses__():
        assert cls.model_copy is Measurement.model_copy, f"{cls.__name__} overrides model_copy"


@pytest.mark.parametrize("build,update,message", [
    (correlation, {"is_causal": True}, "never cause"),
    (correlation, {"n": 3}, "by chance"),
    (cohort, {"population_size": 2}, "ranks individuals"),
    (trend, {"trend_confidence_bp": 9_999}, "never certain"),
    (anomaly, {"periods_used": 2}, "at least"),
])
def test_a_copy_cannot_smuggle_past_a_law(build, update, message):
    """Each of these was reachable in one line before the base re-validated: a causal claim, a
    four-point correlation, a cohort of two, a certain trend, an anomaly with no baseline."""
    with pytest.raises(ValidationError) as caught:
        build().model_copy(update=update)
    assert message in str(caught.value)


def test_a_copy_with_no_update_is_the_same_fields_and_pays_nothing():
    original = correlation()
    assert original.model_copy().model_dump() == original.model_dump()


def test_model_construct_is_still_the_documented_bypass():
    """Deliberately left open. It is pydantic's "I know what I am doing" door, the fixtures in
    this file use it to build the objects the LAWS must reject, and what exists for objects that
    came through it is `validate_situation` — which runs the same laws over an assembled
    situation. Stated as a test so a future reader does not "fix" it and take the law fixtures
    with it."""
    smuggled = MetricCorrelation.model_construct(
        metric_a="a", metric_b="b", cohort_id="c", rho_bp=100,
        strength=CorrelationStrength.WEAK, n=3, is_causal=True)
    assert smuggled.is_causal is True
    with pytest.raises(ValidationError):
        MetricCorrelation.model_validate(smuggled.model_dump())


# ------------------------------------------------------------- D-05 · MetricCorrelation

def test_correlation_refuses_a_small_sample_v6():
    with pytest.raises(ValidationError) as caught:
        correlation(n=MIN_CORRELATION_SAMPLES - 1)
    assert "by chance" in str(caught.value)
    assert correlation(n=MIN_CORRELATION_SAMPLES).n == 20


def test_correlation_is_never_causal_v7():
    """The rule that makes it structurally impossible for any layer above to RECEIVE a causal
    claim from L2, no matter what it asks for."""
    with pytest.raises(ValidationError) as caught:
        correlation(is_causal=True)
    assert "never cause" in str(caught.value)


def test_is_causal_survives_the_round_trip_as_an_explicit_false():
    """The field exists in order to be False: the absence of a causal claim has to be explicit in
    the stored row, not implied by a missing key."""
    assert "is_causal" in json.loads(correlation().model_dump_json())


def test_correlation_refuses_a_metric_against_itself():
    with pytest.raises(ValidationError) as caught:
        correlation(metric_b="account.reply_count")
    assert "with itself" in str(caught.value)


@pytest.mark.parametrize("rho", [-10_000, 0, 10_000])
def test_rho_is_a_signed_proportion(rho):
    assert correlation(rho_bp=rho).rho_bp == rho


@pytest.mark.parametrize("rho,refusal", [(-10_001, ValidationError), (10_001, ValidationError),
                                         (0.62, TypeError)])
def test_rho_outside_the_signed_range_is_refused(rho, refusal):
    """Out of range is a VALUE refusal; a ratio is a TYPE refusal. Both must happen, and naming
    the two apart is what proves the float is not merely being range-checked after a round."""
    with pytest.raises(refusal):
        correlation(rho_bp=rho)


# ---------------------------------------------------------------------- D-06 · Anomaly

def test_anomaly_requires_a_real_baseline():
    with pytest.raises(ValidationError) as caught:
        anomaly(periods_used=MIN_ANOMALY_PERIODS - 1)
    assert "normal band" in str(caught.value)


@pytest.mark.parametrize("direction,current,baseline", [
    (AnomalyDirection.ABOVE, 12, 94), (AnomalyDirection.BELOW, 94, 12)])
def test_anomaly_direction_must_match_its_own_numbers(direction, current, baseline):
    with pytest.raises(ValidationError):
        anomaly(direction=direction, current_bp=current, baseline_bp=baseline)


def test_z_like_may_exceed_ten_thousand():
    """`z_like_bp` is a RATIO, not a proportion — doc 04 flags an anomaly above 30000, so a
    0..10000 check would reject exactly the objects the detector exists to produce."""
    assert anomaly(z_like_bp=91_111).z_like_bp == 91_111
    with pytest.raises(ValidationError):
        anomaly(z_like_bp=-1)


# ------------------------------------------------------------ D-07 · typed absence

def test_licenses_negative_inference_is_computed_not_supplied():
    fact = missing_fact()
    assert fact.licenses_negative_inference is True
    assert fact.is_finding is True
    assert json.loads(fact.model_dump_json())["licenses_negative_inference"] is True
    assert_round_trips(fact)


@pytest.mark.parametrize("absence,licensed", [
    (AbsenceType.PRESENT, False), (AbsenceType.UNKNOWABLE, False),
    (AbsenceType.GENUINELY_ABSENT, True), (AbsenceType.STALE, False),
    (AbsenceType.NOT_EXPECTED, False)])
def test_only_genuine_absence_licenses_an_inference(absence, licensed):
    fact = missing_fact(absence_type=absence) if licensed else missing_fact(
        absence_type=absence, coverage_ready=None, coverage_basis=())
    assert fact.licenses_negative_inference is licensed


def test_a_caller_cannot_set_the_licence():
    """The whole point of the field: no layer can talk itself past it."""
    with pytest.raises(ValidationError) as caught:
        MissingFact(subject_node_id="node_1", expected_fact="contract.owner_node_id",
                    absence_type=AbsenceType.UNKNOWABLE, coverage_ready=None,
                    licenses_negative_inference=True)
    assert "cannot be set" in str(caught.value)


def test_genuine_absence_requires_coverage_and_a_basis():
    """Doc 05 names treating UNKNOWABLE as GENUINELY_ABSENT the worst output in the group — a
    false negative inference about a customer. `coverage_ready` is checked first, always."""
    for coverage in (None, False):
        with pytest.raises(ValidationError) as caught:
            missing_fact(coverage_ready=coverage)
        assert "coverage_ready=True" in str(caught.value)
    with pytest.raises(ValidationError) as caught:
        missing_fact(coverage_basis=())
    assert "what we looked at" in str(caught.value)


def test_an_expected_fact_is_a_path_not_a_sentence():
    """The plain-language labels have spaces, match nothing in the graph and cannot be consulted
    by a predicate — which is how an `exists:` test returned a confident FALSE."""
    with pytest.raises(ValidationError):
        missing_fact(expected_fact="the contract owner")


# --------------------------------------------------------------- D-08 · AuthorityRule

def test_an_inferred_rule_never_enforces():
    """Inferring an approval threshold from behaviour and then enforcing it lets the system
    invent governance. It proposes; a human confirms."""
    assert authority_rule(source=AuthoritySource.INFERRED).enforceable is False
    assert authority_rule(source=AuthoritySource.ADMIN_DECLARED).enforceable is True
    assert authority_rule(source=AuthoritySource.DISCOVERED,
                          evidence_ref="doc_delegation_policy_v4").enforceable is True


def test_a_discovered_rule_must_name_its_document():
    with pytest.raises(ValidationError) as caught:
        authority_rule(source=AuthoritySource.DISCOVERED)
    assert "document it was read from" in str(caught.value)


@pytest.mark.parametrize("kwargs,message", [
    (dict(currency=None), "name its currency"),
    (dict(threshold_minor_units=None), "does not exist"),
    (dict(threshold_minor_units=5_000.5), "minor units"),
])
def test_authority_thresholds_are_integer_money_with_a_currency(kwargs, message):
    with pytest.raises(REFUSED) as caught:
        authority_rule(**kwargs)
    assert message in str(caught.value)


def test_authority_is_historical_and_the_instant_is_a_parameter():
    """"Who could approve this in March?" must be answerable, because a decision made in March
    was correct against March's rules."""
    retired = authority_rule(valid_from=EVAL_TIME - timedelta(days=200),
                             valid_until=EVAL_TIME - timedelta(days=30))
    assert retired.applies_at(EVAL_TIME) is False
    assert retired.applies_at(EVAL_TIME - timedelta(days=100)) is True
    # half-open: a rule superseded at the instant its successor starts must not also match it
    assert retired.applies_at(EVAL_TIME - timedelta(days=30)) is False


def test_a_window_that_ends_before_it_starts_is_refused():
    with pytest.raises(ValidationError) as caught:
        authority_rule(valid_until=EVAL_TIME - timedelta(days=365))
    assert "must be after valid_from" in str(caught.value)


def test_covers_treats_a_null_threshold_and_a_null_amount_differently():
    any_value = authority_rule(threshold_minor_units=None, currency=None)
    assert any_value.covers(None) is True and any_value.covers(1) is True
    priced = authority_rule()
    assert priced.covers(500_000_000) is True
    assert priced.covers(499_999_999) is False
    assert priced.covers(None) is False


def test_the_absent_rule_has_its_own_word():
    """"We have no rule for this" and "anyone may approve this" are opposite facts, and an empty
    return renders as the second one."""
    assert NO_AUTHORITY_RULE == "no_authority_rule"


# -------------------------------------------------------------- D-09 · DependencyChain

def test_chain_links_must_join():
    with pytest.raises(ValidationError) as caught:
        chain(links=(link("a@x.com", "b@x.com"), link("c@x.com", "d@x.com")))
    assert "must join" in str(caught.value)


def test_a_resolved_link_may_not_sit_in_a_chain():
    with pytest.raises(ValidationError) as caught:
        chain(links=(link("legal@globeworked.com", "deepthi@globeworked.com", resolved=True),))
    assert "no resolved link" in str(caught.value)


def test_circular_wait_is_checked_against_the_links_in_both_directions():
    closing = (link("a@x.com", "b@x.com"), link("b@x.com", "a@x.com"))
    with pytest.raises(ValidationError) as caught:
        chain(links=closing, circular_wait=False)
    assert "must set circular_wait" in str(caught.value)
    with pytest.raises(ValidationError) as caught:
        chain(circular_wait=True)
    assert "does not close" in str(caught.value)
    cycle = chain(links=closing, circular_wait=True)
    assert cycle.nodes == ("a@x.com", "b@x.com", "a@x.com")


def test_chain_depth_is_capped():
    nodes = [f"n{index}@x.com" for index in range(MAX_DEPENDENCY_DEPTH + 2)]
    links = tuple(link(nodes[i], nodes[i + 1]) for i in range(MAX_DEPENDENCY_DEPTH + 1))
    with pytest.raises(ValidationError) as caught:
        chain(links=links)
    assert "at most 6 edges" in str(caught.value)


def test_chain_reads_root_terminal_and_nodes_from_its_links():
    built = chain()
    assert built.root == "legal@globeworked.com"
    assert built.terminal == "renewal_msa_2026"
    assert built.depth == 2
    assert built.nodes == ("legal@globeworked.com", "deepthi@globeworked.com",
                           "renewal_msa_2026")


def test_a_dependency_link_needs_a_receipt_and_two_ends():
    with pytest.raises(ValidationError) as caught:
        link("a@x.com", "b@x.com", evidence=())
    assert "no receipt" in str(caught.value)
    with pytest.raises(ValidationError) as caught:
        link("a@x.com", "a@x.com")
    assert "cannot block itself" in str(caught.value)


# ------------------------------------------------- D-01 · importance, the X5 defect closed

def test_an_unscored_situation_cannot_carry_the_5000_constant():
    """`context/situation_bso.py:39` stamps DEFAULT_IMPORTANCE_BP = 5000 on every situation ever
    produced. This is the assertion that the v2 contract makes that state unconstructible."""
    with pytest.raises(ValidationError) as caught:
        importance(basis=ImportanceBasis.UNSCORED, score_bp=5_000, base_bp=None, components={})
    assert "score_bp=0" in str(caught.value)


def test_an_unscored_situation_carries_zero_and_says_so():
    unscored = importance(basis=ImportanceBasis.UNSCORED, score_bp=0, base_bp=None,
                          components={}, version="unscored")
    assert unscored.score_bp == 0 and unscored.is_measured is False
    assert_round_trips(unscored)


def test_a_scored_situation_must_explain_itself():
    with pytest.raises(ValidationError) as caught:
        importance(components={})
    assert "why is this a" in str(caught.value)
    with pytest.raises(ValidationError) as caught:
        importance(base_bp=None)
    assert "constituent signal" in str(caught.value)


def test_an_unscored_attribution_may_not_smuggle_a_base_or_components():
    with pytest.raises(ValidationError) as caught:
        importance(basis=ImportanceBasis.UNSCORED, score_bp=0, base_bp=8_100,
                   components={"base": 8_100})
    assert "arithmetic that did not happen" in str(caught.value)


def test_inherited_must_equal_its_base():
    with pytest.raises(ValidationError) as caught:
        importance(basis=ImportanceBasis.INHERITED, score_bp=7_400, base_bp=8_100,
                   components={"base": 8_100})
    assert "must equal its base" in str(caught.value)
    inherited = importance(basis=ImportanceBasis.INHERITED, score_bp=8_100, base_bp=8_100,
                           components={"base": 8_100})
    assert inherited.score_bp == inherited.base_bp


def test_importance_components_are_signed_integers_and_never_floats():
    """A subtracting modifier is stored as the negative delta it applied — including the
    multiplicative coverage step, whose applied delta is what makes it readable at all."""
    assert importance().components["staleness"] == -1_500
    with pytest.raises(TypeError):
        importance(components={"coverage_penalty": 0.8})


def test_a_situation_cannot_be_built_without_an_attribution():
    """No default at any level — a constant cannot arrive by omission."""
    kwargs = situation_kwargs()
    kwargs.pop("importance")
    with pytest.raises(ValidationError):
        BusinessSituationObject(**kwargs)


# --------------------------------------------------------- D-01 · the confidence vector

def test_the_vector_has_six_axes_and_an_unmeasured_one_is_none():
    vector = confidence()
    assert tuple(vector.axes) == CONFIDENCE_AXES and len(CONFIDENCE_AXES) == 6
    assert vector.axes["coverage"] is None
    assert "coverage" not in vector.measured_axes
    assert_round_trips(vector)


def test_composition_may_not_name_an_axis_with_no_basis():
    with pytest.raises(ValidationError) as caught:
        confidence(composed_from=("evidence", "coverage"))
    assert "no basis" in str(caught.value)


def test_composition_may_not_exceed_its_weakest_input():
    with pytest.raises(ValidationError) as caught:
        confidence(overall_bp=9_000)
    assert "manufacture certainty" in str(caught.value)


def test_composition_from_nothing_is_refused():
    with pytest.raises(ValidationError) as caught:
        confidence(composed_from=())
    assert "at least one axis" in str(caught.value)


def test_an_unknown_axis_name_is_refused():
    with pytest.raises(ValidationError) as caught:
        confidence(composed_from=("evidence", "vibes"))
    assert "do not exist" in str(caught.value)


def test_the_six_axes_are_the_six_that_exist():
    """Pins the vocabulary to `context/situations.py`, which now computes all six.
    `contracts/` may not import `context/`, so the two are pinned by this test instead.

    This assertion used to read `set(CONFIDENCE_AXES) - {"analytic"}`, because the sixth axis
    existed in the contract and nowhere else. L2.5.1-U1 built it (`situations.analytic_score`),
    and the exclusion came out with it — the failure mode this test guards is doc 09's
    must-not-regress item 3, a vector collapsing toward a scalar, and an axis the contract names
    but the scorer does not produce is that collapse one field at a time."""
    from genios_engine.context.situations import Confidence
    live = {field.name for field in dataclasses.fields(Confidence)} - {
        "overall", "missing", "inputs"}
    assert live == set(CONFIDENCE_AXES)


# ----------------------------------------------------------- D-01 · the situation object

def test_the_situation_states_match_the_live_lifecycle():
    """`contracts/` may not import `context/`; the states are spelled in both places and pinned
    together here, the way `signal.py`'s constants are pinned to Layer 1's."""
    from genios_engine.context import situations
    assert SITUATION_STATES == {situations.STATUS_ACTIVE, situations.STATUS_DORMANT,
                                situations.STATUS_RESOLVED, situations.STATUS_ARCHIVED}


@pytest.mark.parametrize("field,value", [("signal_ids", ()), ("evidence", ())])
def test_a_situation_needs_signals_and_receipts(field, value):
    with pytest.raises(ValidationError):
        situation(**{field: value})


def test_a_pattern_must_name_the_facts_that_fired_it():
    """"This fired because of these five facts" is what makes a situation defensible on a card.
    A pattern id alone is an assertion."""
    with pytest.raises(ValidationError) as caught:
        situation(matched_conditions=())
    assert "assertion" in str(caught.value)
    correlated = situation(pattern_id=None, matched_conditions=())
    assert correlated.pattern_id is None


def test_a_matched_condition_must_cite_its_evidence():
    with pytest.raises(ValidationError) as caught:
        MatchedCondition(field_path="contract.owner_node_id", operator="exists",
                         expected=True, observed=False, evidence=())
    assert "must cite the evidence" in str(caught.value)


def test_a_situation_state_outside_the_four_is_refused():
    with pytest.raises(ValidationError):
        situation(state="closed")


def test_an_unknown_schema_version_is_refused():
    with pytest.raises(ValidationError) as caught:
        situation(schema_version=BUSINESS_SITUATION_VERSION)
    assert "unsupported business situation schema" in str(caught.value)


def test_coverage_ready_is_tri_state_on_the_situation_too():
    assert situation(coverage_ready=None).coverage_ready is None
    with pytest.raises(TypeError):
        situation(coverage_ready=1)


def test_signal_ids_are_sorted_and_deduplicated():
    """Both are hashed into a content address: a different iteration order over the same set
    would mint a new expertise package for an unchanged situation, which is the mechanism behind
    the 995 MB read-only incident."""
    built = situation(signal_ids=("sig_b", "sig_a", "sig_b"))
    assert built.signal_ids == ("sig_a", "sig_b")


def test_the_content_key_excludes_the_trace_id():
    """A trace id identifies one OBSERVATION of a situation, not the situation."""
    key = situation().content_key()
    assert "trace_id" not in key
    assert situation(trace_id="trace_other").content_key() == key


def test_the_situation_reads_expose_the_v1_field_names():
    built = situation()
    assert built.importance_bp == built.importance.score_bp == 7_400
    assert built.confidence_bp == built.confidence.overall_bp == 6_400
    assert built.contested_fields == ("contract.value",)
    assert tuple(fact.expected_fact for fact in built.findings) == ("contract.owner_node_id",)


def test_open_lane_sequences_survive_the_jsonb_round_trip_as_the_same_shape():
    """A lane that accepted a tuple and returned a list would make an object built in memory
    unequal to the same object read back from its own row — a coin flip on every "did this
    change" comparison, in the direction that re-writes the row."""
    built = situation(metadata={"domains": ["sales", "legal"], "nested": {"ids": ("a", "b")}})
    assert built.metadata["domains"] == ("sales", "legal")
    assert built.metadata["nested"]["ids"] == ("a", "b")
    assert_round_trips(built)


def test_metadata_refuses_a_float_at_any_depth():
    """The one lane wide enough to smuggle one, and it reaches a jsonb column where a ratio comes
    back out as a number nobody can trace to a source."""
    with pytest.raises(TypeError) as caught:
        situation(metadata={"scores": {"nested": [0.87]}})
    assert "float" in str(caught.value)


def test_the_situation_is_frozen():
    """It is content-addressed into `expertise_packages`: an in-place edit would leave a stored
    address pointing at content that no longer exists."""
    built = situation()
    with pytest.raises(ValidationError):
        built.state = "resolved"


# ------------------------------------------------------------------ no float, anywhere

def test_no_float_appears_in_a_fully_populated_serialized_situation():
    """V-8 asserted structurally rather than by annotation: `metadata` and a conflict claim's
    value are `Any`-typed lanes where an annotation proves nothing."""
    document = json.loads(situation().model_dump_json())
    floats = [(path, value) for path, value in walk_json(document)
              if isinstance(value, float)]
    assert not floats, f"float reached the serialized situation at {floats}"


def test_the_populated_situation_actually_exercises_every_lane():
    """A no-float assertion over a sparse object proves nothing. This pins that the fixture
    above really does populate every analytic, quality and explainability lane."""
    document = json.loads(situation().model_dump_json())
    for lane in ("trends", "cohort_positions", "anomalies", "correlations", "missing_facts",
                 "conflicts", "dependencies", "matched_conditions", "entities",
                 "relationships", "timeline", "evidence", "metadata"):
        assert document[lane], f"{lane} is empty — the no-float walk would not reach it"


# ================================================================== V-1..V-8 · the gate

def test_a_clean_situation_is_admitted_and_carried():
    decision = validate_situation(situation())
    assert decision.outcome is SituationOutcome.ADMIT
    assert decision.admitted is True
    assert decision.failures == ()
    assert decision.situation is not None
    assert decision.situation.id == "sit_0f21ab"


def test_every_law_has_an_explicit_action_and_all_eight_reject():
    """Unlike L1, where V-1 PARKS and V-5 DOWNGRADES. Doc 08's L2 table gives all eight the same
    action, and getting a failure action backwards does not fail loudly — it silently changes
    what reaches the layer above."""
    assert len(list(L2Law)) == 8
    assert set(LAW_ACTIONS) == set(L2Law)
    assert set(LAW_ACTIONS.values()) == {LawAction.REJECT}
    assert LAW_ACTIONS[L2Law.V1] is LawAction.REJECT      # L1's V-1 parks; L2's does not
    assert LAW_ACTIONS[L2Law.V5] is LawAction.REJECT      # L1's V-5 downgrades; L2's does not


def _bypassed_cohort(**overrides: Any) -> CohortPosition:
    base: dict[str, Any] = dict(
        metric="account.reply_count", cohort_id="accounts_by_arr_quartile:q4",
        population_size=37, percentile_bp=800, band=CohortBand.D1,
        p25_bp=12, p50_bp=40, p75_bp=95, computed_at=EVAL_TIME)
    base.update(overrides)
    return CohortPosition.model_construct(**base)


def _bypassed_trend(**overrides: Any) -> Trend:
    base: dict[str, Any] = dict(
        metric="account.reply_count", direction=TrendDirection.DECLINING,
        relative_slope_bp=-1_200, streak_periods=6, point_count=6,
        coverage_ratio_bp=10_000, trend_confidence_bp=6_400, evidence_points=series())
    base.update(overrides)
    return Trend.model_construct(**base)


def _bypassed_point(**overrides: Any) -> MetricPoint:
    base: dict[str, Any] = dict(
        subject_node_id="node_acc_42", metric="account.reply_count", value_bp=42,
        unit=MetricUnit.COUNT, currency=None,
        observed_at=EVAL_TIME, known=True, coverage_ready=True)
    base.update(overrides)
    return MetricPoint.model_construct(**base)


def _bypassed_correlation(**overrides: Any) -> MetricCorrelation:
    base: dict[str, Any] = dict(
        metric_a="account.reply_count", metric_b="account.meeting_count",
        cohort_id="all_active_accounts", rho_bp=6_200,
        strength=CorrelationStrength.MODERATE, n=24, is_causal=False)
    base.update(overrides)
    return MetricCorrelation.model_construct(**base)


LAW_FIXTURES = [
    (L2Law.V1, "cohort_positions[0]",
     lambda: bypassed(cohort_positions=(_bypassed_cohort(cohort_id=""),))),
    (L2Law.V2, "cohort_positions[0]",
     lambda: bypassed(cohort_positions=(_bypassed_cohort(population_size=3),))),
    (L2Law.V3, "trends[0].evidence_points[0]",
     lambda: bypassed(trends=(_bypassed_trend(
         evidence_points=(_bypassed_point(known=False, value_bp=4_200),)),))),
    (L2Law.V4, "trends[0]",
     lambda: bypassed(trends=(_bypassed_trend(trend_confidence_bp=9_400),))),
    (L2Law.V5, "trends[0]",
     lambda: bypassed(trends=(_bypassed_trend(point_count=2),))),
    (L2Law.V6, "correlations[0]",
     lambda: bypassed(correlations=(_bypassed_correlation(n=5),))),
    (L2Law.V7, "correlations[0]",
     lambda: bypassed(correlations=(_bypassed_correlation(is_causal=True),))),
    (L2Law.V8, "situation",
     lambda: bypassed(metadata={"conversion": 0.87})),
]


@pytest.mark.parametrize("law,subject,build", LAW_FIXTURES,
                         ids=[row[0].value for row in LAW_FIXTURES])
def test_each_law_rejects_its_own_object(law, subject, build):
    """One fixture per law, tripping exactly that law and asserting the exact outcome."""
    decision = validate_situation(build())
    assert decision.outcome is SituationOutcome.REJECT
    assert decision.situation is None, "a rejected situation must not be reachable"
    assert [failure.law for failure in decision.failures] == [law]
    assert decision.failures[0].subject == subject
    assert decision.failures[0].action is LawAction.REJECT
    assert decision.failures[0].detail


#: The same eight laws, expressed as the constructor call each one refuses. The gate exists for
#: objects that skipped a constructor; this table asserts the constructor itself would have
#: refused every one of them — stricter and earlier, per universal rule 5.
CONSTRUCTOR_REFUSALS = [
    (L2Law.V1, lambda: cohort(cohort_id="")),
    (L2Law.V2, lambda: cohort(population_size=MIN_COHORT_POPULATION - 1)),
    (L2Law.V3, lambda: point(known=False, value=4_200)),
    (L2Law.V4, lambda: trend(trend_confidence_bp=MAX_TREND_CONFIDENCE_BP + 1)),
    (L2Law.V5, lambda: trend(point_count=MIN_TREND_POINTS - 1)),
    (L2Law.V6, lambda: correlation(n=MIN_CORRELATION_SAMPLES - 1)),
    (L2Law.V7, lambda: correlation(is_causal=True)),
    (L2Law.V8, lambda: situation(metadata={"conversion": 0.87})),
]


@pytest.mark.parametrize("law,build", CONSTRUCTOR_REFUSALS,
                         ids=[row[0].value for row in CONSTRUCTOR_REFUSALS])
def test_every_law_is_also_enforced_at_construction(law, build):
    """A situation that cannot be built cannot be published by accident. See `REFUSED` for why
    the two exception shapes are both accepted here — V-8 is a TYPE refusal, the other seven are
    VALUE refusals."""
    with pytest.raises(REFUSED):
        build()


def test_a_situation_failing_two_laws_reports_both_in_v_order():
    """A situation that fails V-2 and V-6 has two different upstream defects; reporting only the
    first would reveal the second a day later."""
    decision = validate_situation(bypassed(
        cohort_positions=(_bypassed_cohort(population_size=2),),
        correlations=(_bypassed_correlation(n=5, is_causal=True),)))
    assert [failure.law for failure in decision.failures] == [L2Law.V2, L2Law.V6, L2Law.V7]


def test_v1_reports_both_halves_of_law_two_independently():
    """`cohort_id` and `population_size` are two different missing facts about the same object,
    and a reviewer fixing one must be told about the other."""
    decision = validate_situation(bypassed(
        cohort_positions=(_bypassed_cohort(cohort_id="", population_size=None),)))
    assert [failure.law for failure in decision.failures] == [L2Law.V1, L2Law.V1]


def test_the_gate_names_which_object_tripped_the_law():
    """"V-3 failed" is unactionable on a situation carrying two trends of six points each."""
    decision = validate_situation(bypassed(cohort_positions=(
        _bypassed_cohort(), _bypassed_cohort(population_size=1))))
    assert decision.failures[0].subject == "cohort_positions[1]"


# ------------------------------------------------- the v2 contract expresses the v1 object

#: Every field on the v1 frozen dataclass, mapped to where it lives in v2. The test below pins
#: this against `dataclasses.fields`, so a v1 lane that is silently unrepresentable in v2 fails
#: HERE rather than during the X8 cutover.
V1_TO_V2 = {
    "org_id": "org_id",
    "trace_id": "trace_id",
    "visibility": "visibility",
    "id": "id",
    "signal_ids": "signal_ids",
    "type": "type",
    "confidence_bp": "confidence.overall_bp",
    "importance_bp": "importance.score_bp",
    "evidence": "evidence + provenance_refs",
    "entities": "entities",
    "relationships": "relationships",
    "timeline": "timeline",
    "dependencies": "dependencies",
    "state": "state",
    "metadata": "domain_ids / importance.* / conflict_ids / metadata",
    "schema_version": "schema_version",
}


def v1_situation() -> SituationV1:
    """A realistic v1 object, shaped exactly as `context/situation_bso.build_business_situation`
    emits one on the L1-sourced path: real qualified signal ids, L1's verified spans carrying
    their `signal_id` annotation, real correlated members, and the metadata block."""
    return SituationV1(
        org_id="org_7173",
        trace_id="trace_9c2a1f",
        visibility=Visibility(scope="participants",
                              principals=["deepthi@globeworked.com"],
                              derived_from="l2:narrowest_of_members"),
        id="sit_0f21ab",
        signal_ids=("sig_0e88cd", "sig_0f21ab"),
        type="renewal_at_risk",
        confidence_bp=6_400,
        importance_bp=7_400,
        evidence=({"source_ref": "prepared_content:evt_7f31",
                   "quote": "the $84K annual contract", "start_offset": 310,
                   "end_offset": 334, "verified": True,
                   "signal_id": "sig_0f21ab", "source": "l1_qualified_signal"},
                  {"event_id": "evt_7f31", "source": "situation",
                   "source_object_id": "graph_ref:node_991"}),
        entities=({"id": "deepthi@globeworked.com", "type": "external_contact",
                   "name": "Deepthi", "event_count": 12},
                  {"id": "globeworked.com", "type": "organization",
                   "name": "Globe Worked"}),
        relationships=({"source_id": "deepthi@globeworked.com",
                        "target_id": "globeworked.com", "kind": "works_at"},),
        timeline=({"first_seen_at": (EVAL_TIME - timedelta(days=61)).isoformat(),
                   "last_seen_at": (EVAL_TIME - timedelta(days=2)).isoformat()},),
        dependencies=(),
        state="active",
        metadata={"domain_ids": ["sales"], "coverage_bp": 4_100,
                  "importance_source": "l1_qualified_signals",
                  "importance_version": "alg17.v2",
                  "importance_components": {"monetary_exposure_bp": 8_800,
                                            "weighted_bp": 7_600},
                  "l1_signal_count": 2, "l1_scored_count": 2,
                  "conflict_ids": ["cf_0021"], "shadow": True,
                  "split_required": False, "distinct_counterparty_count": 2})


#: The `importance_source` values the v1 builder writes when Layer 1 actually SCORED the
#: situation. The other three ("l1_unscored", "l1_all_retired", "default") are all the same fact
#: — nothing measured this — spelled three ways, and all three port to UNSCORED.
V1_SCORED_SOURCES = frozenset({"l1_qualified_signals"})


def port_importance(old: SituationV1) -> ImportanceAttribution:
    """The cutover's hardest step: v1's flat `importance_bp` + metadata into an attribution.

    Two things happen here that the contract forces and the v1 shape does not. The score is
    admitted as a SCORE only when `importance_source` says something measured it — otherwise the
    5000 constant becomes an honest zero. And L1's stored component record is split by
    int-ness: the arithmetic into `components`, the context it ran against into `inputs`.
    """
    meta = dict(old.metadata)
    record = dict(meta.get("importance_components") or {})
    numeric = {key: value for key, value in record.items()
               if isinstance(value, int) and not isinstance(value, bool)}
    context = {key: value for key, value in record.items() if key not in numeric}
    if str(meta.get("importance_source") or "default") not in V1_SCORED_SOURCES:
        return ImportanceAttribution(basis=ImportanceBasis.UNSCORED, score_bp=0, base_bp=None,
                                     version="unscored", components={}, inputs={})
    return ImportanceAttribution(
        basis=ImportanceBasis.INHERITED, score_bp=old.importance_bp, base_bp=old.importance_bp,
        version=str(meta.get("importance_version") or "unscored"),
        components=numeric, inputs=context)


def port_v1(old: SituationV1) -> BusinessSituationObject:
    """The X8 cutover, in miniature: every v1 lane onto its v2 home.

    This is a TEST fixture and not the production porter — the real one reads the DB rows the v1
    builder reads. What it proves is the only thing a contract wave can prove: that the v2 type
    is expressive enough for the cutover to be written at all.
    """
    # One sentence cited by two signals is ONE receipt. The v1 builder concatenates L1's spans
    # with the correlation's graph refs, which routinely carry the same quote twice, and
    # repeating it would make a single citation look like corroboration — the rule
    # `gather_l1_signals` already applies within its own set and not across the two lists.
    receipts = tuple(dict.fromkeys(EvidenceSpan.model_validate(item) for item in old.evidence
                                   if "quote" in item))
    join_keys = tuple(str(item[key]) for item in old.evidence
                      for key in ("event_id", "source_object_id", "signal_id")
                      if item.get(key))
    meta = dict(old.metadata)
    coverage = meta.get("coverage_bp")
    moment = old.timeline[0] if old.timeline else {}
    return BusinessSituationObject(
        org_id=old.org_id, trace_id=old.trace_id,
        visibility=Visibility.model_validate(dict(old.visibility)),
        id=old.id, type=old.type, state=old.state,
        domain_ids=tuple(meta.get("domain_ids") or ()),
        signal_ids=old.signal_ids,
        entities=tuple(SituationEntity(**dict(entity)) for entity in old.entities),
        relationships=tuple(SituationRelationship(**dict(edge))
                            for edge in old.relationships),
        timeline=tuple(TimelinePoint(at=datetime.fromisoformat(str(moment[key])), label=label)
                       for key, label in (("first_seen_at", "first_seen"),
                                          ("last_seen_at", "last_seen")) if moment.get(key)),
        dependencies=(),
        evidence=receipts,
        provenance_refs=join_keys,
        confidence=ConfidenceVector(evidence_bp=old.confidence_bp,
                                    coverage_bp=coverage,
                                    overall_bp=old.confidence_bp,
                                    composed_from=("evidence",)),
        coverage_ready=None,
        conflict_ids=tuple(meta.get("conflict_ids") or ()),
        importance=port_importance(old),
        metadata={key: value for key, value in meta.items()
                  if key not in ("domain_ids", "importance_version", "importance_components",
                                 "conflict_ids", "coverage_bp")})


def test_the_v1_to_v2_map_covers_every_v1_field():
    """If a lane is added to (or dropped from) the v1 dataclass, this fails rather than the
    cutover silently losing it."""
    assert set(V1_TO_V2) == {field.name for field in dataclasses.fields(SituationV1)}


def test_the_v2_contract_expresses_everything_the_v1_object_carries():
    old = v1_situation()
    new = port_v1(old)
    assert new.org_id == old.org_id and new.trace_id == old.trace_id
    assert new.id == old.id and new.type == old.type and new.state == old.state
    assert new.signal_ids == old.signal_ids
    assert new.importance_bp == old.importance_bp == 7_400
    assert new.confidence_bp == old.confidence_bp == 6_400
    assert new.visibility.scope == old.visibility["scope"]
    # the verified span survives as a typed receipt; the graph refs survive as join keys
    assert [receipt.quote for receipt in new.evidence] == ["the $84K annual contract"]
    assert new.provenance_refs == ("evt_7f31", "graph_ref:node_991", "sig_0f21ab")
    assert [entity.name for entity in new.entities] == ["Deepthi", "Globe Worked"]
    assert new.entities[1].event_count is None, "'not counted' must not become zero"
    assert [edge.kind for edge in new.relationships] == ["works_at"]
    assert [moment.label for moment in new.timeline] == ["first_seen", "last_seen"]
    assert new.domain_ids == ("sales",)
    assert new.confidence.axes["coverage"] == 4_100
    assert new.conflict_ids == ("cf_0021",)
    assert new.importance.version == "alg17.v2"
    assert new.importance.components["weighted_bp"] == 7_600
    # the residue that has no first-class home is still carried, losslessly
    assert new.metadata["l1_signal_count"] == 2
    assert new.metadata["split_required"] is False
    assert_round_trips(new)


def test_the_ported_object_passes_the_gate():
    """Expressible is not enough — a ported v1 situation must also be ADMITTED, or the cutover
    produces objects the layer above refuses."""
    assert validate_situation(port_v1(v1_situation())).admitted is True


def test_the_v1_constant_path_cannot_be_ported_as_a_score():
    """The v1 fallback stamps 5000 with `importance_source='default'`. Ported honestly it is
    UNSCORED, and UNSCORED cannot carry 5000 — which is exactly the cutover's forcing function."""
    with pytest.raises(ValidationError):
        ImportanceAttribution(basis=ImportanceBasis.UNSCORED, score_bp=5_000, base_bp=None,
                              version="unscored", components={})


# ============================================ the LIVE L2 producer's output, through the gate

# The three tests below are the wiring proof for this wave. X0 builds types, so there is no new
# request path of its own — but there IS an existing production path that emits the object these
# types replace, and it is a pure function: `context/situation_bso.build_business_situation`
# (situation_bso.py:395) is what `context/domain_shadow` calls on every sweep, and everything it
# needs is passed in. Driving the REAL function and porting its REAL output is the only honest
# way a contract wave can prove the X8 cutover is possible, and it is what caught the defect
# `ImportanceAttribution.inputs` exists to fix: L1's stored components record is thirteen keys of
# which six are not numbers.


#: What `gather_evidence_and_signals` returns for a correlation that HAS member evidence: the
#: `graph_source_refs` row, whose `evidence` column holds the span L1 verified.
GRAPH_REF_EVIDENCE = [{"source_ref": "prepared_content:evt_7f31",
                       "quote": "the $84K annual contract", "start_offset": 310,
                       "end_offset": 334, "verified": True, "event_id": "evt_7f31"}]

#: What it returns when the correlation has NO members: a synthetic receipt, labelled as one.
RECONSTRUCTED_EVIDENCE = [{"event_id": "evt_7f31", "source": "situation",
                           "reconstructed": True}]


def live_v1(*, l1: Any = None, evidence: list[dict[str, Any]] | None = None) -> SituationV1:
    """The v1 object exactly as the live builder emits it — not a hand-written fixture."""
    from genios_engine.context.situation_bso import build_business_situation
    return build_business_situation(
        org_id="org_7173",
        situation={"situation_id": "sit_0f21ab", "situation_type": "renewal_at_risk",
                   "domain": "sales", "status": "active", "confidence_overall": 64,
                   "coverage": 41, "anchor_node_id": "globeworked.com",
                   "anchor_type": "organization", "anchor_name": "Globe Worked",
                   "first_seen_at": EVAL_TIME - timedelta(days=61),
                   "last_seen_at": EVAL_TIME - timedelta(days=2)},
        signal_ids=["evt_7f31"],
        evidence=list(GRAPH_REF_EVIDENCE if evidence is None else evidence),
        trace_id="trace_9c2a1f",
        members=({"id": "deepthi@globeworked.com", "type": "external_contact",
                  "name": "deepthi@globeworked.com", "event_count": 12},),
        visibility=Visibility(scope="participants",
                              principals=["deepthi@globeworked.com"],
                              derived_from="l2:narrowest_of_members"),
        l1=l1)


def live_l1_signals() -> Any:
    """`gather_l1_signals`' own record type, carrying L1's REAL components shape — the thirteen
    keys `ImportanceComponents.as_record` writes, minus the unstable `eval_time` the builder
    already strips."""
    from genios_engine.context.situation_bso import L1Signals
    return L1Signals(
        signal_ids=("sig_0e88cd", "sig_0f21ab"),
        scored_signal_ids=("sig_0f21ab",),
        importance_bp=7_400,
        importance_version="alg17.v2",
        components={"monetary_exposure_bp": 8_800, "deadline_proximity_bp": 6_000,
                    "actor_authority_bp": 5_000, "entity_criticality_bp": 4_000,
                    "signal_type_weight_bp": 7_000,
                    "evidence_authority_multiplier_bp": 6_500, "weighted_bp": 7_600,
                    "baseline_used": 8_400_000, "baseline_currency": "USD",
                    "baseline_basis": "org_p50", "entity_standing": "known",
                    "flags": ["baseline_cold_start"]},
        evidence=({"source_ref": "prepared_content:evt_7f31",
                   "quote": "the $84K annual contract", "start_offset": 310,
                   "end_offset": 334, "verified": True,
                   "signal_id": "sig_0f21ab", "source": "l1_qualified_signal"},),
        conflict_ids=("cf_0021",),
        signal_count=2, scored_count=1)


def test_the_live_builders_scored_output_ports_and_is_admitted():
    """The real producer, the real L1 component record, through the real gate."""
    old = live_v1(l1=live_l1_signals())
    assert old.importance_bp == 7_400
    new = port_v1(old)
    assert new.importance.basis is ImportanceBasis.INHERITED
    assert new.importance.score_bp == 7_400
    # the numeric arithmetic and its non-numeric context land in their own lanes, losslessly
    assert new.importance.components["weighted_bp"] == 7_600
    assert new.importance.inputs["baseline_currency"] == "USD"
    # a sequence in an open lane normalises to a tuple in BOTH directions, so the ported object
    # and the same object read back from its own jsonb row compare equal
    assert new.importance.inputs["flags"] == ("baseline_cold_start",)
    assert set(new.importance.components) | set(new.importance.inputs) == set(
        old.metadata["importance_components"])
    assert [receipt.quote for receipt in new.evidence] == ["the $84K annual contract"]
    assert validate_situation(new).admitted is True
    assert_round_trips(new)


def test_the_live_builders_constant_path_becomes_an_honest_absence():
    """`situation_bso.py:52` stamps DEFAULT_IMPORTANCE_BP = 5000 and the builder puts it on every
    situation whose events published no live qualified signal. Ported honestly it is UNSCORED,
    and UNSCORED carries 0 — so the constant cannot survive the cutover as a score."""
    from genios_engine.context.situation_bso import DEFAULT_IMPORTANCE_BP
    old = live_v1(l1=None)                       # real spans, no Layer 1 verdict
    assert old.importance_bp == DEFAULT_IMPORTANCE_BP == 5_000
    assert old.metadata["importance_source"] == "default"
    new = port_v1(old)
    assert new.importance.basis is ImportanceBasis.UNSCORED
    assert new.importance.score_bp == 0
    assert new.importance.is_measured is False
    assert validate_situation(new).admitted is True


def test_the_live_builders_reconstructed_receipt_has_no_spelling_as_a_span():
    """The builder synthesises `{"reconstructed": True}` when nothing real is available. It was
    never a receipt, it becomes a join key, and a situation left with no real span is refused —
    the intended consequence of the cutover, asserted here so it is not discovered in X8."""
    old = live_v1(l1=None, evidence=RECONSTRUCTED_EVIDENCE)
    assert any(item.get("reconstructed") for item in old.evidence)
    with pytest.raises(ValidationError) as caught:
        port_v1(old)
    assert "no receipt is a guess" in str(caught.value)
