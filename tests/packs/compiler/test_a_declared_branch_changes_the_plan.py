"""A variant document was loaded, resolved, carried, hashed — and read by nothing.

    pytest tests/packs/compiler/test_a_declared_branch_changes_the_plan.py -q

`models/` holds 18 authored files across the three shipped corpora and has never changed a single
output. Not because it is switched off — because nothing consumed it. Traced 2026-09-16:

  * `rule_compiler.compile_package_rules` skips it — `artifact_class(record) != "rule"`;
  * `citations` skips it — `CITATION_CLASSES` is
    `(decision_framework, heuristic, mental_model, playbook, rule)` and a variant's kind is
    `vertical` / `model` / `persona` / `offering`;
  * the playbook adapter skips it for the same reason.

It reached the package as an entry in `expert_rules` and was hashed into `expert_snapshot_id`,
which is exactly enough to look wired.

THE ORDERING WAS THE CAUSE. The compiler runs
`capability_resolver -> object_resolver -> knowledge_retriever`, and variants were resolved in the
LAST of the three — after the plan had already decided which objects bind and which never do. A
vertical saying "this kind of company has no invoices" was structurally unable to say it.
Resolution now happens in `CapabilityResolver`, and `never_load` folds into the plan before it is
sealed.

WHAT A BRANCH MAY AND MAY NOT DO. It may only NARROW. A vertical is a statement about what is
irrelevant for this kind of company, not a licence to widen what a capability binds — widening
belongs to the capability's own admitted manifest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.packs.compiler.capability_resolver import (          # noqa: E402
    resolve_declared_variants, variant_never_load)

pytestmark = pytest.mark.unit


class _Doc:
    """A loaded corpus document, as `ExpertBrainCatalog` hands one over."""

    def __init__(self, doc_id: str, content: dict) -> None:
        self.id, self.content = doc_id, content


class _Domain:
    def __init__(self, variants: dict) -> None:
        self.variants = variants


class _Catalog:
    def __init__(self, domains: dict) -> None:
        self._domains = domains

    def domain(self, domain_id: str):
        return self._domains[domain_id]


class _Situation:
    def __init__(self, metadata: dict) -> None:
        self.metadata = metadata


def _catalog():
    return _Catalog({"sales": _Domain({
        "sales.vertical.ai_agency": _Doc("sales.vertical.ai_agency", {
            # The NAME deliberately does not slugify to `ai_agency`. `resolve_declared_variants`
            # matches on three aliases and the name is one of them; a fixture whose name happens
            # to slugify to the folder name passes with the segment alias deleted, which is a
            # test that proves nothing about the alias a tenant actually declares.
            "identity": {"id": "sales.vertical.ai_agency", "kind": "vertical",
                         "name": "Agency, AI-first"},
            "objects": {"never_load": ["sales.obj.core.invoice"]}}),
        "sales.model.b2b": _Doc("sales.model.b2b", {
            "identity": {"id": "sales.model.b2b", "kind": "model",
                         "name": "Business to Business"}}),
    })})


def test_a_branch_is_found_by_its_folder_name() -> None:
    """The alias a tenant declares. `variant_ids` holds slugs, and the last dotted segment of the
    id is one of the three aliases `resolve_declared_variants` matches on."""
    resolved, missing = resolve_declared_variants(
        _catalog(), ("sales",), _Situation({"model_ids": ["ai_agency"]}))
    assert [d.id for d in resolved] == ["sales.vertical.ai_agency"]
    assert missing == ()


def test_the_axis_is_not_part_of_the_request() -> None:
    """A tenant declares what it IS, not which folder the answer lives in. `model_ids` resolves a
    vertical, a model or a persona alike — the key name is historical, not a filter."""
    resolved, _ = resolve_declared_variants(
        _catalog(), ("sales",), _Situation({"model_ids": ["ai_agency", "b2b"]}))
    assert [d.id for d in resolved] == ["sales.model.b2b", "sales.vertical.ai_agency"]


def test_a_branch_nobody_authored_is_named_not_raised() -> None:
    """A typo used to raise `AuthoringIntegrityError`, which `domain_shadow` does not catch by
    name — it landed in the catch-all as `counts["error"]`, per situation, for every situation.
    A tenant's typo became a tenant-wide outage indistinguishable from a compiler bug."""
    resolved, missing = resolve_declared_variants(
        _catalog(), ("sales",), _Situation({"model_ids": ["law_firm"]}))
    assert resolved == ()
    assert missing == ("law_firm",)


