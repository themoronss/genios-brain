"""H8 · the pilot report, exercised against a SEEDED SCRATCH ORG driven by the REAL drain.

THERE IS NO PILOT TENANT. No org has a live `l2_v2_activation` row on any deployment, so
`scripts/l2_shadow_diff.py --org <pilot> --days 7` has never been run over seven days of a
customer's traffic, and this file does not pretend otherwise. Layer 1's equivalent (G10) is open
for the same reason and says so in `docs/plans/L1_V2_BUILD_RECORD.md` §5.1.

What this file does instead is make every number REAL rather than measured: two scratch orgs are
seeded with the shapes H8 is about, `context/runner.process_pending` — the sweep every sync route
and the upload route call — is run over them, and the report is built from what that sweep wrote.
Nothing below hand-writes a trend fact, a cohort position or a pattern fire; each one is produced
by the pass that produces it in production, which is what makes the receipts the report prints
receipts rather than fixtures.

  * `PILOT` passes every line: three anchor situations, all three matched by the pattern path, a
    DECLINING trend whose series resolves, a cohort position whose population is named, fires
    carrying per-condition evidence, no live card left behind.
  * `DARK` fails four of the five, each for its own reason, and is not activated — a report that
    has only ever been seen passing is a report nobody has seen work.

THE ONE THING THIS PROVES THAT NO PURE TEST COULD. `context/patterns` was a complete package that
nothing on the drain called: `evaluate_org` was reachable only from an HTTP route, so
`pattern_fires` was empty on every tenant and the H8 comparison was structurally impossible.
`test_the_drain_runs_the_pattern_pass_only_for_an_ACTIVATED_tenant` drives the real sweep with the
switch off and then on, which is the only way to see that.

Needs GENIOS_TEST_DATABASE_URL; every real-DB case is `pg`-marked, like the rest of this tree.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import l2_shadow_diff as SD                 # noqa: E402
from scripts._db import UnsafeDatabaseTarget             # noqa: E402
from scripts._gate import read_only_connection           # noqa: E402

from genios_engine.context.analytic.cohort import (COHORT_MEMBERSHIP_TABLE,   # noqa: E402
                                                   SYSTEM_AUTHOR, default_fact_registry,
                                                   define_cohort, save_definitions)
from genios_engine.context.analytic.history import (MetricGrain,              # noqa: E402
                                                    PostgresMetricHistory, SampleReason,
                                                    period_start)
from genios_engine.context.analytic.sampler import (TrendedMetric,            # noqa: E402
                                                    sampler_registry)
from genios_engine.contracts.analytic import MetricPoint, MetricUnit          # noqa: E402
from genios_engine.platform import l2_activation as ACT                       # noqa: E402

#: The sweep instant. Every pass in the drain is driven against it, `context_situations.
#: computed_at` and `pattern_fires.evaluated_at` are both stamped from it, and the report's window
#: is cut around it — so this file reads no clock and neither does anything it drives.
AT = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
SINCE = AT - timedelta(days=7)
UNTIL = AT + timedelta(minutes=1)

PILOT = "org_h8_pilot"
DARK = "org_h8_dark"

METRIC = TrendedMetric.DEAL_STAGE_AGE_DAYS.value

#: The three people the pattern registry's `condition_now_satisfied` fires on, and the anchors the
#: anchor path's correlations are opened against. The SAME three, deliberately: H8's first row asks
#: whether the pattern path covers what anchor-based detection produced, and a fixture whose two
#: paths were about different subjects could not answer it either way.
MATCHED_PEOPLE = ("node_h8_person_0", "node_h8_person_1", "node_h8_person_2")
#: A fourth person nobody's pattern matches — the denominator that makes a 100% real.
UNMATCHED_PERSON = "node_h8_person_3"

_TABLES = ("pattern_fires", "pattern_runs", "pattern_activation", "cards", "signals",
           "situation_absences", "context_situations", "context_correlation_members",
           "context_correlations", "cohort_membership", "cohort_definitions", "metric_history",
           "graph_observations", "graph_facts", "graph_edges", "graph_nodes",
           "l2_v2_activation", "l2_convergence")


# ── seeding ──────────────────────────────────────────────────────────────────────────────────

def _org(conn, org_id: str) -> None:
    """An org row with its NOT-NULL columns discovered rather than listed, so a later migration
    adding one does not turn this file into an error."""
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns where table_name='orgs' "
        "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
    cols, ph, vals = ["id"], [":id"], {"id": org_id}
    for r in reqd:
        cols.append(r.column_name)
        ph.append(f":{r.column_name}")
        dt = r.data_type
        vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                               else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                               else False if dt == "boolean"
                               else "{}" if dt in ("json", "jsonb") else "scratch")
    conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                      "on conflict (id) do nothing"), vals)


def _wipe(engine, org_id: str) -> None:
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})


def _node(conn, org: str, node_id: str, node_type: str, name: str) -> None:
    conn.execute(text(
        "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
        "  display_name, identity_strength, valid_from) "
        "values (:n, 1, :o, :t, :k, :d, 'strong', :at) on conflict do nothing"),
        {"n": node_id, "o": org, "t": node_type, "k": f"{node_type}:{node_id}", "d": name,
         "at": AT - timedelta(days=90)})


def _fact(conn, org: str, node_id: str, field: str, value) -> None:
    """A fact the way the pipeline writes one — a JSON scalar in a JSONB column, not a bare
    string. A fixture that got this wrong would prove the evaluator against a column shape
    production does not have."""
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "  value, value_type, status, authority_rank, occurred_at, valid_from) "
        "values (:fv, :fi, :o, :n, :f, cast(:v as jsonb), 'text', 'active', 2, :at, :at) "
        "on conflict (fact_version_id) do nothing"),
        {"fv": f"fv_{org}_{node_id}_{field}", "fi": f"f_{org}_{node_id}_{field}", "o": org,
         "n": node_id, "f": field, "v": json.dumps(value), "at": AT - timedelta(days=5)})


def _correlation(conn, org: str, anchor: str, *, domain: str = "sales") -> None:
    """One anchor-path group. `refresh_situations` turns every row of this table with evidence
    into exactly one `context_situations` row — that IS the old path."""
    conn.execute(text(
        "insert into context_correlations (correlation_id, org_id, anchor_node_id, anchor_type, "
        "  domain, generation, first_event_at, last_event_at, event_count, status) "
        "values (:c, :o, :n, 'person', :d, 1, :first, :last, 4, 'open') "
        "on conflict (correlation_id) do nothing"),
        {"c": f"corr_{org}_{anchor}", "o": org, "n": anchor, "d": domain,
         "first": AT - timedelta(days=20), "last": AT - timedelta(days=2)})


def _person_the_pattern_matches(conn, org: str, node_id: str) -> None:
    """A person in `condition_now_satisfied`'s situation: a condition the cross-timeline
    correlator recorded as satisfied, and the ball in our court. Both conditions are required,
    so a fire here is the real evaluator agreeing, not a fixture asserting."""
    _node(conn, org, node_id, "person", node_id)
    _fact(conn, org, node_id, "derived.timeline.condition_satisfied",
          {"statement": "we will send it once legal signs off"})
    _fact(conn, org, node_id, "thread.ball_in_court", "us")


def _seed_cohort_and_series(store, org: str, *, declining_node: str) -> str:
    """Eight company accounts in one NAMED cohort, each with a reading, and eleven prior monthly
    readings for one of them that fall — the two analytic shapes H8's middle rows are about.

    Written through the REAL history store rather than by raw insert: `to_row` refuses an
    unregistered metric and a value the column cannot hold, so a fixture that went round it could
    seed a series the sampler itself could never have produced.
    """
    registry = default_fact_registry()
    definition = define_cohort(
        org_id=org, name="Active fintech accounts", node_type="company",
        predicate={"all": [{"fact": "account.industry", "op": "eq", "value": "fintech"}]},
        created_by=SYSTEM_AUTHOR, eval_time=AT, registry=registry)
    nodes = [f"node_h8_acct_{i:02d}" for i in range(8)]
    with store.engine.begin() as conn:
        for index, node in enumerate(nodes):
            _node(conn, org, node, "company", f"Account {index}")
            _fact(conn, org, node, "account.industry", "fintech")
    save_definitions(store.engine, [definition])
    joined = period_start(AT - timedelta(days=21), MetricGrain.WEEK)
    with store.engine.begin() as conn:
        for node in nodes:
            conn.execute(text(
                f"insert into {COHORT_MEMBERSHIP_TABLE} (org_id, cohort_id, node_id, joined_at, "
                "  left_at, miss_streak, evaluated_at) values (:o, :c, :n, :j, null, 0, :j) "
                "on conflict do nothing"),
                {"o": org, "c": definition.cohort_id, "n": node, "j": joined})

    history = PostgresMetricHistory(store.engine, sampler_registry())
    this_month = period_start(AT, MetricGrain.MONTH)
    # One reading each, this period: the POPULATION the percentile is cut from.
    history.put(org, [MetricPoint(subject_node_id=node, metric=METRIC,
                                  value_bp=20 + index * 10, unit=MetricUnit.DAYS,
                                  observed_at=this_month, known=True)
                      for index, node in enumerate(nodes)],
                reason=SampleReason.BACKFILL, sampled_at=AT - timedelta(days=2))
    # Eleven prior months for ONE account, falling: the SERIES the decline is computed from.
    # `sampled_at` 45 days back, not `AT` — the sampler's cadence test reads it, and a fixture
    # stamped with the sweep's own instant would tell the sampler it had just run.
    prior = []
    for back in range(11, 0, -1):
        year, remainder = divmod(this_month.year * 12 + (this_month.month - 1) - back, 12)
        prior.append(MetricPoint(subject_node_id=declining_node, metric=METRIC,
                                 value_bp=30 + back * 10, unit=MetricUnit.DAYS,
                                 observed_at=this_month.replace(year=year, month=remainder + 1),
                                 known=True))
    history.put(org, prior, reason=SampleReason.BACKFILL, sampled_at=AT - timedelta(days=45))
    return definition.cohort_id


def _card(conn, org: str, card_id: str, *, signal_id: str, subject: str) -> None:
    """A founder-visible card and the Layer 4 signal behind it. `expires_at` in the future,
    because an expired card is not something a founder can see and counting it would fail the
    regression row over a card that had already gone."""
    conn.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
        "eval_time) values (:s, :o, 'rule_h8', :n, 50, 'because', :at) on conflict do nothing"),
        {"s": signal_id, "o": org, "n": subject, "at": AT})
    conn.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
        "situation, score, expires_at) values (:c, :s, :o, 'prescriptive', 'today', 'h', 's', 50, "
        ":exp) on conflict do nothing"),
        {"c": card_id, "s": signal_id, "o": org, "exp": AT + timedelta(days=7)})


def _anchor_path(store, org: str) -> int:
    """The OLD path, run at the pilot instant. `context/situations.refresh_situations` is what the
    drain calls; it is invoked here with `eval_time=AT` rather than left to the sweep for one
    reason, and it is a property of the drain rather than of this fixture: the runner refreshes
    situations only on a sweep that DRAINED an event (`if done or affected`), and these orgs have
    no pending mail — a quiet week, which is exactly the week the analytic and pattern passes are
    designed to keep working through. Calling the same function with the same instant every other
    pass is driven against is the honest way to give the report an anchor-path output to compare;
    it is the production writer, not a fixture's idea of one.
    """
    from genios_engine.context.situations import refresh_situations
    return refresh_situations(store, org, eval_time=AT)


def _drain(store, org: str) -> dict:
    """The REAL sweep — what every sync route and the upload route call. Driven with no pending
    events on purpose: every analytic pass is measured against a clock rather than against new
    mail, and the pattern pass reads the graph, so a quiet week is a full sweep."""
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings
    return process_pending(org_id=org, store=store, llm=None,
                           crypto_key=get_settings().crypto_key, eval_time=AT)


# ── fixtures ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def seeded(pg_store):
    """Both orgs, seeded and swept once each. Module-scoped: the drain is the expensive part and
    every assertion below reads the same sweep's output, which is also what makes them consistent
    with one another."""
    engine = pg_store.engine
    with engine.begin() as conn:
        _org(conn, PILOT)
        _org(conn, DARK)
    _wipe(engine, PILOT)
    _wipe(engine, DARK)

    # ── PILOT: everything the gate asks for, produced by the passes that produce it ──────────
    with engine.begin() as conn:
        for node in MATCHED_PEOPLE:
            _person_the_pattern_matches(conn, PILOT, node)
            _correlation(conn, PILOT, node)
        _node(conn, PILOT, UNMATCHED_PERSON, "person", UNMATCHED_PERSON)
        # A card on a subject the pattern path DOES cover: it survives the switch-over, so the
        # regression row is 0 because nothing is lost, not because no card exists.
        _card(conn, PILOT, "card_h8_ok", signal_id="sig_h8_ok", subject=MATCHED_PEOPLE[0])
    _seed_cohort_and_series(pg_store, PILOT, declining_node="node_h8_acct_00")
    ACT.activate(engine, PILOT, switch=ACT.SWITCH_ANALYTIC, by="harsh@genios.ai",
                 notes="H8 pilot", at=AT - timedelta(days=8))
    ACT.activate(engine, PILOT, switch=ACT.SWITCH_PATTERNS, by="harsh@genios.ai",
                 at=AT - timedelta(days=8))

    # ── DARK: an anchor path with nobody watching it ─────────────────────────────────────────
    with engine.begin() as conn:
        _node(conn, DARK, "node_dark_person", "person", "Dark")
        _correlation(conn, DARK, "node_dark_person")
        _card(conn, DARK, "card_dark", signal_id="sig_dark", subject="node_dark_person")

    assert _anchor_path(pg_store, PILOT) == len(MATCHED_PEOPLE)
    assert _anchor_path(pg_store, DARK) == 1

    pilot_out = _drain(pg_store, PILOT)
    dark_out = _drain(pg_store, DARK)
    yield pg_store, pilot_out, dark_out
    _wipe(engine, PILOT)
    _wipe(engine, DARK)


@pytest.fixture
def ro(seeded):
    """The script's OWN read-only connection: every assertion is made through the same
    server-enforced transaction the CLI opens, never a permissive one."""
    store, _pilot, _dark = seeded
    conn = read_only_connection(store.engine)
    yield conn
    conn.close()


@pytest.fixture
def pilot(ro):
    return SD.build_report(ro, org_id=PILOT, since=SINCE, until=UNTIL)


@pytest.fixture
def dark(ro):
    return SD.build_report(ro, org_id=DARK, since=SINCE, until=UNTIL)


def _checks(report) -> dict:
    return {key: ok for key, _observed, _gate, ok in report.checks}


# =================================================================================================
# THE TARGET, AND THE REFUSAL TO CHOOSE ONE
# =================================================================================================

def test_the_script_will_not_choose_a_database_for_you(monkeypatch):
    """`scripts/_db.py` has no fallback to the application's settings and this script must not add
    one: on a developer machine `.env` names the production tenant database."""
    monkeypatch.delenv("GENIOS_TARGET_DATABASE_URL", raising=False)
    with pytest.raises(UnsafeDatabaseTarget) as exc:
        SD.main(["--org", PILOT])
    assert "--database-url" in str(exc.value)


def test_the_window_end_is_an_argument_not_a_clock():
    """Doctrine 4. `--as-of` exists so a gate can be replayed against a past instant and produce
    the same report; without it the clock is read ONCE, in `main`, at the process boundary."""
    parsed = SD.parse_instant("2026-03-02T09:00:00Z")
    assert parsed == AT
    assert SD.parse_instant("2026-03-02T09:00:00").tzinfo is timezone.utc
    with pytest.raises(Exception):
        SD.parse_instant("last tuesday")


@pytest.mark.pg
def test_the_connection_the_report_runs_on_refuses_writes(ro):
    """Read-only at the SERVER, not by review. A gate report that could write is a gate report
    that can be blamed for the state it measured."""
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError) as exc:
        ro.execute(text("insert into l2_v2_activation (org_id, enabled_by) values ('x','y')"))
    assert "read-only" in str(exc.value).lower()


# =================================================================================================
# THE WIRING — the pattern path only exists on the drain because of the activation switch
# =================================================================================================

@pytest.mark.pg
def test_the_drain_runs_the_pattern_pass_only_for_an_ACTIVATED_tenant(seeded):
    """**THE TEST THAT MATTERS FOR THIS WAVE.** `evaluate_org` was reachable only from an HTTP
    route, so `pattern_fires` was empty on every tenant and H8's comparison was impossible.

    Both halves are asserted from the same sweep function: DARK is not activated and its drain
    evaluated nothing, PILOT is and its drain fired. Deleting the runner block, or the switch it
    reads, fails one of these two lines.
    """
    _store, pilot_out, dark_out = seeded
    assert dark_out["patterns_evaluated"] == 0, "an unactivated tenant must not pay for the pass"
    assert dark_out["pattern_fires"] == 0
    assert pilot_out["patterns_evaluated"] >= 6, "every registered pattern gets a run row"
    assert pilot_out["pattern_fires"] == len(MATCHED_PEOPLE)


@pytest.mark.pg
def test_switching_the_pattern_switch_off_stops_the_pass_on_the_next_sweep(seeded):
    """The rollback half, proven through the drain rather than through the table. A migration you
    cannot reverse is a cutover with extra steps."""
    store, _pilot, _dark = seeded
    engine = store.engine
    try:
        assert ACT.deactivate(engine, PILOT, switch=ACT.SWITCH_PATTERNS, by="harsh@genios.ai",
                              at=AT) is True
        assert ACT.is_patterns_activated(engine, PILOT) is False
        assert _drain(store, PILOT)["patterns_evaluated"] == 0
    finally:
        ACT.activate(engine, PILOT, switch=ACT.SWITCH_PATTERNS, by="harsh@genios.ai",
                     at=AT - timedelta(days=8))
        _drain(store, PILOT)


@pytest.mark.pg
def test_the_shadow_pass_writes_nothing_the_anchor_path_owns(seeded):
    """Doc 06: *"do not delete the anchor path in this wave"*. The pattern pass may accumulate
    evidence and may not change what a founder sees.

    Asserted against the pass ITSELF rather than against a whole sweep — `evaluate_org` is the one
    line the runner added, and a whole-drain comparison would also be measuring six other passes
    that legitimately write situations. A byte-for-byte snapshot of every `context_situations`
    column, taken either side of one evaluation, is the exact claim: this pass touches nothing the
    anchor path owns.
    """
    store, _pilot, _dark = seeded
    from genios_engine.context.patterns.store import evaluate_org

    def snapshot() -> list[tuple]:
        with store.engine.connect() as conn:
            return [tuple(r) for r in conn.execute(text(
                "select * from context_situations where org_id = :o order by situation_id"),
                {"o": PILOT})]

    before = snapshot()
    report = evaluate_org(store, PILOT, eval_time=AT)
    assert sum(run.fires for run in report.runs) == len(MATCHED_PEOPLE)
    assert snapshot() == before, "a shadow pass must not add, remove or edit a situation"

    with store.engine.connect() as conn:
        activated = conn.execute(text(
            "select count(*) from pattern_fires where org_id = :o and activated"),
            {"o": PILOT}).scalar()
    assert activated == 0, "no pattern is activated for this tenant, so no fire may reach a card"


# =================================================================================================
# ROW 1 — situations produced by both paths
# =================================================================================================

@pytest.mark.pg
def test_a_week_both_paths_produced_in_full_is_100_percent(pilot):
    assert len(pilot.anchor_situations) == len(MATCHED_PEOPLE)
    assert pilot.both_bp == 10_000
    assert pilot.lost_situations == ()
    assert _checks(pilot)["situations_produced_by_both"] is True


@pytest.mark.pg
def test_a_situation_the_pattern_path_did_not_produce_is_named_not_counted(dark):
    """The breach has to arrive with its subjects: "may the anchor path be deleted" is answered
    "no, and these are the situations that disappear", never with a percentage alone."""
    assert len(dark.anchor_situations) == 1
    assert dark.both_bp == 0
    assert [s[1] for s in dark.lost_situations] == ["node_dark_person"]
    assert _checks(dark)["situations_produced_by_both"] is False


@pytest.mark.pg
def test_an_empty_anchor_path_reports_zero_not_a_hundred_percent(ro):
    """A window with no anchor situations has not been COMPARED. Reporting 100% on an empty
    denominator is how "neither path ran here" reads as "the two agree completely"."""
    empty = SD.build_report(ro, org_id=PILOT, since=AT - timedelta(days=400),
                            until=AT - timedelta(days=300))
    assert empty.anchor_situations == ()
    assert empty.both_bp == 0
    assert _checks(empty)["situations_produced_by_both"] is False
    assert any("nothing to lose" in c for c in empty.caveats)


# =================================================================================================
# ROW 2 — "this is getting worse", WITH THE SERIES
# =================================================================================================

@pytest.mark.pg
def test_a_declining_trend_is_counted_only_when_its_series_can_be_read_back(pilot):
    """Doc 09 does not ask for a count of declines. It asks for a decline *"with the numbers
    behind it"* — so the fact's own pointer is resolved against `metric_history` and the points
    are carried into the report."""
    citable = pilot.citable_trends
    assert citable, "the sweep wrote no DECLINING trend whose series resolves"
    receipt = next(t for t in citable if t.subject_node_id == "node_h8_acct_00")
    assert receipt.metric == METRIC
    assert receipt.trend_confidence_bp > 0
    assert receipt.relative_slope_bp < 0
    assert len(receipt.points) == receipt.claimed_periods >= 6
    values = [value for _at, value, _unit, _cov in receipt.points]
    assert values == sorted(values, reverse=True), "the receipt is the falling series itself"
    assert _checks(pilot)["declining_trend_series_citable"] is True


@pytest.mark.pg
def test_a_decline_whose_series_has_gone_is_NOT_citable(seeded, ro):
    """The failure this row exists to catch. The fact stores a POINTER to its series rather than a
    copy, which is the right shape and also the thing that can rot: a retention pass or a merged
    node leaves a decline nobody can check. That is a claim without a receipt and it scores zero.
    """
    store, _pilot, _dark = seeded
    with store.engine.begin() as conn:
        conn.execute(text("delete from metric_history where org_id = :o and subject_node_id = :n"),
                     {"o": PILOT, "n": "node_h8_acct_00"})
    try:
        report = SD.build_report(ro, org_id=PILOT, since=SINCE, until=UNTIL)
        orphan = next(t for t in report.trends if t.subject_node_id == "node_h8_acct_00")
        assert orphan.points == ()
        assert orphan.citable is False
        assert "NOT CITABLE" in SD.render(report)
    finally:
        _seed_cohort_and_series(store, PILOT, declining_node="node_h8_acct_00")
        _drain(store, PILOT)


@pytest.mark.pg
def test_the_rendered_report_prints_the_series_not_a_count(pilot):
    """"Prints the receipt" is the requirement, so it is asserted on the rendered text an operator
    actually reads."""
    rendered = SD.render(pilot)
    assert "RECEIPT · 'this is getting worse'" in rendered
    receipt = next(t for t in pilot.citable_trends if t.subject_node_id == "node_h8_acct_00")
    for at, value, unit, _cov in receipt.points:
        assert f"{at}  {value} {unit}" in rendered


# =================================================================================================
# ROW 3 — "this is unlike its peers", WITH THE POPULATION
# =================================================================================================

@pytest.mark.pg
def test_a_cohort_position_is_counted_only_when_its_population_is_NAMED(pilot):
    named = pilot.named_cohorts
    assert named, "the sweep wrote no cohort position whose population can be named"
    receipt = named[0]
    # The NAME is asserted as a property, not as a literal: the cohort pass builds its own default
    # populations beside the one seeded here and `most_specific` decides which cohort a node is
    # positioned in. Pinning the seeded name would make this test an assertion about that choice
    # rather than about whether the population can be named at all, which is the gate's subject.
    assert receipt.cohort_name, "a position whose cohort nobody named is not a claim"
    assert receipt.node_type == "company"
    assert receipt.created_by
    assert receipt.population_size >= SD.MIN_COHORT_POPULATION
    assert receipt.members_enumerated == receipt.population_size
    assert all(m.startswith("node_h8_acct_") for m in receipt.member_ids)
    assert receipt.percentile_bp is not None and receipt.band
    assert _checks(pilot)["cohort_position_population_named"] is True


@pytest.mark.pg
def test_a_position_whose_cohort_nobody_defined_is_not_a_named_population(seeded, ro):
    """A percentile with a number beside it and no way to find out who the peers were is not the
    claim doc 09 asks for. Deleting the DEFINITION leaves the positions intact and unciteable."""
    store, _pilot, _dark = seeded
    with store.engine.begin() as conn:
        conn.execute(text("delete from cohort_membership where org_id = :o"), {"o": PILOT})
        conn.execute(text("delete from cohort_definitions where org_id = :o"), {"o": PILOT})
    try:
        report = SD.build_report(ro, org_id=PILOT, since=SINCE, until=UNTIL)
        assert report.cohorts, "the position facts are still there"
        assert report.named_cohorts == ()
        assert _checks(report)["cohort_position_population_named"] is False
        assert "POPULATION NOT NAMED" in SD.render(report)
    finally:
        _seed_cohort_and_series(store, PILOT, declining_node="node_h8_acct_00")
        _drain(store, PILOT)


@pytest.mark.pg
def test_the_rendered_report_names_the_population_and_its_members(pilot):
    rendered = SD.render(pilot)
    assert "RECEIPT · 'this is unlike its peers'" in rendered
    assert pilot.named_cohorts[0].cohort_name in rendered
    assert pilot.named_cohorts[0].member_ids[0] in rendered


# =================================================================================================
# ROW 4 — "these facts hold together", WITH THE PER-CONDITION EVIDENCE
# =================================================================================================

@pytest.mark.pg
def test_a_fire_is_counted_only_when_every_condition_carries_its_own_receipt(pilot):
    """Doc 06's contract with Layer 3 is *"this fired because of these five facts"*. A fire whose
    evidence array is empty, or whose entries carry no recoverable `ref`, is an assertion in a
    fact's typography."""
    evidenced = pilot.evidenced_patterns
    assert len(evidenced) == len(MATCHED_PEOPLE)
    receipt = evidenced[0]
    assert receipt.pattern_id == "condition_now_satisfied"
    assert receipt.activated is False, "shadow, until somebody clears the fire-rate guard"
    assert len(receipt.conditions) >= 2
    fields = {c["field_path"] for c in receipt.conditions}
    assert {"derived.timeline.condition_satisfied", "thread.ball_in_court"} <= fields
    assert all(c["ref"] for c in receipt.conditions)
    assert _checks(pilot)["pattern_evidence_per_condition"] is True


