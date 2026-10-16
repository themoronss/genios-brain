"""STEP-14 fix · a question stays ours through every version of its card (the STEP-14 crosscheck, finding 1).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_a_question_stays_ours_through_its_versions.py

Tree `yc2_w27_s14` M42.C2.L-interface.V3.U06 (fix of M42.C2.L-interface.V3.U04 × STEP-13 M36.C2.L-logic.V2.U12) —
`context/file_judgments.PriorVersion.mode`, `reason/expert/dossier.people_of`, `reason/expert/verify._ours_blanked`.

STEP-13's B2: a question card's headline is OUR question — for a held review the very claim its check dropped — and
grounds nothing. STEP-14 made the card live, and two things reopened it:

  * the dossier prints each VERSION's headline under the card (`  version 1: “Is it so: “…”? …”`), and only the
    card's own line was blanked (`count=1`, one regex) — so while the card still asks, a fact citing it is grounded
    on its version line and kept (only the confirmation hold stopped the move);
  * once you answer and the next review DECIDES, the same card carries the decision's signal — its rule is
    `file_review`, so it was no longer named a question card at all, and "Send Arjun the deck and the 2M SAFE terms
    from Sequoia" was SHOWN, grounded on the question version's line (the crosscheck's
    `probes/test_xc14_b2_versions_pg.py`).

Now a card is ours to blank when ANY of its versions asked you (its words' mode, `question` or `answered`) — and every
line of its item that ASKED is blanked: each version that asked, and the card's own line while it asks. A decision
version's words still ground what they say (golden F07, F29 cite a decision card for what it asked the founder — and
F07's card asks after its call; amended after the golden lane, which caught the first rule blanking F07's decision).
"""
from __future__ import annotations

import dataclasses
import os
import re
from datetime import timedelta

import pytest

from genios_engine.context.file_judgments import FileJudgments, PriorCard, PriorVersion
from genios_engine.contracts import claim_check as C
from genios_engine.contracts.card_version import ANSWERED_MODE, QUESTION_MODE
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import test_your_answer_feeds_the_file as T
from tests.reason.expert.test_a_covered_file_decides_once import world  # noqa: F401 — the pg fixture
from tests.reason.expert.test_a_move_on_your_answer_is_confirmed import ITS_QUESTION, YOUR_NO, _check, _review
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401 — its fixture

ANSWER_IN = "Your answer is in; the file is read again"
DECISION = "Send Neel the product roadmap"
#: The move the denied claim would make.
DENIED_MOVE = "Send Neel the deck and the 2M SAFE terms from Sequoia"


def _card(rule: str, headline: str, versions=()) -> PriorCard:
    return PriorCard(card_id="card_q1", subject_node_id=T.NEEL_FILE, headline=headline, level="observation",
                     state="queued", created_at=T.NOW - timedelta(days=3), resolved_at=None, events=(), verdicts=(),
                     versions=tuple(versions), rule_id=rule)


def _v(n: int, headline: str, change: str, mode: str | None) -> PriorVersion:
    return PriorVersion(version=n, headline=headline, change=change, material=True,
                        changed=() if change == "created" else ("ask",), at=T.NOW - timedelta(days=4 - n),
                        mode=mode)


#: A file's card through STEP-14's life: each holds the claim the check dropped on a version that ASKED.
ASKING = {
    "a decision card that became this question": _card(D.QUESTION_CARD_RULE, ITS_QUESTION, [
        _v(1, DECISION, "created", "act"), _v(2, ITS_QUESTION, "asked", QUESTION_MODE)]),
    "this question, answered (s14-D3)": _card(D.QUESTION_CARD_RULE, ANSWER_IN, [
        _v(1, ITS_QUESTION, "created", QUESTION_MODE), _v(2, ANSWER_IN, "answered", ANSWERED_MODE)]),
    "this question, answered, now a decision": _card("file_review", DECISION, [
        _v(1, ITS_QUESTION, "created", QUESTION_MODE), _v(2, ANSWER_IN, "answered", ANSWERED_MODE),
        _v(3, DECISION, "updated", "act")]),
}


