"""STEP-11 · the route plan carries what doing nothing costs, in the situation's own words.

    .venv/bin/python -m pytest tests/packs/compiler/test_the_plan_carries_what_doing_nothing_costs.py -q

Tree `yc2_w27_s11 · M30.C2.L-logic.V0.U04`. A situation may now author `do_nothing_consequence`
(M30.C2.L-contract.V0.U01), and the decider reads the manifest's — which the compiled adapter
builds from the PACKAGE alone, and the package carried no situation sentence: every compiled
decision said *"The <type> situation is left unaddressed while its evidence compounds."* The
resolver now lifts the sentence off the leading situation that wrote one — ranked the way the
card copy is, by the author's priority, ties on id — and the builder writes it into the package
ONLY when one was authored, so every package that exists today keeps its content address.
"""
from __future__ import annotations

from l3_inputs import SALES_ANCHOR_TYPE, build_authoring_root, build_situation, build_slice

from genios_engine.packs.compiler import DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains
from genios_engine.packs.compiler.capability_resolver import CapabilityResolver

SENTENCE = "The investor's next cohort closes and the conversation restarts from zero."


def _situation(root, name: str, *, consequence: str | None, priority_bp: int | None):
    """A second situation on the anchor route, beside the fixture's own."""
    cap = root / "Sales Expertise" / "capabilities/01-qualification/lead-qualification"
    extra = ""
    if consequence is not None:
        extra += f"do_nothing_consequence: {consequence!r}\n"
    if priority_bp is not None:
        extra += f"priority_bp: {priority_bp}\n"
    (cap / f"situations/{name}.yaml").write_text(f"""
identity:
  id: sales.sit.{name}
  name: {name}
  domain: sales
  owner_capability: sales.qualification.lead_qualification
  version: 1.0.0
  status: stable
matches:
  l2_situation_types: [{SALES_ANCHOR_TYPE}]
  when: []
objects:
  load: [sales.obj.core.account]
{extra}metadata:
  owner: Sales
  review_status: approved
  reviewed_by: a.named.human@example.com
""")
    registry = root / "Sales Expertise" / "registry" / "situation-capability-map.yaml"
    text = registry.read_text()
    old = "situations: [sales.sit.anchor]"
    assert text.count(old) == 1
    registry.write_text(text.replace(old, f"situations: [sales.sit.anchor, sales.sit.{name}]"))


def _author_on_anchor(root, consequence: str, priority_bp: int | None = None) -> None:
    anchor = (root / "Sales Expertise" / "capabilities/01-qualification/lead-qualification"
              / "situations/anchor.yaml")
    extra = f"do_nothing_consequence: {consequence!r}\n"
    if priority_bp is not None:
        extra += f"priority_bp: {priority_bp}\n"
    anchor.write_text(anchor.read_text() + extra)


def _plan(root):
    return CapabilityResolver(ExpertBrainCatalog(root), require_admission=False).resolve(
        build_situation(), build_slice())


def _package(root):
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(root),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    return compiler.compile(build_situation(), build_slice())


def test_an_authored_sentence_reaches_the_plan_and_the_package(tmp_path):
    root = build_authoring_root(tmp_path)
    _author_on_anchor(root, SENTENCE)
    plan = _plan(root)
    assert (plan.do_nothing_consequence, plan.do_nothing_situation_id) == (
        SENTENCE, "sales.sit.anchor")
    package = _package(root)
    assert package.metadata["do_nothing_consequence"] == SENTENCE
    assert package.metadata["do_nothing_situation_id"] == "sales.sit.anchor"


def test_no_sentence_means_no_key_so_no_package_re_mints(tmp_path):
    """Omit-when-empty, `expertise_builder`'s own rule for the pattern receipt: a key written None
    on every package is a key hashed into every package's content address."""
    root = build_authoring_root(tmp_path)
    plan = _plan(root)
    assert (plan.do_nothing_consequence, plan.do_nothing_situation_id) == (None, None)
    package = _package(root)
    assert "do_nothing_consequence" not in package.metadata
    assert "do_nothing_situation_id" not in package.metadata


def test_a_blank_sentence_is_no_sentence(tmp_path):
    root = build_authoring_root(tmp_path)
    _author_on_anchor(root, "   ")
    assert _plan(root).do_nothing_consequence is None


def test_the_higher_priority_situation_says_it(tmp_path):
    root = build_authoring_root(tmp_path)
    _author_on_anchor(root, "the anchor's words", priority_bp=3_000)
    _situation(root, "louder", consequence="the louder situation's words", priority_bp=9_000)
    plan = _plan(root)
    assert set(plan.situation_ids) == {"sales.sit.anchor", "sales.sit.louder"}
    assert (plan.do_nothing_consequence, plan.do_nothing_situation_id) == (
        "the louder situation's words", "sales.sit.louder")


def test_a_tie_is_broken_by_id_not_by_reading_order(tmp_path):
    """`aardvark` is listed AFTER the anchor on the route and sorts BEFORE it, so reading order
    and id order disagree — and the id must win, or two compiles of one corpus could differ."""
    root = build_authoring_root(tmp_path)
    _author_on_anchor(root, "the anchor's words", priority_bp=5_000)
    _situation(root, "aardvark", consequence="aardvark's words", priority_bp=5_000)
    assert _plan(root).do_nothing_situation_id == "sales.sit.aardvark"


def test_a_folded_sentence_arrives_without_its_trailing_newline(tmp_path):
    """`do_nothing_consequence: >` — the corpus's usual style — ends in a newline the decider would
    otherwise carry into its prompt."""
    root = build_authoring_root(tmp_path)
    anchor = (root / "Sales Expertise" / "capabilities/01-qualification/lead-qualification"
              / "situations/anchor.yaml")
    anchor.write_text(anchor.read_text() + f"do_nothing_consequence: >\n  {SENTENCE}\n")
    assert _plan(root).do_nothing_consequence == SENTENCE


def test_a_situation_that_wrote_none_does_not_outrank_one_that_did(tmp_path):
    root = build_authoring_root(tmp_path)
    _author_on_anchor(root, SENTENCE, priority_bp=2_000)
    _situation(root, "silent", consequence=None, priority_bp=9_900)
    plan = _plan(root)
    assert (plan.do_nothing_consequence, plan.do_nothing_situation_id) == (
        SENTENCE, "sales.sit.anchor")
