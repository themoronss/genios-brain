"""H1 · L2.4.2 — the metric sampler (BLG-07). The gate for `context/analytic/sampler.py`.

Doc 09 names five acceptance rows for this unit and every one of them is a line of BLG-07's
decision table, so the suite is organised the same way: one test per row, then the cases that are
about the table as a whole — the honest gap, determinism, the point budget, and the wiring.

WHY THE WIRING TEST IS THE ONE THAT MATTERS. Layer 1 shipped six units that were built, green and
called by nothing on a real request path, and each was found only by adversarial review. A test
that constructs a sampler, hands it a snapshot and asserts on the result proves the UNIT. It does
not prove that a sweep ever reaches it. `test_the_sweep_writes_history` therefore drives
`context/runner.process_pending` — the function the sync route and the upload route both call —
against a real Postgres, seeds nothing but graph rows, and asserts that `metric_history` has
points in it afterwards. If the call in `runner.py` is deleted, that test fails and nothing else
here does.

THE HERMETIC LANE USES THE REAL STORE. `history.InMemoryMetricHistory` enforces the same primary
key, the same conditional upsert and the same `to_row` refusals as the table, so a hermetic test
here is not testing a mock of the seam — it is testing the seam with a dict behind it. The only
thing it cannot prove is the SQL, which is what the `pg`-marked tests are for.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.history import (InMemoryMetricHistory, MetricGrain,
                                                    SampleReason, period_start)
from genios_engine.context.analytic.sampler import (BACKFILLABLE, TRENDED_METRICS, Cadence,
                                                    LastPoint, NodeSnapshot, NotBackfillable,
                                                    OrgSnapshot, PointBudget, Reading,
                                                    SamplingContext, TrendedMetric, backfill_org,
                                                    decide, measure, sample_org,
                                                    sampler_registry)

pytestmark = pytest.mark.unit

ORG = "org_scratch_tests"

#: A metric on every one of the three subject types, measured from the message timeline — the
#: cheapest reading to arrange and the one four of the twelve share. Used wherever a test is about
#: the POLICY rather than about a particular measurement.
TOUCHES = TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D


# =================================================================================================
# BUILDERS — a snapshot is data, so every test states the world it is about
# =================================================================================================

def snapshot(*, eval_time: datetime, nodes=(), timeline=None, facts=None, people=None,
             open_asks=None, has_support_desk=False, last_points=None) -> OrgSnapshot:
    """An `OrgSnapshot` with everything defaulted to empty.

    Written out rather than taken from `tests/context/conftest.py`'s `graph` fixture because that
    fixture describes a graph for the whole L2 tree and this unit reads a DERIVED view of it —
    two timestamps per node, a directed timeline, and the last stored point. A test that had to
    go through the graph description to say "this node went quiet in January" would be stating
    the input twice.
    """
    return OrgSnapshot(
        org_id=ORG, eval_time=eval_time, nodes={n.node_id: n for n in nodes},
        timeline={k: tuple(v) for k, v in (timeline or {}).items()},
        facts=facts or {}, people_by_company={k: tuple(v) for k, v in (people or {}).items()},
        open_asks={k: tuple(v) for k, v in (open_asks or {}).items()},
        has_support_desk=has_support_desk, last_points=last_points or {})


def messages(eval_time: datetime, *, days_ago: tuple[int, ...],
             direction: str = "in") -> list[tuple[str, datetime]]:
    """A directed timeline stated in days before `eval_time`, oldest first."""
    return sorted(((direction, eval_time - timedelta(days=d)) for d in days_ago),
                  key=lambda e: e[1])


def context(*, eval_time: datetime, node: NodeSnapshot, value: int | None = 10,
            last_point: LastPoint | None = None,
            metric: TrendedMetric = TOUCHES) -> SamplingContext:
    return SamplingContext(node=node, metric=metric, current_value_bp=value,
                           last_point=last_point, eval_time=eval_time)


def store_with(points=()) -> InMemoryMetricHistory:
    history = InMemoryMetricHistory(sampler_registry())
    for point in points:
        history.put(ORG, [point], reason=SampleReason.SCHEDULED, sampled_at=point.observed_at)
    return history


# =================================================================================================
# BLG-07 — one test per row of the decision table
# =================================================================================================

def test_row_1_a_dormant_node_with_no_activity_is_not_sampled_weekly(eval_time) -> None:
    """Doc 09's first acceptance row, and it is the one that bounds the table.

    Row 1 says "activity in 90d". A node last seen 200 days ago fails it, and with no series and
    no situation nothing else matches either — so the whole (node, metric) pair produces nothing.
    A sampler that sampled it anyway would be paying a row a week for every counterparty the
    business has ever emailed, for ever.
    """
    dormant = NodeSnapshot("node_cold", "company",
                           last_activity_at=eval_time - timedelta(days=200))
    decision = decide(context(eval_time=eval_time, node=dormant))
    assert decision.sampled is False
    assert decision.cadence is None
    assert "no BLG-07 row matches" in decision.explanation


def test_row_1_an_active_counterparty_is_sampled_weekly(eval_time) -> None:
    """The default trended set: an account/deal/person the graph saw move inside 90 days."""
    warm = NodeSnapshot("node_warm", "company", last_activity_at=eval_time - timedelta(days=10))
    decision = decide(context(eval_time=eval_time, node=warm))
    assert (decision.sampled, decision.rule, decision.cadence) == (True, 1, Cadence.WEEKLY)
    assert decision.sample_reason is SampleReason.SCHEDULED


def test_row_1_does_not_reach_a_node_type_the_metric_is_not_about(eval_time) -> None:
    """`account.contact_breadth` is about a company. A `thread` node is not one, and the graph
    holds thousands of them — each of which would otherwise open a twelve-metric series."""
    thread = NodeSnapshot("node_thread", "thread", last_activity_at=eval_time)
    decision = decide(context(eval_time=eval_time, node=thread,
                              metric=TrendedMetric.ACCOUNT_CONTACT_BREADTH))
    assert decision.sampled is False


def test_row_2_a_node_in_an_active_situation_is_sampled_daily(eval_time) -> None:
    """Doc 09's second row. Sampled TODAY even though it was already sampled yesterday — which is
    exactly what a weekly-only node would refuse."""
    live = NodeSnapshot("node_live", "company", last_activity_at=eval_time - timedelta(days=1),
                        in_active_situation=True)
    yesterday = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                          sampled_at=eval_time - timedelta(days=1), value_bp=10)
    decision = decide(context(eval_time=eval_time, node=live, last_point=yesterday))
    assert (decision.sampled, decision.rule, decision.cadence) == (True, 2, Cadence.DAILY)


def test_row_2_beats_row_1_when_both_match(eval_time) -> None:
    """A node can match several rows and the STRONGEST cadence wins.

    If row 1 could dilute row 2 to weekly, "while something is live, resolution matters" would be
    false for precisely the nodes it was written for — every node in an active situation is also
    an active counterparty.
    """
    live = NodeSnapshot("node_live", "company", last_activity_at=eval_time - timedelta(days=1),
                        in_active_situation=True)
    sampled_today = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                              sampled_at=eval_time - timedelta(hours=2), value_bp=10)
    already = decide(context(eval_time=eval_time, node=live, last_point=sampled_today))
    assert already.sampled is False, "daily means once a day, not once a sweep"

    yesterday = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                          sampled_at=eval_time - timedelta(days=1), value_bp=10)
    assert decide(context(eval_time=eval_time, node=live, last_point=yesterday)).rule == 2


def test_row_3_a_value_crossing_changepoint_bp_is_sampled_immediately_off_cadence(
        eval_time) -> None:
    """Doc 09's third row, and `off-cadence` is the whole claim.

    The node was sampled two hours ago, so neither the weekly nor the daily nor the monthly test
    is due. A 40% move on a metric whose `changepoint_bp` is 3000 is sampled anyway, because a
    changepoint is the most informative reading there is and waiting five days for the cadence
    would lose the week it happened in.
    """
    warm = NodeSnapshot("node_warm", "company", last_activity_at=eval_time - timedelta(days=2))
    two_hours_ago = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                              sampled_at=eval_time - timedelta(hours=2), value_bp=100)
    assert decide(context(eval_time=eval_time, node=warm, value=102,
                          last_point=two_hours_ago)).sampled is False, "2% is noise, not a move"
    moved = decide(context(eval_time=eval_time, node=warm, value=140, last_point=two_hours_ago))
    assert (moved.sampled, moved.rule, moved.cadence) == (True, 3, Cadence.IMMEDIATE)
    assert moved.sample_reason is SampleReason.CHANGEPOINT


def test_row_3_never_fires_off_a_gap_or_a_first_reading(eval_time) -> None:
    """Two refusals, and both of them invent a number if they are missing.

    A changepoint against a previous point with no value is a move measured from an absence, and
    a changepoint with no previous point at all would label every node the graph has just learned
    about as having moved — on its first sweep, all at once.
    """
    warm = NodeSnapshot("node_warm", "company", last_activity_at=eval_time - timedelta(days=2))
    from_gap = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                         sampled_at=eval_time - timedelta(hours=2), value_bp=None)
    assert decide(context(eval_time=eval_time, node=warm, value=140,
                          last_point=from_gap)).sampled is False
    # No previous point: rule 1 may well fire, but never rule 3.
    first = decide(context(eval_time=eval_time, node=warm, value=140, last_point=None))
    assert first.rule != 3


def test_row_3_treats_a_move_off_zero_as_off_the_scale(eval_time) -> None:
    """0 -> 1 overdue commitments has no percentage, and it is the most informative sample here.

    Integer division by the previous reading would be a ZeroDivisionError; reporting it as a move
    off the top of a bounded scale is what makes the honest answer also the arithmetic one.
    """
    warm = NodeSnapshot("node_warm", "company", last_activity_at=eval_time - timedelta(days=2))
    sampled_today = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                              sampled_at=eval_time - timedelta(hours=1), value_bp=0)
    decision = decide(context(eval_time=eval_time, node=warm, value=1,
                              last_point=sampled_today,
                              metric=TrendedMetric.ACCOUNT_OVERDUE_COMMITMENT_COUNT))
    assert (decision.sampled, decision.rule) == (True, 3)
    # ... and 0 -> 0 is not a move at all.
    flat = decide(context(eval_time=eval_time, node=warm, value=0, last_point=sampled_today,
                          metric=TrendedMetric.ACCOUNT_OVERDUE_COMMITMENT_COUNT))
    assert flat.rule != 3


def test_row_4_a_revived_node_is_sampled_immediately_and_only_once(eval_time) -> None:
    """Doc 09 does not spell this row out; BLG-07 does, and "only once" is the part with a bill.

    A node quiet since October and back yesterday matches row 4. On the NEXT sweep, with the same
    activity and a point already sampled after it, row 4 must not fire again — otherwise a
    returning account re-measures the whole org's twelve metrics on every sweep for a week to
    rewrite numbers that have not changed.
    """
    revived = NodeSnapshot("node_back", "company",
                           last_activity_at=eval_time - timedelta(days=1),
                           prior_activity_at=eval_time - timedelta(days=120))
    sampled_before_it_came_back = LastPoint(
        observed_at=period_start(eval_time - timedelta(days=7), MetricGrain.WEEK),
        sampled_at=eval_time - timedelta(days=7), value_bp=3)
    first = decide(context(eval_time=eval_time, node=revived, value=3,
                           last_point=sampled_before_it_came_back))
    assert (first.sampled, first.rule, first.cadence) == (True, 4, Cadence.IMMEDIATE)

    sampled_since = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                              sampled_at=eval_time - timedelta(hours=1), value_bp=3)
    again = decide(context(eval_time=eval_time, node=revived, value=3,
                           last_point=sampled_since))
    assert again.rule != 4


def test_row_4_ignores_a_node_that_never_went_quiet(eval_time) -> None:
    """Two messages a week apart is an ordinary active relationship, not a revival.

    `DORMANT_AFTER_DAYS` is imported from `situations.py` rather than restated, so "gone quiet"
    means the same number of days here as it does on the surface that renders it.
    """
    steady = NodeSnapshot("node_steady", "company",
                          last_activity_at=eval_time - timedelta(days=1),
                          prior_activity_at=eval_time - timedelta(days=8))
    older = LastPoint(observed_at=period_start(eval_time - timedelta(days=7), MetricGrain.WEEK),
                      sampled_at=eval_time - timedelta(days=7), value_bp=3)
    assert decide(context(eval_time=eval_time, node=steady, value=3,
                          last_point=older)).rule != 4


def test_row_5_every_node_with_a_series_gets_a_point_each_month(eval_time) -> None:
    """Doc 09's fourth row — the floor density, and the case is a node that fails every other row.

    Dormant for 200 days, in no situation, with a series that stops in January. Rule 5 alone
    fires, monthly, which is what keeps a decline to nothing visible instead of the series simply
    ending and a trend computer reporting "insufficient history" about an account that went dark.
    """
    dormant = NodeSnapshot("node_cold", "company",
                           last_activity_at=eval_time - timedelta(days=200))
    last_month = LastPoint(observed_at=period_start(eval_time - timedelta(days=40),
                                                    MetricGrain.WEEK),
                           sampled_at=eval_time - timedelta(days=40), value_bp=2)
    decision = decide(context(eval_time=eval_time, node=dormant, value=2,
                              last_point=last_month))
    assert (decision.sampled, decision.rule, decision.cadence) == (True, 5, Cadence.MONTHLY)

    # ... and it is a MONTH boundary, not "30 days ago": sampled earlier this month, not due.
    this_month = LastPoint(observed_at=period_start(eval_time, MetricGrain.WEEK),
                           sampled_at=eval_time - timedelta(hours=1), value_bp=2)
    assert decide(context(eval_time=eval_time, node=dormant, value=2,
                          last_point=this_month)).sampled is False


def test_row_5_does_not_start_a_series_on_a_node_the_graph_never_saw_move(eval_time) -> None:
    """The scope that turns rule 5 from a floor into a bill.

    Read as "every node in the graph", the monthly rule is 600k rows a month on a 50k-node org
    from this line alone — the shape of the `expertise_packages` incident. A node with no
    activity and no existing series is not sampled at all.
    """
    never = NodeSnapshot("node_ghost", "company", last_activity_at=None)
    assert decide(context(eval_time=eval_time, node=never, last_point=None)).sampled is False


def test_everything_else_is_not_sampled(eval_time) -> None:
    """BLG-07's last line, stated as its own case because it is the default the table relies on."""
    nothing = NodeSnapshot("node_ghost", "person", last_activity_at=None)
    for metric in TRENDED_METRICS:
        assert decide(context(eval_time=eval_time, node=nothing, metric=metric,
                              value=None)).sampled is False


