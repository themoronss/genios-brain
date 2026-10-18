"""⛔⛔ U01 · Atlas L1-08 — *"`RawObject`, `SourceEvent` and `GatedEvent` do not require visibility."*

Literally true: all three declare the field and all three default it to `None`. ⛔ The scorecard's
evidence line said *"zero declare a `visibility` field"*, which is a **different and false** claim —
optional is not absent, and the two have different fixes. This file pins the correction.

✅ The consequence the claim implies does not happen, because four layers refuse before `None` can
reach a reader: the landing seam derives, **the gate PARKS** (`visibility_unknown`), a re-drain
stays `STILL_BLOCKED`, and the schema is NOT NULL on five of six columns with the sixth paired to
`visibility_scope text NOT NULL DEFAULT 'private'`.

⛔⛔ AND THAT IS WHY THIS FILE EXISTS. Three sites in `context/` read a missing audience as
**permitted** and two more default it to **org-wide**. They are correct *only because* those four
refusals mean they never see a `None`, and nothing connected them to that fact. The safety of a
privacy default rested on one `if` in one file.

⛔ THE SITES WERE FOUND BY AST, NOT GREP, and that is the backward half of the guard. A first pass
by grep found **five**; the AST sweep found **eight**. The three extra are `visibility_principals or
()`, which is a different question — and measuring rather than assuming showed them **fail-closed**:
a `private` scope with an empty principal list is visible to **nobody**. That is asserted here, not
trusted.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from genios_engine.context import fact_visibility as FV
from genios_engine.contracts.visibility import Visibility

SITES = FV.MISSING_VISIBILITY_SITES
REFUSALS = FV.MISSING_VISIBILITY_REFUSALS
CONTEXT = Path(FV.__file__).resolve().parent
ENGINE = CONTEXT.parent
REPO = ENGINE.parent


def _is_visibility_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr.startswith("visibility")
    return isinstance(node, ast.Name) and node.id.startswith("visibility")


def _resolving_sites(path: Path) -> list[int]:
    """Lines where a MISSING audience is resolved without refusing.

    Two shapes, both `BoolOp(Or)`:
      A  `x.visibility is None or …`      -- None reads as permitted
      B  `visibility or <default>`         -- None takes a chosen default
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:                                         # pragma: no cover
        return []
    out: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        first = node.values[0]
        if (isinstance(first, ast.Compare) and len(first.ops) == 1
                and isinstance(first.ops[0], ast.Is) and _is_visibility_expr(first.left)
                and isinstance(first.comparators[0], ast.Constant)
                and first.comparators[0].value is None):
            out.append(node.lineno)
        elif _is_visibility_expr(first):
            out.append(node.lineno)
    return sorted(out)


# ------------------------------------------------------------------ the site table, both ways

def test_the_table_is_not_empty_and_covers_more_than_one_module():
    """⛔ An empty table makes every assertion over it vacuous -- the hole that let a mutation
    survive in `1.4`."""
    assert len(SITES) >= 6, sorted(SITES)
    assert sum(count for count, _v, _m in SITES.values()) >= 8


def test_every_declared_module_still_has_the_declared_number_of_sites():
    """Forward. ⛔ The COUNT is declared, not just the module, so a SECOND site added to an
    already-declared module cannot slip through on the strength of the first."""
    for module, (count, _verdict, _mover) in sorted(SITES.items()):
        path = CONTEXT / module
        assert path.exists(), f"{module} is declared and does not exist"
        found = _resolving_sites(path)
        assert len(found) == count, (
            f"{module} declares {count} site(s) and the AST finds {len(found)} at lines {found}. "
            "Either a site was added -- read what a missing audience means there before raising "
            "the number -- or one was fixed, and the entry should go")


def test_no_module_resolves_a_missing_audience_undeclared():
    """⛔⛔ Backward, and the direction that matters: this is the one that catches a NEW site.

    One direction alone is how `mcp/` escaped the import ratchet in L3-01.
    """
    undeclared = {}
    for path in sorted(CONTEXT.rglob("*.py")):
        module = path.relative_to(CONTEXT).as_posix()
        if module in SITES:
            continue
        found = _resolving_sites(path)
        if found:
            undeclared[module] = found
    assert not undeclared, (
        f"modules resolving a missing audience with no declaration: {undeclared}. Add them to "
        "`MISSING_VISIBILITY_SITES` with what `None` means there -- open, org-wide or fail-closed "
        "-- or make the site refuse")


def test_every_entry_is_graded_and_carries_a_house_form_mover():
    for module, (count, verdict, mover) in SITES.items():
        assert isinstance(count, int) and count >= 1, f"{module}: {count!r}"
        assert verdict.startswith(("⛔", "✅")), f"{module}: ungraded -- {verdict[:40]!r}"
        assert mover.startswith(("MOVES WHEN", "MOVES WITH")), f"{module}: {mover[:40]!r}"


def test_the_open_sites_are_graded_open_and_not_quietly_reworded():
    """⛔ These three are the finding. If any were regraded ✅ without the code changing, the
    declaration would be hiding exactly what it was written to show."""
    for module in ("framing/timeline.py", "framing/headline.py", "fact_visibility.py"):
        assert SITES[module][1].startswith("⛔"), module


