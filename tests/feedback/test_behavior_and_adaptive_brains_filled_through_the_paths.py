"""J4 · THE BEHAVIOUR AND ADAPTIVE BRAINS ARE FILLED BY A POPULATION, THROUGH THE REAL PATHS.

    pytest tests/feedback/test_behavior_and_adaptive_brains_filled_through_the_paths.py -q
    (needs a scratch Postgres — GENIOS_TEST_DATABASE_URL)

WHAT THIS FILE IS FOR, AND WHY IT IS NOT THE ONES NEXT DOOR
------------------------------------------------------------
`tests/packs/brains/test_behavior_distill.py` and `test_adaptive_lease.py` prove the UNITS: hand
`distill` three seeded trend facts, or `qualify_leases` a hand-built cohort, and the right things
happen. Those are claims about functions. J4's two rows —

    behavior entries published through the L6 floors   >= 1
    adaptive lease from card feedback                  >= 1

— are claims about a PRODUCT: that a founder whose mailbox has been filling for five months ends
up with a Behaviour brain, and that a founder who says "right card, wrong moment" ends up with a
lease that has a real clock on it. Those are different claims, and only the second kind is worth
a gate row. So nothing below constructs a trend fact, a cohort or a `LearningObject`. The
population is correspondence; every number in the brain is computed by Layer 2.4 from that
correspondence, and every write is done by:

    context/runner.process_pending        the drain — backfill, sample, recompute the trends
    feedback/orchestrator.run_learning    the weekly pass — N-4's proposals go through its loop
    POST /v1/intelligence/feedback        the founder's verdict, over HTTP, through the router
      -> feedback/brain_pipeline.lease_from_card_feedback  (called by the ROUTE, not by a test)

`scripts/brain_pilot_seed.py` is the driver, and it is used here rather than re-implemented for
the reason the gate exists at all: the script is the thing an operator runs on a pilot tenant, so
a test that drove the same paths its own way would prove a path nobody uses.

THE FLOORS ARE NOT TOUCHED, AND THAT IS ASSERTED
-------------------------------------------------
`test_the_floors_are_the_tenants_own_and_the_data_cleared_them` reads `learning_policies` back out
of the database after the seed and checks the numbers are the shipped defaults, then checks the
published cohort cleared each one and by how much. A seed that "passed" by writing itself a
friendlier policy would fail there, which is the only version of this gate worth having.

WHAT IS STILL TENANT-DEPENDENT
-------------------------------
Whether a real founder's mailbox trends at all, and whether the pattern this population produces
(outbound reach-out tapering across six accounts) is one that founder cares about. The PATH is
what is proven here; the CONTENT is one seeded company's.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.learned_state import snapshot
from genios_engine.contracts.learning import LearningState
from genios_engine.packs.brains import adaptive_lease as al
from genios_engine.packs.brains import behavior_distill as bd
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_j4_behaviour_pilot"
ORG_EXPIRY = "org_j4_lease_expiry"
ORG_SECOND_PASS = "org_j4_second_pass"

#: The shipped promotion floors, spelled here so the test can prove the seeded tenant is being
#: judged by them. Read back out of `learning_policies` below rather than trusted from the
#: contract's defaults: what governs the run is the ROW, and a seeder could have written it.
SHIPPED_FLOORS = {"min_observations": 3, "min_distinct_days": 2, "min_distinct_entities": 3,
                  "min_confidence_bp": 6_000, "max_noise_bp": 4_000,
                  "max_runtime_ttl_seconds": 7 * 24 * 3600}


# =================================================================================================
# THE POPULATION
# =================================================================================================

@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — J4's brain rows need real Postgres")
    return live_db_url


def _wipe(conn, org_id: str) -> None:
    """Every row this tenant owns, in whatever FK order the schema happens to need.

    Discovered rather than listed, for the same reason the Organization file discovers it: this
    seed writes through capture, L2's analytic stratum, the reasoning audit tables and L6, and a
    hand-maintained table list is how a test starts leaking rows into the next run of itself.
    """
    tables = sorted({r[0] for r in conn.execute(text(
        "select table_name from information_schema.columns "
        "where table_schema = 'public' and column_name = 'org_id'"))})
    for _ in range(4):
        remaining = []
        for table in tables:
            savepoint = conn.begin_nested()
            try:
                conn.execute(text(f'delete from "{table}" where org_id = :o'), {"o": org_id})
                savepoint.commit()
            except Exception:                                  # noqa: BLE001 — an FK, next pass
                savepoint.rollback()
                remaining.append(table)
        tables = remaining
        if not tables:
            break
    conn.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _seed(pg_url: str, org_id: str):
    """Run the operator's own seed script against the scratch database, once, at one instant."""
    from scripts.brain_pilot_seed import seed

    engine = get_engine(pg_url)
    with engine.begin() as conn:
        _wipe(conn, org_id)
    at = datetime.now(timezone.utc)
    report = seed(pg_url, org_id=org_id, at=at)
    return engine, at, report