# =================================================================================================
# THE REGISTRY
# =================================================================================================

def test_trended_metrics_is_a_registered_enum_with_a_question_each() -> None:
    """Doc 04: metric names are a registered enum, not free strings, and adding one is deliberate.

    A free string splits its own series on a rename — the old rows stay, the new rows accumulate,
    and a trend over either half reports insufficient history about a metric with years of it.
    The `question` field is BLG-07's other requirement: a metric that cannot name the customer
    question it serves is storage growth with no reader.
    """
    assert len(TRENDED_METRICS) == 12
    for metric, spec in TRENDED_METRICS.items():
        assert isinstance(metric, TrendedMetric)
        assert spec.question.endswith("?"), f"{metric.value} names no customer question"
        assert spec.subject_types, f"{metric.value} is about no node type"
        assert spec.changepoint_bp > 0


def test_every_registered_metric_is_writable_by_the_store() -> None:
    """The registry the sampler hands the store must accept every name the sampler can produce.

    `history.to_row` refuses an unregistered metric — correctly, it is the rename guard — so a
    metric registered here and missing there is a sampler that raises on its first real write.
    """
    registry = sampler_registry()
    for metric, spec in TRENDED_METRICS.items():
        definition = registry.require(metric.value)
        assert definition.unit is spec.unit, f"{metric.value} unit disagrees with the store"
        assert definition.grain is spec.grain


