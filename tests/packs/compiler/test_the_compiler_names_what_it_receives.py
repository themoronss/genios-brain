"""L2-1 · ⛔ the whole Domain Expertise compiler is annotated with the wrong situation type.

**MEASURED 2026-09-24, and this is the finding that made step 1 worth more than a rename.**

`domain_shadow.py:881` is the only production call:

    bso = publication.situation          # PublicationResult.situation -> contracts.situation, v2
    package = compiler.compile(bso, context_slice)

and `DomainCompiler.compile(situation: BusinessSituationObject)` resolves that annotation to
`contracts.domain_expertise` — **v1, the candidate.** Fifteen parameters across eight modules say
the same thing.

⛔ **NOTHING CATCHES IT, AND THE REASON IS ITSELF A FINDING.** The v2 object carries seven
compatibility properties — `importance_bp`, `confidence_bp`, `contested_fields`, `findings`,
`semantic_hash`, `domain_hints`, `brain_subject_keys` — whose own docstring says *"the v1 field
name, as a read"*. `expertise_builder.py:76` does `min(situation.confidence_bp, ...)` on a field
that exists on v1 and **not** on v2, and it works only because of that shim. `upgrade_situation`
already recorded the consequence in its own docstring:

    every consumer read the v1 compatibility views, so the typed contract was decorative

And the compiler's tests construct v1 — `tests/packs/compiler/l3_inputs.py` and
`test_domain_expertise_compiler.py` — so **the shape the compiler is tested on is a shape
production never sends it.** That is this project's recurring defect said in one line.

This suite is the guard. It does not change behaviour: Python does not enforce annotations, and
the runtime path is unchanged. It makes the seam state the truth, so the next reader of
`compile()` is not told the wrong thing.
"""
from __future__ import annotations

import inspect
import typing

import pytest

pytestmark = pytest.mark.unit

#: Every module in the compiler that names a situation type in a signature.
_COMPILER_MODULES = (
    "domain_compiler", "capability_resolver", "expertise_builder", "knowledge_retriever",
    "evidence_aggregator", "brain_resolver", "context_adapter", "runtime_brains",
)


def _situation_annotations():
    """Every (module, callable, parameter) whose annotation is one of the two situation types."""
    from genios_engine.contracts.domain_expertise import SituationCandidate
    from genios_engine.contracts.situation import BusinessSituationObject as Admitted

    found = []
    for name in _COMPILER_MODULES:
        mod = __import__(f"genios_engine.packs.compiler.{name}", fromlist=["x"])
        targets = []
        for attr, obj in vars(mod).items():
            if inspect.isclass(obj) and obj.__module__ == mod.__name__:
                targets += [(f"{attr}.{n}", f) for n, f in vars(obj).items()
                            if inspect.isfunction(f)]
            elif inspect.isfunction(obj) and obj.__module__ == mod.__name__:
                targets.append((attr, obj))
        for label, fn in targets:
            try:
                hints = typing.get_type_hints(fn)
            except Exception:
                continue
            for param, ann in hints.items():
                parts = (ann,) + typing.get_args(ann)
                if SituationCandidate in parts:
                    found.append((f"{name}.{label}", param, "candidate"))
                elif Admitted in parts:
                    found.append((f"{name}.{label}", param, "admitted"))
    return found


def test_the_seam_is_annotated_at_all():
    """A guard over an empty set passes for the wrong reason."""
    assert len(_situation_annotations()) >= 15, (
        "fewer situation-typed parameters than the 15 measured — if the compiler was refactored, "
        "re-measure before trusting anything below")


def test_no_compiler_parameter_claims_to_take_a_candidate():
    """⛔ **The finding, as a build failure.**

    Production hands the compiler an ADMITTED object — `publication.situation`, checked against
    `publication.admitted` two lines earlier. An annotation naming the candidate tells every
    reader the opposite, and the 16-field dataclass it names does not have the 28 fields the
    caller actually passes.
    """
    wrong = [(where, param) for where, param, kind in _situation_annotations()
             if kind == "candidate"]
    assert not wrong, (
        f"{len(wrong)} compiler parameters are annotated with the CANDIDATE and receive the "
        f"ADMITTED object on every sweep: {wrong}")


def test_the_publisher_and_the_compiler_agree_on_the_type():
    """The two ends of one seam, read from the code rather than asserted from memory."""
    from genios_engine.context.situation_publisher import PublicationResult
    from genios_engine.packs.compiler.domain_compiler import DomainCompiler

    produced = typing.get_type_hints(PublicationResult)["situation"]
    consumed = typing.get_type_hints(DomainCompiler.compile)["situation"]
    assert consumed in typing.get_args(produced) or consumed is produced, (
        f"the publisher produces {produced} and the compiler declares it takes {consumed}")


def test_the_compatibility_properties_are_what_made_this_invisible():
    """⛔ Not a complaint about the shim — a record of why fifteen wrong annotations survived.

    Remove any one of these and the mismatch becomes an `AttributeError` on the first sweep. They
    are load-bearing, and that is exactly why the annotation had to be the thing that got fixed.
    """
    from genios_engine.contracts.situation import BusinessSituationObject as Admitted

    shims = {n for n, v in vars(Admitted).items() if isinstance(v, property)}
    assert {"confidence_bp", "importance_bp"} <= shims, (
        "expertise_builder reads situation.confidence_bp and situation.importance_bp, which are "
        "v1 field names. Without these properties the production path raises on the first "
        "situation")