@pytest.mark.parametrize("name", list(ASKING))
@pytest.mark.parametrize("cites", [("card:card_q1",), ("card:card_q1", T.NEEL_MAIL)])
def test_b2_a_question_on_any_version_grounds_nothing(name, cites):
    judged = FileJudgments(file_id=T.NEEL_FILE, cards=(ASKING[name],))
    dossier, people = T._neel(YOUR_NO, judgments=judged)
    assert T.DENIED in dossier.text, "the version line prints the claim — the expert is shown it"
    assert people.question_cards == ("card:card_q1",)
    checked = _check(_review(T.DENIED, DENIED_MOVE, cites=cites, draft=None), YOUR_NO, judgments=judged)
    fact1 = next(v for v in checked.verdicts if v.line == "fact:1")
    assert fact1.verdict == C.DROPPED, checked.verdicts
    assert checked.fate != C.SHOWN and checked.words.headline is None, checked.verdicts


def _item(card):
    judged = FileJudgments(file_id=T.NEEL_FILE, cards=(card,))
    dossier, people = T._neel(YOUR_NO, judgments=judged)
    from genios_engine.reason.expert.verify import _Run  # the check's reader of the dossier
    run = _Run(review=_review(T.DENIED, DENIED_MOVE, cites=("card:card_q1",), draft=None),
               lines=D.lines_by_id(dossier.text), people=people)
    return run.items(["card:card_q1"])


def test_every_line_that_asked_is_blanked_and_no_other():
    """The question's words and its answer's are ours — blanked on every version line that ASKED; the decision's own
    words still ground what they say (golden F07: a fact citing the card's decision version for Leela's name)."""
    item = _item(ASKING["this question, answered, now a decision"])
    assert T.DENIED not in item and ANSWER_IN not in item, item
    assert item.count("“…”") == 2 and item.count(DECISION) == 2, item    # its line and version 3 keep the decision


def test_a_question_card_named_without_its_lines_is_blanked_whole():
    """A `FilePeople` that names a question card but not which of its lines asked (a caller's own) blanks it whole —
    never less than STEP-13's B2 did."""
    judged = FileJudgments(file_id=T.NEEL_FILE, cards=(ASKING["this question, answered, now a decision"],))
    dossier, people = T._neel(YOUR_NO, judgments=judged)
    from genios_engine.reason.expert.verify import _Run
    run = _Run(review=_review(T.DENIED, DENIED_MOVE, cites=("card:card_q1",), draft=None),
               lines=D.lines_by_id(dossier.text), people=dataclasses.replace(people, asked_lines=()))
    item = run.items(["card:card_q1"])
    assert item.count("“…”") == 4 and DECISION not in item, item


def test_a_card_that_asks_now_has_its_own_line_blanked():
    item = _item(ASKING["a decision card that became this question"])
    assert T.DENIED not in item and DECISION in item, item              # the card's line and version 2 asked
    assert item.count("“…”") == 2, item


def test_a_card_whose_question_was_cut_from_view_still_asked_you():
    """The dossier keeps a card's newest versions (`LIMITS["versions"]`): when the question's own version is cut,
    the answer's version still says the card asked you — it stays ours."""
    card = _card("file_review", DECISION, [_v(4, ANSWER_IN, "answered", ANSWERED_MODE), _v(5, DECISION, "updated", "act")])
    _, people = T._neel(YOUR_NO, judgments=FileJudgments(file_id=T.NEEL_FILE, cards=(card,)))
    assert people.question_cards == ("card:card_q1",)


def test_a_card_that_never_asked_is_read_as_before():
    """The control: a decision card with versions, none of which asked — its lines still ground what they say."""
    card = _card("file_review", DECISION, [_v(1, "Reply to Neel", "created", "act"),
                                           _v(2, DECISION, "updated", "act")])
    judged = FileJudgments(file_id=T.NEEL_FILE, cards=(card,))
    _, people = T._neel(YOUR_NO, judgments=judged)
    assert people.question_cards == ()
    checked = _check(_review("A card asking you to send Neel the product roadmap was shown", "Send Neel the deck",
                             also=({"claim": "Neel asked for the product roadmap", "evidence": [T.NEEL_MAIL],
                                    "quote": "Could you send me the product roadmap"},),
                             cites=("card:card_q1",)), judgments=judged)
    assert next(v for v in checked.verdicts if v.line == "fact:1").verdict == C.KEPT, checked.verdicts


