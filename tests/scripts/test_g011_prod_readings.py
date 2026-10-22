"""GeniOS-011 S01.U1 · one read-only runner holds every production reading GeniOS-011 is blocked on.

    .venv/bin/python -m pytest -q tests/scripts/test_g011_prod_readings.py
    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q tests/scripts/test_g011_prod_readings.py

Production has not been read since the 823-commit merge reached it (GeniOS-011 F6), and 61 audit
items wait on a read-only SQL answer. `scripts/g011_prod_readings.py` holds every one of those
queries, runs them on ONE connection whose transaction is `read only` from its first statement, and
writes one JSON keyed by audit item key. What is held here:

  * a planted INSERT / UPDATE / DELETE is refused before the database is even opened — the keyword
    check is the first lock, the server's read-only transaction the second (the `pg` tests);
  * every per-tenant query binds the org as a parameter, never as text, and the few that are facts
    about the server are a closed, named set;
  * one connection, `set transaction read only` first, `--org` required, one JSON keyed by item key;
  * a reading that fails (a table a migration never created) is said in the JSON and does not void
    the rest — on a real database, inside the one read-only transaction.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from scripts import g011_prod_readings as pr

ORG = "org_g011_s01u1_planted"
SCRIPT = Path(pr.__file__)


# ── a connection that records what reached it ──────────────────────────────────────────────────────

class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return list(self._rows)


class _Savepoint:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.savepoints += 1
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    """Records every statement and its parameters. `fail_on` names statements (by a substring) that
    raise the way Postgres does when a table is missing."""

    def __init__(self, fail_on=()):
        self.executed: list[tuple[str, dict]] = []
        self.fail_on = tuple(fail_on)
        self.savepoints = 0
        self.closed = False

    def execute(self, clause, params=None):
        statement = str(clause)
        self.executed.append((statement, dict(params or {})))
        if any(marker in statement for marker in self.fail_on):
            raise ProgrammingError(statement, params, Exception("relation does not exist"))
        return _Result([{"n": 1}])

    def begin_nested(self):
        return _Savepoint(self)

    def close(self):
        self.closed = True


class FakeEngine:
    def __init__(self, fail_on=()):
        self.connections: list[FakeConnection] = []
        self.fail_on = fail_on

    def connect(self):
        conn = FakeConnection(self.fail_on)
        self.connections.append(conn)
        return conn


def _main(monkeypatch, tmp_path, *argv, engine=None):
    import genios_engine.platform.db as db
    engine = engine or FakeEngine()
    monkeypatch.setattr(pr, "resolve_database_url", lambda *a, **k: "postgresql://scratch/x")
    monkeypatch.setattr(db, "get_engine", lambda url: engine)
    out = tmp_path / "readings.json"
    code = pr.main(["--org", ORG, "--out", str(out), *argv])
    return code, engine, out


def _plant(monkeypatch, statement: str, *, item: str = "planted-item") -> None:
    readings = dict(pr.READINGS)
    readings["planted"] = pr.Reading("planted", statement)
    items = dict(pr.ITEMS)
    items[item] = ("planted",)
    monkeypatch.setattr(pr, "READINGS", readings)
    monkeypatch.setattr(pr, "ITEMS", items)


# ── the first lock: only a read reaches the connection ─────────────────────────────────────────────

PLANTED_WRITES = [
    "insert into feature_flags (key, enabled) values ('kill_switch_all', false)",
    "update orgs set plan_status = 'expired' where id = :org",
    "delete from cards where org_id = :org",
    "  DELETE FROM cards WHERE org_id = :org",
    "-- looks like a comment\ndelete from cards where org_id = :org",
    "/* select */ update cards set state = 'expired' where org_id = :org",
    "(delete from cards where org_id = :org)",
    "merge into cards using orgs on true when matched then delete",
    "truncate cards",
    "drop table cards",
    "create table x (id int)",
    "alter table cards add column x int",
    "grant all on cards to public",
    "copy cards from stdin",
    "call do_something()",
    "do $$ begin delete from cards; end $$",
    "explain analyze delete from cards where org_id = :org",
    "set transaction read write",
    "commit",
    "select count(*) from cards where org_id = :org; delete from cards where org_id = :org",
]


@pytest.mark.unit
@pytest.mark.parametrize("statement", PLANTED_WRITES)
def test_the_guard_refuses_anything_but_a_read(statement):
    with pytest.raises(pr.RefusedStatement):
        pr.refuse_unless_read(statement)


@pytest.mark.unit
@pytest.mark.parametrize("statement", [
    "select 1",
    "SELECT count(*) FROM cards WHERE org_id = :org",
    "  with x as (select 1 as n) select n from x",
    "-- the reading\nselect 1",
    "/* why */ select 1;",
    "(select 1) union all (select 2)",
    "show transaction_read_only",
    "select ';' as semicolon_in_a_literal, 'a''b' as quoted",
])
def test_the_guard_lets_a_read_through(statement):
    assert pr.refuse_unless_read(statement) == statement


@pytest.mark.unit
@pytest.mark.parametrize("statement", [
    "insert into feature_flags (key, enabled) values ('kill_switch_all', false)",
    "update orgs set plan_status = 'expired' where id = :org",
    "delete from cards where org_id = :org",
])
def test_a_planted_write_is_refused_before_the_database_is_opened(monkeypatch, tmp_path, capsys,
                                                                 statement):
    _plant(monkeypatch, statement)
    code, engine, out = _main(monkeypatch, tmp_path)
    assert code == pr.EXIT_REFUSED
    assert engine.connections == [], "a refused pass never opens the connection"
    assert not out.exists(), "a refused pass writes no readings"
    assert "planted" in capsys.readouterr().err


@pytest.mark.unit
def test_run_refuses_a_planted_write_before_its_first_statement(monkeypatch):
    """`run` is the second door (a caller with its own connection): it checks every statement
    before executing any, so a write planted LAST still stops the pass before the FIRST read."""
    _plant(monkeypatch, "delete from cards where org_id = :org", item="zz-last")
    conn = FakeConnection()
    with pytest.raises(pr.RefusedStatement):
        pr.run(conn, ORG)
    assert conn.executed == []


@pytest.mark.unit
def test_the_one_execute_in_the_runner_sits_behind_the_guard():
    """AST, not text: the runner has exactly one `.execute(...)` call, in `_read`, and `_read` calls
    `refuse_unless_read` on the statement first. A new execute elsewhere would be a door without a
    guard."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    owners = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "execute"):
                    owners.append((fn.name, node.lineno))
    assert [name for name, _ in owners] == ["_read"], owners
    read = next(fn for fn in ast.walk(tree)
                if isinstance(fn, ast.FunctionDef) and fn.name == "_read")
    guard_lines = [node.lineno for node in ast.walk(read)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "refuse_unless_read"]
    assert guard_lines and min(guard_lines) < owners[0][1]


