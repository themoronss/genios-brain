"""H4 · L2.4.8 — the ANOMALY DETECTOR (BLG-13). The gate for `context/analytic/anomaly.py`.

Doc 09 invokes gate H4 as:

    pytest tests/context/analytic/test_correlator.py tests/context/analytic/test_anomaly.py -q

Organised the way doc 04's acceptance list is written: one test per row, then the cases the list
implies rather than states — the outlier that hides inside its own standard deviation, the
boundary at six and five periods, the gap that is not a zero, the unsaturated extreme,
determinism, and the wiring.

**THE TEST THAT PROVES THE CHOICE OF MAD** is `test_one_outlier_cannot_hide_inside_its_own_sigma`.
It computes the standard deviation of the same series in the test itself (floats are legal in a
test; they are the thing being argued against) and shows the spike sits INSIDE three sigma while
`z_like_bp` reports it twenty-plus MADs out. Swap MAD for sigma in `detect_anomaly` and that row
fails on its own, before any other.

**WHY THE WIRING TEST IS THE ONE THAT MATTERS.** Layer 1 shipped six units that were built, green
and called by nothing on a real request path. Every test above `THE WIRING` here constructs its
series by hand and proves the UNIT. `test_the_sweep_writes_the_anomaly_fact` drives
`context/runner.process_pending` — the sweep both API sync routes and the upload route call —
against a real Postgres and asserts a `derived.anomaly.*` row exists afterwards. Delete the two
lines in `runner.py` and that test fails and nothing else here does.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.anomaly import (ANOMALY_FACT_PREFIX, ANOMALY_VERSION_PREFIX,
                                                    ANOMALY_VISIBILITY_SCOPE,
                                                    ANOMALY_WINDOW_PERIODS,
                                                    BASELINE_PERIODS, DEVIATION_FLAG_BP,
                                                    MAX_ANOMALY_FACTS_PER_SWEEP, Z_LIKE_FLAG_BP,
                                                    AnomalyRefusal, anomaly_fact_field,
                                                    anomaly_fact_value, detect_anomaly,
                                                    refresh_anomaly_facts)
from genios_engine.context.analytic.history import (MetricGrain, PostgresMetricHistory,
                                                    SampleReason, period_start)
from genios_engine.context.analytic.sampler import TrendedMetric, sampler_registry
from genios_engine.contracts.analytic import (MIN_ANOMALY_PERIODS, Anomaly, AnomalyDirection,
                                              MetricPoint, MetricUnit)

pytestmark = pytest.mark.unit

NODE = "node_acct_north"
METRIC = "engagement.touch_count"
_ENGINE = Path(__file__).resolve().parents[3] / "genios_engine"

#: A fixed month rather than "now minus n": the detector takes no clock, so a test that reached
#: for one would be asserting on a different series every day it ran.
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

#: Six months of a metric that genuinely swings between ~50 and ~450. Paired with the flat control
#: in two tests: the same 500 that is a five-sigma event on the flat series is an ordinary Tuesday
#: here, and the only difference between the two verdicts is the width of the node's own band.
NOISY = [100, 480, 20, 350, 60, 300]


def month(index: int) -> datetime:
    year, offset = divmod(EPOCH.month - 1 + index, 12)
    return EPOCH.replace(year=EPOCH.year + year, month=offset + 1)


def series(values, *, metric: str = METRIC, node: str = NODE) -> list[MetricPoint]:
    """A dense monthly series. `None` is a GAP — a period with no reading, never a zero."""
    return [MetricPoint(subject_node_id=node, metric=metric,
                        value_bp=value, unit=MetricUnit.COUNT, observed_at=month(index),
                        known=value is not None)
            for index, value in enumerate(values)]


# =================================================================================================
# DOC 04's ACCEPTANCE LIST
# =================================================================================================

def test_a_stable_series_with_one_spike_is_flagged() -> None:
    """Row 1. Six flat-ish months at ~100 and a 5x month. Unusual AND material — both conditions."""
    verdict = detect_anomaly(series([100, 102, 98, 101, 99, 100, 500]))

    assert verdict.answered and verdict.flagged
    assert verdict.direction is AnomalyDirection.ABOVE
    assert verdict.baseline_bp == 100
    assert verdict.z_like_bp > Z_LIKE_FLAG_BP
    assert verdict.deviation_bp > DEVIATION_FLAG_BP
    assert verdict.periods_used == BASELINE_PERIODS
    assert isinstance(verdict.anomaly, Anomaly)
    assert verdict.anomaly.current_bp == 500 and verdict.anomaly.baseline_bp == 100


def test_a_clear_drop_is_flagged_below() -> None:
    """The direction the product is actually sold on — a collapse, flagged early, against the
    node's OWN norm rather than its cohort's."""
    verdict = detect_anomaly(series([400, 410, 395, 405, 400, 402, 40]))

    assert verdict.flagged
    assert verdict.direction is AnomalyDirection.BELOW
    assert verdict.anomaly is not None and verdict.anomaly.direction is AnomalyDirection.BELOW
    assert verdict.anomaly.current_bp < verdict.anomaly.baseline_bp
    assert verdict.deviation_bp > DEVIATION_FLAG_BP


def test_a_flat_series_holds_no_anomaly() -> None:
    """A metric that does the same thing every month is not news. Measured, answered, not flagged
    — and the numbers are still carried, which is what lets a reader ask why not."""
    verdict = detect_anomaly(series([100, 100, 100, 100, 100, 100, 100]))

    assert verdict.answered and not verdict.flagged and verdict.anomaly is None
    assert verdict.baseline_bp == 100 and verdict.mad_bp == 0
    assert verdict.deviation_bp == 0 and verdict.z_like_bp == 0


def test_the_same_spike_on_a_noisy_series_is_not_flagged() -> None:
    """Row 2, and the pair with row 1 is the point: the SAME reading of 500, on a series that
    routinely swings, is not unusual. The detector measures deviation, not magnitude."""
    stable = detect_anomaly(series([100, 102, 98, 101, 99, 100, 500]))
    noisy = detect_anomaly(series(NOISY + [500]))

    assert stable.flagged, "the control"
    assert not noisy.flagged, "a wide MAD is what 'normal for this node' means"
    assert noisy.mad_bp > stable.mad_bp
    assert noisy.z_like_bp <= Z_LIKE_FLAG_BP
    assert noisy.deviation_bp > DEVIATION_FLAG_BP, (
        "and it is NOT the material floor doing the work here — the move is large, it is simply "
        "not unusual for this node")


def test_a_two_to_four_move_on_a_small_metric_is_not_a_crisis() -> None:
    """Row 3, and both guards are visible in it.

    A metric that sits at 2 going to 4 doubles, so the MATERIAL floor cannot be what stops it —
    `deviation_bp` is 10000, the largest reading it takes. What stops it is that two units of
    movement is two units: with a MAD of zero the z ratio is the move itself in basis points, and
    two is not thirty thousand. The mirror case below is the one where the material floor binds.
    """
    verdict = detect_anomaly(series([2, 2, 2, 2, 2, 2, 4]))

    assert verdict.answered and not verdict.flagged
    assert verdict.deviation_bp == 10_000 > DEVIATION_FLAG_BP, "doubling IS material"
    assert verdict.z_like_bp == 20_000 <= Z_LIKE_FLAG_BP, "and two units is not thirty thousand"

    material_floor = detect_anomaly(series([1000, 1000, 1000, 1000, 1000, 1000, 1010]))
    assert material_floor.z_like_bp == 100_000 > Z_LIKE_FLAG_BP, (
        "a perfectly flat series has a MAD of zero, so any move at all is statistically unusual")
    assert material_floor.deviation_bp == 100 <= DEVIATION_FLAG_BP
    assert not material_floor.flagged, "1% off baseline is not a crisis however tight the band"


def test_five_periods_of_history_refuses() -> None:
    """Row 4. There is no anomaly without a normal to be anomalous against, and D-06 puts the
    floor at six. `Anomaly` itself refuses below it, so a weak answer here would be an exception
    later — the refusal is the honest form of the same fact."""
    verdict = detect_anomaly(series([100, 102, 98, 101, 99, 500]))

    assert not verdict.answered
    assert verdict.refusal is AnomalyRefusal.INSUFFICIENT_HISTORY
    assert verdict.periods_used == 5 < MIN_ANOMALY_PERIODS
    assert verdict.flagged is False and verdict.anomaly is None
    assert verdict.baseline_bp is None and verdict.z_like_bp is None, (
        "a refusal carries no numbers — a baseline printed beside the word 'insufficient' gets "
        "read and quoted anyway")


def test_exactly_six_baseline_periods_answers() -> None:
    """The boundary from the other side. Six known periods behind the current reading is the
    smallest series the contract will build an `Anomaly` from, and it must actually answer."""
    verdict = detect_anomaly(series([100, 102, 98, 101, 99, 100, 500]))

    assert verdict.answered and verdict.periods_used == MIN_ANOMALY_PERIODS
    assert verdict.anomaly is not None
    assert verdict.anomaly.periods_used == MIN_ANOMALY_PERIODS


def test_a_coverage_gap_is_not_read_as_a_drop_to_zero() -> None:
    """Row 5, and doc 04 names it the worst output this group can produce: a false churn alarm
    about a real customer, generated by the tenant connecting one fewer mailbox."""
    holes = detect_anomaly(series([100, None, 102, None, 98, None, 101, 99, 100, 500]))

    assert holes.answered and holes.flagged
    assert holes.periods_used == 6, "three gaps reduced the sample; they contributed no value"
    assert holes.baseline_bp == 100, "a zero for each gap would have dragged this to ~50"
    assert all(point.known for point in holes.evidence_points)

    # And too many holes push the series to a refusal rather than to a fabricated collapse.
    sparse = detect_anomaly(series([100, None, None, 102, None, None, 99, None, 500]))
    assert sparse.refusal is AnomalyRefusal.INSUFFICIENT_HISTORY


def test_a_trailing_gap_is_no_current_reading_not_a_collapse() -> None:
    """The same rule at the other end of the series. A period we have not sampled is not a zero,
    and judging the last KNOWN reading instead would date a July verdict to December."""
    verdict = detect_anomaly(series([100, 102, 98, 101, 99, 100, 500, None]))

    assert verdict.refusal is AnomalyRefusal.NO_CURRENT_READING
    assert not verdict.flagged and verdict.current_bp is None


# =================================================================================================
# THE ROW THAT PROVES THE CHOICE OF MAD
# =================================================================================================

def test_one_outlier_cannot_hide_inside_its_own_sigma() -> None:
    """**THE TEST THIS COMPONENT EXISTS FOR.**

    A standard deviation is defined by squared error, so one extreme reading widens the band in
    proportion to its own extremity — past a point the outlier sits INSIDE three sigma and a
    sigma-based detector reports it as normal. That is the exact reading an anomaly detector is
    built to catch, so the dispersion measure has to be one a single point cannot move: a median
    absolute deviation shifts by at most one rank however far one value travels.

    The float arithmetic below is deliberate and confined to the test. It is the thing being
    argued against; nothing in `anomaly.py` computes it.
    """
    values = [10, 10, 10, 10, 10, 10, 10_000]
    mean = sum(values) / len(values)
    sigma = (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5
    assert abs(values[-1] - mean) < 3 * sigma, (
        "the premise: the outlier is inside three sigma of the sample it dominates, so a "
        "sigma-based detector calls a thousandfold spike normal")

    verdict = detect_anomaly(series(values))
    assert verdict.flagged, "MAD catches exactly what sigma hid"
    assert verdict.baseline_bp == 10 and verdict.mad_bp == 0, (
        "the median and the MAD both ignore the outlier instead of being defined by it")
    assert verdict.z_like_bp > Z_LIKE_FLAG_BP


def test_an_extreme_reading_reports_an_unsaturated_ratio() -> None:
    """`z_like_bp` has NO ceiling — `require_ratio_bp`, not `require_bp`. A 40-MAD event must
    report as 40 MADs: a cap would render a catastrophe and a bad Tuesday as the same number,
    which is the only thing the field is read for."""
    verdict = detect_anomaly(series([100, 110, 90, 105, 95, 100, 400_000]))

    assert verdict.flagged and verdict.mad_bp == 5
    # |400000 - 100| * 10000 // 5 — nothing clamps, and it is three orders past the 0..10000 range
    # a proportion would have been checked against.
    assert verdict.z_like_bp == 399_900 * 10_000 // 5 == 799_800_000
    assert verdict.deviation_bp == 399_900 * 10_000 // 100
    assert verdict.anomaly is not None and verdict.anomaly.z_like_bp == verdict.z_like_bp


def test_the_two_flags_are_both_required() -> None:
    """Doc 04 step 5. Either condition alone is a false positive with a different cause: unusual
    alone is trivia, material alone is a metric that always swings that much."""
    trivial = detect_anomaly(series([1000, 1000, 1000, 1000, 1000, 1000, 1010]))
    assert trivial.z_like_bp > Z_LIKE_FLAG_BP and trivial.deviation_bp <= DEVIATION_FLAG_BP
    assert not trivial.flagged

    routine = detect_anomaly(series(NOISY + [500]))
    assert routine.deviation_bp > DEVIATION_FLAG_BP and routine.z_like_bp <= Z_LIKE_FLAG_BP
    assert not routine.flagged


# =================================================================================================
# INTEGER ARITHMETIC, DETERMINISM, AND NO CLOCK
# =================================================================================================

def test_the_same_series_yields_a_byte_identical_verdict() -> None:
    """Replayability. The detector takes no clock and no model, so a verdict recomputed in
    September from the same rows must equal March's — otherwise a disagreement between two
    readings can be attributed neither to the business nor to the instrument."""
    points = series([100, 102, 98, 101, 99, 100, 500])
    first, second = detect_anomaly(points), detect_anomaly(list(points))

    assert first == second
    assert anomaly_fact_value(first) == anomaly_fact_value(second)


def test_every_number_the_detector_reports_is_an_integer() -> None:
    """No float in any measure or score path. A float baseline compared against a float MAD makes
    the flag decision platform-dependent at the boundary, and the boundary is where it matters."""
    verdict = detect_anomaly(series([100, 102, 98, 101, 99, 100, 500]))

    for value in (verdict.current_bp, verdict.baseline_bp, verdict.mad_bp,
                  verdict.deviation_bp, verdict.z_like_bp, verdict.periods_used):
        assert isinstance(value, int) and not isinstance(value, bool)


def test_the_module_contains_no_float_and_no_model() -> None:
    """The group acceptance gate's two greps, run as a test so a regression fails the suite rather
    than a reviewer's shell."""
    source = (_ENGINE / "context" / "analytic" / "anomaly.py").read_text()
    for banned in ("float(", "import numpy", "import statistics", "sklearn",
                   "LLMClient", "anthropic"):
        assert banned not in source, f"{banned!r} in the anomaly detector"

    # No clock, either — `eval_time` is a parameter at every entry point, so a verdict for a past
    # instant is computed from what was known then rather than from what is true this morning.
    for clock in ("datetime.now", "utcnow", "time.time", "date.today"):
        assert clock not in source, f"{clock!r} in the anomaly detector — it must take no clock"


