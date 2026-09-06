"""H6 · L-4 — the drain loop guards, and the derivation graph's acyclicity.

Doc 09 invokes gate H6's loop half as:

    pytest tests/context/test_convergence.py tests/context/test_coverage_epoch.py \
           tests/context/analytic/test_gap_reason.py -q
    python scripts/derivation_dag_check.py

The two gate rows this file owns:

    | derivation graph is acyclic | **passes** — CI-enforced |
    | drains exceeding `MAX_PASSES` | **0** over 7 days |

**WHAT THE GUARD ACTUALLY IS.** Doc 13's L-4 cycle — event joins a situation, member set changes,
importance recomputed, lifecycle re-derived, observation emitted, observations feed correlation,
round again — is bounded by a fixpoint with a convergence check. Doc 13's own L-1 row says the
drain runs "one pass per sweep", so the fixpoint iterates ACROSS sweeps: the hash of (situations,
memberships, lifecycle states) at the end of one sweep is compared with the hash at the start of
the next, and a sweep that drained NOTHING and still moved the state is a turn of the loop.

**THE MUTATION CHECK.** Add `importance_bp` to `runner._CONVERGENCE_HASH_SQL` and
`test_the_state_hash_ignores_scores_because_they_move_with_the_clock` fails — which is the
difference between an alert that fires on a genuine derivation cycle and one that fires on every
tenant in the system within three sweeps. Reset `passes` unconditionally instead of only on
convergence or new input, and `test_three_no_input_sweeps_that_keep_moving_raise_the_alert` fails.
Count a sweep that drained events as a pass, and
`test_draining_new_events_is_not_a_turn_of_the_fixpoint` fails. In the DAG check, make a producer
OWN the families it selects on rather than consume them, and
`test_the_cycle_search_finds_a_two_module_cycle_a_reader_could_not_see` fails — that is the exact
rule that decides whether "the anomaly detector started reading the trend" appears as an edge or
disappears into ownership.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.runner import (MAX_PASSES, MAX_UNCONVERGED_REPORTED,
                                          _convergence_state_hash, _record_convergence)

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _ROOT / "genios_engine" / "context" / "runner.py"
_SCRIPT = _ROOT / "scripts" / "derivation_dag_check.py"

EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


def _dag_module():
    """The CI script, imported as a module so its parts can be tested in isolation.

    Imported by path rather than added to `sys.path`: `scripts/` is not a package, and putting it
    on the path for the whole session is how a test file starts shadowing a real module.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("derivation_dag_check", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# =================================================================================================
# THE CONSTANTS, AND WHAT THE STATE IS
# =================================================================================================

def test_max_passes_is_three() -> None:
    """Doc 13 fixes the bound at three. Named in code so a reviewer can argue with it, rather than
    spelled at the comparison."""
    assert MAX_PASSES == 3


def test_the_state_hash_covers_situations_memberships_and_lifecycle_and_nothing_else() -> None:
    """Doc 13 hashes exactly three things. A source assertion, because what is IN the hash is the
    whole meaning of "converged" and it is the one thing a reader cannot infer from behaviour."""
    source = _RUNNER.read_text()
    statement = source[source.index("_CONVERGENCE_HASH_SQL"):source.index("def _convergence_state")]

    assert "context_situations" in statement
    assert "context_correlation_members" in statement
    assert "context_node_lifecycle" in statement
    assert "importance_bp" not in statement, (
        "importance is composed against eval_time and drifts on a quiet org — hashing it reports "
        "every tenant as non-convergent within three sweeps, and an alert that fires on everyone "
        "fires on no one")
    assert "confidence_" not in statement and "computed_at" not in statement
    assert "order by" in statement, (
        "string_agg without an order is not deterministic across plans, and a hash that changed "
        "with the planner's mood would report convergence as failure on a big enough tenant")


def test_the_guard_reads_no_clock() -> None:
    """Doctrine 4. `sweep_at` is passed into the bookkeeping; the timestamps written are the
    sweep's own instant, so a replayed sweep writes the same row."""
    source = _RUNNER.read_text()
    block = source[source.index("def _record_convergence"):source.index("def _safe_process_one")]

    assert "now()" not in block and "datetime.now" not in block and "utcnow" not in block
    assert "sweep_at" in block


# =================================================================================================
# THE FIXPOINT — one row per org, and what moves it
# =================================================================================================

ORG = "org_convergence_guard"


def _reset(store, org: str = ORG) -> None:
    with store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'convergence guard') "
                       "on conflict (id) do nothing"), {"o": org})
        for table in ("l2_convergence", "context_situations", "context_correlation_members",
                      "context_node_lifecycle"):
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": org})


