"""The builders in `tests/context/conftest.py`, exercised.

Not a placeholder. Layer 1's most expensive lesson was six units that were green and called by
nothing, and a fixture module is the easiest place in a suite for that to happen again: every
one of the seventeen files beside this one is currently a skip, so `qes`, `graph`,
`declining_series` and `MetricSeriesPoint` have no caller at all until X1 lands. A factory that
has never been run is a factory that will fail on the first wave that touches it, at the worst
possible moment — inside a gate.

These are the assertions that can actually fail:

* `qes()` constructs the REAL `QualifiedEnterpriseSignal`. If L1 adds a required field or
  tightens a validator, this file goes red HERE, in a two-second run, instead of in H5;
* the signal counter makes ids unique within a test and identical across runs — the property
  H5's "identical input twice -> byte-identical" row rests on;
* `MetricSeriesPoint` REFUSES the interpolated point (V-3's shape) rather than letting a test
  hand a fabricated observation to a trend;
* `declining_series` produces the exact two populations H2 contrasts — 6 clean points, and the
  same values with holes — with periods derived from `eval_time`, not from a literal.

Table-driven where there is a table, one row per condition.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from genios_engine.contracts.signal import QualifiedEnterpriseSignal, SignalType



# ── the clock ────────────────────────────────────────────────────────────────────────────────
def test_the_frozen_instant_is_the_one_the_retention_horizon_is_derived_from(
        eval_time, retention_horizon):
    """`RETENTION_HORIZON` must be 24 months of `eval_time`, not a second hardcoded date. Two
    literals is how a retention test and a series test end up measuring different windows."""
    assert eval_time.tzinfo is not None, "a naive eval_time would compare unpredictably"
    assert retention_horizon == eval_time - timedelta(days=730)
    assert eval_time.weekday() == 6, "the docstring's Sunday claim is load-bearing for ISO weeks"


# ── the signal factory ───────────────────────────────────────────────────────────────────────
def test_the_factory_builds_the_real_contract_not_a_lookalike(qes, org_id):
    s = qes(importance_bp=8200, signal_type=SignalType.RISK_FLAGGED)
    assert isinstance(s, QualifiedEnterpriseSignal)
    assert s.org_id == org_id, "the scratch org tests/conftest.py seeds — a pg test FKs against it"
    assert s.importance_bp == 8200
    assert s.signal_type is SignalType.RISK_FLAGGED
    assert s.evidence_refs, "the contract requires evidence; a factory that omitted it is useless"


def test_importance_has_no_default_so_a_flat_population_is_never_an_accident(qes):
    """H5 fails on a population that sits at one value. The factory must not make that the
    easiest thing to write."""
    with pytest.raises(TypeError):
        qes()                                       # type: ignore[call-arg]


def test_ids_are_unique_within_a_test_and_stable_across_runs(qes):
    first = [qes(importance_bp=5000).signal_id for _ in range(3)]
    assert len(set(first)) == 3, "duplicate signal ids would collide in any store-backed test"
    assert first == ["sig_l2_0", "sig_l2_1", "sig_l2_2"], (
        "ids must be derived from a counter, not a uuid — reproducibility is an H5 row")


def test_an_unknown_field_is_rejected_at_the_seam(qes):
    """`extra='forbid'` on the contract. A factory that swallowed typos would let a test think
    it had set `importance` when it had set nothing."""
    with pytest.raises(ValidationError):
        qes(importance_bp=5000, importnace=9000)


@pytest.mark.parametrize("state", ["active", "superseded", "expired", "resolved"])
def test_every_lifecycle_state_the_contract_allows_can_be_built(qes, state):
    assert qes(importance_bp=5000, state=state).state == state


def test_a_state_outside_the_closed_set_is_refused(qes):
    with pytest.raises(ValidationError):
        qes(importance_bp=5000, state="closed")


def test_the_spread_helper_gives_the_h5_shape(qes_spread):
    """One critical + four routine, which is the row that proves `max` rather than `mean`."""
    signals = qes_spread()
    scores = sorted(s.importance_bp for s in signals)
    assert len(signals) == 5
    assert scores[-1] >= 9000, "no critical signal means the max/mean row cannot be tested"
    assert max(scores) - min(scores) > 1500, "a spread this narrow cannot distinguish max"
    assert len({s.signal_id for s in signals}) == 5


# ── the metric point ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("known", "value_bp", "legal"), [
    (True, 4200, True),        # an ordinary observed value
    (True, 0, True),           # a real, measured zero — legal, and NOT the same as a gap
    (False, None, True),       # a coverage gap: unknown, carrying nothing
    (True, None, False),       # "we know it" with no value — a claim with no content
    (False, 4200, False),      # a gap with a value — the interpolation V-3 rejects
])
def test_a_point_may_not_be_both_a_gap_and_a_value(metric_point, eval_time, known,
                                                  value_bp, legal):
    build = lambda: metric_point("node_acct_north", "engagement.touch_count_28d",
                                eval_time, value_bp, known=known)
    if legal:
        assert build().known is known
    else:
        with pytest.raises(AssertionError):
            build()


# ── the graph ────────────────────────────────────────────────────────────────────────────────
def test_the_default_graph_is_below_the_legal_cohort_floor(graph, org_id):
    """Three accounts: enough to compare, deliberately under `population_size >= 5` so a test
    that wants a valid `CohortPosition` has to add members on purpose."""
    g = graph()
    assert g.org_id == org_id
    assert len(g.nodes) == 3
    assert g.node("node_acct_summit").display_name == "Summit Labs"


def test_naming_a_node_the_graph_does_not_have_fails_loudly(graph):
    with pytest.raises(AssertionError):
        graph().node("node_acct_missing")


# ── the series ───────────────────────────────────────────────────────────────────────────────
def test_the_declining_series_is_six_clean_points_ending_at_eval_time(
        declining_series, eval_time, period):
    points = declining_series()
    assert len(points) == 6
    assert all(p.known for p in points)
    assert points[-1].observed_at == eval_time
    assert points[0].observed_at == eval_time - period * 5, "periods must be derived, not typed"
    values = [p.value_bp for p in points]
    assert values == sorted(values, reverse=True), "H2's decisive row needs a real decline"


def test_the_same_series_with_three_gaps_carries_no_values_in_them(declining_series):
    """H2: the same values with 3 gaps must read INSUFFICIENT_COVERAGE, not DECLINING — which
    is only a meaningful test if the gaps are genuinely empty."""
    points = declining_series(gaps=(1, 2, 3))
    gaps = [p for p in points if not p.known]
    assert len(gaps) == 3
    assert all(p.value_bp is None and p.coverage_ready is False for p in gaps)
    assert [p.observed_at for p in points] == [p.observed_at for p in declining_series()], (
        "the gapped series must occupy the SAME periods, or it is a different experiment")


# ── the hermetic guard ───────────────────────────────────────────────────────────────────────
def test_an_unmarked_context_test_cannot_open_a_connection():
    """The guard `tests/capture/` has, in the tree where every unit wants a database."""
    import socket
    with pytest.raises(RuntimeError, match="network access refused"):
        socket.socket().connect(("127.0.0.1", 5432))