def test_baseline_uses_only_the_trailing_window() -> None:
    """"Unlike itself LATELY". An account that changed shape a year ago has a new normal, and
    averaging the old one back in would report the change forever."""
    verdict = detect_anomaly(series([5, 5, 5, 5, 5, 5, 100, 102, 98, 101, 99, 100, 101]))

    assert verdict.periods_used == BASELINE_PERIODS
    assert verdict.baseline_bp == 100, "the ancient 5s are outside the trailing six"
    assert not verdict.flagged


def test_an_empty_series_refuses_rather_than_raising() -> None:
    """A node with no history is the ordinary case on day one, not an error."""
    verdict = detect_anomaly([])
    assert verdict.refusal is AnomalyRefusal.INSUFFICIENT_HISTORY and verdict.periods_used == 0


# =================================================================================================
# THE FACT BODY
# =================================================================================================

def test_the_fact_body_carries_the_verdict_and_a_pointer_to_the_series() -> None:
    verdict = detect_anomaly(series([100, 102, 98, 101, 99, 100, 500]))
    body = anomaly_fact_value(verdict)

    assert anomaly_fact_field(METRIC) == f"{ANOMALY_FACT_PREFIX}{METRIC}"
    assert body["flagged"] is True and body["refusal"] is None
    assert body["direction"] == "above" and body["periods_used"] == 6
    assert body["z_like_bp"] == verdict.z_like_bp
    assert body["series"]["subject_node_id"] == NODE
    assert body["series"]["first_period"] == month(0).isoformat()
    assert body["series"]["last_period"] == month(6).isoformat()


