"""STEP-12 · every file a case's sweeps review has the expert's answer, authored for it by Claude (`06` D49).

    pytest tests/replays/test_every_changed_file_has_an_expert_answer.py -q [-k board_cases]

Tree `yc2_w27_s12` M32.C5.L-data.V1.U02 (`board_cases`: every must-detect case the board fails today and every
must-abstain case) and V1.U03 (every other case). Which files a case's sweeps review is MEASURED, not guessed:
`tests/replays/expert_files.json`, written by a run of every case with the expert switched on — its other model
sites answered from their cassettes, the expert's own prompts by the ideal reader from these very answers, as the
recording will answer them — for each file, the ids its first dossier offered to cite, the stages its playbook
lists, and how many prompts the run asked. Each case's `model.expert` answers exactly those files, or declares why it does not, and each
answer is one the review contract parses, marked `claude`, naming its file as its dossier does (`<key>`), citing
only what that first dossier offered, naming only a listed stage, and writing a number only where that
dossier holds it — the mail's own date, time or number, never one of its own — so it is never refused for a
number its dossier does not hold. (Until STEP-12's decided re-record it wrote no digit at all; a card that
must name *"30 Sep"* or *"Assignment 4"* then could not, M33.C2.L-data.V0.U04.) What the ideal reader then serves, and what the
review run makes of it, the golden lane and M32.C5.L-integration.V3.U05 measure on the real chain.

STEP-13 (`yc2_w27_s13` M35.C4.L-data.V0.U01): each answer also carries what the check reads — a moving
move names the facts it rests on (`rests_on`), a draft whom it goes to (`to`), a quote is the mail's own
words (two or more, no id in it) — and every text that reaches a card speaks to the founder as "you":
never "the founder", never their name or the company's (`03` F178). That each quote IS in its mail, and
that every authored review stands the check whole, the golden lane measures (M35.C4.L-integration.V1.U03).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from genios_engine.contracts.expert_review import ExpertReview, number_tokens
from tests.replays.founder_case import load_cases

pytestmark = pytest.mark.unit

FILES = json.loads((Path(__file__).parent / "expert_files.json").read_text())
CASES = {case.case_id: case for case in load_cases()}

#: The board's state on 10 Oct (`03` §F.1): the must-detect cases it fails — at the gate, in reasoning,
#: with no stage to read — and the must-abstain one it fails. With every must-abstain case, V1.U02's set.
FAILING_MUST_DETECT = ("F01", "F02", "F07", "F09", "F11", "F15", "F16", "F17", "F19", "F24", "F27", "F29",
                       "F47", "F48", "F49", "F50", "F51", "F52", "F54", "F56", "F57")
BOARD_CASES = tuple(sorted(set(FAILING_MUST_DETECT) | {c for c, case in CASES.items()
                                                       if case.kind == "must_abstain"}))
OTHER_CASES = tuple(sorted(set(CASES) - set(BOARD_CASES)))
_KEY = re.compile(r"^<([^<>\s]+)>$")


def _entries(case_id: str) -> list[dict]:
    return list((CASES[case_id].model or {}).get("expert") or ())


def _check(case_id: str) -> None:
    files = FILES[case_id]
    entries = _entries(case_id)
    declared = dict((CASES[case_id].model or {}).get("expert_declared") or {})
    answered, general = set(), []
    for entry in entries:
        assert entry.get("by") == "claude", f"{case_id}: an expert answer is marked claude (D49)"
        keys = [m.group(1) for t in entry.get("when") or () if (m := _KEY.match(str(t)))]
        assert len(keys) == 1, f"{case_id}: an expert answer names its file once, as <key>: {entry['when']}"
        key = keys[0]
        assert key in files, f"{case_id}: <{key}> is no file its sweeps review: {sorted(files)}"
        answered.add(key)
        review = ExpertReview.from_mapping(entry["answer"])            # the contract parses it
        if len(entry["when"]) == 1:
            # The general entry answers the file's FIRST review: it cites only what that dossier
            # offered. A narrower one answers a later dossier only, and is held to it on the chain.
            general.append(key)
            offered = set(files[key]["evidence"])
            cited = {e for f in review.facts for e in f.evidence}
            cited |= {e for i in (*review.inferences, *review.patterns) for e in i.based_on
                      if not e.startswith("fact:")}
            if review.proposed_kind is not None:
                cited |= set(review.proposed_kind.evidence)
            assert cited <= offered, f"{case_id} <{key}>: cites what its first dossier never " \
                                     f"offered: {sorted(cited - offered)}"
        stage = review.expected_vs_actual.stage
        assert stage is None or stage in files[key]["stages"], f"{case_id} <{key}>: stage {stage!r}"
        _what_the_check_reads(case_id, key, review)
        digits = set().union(*(number_tokens(t) for t in review.texts()))
        if len(entry["when"]) == 1:
            held = set(files[key]["numbers"])
            assert digits <= held, (f"{case_id} <{key}>: writes numbers its first dossier does not hold: "
                                    f"{sorted(digits - held)}")
    assert sorted(general) == sorted(set(general)) and set(general) == answered, \
        f"{case_id}: every answered file has exactly one general entry: {sorted(general)}"
    missing = set(files) - answered - set(declared)
    assert not missing, f"{case_id}: files its sweeps review with no expert answer: {sorted(missing)}"
    for key, why in declared.items():
        assert key in files and len(str(why).split()) >= 5, f"{case_id}: <{key}> is declared with a reason"


#: Words a card never says of the founder (`03` F178): the phrase, and — per case — their names.
_THE_FOUNDER = re.compile(r"\bthe founder\b", re.I)


def _what_the_check_reads(case_id: str, key: str, review) -> None:
    from genios_engine.contracts.expert_review import MOVING
    where = f"{case_id} <{key}>"
    move = review.next_move
    if move is not None and review.mode in MOVING:
        assert move.rests_on, f"{where}: a moving move names the facts it rests on (rests_on)"
    if review.draft:
        assert move is not None and move.to, f"{where}: a draft says whom it goes to (to)"
    for n, fact in enumerate(review.facts, start=1):
        if fact.quote:
            assert len(fact.quote.split()) >= 2 and "[" not in fact.quote, \
                f"{where} fact {n}: a quote is the mail's own words, two or more"
    founder = CASES[case_id].founder
    names = [n for n in (founder.name, (founder.name or "").split()[0], founder.company) if n]
    card = [move.what if move is not None else review.frames.primary, review.frames.primary,
            review.done_when,
            # STEP-14 (`yc2_w27_s14` M43.C2.L-data.V2.U05): the gold card shows the alternative and when to wait or
            # stop (0221) — card words now, held by the check (check.v3), so they speak to you too.
            review.alternative, review.wait_or_stop]
    for text in (t for t in card if t):
        assert not _THE_FOUNDER.search(text), f"{where}: a card calls you the founder — {text!r}"
        for name in names:
            assert not re.search(rf"\b{re.escape(name)}\b", text), \
                f"{where}: a card names {name!r} as a party — {text!r}"


def test_every_case_is_measured():
    assert set(FILES) == set(CASES)


@pytest.mark.parametrize("case_id", BOARD_CASES)
def test_board_cases(case_id):
    _check(case_id)


@pytest.mark.parametrize("case_id", OTHER_CASES)
def test_other_cases(case_id):
    _check(case_id)


def test_a_number_its_first_dossier_does_not_hold_is_refused(monkeypatch):
    """⛔ The rule's teeth (M33.C2.L-data.V0.U04): F26's authored move names the mail's own *"30 Sep at 11
    am"* — held, so it passes; the same move naming a 31st it was never shown is refused."""
    import copy
    import sys
    module = sys.modules[__name__]
    case = copy.deepcopy(CASES["F26"])
    entry = next(e for e in case.model["expert"] if len(e["when"]) == 1)
    _check("F26")
    entry["answer"]["next_move"]["what"] = entry["answer"]["next_move"]["what"].replace("30 Sep", "31 Sep")
    monkeypatch.setitem(module.CASES, "F26", case)
    with pytest.raises(AssertionError, match="does not hold"):
        _check("F26")