@pytest.mark.pg
def test_a_fire_with_no_evidence_is_refused_even_though_it_is_a_fire(seeded, ro):
    """Read at THIS end as well as written at the other. `matcher._evidenced` already refuses an
    unevidenced satisfaction, but a row written by an older writer, or emptied by a migration, is
    exactly the claim this report must not count."""
    store, _pilot, _dark = seeded
    with store.engine.begin() as conn:
        conn.execute(text("update pattern_fires set evidence = '[]'::jsonb where org_id = :o"),
                     {"o": PILOT})
    try:
        report = SD.build_report(ro, org_id=PILOT, since=SINCE, until=UNTIL)
        assert report.patterns and report.evidenced_patterns == ()
        assert _checks(report)["pattern_evidence_per_condition"] is False
        assert "NO PER-CONDITION EVIDENCE" in SD.render(report)
    finally:
        _drain(store, PILOT)


@pytest.mark.pg
def test_the_rendered_report_prints_each_condition_with_what_satisfied_it(pilot):
    rendered = SD.render(pilot)
    assert "RECEIPT · 'these facts hold together'" in rendered
    assert "thread.ball_in_court" in rendered
    assert "ref=" in rendered


# =================================================================================================
# ROW 5 — founder-visible regressions
# =================================================================================================