def test_a_version_carries_the_mode_it_was_shown_in():
    from genios_engine.context.file_judgments import _versions
    from genios_engine.contracts.card_version import VersionWords, version_of
    asked = VersionWords(headline=ITS_QUESTION, situation="It asks", mode=QUESTION_MODE, ask="q1")
    answered = VersionWords(headline=ANSWER_IN, situation="Your answer", mode=ANSWERED_MODE, ask="q1")
    decided = VersionWords(headline=DECISION, situation="It decides", mode="act", ask="a1")
    raw = [{"detail": version_of(asked, answered, version=2, signal_id="s2", answered=True).as_mapping(),
            "at": T.NOW.isoformat()},
           {"detail": version_of(answered, decided, version=3, signal_id="s3").as_mapping(), "at": T.NOW.isoformat()}]
    versions, unread = _versions(T.NOW - timedelta(days=1), raw)
    assert unread == 0 and [(v.version, v.mode) for v in versions] == [
        (1, QUESTION_MODE), (2, ANSWERED_MODE), (3, "act")]


# ── the database path: B2's own scenario, through your answer and then the file's next decision ─────────────────

@pytest.mark.pg
def test_b2_through_the_answer_and_the_decision_on_the_same_card(world):
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — this test needs a scratch Postgres")
    from genios_engine.deliver import actions
    from genios_engine.deliver.store import CardStore
    from genios_engine.platform.self_identity import SelfIdentity
    from tests.deliver.test_a_question_card import _build, _cards
    from tests.reason.expert import test_a_covered_file_decides_once as K
    from tests.reason.expert.test_a_held_file_asks import _held, _write

    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _sit, events = K._fund(store, org)
    review = ExpertReview.from_mapping(K._review(sorted(events)[0]))
    claim = "Arjun asked for the deck and the 2M SAFE terms from Sequoia"
    held = dataclasses.replace(_held(review), question=f"Is it so: “{claim}”? It is not in what it cites.")
    _write(store, org, anchor, "ffp-b2-1", events, checked=held)
    K._compile(store, org, registry, covered={anchor: "ffp-b2-1"})
    _build(store, cards, org)
    [card] = _cards(store, org)
    assert actions.ingest_action(card_store=cards, graph=store, org_id=org, card_id=card.card_id,
                                 actor="founder@meridian.test", action="answer",
                                 eval_time=K.NOW + timedelta(minutes=5), allow_any_assignee=True,
                                 words=T.YOUR_NO)["ok"]
    # The file's next review decides: the SAME card's next version (s14-D3).
    K._write(store, org, anchor, "ffp-b2-act-2", events)
    later = K.NOW + timedelta(hours=1)
    K._compile(store, org, registry, covered={anchor: "ffp-b2-act-2"}, at=later)
    _build(store, cards, org, at=later)
    [one] = _cards(store, org)
    assert one.card_id == card.card_id, "one file, one card — the decision is its next version"
    with store.engine.connect() as c:
        parts = D.read_parts(c, org, anchor, now=later + timedelta(hours=2))
    dossier = D.build_dossier(parts)
    people = D.people_of(parts, us=SelfIdentity.of(addresses=("founder@meridian.test",), domains=("meridian.test",)))
    card_ref = f"card:{card.card_id}"
    assert claim in dossier.text, "the question version's line prints the claim — the expert is shown it"
    assert people.question_cards == (card_ref,)
    answer_ref = re.search(r"\[(answer:[^\]]+)\]", dossier.text).group(1)
    raw = K._review(sorted(events)[0])
    for cites in ([card_ref], [card_ref, answer_ref]):
        mapping = dict(raw, facts=[{"claim": claim, "evidence": cites}])
        mapping["next_move"] = dict(raw["next_move"], rests_on=["fact:1"],
                                    what="Send Arjun the deck and the 2M SAFE terms from Sequoia")
        checked = check_review(ExpertReview.from_mapping(mapping), dossier.text, people)
        fact1 = next(v for v in checked.verdicts if v.line == "fact:1")
        assert fact1.verdict == C.DROPPED, (cites, checked.verdicts)
        assert checked.fate != C.SHOWN and checked.words.headline is None, (cites, checked.verdicts)
