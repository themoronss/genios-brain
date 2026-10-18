"""STEP-13 · the invention rule is one rule, and every layer may ask it.

    .venv/bin/python -m pytest -q tests/platform/test_the_invention_rule_is_one.py

Tree `yc2_w27_s13` M35.C2.L-logic.V0.U08 (`platform/grounding.py`). The card validator's V-02 lived in
`deliver/render`, above reasoning, so the expert's check could not ask it without importing upward. It moved,
byte for byte, to the cross-cutting layer: `deliver/render` re-exports the SAME objects under the names its
callers have always imported, so there is one rule, in one place. `corpus_of` reads plain texts the way
`deliver/render._corpus` reads a card's facts — lowercased, each ISO date expanded into its human forms.
"""
from __future__ import annotations

import pytest

from genios_engine.deliver import render
from genios_engine.platform import grounding as G

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("name, public", [
    ("invention_ok", "invention_ok"), ("_digit_runs", "digit_runs"), ("_proper_nouns", "proper_nouns"),
    ("_expand_dates", "expand_dates"), ("_fold", "fold"), ("_haystack", "haystack"),
    ("_GRAMMAR_WORDS", "GRAMMAR_WORDS")])
def test_the_card_validator_asks_the_platforms_own_rule(name, public):
    assert getattr(render, name) is getattr(G, public) is getattr(G, name)


def test_the_rule_did_not_move_up_or_sideways():
    """The rule's own module imports nothing of the engine: it is the bottom of every layer that asks it."""
    import ast
    tree = ast.parse(open(G.__file__, encoding="utf-8").read())
    engine = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and (n.module or "").startswith(
        "genios_engine")]
    assert engine == []


def test_a_corpus_of_plain_lines_grounds_a_date_as_a_sentence_writes_it():
    text, nums = G.corpus_of(["- [evt_x] 2026-08-04 10:00 UTC · they wrote · Introly",
                              "  “Arjun, meet Marco Ruiz — 1200 users.”", None])
    assert text == text.lower() and "august" in text and "aug" in text and "tuesday" in text
    assert {"2026", "08", "04", "10", "00", "1200"} <= nums, "every line's digits, not the first's"
    assert "none" not in text, "a missing line is no words at all"
    assert G.invention_ok("Introly introduced Marco on 4 Aug", text, nums) == (True, None)
    assert G.invention_ok("Introly introduced Marco on 4 March", text, nums) == (False, "name:March")
    assert G.invention_ok("Neel introduced Marco", text, nums) == (False, "name:Neel")


def test_quiet_and_by_open_a_sentence_without_reading_as_an_entity():
    """STEP-15 M45.C5.L-integration.V1.U02's acceptance: `executive/morning_template.words_for`
    writes "Quiet for 7 days." and "By 9 Oct." as a line's own second sentence — the template's own
    faithful words, failing the check they are the ground truth for, the first time this guard was
    ever run against them. Same mechanism as "Pending"/"Waiting" above it in `_GRAMMAR_WORDS`; each
    claim but the opening word is grounded the same way the file's own date test above grounds one."""
    # Mid-string, after a period — exactly how `words_for` writes it, and the shape that read as
    # invented: the FIRST word of a checked string is treated differently than one that opens a
    # LATER sentence, so a one-sentence probe would not have reproduced the failure this pins.
    # The corpus must NOT itself contain the word "quiet" — `quiet_days` is a computed signal,
    # never an item's own material, and a corpus that happened to say it would mask the very
    # thing this test exists to isolate (the stop-list, not a coincidental match).
    quiet_text, quiet_nums = G.corpus_of(["Bluepeak has not replied since they wrote on 7 days."])
    assert "quiet" not in quiet_text
    assert G.invention_ok("Bluepeak has not replied. Quiet for 7 days.", quiet_text, quiet_nums) \
        == (True, None)
    by_text, by_nums = G.corpus_of(["Bluepeak owes a reply.", "2026-10-09 the reply is due."])
    assert G.invention_ok("Bluepeak owes a reply. By 9 Oct.", by_text, by_nums) == (True, None)


def test_the_rule_still_refuses_what_it_always_refused():
    corpus, nums = render._corpus({"deal.amount": {"value": 1200}}, {}, quotes=[{"quote": "Thanks Priya"}])
    assert render.invention_ok("Priya agreed to 1200", corpus, nums) == (True, None)
    assert render.invention_ok("Priya agreed to 9000", corpus, nums) == (False, "number:9000")
    assert render.invention_ok("Initech will vouch for us", corpus, nums) == (False, "name:Initech")