@pytest.mark.pg
def test_a_card_whose_subject_the_pattern_path_also_covers_is_not_a_regression(pilot):
    """The regression row must not fire on the existence of a card. PILOT has one, on a subject
    both paths produced — nothing a founder can see is lost by switching over."""
    assert pilot.regressions == ()
    assert _checks(pilot)["founder_visible_regressions"] is True


@pytest.mark.pg
def test_a_card_built_on_a_situation_only_the_anchor_path_found_IS_a_regression(dark):
    """The founder-visible object is the card, and this is the sentence the row exists to say:
    delete anchor-based detection today and this card stops existing."""
    assert [(c, a) for c, _s, a in dark.regressions] == [("card_dark", "node_dark_person")]
    assert _checks(dark)["founder_visible_regressions"] is False
    assert "cards that stop existing on switch-over" in SD.render(dark)


@pytest.mark.pg
def test_an_expired_card_is_not_a_founder_visible_regression(seeded, ro):
    """An expired card is not something a founder can see, and failing the gate over one would
    make the row a measure of the card table's history rather than of what is on screen."""
    store, _pilot, _dark = seeded
    with store.engine.begin() as conn:
        conn.execute(text("update cards set expires_at = :e where org_id = :o"),
                     {"o": DARK, "e": AT - timedelta(days=1)})
    try:
        assert SD.build_report(ro, org_id=DARK, since=SINCE, until=UNTIL).regressions == ()
    finally:
        with store.engine.begin() as conn:
            conn.execute(text("update cards set expires_at = :e where org_id = :o"),
                         {"o": DARK, "e": AT + timedelta(days=7)})


