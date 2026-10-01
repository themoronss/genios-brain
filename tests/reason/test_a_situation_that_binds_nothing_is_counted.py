r"""Plane D `U06` · a route refusal is counted WITH its dimensions.

⛔ WHAT WAS WRONG. `domain_shadow` counted `counts["no_route"] += 1` and nothing else. *"Twelve
situations found no route"* is one type twelve times or twelve types once — opposite problems,
opposite fixes, and the same number. This layer wrote the rule for itself in L1:
**a count without its dimension is not a measurement.**

⛔ AND THE FLAT TOTAL IS UNCHANGED, DELIBERATELY.
`tests/reason/test_the_cutover_is_declared_before_it_happens.py` asserts on `"no_route": 0` and
scripts read the same key. Replacing a counter to improve it is how a measurement wave breaks the
gate that was watching it.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from genios_engine.packs.compiler.errors import NoExpertiseRoute
from genios_engine.reason import domain_shadow

REPO = pathlib.Path(__file__).resolve().parents[2]


# ── the handler, read structurally ────────────────────────────────────────────────────────────

def _handler() -> ast.ExceptHandler:
    """The `except NoExpertiseRoute` block in `shadow_compile`, from the AST.

    ⛔ AST, NOT A GREP. `shadow_compile` is 700 lines of which most are comments naming the very
    identifiers a grep would match; this session matched a docstring instead of code four times
    before writing the rule into its own tests.
    """
    tree = ast.parse(inspect.getsource(domain_shadow))
    found = [h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)
             and isinstance(h.type, ast.Name) and h.type.id == "NoExpertiseRoute"]
    assert len(found) == 1, f"expected one handler, found {len(found)}"
    return found[0]


def test_the_flat_total_is_still_incremented():
    """Every existing reader of `no_route` keeps working."""
    src = ast.unparse(_handler())
    assert "counts['no_route'] += 1" in src


def test_the_handler_binds_the_exception_so_it_can_read_the_reason():
    """`except NoExpertiseRoute:` with no `as` cannot ask anything of the refusal."""
    assert _handler().name is not None


def test_the_reason_is_read_off_the_exception_and_not_off_its_message():
    """⛔ THE POINT OF `U05`. Until the exception carried a validated reason, the only classifier in
    the codebase told four causes apart with three substring tests and an `else`."""
    src = ast.unparse(_handler())
    assert ".reason" in src
    assert "str(exc)" not in src and "in text" not in src


def test_both_dimensions_are_recorded():
    src = ast.unparse(_handler())
    assert "no_route_by_reason" in src and "no_route_by_type" in src


def test_a_refusal_that_could_not_name_its_type_is_kept_not_dropped():
    """A slice the pass could not dimension must be visible AS that, rather than absent from the
    total — which is what would silently unbalance the two breakdowns."""
    src = ast.unparse(_handler())
    assert "'unknown'" in src


# ── the breakdowns are declared, always ───────────────────────────────────────────────────────

def test_both_breakdowns_are_declared_before_the_loop():
    """⛔ A key that appears only when it fires is a key nobody knows exists. An absent
    `no_route_by_reason` reads as "this build does not measure that"; an empty one reads as
    "nothing was refused", which is the fact."""
    src = inspect.getsource(domain_shadow.shadow_compile)
    assert "no_route_by_reason: dict[str, int] = {}" in src
    assert "no_route_by_type: dict[str, int] = {}" in src


def test_both_reach_the_returned_result():
    src = inspect.getsource(domain_shadow.shadow_compile)
    assert 'result["no_route_by_reason"]' in src
    assert 'result["no_route_by_type"]' in src


def test_they_are_sorted_into_the_result():
    """An unordered mapping in a logged result makes two identical passes diff against each other."""
    src = inspect.getsource(domain_shadow.shadow_compile)
    assert "dict(sorted(no_route_by_reason.items()))" in src
    assert "dict(sorted(no_route_by_type.items()))" in src


def test_they_are_not_stored_inside_the_counter():
    """⛔ `counts` is a `Counter` of ints. A mapping among them makes `most_common()` and
    `Counter.__add__` raise on a type comparison the moment somebody reaches for either."""
    src = inspect.getsource(domain_shadow.shadow_compile)
    assert 'counts.setdefault("no_route_by_reason"' not in src
    assert 'counts["no_route_by_reason"]' not in src


# ── the receipt: the two breakdowns must agree with the total ─────────────────────────────────

def test_the_pass_compares_its_own_two_breakdowns():
    """⛔ Two numbers that are supposed to agree and are never compared eventually disagree — the
    argument `deliver/lane_recall` makes about the per-lane tallies."""
    src = inspect.getsource(domain_shadow.shadow_compile)
    assert "no_route_unbalanced" in src
    assert "sum(no_route_by_reason.values())" in src
    assert "sum(no_route_by_type.values())" in src


def test_the_receipt_does_not_raise():
    """⛔ *"A receipt that can abort the thing it is a receipt for turns an accounting failure into a
    product failure"* — `BundleStore.record_call`, already written down."""
    tree = ast.parse(inspect.getsource(domain_shadow.shadow_compile))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        rendered = ast.unparse(node.test)
        if "no_route_by_reason" not in rendered:
            continue
        raises = [n for n in ast.walk(node) if isinstance(n, ast.Raise)]
        assert not raises, "the balance check raises; it must record and continue"