@pytest.fixture(scope="module")
def pilot():
    """The seeded tenant every read-only test in this file shares. One seed, not eight.

    Module-scoped, so `live_db_url` (function-scoped) cannot be a dependency; the same resolver
    it wraps is called directly, which keeps the target the scratch database and never the
    application's configured one.
    """
    from tests.conftest import live_test_database_url

    url = live_test_database_url()
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — J4's brain rows need real Postgres")
    engine, at, report = _seed(url, ORG)
    yield engine, at, report
    with engine.begin() as conn:
        _wipe(conn, ORG)


@pytest.fixture
def expiring_pilot(pg_url):
    """A tenant of its own, for the test that pushes the clock past a lease's expiry.

    Separate because that test runs a later weekly pass, which retires a lease and re-grants one;
    on the shared tenant every other assertion in this file would then depend on the order pytest
    happened to run them in — which is exactly how a gate starts passing for the wrong reason.
    """
    engine, at, report = _seed(pg_url, ORG_EXPIRY)
    yield engine, at, report
    with engine.begin() as conn:
        _wipe(conn, ORG_EXPIRY)


@pytest.fixture
def second_pass_pilot(pg_url):
    """A tenant of its own, for the same reason: this one runs next week's pass."""
    engine, at, report = _seed(pg_url, ORG_SECOND_PASS)
    yield engine, at, report
    with engine.begin() as conn:
        _wipe(conn, ORG_SECOND_PASS)


def _rows(engine, sql: str, **params):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _brain_rows(engine, org_id: str, brain: str):
    return _rows(engine,
                 "select e.subject, e.version, e.value, e.learning_id, o.unit, o.state "
                 "from learned_brain_entries e left join learning_objects o "
                 "on o.org_id = e.org_id and o.learning_id = e.learning_id "
                 "where e.org_id = :o and e.brain = :b and e.active order by e.subject",
                 o=org_id, b=brain)


def _gate_report(engine, org_id: str, at: datetime):
    from scripts.brain_content_report import build_report

    with engine.connect() as conn:
        return build_report(conn, org_id=org_id, at=at)


# =================================================================================================
# THE BEHAVIOUR HALF
# =================================================================================================

def test_a_founders_correspondence_becomes_a_behaviour_pattern_through_the_weekly_pass(pilot):
    """J4 row 2. The population is email; the entry is what the weekly pass made of it."""
    engine, _at, report = pilot
    assert report.messages > 1_000, "the population is meant to be a mailbox, not three examples"
    assert report.trend_facts > 0, "L2.4 published nothing, so there was nothing to distil"

    entries = _brain_rows(engine, ORG, "behavior")
    assert len(entries) >= 1, "the Behaviour brain is empty after a full weekly pass"
    for row in entries:
        assert row["unit"] == bd.BEHAVIOR_UNIT, "an entry no Layer 3 pipeline proposed"
        assert row["state"] == LearningState.GOVERNED.value
        assert row["value"]["kind"] == "behavior_pattern"
        assert row["subject"].startswith(f"{bd.BEHAVIOR_SUBJECT_PREFIX}:")


