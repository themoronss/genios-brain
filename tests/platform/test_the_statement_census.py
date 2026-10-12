"""STEP-17 §3.2 · the statement census — every SQL statement the engine and its scripts hold, whole.

    .venv/bin/python -m pytest -q tests/platform/test_the_statement_census.py

`yc2_w27_s17` M40.C1.L-contract.V0.U01. `platform/table_coverage` reads every string node that
starts like SQL, which is right for ATTRIBUTION and wrong for PLANNING: measured at `c97155cd`,
745 of its 3,064 "statements" are pieces of a larger expression (`"select … from " + T` is two) and
21 are docstrings that begin *"Select only …"*. And the statement STEP-18 B1 broke — the weekly
calibration's, spread over three modules as `"with " + AUDITED_CARD_JUDGMENTS_CTES + …` — is, read
as text, a statement with holes that nothing could plan. So the census takes the OUTERMOST string
expression only and resolves each `{NAME}` through the module's own value.

Hermetic: the engine modules are imported, never run against a database; the scripts are read from
their source and never imported.
"""
from __future__ import annotations

import importlib

import pytest

from genios_engine.platform import statement_plans as sp

pytestmark = pytest.mark.unit

SAMPLE = '''
"""Select only what the docstring says — prose, not a statement."""
T = "cards"
WORDS = {"update", "with"}

def f(c, cond, x, cols):
    """Update one phase; a docstring again."""
    c.execute(text("select a from cards where id = :id"))
    c.execute(text("select a, b from " + T + " where id = :id"))
    c.execute(text(f"select a from {T} where b = 1"))
    c.execute(text(f"select a from cards where {cond}"))
    c.execute(text(f"select {x.y} from cards"))
    c.execute(text("select " + ", ".join(cols) + " from cards"))
    c.execute(text("select a from %s" % T))
    sql = "select a from cards"
    sql += " where b = :b"
    c.execute(text(sql))
    print("select a from cards -- printed for a human, never run")
    return ("update the crm", "delete my data")
'''


def _census(source: str = SAMPLE, constants: dict | None = None):
    return sp.census_of("genios_engine/sample.py", source,
                        resolve=(constants or {"T": "cards"}).get)


def _by_line(stmts):
    return {s.line: s for s in stmts}


def test_the_sample_census_is_exactly_its_whole_expressions():
    """One row per whole expression, in source order — every exclusion and every hole at once.
    The last two rows look like SQL and are not; they are left to the planner's test, which names
    each such string one by one rather than guessing (`test_every_statement_plans.NOT_SQL`)."""
    assert [(s.line, s.sql, s.holes) for s in sorted(_census(), key=lambda s: (s.line, s.sql))] == [
        (8, "select a from cards where id = :id", ()),
        (9, "select a, b from cards where id = :id", ()),
        (10, "select a from cards where b = 1", ()),
        (11, "select a from cards where {cond}", ("cond",)),
        (12, "select {?} from cards", ("?",)),
        (13, "select {?} from cards", ("?",)),
        (14, "select a from %s", ("%",)),
        (15, "select a from cards", ("+=",)),
        (19, "delete my data", ()),
        (19, "update the crm", ()),
    ]


def test_one_statement_per_whole_expression_never_its_pieces():
    sqls = [s.sql for s in _census()]
    assert "select a, b from cards where id = :id" in sqls
    assert not any(s.strip() in ("select a, b from", "select a, b from cards") for s in sqls), (
        "the left side of a `+` is a piece of the statement, not a second one")
    assert sum("select a, b from" in s for s in sqls) == 1


def test_a_docstring_a_word_and_a_printed_query_are_not_statements():
    sqls = [s.sql for s in _census()]
    assert not any(s.lower().startswith(("select only", "update one")) for s in sqls)
    assert "update" not in sqls and "with" not in sqls
    assert not any("printed for a human" in s for s in sqls), (
        "printing a query is not running one — table_coverage's rule")


def test_constants_resolve_and_what_cannot_stays_a_named_hole():
    found = {s.sql: s.holes for s in _census()}
    assert found["select a from cards where b = 1"] == ()
    assert found["select a from cards where {cond}"] == ("cond",)
    assert found["select {?} from cards"] == ("?",)


def test_an_expression_hole_is_never_resolved_even_by_a_resolver_that_would():
    """`{?}` stands for an expression — `x.y`, a call — and no name lookup may fill it."""
    found = {s.sql for s in _census(constants={"T": "cards", "?": "a, b"})}
    assert "select {?} from cards" in found and "select a, b from cards" not in found


def test_an_expression_that_is_a_call_is_a_hole_not_a_dropped_statement():
    """`"select " + ", ".join(cols) + " from cards"` — table_coverage's `_template` renders it as
    nothing, so a reader built on it would never see the statement at all."""
    stmts = [s for s in _census() if s.sql == "select {?} from cards"]
    assert len(stmts) == 2 and all(s.holes == ("?",) for s in stmts)


def test_a_percent_format_and_an_augmented_statement_are_assembled_at_run_time():
    found = {s.sql: s.holes for s in _census()}
    assert found["select a from %s"] == ("%",)
    assert found["select a from cards"] == ("+=",), (
        "`sql += …` finishes the statement at run time — the first literal is not all of it")


def test_a_name_is_resolved_before_the_shape_is_judged():
    """A statement may begin with its constant: `CTES + "select …"`."""
    src = 'c.execute(text(CTE + " select x from y"))\n'
    stmts = sp.census_of("genios_engine/s.py", src,
                         resolve={"CTE": "with y as (select 1 as x)"}.get)
    assert [s.sql for s in stmts] == ["with y as (select 1 as x) select x from y"]
    assert stmts[0].holes == ()


