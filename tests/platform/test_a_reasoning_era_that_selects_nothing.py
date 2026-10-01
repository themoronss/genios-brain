r"""`U1` · thirty receipts were green while the product had produced no card for six days.

⛔ WHAT HAPPENED, MEASURED 2026-10-01. `L1`, `L2` and `L3` wrote rows on 2026-09-30. `L4` and `L5`
stopped on 2026-09-25. In between, the reasoning layer ran 2,681 times, produced 8,044 candidates —
7,872 of them `disposition='eligible'` — and set `selected_candidate_id` on **none** of them. No
selection means no `signals` row, no signal means `executive/`'s gate matches nothing, and the 150
existing cards aged past their windows.

⛔ AND NOT ONE OF THE THIRTY RECEIPTS SAID SO. Four were green for reasons worth stating:

    #19 more than one candidate is ever considered   = 11      candidates ARE produced
    #21 the system has abstained at least once       = 1,772   ⛔ green BECAUSE of the defect
    #22 decisions become tracked commitments         = 75      green on append-only history
    #14 the live pass has actually run               = 2,376   the pass runs, and emits nothing

`#21` is the one to read twice. Abstention is healthy and that receipt measures that it happens —
so a system abstaining **100% of the time** satisfies it perfectly.

⛔ THE QUESTION IS A CONJUNCTION, NOT A COUNT. A high defer rate is healthy: the previous reasoning
era deferred 8,208 times and still produced 1,157 decisions. The defect is a selection rate of
**exactly zero** over runs that had something to select from.

⛔ AND THE RECEIPT MUST NOT PASS VACUOUSLY. The natural `having count(*) > 0 and count(selected) = 0`
returns no rows when the era produced nothing at all — which reads as "no violation" and would make
this receipt **green on a completely dead pipeline**. That is the failure it exists to prevent, so
an empty era returns `-1` and fails.

⛔ WHAT IT DOES NOT CLAIM. Not the cause. The cause was `GENIOS_L4_LLM_DECISION_MAKER = true` with
the Anthropic spend limit refusing every call and `reason/llm_decision_maker.py:20`'s declared
*"Failure is DEFER, never the formula"* — a deliberate design, not a bug. These tests guard the
question and the three distinct answers; the reason lives in
`speedrun008/YCW27/layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md`.

## Living log — the numbers this file is pinned to

    2026-10-01   the receipt is RED on production, correctly
                   org_66bca8…   480      org_2f1bc0…   849      org_e97e86…  2,253
                   all orgs    3,582
                 ⛔ and with the era bound REMOVED it returns 0 and PASSES — the old era's
                   1,157 selections hide the new era's zero. The bound is not a weakening;
                   it is the entire thing that makes the receipt work.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import textwrap

import pytest

from genios_engine.platform import receipts as R
from genios_engine.platform.receipts import receipts
from genios_engine.reason.unit_health import (REASONING_ERAS, ReasoningEra,
                                              current_reasoning_era)

CLAIM = "the current reasoning era selects, not only defers"


def _receipt(org: str | None = "org_x"):
    found = [r for r in receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, f"expected exactly one {CLAIM!r} receipt, found {len(found)}"
    return found[0]


# ── the three answers must be distinct, and only one of them passes ───────────────

def test_a_selection_rate_of_zero_fails() -> None:
    """N runs had candidates and selected none. The number says how many."""
    assert _receipt().expect(2681) is False
    assert _receipt().expect(1) is False


def test_an_empty_era_fails_rather_than_passing_vacuously() -> None:
    """⛔ THE POINT OF THE WHOLE DESIGN.

    A `having` clause would return no rows for an era with no runs, every caller would read that
    as "no violation", and the receipt would be **green on a dead pipeline** — which is the exact
    state it exists to detect. `-1` is the era saying "I produced nothing", and it fails.
    """
    assert _receipt().expect(-1) is False, (
        "an era that produced no runs at all must FAIL. A receipt that goes green when the "
        "product stops entirely is worse than no receipt, because it is read as reassurance")


def test_at_least_one_selection_passes() -> None:
    assert _receipt().expect(0) is True


def test_the_sql_returns_minus_one_for_an_empty_era_and_not_null() -> None:
    """Structural: the `case` must have the `count(*) = 0 -> -1` arm.

    Asserted on the text of that one branch rather than by running SQL, because a `case` whose
    empty arm is removed falls through to `else 0` and the receipt starts passing on silence —
    a one-token edit with the worst possible consequence.
    """
    sql = " ".join(_receipt().sql.split())
    assert "when count(*) = 0 then -1" in sql, (
        "the empty-era arm is missing; without it an era with no runs returns 0 and PASSES")
    assert "when count(ro.selected_candidate_id) = 0 then count(*)" in sql
    assert "else 0" in sql


# ── the conjunction, not a count ──────────────────────────────────────────────────

def test_it_counts_selections_and_not_defers() -> None:
    """⛔ A high defer rate is HEALTHY. The previous era deferred 8,208 times and produced 1,157
    decisions. A receipt that counted defers would have been red through the product's best
    month."""
    sql = " ".join(_receipt().sql.split())
    assert "selected_candidate_id" in sql
    for forbidden in ("outcome_kind", "'defer'", "defer"):
        assert forbidden not in sql, (
            f"{forbidden!r} in the query — this receipt must not measure DEFERS. Defer is "
            "healthy; a selection rate of exactly zero is not")


def test_it_only_asks_about_runs_that_had_something_to_select() -> None:
    """A run with no candidates cannot select one, and counting it as a failure would make the
    receipt red for every abstention the layer is designed to make."""
    sql = " ".join(_receipt().sql.split())
    assert "exists" in sql and "reasoning_candidates" in sql, (
        "the query must restrict to runs that produced candidates — otherwise a correct "
        "abstention is indistinguishable from a failure to select")


# ── the boundary comes from the declaration, never a literal ──────────────────────

def test_the_builder_imports_the_era_rather_than_restating_the_date() -> None:
    source = textwrap.dedent(inspect.getsource(R._ERA_SELECTS_NOTHING_SQL))
    tree = ast.parse(source)
    body = tree.body[0]
    assert isinstance(body, ast.FunctionDef)

    imported = {node.module for node in ast.walk(body) if isinstance(node, ast.ImportFrom)}
    assert "genios_engine.reason.unit_health" in imported, (
        "the boundary must be imported from the declaration that owns it, so the receipt cannot "
        "drift by carrying its own copy — the rule `neutral_default_boundary` established")

    # ⛔ AST, AND THE DOCSTRING IS EXCLUDED BY IDENTITY, NOT BY VALUE. `ast.get_docstring`
    # returns the CLEANED text while the node holds the raw one, so comparing them lets the
    # docstring through and this assertion fails on its own prose — which is exactly what it did
    # on the first run. The docstring is the first statement; excluding that node is exact.
    docstring_node = (body.body[0].value
                      if body.body and isinstance(body.body[0], ast.Expr)
                      and isinstance(body.body[0].value, ast.Constant) else None)
    literals = [node.value for node in ast.walk(body)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node is not docstring_node]
    assert literals, "no string literals found — the AST walk is not reaching the body"
    for text in literals:
        assert not re.search(r"\d{4}-\d{2}-\d{2}", text), (
            f"an ISO date is inlined in the builder's code: {text[:60]!r}. The era owns the date")


def test_the_boundary_actually_REACHES_the_sql() -> None:
    """⛔ THE HALF-GUARD THIS FILE SHIPPED WITH, AND THE MUTATION THAT FOUND IT.

    `test_the_builder_imports_the_era_rather_than_restating_the_date` proves the boundary is
    **imported**. It does not prove it is **used**. Replacing the whole `where ro.created_at >=
    '{boundary}'` clause with `where 1=1` left the import in place, and **all fifteen tests
    passed** — while on production the receipt went from 3,582 (correctly red) to 0 (green), because
    the previous era's 1,157 selections hide the current era's zero.

    > ⛔ **Declared and written are two directions, and one alone is half a guard.** The boundary
    > being imported is the declaration; the boundary being in the predicate is the writing.

    So this asserts the generated SQL contains the live boundary **and** that it bounds
    `created_at`, which is the column that makes it an era rather than a filter on something else.
    """
    boundary = current_reasoning_era().boundary
    sql = " ".join(_receipt().sql.split())

    assert boundary in sql, (
        f"the era boundary {boundary!r} is imported but never reaches the query. Without it this "
        "receipt averages the live implementation with a retired one and goes GREEN on a stopped "
        "product — measured: 3,582 red becomes 0 green")
    assert f"ro.created_at >= '{boundary}'" in sql, (
        "the boundary must bound `created_at`. Bounding anything else is a filter, not an era")
    assert "where 1=1" not in sql, "the era bound was replaced by a tautology"


def test_a_boundary_that_is_not_a_date_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The date is interpolated into SQL, so its shape is checked before it goes in."""
    import genios_engine.reason.unit_health as H
    monkeypatch.setattr(H, "REASONING_ERAS",
                        (ReasoningEra(boundary="2026-09-29'; drop table cards; --",
                                      what_changed="x", measured="y"),))
    with pytest.raises(ValueError, match="ISO date"):
        R._ERA_SELECTS_NOTHING_SQL(None)