def test_every_number_in_the_entry_is_one_layer_2_published(pilot):
    """N-4 READS L2.4's arithmetic. Each entry's reading must be a fact row that still exists."""
    engine, _at, _seed_report = pilot
    entries = _brain_rows(engine, ORG, "behavior")
    facts = {r["fact_version_id"]: r for r in _rows(
        engine, "select fact_version_id, subject_node_id, value from graph_facts "
                "where org_id = :o and status = 'active' and valid_to is null "
                "and field like 'derived.trend.%'", o=ORG)}
    for row in entries:
        reading = row["value"]["reading"]
        fact = facts.get(reading["fact_version_id"])
        assert fact is not None, "the entry cites a trend fact that is not in the table"
        assert fact["subject_node_id"] == reading["subject_node_id"]
        published = fact["value"]
        # Every integer the brain states is the integer the fact carries — not a re-derivation.
        for name in ("relative_slope_bp", "streak_periods", "point_count", "coverage_ratio_bp",
                     "trend_confidence_bp"):
            assert reading[name] == published[name], f"{name} was recomputed, not read"
        assert row["value"]["metric"] == published["metric"]
        assert row["value"]["direction"] == published["direction"]


def test_the_floors_are_the_tenants_own_and_the_data_cleared_them(pilot):
    """The seed may not buy a pass by writing itself a friendlier policy. Read the row back."""
    engine, at, _seed_report = pilot
    policy_row = _rows(engine, "select * from learning_policies where org_id = :o", o=ORG)
    assert len(policy_row) == 1
    stored = policy_row[0]
    for name, shipped in SHIPPED_FLOORS.items():
        assert stored[name] == shipped, f"the seeded tenant's {name} is not the shipped floor"

    from genios_engine.feedback.orchestrator import load_or_seed_policy

    with engine.connect() as conn:
        policy = load_or_seed_policy(conn, ORG, now=at)
        readings = bd.read_trend_readings(conn, org_id=ORG)
    patterns, _refusals = bd.qualify(readings, policy=policy)
    assert patterns, "no cohort cleared CLG-10 on the seeded population"
    pattern = patterns[0]
    assert pattern.observations >= stored["min_observations"]
    assert pattern.distinct_periods >= stored["min_distinct_days"]
    assert pattern.distinct_entities >= stored["min_distinct_entities"]
    assert pattern.confidence_bp >= stored["min_confidence_bp"]
    assert pattern.noise_bp <= stored["max_noise_bp"]
    # CLG-10's own window gate, the one threshold N-4 owns, on real observed time.
    assert pattern.window_days >= bd.BEHAVIOR_MIN_WINDOW_DAYS


def test_the_statement_is_descriptive_and_no_model_wrote_a_number(pilot):
    """Doc 02's failure mode is the model editorialising. With no labeler, nothing can."""
    engine, _at, _seed_report = pilot
    for row in _brain_rows(engine, ORG, "behavior"):
        value = row["value"]
        assert value["statement_source"] == "deterministic"
        statement = value["pattern_statement"]
        words = {w.strip(".,;:!?()[]'\"").lower() for w in statement.split()}
        assert not (words & bd.JUDGMENT_LEXICON), f"the statement editorialises: {statement}"
        # The numbers in the sentence are the cohort's, templated. Spot-check the entity count.
        assert str(value["cohort"]["entities"]) in statement


def test_a_second_pass_on_the_same_facts_mints_no_new_version(second_pass_pilot):
    """A stable habit is not weekly news. The content-addressed identity is what proves it."""
    engine, at, _seed_report = second_pass_pilot
    from genios_engine.feedback.orchestrator import run_learning

    before = {r["subject"]: r["version"]
              for r in _brain_rows(engine, ORG_SECOND_PASS, "behavior")}
    assert before, "nothing was published, so there is no version to hold still"
    with engine.begin() as conn:
        # A week later: a new claimable week, the same facts underneath.
        counts = run_learning(conn, org_id=ORG_SECOND_PASS, now=at + timedelta(days=7))
    assert counts.get("skipped") is None, counts
    after = {r["subject"]: r["version"]
             for r in _brain_rows(engine, ORG_SECOND_PASS, "behavior")}
    assert after == before, "the same measurement produced a second version"
    assert counts["unchanged"] >= len(before)


# =================================================================================================
# THE ADAPTIVE HALF
# =================================================================================================