def test_backfillable_is_the_subset_the_event_ledger_can_answer() -> None:
    """U2 refuses rather than approximating.

    `deal.value_minor_units` is computed from a current-value fact; replaying it would stamp
    today's number on last March with `sample_reason='backfill'` on it, which is a fabricated
    observation with paperwork.
    """
    assert TrendedMetric.ENGAGEMENT_TOUCH_COUNT_28D in BACKFILLABLE
    assert TrendedMetric.DEAL_VALUE_MINOR_UNITS not in BACKFILLABLE
    with pytest.raises(NotBackfillable):
        backfill_org(None, org_id=ORG, metric=TrendedMetric.DEAL_VALUE_MINOR_UNITS,
                     since=datetime(2026, 1, 1, tzinfo=timezone.utc),
                     until=datetime(2026, 3, 1, tzinfo=timezone.utc))


# =================================================================================================
# A METRIC WITH NO READING IS NOT ZERO
# =================================================================================================

def test_a_metric_the_graph_cannot_answer_is_a_gap_and_not_a_row(eval_time) -> None:
    """The rule the whole group rests on, in the one case that occurs on every live org.

    `derived.py` refuses to infer `deal.value` — "there is no honest way to infer a number nobody
    stated" — so the fact is absent on all but one node of the design partner's graph. The
    sampler must produce `known=False` with no value, and must write NO ROW: `metric_history`'s
    `value_bp` is NOT NULL, so absence IS the storage of a gap, and `read_series` materialises it
    back as a gap. A zero here would make the pipeline look like it collapsed to nothing.
    """
    node = NodeSnapshot("node_acct", "company", last_activity_at=eval_time - timedelta(days=1))
    world = snapshot(eval_time=eval_time, nodes=[node])
    history = store_with()

    run = sample_org(None, org_id=ORG, eval_time=eval_time, history=history,
                     snapshot=world)

    gaps = {p.metric for p in run.gap_points}
    assert TrendedMetric.DEAL_VALUE_MINOR_UNITS.value in gaps
    for point in run.gap_points:
        assert point.known is False and point.value_bp is None
    assert all(p.value_bp is not None for p in run.points), "a stored point always has a reading"
    # The decisive assertion: no row, and in particular no zero.
    series = history.read_series(ORG, "node_acct", TrendedMetric.DEAL_VALUE_MINOR_UNITS.value,
                                 since=eval_time, until=eval_time)
    assert [p.value_bp for p in series] == [None]
    assert [p.known for p in series] == [False]


