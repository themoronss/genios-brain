"""L2 · Projections and domain specs — Layer 2 working for domains it has never heard of.

Two requirements drove this, and both are about the FUTURE:

  * More domains are coming. Sales, support and admin today; engineering, legal, hiring
    later. Layer 2 must not need editing when they arrive.
  * Layer 3 domain expertise is coming. Layer 2 must hold a seam for it, not a copy of it.

So most of these tests assert what Layer 2 does NOT know and does NOT do.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from genios_engine.context.domain_spec import (DomainSpec, generic_spec, is_registered,
                                               register, registered_domains, spec_for)
from genios_engine.context.situations import coverage_score, situation_type

ROOT = Path(__file__).resolve().parents[1] / "genios_engine"


def _code_only(path: Path) -> str:
    """Executable code with docstrings and comments stripped.

    These checks are about what the code KNOWS, not what the prose explains. A module
    docstring that says 'add "engineering" upstream and its lens exists immediately' is
    documenting the very property under test — matching on raw text would fail the file
    for describing itself correctly.
    """
    import ast
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
    return ast.unparse(tree).lower()


# ── open by default: the requirement that domains will grow ──────────────────────

def test_an_unknown_domain_just_works() -> None:
    """The whole requirement in one test. A domain nobody has described must produce a
    working spec — not an error, not None, not a special case every caller must handle."""
    spec = spec_for("engineering")
    assert spec.domain == "engineering"
    assert spec.display_name == "Engineering"
    assert spec.type_for("company") == "engineering_company"
    assert spec.fields_for("engineering_company") == {}


def test_an_unmapped_situation_stays_visibly_unmapped() -> None:
    """`<domain>_<anchor>` rather than a generic bucket. Filing an unknown thing under a
    known name is how a report becomes confidently wrong."""
    assert situation_type("company", "legal") == "legal_company"
    assert situation_type("deal", "hiring") == "hiring_deal"


def test_a_new_domain_is_not_reported_as_completely_uncovered() -> None:
    """THE TRAP. "We expect nothing" must score 100% covered, not 0% known — otherwise
    every situation in a new domain looks broken on the day it is added. Absence read as
    negative evidence, which this codebase refuses everywhere else."""
    score, missing = coverage_score(present_fields=set(),
                                    expected=spec_for("engineering").fields_for("x"))
    assert (score, missing) == (100, [])


def test_spec_lookup_never_fails() -> None:
    for value in ("", None, "   ", "Weird_New_Domain", "UPPER"):
        assert spec_for(value).domain


def test_an_empty_domain_falls_back_rather_than_erroring() -> None:
    assert spec_for(None).domain == "general"
    assert spec_for("").domain == "general"


def test_domain_names_are_matched_case_insensitively() -> None:
    """A domain arriving as "Sales" from one source and "sales" from another must not
    become two lenses."""
    assert spec_for("SALES").domain == spec_for("sales").domain == "sales"


# ── the seam Layer 3 will use ────────────────────────────────────────────────────

def test_layer3_can_take_over_a_domain_without_editing_layer2() -> None:
    """The built-in specs are placeholders. A registry that refused to be overwritten
    would force Layer 2 to be edited to remove them first — exactly what this seam
    exists to prevent."""
    original = spec_for("sales")
    try:
        register(DomainSpec(domain="sales", display_name="Revenue",
                            situation_types={"company": "pipeline_opportunity"}))
        assert spec_for("sales").display_name == "Revenue"
        assert situation_type("company", "sales") == "pipeline_opportunity"
    finally:
        register(original)
    assert spec_for("sales").display_name == "Sales"


def test_a_brand_new_domain_can_be_registered() -> None:
    try:
        register(DomainSpec(domain="engineering", display_name="Engineering",
                            situation_types={"company": "incident"},
                            expected_fields={"incident": {"x.y": "a thing"}}))
        assert situation_type("company", "engineering") == "incident"
        assert spec_for("engineering").fields_for("incident") == {"x.y": "a thing"}
        assert is_registered("engineering")
    finally:
        import genios_engine.context.domain_spec as ds
        ds._SPECS.pop("engineering", None)


def test_registered_domains_is_not_the_list_of_real_domains() -> None:
    """A registry lists what someone has DESCRIBED. Data can carry a domain nobody
    described, and treating the registry as the universe would make Layer 2 reject it."""
    assert "engineering" not in registered_domains()
    assert spec_for("engineering").domain == "engineering"   # still works


def test_a_spec_needs_a_name() -> None:
    import pytest
    with pytest.raises(ValueError, match="needs a domain name"):
        register(DomainSpec(domain=""))


# ── Layer 2 must not know any domain by name ─────────────────────────────────────

def test_domain_names_appear_in_exactly_one_file_in_the_context_layer() -> None:
    """The honest version of this claim.

    An earlier draft asserted "Layer 2 holds no domain knowledge" while excluding
    domain_spec.py — the one file that names sales, support and admin. The knowledge had
    moved 200 lines sideways and the test was checking everywhere it wasn't.

    The defensible property is not "nowhere" but "one place, and it is overridable": the
    registry holds the defaults, everything else stays domain-blind, and Layer 3 replaces
    the defaults through `register()` rather than by editing Layer 2.
    """
    names = ('"sales"', "'sales'", '"support"', "'support'", '"admin"', "'admin'")
    offenders = []
    for module in sorted((ROOT / "context").glob("*.py")):
        if module.name == "domain_spec.py":
            continue                     # THE one place, by design
        source = _code_only(module)
        offenders += [f"{module.name}:{n}" for n in names if n in source]
    assert not offenders, (
        "a domain is named outside the registry — it belongs in domain_spec.py so a new "
        f"domain never requires editing Layer 2: {offenders}")


def test_the_registry_really_is_that_one_place() -> None:
    """Guard the exemption above: if the defaults ever leave domain_spec.py, the test
    that excuses it must stop passing vacuously."""
    # `_code_only` round-trips through ast.unparse, which normalises string quoting —
    # so this checks the registry's CONTENTS rather than its source text.
    from genios_engine.context.domain_spec import registered_domains
    assert {"sales", "support", "admin"} <= set(registered_domains())


def test_projections_never_name_a_domain() -> None:
    """Add a domain upstream and its lens must exist immediately, with no change here."""
    source = _code_only(ROOT / "context" / "projections.py")
    for domain in ("sales", "support", "admin", "hr", "finance", "engineering"):
        assert f'"{domain}"' not in source
        assert f"'{domain}'" not in source


def test_projections_are_discovered_from_data_not_declared() -> None:
    from genios_engine.context.projections import available_projections
    source = inspect.getsource(available_projections)
    assert "from context_situations" in source
    assert "group by domain" in source


# ── the constitutional rule ──────────────────────────────────────────────────────

def test_a_lens_never_narrows_evaluation() -> None:
    """The third time this rule appears in Layer 2, and the most dangerous: a projection
    LOOKS reasonable ("the Sales view shouldn't show promotional email"). Showing less is
    fine; evaluating less is not. Anything mis-assigned — or in no lens — would become
    permanently invisible with nothing reporting it missing."""
    offenders = [str(py.relative_to(ROOT)) for py in (ROOT / "reason").rglob("*.py")
                 if "context.projections" in py.read_text()
                 or "from genios_engine.context import projections" in py.read_text()]
    assert not offenders, f"reason/ must not scope itself by a lens: {offenders}"


def test_whatever_falls_through_every_lens_is_findable() -> None:
    """Without this a projection system is a way to lose things quietly: an entity nobody
    classified is invisible in every view, absent from every count, and unreported."""
    from genios_engine.context.projections import unprojected_nodes
    assert callable(unprojected_nodes)
    source = inspect.getsource(unprojected_nodes)
    assert "not exists" in source


def test_projections_store_nothing() -> None:
    """No membership table. It would go stale the instant a situation changes domain, is
    folded by a merge, or opens a new generation — and a stale lens is worse than none,
    because nothing in the system disagrees with it."""
    source = _code_only(ROOT / "context" / "projections.py")
    for mutation in ("insert into", "update ", "delete from", "create table"):
        assert mutation not in source


def test_no_migration_creates_a_projection_membership_table() -> None:
    migrations = Path(__file__).resolve().parents[1] / "migrations"
    for sql_file in migrations.glob("*.sql"):
        text_ = sql_file.read_text().lower()
        assert "create table if not exists node_projections" not in text_
        assert "create table if not exists context_projections" not in text_


# ── the things a lens must not get wrong ─────────────────────────────────────────

def test_an_entity_can_be_in_several_lenses_at_once() -> None:
    """A customer with a live deal AND an open support ticket belongs to both. Returning
    one would make the other view lose them — silently, since neither view can tell it is
    incomplete."""
    from genios_engine.context.projections import node_projections
    assert inspect.signature(node_projections).return_annotation == "list[str]"


def test_membership_has_exactly_one_definition() -> None:
    """THE defect this module was rewritten to fix.

    The first draft answered "who is in this lens?", "which lenses is this node in?" and
    "what falls through every lens?" with three different SQL definitions. A participant
    in the Sales lens was simultaneously reported as belonging to no lens at all — three
    answers to one question, inside the module written to prevent exactly that.

    Every one of them must now read the same constant.
    """
    from genios_engine.context import projections
    for fn in (projections.projection_members, projections.node_projections,
               projections.unprojected_nodes):
        assert "_REACHED" in inspect.getsource(fn), fn.__name__
    # And there must be only one such constant to read.
    assert not hasattr(projections, "_MEMBER_SQL")


def test_a_truncated_lens_says_so() -> None:
    """"500 members" must be distinguishable from "exactly 500 members" when the truth is
    40,000 — a truncation the caller cannot see and would not suspect."""
    from genios_engine.context.projections import Projection
    assert {"total_members", "truncated"} <= set(Projection.__dataclass_fields__)


def test_situations_record_which_registry_typed_them() -> None:
    """`situation_type`, `coverage` and `missing` are DERIVED from the specs and then
    PERSISTED. A registry change silently rewrites stored values on the next refresh, so
    the row has to say which registry produced it — otherwise a re-typing is
    indistinguishable from the world having changed."""
    from genios_engine.context.domain_spec import spec_version
    from genios_engine.context.situations import score_situation
    assert "domain_spec_version" in inspect.getsource(score_situation)
    assert spec_version() == spec_version()          # content-addressed, not random


def test_the_spec_version_moves_when_the_registry_does() -> None:
    from genios_engine.context.domain_spec import DomainSpec, register, spec_version
    before = spec_version()
    try:
        register(DomainSpec(domain="temp_domain_for_test", display_name="Temp"))
        assert spec_version() != before
    finally:
        import genios_engine.context.domain_spec as ds
        ds._SPECS.pop("temp_domain_for_test", None)
    assert spec_version() == before


def test_edges_leaving_the_lens_are_reported_not_dropped() -> None:
    """Dropping them makes the lens claim the customer has no other relationships — a lie
    by omission, and the worst kind, because the view looks complete."""
    from genios_engine.context.projections import boundary_edges
    source = inspect.getsource(boundary_edges)
    assert "outside_node_id" in source
    # The XOR is what makes it a BOUNDARY edge: exactly one end inside the lens.
    assert "<>" in source


def test_a_lens_can_include_history_when_asked() -> None:
    """A working view defaults to active. A historical question needs the rest, which is
    why this is a parameter and not a hard-coded filter."""
    from genios_engine.context.projections import projection_members
    assert "active_only" in inspect.signature(projection_members).parameters
    assert inspect.signature(projection_members).parameters["active_only"].default is True


def test_a_lens_reports_whether_its_domain_is_described_yet() -> None:
    """"Present in the data, not described yet" is a normal state while a domain is being
    introduced — and the caller has to be able to tell."""
    from genios_engine.context.projections import Projection
    assert "registered" in Projection.__dataclass_fields__


def test_the_generic_spec_is_functional_not_degraded() -> None:
    spec = generic_spec("procurement")
    assert spec.display_name == "Procurement"
    assert spec.type_for("company") == "procurement_company"
    assert spec.fields_for("anything") == {}
