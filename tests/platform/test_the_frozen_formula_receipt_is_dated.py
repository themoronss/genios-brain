r"""`D.U03` · the frozen-formula receipt asked a correct question with no date on it.

⛔ WHAT WAS WRONG, AND IT WAS NOT THE QUESTION. The receipt asked whether any candidate carries
`impact`, `risk` and `effort` all at the 5000 neutral default, and expected zero. That is the right
question on the right table, and `reason/decision_maker.py:181` states the doctrine it enforces:
*"Never substitute 5000. A neutral default is exactly the bug that made every card score 50."*

⛔ THE DEFECT WAS REAL. Measured on production 2026-10-01:

    risk = 5000, on its own                              59 rows
    impact AND risk AND effort = 5000                    59 rows   -> perfect correlation
    all five of guards.CANDIDATE_COMPONENTS = 5000        53 rows

Three nominally independent integers never once land on 5000 apart, and for 53 of the 59 the
WHOLE ranking formula was one constant. Both candidate seams had built `PlayDefinition` without
those fields, so the dataclass defaults stood in for measurements.

⛔ AND IT WAS CLOSED THREE WEEKS BEFORE THE RECEIPT WAS READ.

    the 59 frozen rows   2026-08-17 19:21:18 -> 2026-09-07 23:55:58
    fix commit 75096bab  2026-09-08
    written at or after the boundary   34,167 candidates, across all three orgs, 0 frozen

The last frozen row is the day before the commit that closed it.

⛔ SO WHAT WAS BROKEN IS THE RECEIPT. `reasoning_candidates` is append-only and this codebase
soft-deletes only, so those 59 rows are permanent and the receipt returns 59 forever.
`api/routes.py:161` computes `ready = not failed` over this list — one unfixable receipt holding
the release gate shut for a defect that no longer exists. **A receipt over append-only history
needs a lower bound, or it is not a gate but a monument.**

⛔ WHICH IS WHY THESE TESTS GUARD THE PREDICATE, NOT THE ANSWER. Adding a date is a hair's breadth
from making a receipt green, and the difference has to be provable: the three equalities must be
byte-for-byte what they always were, the receipt must still be able to fail, and the boundary must
come from the declaration rather than a literal somebody can nudge.
"""
from __future__ import annotations

import ast
import inspect
import re
import textwrap

import pytest

from genios_engine.platform import receipts as R
from genios_engine.reason import unit_health as U

CLAIM = "the score components the scorer writes NOW are measured, not placeholders"
DEFECT = "score_components.neutral_default"

#: What the receipt asked before the date was added, byte-for-byte.
HISTORICAL_PREDICATE = (
    "select count(*) from reasoning_candidates where "
    "score_components->>'impact' = '5000' and score_components->>'risk' = '5000' "
    "and score_components->>'effort' = '5000'"
)


def _receipt():
    found = [r for r in R.receipts(None) if r.claim == CLAIM]
    assert len(found) == 1, f"expected exactly one receipt asking this, got {len(found)}"
    return found[0]


# --------------------------------------------------------------------------------------------
# the predicate was not touched
# --------------------------------------------------------------------------------------------

def test_the_predicate_is_byte_for_byte_what_it_always_asked() -> None:
    """The three equalities are unchanged. This is what separates dating from weakening."""
    sql = R._PLACEHOLDER_COMPONENTS_SQL(None)
    assert sql.startswith(HISTORICAL_PREDICATE), (
        "the original predicate must survive verbatim; anything else is a different question")


def test_the_only_change_is_the_lower_bound() -> None:
    added = R._PLACEHOLDER_COMPONENTS_SQL(None)[len(HISTORICAL_PREDICATE):]
    assert added == f" and created_at >= '{U.neutral_default_boundary()}'", (
        f"exactly one clause may be added, and it must be the bound; got {added!r}")


def test_the_org_filter_still_applies() -> None:
    """A tenant's readiness page must not answer about every tenant at once."""
    assert "org_id" in R._PLACEHOLDER_COMPONENTS_SQL("org_abc")
    assert _receipt().fleet_wide is False
    assert _receipt().layer == "L4"


# --------------------------------------------------------------------------------------------
# it can still fail
# --------------------------------------------------------------------------------------------

def test_the_receipt_was_not_made_to_pass() -> None:
    """One candidate written by the old code today, and this goes red again."""
    expect = _receipt().expect
    assert expect(0) is True
    assert expect(1) is False, "a single returned candidate must fail the receipt"
    assert expect(59) is False