def test_a_zero_reading_and_a_gap_are_different_things(eval_time) -> None:
    """Zero touches on a node we have corresponded with is a READING; on a node we never have,
    it is unknown. Getting this backwards is what makes a trend confidently wrong."""
    known_node = NodeSnapshot("node_known", "person",
                              last_activity_at=eval_time - timedelta(days=200))
    unknown_node = NodeSnapshot("node_unknown", "person",
                                last_activity_at=eval_time - timedelta(days=1))
    world = snapshot(eval_time=eval_time, nodes=[known_node, unknown_node],
                     timeline={"node_known": messages(eval_time, days_ago=(200, 210))})

    assert measure(world, "node_known", TOUCHES) == Reading(0, coverage_ready=True)
    assert measure(world, "node_unknown", TOUCHES) == Reading(None, coverage_ready=False)


def test_a_relationship_with_no_reply_has_no_latency(eval_time) -> None:
    """Writing 0 would make the least responsive counterparty in the graph the fastest."""
    node = NodeSnapshot("node_quiet", "person", last_activity_at=eval_time - timedelta(days=2))
    world = snapshot(eval_time=eval_time, nodes=[node],
                     timeline={"node_quiet": messages(eval_time, days_ago=(2, 5, 9),
                                                      direction="out")})
    reading = measure(world, "node_quiet", TrendedMetric.RELATIONSHIP_RESPONSE_LATENCY_HOURS)
    assert reading.value_bp is None and reading.known is False


def test_support_metrics_are_unknown_on_an_org_with_no_desk(eval_time) -> None:
    """`support_situations.py`'s rule, applied one layer up: never assert a queue that is not
    there. Zero open tickets on an org with no ticketing is coverage that does not exist."""
    node = NodeSnapshot("node_acct", "company", last_activity_at=eval_time)
    world = snapshot(eval_time=eval_time, nodes=[node], has_support_desk=False)
    assert measure(world, "node_acct", TrendedMetric.SUPPORT_TICKET_COUNT_28D).known is False

    with_desk = snapshot(eval_time=eval_time, nodes=[node], has_support_desk=True,
                         open_asks={"node_acct": [eval_time - timedelta(days=3)]})
    assert measure(with_desk, "node_acct",
                   TrendedMetric.SUPPORT_TICKET_COUNT_28D) == Reading(1, coverage_ready=True)


# =================================================================================================
# DETERMINISM
# =================================================================================================

