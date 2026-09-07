"""N-4 · behaviour distillation (CLG-10) — the gate, the label, and the published entry.

Every fixture body here is built by calling Layer 2.4's OWN writer (`compute_trend` →
`trend_fact_value`), never by hand-writing a dict that looks like one. That is deliberate: a test
that invents the shape it reads proves the reader agrees with the test, not with the producer, and
the whole claim of this unit is that it reads what L2.4 actually publishes.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.analytic import MetricPoint, MetricUnit
from genios_engine.contracts.learning import LearningPolicy, LearningTarget
from genios_engine.context.analytic.trend import (
    COVERAGE_FLOOR_BP,
    compute_trend,
    find_changepoint,
    trend_fact_field,
    trend_fact_value,
)
from genios_engine.packs.brains import behavior_distill as bd

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
FIRST_PERIOD = datetime(2026, 1, 5, tzinfo=timezone.utc)
METRIC = "engagement.outbound_count_28d"
POLICY = LearningPolicy(org_id="org_scratch_tests", revision=1)


# ---- fixtures built THROUGH Layer 2.4's own writer --------------------------------------------

def _series(node: str, *, periods: int = 12, start_bp: int = 10_000, step_bp: int = -500,
            metric: str = METRIC, known: tuple[bool, ...] | None = None,
            first_period: datetime = FIRST_PERIOD) -> list[MetricPoint]:
    points = []
    for i in range(periods):
        is_known = True if known is None else known[i]
        points.append(MetricPoint(
            subject_node_id=node, metric=metric,
            value_bp=(start_bp + step_bp * i) if is_known else None,
            unit=MetricUnit.COUNT, observed_at=first_period + timedelta(days=7 * i),
            known=is_known))
    return points


def _fact_body(node: str, **kwargs) -> tuple[str, dict]:
    points = _series(node, **kwargs)
    trend = compute_trend(points)
    changepoint = find_changepoint(points) if trend.direction.value in ("rising", "declining") else None
    return trend_fact_field(kwargs.get("metric", METRIC)), trend_fact_value(trend, changepoint)


def _reading(node: str, **kwargs) -> bd.TrendReading:
    field, body = _fact_body(node, **kwargs)
    series = body["series"]
    return bd.TrendReading(
        fact_version_id=f"fv_trend_{node}_{field}", subject_node_id=node,
        metric=body["metric"], direction=body["direction"],
        relative_slope_bp=body["relative_slope_bp"], streak_periods=body["streak_periods"],
        point_count=body["point_count"], coverage_ratio_bp=body["coverage_ratio_bp"],
        trend_confidence_bp=body["trend_confidence_bp"],
        first_period=datetime.fromisoformat(series["first_period"]),
        last_period=datetime.fromisoformat(series["last_period"]), periods=series["periods"])


def _cohort(nodes=("node_a", "node_b", "node_c"), **kwargs):
    return [_reading(node, **kwargs) for node in nodes]


def _with(reading: bd.TrendReading, **overrides) -> bd.TrendReading:
    """The same reading with one number changed. Slotted dataclass, so fields are named."""
    fields = {name: getattr(reading, name) for name in bd.TrendReading.__dataclass_fields__}
    return bd.TrendReading(**{**fields, **overrides})


# ---- the registry is not free text ------------------------------------------------------------

def test_every_eligible_metric_is_a_registered_l2_metric():
    """A rename in L2.4's enum must break this build, not silently empty the Behavior brain."""
    from genios_engine.context.analytic.sampler import TrendedMetric

    registered = {m.value for m in TrendedMetric}
    assert bd.BEHAVIOR_ELIGIBLE_METRICS <= registered, (
        f"not registered in L2.4: {sorted(bd.BEHAVIOR_ELIGIBLE_METRICS - registered)}")


def test_the_eligible_set_is_the_companys_own_conduct_not_the_worlds():
    """Behaviour is what THIS company does. Inbound volume and ticket demand are not its conduct."""
    for not_ours in ("engagement.inbound_count_28d", "support.ticket_count_28d",
                     "deal.stage_age_days", "deal.value_minor_units"):
        assert not_ours not in bd.BEHAVIOR_ELIGIBLE_METRICS
    assert trend_fact_field(METRIC) in bd.eligible_trend_fields()


# ---- CLG-10, step by step ---------------------------------------------------------------------

def test_a_two_week_trend_is_not_a_pattern():
    """Doc 02's own failure mode: *pattern from 2 weeks of data → 60-day window gate*."""
    short = _cohort(periods=4)                      # four weekly points = 21 days of window
    assert all(r.window_days < bd.BEHAVIOR_MIN_WINDOW_DAYS for r in short)
    patterns, refusals = bd.qualify(short, policy=POLICY)
    assert patterns == ()
    assert {r.reason for r in refusals} == {"window_below_floor"}