def test_a_founders_bad_timing_verdict_becomes_a_leased_adaptive_entry(pilot):
    """J4 row 3. The verdicts were posted to `/v1/intelligence/feedback`; this reads the result."""
    engine, at, report = pilot
    assert report.verdicts >= 3, "the founder's cohort is thinner than the tenant's own floor"

    leases = _rows(engine,
                   "select m.subject, m.value, m.active, m.expires_at, m.learning_id, o.unit, "
                   "o.state from temporary_memories m left join learning_objects o "
                   "on o.org_id = m.org_id and o.learning_id = m.learning_id "
                   "where m.org_id = :o and m.active", o=ORG)
    assert len(leases) == 1, f"expected exactly one LIVE lease, got {len(leases)}"
    lease = leases[0]
    assert lease["unit"] == al.LEASE_UNIT, "a lease no Layer 3 pipeline proposed"
    assert lease["state"] == LearningState.GOVERNED.value
    assert lease["value"]["source"] == "card_feedback"
    assert lease["value"]["reason"] == al.LEASE_REASON
    assert lease["subject"] == al.lease_subject(lease["value"]["capability_id"])
    # THE MANDATORY CLOCK, inside the tenant's ceiling.
    assert lease["expires_at"] is not None
    assert lease["expires_at"] <= at + timedelta(
        seconds=SHIPPED_FLOORS["max_runtime_ttl_seconds"] + 60)
    assert lease["expires_at"] > at


def test_the_lease_counts_the_verdicts_the_route_actually_wrote(pilot):
    """The statement's integers are counts of `card_feedback_verdicts` rows, not a model's."""
    engine, _at, _seed_report = pilot
    lease = _rows(engine, "select value from temporary_memories where org_id = :o and active",
                  o=ORG)[0]
    value = lease["value"]
    ledger = _rows(engine,
                   "select cause, reason, actor_id, card_id, occurred_at "
                   "from card_feedback_verdicts where org_id = :o and capability_id = :c",
                   o=ORG, c=value["capability_id"])
    bad_timing = [r for r in ledger
                  if r["cause"] == al.LEASE_CAUSE and r["reason"] == al.LEASE_REASON]
    assert value["verdicts"] == len(ledger)
    assert value["bad_timing"] == len(bad_timing)
    assert value["distinct_actors"] == len({r["actor_id"] for r in bad_timing})
    assert value["distinct_days"] == len({r["occurred_at"].date() for r in bad_timing})
    assert value["share_bp"] == len(bad_timing) * 10_000 // len(ledger)


def test_a_lease_is_readable_by_delivery_until_the_instant_it_is_not(pilot):
    """The reader filters on the clock, so expiry is real before any sweep runs."""
    engine, _at, _seed_report = pilot
    lease = _rows(engine, "select subject, expires_at from temporary_memories "
                          "where org_id = :o and active", o=ORG)[0]
    with engine.connect() as conn:
        before = snapshot(conn, org_id=ORG, consumer="delivery", subject=lease["subject"],
                          now=lease["expires_at"] - timedelta(seconds=1))
        after = snapshot(conn, org_id=ORG, consumer="delivery", subject=lease["subject"],
                         now=lease["expires_at"] + timedelta(seconds=1))
    assert lease["subject"] in before.runtime
    assert after.runtime == {}, "an expired lease is still being handed to delivery"


def test_the_fourth_complaint_supersedes_the_lease_the_third_earned(pilot):
    """ONE ACTIVE LEASE PER SUBJECT — the rule the versioned brains keep, kept here too.

    The founder's third `bad_timing` verdict clears the tenant's floors (three observations
    across three days), so the route grants a lease inside that request. The fourth verdict
    arrives with a larger cohort, which is a different measurement and therefore a different
    proposal — and `contracts/learned_state.snapshot` keys live leases BY SUBJECT, so leaving both
    active would hand a reader two contradictory statements of one preference. The older row is
    retired, and the retirement says `superseded_by_lease`, not `lease_expired`: nothing ran out.
    """
    engine, _at, _seed_report = pilot
    rows = _rows(engine, "select memory_id, learning_id, active, value from temporary_memories "
                         "where org_id = :o order by created_at", o=ORG)
    assert len(rows) == 2, "the seed posted four verdicts; three and four are both leaseable"
    older, newer = rows
    assert older["active"] is False and newer["active"] is True
    assert older["value"]["verdicts"] < newer["value"]["verdicts"]

    archived = _rows(engine, "select from_state, to_state, reason_code, actor, detail "
                             "from learning_transitions where org_id = :o and learning_id = :l "
                             "and to_state = :t", o=ORG, l=older["learning_id"],
                     t=LearningState.ARCHIVED.value)
    assert len(archived) == 1, "a superseded lease left no receipt"
    assert archived[0]["from_state"] == LearningState.TEMPORARY.value
    assert archived[0]["reason_code"] == "superseded_by_lease"
    assert archived[0]["actor"] == "pipeline"
    assert archived[0]["detail"]["superseded_by"] == newer["learning_id"]