def _busy_world(eval_time: datetime) -> OrgSnapshot:
    """Three accounts, their people, deals, commitments and a desk — enough that every probe runs."""
    nodes = [
        NodeSnapshot("node_acct_north", "company", last_activity_at=eval_time - timedelta(days=2),
                     prior_activity_at=eval_time - timedelta(days=9)),
        NodeSnapshot("node_acct_summit", "company", last_activity_at=eval_time - timedelta(days=1),
                     in_active_situation=True),
        NodeSnapshot("node_p_ann", "person", last_activity_at=eval_time - timedelta(days=3)),
        NodeSnapshot("node_p_bo", "person", last_activity_at=eval_time - timedelta(days=40)),
        NodeSnapshot("node_deal_north", "deal", last_activity_at=eval_time - timedelta(days=4)),
    ]
    return snapshot(
        eval_time=eval_time, nodes=nodes,
        timeline={
            "node_acct_north": messages(eval_time, days_ago=(2, 6)) +
                               messages(eval_time, days_ago=(4, 8), direction="out"),
            "node_p_ann": messages(eval_time, days_ago=(3,)) +
                          messages(eval_time, days_ago=(5,), direction="out"),
            "node_p_bo": messages(eval_time, days_ago=(40, 51)),
            "node_deal_north": messages(eval_time, days_ago=(4, 11)),
        },
        facts={
            "node_acct_north": {"deal.stage": ("proposing", eval_time - timedelta(days=21)),
                                "deal.value": (250_000, eval_time - timedelta(days=21)),
                                "deal.currency": ("usd", eval_time - timedelta(days=21)),
                                "commitment.due_at": (
                                    (eval_time - timedelta(days=2)).isoformat(), eval_time)},
            "node_p_ann": {"commitment.due_at": (
                (eval_time + timedelta(days=5)).isoformat(), eval_time)},
        },
        people={"node_acct_north": ["node_p_ann", "node_p_bo"]},
        open_asks={"node_p_ann": [eval_time - timedelta(days=6),
                                  eval_time - timedelta(days=20)]},
        has_support_desk=True)


def test_two_sweeps_at_one_eval_time_produce_identical_points(eval_time) -> None:
    """The property that makes a re-run an overwrite instead of a disagreeing second observation.

    Compared as the full serialised points, not as a count: an ordering that changed between runs
    would still produce the same number of rows and a different table, and the whole of L2.4 is
    built on being able to attribute a change to the business rather than to the machinery.
    """
    world = _busy_world(eval_time)
    first = sample_org(None, org_id=ORG, eval_time=eval_time, history=store_with(),
                       snapshot=world)
    second = sample_org(None, org_id=ORG, eval_time=eval_time, history=store_with(),
                        snapshot=world)

    assert first.points, "the world is not empty; this test proves nothing if nothing was sampled"
    assert [p.model_dump() for p in first.points] == [p.model_dump() for p in second.points]
    assert [p.model_dump() for p in first.gap_points] == [p.model_dump() for p in second.gap_points]
    assert first.by_rule == second.by_rule


def test_the_second_sweep_of_one_period_adds_no_rows(eval_time) -> None:
    """The write-amplification claim, as an assertion.

    `expertise_packages` reached 181 MB over 345 rows through exactly this shape — a store
    appended to on a path that runs constantly. Two sweeps in one period must cost the rows of
    one, and the store's conditional upsert is what makes the second one report zero changes.
    """
    world = _busy_world(eval_time)
    history = store_with()
    first = sample_org(None, org_id=ORG, eval_time=eval_time, history=history, snapshot=world)
    assert first.written > 0

    # Same instant, same graph, fresh policy inputs read back out of the store.
    replayed = snapshot(
        eval_time=eval_time, nodes=list(world.nodes.values()), timeline=world.timeline,
        facts=world.facts, people=world.people_by_company, open_asks=world.open_asks,
        has_support_desk=True,
        last_points={(p.subject_node_id, p.metric):
                     LastPoint(p.observed_at, eval_time, p.value_bp) for p in first.points})
    second = sample_org(None, org_id=ORG, eval_time=eval_time, history=history,
                        snapshot=replayed)
    assert second.written == 0, "a re-sample of one period must overwrite, never append"


def test_no_measure_or_score_is_a_float(eval_time) -> None:
    """Integer basis points only. A `.5` anywhere in a measure path is a reading that cannot be
    compared to itself across a version, which is the one thing a measuring instrument may not
    do."""
    run = sample_org(None, org_id=ORG, eval_time=eval_time, history=store_with(),
                     snapshot=_busy_world(eval_time))
    for point in run.points:
        assert isinstance(point.value_bp, int) and not isinstance(point.value_bp, bool)


def test_the_sampler_reads_no_clock() -> None:
    """`eval_time` is a parameter, and the module must not be able to reach around it.

    A single `datetime.now()` below this seam makes two sweeps of one graph disagree about the
    period they are describing, and the primary key that makes a re-run idempotent stops matching.
    """
    from genios_engine.context.analytic import sampler

    source = inspect.getsource(sampler)
    assert "datetime.now" not in source
    assert "utcnow" not in source
    assert "time.time" not in source


# =================================================================================================
# U3 — THE POINT BUDGET GUARD
# =================================================================================================