def test_a_refusal_is_written_as_a_fact_too() -> None:
    """The stale-fact rule. Writing only the flagged verdicts leaves last week's anomaly sitting
    on a node that has since returned to normal, and nothing ever retracts it."""
    body = anomaly_fact_value(detect_anomaly(series([100, 102, 98])))

    assert body["flagged"] is False
    assert body["refusal"] == "insufficient_history"
    assert body["z_like_bp"] is None


# =================================================================================================
# THE WIRING — a REAL sweep, on a REAL database, reaching the anomaly detector
# =================================================================================================

def test_the_drain_calls_the_anomaly_refresh() -> None:
    """The cheap absence guard; the row below is the real one."""
    runner = (_ENGINE / "context" / "runner.py").read_text()
    assert "refresh_anomaly_facts" in runner
    assert "anomaly_facts" in runner


@pytest.mark.pg
def test_the_sweep_writes_the_anomaly_fact(pg_store) -> None:
    """**THIS IS THE TEST THAT MATTERS.** `context/runner.process_pending` reaches U2.

    Eleven monthly readings of `deal.stage_age_days` are seeded through the real store — a deal
    that has sat at ~30 days every month — and the sweep itself samples the twelfth, which the
    fixture has arranged to be far outside that band. Nothing above this line would notice if the
    two lines in `runner.py` were deleted, because every test builds its series by hand.

    The sweep is driven with no pending events on purpose: an anomaly is measured against a CLOCK,
    so the org whose inbox went quiet is exactly the org whose collapse is worth surfacing.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_anomaly_wiring"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_flat_history(pg_store, org, at)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=at)
        assert out["processed"] == 0, "no events: this sweep drained nothing"
        assert out["anomaly_facts"] > 0, (
            "the sweep reached no anomaly detector — `refresh_anomaly_facts` is not on the real "
            "request path")

        field = anomaly_fact_field(TrendedMetric.DEAL_STAGE_AGE_DAYS.value)
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select field, value from graph_facts "
                "where org_id=:o and field like :p order by field"),
                {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"}).all()
        written = {row.field: row.value for row in rows}
        assert field in written, f"no {field} fact: the series was there and no verdict written"

        body = written[field]
        assert body["refusal"] is None, body
        assert body["periods_used"] >= MIN_ANOMALY_PERIODS
        assert body["baseline_bp"] == 30, "eleven flat months at 30 days in stage"
        assert body["flagged"] is True and body["direction"] == "above", body
        assert body["z_like_bp"] > Z_LIKE_FLAG_BP
        assert body["series"]["subject_node_id"] == "node_acct_anom"

        # THE WRITE-AMPLIFICATION PROOF. `expertise_packages` reached 181 MB over 345 rows and put
        # this database into read-only, and the shape that did it was a writer that appended a row
        # every time it ran. A verdict is recomputed on EVERY drain, so this is the same shape
        # unless the version-keyed upsert holds.
        with pg_store.engine.connect() as conn:
            before = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"}).scalar()
        process_pending(org_id=org, store=pg_store, llm=None,
                        crypto_key=get_settings().crypto_key, eval_time=at)
        with pg_store.engine.connect() as conn:
            after = conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"}).scalar()
        assert after == before > 0, "two sweeps in one period must not grow graph_facts"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_refresh_reads_point_in_time(pg_store) -> None:
    """Replayability against a real store. The same org, refreshed at an `eval_time` BEFORE the
    series was sampled, must see none of it — a refresh that reached for `now()` inside the read
    would compute a past instant's verdict from today's readings."""
    org = "org_anomaly_asat"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_flat_history(pg_store, org, at)
    try:
        assert refresh_anomaly_facts(pg_store, org, eval_time=at).facts_written > 0
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from graph_facts where org_id=:o and field like :p"),
                         {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"})

        written = refresh_anomaly_facts(
            pg_store, org, eval_time=at - timedelta(days=365)).facts_written
        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select value from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"}).all()
        assert written == len(rows) > 0
        assert all(row.value["refusal"] is not None for row in rows), (
            "a read as-at a past instant must not see readings sampled later")
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_deleting_an_org_erases_its_anomaly_facts(pg_store) -> None:
    """U2 adds NO TABLE — the verdict is a `graph_facts` row, already on the org-scoped erasure
    list. Proven rather than asserted from the list: the loop in `api/account_routes` runs with no
    try/except, so an omission there is silent."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "graph_facts" in _ORG_SCOPED_TABLES

    org = "org_anomaly_erasure"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_flat_history(pg_store, org, at)
    try:
        assert refresh_anomaly_facts(pg_store, org, eval_time=at).facts_written > 0
        with pg_store.engine.begin() as conn:
            for table in _ORG_SCOPED_TABLES:
                conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                "select count(*) from graph_facts where org_id=:o"), {"o": org}).scalar() == 0
    finally:
        _drop_org(pg_store, org)


