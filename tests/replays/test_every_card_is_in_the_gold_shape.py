"""STEP-14 · M43's acceptance — every expert card on the golden set in the gold shape, and nothing false on it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_every_card_is_in_the_gold_shape.py -q

Tree `yc2_w27_s14` M43.C6.L-integration.V4.U10 (STEP-14 §3.3–§3.5; `03` F64, F164, F179; s14-F6–F11). Every founder
case replayed from its cassette (`cassettes.replayed`); on every expert card — a decision's or a held file's
question card:

  * its subject (the file's person when it has one) and never a bare domain; why now; what remains where the file
    holds an open ask;
  * a shown move WHOLE under *recommended* (who, what, for whom, by when, to), the headline the move cut at a clause —
    its start, at most 60 characters, never ending on a bare function word (s14-D8);
  * its alternative and its stop rule (check.v3) on a decision's card;
  * its window, said among its receipts with where it came from — the move's own date wherever the move has one, and
    a default said to be one (`03` F179);
  * only measured confidence axes — no R (s14-F9).

THE CONTRACT, PLANTED (`contracts/card_contract`, both writers): on F04 — Sofia's demo, one shown expert card — the
served card is made to say what no card may: a field's name in its situation (internal), our own company as its
subject (us). Each is refused at the pipeline's writer and no card shows it; with the contract switched off, each
planted card reaches the app's queue (the negative control). An expert card's words were held to its dossier by its
check, so money, a quote and a number cannot reach its writer; and no golden case raises a P4 team or verify card —
those rules, and the team writer, are held by `tests/deliver/test_no_card_breaks_the_contract.py` and
`tests/reason/test_the_team_writer_keeps_the_contract.py`.
"""
from __future__ import annotations

import os
import re

import pytest

from genios_engine.deliver.card_builder import FUNCTION_WORDS
from genios_engine.deliver.render import HEADLINE_CAP
from genios_engine.reason.expert.card_lines import DEFAULT, MOVE_DATE, WINDOW_FROM, WINDOW_SAID
from genios_engine.reason.expert.decide import CAPABILITY_ID
from genios_engine.deliver.store import QUESTION_CARD_BUILDER
from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.marking import cards_about

CASES = load_cases()
BY_ID = {c.case_id: c for c in CASES}
_BARE_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _expert_cards(run):
    return [c for c in run.cards if c.gold.get("capability_key") == CAPABILITY_ID
            or c.gold.get("builder_version") == QUESTION_CARD_BUILDER]


def _param(case):
    return pytest.param(case, id=case.case_id, marks=[pytest.mark.pg, pytest.mark.golden])


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_every_expert_card_is_in_the_gold_shape(case):
    _scratch_db()
    run = cassettes.replayed(case)
    for card in _expert_cards(run):
        g, where = card.gold, f"{case.case_id} {card.card_id}"
        assert g["subject"] and not _BARE_DOMAIN.match(g["subject"]), f"{where}: a bare domain as its subject"
        assert g["why_now"], f"{where}: no why now"
        if g["builder_version"] == QUESTION_CARD_BUILDER:
            continue                       # a question asks — it carries no move, no window (STEP-13, as built)
        window = g["window"]
        assert window and window["from"] in WINDOW_FROM and window["window"] == WINDOW_SAID[window["from"]], \
            f"{where}: its window is not said with where it came from"
        assert g["window_days"] == window["days"], f"{where}: the window it says is not the window it holds"
        assert g["alternative"] and g["wait_or_stop"], f"{where}: no alternative or no stop rule"
        recommended = g["recommended"]
        if card.level == "prescriptive":
            assert recommended and recommended.get("what") and recommended.get("who"), f"{where}: no move whole"
            head = g["headline"]
            assert len(head) <= HEADLINE_CAP and recommended["what"].startswith(head), \
                f"{where}: the headline is not the move cut: {head!r}"
            assert head.split()[-1].lower().strip(",;:—") not in FUNCTION_WORDS, f"{where}: ends on {head!r}"
            if recommended.get("by_when"):
                assert window["from"] == MOVE_DATE, f"{where}: a move with a date on a {window['from']} window"
        assert "R" not in (card.gold.get("confidence") or {}), f"{where}: R shown"


@pytest.mark.pg
@pytest.mark.golden
def test_the_gold_shape_is_measured_on_every_expert_card():
    """Not vacuous: the set carries shown moves, question cards and every kind of window but none it lacks."""
    _scratch_db()
    cards = [c for case in CASES for c in _expert_cards(cassettes.replayed(case))]
    shown = [c for c in cards if c.level == "prescriptive" and c.gold["recommended"]]
    questions = [c for c in cards if c.gold["builder_version"] == QUESTION_CARD_BUILDER]
    assert len(shown) >= 30 and len(questions) >= 3, (len(shown), len(questions))
    froms = {c.gold["window"]["from"] for c in cards if c.gold["window"]}
    assert {MOVE_DATE, DEFAULT} <= froms, froms


# ── the contract, planted ────────────────────────────────────────────────────────────────────────────────────────
PLANTS = {
    # a field's name in what the founder reads (s14-F10): the expert's reading, with `party.role` in it
    "internal": ("situation", " Check party.role with Sofia first.", "party.role"),
    # our own company as the card's subject (`platform/self_identity`)
    "us": ("subject", "Nimbus Labs", "Nimbus Labs"),
}


def _planted_run(rule: str, *, contract: bool):
    from genios_engine.deliver import pipeline
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM
    case = BY_ID["F04"]
    part, words, _shows = PLANTS[rule]
    with pytest.MonkeyPatch.context() as mp:
        if part == "situation":
            served = pipeline.review_copy
            mp.setattr(pipeline, "review_copy",
                       lambda copy, template: (lambda c: {**c, "situation": c["situation"] + words})(
                           served(copy, template)))
        else:
            build = pipeline.build_draft
            mp.setattr(pipeline, "build_draft", lambda *a, **k: {**build(*a, **k), "business_subject": words})
        if not contract:
            mp.setattr(pipeline, "_contract_refusals", lambda *_a, **_k: ())
        return run_case(case, RecordedLLM(cassettes.load(case)))


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("rule", sorted(PLANTS))
def test_a_planted_rule_is_refused_and_no_card_shows_it(rule):
    _scratch_db()
    _part, _words, shows = PLANTS[rule]
    assert cards_about(cassettes.replayed(BY_ID["F04"]), ("Sofia", "Brandt"), shown=True), "F04 shows its card"
    run = _planted_run(rule, contract=True)
    assert not run.misses, "the plant moved no prompt"
    assert not [c for c in run.cards if shows in c.text or shows == (c.subject or "")], f"{rule}: a card shows it"
    assert not cards_about(run, ("Sofia", "Brandt"), shown=True), f"{rule}: the planted card reached the app"


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("rule", sorted(PLANTS))
def test_with_the_contract_off_the_planted_card_reaches_the_app(rule):
    """⛔ THE NEGATIVE CONTROL: the same plant with `_contract_refusals` switched off — it reaches the queue."""
    _scratch_db()
    _part, _words, shows = PLANTS[rule]
    run = _planted_run(rule, contract=False)
    planted = [c for c in run.cards if c.app_sweeps and (shows in c.text or shows == (c.subject or ""))]
    assert planted, f"{rule}: with the contract off, the planted card should reach the app"