# =================================================================================================
# ACTIVATION IS A PRECONDITION, NOT A METRIC
# =================================================================================================

@pytest.mark.pg
def test_a_tenant_nobody_activated_cannot_pass_even_with_five_green_rows(seeded, ro):
    """"Built but not enabled is not done." A set of zeros from an inactive tenant is not a pass,
    and this is asserted on the tenant whose rows are otherwise all green."""
    store, _pilot, _dark = seeded
    with store.engine.begin() as conn:
        conn.execute(text("delete from l2_v2_activation where org_id = :o"), {"o": PILOT})
    try:
        report = SD.build_report(ro, org_id=PILOT, since=SINCE, until=UNTIL)
        assert all(ok for _k, _o, _g, ok in report.checks), "every measured row still passes"
        assert report.activation.present is False
        assert report.passed is False
        assert any("NO row in l2_v2_activation" in c for c in report.caveats)
    finally:
        ACT.activate(store.engine, PILOT, switch=ACT.SWITCH_ANALYTIC, by="harsh@genios.ai",
                     notes="H8 pilot", at=AT - timedelta(days=8))
        ACT.activate(store.engine, PILOT, switch=ACT.SWITCH_PATTERNS, by="harsh@genios.ai",
                     at=AT - timedelta(days=8))


@pytest.mark.pg
def test_a_switch_off_INSIDE_the_window_is_reported_as_a_shortened_comparison(seeded, ro):
    """G10's lesson, restated for L2: a seven-day window that silently contains a mid-week
    switch-off is a diff nobody can read."""
    store, _pilot, _dark = seeded
    off_at = AT - timedelta(days=3)
    with store.engine.begin() as conn:
        conn.execute(text("update l2_v2_activation set patterns_disabled_at = :d where org_id=:o"),
                     {"o": PILOT, "d": off_at})
    try:
        report = SD.build_report(ro, org_id=PILOT, since=SINCE, until=UNTIL)
        assert report.activation.patterns_live is False and report.activation.present is True
        assert report.passed is False
        assert any("INSIDE this window" in c for c in report.caveats)
    finally:
        with store.engine.begin() as conn:
            conn.execute(text(
                "update l2_v2_activation set patterns_disabled_at = null where org_id = :o"),
                {"o": PILOT})


