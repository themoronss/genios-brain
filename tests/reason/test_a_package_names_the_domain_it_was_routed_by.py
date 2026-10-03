"""⛔⛔ U01 · Atlas L2-11, located — *"wrong first domain … can still enter the wrong view"*.

`reason/adapters/expertise.py` reads the package's own metadata bag and takes the first entry::

    domain_ids = package.metadata.get("domain_ids") or ()
    domain = str(domain_ids[0]) if domain_ids else "general"

That value becomes `CapabilityManifest.domain`, and `reason/domain_shadow.py` uses that field to
pick which TENANT PACK the reasoning reads. So the index does not choose a label — it chooses the
knowledge, and `reason/runner.py` gates on the same field.

⛔ AND THE LIST ARRIVES SORTED. `RoutePlan` is sealed with `domain_ids=tuple(sorted(
selected_domains))` over a `set`, and a situation with no usable hint resolves against
`sorted(self.catalog.domains.keys())` — every authored domain. A multi-domain route therefore
reasons against whichever pack sorts first *alphabetically*, and nothing records that a choice
existed.

✅ THE CONTRACT ALREADY OWNS THE RIGHT ACCESSOR. `SituationCandidate.domain_hints` returns every
entry, sorted and unique; `packs/compiler/runtime_brains` consumes it that way. The routing site
reaches past it into the raw bag.

WHAT THIS FILE PINS. Receipt 45 measures how often the pick actually had something to pick
between, and these tests hold the receipt to what makes it meaningful: that it is a correctness
receipt rather than a presence one, that its metadata key is DERIVED from the writer's own field
names, and — in both directions — that it refuses rather than silently passing when either of the
two things that would make it always-green happens.

⛔ SEVERAL TESTS HERE ASSERT THAT THE DEFECT IS STILL PRESENT, and that is deliberate. When the
routing site is fixed, they fail with a message saying so, because a receipt that outlives the
condition it measures is a number nobody can interpret. The fix and the retirement of the receipt
have to happen in the same change.
"""

from __future__ import annotations

import ast
import re
from dataclasses import fields
from pathlib import Path

import pytest

from genios_engine.contracts.domain_expertise import (OBSERVATION_METADATA_KEYS,
                                                      addressable_metadata)
from genios_engine.packs.compiler.models import RoutePlan
from genios_engine.platform import receipt_coverage as C
from genios_engine.platform import receipts as R

CLAIM = "no published reasoning package was routed by picking one of several domains"
ENGINE = Path(R.__file__).resolve().parent.parent
ROUTING_SITE = ENGINE / "reason" / "adapters" / "expertise.py"
PACK_SELECTOR = ENGINE / "reason" / "domain_shadow.py"


