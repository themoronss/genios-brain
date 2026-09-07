"""Builders for the L2.6 suite — one slice factory, and a pattern factory that is DATA.

Everything here follows `tests/context/conftest.py`'s discipline: the clock is `eval_time`, the
graph is a frozen description, and nothing reaches the network. The addition is a `GraphSlice`
factory, because every unit in `context/patterns/` takes a slice and a test that assembled one by
hand in each file would drift from the shape the store actually produces.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

import pytest

from genios_engine.context.patterns.contract import Pattern
from genios_engine.context.patterns.registry import load_pattern
from genios_engine.context.patterns.slice import (GraphSlice, SliceEdge, SliceFact, SliceNode,
                                                  SliceObservation)
from genios_engine.contracts.analytic import (Anomaly, AnomalyDirection, CohortBand,
                                              CohortPosition, MetricPoint, MetricUnit, Trend,
                                              TrendDirection)
from genios_engine.contracts.quality import AbsenceType, MissingFact

ANCHOR_ID = "node_sub_aws"


@pytest.fixture
def fact():
    """One `SliceFact`. `fact_version_id` defaults to a derivation of the field so a test never
    has to invent an id, and two facts on one field are still distinguishable."""
    def _build(field_path: str, value: Any, *, node_id: str = ANCHOR_ID,
               fact_version_id: str | None = None, occurred_at: datetime | None = None,
               **kw: Any) -> SliceFact:
        return SliceFact(subject_node_id=node_id, field_path=field_path, value=value,
                         fact_version_id=fact_version_id or f"fv_{field_path.replace('.', '_')}",
                         occurred_at=occurred_at, **kw)
    return _build


@pytest.fixture
def absent():
    """A typed absence. The `absence_type` is REQUIRED with no default, which is the fixture's one
    opinion: the whole subject of L2.5.5 is that the five answers are different, and a default
    would make the dangerous one (`GENUINELY_ABSENT`) the one a test gets without asking."""
    def _build(expected_fact: str, absence_type: AbsenceType, *, node_id: str = ANCHOR_ID,
               coverage_ready: bool | None = True,
               coverage_basis: Sequence[str] = ("gmail", "gcal")) -> MissingFact:
        if absence_type is AbsenceType.UNKNOWABLE:
            coverage_ready, coverage_basis = None, ()
        return MissingFact(subject_node_id=node_id, expected_fact=expected_fact,
                           absence_type=absence_type, coverage_ready=coverage_ready,
                           coverage_basis=tuple(sorted(coverage_basis)))
    return _build


@pytest.fixture
def graph_slice(eval_time):
    """One anchor's world. Everything defaults to empty so a test states only what it is about."""
    def _build(*, node_type: str = "subscription", node_id: str = ANCHOR_ID,
               facts: Sequence[SliceFact] = (), edges: Sequence[SliceEdge] = (),
               observations: Sequence[SliceObservation] = (),
               absences: Sequence[MissingFact] = (), trends: Sequence[Trend] = (),
               cohort_positions: Sequence[CohortPosition] = (),
               anomalies: Sequence[Anomaly] = (),
               edge_coverage: Sequence[str] = (),
               authority_threshold_minor_units: int | None = None,
               authority_rule_id: str | None = None,
               member_signal_ids: Sequence[str] = (),
               member_event_ids: Sequence[str] = (),
               org_id: str = "org_scratch_tests") -> GraphSlice:
        return GraphSlice(
            org_id=org_id, anchor=SliceNode(node_id, node_type, "AWS"),
            facts=tuple(facts), edges=tuple(edges), observations=tuple(observations),
            absences=tuple(absences), trends=tuple(trends),
            cohort_positions=tuple(cohort_positions), anomalies=tuple(anomalies),
            edge_coverage=frozenset(edge_coverage),
            authority_threshold_minor_units=authority_threshold_minor_units,
            authority_rule_id=authority_rule_id,
            member_signal_ids=tuple(member_signal_ids),
            member_event_ids=tuple(member_event_ids), read_at=eval_time)
    return _build