@pytest.mark.pg
def test_the_whole_pilot_org_passes_the_gate(pilot):
    """Every H8 row, on one tenant, from one real sweep — the verdict line the CLI exits on."""
    assert pilot.passed is True, SD.render(pilot)
    assert dict(pilot.as_dict())["gate"] == "H8"


# =================================================================================================
# HONESTY — what a seeded org cannot measure
# =================================================================================================

@pytest.mark.pg
def test_every_report_states_which_rows_need_a_real_tenant_and_seven_days(pilot):
    """The deliverable is an honest gate, not a green number produced from a fixture that claims
    to be a week of real traffic. Every row H8 measures is named here with why a seeded org can
    only demonstrate it, and the command to run when a tenant exists travels with the report."""
    measured = {key for key, _o, _g, _ok in pilot.checks}
    assert {key for key, _why in SD.NEEDS_REAL_TENANT} == measured, (
        "a row was added to the gate without saying whether a fixture can measure it")
    rendered = SD.render(pilot)
    assert "NOT MEASURED WITHOUT A REAL TENANT AND REAL ELAPSED TIME" in rendered
    assert SD.PILOT_COMMAND in rendered
    assert SD.PILOT_COMMAND in json.dumps(pilot.as_dict())


@pytest.mark.pg
def test_the_cli_exits_zero_on_a_pass_and_one_on_a_breach(seeded, monkeypatch, capsys):
    """The whole entry point, including the exit code CI reads. A gate report that printed FAIL
    and exited 0 would be a gate nothing enforces."""
    import os
    monkeypatch.setenv("GENIOS_TARGET_DATABASE_URL", os.environ["GENIOS_TEST_DATABASE_URL"])
    args = ["--days", "7", "--as-of", (AT + timedelta(minutes=1)).isoformat()]
    assert SD.main(["--org", PILOT, *args]) == 0
    assert "VERDICT: PASS" in capsys.readouterr().out
    assert SD.main(["--org", DARK, *args]) == 1
    assert "VERDICT: FAIL" in capsys.readouterr().out


