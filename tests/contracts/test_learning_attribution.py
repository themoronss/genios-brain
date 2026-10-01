r"""L6 STEP-01 · `M14.C1.U01` — eleven reasons, one layer each, closed both ways.

⛔ `wrong_facts` ALONE covered a mis-read email (capture), a fact linked to the wrong company
(context) and a stale value nobody refreshed (capture again) — three teams, one word, and no way to
debit any of them.

⛔ AND THE TOPOLOGY GATE CAUGHT MY FIRST DESIGN. The module imported `genios_engine.LAYERS` so the
layer names could be checked at import time, and
`test_layer_topology.py::test_contracts_import_nothing_above_platform` failed the build:
*"contracts/ is the boundary vocabulary — it may depend on platform/stdlib only."* The gate was
right. The requirement moved here.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import pathlib

import pytest

from genios_engine.LAYERS import LAYERS
from genios_engine.contracts import learning_attribution as LA
from genios_engine.contracts.learning_attribution import (ALL_REASONS, ATTRIBUTION,
                                                          DEBITABLE_LAYERS, LAYER_ORDER,
                                                          LEGACY_REASONS, PrecisionRole,
                                                          WrongReason, attribute,
                                                          reasons_for_layer)
from genios_engine.feedback.attribution import (AttributionReport,
                                                every_legacy_reason_still_grades_the_way_it_did,
                                                route, timing_never_grades_accuracy)

REPO = pathlib.Path(__file__).resolve().parents[2]


# ── the vocabulary ────────────────────────────────────────────────────────────────────────────

def test_there_are_eleven_reasons():
    assert len(ALL_REASONS) == 11 == len(set(ALL_REASONS))



@pytest.mark.parametrize("reason", sorted(WrongReason, key=lambda r: r.value))
def test_every_reason_debits_exactly_one_layer_and_names_a_fix(reason):
    """⛔ A reason that debits two layers debits neither: the next person to read the number cannot
    act on it. Where a reason genuinely spans two, the reason is drawn wrongly and gets split —
    which is what having eleven rather than three is FOR."""
    att = ATTRIBUTION[reason]
    assert att.layer in DEBITABLE_LAYERS
    assert att.fix.strip() and not att.fix.endswith(".py"), (
        "a module path goes stale on the next refactor; a sentence does not")



def test_every_reason_has_an_attribution_and_every_attribution_a_reason():
    assert set(ATTRIBUTION) == set(WrongReason)



def test_every_debitable_layer_is_reachable_from_some_reason():
    """⛔ A layer nothing can debit is a layer this map cannot report on, and the fix somebody
    eventually applies is to widen a reason until it is reachable — at which point the widening,
    not the design, decides who gets blamed."""
    assert {a.layer for a in ATTRIBUTION.values()} == DEBITABLE_LAYERS



def test_the_learner_cannot_debit_itself():
    """L6 READS these debits. A reason attributing failure to the learner would have the learner
    grade itself; if learning is wrong, that shows up as every other layer's debits being wrong at
    once, which is a different investigation and not a button on a card."""
    assert "feedback" not in DEBITABLE_LAYERS
    assert all(a.layer != "feedback" for a in ATTRIBUTION.values())


# ── the single source of truth for layer names ────────────────────────────────────────────────


def test_every_debitable_layer_is_a_real_package_in_layers_py():
    """⛔ THE CHECK THAT MOVED HERE, AND WHY. The first version of `learning_attribution` imported
    `genios_engine.LAYERS` so this could run at import time, and
    `test_layer_topology.py::test_contracts_import_nothing_above_platform` failed the build on it —
    *"contracts/ is the boundary vocabulary — it may depend on platform/stdlib only."* The gate was
    right: `contracts/` is what every layer imports, so a dependency added there is added
    everywhere. The requirement stands and lives here instead."""
    assert DEBITABLE_LAYERS <= set(LAYERS), sorted(DEBITABLE_LAYERS - set(LAYERS))



def test_every_layer_number_matches_layers_py():
    """A second list of numbers is a second source of truth, and the first rename makes them
    disagree silently. This is the assertion that keeps them honest."""
    assert LAYER_ORDER == {name: LAYERS[name] for name in LAYER_ORDER}



def test_contracts_does_not_import_the_topology_it_describes():
    tree = ast.parse(pathlib.Path(LA.__file__).read_text())
    mods = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("LAYERS" in m for m in mods), mods



def test_the_three_original_spellings_survived():
    """⛔ Every judgment already recorded grades on these words. Renaming one silently re-scores the
    28-day window — a rule that was fine on Monday gets muted on Tuesday with no event to point at."""
    assert LEGACY_REASONS <= set(ALL_REASONS)



def test_an_attribution_refuses_a_layer_nobody_can_debit():
    with pytest.raises(ValueError, match="not a debitable layer"):
        LA.Attribution("feedback", PrecisionRole.NONE, "grade yourself")



def test_an_attribution_refuses_to_exist_without_a_stated_fix():
    with pytest.raises(ValueError, match="no stated fix"):
        LA.Attribution("capture", PrecisionRole.NONE, "   ")



def test_a_team_can_list_the_reasons_it_owns():
    assert set(reasons_for_layer("context")) == {"wrong_subject", "bad_link"}
    assert reasons_for_layer("feedback") == ()



def test_an_unknown_reason_returns_none_rather_than_raising():
    """A judgment row is written by a client; an unrecognised reason must not crash a calibration
    pass over a whole tenant."""
    assert attribute("nonsense") is None
    assert attribute(WrongReason.BAD_LINK) is not None
    assert attribute("bad_link") is not None


