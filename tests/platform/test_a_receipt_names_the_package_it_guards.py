r"""Guards per package is DATA now — and the package `STEP-10` sent me to was the wrong one.

⛔ WHAT WAS WRONG. `STEP-10` claimed *"L5 is 9,431 lines and carried 2 of the programme's 33
receipts — 4,715 lines per guard against L4's 881"*, and **three of those numbers were wrong**:
`deliver/` carried **5**, lines per guard was **1,886**, and **four** of the five worked rather than
one. The count was derived once, by hand, by filtering on `Receipt.layer` — and
`genios_engine/LAYERS.py` warns in its own docstring: *"Atlas 5.2 is our `deliver` (6), and Atlas 6
is our `feedback` (7) — **so always name the package, never the digit alone**."* The filter named the
digit.

⛔ The wrong number then appeared in **eleven documents**, and **no assertion depended on it** —
which is exactly why it survived review. *A claim worth asserting is worth storing as data.*

⛔⛔ AND THE NUMBER POINTED AT THE WRONG PACKAGE. Measured from the declaration:

    feedback     9 receipts   5 correctness    4,040 lines        448 lines per guard
    reason       8            5               41,363            5,170
    deliver      7            5               10,020            1,431
    capture      5            5               47,184            9,436
    context      2            2               50,877   ⛔⛔    25,438
    executive    2            1                6,230            3,115
    platform     1            1               11,950           11,950
    packs        1            0                8,188            8,188

⛔ **`context/` is 50,877 lines with TWO guards.** `STEP-10` spent a whole step on `deliver/`
because a hand-derived number said 4,715 — and `context/` is **5.4× worse than that**, 13× worse
than `deliver/`'s real figure at the time, and `deliver/` is now the third-best covered package in
the product.

⛔ THE MAPPING IS DECLARED, NOT PARSED, AND THAT WAS MEASURED FIRST. An outer-`from` resolver fails
on **4 of 40** receipts — each reads `select … from ( <subquery> )`, a derived table whose real
source is inside the parentheses. Two earlier parsing attempts produced confident wrong answers:
`[a-z_]+` stops at the digit in `l2_convergence` and reports table `l`, and `jsonb_each` is a
function. *A resolver that is merely stricter is not more correct.*

⛔ A THIRD CATEGORY EXISTS. Some claims go red for reasons **no package can fix** — a tenant with no
seats, no manager, no pack binding, no channel. Calling those `deliver/`'s or `context/`'s guards
would inflate a package's coverage with work it cannot do, so they are declared `READINESS` and
counted separately.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from genios_engine.LAYERS import CROSS_CUTTING, LAYERS
from genios_engine.platform import receipt_coverage as C
from genios_engine.platform.receipts import receipts

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENGINE = _ROOT / "genios_engine"
_VALID = frozenset(LAYERS) | CROSS_CUTTING | {C.READINESS}


def _lines(package: str) -> int:
    directory = _ENGINE / package
    if not directory.exists():
        return 0
    return sum(1 for f in directory.rglob("*.py")
               for _ in f.read_text(encoding="utf-8", errors="ignore").splitlines())


# =============================================================================================
# 1 · both directions, and the two faults they caught
# =============================================================================================

def test_every_receipt_declares_the_package_it_guards() -> None:
    """⛔ A new receipt with no entry fails the build, so nobody's coverage changes unnoticed."""
    assert C.undeclared_receipts() == (), (
        f"receipts with no declared package: {C.undeclared_receipts()}")


def test_no_declaration_names_a_claim_that_no_longer_ships() -> None:
    """⛔ THE SECOND DIRECTION, AND IT CAUGHT ME TWICE ON THE FIRST RUN. I built the declaration
    from a dump that truncated each claim at 62 characters, so two keys were cut short —
    *"…is written or declared"* for *"…is written or declared unwritten"*, and *"…not promised"*
    for *"…not placeholders"*. Direction one reported them as undeclared and direction two as
    stale, naming both halves of the same mistake.

    ⛔ *A totality guard that runs one way is half a guard* — and the half that is easy to skip is
    the half that found this."""
    assert C.stale_declarations() == (), (
        f"declared claims the receipts no longer ship: {C.stale_declarations()}")


def test_no_two_receipts_share_a_claim() -> None:
    """⛔ `receipts()` is a list and nothing stops two entries carrying the same claim — at which
    point a dict keyed on the claim silently loses one and the count under-reports. The guard that
    makes this mapping trustworthy has to rule that out rather than assume it."""
    assert C.duplicate_claims() == (), f"claims shared by two receipts: {C.duplicate_claims()}"


@pytest.mark.parametrize("claim", sorted(C.RECEIPT_PACKAGE))
def test_every_entry_names_a_real_package_and_a_usable_reason(claim: str) -> None:
    package, why = C.RECEIPT_PACKAGE[claim]
    assert package in _VALID, f"{claim!r} names {package!r}, which is not a package or readiness"
    assert len(why) >= 30, f"{claim!r}'s reason says nothing usable"


def test_no_reason_is_thin() -> None:
    assert C.thin_declarations() == ()


# =============================================================================================
# 2 · ⛔ the STEP-10 correction, pinned
# =============================================================================================

def test_deliver_is_not_the_two_receipt_desert_step_10_was_motivated_by() -> None:
    """⛔ The corrected number, asserted so the retracted one cannot be reinstated by a reader of
    the old documents. `STEP-10` said 2; it was 5 then and is 7 now."""
    per = C.receipts_per_package()
    assert per["deliver"] >= 5, "deliver/'s coverage has fallen below what STEP-10 measured wrongly"
    assert _lines("deliver") // per["deliver"] < 4715, (
        "deliver/ is back above the lines-per-guard figure STEP-10 claimed — which was never true")


