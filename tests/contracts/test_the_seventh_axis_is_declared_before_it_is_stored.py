"""The readiness axis exists on the BLOCKING vector and not yet in storage — on purpose.

Atlas cell L2-07 — *"role/source-readiness completeness is not part of the blocking vector"* — is
answered by a seventh axis, `readiness`. This file pins the two things about that axis that a
later reader is most likely to get wrong:

1. **It is declared on one vector and not the other, and that is temporary and deliberate.**
   `contracts/situation.CONFIDENCE_AXES` has seven; `contracts/situation_evidence.CONFIDENCE_AXES`
   has six. The second is the STORAGE vector, and its `complete` property is the group gate's own
   row ("confidence vector axes present — all 6") taken as a count. Declaring a seventh axis there
   before `context_situations.confidence_readiness` exists would turn that gate permanently red
   for a reason nobody could look up, because there would be no column to inspect.

2. **It is not composed.** `admin` scores 1-of-2 required capabilities, and composing readiness
   would cap `overall_bp` at 5000 on all 310 admin situations through the weakest-axis law — two
   thirds of the stored corpus re-scored. That is a product decision about what the product should
   refuse to say, it is not answerable before the axis has been stored for a full sweep, and it is
   not this unit's to make.

⛔ AND THE DEFECT THAT MADE THIS FILE NECESSARY. The axis names were declared THREE times and only
two of them were constants: `context/situation_publisher.py` held a hand-written tuple of the six.
A seventh axis added to the contract would have been read by nothing there, published as `None` on
every situation, and reported as working by every test that only asked the contract. The publisher
now reads the constant, and `test_the_publisher_reads_the_constant_and_not_its_own_list` is what
keeps it reading it.

See `speedrun008/YCW27/layer-2-reasoning/16-AUDIT-AND-PLAN-the-readiness-axis.md`.
"""

from __future__ import annotations

import ast
import inspect

from genios_engine.contracts.situation import CONFIDENCE_AXES as BLOCKING_AXES
from genios_engine.contracts.situation import ConfidenceVector
from genios_engine.contracts.situation_evidence import CONFIDENCE_AXES as STORED_AXES

#: The axis this unit added, and the single name the two lists are allowed to differ by.
SEVENTH = "readiness"


def test_the_blocking_vector_carries_the_seventh_axis() -> None:
    assert BLOCKING_AXES[-1] == SEVENTH, (
        f"the readiness axis must be on the blocking vector — that is what cell L2-07 asks for. "
        f"Got {BLOCKING_AXES}")
    assert len(BLOCKING_AXES) == 7
    assert len(set(BLOCKING_AXES)) == 7, "an axis name is declared twice"


def test_the_storage_vector_does_not_yet_and_the_difference_is_exactly_one_declared_name() -> None:
    """⛔ The divergence is ONE UNIT LONG and this is its receipt.

    Asserted as an exact set difference rather than `len(...) == 6`, because the risk is not that
    storage falls behind — it is that it falls behind by something NOBODY DECLARED. A second axis
    quietly added to one list and not the other would pass a length check on the day it landed.
    """
    missing_from_storage = set(BLOCKING_AXES) - set(STORED_AXES)
    extra_in_storage = set(STORED_AXES) - set(BLOCKING_AXES)

    assert missing_from_storage == {SEVENTH}, (
        f"the two axis lists may differ by exactly {SEVENTH!r} and nothing else, until migration "
        f"0191 adds `context_situations.confidence_readiness`. Got {missing_from_storage}")
    assert extra_in_storage == set(), (
        f"storage names an axis the blocking vector does not: {extra_in_storage} — that is the "
        "divergence pointing the wrong way, and no unit declared it")


def test_the_seventh_axis_is_nullable_and_absent_from_composition() -> None:
    """A vector built without readiness composes to exactly what it did before the axis existed."""
    vector = ConfidenceVector(evidence_bp=9_000, freshness_bp=8_000, overall_bp=8_000,
                              composed_from=("evidence", "freshness"))

    assert vector.readiness_bp is None, "the axis must default to no basis, never to 0"
    assert SEVENTH not in vector.composed_from
    assert vector.overall_bp == 8_000, (
        "declaring an axis moved a composed number — the axis is REPORTED in this unit, and "
        "composing it re-scores 310 admin situations")
    assert SEVENTH not in vector.measured_axes, "an axis with no basis is not a measured one"
    assert vector.axes[SEVENTH] is None, "`axes` must report the absence, not omit the key"


def test_a_measured_readiness_still_may_not_manufacture_certainty() -> None:
    """When the axis IS composed — which is a later unit — the weakest-axis law must already
    cover it. Pinned now, while it is cheap, rather than after the first vector that needs it."""
    import pytest
    from pydantic import ValidationError

    # Admin's real number: 1 of 2 required capabilities fresh.
    ok = ConfidenceVector(evidence_bp=9_000, readiness_bp=5_000, overall_bp=5_000,
                          composed_from=("evidence", "readiness"))
    assert ok.overall_bp == 5_000

    with pytest.raises(ValidationError, match="manufacture certainty"):
        ConfidenceVector(evidence_bp=9_000, readiness_bp=5_000, overall_bp=9_000,
                         composed_from=("evidence", "readiness"))

    with pytest.raises(ValidationError, match="no basis"):
        ConfidenceVector(evidence_bp=9_000, overall_bp=9_000,
                         composed_from=("evidence", "readiness"))


def test_the_publisher_reads_the_constant_and_not_its_own_list() -> None:
    """⛔ F-1, pinned at the AST and not by grepping for a word.

    `_confidence` used to carry a hand-written tuple of the six axis names. The failure that
    makes this expensive is silent: the contract grows an axis, the publisher does not, and every
    published situation carries `None` on it while the contract-level tests all pass.

    The check is structural — no `ast.Tuple` or `ast.List` of string constants in the function —
    so it cannot be satisfied by renaming a variable, and cannot be broken by a docstring that
    happens to quote the axis names.
    """
    from genios_engine.context import situation_publisher

    tree = ast.parse(inspect.getsource(situation_publisher._confidence))
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    literal_lists = [
        node for node in ast.walk(function)
        if isinstance(node, (ast.Tuple, ast.List))
        and len(node.elts) >= 3
        and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts)
    ]
    assert literal_lists == [], (
        "`_confidence` spells out a list of names instead of reading `CONFIDENCE_AXES`. A third "
        "copy of the axis vocabulary is how the seventh axis gets declared on the contract and "
        "published as None on every situation, with every contract test still green.")

    names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    assert "CONFIDENCE_AXES" in names, (
        "`_confidence` must read the constant by name — that is the only thing that makes an "
        "eighth axis flow without a second edit here")


def test_every_axis_on_the_contract_has_a_field_to_hold_it() -> None:
    """The constant and the model cannot drift: a name in `CONFIDENCE_AXES` with no `<name>_bp`
    field makes `axes` raise `AttributeError` on a renderer, which is the failure one layer worse
    than a missing number."""
    for axis in BLOCKING_AXES:
        assert f"{axis}_bp" in ConfidenceVector.model_fields, (
            f"`CONFIDENCE_AXES` names {axis!r} and `ConfidenceVector` has no {axis}_bp field")

    declared = {name[:-3] for name in ConfidenceVector.model_fields if name.endswith("_bp")}
    assert declared - {"overall"} == set(BLOCKING_AXES), (
        "a `*_bp` field exists that `CONFIDENCE_AXES` does not name — `axes` and `measured_axes` "
        "both iterate the constant, so such a field is invisible to every reader")
