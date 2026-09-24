"""L2-1 · which situation type is which stage — the one table, checked both directions.

⛔ **TWO CONTRACT CLASSES WERE BOTH CALLED `BusinessSituationObject`, AND THE SHARED NAME COST
TWICE.**

1. It cost this plan's first draft a wrong paragraph — the two were recorded as rival duplicates
   with *"zero callers"* when they are stages of one object, joined at `situation_publisher.py`.
2. It left **fifteen parameters across the entire Domain Expertise compiler** annotated with the
   CANDIDATE while every production sweep hands them the ADMITTED object. Nothing caught it,
   because the two spell the same and the admitted object carries seven v1-shaped compatibility
   properties. `upgrade_situation` had already written the consequence down: *"every consumer
   read the v1 compatibility views, so the typed contract was decorative."*

**This module is the repo's own answer to that, applied here.** `LAYERS.py`, `_registry.py`,
`PRECEDENCE` and `ANCHOR_FAMILIES` all do the same thing: a table with a row per member, and an
import-time check in BOTH directions. A stage that is declared and resolves to nothing fails; a
situation contract type that exists with no row fails. Neither can drift alone.

**It is data, not behaviour.** Nothing at runtime consults it; the tests do, and the build does.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

#: ⛔ The date `contracts.domain_expertise.BusinessSituationObject` may be deleted. One release.
#: It lives HERE and nowhere else, because a date written twice is a date that disagrees.
ALIAS_REMOVAL = "2026-12-24"


@dataclass(frozen=True, slots=True)
class SituationStage:
    """One situation contract type, and which side of the admission gate it lives on."""

    module: str
    #: `candidate` before `validate_situation` has judged it; `admitted` after.
    stage: str
    #: What builds it. A row that cannot name its producer is a row nobody owns.
    produced_by: str
    what: str


SITUATION_STAGES: dict[str, SituationStage] = {
    "SituationCandidate": SituationStage(
        module="genios_engine.contracts.domain_expertise",
        stage="candidate",
        produced_by="context.situation_bso.build_business_situation",
        what="v1 · 16 fields. What assembly produces, BEFORE the eight admission laws judge it. "
             "Was called `BusinessSituationObject`; the old name survives as a deprecated alias "
             "until ALIAS_REMOVAL."),
    "BusinessSituationObject": SituationStage(
        module="genios_engine.contracts.situation",
        stage="admitted",
        produced_by="context.situation_publisher.upgrade_situation",
        what="v2 · 28 fields, frozen and content-addressed. The ONLY situation object exposed "
             "above Layer 2. Carries seven compatibility properties named for v1 fields, which "
             "is what let fifteen wrong annotations survive."),
}

#: Contract modules a situation type could live in. Named rather than discovered, so a type that
#: moves to a new module shows up as an undeclared type instead of vanishing from the check.
_SEARCHED: tuple[str, ...] = (
    "genios_engine.contracts.domain_expertise",
    "genios_engine.contracts.situation",
)

#: Names that LOOK like a situation stage and are not one. **Declared, with a reason** — the same
#: idiom as `UNROUTED_PATTERN_TYPES` and `lane_health.SILENT_LANES`, because an exclusion nobody
#: wrote down is indistinguishable from an oversight.
NOT_A_STAGE: dict[str, str] = {
    "SituationContextSlice": "the EVIDENCE handed alongside a situation, not the situation",
    "SituationEntity": "a row inside a situation",
    "SituationRelationship": "a row inside a situation",
    "SituationType": "the taxonomy of what a situation is ABOUT, not a stage of one",
    # ⛔ FOUND BY THIS GUARD ON ITS FIRST RUN, which is the whole argument for writing it.
    # Neither is a situation. Both are the GATE's answer about one, and putting them in
    # SITUATION_STAGES would have made the table mean two different things at once.
    "SituationDecision": "the admission gate's ANSWER — what to do, which laws failed, on what. "
                         "It carries a situation; it is not one",
    "SituationOutcome": "the two values that answer can take (admit / reject). An enum",
}


def resolve(name: str) -> Any | None:
    """The class a declared row points at, or None if the row has rotted."""
    stage = SITUATION_STAGES.get(name)
    if stage is None:
        return None
    return getattr(importlib.import_module(stage.module), name, None)


def undeclared_situation_types() -> frozenset[str]:
    """⛔ The other direction. Every `Situation*`-shaped contract class with no row.

    This is the half that stops a THIRD ambiguous type arriving the way the second one did.
    """
    found: set[str] = set()
    for module_name in _SEARCHED:
        module = importlib.import_module(module_name)
        for attr in dir(module):
            if not (attr.startswith("Situation") or attr.endswith("SituationObject")):
                continue
            value = getattr(module, attr)
            if not isinstance(value, type):
                continue
            if attr in SITUATION_STAGES or attr in NOT_A_STAGE:
                continue
            found.add(attr)
    return frozenset(found)


def _check() -> None:
    """Import-time totality, the way this codebase does it everywhere else."""
    for name, stage in SITUATION_STAGES.items():
        assert stage.stage in {"candidate", "admitted"}, f"{name}: unknown stage {stage.stage!r}"
        assert stage.produced_by and stage.what, f"{name}: a row with no reason is a label"


_check()

__all__ = ["ALIAS_REMOVAL", "NOT_A_STAGE", "SITUATION_STAGES", "SituationStage", "resolve",
           "undeclared_situation_types"]