@pytest.mark.pg
def test_the_json_report_is_parseable_because_the_target_banner_goes_to_stderr(seeded, monkeypatch,
                                                                              capsys):
    """`scripts/_db.py` prints the resolved target before returning — a guard the operator cannot
    see is a guard they cannot correct — and two human-readable lines ahead of a JSON document
    make the document unparseable. Both survive, on separate streams."""
    import os
    monkeypatch.setenv("GENIOS_TARGET_DATABASE_URL", os.environ["GENIOS_TEST_DATABASE_URL"])
    SD.main(["--org", PILOT, "--days", "7", "--json",
             "--as-of", (AT + timedelta(minutes=1)).isoformat()])
    captured = capsys.readouterr()
    assert "[db] target" in captured.err and "[db]" not in captured.out
    body = json.loads(captured.out)
    assert body["passed"] is True
    assert len(body["trend_receipts"][0]["series"]) >= 6, "the receipt travels in the JSON too"
    assert body["cohort_receipts"][0]["member_ids"]
    assert body["pattern_receipts"][0]["conditions"]


def test_the_field_prefixes_this_report_reads_are_the_ones_the_writers_write():
    """The report is a READER, and it spells four names the analytic package owns. Pinned here so
    a rename one side of the seam cannot make a gate silently report zero of everything."""
    from genios_engine.context.analytic.comparator import POSITION_FACT_PREFIX
    from genios_engine.context.analytic.trend import TREND_FACT_PREFIX
    from genios_engine.contracts.analytic import MIN_COHORT_POPULATION, TrendDirection
    assert SD.TREND_FIELD_PREFIX == TREND_FACT_PREFIX
    assert SD.COHORT_FIELD_PREFIX == POSITION_FACT_PREFIX
    assert SD.DECLINING == TrendDirection.DECLINING.value
    assert SD.MIN_COHORT_POPULATION == MIN_COHORT_POPULATION