def _cleanup(store, org: str = ORG) -> None:
    with store.engine.begin() as c:
        for table in ("l2_convergence", "context_situations", "context_correlation_members",
                      "context_node_lifecycle", "source_events", "graph_facts", "graph_nodes"):
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": org})
        c.execute(text("delete from orgs where id=:o"), {"o": org})


def _situation(store, org: str, situation_id: str, *, status: str = "active",
               anchor: str = "node_a", importance: int | None = None) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, "
            "anchor_node_id, situation_type, domain, status) "
            "values (:s, :o, :c, :a, 'deal', 'sales', :st) "
            "on conflict (situation_id) do update set status = excluded.status, "
            "anchor_node_id = excluded.anchor_node_id"),
            {"s": situation_id, "o": org, "c": f"corr_{situation_id}", "a": anchor, "st": status})
        if importance is not None:
            c.execute(text("update context_situations set importance_bp = :b "
                           "where situation_id = :s"), {"b": importance, "s": situation_id})


@pytest.mark.pg
def test_the_state_hash_is_stable_when_nothing_moves(pg_store) -> None:
    """The base case, and the one the whole guard rests on: reading an unchanged graph twice must
    produce the same fingerprint, or every sweep on every tenant looks like a turn of the loop."""
    _reset(pg_store)
    try:
        _situation(pg_store, ORG, "sit_1")
        assert _convergence_state_hash(pg_store, ORG) == _convergence_state_hash(pg_store, ORG)
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_the_state_hash_ignores_scores_because_they_move_with_the_clock(pg_store) -> None:
    """**The mutation this file exists to catch.** Importance is composed against `eval_time`, so
    on a perfectly quiet org it drifts every sweep. A hash that included it would report every
    tenant as non-convergent within three sweeps, and doc 13's alert would be worthless on the day
    it mattered."""
    _reset(pg_store)
    try:
        _situation(pg_store, ORG, "sit_1", importance=4000)
        before = _convergence_state_hash(pg_store, ORG)
        _situation(pg_store, ORG, "sit_1", importance=9100)

        assert _convergence_state_hash(pg_store, ORG) == before
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_the_state_hash_moves_when_a_lifecycle_state_moves(pg_store) -> None:
    """The other direction, which is what makes the test above an assertion rather than a
    tautology: the three things doc 13 names DO move the fingerprint."""
    _reset(pg_store)
    try:
        _situation(pg_store, ORG, "sit_1", status="active")
        active = _convergence_state_hash(pg_store, ORG)
        _situation(pg_store, ORG, "sit_1", status="resolved")
        resolved = _convergence_state_hash(pg_store, ORG)
        assert resolved != active

        with pg_store.engine.begin() as c:
            c.execute(text("insert into context_node_lifecycle (org_id, node_id, lifecycle) "
                           "values (:o, 'node_a', 'dormant')"), {"o": ORG})
        assert _convergence_state_hash(pg_store, ORG) != resolved
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_a_sweep_that_changes_nothing_converges_and_holds_the_counter_at_zero(pg_store) -> None:
    _reset(pg_store)
    try:
        _situation(pg_store, ORG, "sit_1")
        held = _convergence_state_hash(pg_store, ORG)
        entry = _record_convergence(pg_store, ORG, before=held, after=held, drained=False,
                                    sweep_at=EVAL_TIME)

        assert entry == {"checked": True, "converged": True, "passes": 0, "exceeded": False,
                         "state_hash": held}
        with pg_store.engine.connect() as c:
            row = c.execute(text("select passes, exceeded_at from l2_convergence where org_id=:o"),
                            {"o": ORG}).first()
        assert row.passes == 0 and row.exceeded_at is None
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_draining_new_events_is_not_a_turn_of_the_fixpoint(pg_store) -> None:
    """New evidence is SUPPOSED to move the graph. Counting it would make the guard a measure of
    how busy a tenant is rather than of whether their derivations settle — and the busiest tenant
    would be the one it alerted on."""
    _reset(pg_store)
    try:
        for _ in range(MAX_PASSES + 2):
            entry = _record_convergence(pg_store, ORG, before="a", after="b", drained=True,
                                        sweep_at=EVAL_TIME)
            assert entry["passes"] == 0 and entry["exceeded"] is False
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_three_no_input_sweeps_that_keep_moving_raise_the_alert(pg_store) -> None:
    """The gate row: *drains exceeding `MAX_PASSES` — 0 over 7 days.* A tenant whose state keeps
    moving with no new input has a real derivation cycle, and doc 13 is explicit that this is "an
    alert, not a log line"."""
    _reset(pg_store)
    try:
        _situation(pg_store, ORG, "sit_moving")
        for turn in range(1, MAX_PASSES):
            entry = _record_convergence(pg_store, ORG, before=f"h{turn}", after=f"h{turn + 1}",
                                        drained=False, sweep_at=EVAL_TIME)
            assert entry["passes"] == turn
            assert entry["exceeded"] is False, "the bound is three, not one"

        entry = _record_convergence(pg_store, ORG, before="h3", after="h4", drained=False,
                                    sweep_at=EVAL_TIME)
        assert entry["passes"] == MAX_PASSES
        assert entry["exceeded"] is True

        with pg_store.engine.connect() as c:
            row = c.execute(text("select passes, exceeded_at, detail from l2_convergence "
                                 "where org_id=:o"), {"o": ORG}).first()
        assert row.exceeded_at is not None
        assert row.detail["state_hash_before"] == "h3"
        assert row.detail["state_hash_after"] == "h4"
        assert row.detail["max_passes"] == MAX_PASSES
        assert "situations_still_changing" in row.detail, (
            "doc 13: record the org, the situations still changing, and the state hashes")
        assert len(row.detail["situations_still_changing"]) <= MAX_UNCONVERGED_REPORTED
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_converging_again_clears_a_standing_breach(pg_store) -> None:
    """`exceeded_at` must always mean "still breaching", never "breached once, in 2024" — otherwise
    the operator's query returns a tenant that fixed itself six months ago."""
    _reset(pg_store)
    try:
        for turn in range(MAX_PASSES):
            _record_convergence(pg_store, ORG, before=f"h{turn}", after=f"h{turn + 1}",
                                drained=False, sweep_at=EVAL_TIME)
        entry = _record_convergence(pg_store, ORG, before="settled", after="settled",
                                    drained=False, sweep_at=EVAL_TIME)

        assert entry["converged"] is True and entry["exceeded"] is False
        with pg_store.engine.connect() as c:
            row = c.execute(text("select passes, exceeded_at, detail from l2_convergence "
                                 "where org_id=:o"), {"o": ORG}).first()
        assert row.passes == 0 and row.exceeded_at is None and row.detail == {}
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_an_unreadable_state_leaves_the_counter_exactly_as_it_was(pg_store) -> None:
    """A guard that could not read the graph this sweep must neither manufacture a breach nor
    silently clear one. `checked: False` is an honest answer; a reset would be a lie."""
    _reset(pg_store)
    try:
        _record_convergence(pg_store, ORG, before="a", after="b", drained=False,
                            sweep_at=EVAL_TIME)
        entry = _record_convergence(pg_store, ORG, before=None, after="b", drained=False,
                                    sweep_at=EVAL_TIME)

        assert entry == {"checked": False}
        with pg_store.engine.connect() as c:
            passes = c.execute(text("select passes from l2_convergence where org_id=:o"),
                               {"o": ORG}).scalar()
        assert passes == 1, "the probe failed; the counter is not evidence of anything either way"
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_one_row_per_org_however_many_sweeps_run(pg_store) -> None:
    """The bound. `expertise_packages` reached 181 MB across 345 rows by appending once per run;
    this ledger is written on EVERY drain, so it is that shape unless the primary key holds."""
    _reset(pg_store)
    try:
        for turn in range(12):
            _record_convergence(pg_store, ORG, before=f"a{turn}", after=f"a{turn + 1}",
                                drained=turn % 2 == 0, sweep_at=EVAL_TIME)
        with pg_store.engine.connect() as c:
            assert c.execute(text("select count(*) from l2_convergence where org_id=:o"),
                             {"o": ORG}).scalar() == 1
    finally:
        _cleanup(pg_store)