# ── every per-tenant query binds the org; the server facts are a closed set ────────────────────────

SERVER_FACTS = {"transaction_read_only", "migrations_since_0191", "screen_followups_0250_columns",
                "feedback_check_constraints", "database_size", "largest_tables"}


@pytest.mark.unit
def test_the_server_facts_are_a_closed_set():
    assert {name for name, r in pr.READINGS.items() if r.server} == SERVER_FACTS


@pytest.mark.unit
@pytest.mark.parametrize("name", sorted(pr.READINGS))
def test_every_reading_is_a_read_and_binds_exactly_the_org(name):
    reading = pr.READINGS[name]
    assert reading.name == name
    pr.refuse_unless_read(reading.sql)
    binds = set(text(reading.sql).compile().params)
    assert binds == (set() if reading.server else {"org"}), (name, binds)


@pytest.mark.unit
def test_every_org_reading_was_run_with_the_org_bound_never_written_in(monkeypatch, tmp_path):
    code, engine, _ = _main(monkeypatch, tmp_path)
    assert code == 0
    [conn] = engine.connections
    by_sql = {r.sql: r for r in pr.READINGS.values()}
    ran = conn.executed[1:]
    assert len(ran) == len(pr.READINGS), "every reading runs once, however many items share it"
    for statement, params in ran:
        reading = by_sql[statement]
        assert ORG not in statement, f"{reading.name} carries the org as text"
        assert params == ({} if reading.server else {"org": ORG}), (reading.name, params)