def test_a_sixty_day_cohort_across_three_entities_is_a_pattern():
    patterns, refusals = bd.qualify(_cohort(), policy=POLICY)
    assert [r.reason for r in refusals] == []
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.metric == METRIC and pattern.direction == "declining"
    assert pattern.distinct_entities == 3
    assert pattern.window_days >= bd.BEHAVIOR_MIN_WINDOW_DAYS
    assert pattern.observations == 36                # 3 entities x 12 measured points


def test_one_account_alone_is_that_accounts_story_not_a_company_habit():
    """The k-anonymity floor the tenant already declares — applied to Behavior, by CLG-10."""
    patterns, refusals = bd.qualify(_cohort(nodes=("node_a",)), policy=POLICY)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["insufficient_distinct_entities"]


def test_a_refusal_is_never_read_as_a_habit():
    """`insufficient_coverage` is L2.4 saying it cannot see; reading it as flat is the whole fault."""
    holes = (True, False, False, True, False, False, True, False, False, True, False, False)
    readings = _cohort(known=holes)
    assert {r.direction for r in readings} == {"insufficient_coverage"}
    patterns, refusals = bd.qualify(readings, policy=POLICY)
    assert patterns == ()
    assert {r.reason for r in refusals} == {"direction_is_not_a_claim"}


def test_a_holey_series_that_still_names_a_direction_is_refused_on_coverage():
    holey = _with(_reading("node_a"), coverage_ratio_bp=COVERAGE_FLOOR_BP - 1)
    patterns, refusals = bd.qualify([holey], policy=POLICY)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["coverage_below_floor"]


def test_a_weak_cohort_is_held_by_the_tenants_confidence_floor():
    strict = LearningPolicy(org_id="o", revision=1, min_confidence_bp=9_000)
    patterns, refusals = bd.qualify(_cohort(), policy=strict)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["below_confidence_floor"]


def test_the_confidence_is_the_lower_median_so_one_weak_member_cannot_kill_a_cohort():
    readings = _cohort(nodes=("node_a", "node_b", "node_c", "node_d", "node_e"))
    weak = _with(readings[0], trend_confidence_bp=100)
    patterns, _ = bd.qualify([weak] + readings[1:], policy=POLICY)
    assert len(patterns) == 1
    assert patterns[0].confidence_bp == 8_000        # the median, not the minimum


# ---- the model labels; it never computes ------------------------------------------------------

def test_the_deterministic_statement_carries_the_measured_numbers():
    pattern = bd.qualify(_cohort(), policy=POLICY)[0][0]
    statement, source, refusal = bd.label_pattern(pattern)
    assert (source, refusal) == ("deterministic", "")
    assert f"{pattern.distinct_entities} accounts" in statement
    assert f"{pattern.weeks} weeks" in statement
    assert str(pattern.slope_bp) in statement


def test_a_model_template_is_accepted_and_its_numbers_are_ours():
    pattern = bd.qualify(_cohort(), policy=POLICY)[0][0]
    statement, source, refusal = bd.label_pattern(
        pattern, labeler=lambda req: "outbound contact has been {direction} for {weeks} weeks "
                                     "across {entities} accounts.")
    assert (source, refusal) == ("model", "")
    assert f"for {pattern.weeks} weeks" in statement
    assert f"across {pattern.distinct_entities} accounts" in statement


@pytest.mark.parametrize("candidate,reason", [
    ("engagement fell for 12 weeks", "digit_in_template"),
    ("the founder is a bottleneck on {entities} accounts", "judgment_word"),
    ("outbound is {direction} for {quarters} quarters", "unknown_placeholder"),
    ("outbound is {direction} " + "x" * 300, "template_too_long"),
    ("   ", "empty_template"),
    (None, "empty_template"),
    ("outbound is {direction lately", "malformed_placeholder"),   # unbalanced brace
    ("outbound is {series.direction} lately", "malformed_placeholder"),  # attribute access
    ("outbound is {0} lately", "digit_in_template"),               # a positional field IS a digit
])
def test_a_template_that_breaks_a_rule_is_refused(candidate, reason):
    assert bd.check_template(candidate) == reason


def test_a_refused_label_falls_back_and_the_refusal_is_reported():
    pattern = bd.qualify(_cohort(), policy=POLICY)[0][0]
    statement, source, refusal = bd.label_pattern(
        pattern, labeler=lambda req: "engagement dropped 41 times")
    assert source == "deterministic" and refusal == "digit_in_template"
    assert statement == bd.render_statement(bd.DEFAULT_TEMPLATES["declining"],
                                            pattern.template_values())


