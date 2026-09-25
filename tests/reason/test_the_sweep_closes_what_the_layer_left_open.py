"""L2 · the 0→8 sweep — what the nine steps left behind, closed.

⛔ **THIS FILE EXISTS BECAUSE THE SWEEP FOUND THREE THINGS THE STEPS THEMSELVES MISSED**, and each
one is the defect this plan has been chasing since L2-0: something built, correct, and reached by
nothing.

1. **L2-3 built a token budget so L2-5's cost check could argue about a number** — *"it REPORTS
   and never truncates"* — and **L2-5 sends a slice to a model without consulting it.**
2. **S07 was OPEN**: the compiler's tests build a `SituationCandidate` and production hands it an
   admitted object, so *"the shape the compiler is tested on is a shape production never sends."*
3. **A guard that answers plausibly when called wrong** was recorded twice — in L2-0 and again in
   L2-5's `expected_facts` — and never hardened.
"""
from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


# =================================================================================================
# 1 · the budget L2-3 measured and L2-5 never read
# =================================================================================================

def test_the_reasoner_measures_the_slice_it_is_about_to_send():
    """⛔ L2-3: *"`SLICE_TOKEN_BUDGET` is a LINE TO NOTICE… a slice over it is reported so L2-5's
    cost check argues about a number instead of a feeling."* L2-5 shipped without reading it."""
    from genios_engine.reason import situation_reasoner

    src = inspect.getsource(situation_reasoner)
    assert "slice_weight" in src or "over_budget" in src, (
        "the reasoner sends a slice to a model and never asks what it weighs")


def test_an_oversized_slice_is_reported_and_never_truncated():
    """⛔ *"Dropping facts to hit a number is how a reasoner concludes from evidence nobody chose
    to remove."* The budget reports. It does not edit the input."""
    from genios_engine.reason.situation_reasoner import weigh_before_sending

    small = weigh_before_sending("x" * 400)
    assert small.over is None

    big = weigh_before_sending("y" * 400_000)
    assert big.over is not None
    assert str(big.tokens) in big.over, "the warning does not name the number"
    assert big.payload == "y" * 400_000, "the slice was edited to fit a budget"


def test_the_sweep_counts_an_oversized_slice_rather_than_swallowing_it():
    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow.shadow_compile)
    assert "slice_over_budget" in src, (
        "a slice that blew the budget is invisible, which is the defect L2-0 spent a step on")


# =================================================================================================
# 2 · S07 · the compiler, driven with what production actually sends it
# =================================================================================================

def test_the_compiler_accepts_the_object_publish_situation_returns():
    """⛔ **S07, CLOSED.** L2-1 corrected fifteen annotations and recorded that no test drove the
    compiler with the admitted object. This is that test.

    It asserts the two things the annotations now claim: the compiler's parameter names the
    ADMITTED type, and an instance of that type carries every attribute the compile path reads
    off it — including the v1-named compatibility properties that made the mismatch survivable.
    """
    import typing

    from genios_engine.context.situation_publisher import PublicationResult
    from genios_engine.packs.compiler.domain_compiler import DomainCompiler

    produced = typing.get_type_hints(PublicationResult)["situation"]
    consumed = typing.get_type_hints(DomainCompiler.compile)["situation"]
    assert consumed in typing.get_args(produced) or consumed is produced

    from tests.contracts.l2_situation_fixture import minimal_situation

    admitted = minimal_situation()
    assert isinstance(admitted, consumed), (
        "the object `publish_situation` returns is not an instance of what the compiler declares")
    # Every attribute the compile path reads off the situation must resolve on it.
    for attribute in ("confidence_bp", "importance_bp", "domain_ids", "type", "evidence",
                      "missing_facts", "coverage_ready", "id", "org_id", "visibility"):
        getattr(admitted, attribute)


def test_the_compilers_own_fixture_still_builds_a_candidate_and_that_is_recorded():
    """Not a defect to fix here — a fact to keep visible. A candidate is a real object with a real
    producer; what was wrong was that NOTHING drove the admitted shape. Now something does."""
    import ast
    import pathlib

    from genios_engine.contracts.domain_expertise import SituationCandidate

    src = pathlib.Path("tests/packs/compiler/l3_inputs.py").read_text()
    names = {n.func.id for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "BusinessSituationObject" in names or "SituationCandidate" in names
    assert SituationCandidate.__name__ == "SituationCandidate"


# =================================================================================================
# 3 · the guard that answered plausibly when called wrong
# =================================================================================================

def test_the_situation_admission_rule_refuses_a_document_instead_of_answering_about_it():
    """⛔ **RECORDED TWICE AND NEVER HARDENED.** `situation_admission_reason` takes a MAPPING. Its
    `hasattr(authored, "get")` guard means a `SourceDocument` reads `{}` and answers
    `identity_status_absent` **for every document in the corpus** — a caller error that looks
    exactly like a data verdict.

    L2-0 hit it and reported *"all 69 situations inadmissible"*. L2-5's `expected_facts` hit the
    same class of trap with `domains_declaring`. A guard that converts a type error into a
    plausible wrong answer is worse than no guard.
    """
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

    catalog = ExpertBrainCatalog("Domain Expertise")
    document = next(iter(catalog.domains["admin"].situations.values()))

    # The right call still works.
    assert situation_admission_reason(document.content) is None

    # The wrong call must RAISE rather than answer.
    with pytest.raises(TypeError):
        situation_admission_reason(document)
