"""Nothing has ever asked a tenant what it is, so every tenant reads the identical corpus.

    pytest tests/context/test_a_tenant_can_say_what_kind_of_company_it_is.py -q

The corpus has branched for this since it was written — `models/` (18 files), `verticals/`,
`offerings/`, resolved most-specific-first. `l3_activation.variant_ids` is what selects a branch.
Measured on the pilot 2026-09-16: `[]` on all three activation rows, and nothing in the product
has ever written that column. So the branch mechanism is handed an empty list for every tenant
and the canonical text is all anybody gets.

`context/tenant_profile` is the input it never had. These tests pin the four properties that
decide whether a declaration survives the trip to the compiler.

WHY THERE IS NO INFERENCE TEST. There is no inference. Measured on the same day: the graph holds
no self-description — `company.industry` has 3 rows and they are about counterparties, and the
only other candidate is `thread.objective`, 236 values of free prose that are unique to their own
thread by construction. Inferring a category from those means keyword rules tuned on one tenant's
vocabulary. A tenant that declares nothing keeps exactly the behaviour it has today.
"""
from __future__ import annotations

import pytest

from genios_engine.context import tenant_profile as TP

pytestmark = pytest.mark.unit


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """A two-domain corpus on disk, so the vocabulary is read rather than declared in the test."""
    def branch(domain: str, axis_dir: str, slug: str, declared_id: str, filename: str):
        d = tmp_path / domain / axis_dir / slug
        d.mkdir(parents=True)
        (d / filename).write_text(f"identity:\n  id: {declared_id}\n  kind: {filename[:-5]}\n")
    branch("Admin Expertise", "verticals", "ai_agency", "admin.vertical.ai_agency", "vertical.yaml")
    branch("Admin Expertise", "verticals", "saas", "admin.vertical.saas", "vertical.yaml")
    branch("Sales Expertise", "verticals", "ai_agency", "sales.vertical.ai_agency", "vertical.yaml")
    branch("Admin Expertise", "roles", "cto", "admin.role.cto", "role.yaml")
    # THE TRAP: folder says `pm`, the id ends `product_manager`. Loaded, and unreachable by folder.
    branch("Admin Expertise", "roles", "pm", "admin.role.product_manager", "role.yaml")
    (tmp_path / "_scratch").mkdir()
    monkeypatch.setattr(TP, "corpus_root", lambda: tmp_path)
    TP._axis_entries.cache_clear()
    yield tmp_path
    TP._axis_entries.cache_clear()


def test_the_vocabulary_is_the_corpus(corpus) -> None:
    """Not a list kept beside it. A category exists exactly when somebody authored it, and the
    same slug in two domains is ONE category, not two."""
    assert TP.categories() == ("ai_agency", "saas")
    assert TP.reader_roles() == ("cto", "pm")


def test_a_value_no_corpus_declares_is_named(corpus) -> None:
    """The drift, caught where it is still cheap. A tenant switched on for a role nobody
    authored resolves to nothing and the card silently falls back to canonical doctrine."""
    assert TP.undeclared("vertical", ["ai_agency", "law_firm"]) == ("law_firm",)
    assert TP.undeclared("role", ["cto"]) == ()


def test_a_branch_unreachable_by_its_own_folder_name_is_reported(corpus) -> None:
    """`_resolve_variants` matches a request against the full id, its last dotted segment, and the
    slugified name. A folder called `pm` whose id ends `product_manager` is authored, loaded, and
    can never be asked for by the name it sits under — the silent-fallback trap."""
    assert TP.resolvable_slugs("role") == ("cto",)
    assert TP.unreachable_slugs("role") == (("pm", "admin.role.product_manager"),)


def test_an_undeclared_axis_is_empty_rather_than_an_error(corpus) -> None:
    """A corpus with no `offerings/` is a corpus that has not branched on what it sells."""
    assert TP.declared("offering") == ()
    assert TP.declared("not_an_axis") == ()


def test_absent_is_absent_and_not_an_empty_string() -> None:
    """A tenant that declared no role gets NO `org.persona` fact. An empty string is a value a
    reader can act on; the missing field is the honest statement that nobody said. It is also what
    keeps the package's content address still for a tenant that declared nothing."""
    facts = TP.profile_facts(category="ai_agency")
    assert [f[0] for f in facts] == [TP.CATEGORY_FIELD, TP.CATEGORY_BASIS_FIELD]
    assert TP.profile_facts() == ()


def test_every_declared_value_carries_its_basis() -> None:
    """The same pairing `commitment.owner`/`commitment.owner_basis` already uses: a reader must be
    able to tell a thing somebody stated from a thing the system assumed."""
    facts = dict((f[0], f[1]) for f in
                 TP.profile_facts(category="saas", reader_role="cto"))
    assert facts[TP.CATEGORY_BASIS_FIELD] == TP.BASIS_DECLARED
    assert facts[TP.ROLE_BASIS_FIELD] == TP.BASIS_DECLARED


def test_there_is_no_inferred_basis() -> None:
    """The refusal, enforced. A caller that wants to record a guess has to change this module and
    say why in the diff, rather than passing a string nobody notices."""
    with pytest.raises(ValueError, match="unknown profile basis"):
        TP.profile_facts(category="saas", basis="inferred")


def test_the_variant_ids_are_ordered_most_specific_first() -> None:
    """The corpus resolves role -> vertical -> model -> canonical. The stored row should show
    the same precedence the compiler applies, or an operator reading it is reading a lie."""
    profile = {TP.CATEGORY_FIELD: "ai_agency", TP.ROLE_FIELD: "cto"}
    assert TP.variant_ids_for(profile) == ("cto", "ai_agency")


def test_a_tenant_that_declared_nothing_selects_nothing() -> None:
    """Today's behaviour, kept exactly. No declaration means no overlay means canonical text —
    which is what every tenant already gets, so nothing regresses on the day this ships."""
    assert TP.variant_ids_for({}) == ()