# =================================================================================================
# THE WIRING — the guard runs on the sweep every route already calls
# =================================================================================================

def test_the_drain_takes_the_hash_before_it_writes_and_after_every_pass() -> None:
    """Position is the whole design. A "before" taken after the drain would compare a sweep against
    itself; an "after" taken before the composer would call a sweep converged that had not finished
    changing the graph."""
    source = _RUNNER.read_text()

    before = source.index("state_hash_before = _convergence_state_hash")
    after = source.index("_record_convergence(store, org_id, before=state_hash_before")
    assert before < source.index("while done < max_total"), "the fingerprint precedes the drain"
    assert after > source.index("refresh_situation_importance(store"), (
        "the second fingerprint must follow every pass that can move a situation")


@pytest.mark.pg
def test_the_sweep_reports_its_convergence(pg_store) -> None:
    """**THIS IS THE TEST THAT MATTERS.** `context/runner.process_pending` — the sweep both API
    sync routes and the upload route call — runs the guard and carries the answer out.

    Two sweeps with no events at one instant: the first records the org's fingerprint, the second
    finds it unchanged and reports `converged`. Delete the two lines in `runner.py` and this fails
    and nothing else here does.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    _reset(pg_store)
    try:
        _situation(pg_store, ORG, "sit_wire")
        key = get_settings().crypto_key
        process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key, eval_time=EVAL_TIME)
        out = process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key,
                              eval_time=EVAL_TIME)

        assert out["convergence"]["checked"] is True, (
            "the sweep reached no convergence guard — it is not on the real request path")
        assert out["convergence"]["converged"] is True
        assert out["convergence"]["passes"] == 0
        assert out["convergence"]["exceeded"] is False

        with pg_store.engine.connect() as c:
            row = c.execute(text("select state_hash, last_pass_at from l2_convergence "
                                 "where org_id=:o"), {"o": ORG}).first()
        assert row is not None
        assert row.last_pass_at == EVAL_TIME, "the sweep's own instant, never a second clock"
    finally:
        _cleanup(pg_store)


@pytest.mark.pg
def test_the_sweep_measures_what_the_SWEEP_did_not_what_happened_between_sweeps(pg_store) -> None:
    """The measurement boundary, and it is subtler than it looks.

    The "before" fingerprint is taken at the top of `process_pending`, so a change somebody else
    made while the drain was not running is already in it and the sweep correctly reports
    CONVERGED — it did not move anything. Taking the "before" from the previous sweep's stored hash
    instead would count every edit made by a route, a migration or another worker as a turn of
    Layer 2's own fixpoint, and the alert would fire on tenants whose derivations settle perfectly.

    A pass is a sweep that moved the state ITSELF with nothing to ingest. That arithmetic is proven
    on `_record_convergence` above, where the three inputs can be stated instead of arranged.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    _reset(pg_store)
    try:
        key = get_settings().crypto_key
        _situation(pg_store, ORG, "sit_one")
        process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key, eval_time=EVAL_TIME)

        _situation(pg_store, ORG, "sit_two", anchor="node_b")     # not the drain's doing
        out = process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key,
                              eval_time=EVAL_TIME)

        assert out["processed"] == 0
        assert out["convergence"]["converged"] is True
        assert out["convergence"]["passes"] == 0
        with pg_store.engine.connect() as c:
            stored = c.execute(text("select state_hash from l2_convergence where org_id=:o"),
                               {"o": ORG}).scalar()
        assert stored == _convergence_state_hash(pg_store, ORG), (
            "the ledger holds the fingerprint of the graph as the sweep left it")
    finally:
        _cleanup(pg_store)