def _receipt(org=None):
    found = [r for r in R.receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, f"expected exactly one receipt claiming {CLAIM!r}, got {len(found)}"
    return found[0]


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- the receipt itself

def test_the_receipt_exists_and_is_layer_two():
    """The claim is about the PICK, which is Layer 2's, not about the table, which is L3's."""
    assert _receipt().layer == "L2"


def test_it_is_a_correctness_receipt_and_not_a_presence_one():
    """⛔ `expect(0) is True` is the whole difference. A presence receipt asks "did anything
    happen"; this one asks "did the wrong thing happen", and zero is the right answer."""
    receipt = _receipt()
    assert receipt.expect(0) is True, "zero multi-domain routes must PASS"
    assert receipt.expect(1) is False, "one must FAIL -- otherwise the receipt cannot go red"
    assert receipt.expect(99) is False


def test_it_reads_the_table_the_publisher_actually_writes():
    sql = _receipt().sql
    assert "expertise_packages" in sql
    assert "payload" in sql, "the metadata rides in the jsonb payload, not in a column"


def test_it_is_org_scoped_and_not_fleet_wide():
    """A tenant's readiness page must not report another tenant's routes."""
    receipt = _receipt("org-1")
    assert receipt.fleet_wide is False
    assert "org_id = :org" in receipt.sql
    assert "org_id = :org" not in _receipt(None).sql


def test_it_asks_for_MORE_than_one_and_not_merely_for_presence():
    """⛔ `> 1`, never `>= 1`. A single-domain route has nothing to pick between and is the
    ordinary case; counting it would make the receipt red on every healthy tenant."""
    sql = _receipt().sql
    assert "> 1" in sql
    assert ">= 1" not in sql and "> 0" not in sql


def test_it_guards_the_json_type_before_measuring_its_length():
    """`jsonb_array_length` raises on a non-array, and one raising receipt used to take every
    receipt after it -- so the type is checked first, in SQL."""
    sql = _receipt().sql
    assert "jsonb_typeof" in sql
    assert sql.index("jsonb_typeof") < sql.index("jsonb_array_length")


# ------------------------------------------------------------- the key is derived, never spelled

def test_the_metadata_key_is_a_field_of_the_writers_own_plan():
    """⛔ `packs/compiler/expertise_builder` writes `"domain_ids": plan.domain_ids`, so the key is
    `RoutePlan`'s field name. The receipt looks it up there rather than carrying a second copy."""
    assert "domain_ids" in {f.name for f in fields(RoutePlan)}
    assert "'domain_ids'" in _receipt().sql


def test_the_builder_refuses_when_the_plan_loses_the_field(monkeypatch):
    """⛔ A rename must stop the receipt, not leave it counting a key nobody writes.

    A real dataclass with the field renamed, because that is the change a person actually makes.
    """
    import dataclasses

    import genios_engine.packs.compiler.models as models

    @dataclasses.dataclass(frozen=True)
    class _Renamed:
        domain_identifiers: tuple[str, ...] = ()

    monkeypatch.setattr(models, "RoutePlan", _Renamed)
    with pytest.raises(AssertionError, match="no longer carries"):
        R._MULTI_DOMAIN_ROUTED_PACKAGE_SQL(None)


def test_the_builder_refuses_when_the_plan_stops_being_a_dataclass(monkeypatch):
    """⛔ FOUND BY THE TEST ABOVE FAILING. The first draft monkeypatched a plain class and got
    `TypeError: must be called with a dataclass type or instance` out of the stdlib -- a message
    that names no claim. The builder now asks first, so an unrunnable receipt says which question
    it stopped being able to answer."""
    import genios_engine.packs.compiler.models as models

    class _NotADataclass:
        domain_ids = ()

    monkeypatch.setattr(models, "RoutePlan", _NotADataclass)
    with pytest.raises(AssertionError, match="no longer a dataclass"):
        R._MULTI_DOMAIN_ROUTED_PACKAGE_SQL(None)


def test_the_builder_refuses_when_the_key_becomes_unaddressable(monkeypatch):
    """⛔⛔ THE ALWAYS-GREEN FAILURE, GUARDED. `addressable_metadata` strips
    `OBSERVATION_METADATA_KEYS` inside `ExpertisePackage.to_semantic_dict`, which is what the
    publisher stores. If `domain_ids` ever joined that set, the column would be absent, the count
    would be 0 for ever, and the receipt would pass while measuring nothing."""
    import genios_engine.contracts.domain_expertise as DE

    monkeypatch.setattr(DE, "OBSERVATION_METADATA_KEYS", frozenset({"domain_ids"}))
    with pytest.raises(AssertionError, match="always|go green by itself|OBSERVATION_METADATA"):
        R._MULTI_DOMAIN_ROUTED_PACKAGE_SQL(None)


def test_the_key_survives_the_filter_the_publisher_applies():
    """The positive half of the same fact, asserted against the real function."""
    assert "domain_ids" not in OBSERVATION_METADATA_KEYS
    kept = addressable_metadata({"domain_ids": ["a", "b"], "context_graph_version": 7})
    assert kept == {"domain_ids": ["a", "b"]}, (
        "`domain_ids` must survive and the observation key must not -- if this flips, the "
        "receipt's column moves")


# ------------------------------------------------- the defect is still there, pinned by the AST

def test_the_routing_site_still_takes_the_first_entry():
    """⛔ Pinned by the AST, not by a substring: a comment mentioning `domain_ids[0]` must not be
    able to satisfy this, and neither must a string.

    WHEN THIS FAILS THE ROUTING SITE WAS FIXED. Good -- then re-point or retire receipt 45 in the
    same change, because a receipt that outlives its condition is a number nobody can read.
    """
    subscripts = [
        node for node in ast.walk(_tree(ROUTING_SITE))
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name) and node.value.id == "domain_ids"
        and isinstance(node.slice, ast.Constant) and node.slice.value == 0
    ]
    assert subscripts, (
        "`domain_ids[0]` is gone from the routing site. If the pick now records itself or uses "
        "`domain_hints`, receipt 45 has nothing left to measure -- retire it deliberately")