def test_the_detail_states_the_measured_truth_and_points_at_the_declaration() -> None:
    detail = _receipt().detail
    for fact in ("59", "ALL FIVE", "2026-09-08", "75096bab", "unit_health"):
        assert fact in detail, f"the detail must carry {fact!r} so a reader need not re-measure"


# --------------------------------------------------------------------------------------------
# the boundary comes from the declaration, not from a literal
# --------------------------------------------------------------------------------------------

def _string_constants_excluding_docstring(func) -> list[str]:
    """Every str literal inside the function body, minus its docstring.

    ⛔ AN AST WALK AND NOT A GREP. A whole-file scan for the date matches this module's own prose
    and the receipt's detail, both of which quote it on purpose. The question is only whether the
    EXECUTED code carries its own copy.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    fn = tree.body[0]
    body = fn.body[1:] if (isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)
                           and isinstance(fn.body[0].value.value, str)) else fn.body
    out: list[str] = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append(node.value)
    return out


def test_the_builder_reads_the_declaration_rather_than_restating_the_date() -> None:
    literals = _string_constants_excluding_docstring(R._PLACEHOLDER_COMPONENTS_SQL)
    boundary = U.neutral_default_boundary()
    assert boundary not in literals, (
        "the builder must not carry its own copy of the boundary -- it would drift from "
        "reason/unit_health.CLOSED_DEFECTS the moment one of the two was edited")


def test_the_builder_imports_the_boundary_from_unit_health() -> None:
    tree = ast.parse(textwrap.dedent(inspect.getsource(R._PLACEHOLDER_COMPONENTS_SQL)))
    imported = {alias.name
                for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                for alias in node.names}
    assert "neutral_default_boundary" in imported


def test_the_receipt_calls_the_builder_rather_than_inlining_sql() -> None:
    """AST over `receipts()`: the sql argument must be the builder call, not a string."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(R.receipts)))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Receipt"):
            continue
        args = node.args
        if len(args) >= 2 and isinstance(args[1], ast.Constant) and args[1].value == CLAIM:
            sql_arg = args[2]
            assert isinstance(sql_arg, ast.Call), (
                "the sql must come from _PLACEHOLDER_COMPONENTS_SQL, not be inlined")
            assert getattr(sql_arg.func, "id", None) == "_PLACEHOLDER_COMPONENTS_SQL"
            return
    pytest.fail(f"no Receipt(...) call found carrying the claim {CLAIM!r}")


def test_a_boundary_that_is_not_a_date_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The date is interpolated into SQL, so its shape is checked before it gets there."""
    monkeypatch.setattr(U, "neutral_default_boundary", lambda: "last Tuesday")
    with pytest.raises(ValueError, match="ISO date"):
        R._PLACEHOLDER_COMPONENTS_SQL(None)


# --------------------------------------------------------------------------------------------
# the declaration itself
# --------------------------------------------------------------------------------------------

def test_the_defect_is_declared_with_everything_a_reader_needs() -> None:
    d = U.CLOSED_DEFECTS[DEFECT]
    assert d.rows == 59, "the measured size, as audited on production 2026-10-01"
    assert d.boundary == "2026-09-08"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.measured_on)
    assert "75096bab" in d.closed_by, "a boundary must name what establishes it"
    assert "play_priors" in d.closed_by


def test_the_boundary_is_after_the_last_affected_row() -> None:
    """The audit measured the last frozen row at 2026-09-07; a boundary before it would
    silently re-admit the defect's own rows into the receipt."""
    assert U.CLOSED_DEFECTS[DEFECT].boundary > "2026-09-07"


@pytest.mark.parametrize("field", ["reason", "boundary", "closed_by", "measured_on"])
def test_an_incomplete_declaration_is_refused(field: str) -> None:
    kwargs = dict(reason="r", boundary="2026-09-08", closed_by="c", rows=1,
                  measured_on="2026-10-01")
    kwargs[field] = "   "
    with pytest.raises(ValueError):
        U.ClosedDefect(**kwargs)


def test_a_negative_row_count_is_refused() -> None:
    with pytest.raises(ValueError, match="count"):
        U.ClosedDefect(reason="r", boundary="2026-09-08", closed_by="c", rows=-1,
                       measured_on="2026-10-01")


def test_the_declaration_is_immutable() -> None:
    with pytest.raises(TypeError):
        U.CLOSED_DEFECTS["invented"] = U.CLOSED_DEFECTS[DEFECT]  # type: ignore[index]
