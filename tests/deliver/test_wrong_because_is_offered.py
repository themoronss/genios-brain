r"""L6 STEP-02 · `M14.C1.U02` — "Wrong because…" offers what the API accepts.

⛔ ONE VOCABULARY, FIVE READERS, CHANGED TOGETHER OR NOT AT ALL. Widening what the card offers
without widening what the API accepts gives the founder a button the server refuses with
`allowed_reasons`. That is `FEATURE_CARDS_FROM_SITUATIONS` again — *"the reader was looking for a
word the writer rejected"* — which cost this codebase a lane no tenant could switch on.
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

def test_the_card_offers_exactly_what_the_api_accepts():
    """⛔ Offering a button the server refuses is `FEATURE_CARDS_FROM_SITUATIONS` again — "the
    reader was looking for a word the writer rejected" — which cost a lane no tenant could enable."""
    from genios_engine.deliver.actions import WRONG_REASONS
    from genios_engine.deliver.card_builder import _WRONG_REASONS

    assert set(WRONG_REASONS) == set(_WRONG_REASONS) == set(ALL_REASONS)



def test_neither_side_holds_its_own_copy_of_the_list():
    from genios_engine.deliver import actions, card_builder

    for module in (actions, card_builder):
        mods = {(n.module or "") for n in ast.walk(ast.parse(pathlib.Path(module.__file__)
                                                             .read_text()))
                if isinstance(n, ast.ImportFrom)}
        assert "genios_engine.contracts.learning_attribution" in mods



def test_every_reason_appears_in_exactly_one_group_a_person_can_read():
    """"The facts are wrong" is a sentence somebody can pick. "capture" is not."""
    from genios_engine.deliver.card_builder import _WRONG_REASON_GROUPS

    flat = [r for group in _WRONG_REASON_GROUPS.values() for r in group]
    assert sorted(flat) == sorted(ALL_REASONS), "a reason in no group is a reason nobody can choose"
    assert len(flat) == len(set(flat)), "a reason in two groups is two buttons for one answer"



def test_the_groups_are_all_lists_because_a_tuple_serialises_differently():
    from genios_engine.deliver.card_builder import _WRONG_REASON_GROUPS

    assert all(isinstance(v, list) for v in _WRONG_REASON_GROUPS.values())



def test_the_builder_version_was_bumped():
    """`BUILDER_VERSION`'s own rule: *"BUMP THIS whenever what a card can SAY changes."* The card
    now carries a lane and eleven reasons, so an existing untouched card must be recomposed —
    otherwise the improvement lands only on signals nobody has seen yet."""
    from genios_engine.deliver.card_builder import BUILDER_VERSION

    assert BUILDER_VERSION != "card-builder.v5-evidence-backed-copy"


# ── the router ────────────────────────────────────────────────────────────────────────────────