def test_declaring_nothing_resolves_nothing() -> None:
    """Today's behaviour for every tenant, kept exactly: no declaration, no overlay, canonical."""
    assert resolve_declared_variants(_catalog(), ("sales",), _Situation({})) == ((), ())


def test_a_branch_removes_the_object_it_says_is_irrelevant() -> None:
    """THE POINT OF THE CHANGE. Until now this returned nothing a plan could act on."""
    resolved, _ = resolve_declared_variants(
        _catalog(), ("sales",), _Situation({"model_ids": ["ai_agency"]}))
    assert variant_never_load(resolved) == {"sales.obj.core.invoice"}


def test_a_branch_that_says_nothing_removes_nothing() -> None:
    """A model with no `objects` block must not silently empty the plan."""
    resolved, _ = resolve_declared_variants(
        _catalog(), ("sales",), _Situation({"model_ids": ["b2b"]}))
    assert variant_never_load(resolved) == set()


def test_the_plan_is_narrowed_and_never_widened() -> None:
    """A vertical states what is irrelevant here. Widening what a capability may bind belongs to
    the capability's own admitted manifest, so a branch's only power over the plan is removal."""
    from genios_engine.packs.compiler.capability_resolver import variant_never_load as never

    widening = (_Doc("x", {"identity": {"id": "x", "kind": "vertical"},
                           "objects": {"load": ["sales.obj.core.contract"],
                                       "never_load": ["sales.obj.core.invoice"]}}),)
    # `load` is ignored entirely — only the removal survives.
    assert never(widening) == {"sales.obj.core.invoice"}


# ── end to end, through the real compiler ───────────────────────────────────────────────────