def test_the_fail_closed_sites_are_graded_closed_and_each_one_is_PROVEN_closed():
    """⛔⛔ FOUND BY A SURVIVING MUTATION, AND IT WAS A REAL HOLE. `test_the_open_sites_are_graded_open`
    existed and its converse did not, so flipping `correlation_people.py` from ✅ to ⛔ -- or the
    other way, which is the dangerous direction -- passed every test.

    ⛔ And a grade is not taken on trust: each ✅ entry has to name the mechanism that closes it,
    and the mechanism itself is exercised by
    `test_a_private_scope_with_no_principals_is_visible_to_NOBODY`.
    """
    closed = {m for m, (_c, v, _mv) in SITES.items() if v.startswith("✅")}
    assert closed == {"correlation_people.py", "graph_store.py"}, (
        f"the fail-closed set is now {sorted(closed)}. Both directions matter: a site regraded "
        "✅ without the code changing hides the finding, and one regraded ⛔ without cause sends "
        "the next reader after a defect that is not there")
    for module in closed:
        verdict = SITES[module][1]
        assert "principal" in verdict.lower(), (
            f"{module} is graded fail-closed and does not name WHY -- an empty principal list "
            "excluding is the whole mechanism, and it is the thing that could change")


def test_situation_bso_is_graded_on_BOTH_of_its_shapes():
    """⛔ It holds three sites of two different kinds, and an entry that mentioned only one would
    read as a complete answer about the module."""
    _count, verdict, _mover = SITES["situation_bso.py"]
    assert "ORG" in verdict or "org" in verdict
    assert "FAIL-CLOSED" in verdict or "fail-closed" in verdict
    # ⛔ FOUND BY A SURVIVING MUTATION. Checking for the WORD "fail-closed" is not checking that
    # the entry explains it: stripping the explanation left the word standing. The entry has to
    # name the mechanism, which is the empty principal list, and the scope it sits under.
    assert "principal" in verdict.lower() and "private" in verdict.lower(), (
        "the entry names a fail-closed site without naming what closes it. `principals or ()` "
        "under a `private` scope is the mechanism, and it is what a re-reader has to check")


# -------------------------------------------------- the four refusals that make the sites safe

def test_all_four_refusals_are_declared_with_a_place():
    assert set(REFUSALS) == {"1-derive", "2-park", "3-still-blocked", "4-not-null"}, sorted(REFUSALS)
    for key, (what, where) in REFUSALS.items():
        assert where, key
        # ⛔⛔ FOUND BY A SURVIVING MUTATION, AND I HAD ALREADY LEARNED THIS ONCE. Step `2.1`
        # replaced an `assert len(why) > 80` for exactly this reason -- length is not content --
        # and this file was written with `len(what) > 40` anyway. A rule learned in a doctrine
        # table is not a rule applied.
        #
        # Each refusal now has to name the thing it refuses WITH: the verb or the artefact a
        # re-reader would go and look at. Derived from the place, not spelled per entry.
        leaf = where.rstrip("/").split("/")[-1].removesuffix(".py")
        hint = {"normalize": ("deriv",), "gate": ("park",),
                "recapture": ("still_blocked", "re-drain", "redrain"),
                "migrations": ("not null",)}[leaf]
        assert any(h in what.lower() for h in hint), (
            f"{key} points at {where} and its statement names none of {hint}. A refusal that does "
            "not say what it refuses with cannot be re-measured")
        # ⛔ A MUTATION SURVIVES HERE AND IT IS LEFT SURVIVING ON PURPOSE. Weakening the
        # `4-not-null` statement from "five of the six columns are NOT NULL" to "are constrained"
        # passes, because the entry still names NOT NULL further along (in the scope default) and
        # because the hint is a disjunction.
        #
        # ⛔ Tightening it would mean asserting the COUNT in the prose -- and `2.1` produced the
        # rule that *a comment's count ages faster than its claim*, having found a module docstring
        # saying "the four writers" where there were eight callers. So the prose is deliberately
        # the weaker guard: the fact it describes is measured independently and from the source of
        # truth by `test_the_schema_refuses_it_independently_of_the_code`, which parses the
        # migrations, requires at most one nullable column, and requires that one to sit beside a
        # fail-closed scope default. ⛔ If that test ever goes, this one stops being belt to its
        # braces and the count has to move into code, not into a sentence.


def test_the_landing_seam_still_derives():
    """⛔ FOUND BY A SURVIVING MUTATION. The first version asserted `"derive_visibility" in source`
    -- a substring, which an `import derive_visibility as _unused` satisfies perfectly while
    nothing calls it. *A call that is syntactically present is not a call that is made*, and the
    weaker form of that rule is that a NAME present is not a call at all.
    """
    tree = ast.parse((ENGINE / "capture" / "landing" / "normalize.py").read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ((isinstance(node.func, ast.Name) and node.func.id == "derive_visibility")
             or (isinstance(node.func, ast.Attribute) and node.func.attr == "derive_visibility"))
    ]
    assert calls, (
        "`derive_visibility` is not CALLED in the landing seam. Refusal 1 is gone, and every "
        "event now reaches the gate with whatever the connector happened to attach")