def test_the_chosen_domain_reaches_the_capability_manifest():
    """The severity link, half one: the pick is not a local label."""
    tree = _tree(ROUTING_SITE)
    passed = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "CapabilityManifest"
        and any(kw.arg == "domain" and isinstance(kw.value, ast.Name)
                and kw.value.id == "domain" for kw in node.keywords)
    ]
    assert passed, ("the chosen domain no longer reaches `CapabilityManifest(domain=...)`; receipt "
                    "45's severity argument rested on it")


def test_the_manifest_domain_selects_the_tenant_pack():
    """The severity link, half two: that field picks the KNOWLEDGE.

    ⛔ Attribute access on the AST rather than the phrase `manifest.domain`, because the phrase
    appears in prose in this very file and a text search would be satisfied by a comment.
    """
    reads = [
        node for node in ast.walk(_tree(PACK_SELECTOR))
        if isinstance(node, ast.Attribute) and node.attr == "domain"
        and isinstance(node.value, ast.Name) and node.value.id == "manifest"
    ]
    assert len(reads) >= 2, (
        f"`manifest.domain` is read {len(reads)}x in domain_shadow.py; the pack selection "
        "(`packs[manifest.domain] = _tenant_pack(...)`) was what made the alphabetical pick "
        "matter rather than merely untidy")


def test_the_plan_can_hold_several_domains_so_the_pick_is_real():
    """⛔ If this were a single value the receipt would be theatre. It is a tuple, built with
    `tuple(sorted(...))` over a `set`, which is also why `[0]` is the ALPHABETICALLY first."""
    annotation = {f.name: f.type for f in fields(RoutePlan)}["domain_ids"]
    assert "tuple" in str(annotation), annotation
    source = (ENGINE / "packs" / "compiler" / "capability_resolver.py").read_text(encoding="utf-8")
    assert re.search(r"domain_ids=tuple\(sorted\(selected_domains\)\)", source), (
        "the plan no longer seals `domain_ids` as a sorted tuple of a set -- re-read whether "
        "`[0]` is still the alphabetically first domain before trusting receipt 45's wording")


def test_a_right_way_to_read_the_field_already_exists():
    """✅ So the finding is "the site reaches past the accessor", not "no accessor exists"."""
    from genios_engine.contracts.domain_expertise import SituationCandidate

    assert isinstance(getattr(SituationCandidate, "domain_hints", None), property), (
        "`domain_hints` is what returns every domain, sorted and unique; the receipt's detail "
        "line tells an operator to use it")


# --------------------------------------------------------------------------------- the paperwork

def test_the_receipt_declares_the_package_an_operator_would_read():
    package, why = C.RECEIPT_PACKAGE[CLAIM]
    assert package == "reason", (
        "the table is L3's and the claim is `reason/`'s; the declaration has to say which, the "
        "way the bound-fact-path receipt does")
    assert "expertise_packages" in why and "domain_shadow" in why, (
        "the declaration must name both the table it queries and the place the pick bites, or the "
        "next reader re-derives it")


def test_nothing_is_undeclared_or_stale_in_either_direction():
    assert C.undeclared_receipts() == ()
    assert C.stale_declarations() == ()