# =================================================================================================
# THE DERIVATION DAG — CI-enforced, and it has to have teeth
# =================================================================================================

def test_the_dag_check_passes_on_this_tree() -> None:
    """H6's row: *derivation graph is acyclic — passes, CI-enforced.* Run as a subprocess, exactly
    as CI runs it, so the exit code being asserted is the exit code CI reads."""
    result = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True,
                            cwd=str(_ROOT))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "check A · PASS" in result.stdout
    assert "check B · PASS" in result.stdout


def test_the_dag_check_reads_nothing_but_source_and_holds_no_clock() -> None:
    """Read-only and clock-free, both required of a CI gate: a check that could write would be a
    migration nobody reviewed, and one that read a clock would pass on Tuesdays."""
    source = _SCRIPT.read_text()

    assert "datetime" not in source and "now()" not in source
    assert "create_engine" not in source and "sqlalchemy" not in source
    assert "GENIOS_DATABASE_URL" not in source


def test_the_cycle_search_answers_on_a_graph_a_reader_can_check_by_hand() -> None:
    """The search itself, on graphs small enough to verify by eye — so a failure below is a failure
    of the EXTRACTION rather than of the algorithm."""
    find_cycle = _dag_module().find_cycle

    assert find_cycle({"a": {"b"}, "b": {"c"}, "c": set()}) is None
    assert find_cycle({"a": {"b"}, "b": {"a"}}) is not None
    assert find_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}) is not None
    assert find_cycle({}) is None
    long_chain = {f"n{i}": {f"n{i + 1}"} for i in range(200)}
    assert find_cycle({**long_chain, "n200": set()}) is None, "no recursion limit in the walk"