@pytest.mark.parametrize("spoil, says", [
    (lambda a: a["next_move"].pop("rests_on"), "rests_on"),
    (lambda a: a["next_move"].pop("to"), "whom it goes to"),
    (lambda a: a["facts"][0].update(quote="deck"), "two or more"),
    (lambda a: a["facts"][0].update(quote="send [evt_1] the deck"), "two or more"),
    (lambda a: a.update(done_when="The founder has sent the deck."), "calls you the founder"),
    (lambda a: a["frames"].update(primary="Arjun owes Kunal the deck."), "names 'Arjun'"),
    (lambda a: a["next_move"].update(what="Send the Nimbus Labs deck to Kunal"), "names 'Nimbus Labs'"),
    # STEP-14 (M43.C2.L-data.V2.U05): the alternative and the stop rule are card words too.
    (lambda a: a.update(alternative="If the founder prefers, send it after the call."), "calls you the founder"),
    (lambda a: a.update(wait_or_stop="Wait until Arjun hears back, then stop."), "names 'Arjun'"),
])
def test_what_the_check_reads_is_held_on_every_answer(monkeypatch, spoil, says):
    """⛔ Its teeth (M35.C4.L-data.V0.U01): F05's general answer passes; each spoilt copy of it fails, for
    the reason it was spoilt."""
    import copy
    import sys
    module = sys.modules[__name__]
    _check("F05")
    case = copy.deepcopy(CASES["F05"])
    entry = next(e for e in case.model["expert"] if e["answer"].get("draft") and e["answer"].get("next_move"))
    spoil(entry["answer"])
    monkeypatch.setitem(module.CASES, "F05", case)
    with pytest.raises(AssertionError, match=re.escape(says)):
        _check("F05")