def test_the_clock_retires_the_lease_and_the_ledger_says_the_clock_did_it(expiring_pilot):
    """ACROSS THE BOUNDARY, through the weekly pass — the sweep an operator actually runs.

    Three instants, because two would tell a comfortable half-truth:

    * one second BEFORE the expiry the report shows a live lease;
    * one second AFTER it, and before any sweep, `expired_not_cleared = 1` — the number that
      tells an operator the sweep has stopped running, since a reader already ignores the row;
    * the next weekly pass retires it, and the transition names `clock` as the actor, because a
      lease that ran out has to be distinguishable from one a human revoked.

    THE LEASE IS NOT RENEWED, and that is the design rather than a gap. The same four verdicts
    produce the same content-addressed proposal, `persist` answers `unchanged` for an object it
    has already governed, and nothing is published. A lease that re-granted itself every week
    from one week's clicks would be a permanent memory on an instalment plan. New complaints make
    a new cohort, which is a new proposal, which is a new lease — and that path is the one
    `test_the_fourth_complaint_supersedes_the_lease_the_third_earned` walks.
    """
    engine, at, _seed_report = expiring_pilot
    from genios_engine.feedback.orchestrator import run_learning

    lease = _rows(engine, "select memory_id, learning_id, subject, expires_at "
                          "from temporary_memories where org_id = :o and active",
                  o=ORG_EXPIRY)[0]
    expires_at = lease["expires_at"]

    just_before = _gate_report(engine, ORG_EXPIRY, expires_at - timedelta(seconds=1))
    assert just_before.leases.live == 1 and just_before.leases.from_card_feedback == 1
    assert just_before.leases.expired_not_cleared == 0

    just_after = _gate_report(engine, ORG_EXPIRY, expires_at + timedelta(seconds=1))
    assert just_after.leases.live == 0
    assert just_after.leases.expired_not_cleared == 1, "an expired lease nobody names is invisible"
    assert just_after.leases.expired_subjects == (lease["subject"],)

    with engine.begin() as conn:
        counts = run_learning(conn, org_id=ORG_EXPIRY, now=expires_at + timedelta(seconds=1))
    assert counts.get("skipped") is None, counts
    assert counts["expired_leases"] == 1

    retired = _rows(engine, "select active from temporary_memories where org_id = :o "
                            "and memory_id = :m", o=ORG_EXPIRY, m=lease["memory_id"])
    assert retired[0]["active"] is False, "the lease outlived its own clock"

    transitions = _rows(engine,
                        "select from_state, to_state, reason_code, actor, detail "
                        "from learning_transitions where org_id = :o and learning_id = :l "
                        "order by occurred_at", o=ORG_EXPIRY, l=lease["learning_id"])
    expiry = [t for t in transitions if t["to_state"] == LearningState.EXPIRED.value]
    assert len(expiry) == 1, "the retirement left no receipt"
    assert expiry[0]["from_state"] == LearningState.TEMPORARY.value
    assert expiry[0]["reason_code"] == "lease_expired"
    assert expiry[0]["actor"] == "clock", "the clock closed it, and only the ledger can say so"
    assert expiry[0]["detail"]["memory_id"] == lease["memory_id"]

    after = _gate_report(engine, ORG_EXPIRY, expires_at + timedelta(seconds=2))
    assert after.leases.live == 0 and after.leases.expired_not_cleared == 0
    assert not _rows(engine, "select 1 from temporary_memories where org_id = :o and active",
                     o=ORG_EXPIRY), "the same evidence was leased twice"
    # The gate row now reads 0 — correctly, because the brain no longer HOLDS the preference —
    # and the reported history is what tells an operator which kind of zero this is.
    assert after.leases.from_card_feedback == 0
    assert after.leases.from_card_feedback_ever == after.leases.cleared

    # Five weeks out the verdicts have fallen out of `LEASE_WINDOW_DAYS` as well, so there is not
    # even a cohort to read: the tenant is quiet, and stays quiet.
    aged_out = at + timedelta(days=al.LEASE_WINDOW_DAYS + 7)
    with engine.begin() as conn:
        counts = run_learning(conn, org_id=ORG_EXPIRY, now=aged_out)
    assert counts.get("skipped") is None, counts
    assert counts["expired_leases"] == 0, "there was nothing left to retire"
    final = _gate_report(engine, ORG_EXPIRY, aged_out)
    assert final.leases.live == 0 and final.leases.expired_not_cleared == 0


