"""⛔⛔ U02 · Atlas L2-01 — *"incorrect authority configuration would still be applied consistently"*.

`graph_facts.authority_rank` is a plain integer column, and it carries two scales:

* `capture/validate/authority.AUTHORITY_RANK` — a dense ladder, `0..MAX_AUTHORITY_RANK`, seven
  classes, no ties, `inferred` at the bottom and `signed_document` at the top;
* `context/analytic/publish.DEFAULT_AUTHORITY_RANK` — **100**, written into the same column of the
  same table.

⛔ And `context/graph_store.fact_write_action` compares the raw integers and nothing else: a
strictly-lower new rank is flagged a `discrepancy` and discarded, anything else supersedes. So a
row at 100 cannot be superseded by a countersigned contract — the contract is the thing that gets
dropped.

⛔ THREE MORE RANKS DO NOT SAY HOW THEY WERE DECIDED. The unmapped floor is `inferred`'s own rank
0; `write_fact` and `build_evidence_ref` default to a bare `1`, which is `chat_aside`; and
`write_edge` defaults to a bare `2`, which is `email_prose`. `UNINTERPRETABLE_RANKS` declares all
four with a reason and a mover, and this file checks that table **in both directions** — a declared
rank that has become unambiguous is as much a lie as an ambiguous rank nobody declared.

⛔ WHAT IS NOT CLAIMED. No live corruption. The derived writer scopes its own lookup by
`version_prefix`, and the observed and derived writers share no literal field name. ⛔ But
`write_fact`'s lookup is NOT prefix-scoped, so the separation rests on two field vocabularies never
meeting, nothing enforces that, and 31 `field=` arguments could not be resolved statically — the
resolver's coverage is stated beside its verdict, because a measurement that hides its blind spot
reads as a proof.
"""

from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.capture.validate import authority as A
from genios_engine.platform import receipt_coverage as C
from genios_engine.platform import receipts as R

CLAIM = "no fact holds two authority scales at once"
ENGINE = Path(R.__file__).resolve().parent.parent
GRAPH_STORE = ENGINE / "context" / "graph_store.py"
DERIVED_PUBLISH = ENGINE / "context" / "analytic" / "publish.py"