def test_context_is_the_worst_covered_package() -> None:
    """⛔⛔ THE FINDING THIS MODULE EXISTS TO SURFACE, asserted so it cannot be lost in prose the
    way `STEP-10`'s number was. `context/` is the largest package in the engine and carries two
    guards.

    ⛔ Asserted as a RANKING, not a number: the line count grows every week and a pinned threshold
    would rot. If another package overtakes it, this fails and the new worst case is read
    deliberately."""
    per = C.receipts_per_package()
    ratios = {pkg: _lines(pkg) // n for pkg, n in per.items()
              if pkg != C.READINESS and _lines(pkg)}
    worst = max(ratios, key=lambda p: ratios[p])
    assert worst == "context", f"the worst-covered package is now {worst} at {ratios[worst]:,}"
    assert ratios["context"] > ratios["deliver"] * 5, (
        "context/ is no longer dramatically worse than the package STEP-10 was alarmed about")


def test_the_package_is_never_derived_from_the_layer_label() -> None:
    """⛔ THE GUARD AGAINST THE METHOD THAT PRODUCED THE WRONG NUMBER. `Receipt.layer` is a
    hand-written string carrying two vocabularies — `944b4f76` *("all seven layers")* used
    `LAYERS.py`'s numbering and `22d598b1` *("all six product layers")* mixed the Atlas's into the
    same field. This module must not consult it."""
    tree = ast.parse((_ENGINE / "platform" / "receipt_coverage.py").read_text(encoding="utf-8"))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "layer" not in attrs, "receipt_coverage reads Receipt.layer — the STEP-10 method"


def test_the_layer_label_is_left_alone() -> None:
    """⛔ And nothing here relabels a receipt. `receipts(layer)` filters on that string, so a
    relabel changes which receipts an operator's layer-scoped run executes — a decision, not a
    tidy-up."""
    labels = {r.layer for r in receipts(None)}
    assert labels == {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}, (
        f"the layer labels changed: {sorted(labels)} — that is a behaviour change, not a fix")


# =============================================================================================
# 3 · ⛔ why the mapping is declared and not parsed
# =============================================================================================

def test_an_outer_from_resolver_cannot_answer_for_every_receipt() -> None:
    """⛔ THE MEASUREMENT THAT JUSTIFIES THE HAND DECLARATION. Four receipts read
    `select … from ( <subquery> )`, so a depth-zero `from` scan finds a derived table and no source
    at all. Pinned as a floor, so a fifth such receipt does not quietly make parsing look viable."""
    unresolved = []
    for receipt in receipts(None):
        sql = " ".join(receipt.sql.split())
        depth, outer = 0, None
        for m in re.finditer(r"\(|\)|\bfrom\s+([a-z_][a-z0-9_.]*)", sql, re.I):
            token = m.group(0)
            if token == "(":
                depth += 1
            elif token == ")":
                depth -= 1
            elif depth == 0 and outer is None:
                outer = m.group(1)
        if outer is None:
            unresolved.append(receipt.claim)
    assert len(unresolved) >= 4, (
        "fewer than four receipts defeat an outer-from scan — re-read whether parsing is now "
        f"viable rather than keeping a hand declaration. Unresolved: {unresolved}")


def test_a_name_shaped_regex_still_misreads_a_table() -> None:
    """⛔ The other half of the same lesson, pinned. `[a-z_]+` cannot match a digit, so it reports
    `l2_convergence` as table `l` — a confident wrong answer, twice in this programme."""
    assert re.match(r"[a-z_]+", "l2_convergence").group(0) == "l"
    assert re.match(r"[a-z_][a-z0-9_.]*", "l2_convergence").group(0) == "l2_convergence"


# =============================================================================================
# 4 · the readiness category, and the correctness split
# =============================================================================================

def test_readiness_receipts_are_all_presence_checks() -> None:
    """⛔ Right by construction: a readiness gate asks *"has a human done the thing"*, so zero is
    the failure. If one ever becomes a correctness check it is no longer readiness."""
    assert C.correctness_per_package().get(C.READINESS, 0) == 0
    assert C.receipts_per_package()[C.READINESS] >= 5


def test_no_readiness_claim_is_blamed_on_a_package() -> None:
    """⛔ `org_seats`, `org_channels` and `tenant_packs` are written by `api/` or activated by a
    human. Forcing them into a package would inflate that package's coverage with work it cannot
    do — which is the opposite of what this module is for."""
    for claim in ("the tenant has at least one active seat",
                  "at least one seat has a manager",
                  "there is a channel this tenant can be reached on",
                  "the tenant is bound to a pack"):
        assert C.RECEIPT_PACKAGE[claim][0] == C.READINESS, claim


def test_feedback_carries_the_correctness_receipts_s5_to_s7_built() -> None:
    """⛔ The L6 re-crosscheck measured `feedback/` at **four receipts, all presence**. Asserted as
    a floor so a later step can add more without editing this."""
    assert C.correctness_per_package()["feedback"] >= 5


def test_every_package_with_a_receipt_is_counted_once() -> None:
    """The totals must reconcile: every live claim is either declared to a package or to readiness,
    and the per-package counts sum to the number of receipts."""
    assert sum(C.receipts_per_package().values()) == len(C.live_claims())
    assert len(C.live_claims()) == len(C.RECEIPT_PACKAGE)


def test_packs_has_no_correctness_receipt_and_that_is_declared() -> None:
    """⛔ Recorded rather than fixed here: `packs/` is 8,188 lines with one PRESENCE receipt
    (*"compiled expertise packages exist"*). Naming it is the point — a package nobody asks a
    correctness question of is the state `feedback/` was in before `S5`."""
    assert C.receipts_per_package()["packs"] == 1
    assert C.correctness_per_package().get("packs", 0) == 0