@pytest.fixture
def observation(eval_time):
    def _build(kind: str, *, days_ago: int = 1, node_id: str = ANCHOR_ID,
               observation_id: str | None = None) -> SliceObservation:
        return SliceObservation(observation_id=observation_id or f"obs_{kind}",
                                subject_node_id=node_id, kind=kind,
                                occurred_at=eval_time - timedelta(days=days_ago))
    return _build


@pytest.fixture
def trend(eval_time):
    """A real `Trend`, built through the contract so a fixture cannot be a shape L2.4 can no
    longer produce."""
    def _build(metric: str = "engagement.touch_count_28d",
               direction: TrendDirection = TrendDirection.DECLINING,
               *, confidence_bp: int = 7000, point_count: int = 6) -> Trend:
        points = tuple(MetricPoint(
            subject_node_id=ANCHOR_ID, metric=metric, unit=MetricUnit.COUNT,
            observed_at=eval_time - timedelta(days=7 * (point_count - i)),
            value_bp=1000 * (point_count - i), known=True,
            coverage_ready=True) for i in range(point_count))
        # The slope has to agree with the direction — the contract refuses a rising trend with a
        # negative slope, the same "the label must match the number" rule the cohort band keeps.
        slope = {TrendDirection.RISING: 2500, TrendDirection.DECLINING: -2500}.get(direction, 0)
        return Trend(metric=metric, direction=direction, relative_slope_bp=slope,
                     streak_periods=point_count, point_count=point_count,
                     coverage_ratio_bp=10000, trend_confidence_bp=confidence_bp,
                     evidence_points=points)
    return _build


@pytest.fixture
def position(eval_time):
    def _build(metric: str = "engagement.touch_count_28d", *, percentile_bp: int = 1200,
               population: int = 20, band: CohortBand | None = None) -> CohortPosition:
        # The band is DERIVED from the percentile and the population, never chosen: the contract
        # refuses a label its own arithmetic cannot reach, and a fixture that hardcoded `D2` would
        # be unbuildable for every cohort of ten or fewer.
        label = band or CohortBand.for_percentile(percentile_bp, divisions=10,
                                                  population_size=population)
        return CohortPosition(metric=metric, cohort_id="coh_seed_accounts",
                              population_size=population, percentile_bp=percentile_bp, band=label,
                              p25_bp=1000, p50_bp=2000, p75_bp=3000, computed_at=eval_time)
    return _build


@pytest.fixture
def anomaly():
    def _build(metric: str = "support.ticket_count_28d", *,
               direction: AnomalyDirection = AnomalyDirection.ABOVE,
               periods_used: int = 8, z_like_bp: int = 40000) -> Anomaly:
        # The reading has to sit on the side the direction names — the contract refuses a BELOW
        # anomaly whose current reading is above its baseline, which is the same "the label must
        # match the number" rule `CohortBand` keeps.
        above = direction is AnomalyDirection.ABOVE
        return Anomaly(metric=metric, current_bp=9000 if above else 500, baseline_bp=3000,
                       mad_bp=500, deviation_bp=20000, z_like_bp=z_like_bp, direction=direction,
                       periods_used=periods_used)
    return _build


@pytest.fixture
def pattern():
    """A pattern from the doc-06 mapping shape, with the boilerplate every pattern needs.

    Built through `load_pattern` and not through `Pattern(...)`, so every test in this tree
    exercises the same parser the YAML files go through — a fixture that bypassed it would prove
    the evaluator against objects no file can produce.
    """
    def _build(**overrides: Any) -> Pattern:
        body: dict[str, Any] = {
            "pattern_id": "test_pattern", "version": 1, "domain": ["admin"],
            "anchor": {"node_type": "subscription"},
            "conditions": [{"kind": "fact", "field": "subscription.status", "op": "eq",
                            "value": "active"}],
            "emits": {"situation_type": "test_situation"},
            "expected_fire_rate": {"per_100_anchors_per_30d": 5},
            "owner": "harsh@thegenios.com",
            "first_evidence": {"positive": "fixture", "negative": "fixture"}}
        body.update(overrides)
        return load_pattern(body)
    return _build