def _corpus_with_a_vertical(tmp_path: Path) -> Path:
    """The shipped fixture corpus, plus one vertical that removes an optional object.

    Built on `test_domain_expertise_compiler._authoring_root` rather than a hand-rolled tree, so
    this exercises the same registry, capability, manifests and situation the compiler's own
    determinism tests run against — and a change to that fixture cannot leave this one asserting
    against a corpus nobody else compiles.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_dec_fixtures",
        Path(__file__).resolve().parents[2] / "test_domain_expertise_compiler.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_dec_fixtures"] = module
    spec.loader.exec_module(module)

    root = module._authoring_root(tmp_path)
    branch = root / "Sales Expertise" / "verticals" / "ai_agency"
    branch.mkdir(parents=True)
    (branch / "vertical.yaml").write_text(
        "identity:\n"
        "  id: sales.vertical.ai_agency\n"
        "  name: AI Agency\n"
        "  kind: vertical\n"
        "  domain: sales\n"
        "  version: 0.1.0\n"
        "  status: draft\n"
        "objects:\n"
        # `champion` is the fixture route's OPTIONAL object. An agency selling delivery capacity
        # has no champion to multithread to, and says so.
        "  never_load: [sales.obj.core.champion]\n"
        "render:\n"
        "  fallback:\n"
        "    headline: \"{entity} — delivery capacity at risk\"\n")
    return root, module


def test_a_declared_vertical_removes_an_object_from_a_real_compile(tmp_path: Path) -> None:
    """The whole change, end to end: declaring a branch changes what the compiler binds.

    Two compiles of the SAME situation over the SAME corpus, differing only in what the tenant
    declared. Before this change both produced identical plans, because the variant resolved
    after the plan was sealed.
    """
    from genios_engine.packs.compiler import (
        DomainCompiler, ExpertBrainCatalog, InMemoryExpertisePublisher, InMemoryRuntimeBrains)

    root, module = _corpus_with_a_vertical(tmp_path)

    def compile_with(model_ids):
        compiler = DomainCompiler(
            catalog=ExpertBrainCatalog(root), require_admission=False,
            runtime_brains=InMemoryRuntimeBrains(), publisher=InMemoryExpertisePublisher())
        return compiler.compile(module._situation(model_ids=model_ids))

    canonical = compile_with(["sales.model.b2b"])
    declared = compile_with(["ai_agency"])

    canonical_objects = {str(o.get("id")) for o in canonical.objects}
    declared_objects = {str(o.get("id")) for o in declared.objects}

    assert "sales.obj.core.champion" in canonical_objects, (
        "the fixture route must offer the object, or this test proves nothing")
    assert "sales.obj.core.champion" not in declared_objects, (
        "the declared vertical said this object is irrelevant and it was bound anyway")
    assert "sales.obj.core.account" in declared_objects, (
        "a branch may only narrow — the required object must survive")


def test_the_two_compiles_are_different_packages(tmp_path: Path) -> None:
    """And the difference reaches the content address, so Layer 4 and Layer 7 can tell them apart.
    `expert_snapshot_id` already hashed the variant documents; what is new is that the OBJECTS
    differ too, which is the part a card is built from."""
    from genios_engine.packs.compiler import (
        DomainCompiler, ExpertBrainCatalog, InMemoryExpertisePublisher, InMemoryRuntimeBrains)

    root, module = _corpus_with_a_vertical(tmp_path)

    def compile_with(model_ids):
        compiler = DomainCompiler(
            catalog=ExpertBrainCatalog(root), require_admission=False,
            runtime_brains=InMemoryRuntimeBrains(), publisher=InMemoryExpertisePublisher())
        return compiler.compile(module._situation(model_ids=model_ids))

    assert compile_with(["sales.model.b2b"]).semantic_hash != \
        compile_with(["ai_agency"]).semantic_hash


def test_a_tenant_that_declares_a_branch_nobody_authored_still_compiles(tmp_path: Path) -> None:
    """Named on the package, never raised. `domain_shadow` does not catch
    `AuthoringIntegrityError` by name, so a typo here used to be a tenant-wide outage."""
    from genios_engine.packs.compiler import (
        DomainCompiler, ExpertBrainCatalog, InMemoryExpertisePublisher, InMemoryRuntimeBrains)

    root, module = _corpus_with_a_vertical(tmp_path)
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(root), require_admission=False,
        runtime_brains=InMemoryRuntimeBrains(), publisher=InMemoryExpertisePublisher())

    package = compiler.compile(module._situation(model_ids=["law_firm"]))
    # `freeze_mapping` turns the builder's list into a tuple on the frozen package; what matters
    # is that the name survives to where a reader can see it.
    assert tuple(package.metadata["unresolved_variant_ids"]) == ("law_firm",)


# ── the words ───────────────────────────────────────────────────────────────────────────────

def _branch(doc_id: str, kind: str, render: dict | None = None):
    content = {"identity": {"id": doc_id, "kind": kind, "name": f"{kind} branch"}}
    if render is not None:
        content["render"] = render
    return _Doc(doc_id, content)


BASE_RENDER = {
    "artifact_kind": "brief",
    "render_hint": "Lead with the promise and the date.",
    "fallback": {"headline": "{entity} — promise past due",
                 "situation": "A promise to {entity} is past its date."},
}


def test_a_branch_rewords_the_card() -> None:
    """`render` is what a reader actually sees: it reaches `card_builder` as
    `capability_render`. A branch overriding it changes the words with no delivery change."""
    from genios_engine.packs.compiler.capability_resolver import variant_render_overlay

    branch = _branch("sales.vertical.ai_agency", "vertical",
                     {"fallback": {"headline": "{entity} — goodwill owed"}})
    merged = variant_render_overlay((branch,), BASE_RENDER)
    assert merged["fallback"]["headline"] == "{entity} — goodwill owed"


def test_a_branch_states_only_what_differs() -> None:
    """The contract every variant file already keeps — nothing is copied into a branch, and
    resolution is persona -> vertical -> model -> canonical. A branch that rewords the headline
    and says nothing about the kind keeps the canonical kind and the canonical sentence."""
    from genios_engine.packs.compiler.capability_resolver import variant_render_overlay

    branch = _branch("v", "vertical", {"fallback": {"headline": "new"}})
    merged = variant_render_overlay((branch,), BASE_RENDER)
    assert merged["artifact_kind"] == "brief"
    assert merged["fallback"]["situation"] == BASE_RENDER["fallback"]["situation"]


def test_the_more_specific_branch_wins() -> None:
    """A tenant declaring both a vertical and a persona is making two statements about itself.
    Where they touch the same words the narrower one knows more: a CTO at an AI agency reads a
    CTO's card. Order comes from `identity.kind`, not from whatever the files were named."""
    from genios_engine.packs.compiler.capability_resolver import variant_render_overlay

    vertical = _branch("z.vertical.agency", "vertical", {"fallback": {"headline": "vertical"}})
    persona = _branch("a.persona.cto", "persona", {"fallback": {"headline": "persona"}})
    # Passed vertical-first and persona-first; the id sort would flip them, the axis sort must not.
    assert variant_render_overlay((vertical, persona), BASE_RENDER)["fallback"]["headline"] \
        == "persona"
    assert variant_render_overlay((persona, vertical), BASE_RENDER)["fallback"]["headline"] \
        == "persona"