def test_a_labeler_that_raises_is_a_refusal_not_a_crash():
    pattern = bd.qualify(_cohort(), policy=POLICY)[0][0]

    def _boom(_request):
        raise RuntimeError("model unreachable")

    statement, source, refusal = bd.label_pattern(pattern, labeler=_boom)
    assert source == "deterministic" and refusal == "labeler_error:RuntimeError"
    assert statement


def test_the_prompt_never_shows_the_model_a_number():
    pattern = bd.qualify(_cohort(), policy=POLICY)[0][0]
    prompt = bd.build_label_prompt(bd.LabelRequest(
        metric=pattern.metric, direction=pattern.direction, values=pattern.template_values(),
        default_template=bd.DEFAULT_TEMPLATES[pattern.direction]))
    for measured in (pattern.distinct_entities, pattern.weeks, pattern.slope_bp,
                     pattern.streak_periods, pattern.coverage_bp):
        assert str(measured) not in prompt.replace(str(bd.MAX_TEMPLATE_LENGTH), "")


def test_the_llm_adapter_declines_rather_than_trusting_a_failed_call():
    class _Client:
        def __init__(self, result):
            self.result = result

        def call(self, prompt, *, max_tokens=0):
            return self.result

    class _Result:
        def __init__(self, ok, parsed):
            self.ok, self.parsed = ok, parsed

    request = bd.LabelRequest(metric=METRIC, direction="declining", values={},
                              default_template="x")
    assert bd.llm_labeler(_Client(_Result(False, {"template": "t"})))(request) is None
    assert bd.llm_labeler(_Client(_Result(True, {})))(request) is None
    assert bd.llm_labeler(_Client(_Result(True, {"template": "t"})))(request) == "t"


# ---- the real path: read → gate → propose → the Layer 6 pipeline -------------------------------

@pytest.fixture()
def conn(live_db_url):
    """A real-Postgres transaction, rolled back. The scratch database, never the configured one."""
    if not live_db_url:
        pytest.skip("no database configured")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _seed_trend_fact(c, org, node, **kwargs):
    field, body = _fact_body(node, **kwargs)
    version_id = f"fv_trend_{node}_{field}"
    c.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "value, value_type, status, authority_rank, confidence, occurred_at, valid_from, "
        "visibility_scope) values (:vid, :fid, :o, :n, :f, cast(:v as jsonb), 'json', 'active', "
        "100, 0.9, :now, :now, 'org') on conflict (fact_version_id) do update set "
        "value = excluded.value, valid_to = null, status = 'active'"),
        {"vid": version_id, "fid": f"f_trend_{node}_{field}", "o": org, "n": node, "f": field,
         "v": json.dumps(body, sort_keys=True), "now": NOW})
    return version_id


def _policy(org):
    return LearningPolicy(org_id=org, revision=1)


def test_distill_reads_the_facts_l2_actually_published(conn):
    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    readings = bd.read_trend_readings(c, org_id=org)
    ours = [r for r in readings if r.subject_node_id in ("node_a", "node_b", "node_c")]
    assert len(ours) == 3
    assert {r.direction for r in ours} == {"declining"}
    assert all(r.trend_confidence_bp == 8_000 and r.point_count == 12 for r in ours)


def test_an_ineligible_metric_is_never_even_read(conn):
    c, org = conn
    _seed_trend_fact(c, org, "node_x", metric="engagement.inbound_count_28d")
    assert [r for r in bd.read_trend_readings(c, org_id=org)
            if r.subject_node_id == "node_x"] == []


def test_the_pattern_reaches_the_behavior_brain_through_the_l6_floors(conn):
    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    from genios_engine.feedback.brain_pipeline import admit_proposals

    proposals, refusals = bd.distill(c, org_id=org, policy=_policy(org))
    assert len(proposals) == 3 and all(p.target is LearningTarget.BEHAVIOR for p in proposals)
    counts = admit_proposals(c, proposals, policy=_policy(org), now=NOW)
    assert counts.published == 3 and counts.held == 0 and counts.refused == 0

    rows = c.execute(text(
        "select subject, version, value, learning_id from learned_brain_entries "
        "where org_id=:o and brain='behavior' and active order by subject"),
        {"o": org}).mappings().all()
    assert [r["subject"] for r in rows] == [bd.behavior_subject(METRIC, n)
                                            for n in ("node_a", "node_b", "node_c")]
    assert all(r["version"] == 1 for r in rows)
    value = rows[0]["value"]
    assert value["pattern_statement"].startswith(METRIC)
    assert value["cohort"]["entities"] == 3
    # The receipt: the entry names the learning object that proposed it, and that object exists.
    assert c.execute(text("select count(*) from learning_objects where org_id=:o and "
                          "learning_id=:l and unit=:u"),
                     {"o": org, "l": rows[0]["learning_id"], "u": bd.BEHAVIOR_UNIT}).scalar() == 1
    del refusals


