"""No test may find a receipt by a substring that matches more than one claim.

⛔ FOUND BY BREAKING, 2026-10-03. `tests/deliver/test_nothing_dies_of_low_confidence.py` looked up
its receipt with `[r for r in receipts(None) if "lane" in r.claim][0]` and asserted
`receipt.layer == "L5"`. Three claims contain that substring:

    [L5] every delivered card carries a lane, or is labelled unrouted   ← the one it meant
    [L6] the delivery control plane has run                             ⛔ `lane` inside `plane`
    [L1] no warm-lane row is parked where nothing can see it            ⛔ added that day

⛔⛔ **It had been one receipt-ordering away from testing the wrong receipt since the L6 claim was
written**, and it passed only because the intended one happened to come first. *A grep hands over a
sentence without its subject* — and `[0]` of a substring match is that grep.

⛔ THE RULE, NOT THE REWRITE. Five other lookups use the same idiom and **all five are unique**,
measured below rather than assumed. So nothing is rewritten; this guard makes the next collision
fail loudly, in one named place, instead of inside whichever test happens to lose the ordering.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from genios_engine.platform.receipts import receipts

_TESTS = Path(__file__).resolve().parents[1]
_SELF = Path(__file__).name


def lookups_in(source: str) -> frozenset[str]:
    """The substrings a module uses to SELECT a receipt. Pure, so the branches can be tested.

    ⛔ EXTRACTED BECAUSE A MUTATION SURVIVED. Making the `receipts(...)` check unconditional changed
    no answer, since today every `"x" in …claim` filter happens to sit in a receipts comprehension
    — so the branch was defence-in-depth with no failing mutation. ⛔ Rather than delete a check
    that WILL matter the first time something else is iterated with a `.claim` filter, the scan
    became a function over source text, and the tests below exercise both branches directly.
    *One implementation, tested directly* — the same repair as `table_coverage.set_columns`.
    """
    out: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:                    # pragma: no cover - the suite parses
        return frozenset()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            continue
        over_receipts = any(
            isinstance(gen.iter, ast.Call)
            and (getattr(gen.iter.func, "id", None) == "receipts"
                 or getattr(gen.iter.func, "attr", None) == "receipts")
            for gen in node.generators)
        if not over_receipts:
            continue
        for gen in node.generators:
            for condition in gen.ifs:
                for inner in ast.walk(condition):
                    if not (isinstance(inner, ast.Compare) and len(inner.ops) == 1
                            and isinstance(inner.ops[0], ast.In)):
                        continue
                    left, right = inner.left, inner.comparators[0]
                    if (isinstance(left, ast.Constant) and isinstance(left.value, str)
                            and isinstance(right, ast.Attribute) and right.attr == "claim"):
                        out.add(left.value)
    return frozenset(out)


def _lookups() -> dict[str, set[str]]:
    """``{substring: {file, …}}`` for every `"…" in <x>.claim` **in code**.

    ⛔ IT IS THE COMPREHENSION'S FILTER, NOT EVERY `in …claim`. The second version counted any
    `"x" in <y>.claim` comparison and reported a collision at
    `tests/reason/test_a_unit_that_says_nothing_is_not_working.py:210` — which is
    `assert "declared" in receipt.claim`, an assertion about an **already-selected** receipt and
    perfectly safe. ⛔ **Selecting a receipt by substring is the defect; asserting a word appears in
    one you already hold is not**, and conflating them is the same mistake in a different coat: a
    pattern that matches the shape without its subject. So this walks only the `ifs` of a
    comprehension whose iterable is a `receipts(...)` call.

    ⛔ READ FROM THE AST, AND THE FIRST VERSION WAS A REGEX OVER THE FILE TEXT. It matched the
    repair comment in `tests/deliver/test_nothing_dies_of_low_confidence.py`, which quotes the old
    idiom `if "lane" in r.claim` **in order to explain why it was removed** — so the guard reported
    a collision that no longer existed in any code. ⛔ **Fifth time in this programme that a
    text-level guard broke on the sentence documenting the thing it forbids**, and the rule for it
    was already written in `tests/README.md`: *a claim about PROSE needs attribution, a claim about
    CODE needs the AST.* A comment cannot be a lookup, and a `Compare` node cannot be a comment.
    """
    out: dict[str, set[str]] = {}
    for path in sorted(_TESTS.rglob("*.py")):
        if path.name == _SELF:
            continue                       # this file names the idiom in order to forbid it
        for substring in lookups_in(path.read_text(encoding="utf-8")):
            out.setdefault(substring, set()).add(str(path.relative_to(_TESTS)))
    return out


def test_the_scan_finds_the_idiom_at_all():
    """A guard that measures nothing passes forever."""
    found = _lookups()
    assert found, "no substring receipt lookup found — either they are all gone (then delete this " \
                  "file deliberately) or the pattern stopped matching"
    assert len(found) >= 4, sorted(found)


@pytest.mark.parametrize("substring", sorted(_lookups()))
def test_every_substring_lookup_matches_exactly_one_claim(substring):
    claims = [r.claim for r in receipts("org_probe")]
    hits = [c for c in claims if substring in c]
    assert len(hits) == 1, (
        f'⛔ `if "{substring}" in r.claim` matches {len(hits)} receipts: {hits}. Used by '
        f'{sorted(_lookups()[substring])}. ⛔ Either name the exact claim at that site, or assert '
        f'`len(found) == 1` there — a lookup that takes `[0]` of an ambiguous match tests whichever '
        f'receipt happens to be first, and the answer changes when any receipt is added above it')


def test_a_substring_that_matches_nothing_is_also_a_failure():
    """⛔ The other direction: a claim reworded out from under a lookup leaves a test asserting
    about an empty list, which several of these sites would do with `[0]` — an IndexError, not a
    diagnosis."""
    claims = [r.claim for r in receipts("org_probe")]
    orphans = [s for s in _lookups() if not any(s in c for c in claims)]
    assert not orphans, (
        f"these lookups match no receipt at all: {orphans}. A claim was reworded and the test "
        "that depended on it now asserts about nothing")


def test_the_known_collision_is_what_it_was_measured_to_be():
    """⛔ Pins the instance, so the doctrine keeps its evidence: `lane` really does appear in three
    claims, one of them inside the word `plane`."""
    claims = [r.claim for r in receipts("org_probe")]
    lane = [c for c in claims if "lane" in c]
    assert len(lane) >= 3, lane
    assert any("plane" in c for c in lane), (
        "the `delivery control plane` claim is gone — the clearest half of this evidence with it")


# ── the scanner's own branches, exercised directly ─────────────────────────────────────────────

def test_a_comprehension_over_receipts_is_a_lookup():
    assert lookups_in('x = [r for r in receipts(None) if "abc" in r.claim]') == frozenset({"abc"})
    assert lookups_in('x = [r for r in R.receipts(org) if "abc" in r.claim]') == frozenset({"abc"})


def test_a_comprehension_over_something_else_is_NOT_a_lookup():
    """⛔ THE BRANCH WHOSE MUTATION SURVIVED, NOW LOAD-BEARING. A `.claim` filter over anything but
    `receipts(...)` is not a receipt lookup, and counting it would report collisions about rows
    that are not receipts."""
    assert lookups_in('x = [c for c in catalogue() if "abc" in c.claim]') == frozenset()
    assert lookups_in('x = [c for c in RECEIPT_PACKAGE if "abc" in c.claim]') == frozenset()


def test_an_assertion_about_a_selected_receipt_is_NOT_a_lookup():
    """⛔ The false positive the second version produced: `assert "declared" in receipt.claim` is a
    statement about a receipt already in hand."""
    assert lookups_in('assert "declared" in receipt.claim') == frozenset()


def test_a_comment_quoting_the_idiom_is_NOT_a_lookup():
    """⛔ The false positive the FIRST version produced, and the fifth time in this programme a
    text-level guard broke on the sentence documenting the thing it forbids."""
    assert lookups_in('# was: [r for r in receipts(None) if "lane" in r.claim]\nx = 1') == frozenset()
    assert lookups_in('"""doc: if "lane" in r.claim was removed."""\nx = 1') == frozenset()