def test_the_receipt_calls_the_builder_rather_than_inlining_sql() -> None:
    source = textwrap.dedent(inspect.getsource(R.receipts))
    assert "_ERA_SELECTS_NOTHING_SQL(org)" in source, (
        "the receipt must call the builder — a copy of the SQL in the list is a second place the "
        "era boundary can go stale")


# ── the era declaration itself ────────────────────────────────────────────────────

def test_the_era_is_declared_with_everything_a_reader_needs() -> None:
    era = current_reasoning_era()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", era.boundary)
    assert era.what_changed and era.measured, (
        "an era boundary with no statement of what changed and no measurement is a magic date")
    assert "reasoning_reasoner_results" in era.what_changed, (
        "what_changed must name the thing a reader can go and check")
    assert "12,170" in era.measured and "2,681" in era.measured, (
        "the measurement that established the boundary must be in it, not in a commit message")


def test_the_current_era_is_the_last_one_and_the_list_is_append_only() -> None:
    """Newest LAST. A new implementation appends; the boundary of a past era is a fact about
    history and a receipt that cited it must keep citing the same number."""
    assert current_reasoning_era() is REASONING_ERAS[-1]
    boundaries = [e.boundary for e in REASONING_ERAS]
    assert boundaries == sorted(boundaries), "REASONING_ERAS must be ordered oldest-first"
    assert len(set(boundaries)) == len(boundaries), "two eras cannot share a boundary"


def test_the_era_declaration_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        current_reasoning_era().boundary = "2026-01-01"       # type: ignore[misc]


# ── and it is wired like every other receipt ──────────────────────────────────────

def test_it_is_an_l2_receipt_and_org_filtered() -> None:
    r = _receipt("org_x")
    assert r.layer == "L2"
    assert r.fleet_wide is False, (
        "the selection rate differs per tenant, so this question is not fleet-wide")
    assert ":org" in r.sql
    assert ":org" not in _receipt(None).sql, "no org, no filter"


def test_the_detail_names_the_consequence_and_the_minus_one() -> None:
    detail = _receipt().detail
    assert "no card" in detail, "the detail must say what a reader loses, not restate the query"
    assert "-1" in detail, (
        "the detail must explain the -1, because an operator seeing it needs to know it is a "
        "different sentence from a zero selection rate")


def test_the_receipt_count_went_to_thirty_one() -> None:
    """A literal, so the next change to this list is deliberate. 30 -> 31 on 2026-10-01."""
    assert len(receipts(None)) == 31