def test_the_same_facts_twice_produce_no_version_noise(conn):
    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    from genios_engine.feedback.brain_pipeline import admit_proposals

    first, _ = bd.distill(c, org_id=org, policy=_policy(org))
    admit_proposals(c, first, policy=_policy(org), now=NOW)
    second, _ = bd.distill(c, org_id=org, policy=_policy(org))
    # Identity is content-addressed and this unit reads no clock, so the second batch IS the first.
    assert [p.learning_id for p in second] == [p.learning_id for p in first]
    counts = admit_proposals(c, second, policy=_policy(org), now=NOW + timedelta(days=7))
    assert counts.unchanged == 3 and counts.published == 0
    assert c.execute(text("select max(version) from learned_brain_entries where org_id=:o "
                          "and brain='behavior'"), {"o": org}).scalar() == 1


def test_a_pattern_that_stops_is_superseded_by_its_own_absence(conn):
    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    from genios_engine.feedback.brain_pipeline import admit_proposals

    first, _ = bd.distill(c, org_id=org, policy=_policy(org))
    admit_proposals(c, first, policy=_policy(org), now=NOW)

    # The behaviour changes: the same three accounts now trend the other way.
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node, start_bp=4_000, step_bp=500)
    second, _ = bd.distill(c, org_id=org, policy=_policy(org))
    admit_proposals(c, second, policy=_policy(org), now=NOW + timedelta(days=7))

    rows = c.execute(text(
        "select subject, version, value from learned_brain_entries where org_id=:o "
        "and brain='behavior' and active order by subject"), {"o": org}).mappings().all()
    assert all(r["version"] == 2 for r in rows), "the claim was not superseded"
    assert all(r["value"]["direction"] == "rising" for r in rows)


def test_a_series_that_went_dark_is_named_rather_than_left_looking_true(conn):
    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    from genios_engine.feedback.brain_pipeline import admit_proposals

    proposals, _ = bd.distill(c, org_id=org, policy=_policy(org))
    admit_proposals(c, proposals, policy=_policy(org), now=NOW)
    c.execute(text("update graph_facts set valid_to = :now, status='superseded' "
                   "where org_id=:o and field like 'derived.trend.%'"), {"o": org, "now": NOW})

    _, refusals = bd.distill(c, org_id=org, policy=_policy(org))
    assert {r.reason for r in refusals} == {"series_went_dark"}


def test_the_expert_brain_cannot_be_written_even_by_hand(conn):
    """Law 3, at the database. Not a policy this module could weaken — a CHECK constraint."""
    c, org = conn
    from sqlalchemy.exc import IntegrityError

    savepoint = c.begin_nested()
    with pytest.raises(IntegrityError, match="learned_brain_no_expert"):
        c.execute(text(
            "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, "
            "value, visibility_scope, visibility) values (:o, 'expert', 's', 1, 'lo_x', "
            "'{}', 'organization', '{}')"), {"o": org})
    savepoint.rollback()


def test_the_weekly_run_is_the_caller_no_test_invented(conn):
    """REACHED FROM A REAL PATH: `run_learning` collects these proposals, not a test harness."""
    import inspect

    from genios_engine.feedback import orchestrator

    source = inspect.getsource(orchestrator.run_learning)
    assert "brain_pipeline_proposals" in source
    assert "expire_leases" in source

    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    collected = orchestrator.run_learning(c, org_id=org, now=NOW)
    assert collected.get("skipped") is None
    published = c.execute(text("select count(*) from learned_brain_entries where org_id=:o "
                               "and brain='behavior' and active"), {"o": org}).scalar()
    assert published == 3, "the weekly run did not publish N-4's patterns"


# ---- the gate rows a default policy cannot reach, and the shapes nobody should trust ------------

def test_an_ineligible_metric_is_refused_by_name_not_only_by_the_query():
    """The SQL filter and the gate are two locks. A reading that arrives another way still fails."""
    reading = _with(_reading("node_a"), metric="engagement.inbound_count_28d")
    patterns, refusals = bd.qualify([reading], policy=POLICY)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["metric_not_behavior_eligible"]