# ── the arithmetic, driven directly ───────────────────────────────────────────────────────────

def _tally(refusals):
    """Replay the handler's arithmetic over a list of refusals, the way the pass does."""
    flat = 0
    by_reason: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for exc in refusals:
        flat += 1
        by_reason[exc.reason] = by_reason.get(exc.reason, 0) + 1
        key = exc.situation_type if exc.situation_type is not None else "unknown"
        by_type[key] = by_type.get(key, 0) + 1
    return flat, by_reason, by_type


def test_one_type_refused_twelve_times_reads_differently_from_twelve_types_once():
    """The whole unit in one assertion. Both cases give `no_route = 12`."""
    one = [NoExpertiseRoute("x", reason="no_situation_binds_type", situation_type="vendor_renewal")
           for _ in range(12)]
    many = [NoExpertiseRoute("x", reason="no_situation_binds_type", situation_type=f"t{i}")
            for i in range(12)]
    flat_one, _, by_type_one = _tally(one)
    flat_many, _, by_type_many = _tally(many)
    assert flat_one == flat_many == 12
    assert len(by_type_one) == 1 and len(by_type_many) == 12


def test_an_operations_fact_no_longer_shares_a_bucket_with_an_authoring_gap():
    """⛔ THE MIS-ATTRIBUTION `U05` FIXED, ASSERTED HERE AT THE COUNTING LAYER."""
    refusals = [
        NoExpertiseRoute("x", reason="domain_not_activated", situation_type="reply_owed"),
        NoExpertiseRoute("x", reason="no_situation_binds_type", situation_type="reply_owed"),
    ]
    _, by_reason, by_type = _tally(refusals)
    assert by_reason == {"domain_not_activated": 1, "no_situation_binds_type": 1}
    assert by_type == {"reply_owed": 2}, "same type, two different causes — and both are visible"


@pytest.mark.parametrize("n", [0, 1, 7])
def test_the_breakdowns_always_sum_to_the_flat_total(n):
    refusals = [NoExpertiseRoute("x", reason="predicate_rejected", situation_type=f"t{i}")
                for i in range(n)]
    flat, by_reason, by_type = _tally(refusals)
    assert sum(by_reason.values()) == flat == sum(by_type.values()) == n


def test_a_refusal_with_no_type_still_balances():
    flat, by_reason, by_type = _tally([NoExpertiseRoute("x", reason="predicate_rejected")])
    assert flat == 1 and by_type == {"unknown": 1} and sum(by_type.values()) == flat


# ── and no migration was added for it ─────────────────────────────────────────────────────────

def test_no_sixth_funnel_stage_was_minted_for_this():
    """⛔ The funnel's stage vocabulary is closed and check-constrained in `0188`. A route-refusal
    REASON is not a sixth stage — it is the *why* behind an existing drop between
    `situations_formed` and `capability_resolved`. Widening a closed taxonomy to hold a different
    kind of thing is how the taxonomy stops meaning anything."""
    from genios_engine.platform.funnel import STAGES

    assert len(STAGES) == 5
    assert not any("no_route" in s for s in STAGES)


def test_no_migration_was_added_for_a_dashboard_number():
    """Five migrations (0186-0190) are already unapplied in production. A sixth for a returned
    dict key is not the trade to make."""
    migrations = sorted(p.name for p in (REPO / "migrations").glob("0*.sql"))
    assert not any("route" in m and int(m[:4]) > 190 for m in migrations), migrations[-3:]