def test_the_per_sweep_read_is_capped() -> None:
    """The bound on the READ, which the version-keyed write does not cover."""
    assert MAX_ANOMALY_FACTS_PER_SWEEP == 2_000
    assert ANOMALY_WINDOW_PERIODS == 12 == 2 * BASELINE_PERIODS


# =================================================================================================
# D5 · THE WRITER MUST NOT REWRITE HISTORY
#
# The old upsert here ended `on conflict ... do update set ... valid_from = excluded.valid_from`.
# That one assignment MOVED the window of a row that already existed, so a verdict published in
# March and re-swept in September read back as `[September, inf)` — and `read_graph(as_of=March)`
# then answered "GeniOS knew nothing about this node in March" about a fact GeniOS itself had
# published in March. Every test above this line reads `graph_facts` with `valid_to is null`,
# which is the live read, and the live read was never wrong. That is why this shipped.
#
# So these read through X7's `read_graph(as_of=...)` — the reader doc 02's acceptance row is
# about — and never through a window predicate the test wrote itself.
# =================================================================================================

@pytest.mark.pg
def test_a_march_verdict_is_still_readable_at_march_after_a_september_sweep(pg_store) -> None:
    """**THE D5 TEST.** One node, one metric, two sweeps six months apart, and March's answer
    survives September's.

    The two verdicts differ in the way every verdict differs across periods: each names the window
    it was taken over, so March's row says it was measured to March and September's says
    September. That difference is what forces the writer to choose between SUPERSEDING March's row
    and overwriting it, and the whole of D5 is that it chose to overwrite.

    Under the old writer the September sweep moved the row's `valid_from` to September and
    `read_graph(as_of=March)` returned NOTHING for the field. Under `publish_derived_fact` March
    is closed at September's instant and keeps its own window, so both instants answer.
    """
    org = "org_anomaly_asof"
    march = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    september = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    field = anomaly_fact_field(TrendedMetric.DEAL_STAGE_AGE_DAYS.value)
    _seed_org_with_a_deal(pg_store, org, march)
    _seed_flat_history(pg_store, org, march)
    try:
        assert refresh_anomaly_facts(pg_store, org, eval_time=march).facts_written == 1
        at_march = _verdict_at(pg_store, org, field, march)
        assert at_march is not None
        assert at_march["series"]["last_period"].startswith("2026-03")

        assert refresh_anomaly_facts(pg_store, org, eval_time=september).facts_written == 1

        # THE ASSERTION THE OLD WRITER FAILED: March still answers, with MARCH'S verdict.
        replayed = _verdict_at(pg_store, org, field, march)
        assert replayed is not None, (
            "read_graph(as_of=March) returned nothing for a fact published in March — the "
            "September sweep moved its valid_from, which is D5")
        assert replayed == at_march, "March's row was rewritten with September's answer"

        # ...and September answers with September's, so this is a supersede and not a freeze.
        now = _verdict_at(pg_store, org, field, september)
        assert now is not None and now["series"]["last_period"].startswith("2026-09")

        # Two stints, contiguous and half-open: March's row closed at exactly the instant
        # September's opened, so no instant is answered twice and none is answered by nobody.
        with pg_store.engine.connect() as conn:
            windows = conn.execute(text(
                "select valid_from, valid_to, status from graph_facts "
                "where org_id=:o and field=:f order by valid_from"), {"o": org, "f": field}).all()
        assert len(windows) == 2, windows
        assert windows[0].valid_to == september and windows[0].status == "superseded"
        assert windows[1].valid_from == september and windows[1].valid_to is None
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_same_verdict_swept_again_writes_nothing_at_all(pg_store) -> None:
    """The other half of the bound: a sweep is not evidence. Re-running the SAME instant leaves
    the row untouched — not re-stamped, not re-inserted, not even an `occurred_at` touch — so an
    org that drains hourly does not pay a dead tuple per (node, metric) per hour."""
    org = "org_anomaly_idem"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    field = anomaly_fact_field(TrendedMetric.DEAL_STAGE_AGE_DAYS.value)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_flat_history(pg_store, org, at)
    try:
        first = refresh_anomaly_facts(pg_store, org, eval_time=at)
        again = refresh_anomaly_facts(pg_store, org, eval_time=at)
        assert first.facts_written == 1 and first.unchanged == 0
        assert again.facts_written == 0 and again.unchanged == 1
        with pg_store.engine.connect() as conn:
            assert conn.execute(text(
                "select count(*) from graph_facts where org_id=:o and field=:f"),
                {"o": org, "f": field}).scalar() == 1
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_the_verdict_is_published_at_the_scope_this_module_states(pg_store) -> None:
    """D2. `publish_derived_fact` refuses to default `visibility_scope`, and the answer this
    module gives is `org` — with a reason in the constant, not a literal in an INSERT.

    `org` is right HERE and is not right at the two correlation writers: a verdict carries numbers
    about one node and a pointer back to `metric_history`, never a peer's reading and never a
    sentence lifted out of somebody's mail.
    """
    org = "org_anomaly_scope"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_flat_history(pg_store, org, at)
    try:
        refresh_anomaly_facts(pg_store, org, eval_time=at)
        with pg_store.engine.connect() as conn:
            scopes = {row.visibility_scope for row in conn.execute(text(
                "select visibility_scope from graph_facts where org_id=:o and field like :p"),
                {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"}).all()}
        assert scopes == {ANOMALY_VISIBILITY_SCOPE} == {"org"}
    finally:
        _drop_org(pg_store, org)


def test_this_module_no_longer_writes_graph_facts_itself() -> None:
    """The structural half of D5 and D2 together. Four modules each carried their own copy of one
    upsert and all four ended it with `valid_from = excluded.valid_from`; the fix is not four
    corrected copies, it is ONE writer with the rule in it. So the defect cannot come back here by
    somebody adding a fifth INSERT."""
    source = (_ENGINE / "context" / "analytic" / "anomaly.py").read_text()
    assert "insert into graph_facts" not in source
    assert "update graph_facts" not in source
    assert "publish_derived_fact(" in source
    # The prefix is what scopes the shared writer's open-row lookup, so it has to stay a true
    # PREFIX of the id — and it has to keep matching the rows written before period keying, or
    # every legacy row becomes a second open row on a field that already has one.
    assert ANOMALY_VERSION_PREFIX == "fv_anomaly_"


# =================================================================================================
# D9 · THE DARK TAIL — the budget's tail must MOVE, and the drain must say the tail exists
# =================================================================================================

@pytest.mark.pg
def test_a_pair_cut_by_the_budget_is_judged_first_by_the_next_periods_sweep(pg_store) -> None:
    """**THE D9 TEST.** Three pairs, a budget of two, and the pair that misses out gets its
    verdict from the next sweep instead of never.

    The old read was `order by subject_node_id, metric limit :n`. That order is a function of the
    ids alone, so on an org above budget the SAME pairs were cut on every sweep, for ever: those
    nodes could never receive an anomaly verdict at all, and `anomaly.py` documented the stability
    as a feature. Ordering by staleness — never judged first — makes the omission temporary, and
    this test fails the moment the order goes back to being a function of the id.
    """
    org = "org_anomaly_tail"
    march = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    april = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
    nodes = ("node_tail_a", "node_tail_b", "node_tail_c")
    _seed_org(pg_store, org)
    for node in nodes:
        _seed_flat_history(pg_store, org, march, node_id=node)
    try:
        first = refresh_anomaly_facts(pg_store, org, eval_time=march, limit=2)
        assert first.pairs == 2 and first.budget_exhausted is True, (
            "a sweep that could not reach every pair must say so")
        judged_first = _judged_nodes(pg_store, org)
        assert len(judged_first) == 2
        cut = set(nodes) - judged_first
        assert len(cut) == 1

        second = refresh_anomaly_facts(pg_store, org, eval_time=april, limit=2)
        assert second.budget_exhausted is True
        assert cut <= _judged_nodes(pg_store, org), (
            f"{cut} was cut by March's budget and April's sweep cut it again — the queue is "
            "ordered by id, so this org's tail can never receive a verdict")
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_a_sweep_that_reached_every_pair_does_not_claim_a_tail(pg_store) -> None:
    """The other side of the flag, so `budget_exhausted` cannot be pinned True and called green.
    Reading exactly `limit` pairs is not evidence of a tail; reading `limit + 1` is."""
    org = "org_anomaly_notail"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    nodes = ("node_fit_a", "node_fit_b")
    _seed_org(pg_store, org)
    for node in nodes:
        _seed_flat_history(pg_store, org, at, node_id=node)
    try:
        sweep = refresh_anomaly_facts(pg_store, org, eval_time=at, limit=2)
        assert sweep.pairs == 2 and sweep.budget_exhausted is False
        assert _judged_nodes(pg_store, org) == set(nodes)
    finally:
        _drop_org(pg_store, org)


def test_the_drain_carries_every_budgeted_passs_ceiling_out_with_it() -> None:
    """D9's second half, over the runner's source: a ceiling that is computed and then DISCARDED
    at this seam (`refresh_comparison_facts(...).facts` threw `budget_exhausted` away) makes an
    org above budget look exactly like an org with nothing to do."""
    import inspect

    from genios_engine.context.runner import process_pending

    source = inspect.getsource(process_pending)
    assert '"budget_exhausted": dict(budgets)' in source
    for pass_name in ("metric_points", "anomaly", "cohorts", "comparison", "dependency",
                      "timeline"):
        assert f'budgets["{pass_name}"]' in source, pass_name


@pytest.mark.pg
def test_the_drain_reports_the_budget_ledger_for_a_real_org(pg_store) -> None:
    """And the same thing on the real request path, because a source scan cannot tell whether the
    key survives to the caller."""
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_anomaly_ledger"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    _seed_flat_history(pg_store, org, at)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=at)
        ledger = out["budget_exhausted"]
        assert set(ledger) == {"metric_points", "anomaly", "cohorts", "comparison", "dependency",
                               "timeline"}
        assert ledger["anomaly"] is False, "one node is not two thousand"
        assert all(value is False for value in ledger.values()), ledger
    finally:
        _drop_org(pg_store, org)


def _verdict_at(store, org: str, field: str, instant: datetime):
    """The verdict body X7's point-in-time reader returns for `instant`, or None.

    Through `read_graph(as_of=...)` on purpose — the same reader doc 02's acceptance row names.
    A test that wrote its own `valid_from <= t and (valid_to is null or valid_to > t)` would be
    asserting against a second copy of the predicate, and D5 is precisely a disagreement between
    what was written and what that predicate finds.
    """
    view = store.read_graph(org, as_of=instant)
    found = [fact for fact in view.facts if fact.field == field]
    assert len(found) <= 1, f"two rows answer at {instant.isoformat()}: {found}"
    return found[0].value if found else None


def _judged_nodes(store, org: str) -> set[str]:
    with store.engine.connect() as conn:
        return {row.subject_node_id for row in conn.execute(text(
            "select distinct subject_node_id from graph_facts where org_id=:o and field like :p "
            "and valid_to is null"), {"o": org, "p": f"{ANOMALY_FACT_PREFIX}%"}).all()}


# =================================================================================================
# FIXTURES — the smallest world in which a sweep has an anomaly to detect
# =================================================================================================

def _seed_org(store, org: str) -> None:
    """Just the tenant row. `graph_facts.org_id` is FK'd to it; nothing else here needs a node,
    because `refresh_anomaly_facts` reads its pairs off `metric_history` and never off the node
    table — which is the property the budget-rotation tests lean on."""
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Anomaly Wiring') "
                          "on conflict (id) do nothing"), {"o": org})


def _seed_org_with_a_deal(store, org: str, at: datetime) -> None:
    """One org, one company node, one stage fact aged far past its own norm, one observation to
    make the node active enough to sample."""
    _seed_org(store, org)
    with store.engine.begin() as conn:
        conn.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
            "values ('node_acct_anom', 1, :o, 'company', 'Northwind') "
            "on conflict do nothing"), {"o": org})
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "  value, value_type, status, occurred_at, valid_from) "
            "values ('fv_anomwire_stage', 'f_anomwire_stage', :o, 'node_acct_anom', "
            "  'deal.stage', cast('\"proposing\"' as jsonb), 'string', 'active', :at, :at) "
            "on conflict (fact_version_id) do nothing"),
            {"o": org, "at": at - timedelta(days=400)})
        conn.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "  occurred_at, status) "
            "values ('obs_anomwire_1', :o, 'node_acct_anom', 'meeting_request', :at, 'active') "
            "on conflict (observation_id) do nothing"),
            {"o": org, "at": at - timedelta(days=3)})