# =================================================================================================
# H8 GATE REVIEW · the two halves of a receipt the first pass printed as blanks
#
# Both were found by RUNNING the report against the seeded pilot and reading what it said, rather
# than by reading the code: a cohort receipt that printed `ladder p25=None p50=None p75=None`, and
# a pattern block that showed three fires and said nothing at all about the five patterns that
# were evaluated in the same sweep and matched nothing.
# =================================================================================================

@pytest.mark.pg
def test_a_withheld_ladder_prints_its_REASON_and_not_three_blanks(pilot):
    """`comparator.position_fact_value` WITHHOLDS the p25/p50/p75 ladder below
    `MIN_BASELINE_POPULATION` and states why in the row, because — its own words — "a reader that
    found no `p25_bp` could not tell 'this cohort is too small to describe' from 'an older writer
    wrote this row'". The gate report printed the three `None`s and dropped the sentence, which
    re-opened exactly that ambiguity at the one place it is read as evidence.

    The seeded cohort has 8 members and the ladder's floor is 10, so this is the live case.
    """
    named = pilot.named_cohorts
    assert named, "the fixture stopped producing a named cohort position"
    withheld = [c for c in named if c.distribution_withheld]
    assert withheld, ("no cohort receipt carried the withheld reason — either the ladder is now "
                      "publishable at this population or the reason stopped being read")
    assert "10 members" in withheld[0].distribution_withheld

    rendered = SD.render(pilot)
    assert "ladder WITHHELD" in rendered
    assert "ladder p25=None" not in rendered, (
        "three blanks where the fact body carries a sentence: the report is printing the absence "
        "of a disclosure as if it were the absence of data")