# ── one connection, read only first, --org required, one JSON keyed by item key ───────────────────

@pytest.mark.unit
def test_one_connection_and_read_only_is_its_first_statement(monkeypatch, tmp_path):
    code, engine, _ = _main(monkeypatch, tmp_path)
    assert code == 0
    assert len(engine.connections) == 1
    conn = engine.connections[0]
    assert conn.executed[0] == ("set transaction read only", {})
    assert conn.savepoints == len(pr.READINGS), "each reading in its own savepoint"
    assert conn.closed


@pytest.mark.unit
def test_org_is_required(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as stop:
        pr.main(["--out", str(tmp_path / "x.json")])
    assert stop.value.code == 2
    assert "--org" in capsys.readouterr().err


@pytest.mark.unit
def test_the_json_is_keyed_by_item_key(monkeypatch, tmp_path):
    code, _, out = _main(monkeypatch, tmp_path)
    assert code == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert kept["unit"] == "GeniOS-011 S01.U1"
    assert kept["org"] == ORG and kept["at"]
    assert set(kept["items"]) == set(pr.ITEMS)
    for item, readings in kept["items"].items():
        assert set(readings) == set(pr.ITEMS[item]), item
        for name, reading in readings.items():
            assert reading["sql"] == pr.READINGS[name].sql
            assert reading["rows"] == [{"n": 1}] and reading["row_count"] == 1
            assert "error" not in reading
    assert kept["summary"] == {"items": len(pr.ITEMS), "readings": len(pr.READINGS), "failed": 0}


@pytest.mark.unit
def test_every_item_names_only_readings_that_exist_and_every_reading_is_used():
    used = {name for names in pr.ITEMS.values() for name in names}
    assert used <= set(pr.READINGS)
    assert set(pr.READINGS) - used == set(), "a reading no item asks for is noise"
    for item, names in pr.ITEMS.items():
        assert names and len(names) == len(set(names)), item


#: The DONE WHEN of S01.U1, phrase by phrase: (what it asks, the item that holds it, the reading,
#: the table the reading must read).
DONE_WHEN = [
    ("source_events outcome/attention since 18 Oct", "l1-post-deploy-funnel-unmeasured",
     "source_events_since_deploy", "source_events"),
    ("event_trace S1/S2", "l1-post-deploy-funnel-unmeasured", "event_trace_s1_s2_since_deploy",
     "event_trace"),
    ("qualified_signals by type/state", "l1-post-deploy-funnel-unmeasured",
     "qualified_signals_by_type_state", "qualified_signals"),
    ("l1_sync_runs", "l1-refusal-and-coverage-invisible", "l1_sync_runs_since_deploy",
     "l1_sync_runs"),
    ("l1 activation rows", "process-switch-state-invisible", "l1_semantic_activation",
     "l1_semantic_activation"),
    ("l2 activation rows", "process-switch-state-invisible", "l2_v2_activation",
     "l2_v2_activation"),
    ("l3 activation rows", "process-switch-state-invisible", "l3_activation", "l3_activation"),
    ("l4 activation rows", "process-switch-state-invisible", "l4_activation", "l4_activation"),
    ("cards per day by builder_version/output_lane/state since 1 Oct",
     "l5-fewer-cards-refusals-unmeasured", "cards_per_day", "cards"),
    ("card_refusals by rule", "l5-fewer-cards-refusals-unmeasured", "card_refusals_by_rule",
     "card_refusals"),
    ("expert_reviews by status/fate", "process-no-production-number-after-deploy",
     "expert_reviews_per_day_since_deploy", "expert_reviews"),
    ("reasoning_results by status", "l2-fallback-to-formula-lanes",
     "reasoning_results_by_status_lane", "reasoning_results"),
    ("l2_admissions by decision/op", "l2-admission-g2-shadow", "l2_admissions_by_decision_op",
     "l2_admissions"),
    ("l4_r_site_calls by site/outcome", "process-no-production-number-after-deploy",
     "r_site_calls_per_day", "l4_r_site_calls"),
    ("llm_costs per day", "cross-billing-gates-silently-stop-the-org", "llm_calls_per_day",
     "llm_costs"),
    ("schema_migrations >= 0191", "process-migrations-applied-unknown", "migrations_since_0191",
     "schema_migrations"),
    ("orgs plan/billing state", "cross-billing-gates-silently-stop-the-org", "org_plan_state",
     "orgs"),
    ("kill switches", "cross-billing-gates-silently-stop-the-org", "kill_switches",
     "feature_flags"),
    ("evidence_needs by state", "l1-e2-need-fetchers-armed-off", "evidence_needs_by_state",
     "evidence_needs"),
    ("connections capture_scope", "l1-resync-and-history-window", "connections_capture_scope",
     "connections"),
    ("company_brief_lines by section/status", "l1-company-brief-gate-dependence",
     "company_brief_lines_by_section", "company_brief_lines"),
    ("live-situation multiplicity per anchor", "l3-one-subject-many-situations",
     "live_situation_multiplicity", "context_situations"),
    ("DB size", "cross-db-tier-never-budgeted", "database_size", "pg_database_size"),
    ("top tables", "cross-db-tier-never-budgeted", "largest_tables", "pg_statio_user_tables"),
]


@pytest.mark.unit
@pytest.mark.parametrize("asked,item,reading,table", DONE_WHEN, ids=[d[0] for d in DONE_WHEN])
def test_the_done_when_readings_are_held(asked, item, reading, table):
    assert reading in pr.ITEMS[item], f"{asked}: {item} does not hold {reading}"
    assert re.search(rf"\b{table}\b", pr.READINGS[reading].sql), f"{asked}: {reading} reads no {table}"


# ── a reading that fails is said, and the rest still run ───────────────────────────────────────────

@pytest.mark.unit
def test_a_failed_reading_is_said_and_the_rest_still_run(monkeypatch, tmp_path):
    engine = FakeEngine(fail_on=("from l2_admissions",))
    code, engine, out = _main(monkeypatch, tmp_path, engine=engine)
    assert code == pr.EXIT_SOME_FAILED, "a failed reading is not a clean pass"
    kept = json.loads(out.read_text(encoding="utf-8"))
    failed = kept["items"]["l2-admission-g2-shadow"]["l2_admissions_by_decision_op"]
    assert "relation does not exist" in failed["error"] and "rows" not in failed
    assert kept["items"]["l4-approver-and-org-data-writer"]["authority_rules_count"]["rows"]
    assert kept["summary"]["failed"] == 1


# ── on a real database: every reading runs, inside a transaction the server keeps read only ───────

ORG_PG = "org_g011_s01u1_pg"
ORG_PG_OTHER = "org_g011_s01u1_pg_other"


@pytest.fixture
def seeded(live_db_url):
    """Two orgs, each with one l4_activation row and a kill switch — committed, because the runner
    opens its own connection. Removed afterwards (the orgs cascade to l4_activation)."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the readings run on a migrated scratch "
                    "database")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)

    def _clean():
        with engine.begin() as c:
            c.execute(text("delete from feature_flags where key in (:a, :b)"),
                      {"a": f"kill_switch:{ORG_PG}", "b": f"kill_switch:{ORG_PG_OTHER}"})
            c.execute(text("delete from orgs where id in (:a, :b)"),
                      {"a": ORG_PG, "b": ORG_PG_OTHER})

    _clean()
    with engine.begin() as c:
        for org, feature in ((ORG_PG, "expert_review"), (ORG_PG_OTHER, "l2_cards")):
            c.execute(text("insert into orgs (id, name) values (:o, 'G011 S01.U1')"), {"o": org})
            c.execute(text("insert into l4_activation (org_id, feature, enabled_by) "
                           "values (:o, :f, 'g011-s01u1-test')"), {"o": org, "f": feature})
            c.execute(text("insert into feature_flags (key, enabled) values (:k, false)"),
                      {"k": f"kill_switch:{org}"})
    try:
        yield live_db_url, engine
    finally:
        _clean()


@pytest.mark.pg
def test_every_reading_runs_read_only_on_the_migrated_schema(seeded, tmp_path):
    url, _ = seeded
    out = tmp_path / "readings.json"
    code = pr.main(["--org", ORG_PG, "--database-url", url, "--out", str(out)])
    kept = json.loads(out.read_text(encoding="utf-8"))
    errors = {(item, name): r["error"] for item, readings in kept["items"].items()
              for name, r in readings.items() if "error" in r}
    assert errors == {}
    assert code == 0
    proof = kept["items"]["process-migrations-applied-unknown"]["transaction_read_only"]["rows"]
    assert proof == [{"transaction_read_only": "on"}]
    switches = kept["items"]["process-switch-state-invisible"]["l4_activation"]["rows"]
    assert [row["feature"] for row in switches] == ["expert_review"], "the org binds: ours only"
    kills = kept["items"]["cross-billing-gates-silently-stop-the-org"]["kill_switches"]["rows"]
    assert {row["key"] for row in kills} == {"kill_switch_all", f"kill_switch:{ORG_PG}"}, \
        "the global switch (seeded by 0009) and ours — never the other org's"


@pytest.mark.pg
def test_the_server_refuses_the_write_the_keyword_check_cannot_see(seeded, tmp_path, monkeypatch):
    """A data-modifying `with` starts with a read keyword and passes the first lock. The second lock
    is the transaction: Postgres refuses the DELETE, the reading says so, and the row is still
    there. The table that does not exist fails alone — the readings after it still run."""
    url, engine = seeded
    readings = dict(pr.READINGS)
    readings["planted_cte_write"] = pr.Reading(
        "planted_cte_write",
        "with gone as (delete from l4_activation where org_id = :org returning 1) "
        "select count(*) as n from gone")
    readings["planted_missing_table"] = pr.Reading(
        "planted_missing_table", "select count(*) as n from g011_no_such_table where org_id = :org")
    items = {"aa-planted": ("planted_cte_write", "planted_missing_table"), **pr.ITEMS}
    monkeypatch.setattr(pr, "READINGS", readings)
    monkeypatch.setattr(pr, "ITEMS", items)
    out = tmp_path / "readings.json"
    code = pr.main(["--org", ORG_PG, "--database-url", url, "--out", str(out)])
    assert code == pr.EXIT_SOME_FAILED
    kept = json.loads(out.read_text(encoding="utf-8"))
    planted = kept["items"]["aa-planted"]
    assert "read-only transaction" in planted["planted_cte_write"]["error"]
    assert "g011_no_such_table" in planted["planted_missing_table"]["error"]
    assert kept["summary"]["failed"] == 2
    switches = kept["items"]["process-switch-state-invisible"]["l4_activation"]["rows"]
    assert [row["feature"] for row in switches] == ["expert_review"]
    with engine.connect() as c:
        left = c.execute(text("select count(*) from l4_activation where org_id = :o"),
                         {"o": ORG_PG}).scalar()
    assert left == 1, "the planted delete removed nothing"