def _receipt(org=None):
    found = [r for r in R.receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, f"expected one receipt claiming {CLAIM!r}, got {len(found)}"
    return found[0]


def _bare_rank_defaults() -> dict[int, list[str]]:
    """Every `authority_rank=<literal int>` default in the engine, and where.

    ⛔ A LITERAL, NOT ANY DEFAULT. `publish_derived_fact(authority_rank=DEFAULT_AUTHORITY_RANK)` is
    an `ast.Name` and is deliberately NOT counted: naming the number is the fix, so a named default
    must not be reported as the defect it avoids.
    """
    out: dict[int, list[str]] = {}
    for path in sorted(ENGINE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                     # pragma: no cover - not expected
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            positional = [a.arg for a in args.args]
            paired = dict(zip(positional[len(positional) - len(args.defaults):], args.defaults))
            paired.update({a.arg: d for a, d in zip(args.kwonlyargs, args.kw_defaults)})
            default = paired.get("authority_rank")
            if isinstance(default, ast.Constant) and isinstance(default.value, int):
                out.setdefault(default.value, []).append(f"{path.name}:{node.lineno} {node.name}")
    return out


def _ambiguous_ranks() -> dict[int, str]:
    """Every rank a reader cannot interpret, DERIVED — the backward direction's input."""
    found: dict[int, str] = {}
    floor = A.AUTHORITY_RANK[A.UNMAPPED_AUTHORITY]
    found[floor] = "the unmapped floor shares a rank with a real class"
    for rank, sites in _bare_rank_defaults().items():
        found[rank] = f"a bare integer default at {', '.join(sites)}"
    from genios_engine.context.analytic.publish import DEFAULT_AUTHORITY_RANK

    if DEFAULT_AUTHORITY_RANK > A.MAX_AUTHORITY_RANK:
        found[DEFAULT_AUTHORITY_RANK] = "off the ladder entirely"
    return found


# ------------------------------------------------------------------- the declaration, both ways

def test_every_declared_rank_is_really_ambiguous():
    """Forward: nothing is declared that the code no longer does."""
    derived = _ambiguous_ranks()
    lies = sorted(r for r in A.UNINTERPRETABLE_RANKS if r not in derived)
    assert not lies, (
        f"ranks declared uninterpretable that nothing reaches any more: {lies}. A declaration that "
        "outlives its defect sends the next reader looking for something that is fixed")


def test_no_ambiguous_rank_is_undeclared():
    """Backward: nothing the code does is left undeclared.

    ⛔ This is the direction that catches a NEW writer. One direction alone is how `mcp/` escaped
    the import ratchet in L3-01.
    """
    derived = _ambiguous_ranks()
    missing = {r: why for r, why in derived.items() if r not in A.UNINTERPRETABLE_RANKS}
    assert not missing, (
        f"ranks a reader cannot interpret, declared nowhere: {missing}. Add them to "
        "`UNINTERPRETABLE_RANKS` with a reason and a mover, or name the number")


def test_the_declaration_is_not_empty():
    """⛔ An empty table asserts nothing, and both tests above would pass over it vacuously --
    the exact hole that let a mutation survive in `1.4`."""
    assert len(A.UNINTERPRETABLE_RANKS) >= 4, A.UNINTERPRETABLE_RANKS


def test_every_entry_carries_a_house_form_mover():
    for rank, entry in A.UNINTERPRETABLE_RANKS.items():
        _why, mover = entry
        assert mover.startswith(("MOVES WHEN", "MOVES WITH")), f"rank {rank}: {mover[:40]!r}"


def test_every_reason_NAMES_the_thing_it_is_about():
    """⛔ FOUND BY A SURVIVING MUTATION. The first version asserted `len(why) > 80`, which measures
    length and not content: a reason could be ninety characters of nothing, and shrinking rank 0's
    opening line to "floor collision." left the entry long enough to pass.

    So each reason is now held to naming its own evidence, and the names are DERIVED from the same
    measurement the declaration is checked against -- not spelled here a second time.
    """
    ranks = A.UNINTERPRETABLE_RANKS
    floor = A.AUTHORITY_RANK[A.UNMAPPED_AUTHORITY]
    assert "UNMAPPED_AUTHORITY" in ranks[floor][0], (
        f"rank {floor} is the unmapped floor and its reason must name the constant that puts it "
        "there, or the next reader cannot check the claim")

    for rank, sites in _bare_rank_defaults().items():
        functions = {site.split()[-1] for site in sites}
        why = ranks[rank][0]
        named = {fn for fn in functions if fn in why}
        assert named, (
            f"rank {rank} is a bare default at {sorted(functions)} and its reason names none of "
            "them. A declaration that does not name its site cannot be re-measured")

    from genios_engine.context.analytic.publish import DEFAULT_AUTHORITY_RANK

    if DEFAULT_AUTHORITY_RANK > A.MAX_AUTHORITY_RANK:
        assert "DEFAULT_AUTHORITY_RANK" in ranks[DEFAULT_AUTHORITY_RANK][0]


def test_the_two_bare_defaults_are_declared_as_one_fix():
    """They are two signatures with one defect, and a mover that splits them invites half a fix."""
    assert "MOVES WITH rank 2" in A.UNINTERPRETABLE_RANKS[1][1]
    assert "MOVES WITH rank 1" in A.UNINTERPRETABLE_RANKS[2][1]


# ------------------------------------------------------- the facts the declaration rests on

def test_the_unmapped_floor_still_collides_with_a_real_class():
    """⛔ If the floor got its own rank this entry retires -- so the collision is asserted, not
    assumed from the prose."""
    floor = A.AUTHORITY_RANK[A.UNMAPPED_AUTHORITY]
    classes_at_that_rank = [k.value for k, v in A.AUTHORITY_RANK.items() if v == floor]
    assert A.UNMAPPED_AUTHORITY.value in classes_at_that_rank
    assert floor in A.UNINTERPRETABLE_RANKS


def test_the_derived_rank_is_off_the_ladder():
    from genios_engine.context.analytic.publish import DEFAULT_AUTHORITY_RANK, FACT_TABLE

    assert DEFAULT_AUTHORITY_RANK > A.MAX_AUTHORITY_RANK, (
        "the derived scale has folded into the ladder; retire the rank-100 entry and receipt 46 "
        "together")
    assert FACT_TABLE == "graph_facts", (
        "the derived writer no longer writes the same table, which is the whole reason the two "
        "scales can meet")


def test_the_comparison_that_makes_a_rank_decide_is_still_a_bare_less_than():
    """⛔ By AST, over `fact_write_action`'s own body: a comment quoting the comparison must not
    be able to satisfy this."""
    tree = ast.parse(GRAPH_STORE.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "fact_write_action")
    compares = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.Lt)
        and isinstance(n.left, ast.Name) and n.left.id == "new_rank"
        and isinstance(n.comparators[0], ast.Name) and n.comparators[0].id == "held_rank"
    ]
    assert compares, (
        "`new_rank < held_rank` is gone from fact_write_action. If authority is now compared with "
        "a gap rule or a scale-aware helper, re-read receipt 46's wording before trusting it")


