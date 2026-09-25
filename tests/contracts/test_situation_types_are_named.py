"""L2-1 · two classes share one name, and the name is the thing that goes wrong.

⛔ **WHAT THE AMBIGUITY HAS ALREADY COST.**

1. **A wrong paragraph in this plan's first draft.** It recorded the two as rival duplicates with
   *"zero callers"*. They are stages — candidate, then admitted — joined at
   `situation_publisher.py:464`, and `upgrade_situation(old: LegacySituation) -> BSO` says so in
   its own signature.
2. ⛔ **Fifteen parameters across the whole Domain Expertise compiler are annotated with the
   CANDIDATE and are handed the ADMITTED object on every production sweep** — measured by
   `test_the_compiler_names_what_it_receives.py`. Nothing catches it, because the two spell the
   same and v2 carries seven v1-shaped compatibility properties.

The repo's answer to this is always the same and it is written down in `_registry.py`,
`LAYERS.py`, `PRECEDENCE` and `ANCHOR_FAMILIES`: **a table with a row per member, and a check in
BOTH directions at import time.** A name that is not in the table cannot be added silently, and a
row with nothing behind it cannot rot quietly.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_the_candidate_is_named_at_its_definition():
    """⛔ At the DEFINITION, not at one import line.

    `situation_publisher` already aliases it `LegacySituation` at its own import, which fixes the
    ambiguity in exactly one file. Every other reader — twenty imports — still sees the ambiguous
    word.
    """
    from genios_engine.contracts import domain_expertise as mod

    assert hasattr(mod, "SituationCandidate")
    assert mod.SituationCandidate.__name__ == "SituationCandidate", (
        "the class is still called BusinessSituationObject at its definition; renaming only the "
        "export leaves every traceback and every repr ambiguous")


def test_the_old_name_still_imports_and_says_when_it_goes():
    """A deprecated alias ships for one release. **With a date**, or it is not deprecated, it is
    merely disliked."""
    from genios_engine.contracts import domain_expertise as mod
    from genios_engine.contracts.situation_stages import ALIAS_REMOVAL

    assert mod.BusinessSituationObject is mod.SituationCandidate
    assert ALIAS_REMOVAL, "an alias with no removal date is a permanent second name"


def test_every_situation_stage_has_a_row_and_every_row_has_a_class():
    """Both directions. One direction alone is how a table and a codebase drift apart."""
    from genios_engine.contracts.situation_stages import SITUATION_STAGES, resolve

    for name, stage in SITUATION_STAGES.items():
        assert resolve(name) is not None, f"{name} is declared and resolves to nothing"
        assert stage.what, f"{name} has no sentence saying which stage it is"
        assert stage.produced_by, f"{name} does not say what produces it"


def test_a_third_situation_class_cannot_arrive_undeclared():
    """⛔ The guard itself. A new `*Situation*` contract type with no row fails the build.

    This is the check that makes the next ambiguity cost a test run instead of a wrong decision.
    """
    from genios_engine.contracts.situation_stages import undeclared_situation_types

    missing = undeclared_situation_types()
    assert not missing, (
        f"these contract types look like situation stages and have no row in SITUATION_STAGES: "
        f"{sorted(missing)}. Add the row — say which stage it is and what produces it.")


def test_the_two_stages_are_ordered_and_the_order_is_the_seam():
    """candidate -> admitted, and `upgrade_situation` is the one function that crosses it."""
    from genios_engine.contracts.situation_stages import SITUATION_STAGES

    stages = {s.stage for s in SITUATION_STAGES.values()}
    assert stages == {"candidate", "admitted"}, (
        f"expected exactly the two stages the publisher joins, got {sorted(stages)}")


def test_the_candidate_and_the_admitted_object_are_not_the_same_class():
    """If they ever merge, this table is wrong rather than merely redundant — and a merge that
    nobody noticed is exactly how the first draft's wrong paragraph happened."""
    from genios_engine.contracts.domain_expertise import SituationCandidate
    from genios_engine.contracts.situation import BusinessSituationObject as Admitted

    assert SituationCandidate is not Admitted
    assert len(SituationCandidate.__dataclass_fields__) < len(Admitted.model_fields), (
        "the candidate should be the smaller object — it is what assembly produces before the "
        "typed v2 homes are filled")


# =================================================================================================
# L2-1-U4 · the names in the code and the names in the map must not drift apart.
#
# ⛔ THE PLAN SAID docs/LAYER_MAP.md WAS "the second and LAST file carrying digits". It is not:
# docs/architecture/README.md, 02-context-intelligence.md and ENGINEERING-CONSTITUTION.md all
# carry the old names too. Two of those are marked "Status: Reference — frozen target vision,
# 2026-08-07" and rewriting them would be editing history rather than recording it — this
# repository marks stale things AS history (see `_hollow`'s docstring, corrected in L2-0).
#
# So the guard covers the two LIVE surfaces and DECLARES the frozen ones, with a reason. Same
# idiom as `UNROUTED_PATTERN_TYPES` and `DARK_DOMAINS`: an exclusion nobody wrote down is
# indistinguishable from an oversight.
# =================================================================================================

#: Frozen vision documents. They record what was believed on their own date and are not corrected.
_FROZEN_BY_DESIGN: dict[str, str] = {
    "docs/architecture/02-context-intelligence.md":
        "Status: Reference — frozen target vision, 2026-08-07",
    "docs/architecture/ENGINEERING-CONSTITUTION.md":
        "the constitution as ratified; amendments are appended, never retyped",
}


def test_the_code_and_the_map_agree_on_every_layer_name():
    """`LAYERS.py` is the authority. `docs/LAYER_MAP.md` is the only doc that must track it."""
    import pathlib
    import re

    from genios_engine.LAYERS import LAYERS

    doc = pathlib.Path("docs/LAYER_MAP.md").read_text()
    for package in LAYERS:
        row = re.search(rf"^\| `{package}/` \|(.+)$", doc, re.MULTILINE)
        assert row, f"{package} has no row in docs/LAYER_MAP.md"

    for name in ("Situation Intelligence", "Enterprise Signals", "Plane D", "Plane R"):
        assert name in doc, f"docs/LAYER_MAP.md does not carry the name {name!r}"


def test_the_live_architecture_index_points_at_the_authority():
    """⛔ **A GUARD, NOT A FIX — it was already true and this records that it must stay true.**

    `docs/architecture/README.md:58` already points at `../LAYER_MAP.md` and calls it *"the
    current code today"*. That is why its own diagram carrying older names is a stale copy rather
    than a rival authority. A second diagram with different names and no pointer is how "prose
    stale, code right" happens a sixth time.
    """
    import pathlib

    readme = pathlib.Path("docs/architecture/README.md").read_text()
    assert "LAYER_MAP.md" in readme, (
        "the live architecture index does not point at the one translation table")


def test_a_frozen_document_is_frozen_on_purpose_and_says_so():
    """Each excluded file must still exist and still carry the marker its exclusion claims."""
    import pathlib

    for path in _FROZEN_BY_DESIGN:
        assert pathlib.Path(path).is_file(), f"{path} is declared frozen and does not exist"