def test_THE_GATE_STILL_PARKS_AN_UNDERIVABLE_AUDIENCE():
    """⛔⛔ THE LOAD-BEARING REFUSAL. By AST over the gate's own body, not by substring: a comment
    mentioning the reason code must not be able to satisfy this.

    If this fails, the three OPEN sites in `context/` are no longer safe and this is not a test
    to adjust -- it is the privacy default of the product.
    """
    gate = ENGINE / "capture" / "gate" / "gate.py"
    tree = ast.parse(gate.read_text(encoding="utf-8"))
    parks = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "GateResult"
        and any(kw.arg == "action" and isinstance(kw.value, ast.Constant)
                and kw.value.value == "park" for kw in node.keywords)
        and any(kw.arg == "reason_code" and isinstance(kw.value, ast.Constant)
                and kw.value.value == "visibility_unknown" for kw in node.keywords)
    ]
    assert parks, (
        "the gate no longer returns `GateResult(action='park', "
        "reason_code='visibility_unknown')`. Every OPEN site in MISSING_VISIBILITY_SITES depended "
        "on it, and by Layer 2 the recipient list is gone -- nothing downstream can re-derive")


def test_a_redrain_stays_blocked_rather_than_ageing_the_park_out():
    source = (ENGINE / "capture" / "parked" / "recapture.py").read_text(encoding="utf-8")
    assert "STILL_BLOCKED" in source
    assert "no visibility rule covers source" in source, (
        "the re-drain no longer refuses by name; a park that quietly ages out is a park that "
        "published under a guess")


def test_the_schema_refuses_it_independently_of_the_code():
    """⛔ Counted from the migrations, not asserted from memory -- and the ONE nullable column has
    to be the one paired with a fail-closed scope default."""
    columns: list[tuple[str, str]] = []
    for sql in sorted((REPO / "migrations").glob("*.sql")):
        for line in sql.read_text(encoding="utf-8").splitlines():
            if re.match(r"\s*visibility\s+jsonb", line):
                columns.append((sql.name, line.strip()))
    assert columns, "no visibility jsonb column found at all -- the measurement moved"
    nullable = [(f, l) for f, l in columns if "not null" not in l.lower()]
    assert len(nullable) <= 1, (
        f"{len(nullable)} nullable visibility columns: {nullable}. The declaration says five of "
        "six are NOT NULL and the sixth is paired with a fail-closed scope")
    for name, _line in nullable:
        body = (REPO / "migrations" / name).read_text(encoding="utf-8").lower()
        assert "visibility_scope text not null default 'private'" in body, (
            f"{name} has a nullable visibility jsonb and no fail-closed scope default beside it")


# ------------------------------------------------------- the claims the grades rest on, asserted

def test_a_private_scope_with_no_principals_is_visible_to_NOBODY():
    """⛔ The three ✅ FAIL-CLOSED grades rest entirely on this, so it is measured rather than
    reasoned about. `principals or ()` is only safe if an empty list excludes."""
    v = Visibility(scope="private", principals=[], derived_from="guard")
    assert v.can_view("someone@example.com", org_member=True) is False
    assert v.can_view("someone@example.com", org_member=False) is False
    assert v.can_view(None, org_member=True) is False


def test_all_three_capture_contracts_DO_declare_visibility_and_none_require_it():
    """⛔ The scorecard's correction, pinned. Its evidence line said *zero* declare the field."""
    import dataclasses

    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.contracts.gated_event import GatedEvent
    from genios_engine.contracts.source_event import SourceEvent

    raw = {f.name: f for f in dataclasses.fields(RawObject)}
    assert "visibility" in raw, "RawObject no longer declares visibility"
    for model in (SourceEvent, GatedEvent):
        field = model.model_fields.get("visibility")
        assert field is not None, f"{model.__name__} no longer declares visibility"
        assert field.is_required() is False, (
            f"{model.__name__}.visibility is now REQUIRED. That closes L1-08 at the contract and "
            "the OPEN sites could be fixed -- but it also changes every constructor, so read the "
            "declaration before celebrating")


def test_rawobject_visibility_is_still_the_untyped_one():
    """⛔ The lesser finding, recorded where it can be re-measured: `RawObject.visibility` is typed
    `Any` while the other two are `Visibility | None`. `Any` accepts a string, a dict, or a
    wrong-shaped object, and the landing seam reads it with `getattr(raw, "visibility", None)`.

    Not repaired here: `RawObject` is the connector boundary and every connector constructs one.
    """
    import dataclasses

    from genios_engine.capture.connectors.base import RawObject

    annotation = {f.name: f.type for f in dataclasses.fields(RawObject)}["visibility"]
    assert "Any" in str(annotation), (
        f"RawObject.visibility is now {annotation!r} -- if it was typed, say so in the "
        "declaration and drop this test")