# =================================================================================================
# THE GATE, AND THE DISCIPLINE UNDER IT
# =================================================================================================

def test_the_two_j4_rows_are_earned_on_the_seeded_tenant(pilot):
    """The gate command's own report, on the tenant the script seeded. These two rows PASS."""
    engine, at, _seed_report = pilot
    report = _gate_report(engine, ORG, at)
    rows = {label: (ok, measured) for label, ok, measured in report.checks}

    behavior = next(k for k in rows if k.startswith("behavior entries"))
    adaptive = next(k for k in rows if k.startswith("adaptive leases"))
    assert rows[behavior][0], f"J4 behaviour row: {rows[behavior][1]}"
    assert rows[adaptive][0], f"J4 adaptive row: {rows[adaptive][1]}"
    assert int(rows[behavior][1]) >= 1 and int(rows[adaptive][1]) >= 1


def test_nothing_reached_a_brain_except_through_the_l6_pipeline(pilot):
    """Every entry and every lease names the proposal behind it, or it is a breach."""
    engine, at, _seed_report = pilot
    report = _gate_report(engine, ORG, at)
    assert report.outside_pipeline == 0
    assert report.unattributed == 0
    assert report.brain("behavior").by_provenance.get("distilled", 0) >= 1
    assert report.leases.from_card_feedback == 1


def test_the_expert_brain_is_refused_by_the_database_on_this_tenant(pilot):
    """Law 3, at the database — a CHECK, not a convention this pipeline could weaken."""
    engine, _at, _seed_report = pilot
    from sqlalchemy.exc import IntegrityError

    with engine.connect() as conn:
        with pytest.raises(IntegrityError, match="learned_brain_no_expert"):
            conn.execute(text(
                "insert into learned_brain_entries (org_id, brain, subject, version, "
                "learning_id, value, visibility_scope, visibility) values "
                "(:o, 'expert', 'behavior:anything', 1, 'lo_x', '{}', 'organization', '{}')"),
                {"o": ORG})
        conn.rollback()
    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from learned_brain_entries where org_id = :o "
                                 "and brain = 'expert'"), {"o": ORG}).scalar() == 0


def test_the_seed_script_never_calls_the_pipeline_itself():
    """The ROUTE is the caller. A script that called `lease_from_card_feedback` itself would
    prove the function works and nothing about whether a founder's click reaches it.

    Read off the AST rather than off the text, because the script's docstring NAMES the function
    it must not call — a substring check would be satisfied by deleting a sentence of prose.
    """
    import ast
    import inspect

    from scripts import brain_pilot_seed

    tree = ast.parse(inspect.getsource(brain_pilot_seed))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    called = {node.func.attr if isinstance(node.func, ast.Attribute) else
              getattr(node.func, "id", "") for node in ast.walk(tree)
              if isinstance(node, ast.Call)}

    assert "genios_engine.feedback.brain_pipeline" not in imported
    assert "genios_engine.feedback.publisher" not in imported
    assert not any(str(m or "").startswith("genios_engine.packs.brains") for m in imported)
    assert not called & {"lease_from_card_feedback", "admit_proposals", "publish", "distill",
                         "lease_proposals", "expire_leases", "govern", "persist"}

    # What it DOES drive: the drain, the weekly pass, and the founder's verdict over HTTP.
    assert "genios_engine.feedback.orchestrator" in imported
    assert "genios_engine.context.runner" in imported
    assert {"run_learning", "process_pending"} <= called
    assert "/v1/intelligence/feedback" in inspect.getsource(brain_pilot_seed)