def test_a_json_literal_or_a_regex_count_is_not_a_hole():
    src = ('c.execute(text("select cast(\'{}\' as jsonb), x ~ \'^a{64}$\' from t"))\n')
    (stmt,) = sp.census_of("genios_engine/s.py", src, resolve={}.get)
    assert stmt.holes == ()


def test_each_statement_says_where_it_lives():
    stmts = _census()
    assert all(s.path == "genios_engine/sample.py" and s.line > 0 for s in stmts)


def test_a_script_resolves_its_own_constants_and_the_engine_constants_it_imports():
    """A script is read, never imported: its own module constants from the AST, and a name it
    imports from `genios_engine` from that engine module's value."""
    src = ('from genios_engine.context.analytic.history import HISTORY_TABLE\n'
           'T = "cards"\n'
           'Q = f"select a from {T}"\n'
           'def main(c):\n'
           '    c.execute(text(f"select count(*) from {HISTORY_TABLE}"))\n'
           '    c.execute(text(Q + " where b = 1"))\n')
    asked: list[str] = []

    def importer(name):
        asked.append(name)
        return importlib.import_module(name)

    resolve = sp._resolver("scripts/x.py", src, importer, frozenset())
    stmts = sp.census_of("scripts/x.py", src, resolve=resolve)
    assert sorted((s.sql, s.holes) for s in stmts) == [
        ("select a from cards", ()),
        ("select a from cards where b = 1", ()),
        ("select count(*) from metric_history", ()),
    ]
    assert set(asked) == {"genios_engine.context.analytic.history"}


# ── the tree ───────────────────────────────────────────────────────────────────────────────────

def test_the_calibration_statement_is_found_whole_with_card_level_resolved():
    """STEP-18 B1. The statement `feedback/calibrate` runs every week is built from three modules'
    constants; resolved, it is one statement with no hole, and it reads `card_level` from the CTE
    `reason/authority.AUDITED_CARD_JUDGMENTS_CTES` defines. The planner can only catch B1 if this
    holds."""
    calib = [s for s in sp.statements() if s.path == "genios_engine/feedback/calibrate.py"
             and "canonical_judgments as (" in s.sql]
    assert len(calib) == 1, [s.line for s in calib]
    (stmt,) = calib
    assert stmt.holes == ()
    assert "card_level in ('prescriptive','predictive')" in stmt.sql
    assert stmt.sql.lstrip().lower().startswith("with audited_cards as (")


def test_the_census_covers_the_engine_and_the_scripts():
    stmts = sp.statements()
    paths = {s.path.split("/")[0] for s in stmts}
    assert paths == {"genios_engine", "scripts"}
    counts = sp.census()
    assert counts["statements"] == len(stmts)
    # ⛔ A FLOOR, NOT AN EQUALITY: adding SQL is ordinary, losing the ability to read it is not.
    assert counts["statements"] >= 2_200, counts
    assert counts["resolved_whole"] >= 2_000, counts
    assert counts["pieces"] >= 700 and counts["docstrings"] >= 15, (
        "the census must keep NAMING what it leaves out", counts)
    assert counts["resolved_whole"] + counts["assembled_at_run_time"] == counts["statements"]
    # A script statement resolved through the engine constant it imports — read, never run.
    assert any(s.path == "scripts/history_density_report.py" and not s.holes
               and s.sql.strip() == "select count(*) from metric_history" for s in stmts)


def test_no_engine_module_fails_to_import():
    """A module the census cannot import keeps every hole it has — coverage would shrink with no
    failure anywhere."""
    sp.statements()
    assert sp.import_failures() == ()


def test_an_import_that_fails_is_named_and_its_holes_stay_holes():
    """The negative control for the test above: with an importer that refuses one engine module,
    that module is named with its reason, and the calibration statement keeps its holes rather than
    passing as whole."""
    def importer(name):
        if name == "genios_engine.feedback.calibrate":
            raise ImportError("refused by the test")
        return importlib.import_module(name)

    failures: dict[str, str] = {}
    stmts = sp.build_statements(importer=importer, failures=failures)
    assert failures == {"genios_engine.feedback.calibrate": "ImportError: refused by the test"}
    calib = [s for s in stmts if s.path == "genios_engine/feedback/calibrate.py"
             and "judgment_counts as (" in s.sql]
    assert len(calib) == 1
    assert "AUDITED_CARD_JUDGMENTS_CTES" in calib[0].holes, calib[0].holes


def test_a_local_alias_of_a_table_constant_resolves():
    """`table = L4_ACTIVATION_TABLE` inside the function, then `f"insert into {table} …"` —
    `table_coverage`'s third hop, reused."""
    found = [s for s in sp.statements() if s.path == "genios_engine/platform/l4_activation.py"
             and s.sql.startswith("insert into l4_activation (org_id, feature, enabled_at")]
    assert len(found) == 1 and found[0].holes == ()
    assert "case when l4_activation.disabled_at is null" in found[0].sql


def test_a_script_is_read_and_never_run():
    """`scripts/` are operator tools — some read production. The census parses them; importing one
    would run its top-level code. Every import the census asks for is recorded, on a census built
    afresh."""
    asked: list[str] = []

    def importer(name):
        asked.append(name)
        return importlib.import_module(name)

    stmts = sp.build_statements(importer=importer)
    assert asked, "the engine modules are imported to resolve their constants"
    assert all(name.startswith("genios_engine.") for name in asked), sorted(
        n for n in asked if not n.startswith("genios_engine."))
    assert any(s.path.startswith("scripts/") and not s.holes for s in stmts)