def test_a_branch_with_no_render_returns_the_base_object_itself() -> None:
    """Not a copy of it. `render` travels in the metadata hashed into the package's content
    address, so rebuilding an identical mapping would mint a new address for knowledge that did
    not change — the churn that took this database read-only twice."""
    from genios_engine.packs.compiler.capability_resolver import variant_render_overlay

    assert variant_render_overlay((_branch("m", "model"),), BASE_RENDER) is BASE_RENDER
    assert variant_render_overlay((), BASE_RENDER) is BASE_RENDER


def test_a_branch_can_reword_a_route_that_authored_no_copy() -> None:
    """A situation with no `render` block is the common case in the shipped corpus. A branch must
    still be able to speak for it rather than silently doing nothing."""
    from genios_engine.packs.compiler.capability_resolver import variant_render_overlay

    branch = _branch("v", "vertical", {"fallback": {"headline": "spoken for"}})
    assert variant_render_overlay((branch,), None)["fallback"]["headline"] == "spoken for"


def test_the_branchs_words_reach_the_package_through_a_real_compile(tmp_path: Path) -> None:
    """THE CALL SITE, not just the function. `variant_render_overlay` had five passing tests while
    the line that calls it could be deleted without failing one of them — the overlay was correct
    and unreachable, which is the exact shape of the defect this whole step exists to fix.

    `package.metadata["render"]` is what becomes `manifest.metadata["render"]`, which
    `deliver/pipeline` reads as `capability_render` and `card_builder` uses as its template. So
    this assertion is the last compiler-side hop before a human reads different words.
    """
    from genios_engine.packs.compiler import (
        DomainCompiler, ExpertBrainCatalog, InMemoryExpertisePublisher, InMemoryRuntimeBrains)

    root, module = _corpus_with_a_vertical(tmp_path)

    def compile_with(model_ids):
        compiler = DomainCompiler(
            catalog=ExpertBrainCatalog(root), require_admission=False,
            runtime_brains=InMemoryRuntimeBrains(), publisher=InMemoryExpertisePublisher())
        return compiler.compile(module._situation(model_ids=model_ids))

    canonical = (compile_with(["sales.model.b2b"]).metadata.get("render") or {})
    declared = (compile_with(["ai_agency"]).metadata.get("render") or {})

    headline = (declared.get("fallback") or {}).get("headline")
    assert headline == "{entity} — delivery capacity at risk", (
        "the declared branch's words did not reach the package the card is built from")
    assert (canonical.get("fallback") or {}).get("headline") != headline, (
        "both compiles produced the same copy, so this proves nothing about the overlay")