def test_the_promotion_rule_still_keys_on_the_bare_number_one():
    """⛔ This is what makes rank 1's ambiguity load-bearing rather than latent: a caller that
    passed nothing is promoted exactly as a stated chat aside is."""
    source = GRAPH_STORE.read_text(encoding="utf-8")
    assert "held.authority_rank == 1" in source, (
        "the promotion rule no longer compares the held rank to a bare 1; rank 1's entry says it "
        "is load-bearing because of this line")


def test_write_facts_lookup_is_still_not_prefix_scoped():
    """⛔ THE WHOLE REASON THE HAZARD IS A HAZARD. `publish_derived_fact` scopes by
    `version_prefix`; `write_fact` does not, so it can pick up a derived row as `held`."""
    gs = GRAPH_STORE.read_text(encoding="utf-8")
    dp = DERIVED_PUBLISH.read_text(encoding="utf-8")
    assert "version_prefix" in dp, "the derived writer's prefix scoping is the asymmetry's other half"
    assert "version_prefix" not in gs, (
        "`graph_store` now knows about version prefixes. If `write_fact`'s lookup became "
        "prefix-scoped, the hazard is closed -- retire receipt 46 and rank 100's entry")


def test_one_writer_already_does_it_the_right_way():
    """✅ So the finding is "three sites write a bare digit", not "nobody thought about it" --
    and the fix has a precedent in the codebase rather than being invented here."""
    bare = _bare_rank_defaults()
    assert 100 not in bare, (
        "DEFAULT_AUTHORITY_RANK is a NAMED constant and must not be counted as a bare default; "
        "naming the number is the fix this unit recommends")
    sites = sum(len(v) for v in bare.values())
    assert sites >= 3, f"expected the three bare-digit defaults, found {sites}: {bare}"


# ----------------------------------------------------------------------------------- receipt 46

def test_the_receipt_exists_and_can_go_red():
    receipt = _receipt()
    assert receipt.layer == "L2"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False


def test_it_asks_for_BOTH_scales_on_one_pair():
    """Not "does an off-ladder rank exist" -- that is true today and would be red for ever. The
    question is whether the two scales have ever MET on one `(node, field)`."""
    sql = _receipt().sql
    assert "bool_or" in sql and sql.count("bool_or") == 2
    assert "group by subject_node_id, field" in sql


def test_it_uses_the_readers_own_predicate():
    """⛔ `write_fact` selects `held` with exactly this; a different predicate would measure rows
    the comparison never sees."""
    sql = _receipt().sql
    assert "valid_to is null" in sql and "status = 'active'" in sql


def test_it_is_org_scoped():
    assert "org_id = :org" in _receipt("org-1").sql
    assert "org_id = :org" not in _receipt(None).sql
    assert _receipt().fleet_wide is False


def test_the_ladder_top_is_derived_and_not_written_twice():
    assert f"<= {A.MAX_AUTHORITY_RANK}" in _receipt().sql
    assert f"> {A.MAX_AUTHORITY_RANK}" in _receipt().sql


def test_the_builder_refuses_when_nothing_is_off_ladder_any_more(monkeypatch):
    """⛔⛔ THE ALWAYS-GREEN FAILURE, GUARDED. With no off-ladder rank declared, the `> top` half
    can never match and the receipt would pass while measuring nothing."""
    import pytest

    monkeypatch.setattr(A, "UNINTERPRETABLE_RANKS", {0: ("x" * 90, "MOVES WHEN never")})
    with pytest.raises(AssertionError, match="can never match|pass for ever"):
        R._MIXED_AUTHORITY_SCALE_SQL(None)


def test_the_receipt_declares_the_package_that_defines_a_rank():
    package, why = C.RECEIPT_PACKAGE[CLAIM]
    assert package == "capture", (
        "the table is `context/`'s and the comparison is too, but the thing that says what a rank "
        "MEANS is the ladder -- that is where an operator settles which scale is right")
    assert "UNINTERPRETABLE_RANKS" in why and "graph_facts" in why


def test_nothing_is_undeclared_or_stale():
    assert C.undeclared_receipts() == ()
    assert C.stale_declarations() == ()