def test_a_ten_thousand_node_org_stays_under_the_declared_point_budget(eval_time) -> None:
    """Doc 09's fifth row, and the one that keeps this table from being the last incident again.

    Ten thousand active companies, all eligible, all due. Without a guard that is one sweep
    writing a six-figure insert. The guard caps it, reports the overflow rather than swallowing
    it, and drops a DETERMINISTIC tail so the next sweep picks up exactly where this one stopped.
    """
    nodes = [NodeSnapshot(f"node_{i:05d}", "company",
                          last_activity_at=eval_time - timedelta(days=3))
             for i in range(10_000)]
    world = snapshot(eval_time=eval_time, nodes=nodes,
                     timeline={n.node_id: messages(eval_time, days_ago=(3, 12))
                               for n in nodes})
    budget = PointBudget(limit=5_000)

    run = sample_org(None, org_id=ORG, eval_time=eval_time, history=store_with(),
                     snapshot=world, budget=budget)

    assert run.written == 5_000
    assert run.budget_exhausted and run.dropped_over_budget > 0
    assert len(run.points) == 5_000
    # Deterministic tail: the same run twice drops the same candidates.
    again = sample_org(None, org_id=ORG, eval_time=eval_time, history=store_with(),
                       snapshot=world, budget=PointBudget(limit=5_000))
    assert [p.subject_node_id for p in run.points] == [p.subject_node_id for p in again.points]


def test_the_default_budget_is_stated_and_not_a_magic_number() -> None:
    """The cap is a declared number, so "we exceeded the budget" is a thing an operator can read
    off a run rather than infer from a table size."""
    from genios_engine.context.analytic.sampler import DEFAULT_POINT_BUDGET

    assert PointBudget().limit == DEFAULT_POINT_BUDGET == 20_000


# =================================================================================================
# U2 — THE BACKFILL SAMPLER
# =================================================================================================

def test_backfill_reconstructs_a_series_from_the_event_ledger(eval_time) -> None:
    """An 18-month event backfill becomes 18 months of computable history the moment this runs.

    Every point lands on a boundary `history.periods_between` will actually visit — the same
    function the dense reader walks — which is doc 04's mitigation for "backfill and live sampling
    disagree on period boundaries -> phantom changepoints".
    """
    node = NodeSnapshot("node_p_ann", "person", last_activity_at=eval_time - timedelta(days=3))
    world = snapshot(eval_time=eval_time, nodes=[node],
                     timeline={"node_p_ann": messages(
                         eval_time, days_ago=tuple(range(3, 120, 6)))})
    history = store_with()

    run = backfill_org(None, org_id=ORG, metric=TOUCHES, since=eval_time - timedelta(days=112),
                       until=eval_time, history=history, snapshot=world)

    assert run.written == len(run.points) > 4, "a trend needs four points; a backfill gives many"
    assert all(p.observed_at == period_start(p.observed_at, MetricGrain.WEEK) for p in run.points)
    series = history.read_series(ORG, "node_p_ann", TOUCHES.value,
                                 since=eval_time - timedelta(days=56), until=eval_time)
    assert all(p.known for p in series), "the ledger covers this range; there is no gap in it"


def test_backfill_is_idempotent_over_a_range_it_already_covered(eval_time) -> None:
    """Same primary key as the live path. A second backfill over the same range changes nothing —
    which is what makes it safe to re-run when a metric is added to an org twice."""
    node = NodeSnapshot("node_p_ann", "person", last_activity_at=eval_time - timedelta(days=3))
    world = snapshot(eval_time=eval_time, nodes=[node],
                     timeline={"node_p_ann": messages(eval_time,
                                                      days_ago=tuple(range(3, 90, 6)))})
    history = store_with()
    kwargs = dict(org_id=ORG, metric=TOUCHES, since=eval_time - timedelta(days=84),
                  until=eval_time, history=history, snapshot=world)

    first = backfill_org(None, **kwargs)
    second = backfill_org(None, **kwargs)
    assert first.written > 0 and second.written == 0


def test_backfill_writes_no_point_for_a_period_before_the_series_began(eval_time) -> None:
    """A week before this node's first message is not a gap in its series — the series had not
    started. Writing one would manufacture a coverage hole on every node back to the horizon."""
    node = NodeSnapshot("node_new", "person", last_activity_at=eval_time - timedelta(days=2))
    world = snapshot(eval_time=eval_time, nodes=[node],
                     timeline={"node_new": messages(eval_time, days_ago=(2, 5))})

    run = backfill_org(None, org_id=ORG, metric=TOUCHES, since=eval_time - timedelta(days=180),
                       until=eval_time, history=store_with(), snapshot=world)

    earliest = min(p.observed_at for p in run.points)
    assert earliest >= period_start(eval_time - timedelta(days=6), MetricGrain.WEEK)


# =================================================================================================
# THE WIRING — a REAL sweep, on a REAL database, reaching the sampler
# =================================================================================================

