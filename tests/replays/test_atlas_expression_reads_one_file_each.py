"""STEP-14 · the Atlas's replay 02, expressed: each introduction its own file — the predicates that say so.

    pytest tests/replays/test_atlas_expression_reads_one_file_each.py -q

Tree `yc2_w27_s14` M43.C6.L-integration.V2.U08 (s14-D5). Replay 02's pass conditions are about SEVERAL contacts at
once — *"every decision names exactly one introduced contact"*, *"each of the three carries a distinct lifecycle"* —
which one `card_about` list cannot say. Three predicates (`tests/replays/atlas_expression.check`):

  each        a list of term groups, one per contact: exactly one card the app showed about each, and no card about
              two of them (target precision);
  open_at_end each group's card is still open after the last sweep (none closed by another contact's reply);
  versioned   the card about these terms has two versions or more (it moved on — never a second card).

Pure: judged on hand-made runs, like `test_marking`.
"""
from __future__ import annotations

from tests.replays import atlas_expression as ax
from tests.replays.test_marking import _card, _run

GROUPS = [["Tara", "Quillstone"], ["Dev", "Ferncrest"], ["Anaya", "Harborline"]]
CARDS = [_card("c1", "Send Tara Sethi your deck"), _card("c2", "Offer Dev Malhotra a demo"),
         _card("c3", "Answer Anaya Kulkarni by Monday")]


def test_one_card_for_each_contact_passes():
    assert ax.check({"each": GROUPS}, _run(cards=CARDS)) == []


def test_a_card_naming_two_contacts_fails_target_precision():
    pooled = [_card("c1", "Send Tara Sethi your deck, and offer Dev Malhotra a demo"), CARDS[2]]
    problems = ax.check({"each": GROUPS}, _run(cards=pooled))
    assert any("names more than one contact" in p for p in problems), problems


def test_a_contact_with_no_card_or_two_fails():
    assert any("Dev/Ferncrest" in p for p in ax.check({"each": GROUPS}, _run(cards=[CARDS[0], CARDS[2]])))
    twice = [*CARDS, _card("c4", "Dev Malhotra asked again")]
    assert any("2 card(s) about Dev/Ferncrest" in p for p in ax.check({"each": GROUPS}, _run(cards=twice)))


def test_a_card_the_app_never_showed_is_not_counted():
    hidden = [CARDS[0], _card("c2", "Offer Dev Malhotra a demo", shown=()), CARDS[2]]
    assert any("Dev/Ferncrest" in p for p in ax.check({"each": GROUPS}, _run(cards=hidden)))


def test_every_card_is_open_after_the_last_sweep():
    assert ax.check({"each": GROUPS, "open_at_end": True}, _run(cards=CARDS)) == []
    closed = [CARDS[0], _card("c2", "Offer Dev Malhotra a demo", sweeps=(0,)), CARDS[2]]
    problems = ax.check({"each": GROUPS, "open_at_end": True}, _run(cards=closed))
    assert any("c2" in p and "not open after the last sweep" in p for p in problems), problems


def test_the_card_that_moved_on_has_versions():
    moved = [_card("c1", "Confirm Wednesday with Tara Sethi", versions=("Write to Tara Sethi", "Confirm Wednesday")),
             *CARDS[1:]]
    assert ax.check({"versioned": ["Tara"]}, _run(cards=moved)) == []
    once = [_card("c1", "Send Tara Sethi your deck", versions=("Send Tara Sethi your deck",)), *CARDS[1:]]
    problems = ax.check({"versioned": ["Tara"]}, _run(cards=once))
    assert any("c1" in p and "1 version" in p for p in problems), problems
    assert any("no card" in p for p in ax.check({"versioned": ["Zara"]}, _run(cards=CARDS)))
