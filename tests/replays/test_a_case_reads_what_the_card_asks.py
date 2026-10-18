"""STEP-14 fix · a case can say what the card's headline must say — the move it advises, the question it asks.

    .venv/bin/python -m pytest -q tests/replays/test_a_case_reads_what_the_card_asks.py

Tree `yc2_w27_s14` M43.C6.L-integration.V2.U12 (the STEP-14 crosscheck, finding 10). `mentions` reads every line of a
card, so golden F63 — and replay 02's m05 — passed on "address" in the card's situation line while the card ASKED
"Can you tell us whether Ishaan will write first?". `headline_says` reads the headline alone; F63 and m05 require the
address there, and both are blocked (strict xfail) until the file asks it (STEP-13b, M37).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.replays import atlas_expression, marking
from tests.replays.founder_case import CardExpectation, CardView, load_cases

pytestmark = pytest.mark.unit

ASKS = "Can you tell us whether Ishaan will write first?"


def _run(headline: str):
    card = CardView(card_id="card_q", state="queued", level="review",
                    text=f"{headline}\nIntrolly gave no address for Ishaan", output_lane="investigation",
                    sweeps=(0,), app_sweeps=(0,), gold={"headline": headline})
    return SimpleNamespace(cards=(card,), chain_ok=(True,), misses=(), memory=(), landed=())


def test_a_card_that_asks_something_else_fails_the_case():
    exp = CardExpectation(about=("Ishaan",), min=1, max=1, mentions=("address",), headline_says=("address",))
    check = marking._card_check(0, exp, _run(ASKS))
    assert check.verdict == marking.FAIL and "headline" in check.reason, check
    assert marking._card_check(0, exp, _run("Can you tell us Ishaan Mehra's email address?")).verdict == marking.PASS


def test_mentions_alone_would_pass_it():
    """⛔ THE NEGATIVE CONTROL: the same card, read by `mentions` alone, passes — the hole this closes."""
    exp = CardExpectation(about=("Ishaan",), min=1, max=1, mentions=("address",))
    assert marking._card_check(0, exp, _run(ASKS)).verdict == marking.PASS


def test_f63_and_m05_ask_for_the_address_in_the_headline():
    f63 = next(c for c in load_cases() if c.case_id == "F63")
    assert f63.cards[0].headline_says == ("address",) and f63.blocked_on
    spec = atlas_expression.expression("02", 5)
    assert spec["headline_says"] == ["address"]
    spec = {k: v for k, v in spec.items() if k not in ("memory", "case", "why")}     # the card predicates alone
    assert atlas_expression.check(spec, _run(ASKS)) == [
        "card card_q does not say ['address'] in its headline"]