def _seed_flat_history(store, org: str, at: datetime, node_id: str = "node_acct_anom") -> None:
    """Eleven prior monthly readings of `deal.stage_age_days`, all 30 — the twelve-period window
    minus the period this sweep samples for itself, which the stage fact above makes ~400.

    `node_id` is a parameter so a test can seed SEVERAL pairs and watch the per-sweep budget
    choose between them; the default is the one node the wiring tests use.

    Written through the REAL store rather than by raw insert: `to_row` refuses an unregistered
    metric and a value that will not fit the column, so a fixture that went round it could seed a
    series the sampler itself could never have produced.
    """
    history = PostgresMetricHistory(store.engine, sampler_registry())
    metric = TrendedMetric.DEAL_STAGE_AGE_DAYS.value
    this_month = period_start(at, MetricGrain.MONTH)
    points = []
    for back in range(11, 0, -1):
        year, remainder = divmod(this_month.year * 12 + (this_month.month - 1) - back, 12)
        points.append(MetricPoint(
            subject_node_id=node_id, metric=metric, value_bp=30,
            unit=MetricUnit.DAYS, observed_at=this_month.replace(year=year, month=remainder + 1),
            known=True))
    # `sampled_at` is 45 days back: the sampler's cadence test reads it, so a fixture stamped with
    # the sweep's own instant would tell the sampler it had just run and no current point would be
    # taken — leaving the series with a trailing gap and the detector with nothing to judge.
    history.put(org, points, reason=SampleReason.BACKFILL, sampled_at=at - timedelta(days=45))


def _drop_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        for table in ("metric_history", "graph_observations", "graph_facts", "graph_nodes"):
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
