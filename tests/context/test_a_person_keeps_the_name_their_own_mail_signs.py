"""The write-path fix reached nobody who was already in the graph.

`name_person_node` landed with a caller in `context/pipeline._person`, and `find_or_create_node`
writes `display_name` when it CREATES a node and never again. So every person captured before
that fix keeps their address for ever — and the people who most need a name are exactly the ones
nobody has written to since. `name_thread_nodes` and `name_company_nodes` both make that argument
in their own docstrings; the person lane had the fix and no sweep.

MEASURED 2026-09-17, three orgs: 88 person nodes still displaying an email, and 30 of them have a
From-header name sitting in `source_events` — "Harsh Tripathi", "Anirudh Sharma", "Anisha Prasad"
across 295 events. The other 58 have never been seen with a name and are correctly left alone: a
name nothing observed must not be invented.

AND `name_company_nodes` HAD NO CALLER AT ALL. Its docstring carries its own measurement — "48 of
48 company nodes displaying a hostname, 19 cards opening on peakxv.com rather than PeakXV" — and
nothing ever ran it, so on 2026-09-17 it was still 29 of 48. Both passes are on the heartbeat now
and the last test here is what says so.
"""
from __future__ import annotations

import ast
import inspect

import pytest

pytest.importorskip("sqlalchemy")

from genios_engine.context.backfill import best_person_name  # noqa: E402


def _row(surface, seen, node="n1", org="org_1"):
    return {"org_id": org, "node_id": node, "surface": surface, "seen": seen}


# =============================================================================================
# the choice, which has to be the same on every machine
# =============================================================================================
def test_the_form_they_use_most_wins():
    """Not the first row read. A re-run over a different slice must name them the same."""
    best = best_person_name([_row("R K", 1), _row("Ritu Kumari", 9), _row("Ritu", 2)])

    assert best[("org_1", "n1")][1] == "Ritu Kumari"


def test_a_tie_on_frequency_breaks_towards_the_fuller_spelling():
    best = best_person_name([_row("Ritu", 4), _row("Ritu Kumari", 4)])

    assert best[("org_1", "n1")][1] == "Ritu Kumari"


def test_a_tie_on_both_is_still_decided():
    """Two spellings, same count, same length. Left to luck this returns whichever the driver
    happened to yield first, and the name changes between passes."""
    a = best_person_name([_row("Ana Silva", 3), _row("Ana Sousa", 3)])
    b = best_person_name([_row("Ana Sousa", 3), _row("Ana Silva", 3)])

    assert a[("org_1", "n1")] == b[("org_1", "n1")]


def test_the_order_rows_arrive_in_never_changes_the_answer():
    rows = [_row("Ritu", 2), _row("Ritu Kumari", 9), _row("R K", 9), _row("Ritu K", 1)]

    assert best_person_name(rows) == best_person_name(list(reversed(rows)))


def test_people_are_kept_apart():
    """One dict, many nodes. A key collision would give one person another's name."""
    best = best_person_name([_row("Ray Liao", 2, node="a"), _row("Peter Bronk", 3, node="b")])

    assert best[("org_1", "a")][1] == "Ray Liao"
    assert best[("org_1", "b")][1] == "Peter Bronk"


def test_the_same_node_id_in_two_orgs_is_two_people():
    best = best_person_name([_row("Ray Liao", 2, org="org_1"), _row("Ana Silva", 2, org="org_2")])

    assert best[("org_1", "n1")][1] == "Ray Liao"
    assert best[("org_2", "n1")][1] == "Ana Silva"


def test_a_blank_surface_is_not_a_name():
    """`coalesce(...,'') <> ''` filters these in SQL; the ranking must not re-admit one."""
    assert best_person_name([_row("   ", 9)]) == {}


def test_whitespace_is_normalised_but_the_name_is_not_tidied():
    """"Singh, Alok" and "Surender KUMAR KUMAR" are how those people's own mail clients introduce
    them. The write path passes `sender_name` through verbatim, and a sweep that tidied would
    call the same person two things depending on which pass reached them first."""
    best = best_person_name([_row("  Singh,   Alok  ", 2)])

    assert best[("org_1", "n1")][1] == "Singh, Alok"


# =============================================================================================
# the call site — both passes, because one of them never had one
# =============================================================================================
def test_the_heartbeat_runs_both_naming_sweeps():
    """`name_company_nodes` shipped with a measurement in its docstring and no caller, so the
    number it was written to move never moved. A sweep nothing runs is a comment."""
    from genios_engine.api import routes

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(routes)))
              if isinstance(n, ast.FunctionDef) and n.name == "run_maintenance_sweep")
    src = ast.unparse(fn)

    assert "name_person_nodes(" in src, "people are still named only on the write path"
    assert "name_company_nodes(" in src, "the company sweep has no caller again"


def test_the_company_sweep_is_given_an_org():
    """It resolves mentions against ONE tenant's anchors — `resolve_company_mention` takes an
    org — so a fleet-wide call would be a TypeError caught by the heartbeat's `except` and
    reported as a generic naming failure for ever."""
    from genios_engine.api import routes

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(routes)))
              if isinstance(n, ast.FunctionDef) and n.name == "run_maintenance_sweep")
    call = next(n for n in ast.walk(fn)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "name_company_nodes")

    assert len(call.args) >= 2, "name_company_nodes is called without an org id"
