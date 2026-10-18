"""STEP-14 fix · the board's forbidden judge reads every line the founder is shown — the gold card's lines too.

    .venv/bin/python -m pytest -q tests/replays/test_the_board_reads_every_line_shown.py
    (the golden half: GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_REQUIRED=1)

Tree `yc2_w27_s14` M43.C6.L-integration.V3.U11 (fix of M42.C4.L-integration.V1.U02 / M42.C4.L-logic.V2.U03 /
M43.C6.L-integration.V3.U09; the STEP-14 crosscheck, finding 9). `CardView.text` left out what M43 added — the move
whole (who, what, for whom, to), its alternative, when to stop, what done looks like, what doing nothing costs, the
role — and `engine_runner._said` read a version's headline, situation and draft only; the P4 writer's events kept no
`words`. A forbidden phrase planted in the gold columns passed the board; today they hold none (368 lines checked).

Now every such line is read into `CardView.shown_lines` — the card's columns and every version's move, alternative
and stop rule — and the forbidden judge (`marking._forbidden`) reads them with the card's words. They are kept out
of `text`: which cards a case is ABOUT, and what they mention, is matched where it always was. The P4 writer's
created and rebuilt events carry their `words`.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from tests.replays import marking
from tests.replays.founder_case import CardView


def _card(**over):
    base = dict(card_id="card_1", state="queued", level="prescriptive", text="Send Sofia the demo notes",
                output_lane="decision", sweeps=(0,), app_sweeps=(0,))
    return CardView(**{**base, **over})


def _case(phrase: str):
    return SimpleNamespace(forbidden_names=(), forbidden_phrases=(phrase,))


@pytest.mark.parametrize("line", [
    "Instead, ask Sofia's CFO for the wire",                      # an alternative
    "Stop when the wire transfer clears",                          # when to stop
    "who: Arjun · for whom: Sofia at Brandt · wire transfer",       # the move whole
])
def test_a_forbidden_phrase_in_a_gold_line_is_caught(line):
    run = SimpleNamespace(cards=(_card(shown_lines=(line,)),))
    hits = list(marking._forbidden(_case("wire"), run))
    assert hits == [("card_1", "wire")], hits


def test_the_same_phrase_nowhere_is_no_hit():
    """⛔ THE NEGATIVE CONTROL: nothing planted, nothing found."""
    run = SimpleNamespace(cards=(_card(shown_lines=("Instead, ask Sofia's CFO",)),))
    assert list(marking._forbidden(_case("wire"), run)) == []


def test_a_gold_line_never_makes_a_card_about_someone():
    """Which cards a case is about is matched on what it was always matched on — a move's "for whom" naming Priya
    makes no card about Priya."""
    run = SimpleNamespace(cards=(_card(shown_lines=("for whom: Priya Nair at Accel",)),))
    assert marking.cards_about(run, ("Priya",), ever=True) == []


def test_every_line_shown_is_read_from_the_card_and_its_versions():
    from tests.replays.engine_runner import _gold_lines, _said_beyond
    row = SimpleNamespace(recommended={"who": "Arjun", "what": "Send the notes", "for_whom": "Sofia", "to": "sofia@x"},
                          alternative="Instead, call", wait_or_stop="Stop when signed", success_signal="Sofia replies",
                          do_nothing_consequence="The demo goes cold", relationship_role="intro")
    assert _gold_lines(row) == ("Arjun", "Send the notes", "Sofia", "sofia@x", "Instead, call", "Stop when signed",
                                "Sofia replies", "The demo goes cold", "intro")
    assert _said_beyond({"headline": "h", "move": "Send the notes whole", "alternative": "a", "wait_or_stop": "w"}) \
        == ("Send the notes whole", "a", "w")


@pytest.mark.pg
@pytest.mark.golden
def test_on_the_golden_set_every_alternative_is_read():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
            pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from tests.replays import cassettes
    from tests.replays.founder_case import load_cases
    case = next(c for c in load_cases() if c.case_id == "F04")
    cards = [c for c in cassettes.replayed(case).cards if c.gold.get("alternative")]
    assert cards and all(c.gold["alternative"] in c.shown_lines for c in cards)