@pytest.mark.pg
def test_the_sweep_writes_history(pg_store) -> None:
    """`context/runner.process_pending` — the sweep both API routes call — reaches the sampler.

    THIS IS THE TEST THAT MATTERS. Layer 1 shipped six units that were green and called by
    nothing; each cost a rework cycle and each was found only by review. Nothing above this line
    would notice if the two lines in `runner.py` were deleted, because every one of them
    constructs the sampler itself.

    The entry point is driven with no pending events on purpose: the sampler must run on a sweep
    that drained nothing, because every metric it takes is measured against a CLOCK — a 28-day
    count, an age, a days-since — so they change because time passed. An org with a quiet inbox
    is exactly the org whose decline is worth surfacing, and gating this pass on "did we ingest
    anything" would freeze its series at the last sweep that happened to have mail.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_sampler_wiring"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    try:
        out = process_pending(org_id=org, store=pg_store, llm=None,
                              crypto_key=get_settings().crypto_key, eval_time=at)
        assert out["processed"] == 0, "no events: this sweep drained nothing"
        assert out["metric_points"] > 0, (
            "the sweep reached no sampler — `sample_org` is not on the real request path")

        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select metric, value_bp, observed_at, sample_reason, unit "
                "from metric_history where org_id=:o order by metric"), {"o": org}).all()
        stored = {r.metric: r for r in rows}
        assert TrendedMetric.DEAL_STAGE_AGE_DAYS.value in stored, (
            "the deal stage fact was seeded 21 days before eval_time and must be measurable")
        aged = stored[TrendedMetric.DEAL_STAGE_AGE_DAYS.value]
        assert aged.value_bp == 21 and aged.unit == "days"
        assert aged.sample_reason == SampleReason.SCHEDULED.value
        assert aged.observed_at == period_start(at, MetricGrain.MONTH)
        # The gap rule on the real path: no `deal.value` fact was seeded, so no row exists —
        # and in particular there is no zero.
        assert TrendedMetric.DEAL_VALUE_MINOR_UNITS.value not in stored

        # A second sweep at the same instant is an OVERWRITE, not a second period.
        before = len(rows)
        process_pending(org_id=org, store=pg_store, llm=None,
                        crypto_key=get_settings().crypto_key, eval_time=at)
        with pg_store.engine.connect() as conn:
            after = conn.execute(text("select count(*) from metric_history where org_id=:o"),
                                 {"o": org}).scalar()
        assert after == before, "two sweeps in one period must not double the table"
    finally:
        _drop_org(pg_store, org)


@pytest.mark.pg
def test_deleting_an_org_erases_its_metric_history(pg_store) -> None:
    """`metric_history` must be erasable with the tenant, on the list that runs with no try/except.

    A table missing from `api/account_routes._ORG_SCOPED_TABLES` breaks org deletion for EVERY
    tenant, not just the one being deleted — the loop has no exception handling by design, so a
    name that is not there fails the whole request. And a history table left behind holds a
    deleted customer's engagement and pipeline readings.
    """
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "metric_history" in _ORG_SCOPED_TABLES

    org = "org_sampler_erasure"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_deal(pg_store, org, at)
    try:
        sample_org(pg_store, org_id=org, eval_time=at)
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select count(*) from metric_history where org_id=:o"),
                                {"o": org}).scalar() > 0
        # Erasure the way the route does it: the table name, in the org-scoped loop.
        with pg_store.engine.begin() as conn:
            for table in _ORG_SCOPED_TABLES:
                conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select count(*) from metric_history where org_id=:o"),
                                {"o": org}).scalar() == 0
    finally:
        _drop_org(pg_store, org)


def _seed_org_with_a_deal(store, org: str, at: datetime) -> None:
    """One org, one company node, one stage fact aged 21 days, one observation to make it active.

    Deliberately the SMALLEST world in which the sampler has something true to say: rule 1 needs
    activity inside 90 days (the observation), and `deal.stage_age_days` needs a stage fact with
    an `occurred_at` (the fact). Nothing else is seeded, so every other metric is an honest gap —
    which is itself part of what the wiring test asserts.
    """
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Sampler Wiring') "
                          "on conflict (id) do nothing"), {"o": org})
        conn.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
            "values ('node_acct_wire', 1, :o, 'company', 'Northwind') "
            "on conflict do nothing"), {"o": org})
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "  value, value_type, status, occurred_at, valid_from) "
            "values ('fv_wire_stage', 'f_wire_stage', :o, 'node_acct_wire', 'deal.stage', "
            "  cast('\"proposing\"' as jsonb), 'string', 'active', :at, :at) "
            "on conflict (fact_version_id) do nothing"),
            {"o": org, "at": at - timedelta(days=21)})
        conn.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "  occurred_at, status) "
            "values ('obs_wire_1', :o, 'node_acct_wire', 'meeting_request', :at, 'active') "
            "on conflict (observation_id) do nothing"),
            {"o": org, "at": at - timedelta(days=3)})


def _drop_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        for table in ("metric_history", "graph_observations", "graph_facts", "graph_nodes"):
            conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


# =================================================================================================
# THE BACKFILL'S WIRING — L2.4.2-U2 on the real sweep, guarded to once per tenant
# =================================================================================================

def _seed_org_with_a_year_of_mail(store, org: str, at: datetime) -> None:
    """One person, one message a week for sixty weeks, half of them inbound.

    Sixty weeks reaches PAST the live sampler's 400-day window on purpose: it is the only shape in
    which "the backfill read its own wider snapshot" is distinguishable from "the backfill shared
    the sampler's", and the two answers differ by five months of history.
    """
    with store.engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, 'Backfill Wiring') "
                          "on conflict (id) do nothing"), {"o": org})
        conn.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, display_name) "
            "values ('node_p_backfill_wiring', 1, :o, 'person', 'Priya') on conflict do nothing"), {"o": org})
        for week in range(60):
            when = at - timedelta(days=7 * week + 1)
            field = "thread.last_inbound" if week % 2 == 0 else "thread.last_outbound"
            ev, fv = f"evt_bf_{week}", f"fv_bf_{week}"
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "  object_type, source_object_id, dedup_key, actor, occurred_at) "
                "values (:e, :o, 'conn_bf', 'gmail', 'message', :e, :e, "
                "  cast('{}' as jsonb), :at) on conflict (event_id) do nothing"),
                {"e": ev, "o": org, "at": when})
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from) "
                "values (:fv, :f, :o, 'node_p_backfill_wiring', :field, cast('true' as jsonb), 'bool', "
                "  'active', :at, :at) on conflict (fact_version_id) do nothing"),
                {"fv": fv, "f": f"f_bf_{week}", "o": org, "field": field, "at": when})
            conn.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, fact_version_id, "
                "  event_id) values (:sr, :o, :fv, :e) on conflict do nothing"),
                {"sr": f"sr_bf_{week}", "o": org, "fv": fv, "e": ev})


@pytest.mark.pg
def test_the_first_sweep_backfills_history_and_no_later_sweep_repeats_it(pg_store) -> None:
    """`backfill_org` had no production caller — L1's defect, repeated in L2. This is its caller.

    WHY IT MATTERS IN NUMBERS, not in principle. BLG-08 needs four points and BLG-13 needs six, so
    at a weekly grain a tenant with no backfill answers `INSUFFICIENT_HISTORY` on every trend for
    its first four to six WEEKS. A seven-day pilot would end before the analytic stratum said one
    thing, and it would read as a quiet product rather than as an uncalled function.

    Driven through `process_pending` — the sweep both sync routes and the upload route call — and
    NOT through `backfill_history_for_drain`, because a test that constructs the thing it is
    checking is wired to cannot notice the two lines in `runner.py` being deleted.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    org = "org_backfill_wiring"
    at = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    _seed_org_with_a_year_of_mail(pg_store, org, at)
    try:
        first = process_pending(org_id=org, store=pg_store, llm=None,
                                crypto_key=get_settings().crypto_key, eval_time=at)
        assert first["history_backfilled"] > 0, (
            "the sweep reached no backfill — `backfill_org` is not on the real request path and "
            "every trend on a new tenant reports INSUFFICIENT_HISTORY for its first month")

        with pg_store.engine.connect() as conn:
            rows = conn.execute(text(
                "select metric, observed_at, sample_reason from metric_history where org_id=:o"),
                {"o": org}).all()
        backfilled = [r for r in rows if r.sample_reason == SampleReason.BACKFILL.value]
        assert backfilled, "rows exist but none is marked as reconstructed"
        # ENOUGH POINTS TO TREND. This is the number the whole unit exists to produce.
        per_metric: dict[str, int] = {}
        for row in backfilled:
            per_metric[row.metric] = per_metric.get(row.metric, 0) + 1
        assert max(per_metric.values()) >= 6, (
            f"the deepest reconstructed series has {max(per_metric.values())} points; BLG-13 "
            "needs six, so nothing would trend on this tenant's first day")
        # PAST THE LIVE WINDOW. A backfill sharing the sampler's 400-day snapshot stops here.
        oldest = min(r.observed_at for r in backfilled)
        assert oldest < at - timedelta(days=400), (
            f"the oldest reconstructed period is {oldest.isoformat()}, inside the live sampler's "
            "400-day window — the backfill is reading the sampler's snapshot, not its own wider "
            "one, and five months of ledger were left on the floor")

        # ONCE PER TENANT. The guard is existence, so the second sweep reconstructs nothing.
        # Counted on the RECONSTRUCTED rows, not on the table: the live sampler legitimately
        # writes this period's readings on every sweep, so a whole-table count would go up by
        # design and an assertion against it would be asserting the sampler is broken.
        before = len(backfilled)
        second = process_pending(org_id=org, store=pg_store, llm=None,
                                 crypto_key=get_settings().crypto_key,
                                 eval_time=at + timedelta(days=1))
        assert second["history_backfilled"] == 0, (
            "the backfill ran twice — an 18-month reconstruction on every drain is a per-sweep "
            "cost the guard exists to remove")
        with pg_store.engine.connect() as conn:
            after = conn.execute(text(
                "select count(*) from metric_history where org_id=:o and sample_reason=:r"),
                {"o": org, "r": SampleReason.BACKFILL.value}).scalar()
        assert after == before, (
            f"reconstructed rows went {before} -> {after}; the guard let a second backfill "
            "through")
    finally:
        with pg_store.engine.begin() as conn:
            for table in ("metric_history", "graph_source_refs", "graph_facts", "source_events",
                          "graph_nodes"):
                conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
            conn.execute(text("delete from orgs where id=:o"), {"o": org})


def test_the_drain_calls_the_backfill_before_the_live_sampler() -> None:
    """Order is load-bearing: the live sampler writes the current period, and `has_points` is an
    EXISTENCE guard — so a backfill placed second would find that row and never run at all."""
    import inspect

    from genios_engine.context.runner import process_pending

    source = inspect.getsource(process_pending)
    backfill_at = source.find("backfill_history_for_drain(store")
    sample_at = source.find("sample_org(store")
    assert backfill_at != -1, (
        "no sweep reaches the backfill — a new tenant's every trend reads INSUFFICIENT_HISTORY "
        "for its first month and `backfill_org` is a function nothing calls")
    assert sample_at != -1
    assert backfill_at < sample_at, (
        "the live sampler now runs first; its write makes `has_points` true, so the backfill "
        "would be skipped on the one sweep it was ever going to run on")