def test_a_producer_that_selects_on_a_family_is_reading_it_not_owning_it() -> None:
    """**The rule the whole check turns on.** A module that publishes facts and also QUERIES another
    family is a consumer of that family. Call it an owner instead and the edge disappears into
    ownership — which is exactly what would happen the day the anomaly detector starts reading the
    trend, and the cycle would vanish rather than fail."""
    dag = _dag_module()
    trend = dag.Module(_ROOT / "genios_engine" / "context" / "analytic" / "trend.py")

    assert "derived.trend" in trend.owns
    assert trend.consumes == set(), "trend.py queries nobody else's family today"


def test_the_cycle_search_finds_a_two_module_cycle_a_reader_could_not_see(tmp_path) -> None:
    """The end-to-end teeth, on two fixture modules: one publishes `derived.alpha` and selects on
    `derived.beta`, the other does the reverse. Neither file shows the cycle on its own — which is
    the only kind of cycle this check is for."""
    dag = _dag_module()
    (tmp_path / "alpha.py").write_text(
        'from genios_engine.context.analytic.publish import publish_derived_fact\n'
        'PREFIX = "derived.alpha."\n'
        'READ = "select value from graph_facts where field like \'derived.beta.%\'"\n')
    (tmp_path / "beta.py").write_text(
        'from genios_engine.context.analytic.publish import publish_derived_fact\n'
        'PREFIX = "derived.beta."\n'
        'READ = "select value from graph_facts where field like \'derived.alpha.%\'"\n')
    modules = {m.dotted: m for m in (dag.Module(tmp_path / "alpha.py"),
                                     dag.Module(tmp_path / "beta.py"))}
    edges, _self_edges, _leaves = dag.build_graph(modules)
    cycle = dag.find_cycle(edges)

    assert cycle is not None, edges
    assert set(cycle) == {"derived.alpha", "derived.beta"}


def test_an_fstring_table_name_is_still_a_read(tmp_path) -> None:
    """`cohort.py` and `peer_baseline.py` write `f"insert into {TABLE} ..."`, and `trend.py` reads
    `f"... from {HISTORY_TABLE} ..."` with the constant IMPORTED. An extractor blind to either
    reports those modules as deriving nothing and reading nothing, and the graph goes quietly
    empty — which passes."""
    dag = _dag_module()
    trend = dag.Module(_ROOT / "genios_engine" / "context" / "analytic" / "trend.py",
                       {"HISTORY_TABLE": "metric_history"})

    assert "metric_history" in trend.read_tables


def test_the_check_refuses_an_empty_graph_rather_than_passing_it() -> None:
    """A gate that reports "acyclic" because it found nothing to check is worse than no gate. The
    real tree must produce a graph with real content, and the script fails closed if it does not."""
    dag = _dag_module()
    modules = dag.load_modules()
    edges, _self_edges, _leaves = dag.build_graph(modules)

    assert len(edges) > 10, "the extractor found almost nothing — the source moved"
    assert "derived.trend" in edges and "metric_history" in edges["derived.trend"]
    assert "metric_history" in edges, "the history store must be a node, or check B has no seed"
    assert "check A · PASS" in _SCRIPT.read_text()


def test_a_metric_measured_from_situation_state_is_the_trap_doc_13_names() -> None:
    """Check B's subject, proven on the real sampler: the snapshot field fed by
    `context_situations` is `in_active_situation`, it is fed by the CADENCE read (BLG-07 rule 2),
    and no metric PROBE touches it. A probe that did would make `metric_history` an input to its
    own computation."""
    import ast

    dag = _dag_module()
    tree = ast.parse(dag.SAMPLER.read_text())
    fields = dag.snapshot_field_sources(tree)
    probes = dag.probe_functions(tree)
    touched = dag.probe_attributes(tree, probes) & set(fields)

    assert "context_situations" in fields["in_active_situation"], (
        "the situation read must be visible to the analysis, or check B proves nothing")
    assert "in_active_situation" not in touched, (
        "a metric probe reads situation state — doc 13's named trap")
    assert "context_situations" in dag.downstream_of_history(dag.load_modules())
    assert not (touched & {"in_active_situation", "nodes"})