def test_a_tenant_that_narrowed_its_noise_ceiling_is_obeyed():
    """`max_noise_bp` is the tenant's, and a cohort's noise is the holes in its own series."""
    quiet = LearningPolicy(org_id="o", revision=1, max_noise_bp=100)
    readings = [_with(r, coverage_ratio_bp=9_000) for r in _cohort()]
    patterns, refusals = bd.qualify(readings, policy=quiet)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["too_noisy"]
    assert bd.qualify(readings, policy=POLICY)[0], "the default ceiling still admits it"


def test_a_tenant_that_raised_its_observation_floor_is_obeyed():
    demanding = LearningPolicy(org_id="o", revision=1, min_observations=100)
    patterns, refusals = bd.qualify(_cohort(), policy=demanding)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["insufficient_observations"]


def test_a_tenant_that_raised_its_period_floor_is_obeyed():
    demanding = LearningPolicy(org_id="o", revision=1, min_distinct_days=20)
    patterns, refusals = bd.qualify(_cohort(), policy=demanding)
    assert patterns == ()
    assert [r.reason for r in refusals] == ["insufficient_distinct_periods"]


def test_a_fact_body_that_cannot_be_read_as_a_trend_is_skipped_not_guessed_at(conn):
    """Another writer's malformed row is not this module's to repair — and never half-read."""
    c, org = conn
    field = trend_fact_field(METRIC)
    c.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "value, value_type, status, authority_rank, confidence, occurred_at, valid_from, "
        "visibility_scope) values ('fv_trend_junk', 'f_trend_junk', :o, 'node_junk', :f, "
        "cast(:v as jsonb), 'json', 'active', 100, 0.9, :now, :now, 'org')"),
        {"o": org, "f": field, "now": NOW,
         "v": json.dumps({"metric": METRIC, "direction": "declining"})})
    assert [r for r in bd.read_trend_readings(c, org_id=org)
            if r.subject_node_id == "node_junk"] == []


def test_a_flatlined_metric_retracts_its_own_published_pattern(conn):
    """Doc 02's acceptance: *a published pattern whose metric flatlines is superseded*.

    The flat reading does not qualify as a pattern of its own — FLAT is not a claim — so the only
    thing that can supersede the entry is the decay path, through the same floors.
    """
    c, org = conn
    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node)
    from genios_engine.feedback.brain_pipeline import admit_proposals

    first, _ = bd.distill(c, org_id=org, policy=_policy(org))
    admit_proposals(c, first, policy=_policy(org), now=NOW)

    for node in ("node_a", "node_b", "node_c"):
        _seed_trend_fact(c, org, node, step_bp=0)          # the behaviour stops moving
    second, refusals = bd.distill(c, org_id=org, policy=_policy(org))
    assert {r.reason for r in refusals} == {"direction_is_not_a_claim"}
    assert len(second) == 3 and all(p.proposed_value["active"] is False for p in second)
    admit_proposals(c, second, policy=_policy(org), now=NOW + timedelta(days=7))

    rows = c.execute(text(
        "select version, value from learned_brain_entries where org_id=:o and brain='behavior' "
        "and active order by subject"), {"o": org}).mappings().all()
    assert [r["version"] for r in rows] == [2, 2, 2]
    assert all(r["value"]["active"] is False for r in rows)
    assert all("no longer declining" in r["value"]["pattern_statement"] for r in rows)


def test_a_producer_that_raises_costs_its_own_seam_and_nothing_else(conn, monkeypatch):
    """The savepoint IS the isolation. Without it the aborted transaction takes the run with it."""
    from genios_engine.feedback import brain_pipeline

    def _boom(connection, **_kwargs):
        # A DATABASE error, not a Python one: that is what actually poisons a PostgreSQL
        # transaction, and a bare try/except would leave the caller unable to run one more
        # statement — including the rejection row meant to record the isolation.
        connection.execute(text("select * from a_table_that_does_not_exist"))

    monkeypatch.setattr(brain_pipeline.behavior_distill, "distill", _boom)
    c, org = conn
    proposals = brain_pipeline.brain_pipeline_proposals(c, org_id=org, policy=_policy(org),
                                                        now=NOW)
    assert proposals == [], "the other pipeline still ran and simply had nothing to propose"
    rejection = c.execute(text(
        "select seam, reason_code from learning_input_rejections where org_id=:o "
        "order by created_at desc limit 1"), {"o": org}).mappings().first()
    assert rejection is not None, "the isolation left no record"
    assert rejection["seam"] == "brains.behavior_distill"
    assert "a_table_that_does_not_exist" in rejection["reason_code"]
    # And the connection is STILL USABLE — the point of the savepoint.
    assert c.execute(text("select 1")).scalar() == 1