@pytest.mark.pg
def test_the_patterns_that_did_NOT_fire_are_named_with_the_condition_that_stopped_them(pilot):
    """Doc 06's SECOND failure mode is a pattern that never fires, and a fire count of zero cannot
    tell "this tenant has no such situation" from "condition 0 reads a field this tenant spells
    differently". `store.record_evaluation` writes a `pattern_runs` row for every pattern
    including the silent ones — the only reason that distinction is recoverable at all — and the
    report ignored it.

    Five of the six shipped patterns are silent on this fixture, in two distinct ways, and the
    report must now separate them: three have no anchor of their type in the graph at all, two
    considered anchors and were stopped by a named condition on a named field.
    """
    silent = {p.pattern_id: p for p in pilot.silent}
    assert len(silent) >= 4, f"expected the quiet patterns to be reported, got {sorted(silent)}"

    stopped = silent["relationship_going_cold"]
    assert stopped.anchors_considered > 0, "this pattern had anchors to look at"
    assert stopped.top_failure_reason == "fact_missing"
    assert stopped.top_failure_field == "account.status", (
        "the report must name the FIELD that stopped it — that is the whole difference between "
        "'no such situation here' and 'this tenant spells it differently'")

    nothing_to_match = [p for p in pilot.silent if p.anchors_considered == 0]
    assert nothing_to_match, "a pattern with no anchor of its type must be distinguishable"

    rendered = SD.render(pilot)
    assert "the patterns that did NOT fire" in rendered
    assert "stopped at condition #0 (fact_missing) on account.status" in rendered
    assert "nothing to match" in rendered


@pytest.mark.pg
def test_a_silent_pattern_is_printed_but_never_scored(pilot):
    """A pattern that matched nothing is a legitimate answer about a tenant, not a breach. Failing
    H8 over one would fail it over a customer who simply has no renewal at risk this week, so the
    silent block is a receipt and never a check row."""
    assert pilot.silent, "the fixture has silent patterns to reason about"
    assert pilot.passed, "silent patterns must not move the verdict"
    keys = {key for key, _observed, _gate, _ok in pilot.checks}
    assert not any("silent" in key for key in keys)
    assert len(keys) == 5, "H8 has five rows and the silent block is not a sixth"
