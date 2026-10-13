"""STEP-13 · a move resting on your answer is confirmed with you (second crosscheck B2, `03` X05).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_a_move_on_your_answer_is_confirmed.py

Tree `yc2_w27_s13` M36.C2.L-logic.V2.U12 (fix) — `reason/expert/verify.check_review`, `reason/expert/dossier.people_of`,
`context/file_judgments`. X05 was claimed closed and was not:

  * PURE PATH — your answer is "No. He asked for the roadmap, not the deck." The next review claims "Neel asked for
    the deck", citing `answer:<id>`: no name or number of it is off your words, so it stood, and "Send Neel the
    deck" was SHOWN. Names and numbers are all the check reads; whether a claim says what you SAID is not read.
  * DATABASE PATH — the resolved question card's line in WHAT WAS JUDGED BEFORE prints its headline: for a held
    review the very claim its check dropped. Cited as `card:<id>`, it grounded "Arjun asked for the deck and the
    2M SAFE terms from Sequoia" again, and its move was SHOWN (`notes/ska/test_f5_card2.py`, X05's own
    counter-example).

Now a question card's headline grounds nothing — it is our question, not anyone's words — and a move whose
standing ground is only what you told us (your answer, a question card; no mail, no meeting) is CONFIRMED with
you before it is shown: held, asking "You said: “…”. Should we go ahead with “<the move>”?". Your yes to that
lets it stand (noted `confirmed_by_you`); anything else and it is not made (suppressed, `declined_by_you`). The
bound, declared: a move resting on a mail beside your answer is grounded on the mail and not asked.
"""
from __future__ import annotations

import dataclasses
import os
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from genios_engine.context.file_judgments import FileJudgments, PriorCard
from genios_engine.context.founder_questions import ANSWERED, Question, question_id_for
from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import asks
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import verify as V
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import test_your_answer_feeds_the_file as T
from tests.reason.expert.test_a_covered_file_decides_once import world  # noqa: F401 — the pg fixture
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401 — its fixture

U = timezone.utc
#: The question the file asked you (its words are not what this is about).
ASKED = "What did Neel ask for before his partner meeting?"


def _answer(question: str, words: str, *, days_ago: float) -> Question:
    return Question(question_id=question_id_for("org_x", T.NEEL_FILE, "ffp-neel-1", question), file_id=T.NEEL_FILE,
                    fingerprint="ffp-neel-1", run_id="run_1", question=question, why=asks.WHY_FIND_OUT,
                    asked_at=T.NOW - timedelta(days=days_ago + 1), state=ANSWERED, answer=words,
                    answered_by="user_arjun", answered_at=T.NOW - timedelta(days=days_ago))


YOUR_NO = _answer(ASKED, T.YOUR_NO, days_ago=2)
CITE = f"answer:{YOUR_NO.question_id}"


def _review(claim: str, what: str, *, cites=(CITE,), draft: str = "Hi Neel, attaching the deck.",
            also: tuple[dict, ...] = ()) -> ExpertReview:
    base = T._neel_review({"evidence": [CITE]}).as_mapping()
    facts = [{"claim": claim, "evidence": list(cites)}, base["facts"][1], *also]
    return ExpertReview.from_mapping({
        **base, "facts": facts, "draft": draft, "done_when": "Neel has it",
        "next_move": {**base["next_move"], "what": what, "rests_on": [f"fact:{n}" for n in range(1, len(facts) + 1)]}})


def _check(review: ExpertReview, *answers: Question, judgments: FileJudgments | None = None) -> C.CheckedReview:
    dossier, people = T._neel(*answers, judgments=judgments)
    return check_review(review, dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)


def _confirmation(move: str, words: str = T.YOUR_NO) -> str:
    return f"You said: “{words}”. Should we go ahead with “{move}”?"


# ── the pure path ──────────────────────────────────────────────────────────────────────────────────────

def test_b2_your_no_never_shows_the_move_you_denied():
    """The red: "Neel asked for the deck" on your "No" stood, and "Send Neel the deck" was shown."""
    checked = _check(_review("Neel asked for the deck", "Send Neel the deck"), YOUR_NO)
    assert checked.fate == C.HELD, (checked.fate, checked.verdicts)
    assert checked.question == _confirmation("Send Neel the deck")
    assert checked.because == C.HELD_BECAUSE[C.ON_YOUR_ANSWER]
    assert checked.words.headline is None and checked.words.draft is None and checked.words.evidence == ()
    assert C.LineVerdict("rests_on", C.DROPPED, C.ON_YOUR_ANSWER, CITE) in checked.verdicts


def test_any_move_resting_only_on_your_answer_is_confirmed_first():
    """Even one that says what you said: whether it does is not read, so it is asked."""
    checked = _check(_review("You told us he asked for the roadmap, not the deck", "Send Neel the roadmap",
                             draft="Hi Neel, attaching the roadmap."), YOUR_NO)
    assert checked.fate == C.HELD and checked.question == _confirmation("Send Neel the roadmap")


def test_your_yes_to_the_confirmation_lets_the_move_stand():
    yes = _answer(_confirmation("Send Neel the roadmap"), "Yes, please send it.", days_ago=1)
    checked = _check(_review("You told us he asked for the roadmap, not the deck", "Send Neel the roadmap",
                             draft="Hi Neel, attaching the roadmap."), yes, YOUR_NO)
    assert checked.fate == C.SHOWN, checked.verdicts
    assert checked.words.headline == "Send Neel the roadmap"
    assert C.LineVerdict("move", C.NOTED, C.CONFIRMED_BY_YOU, f"answer:{yes.question_id}") in checked.verdicts


@pytest.mark.parametrize("words", ["No — he wants the roadmap.", "Yes, but not the deck.", "Not yet.",
                                   "Wait until Monday."])
def test_anything_but_a_yes_to_the_confirmation_makes_no_move(words):
    said = _answer(_confirmation("Send Neel the deck"), words, days_ago=1)
    checked = _check(_review("Neel asked for the deck", "Send Neel the deck"), said, YOUR_NO)
    assert checked.fate == C.SUPPRESSED and checked.because == f"{C.DECLINED_BY_YOU}:answer:{said.question_id}"
    assert checked.words.headline is None and checked.question is None


def test_a_confirmation_is_matched_on_the_move_not_on_which_answer_it_quotes():
    """Your yes is itself an answer: the next review may cite it, and the confirmation it asks quotes it — the
    move you confirmed is the same move."""
    yes = _answer(_confirmation("Send Neel the deck"), "Yes.", days_ago=1)
    checked = _check(_review("Neel wants the deck", "Send Neel the deck", cites=(f"answer:{yes.question_id}",)),
                     yes, YOUR_NO)
    assert checked.fate == C.SHOWN and any(v.reason == C.CONFIRMED_BY_YOU for v in checked.verdicts)


def test_the_bound_a_move_on_his_mail_beside_your_answer_is_not_asked():
    """Declared: the mail grounds it — a claim's polarity is not read (G5)."""
    mail = {"claim": "Neel asked for the product roadmap", "evidence": [T.NEEL_MAIL],
            "quote": "Could you send me the product roadmap"}
    checked = _check(_review("You told us he asked for the roadmap", "Send Neel the product roadmap",
                             draft="Hi Neel, attaching the product roadmap.", also=(mail,)), YOUR_NO)
    assert checked.fate == C.SHOWN and checked.words.headline == "Send Neel the product roadmap"


def test_a_find_out_review_on_your_answer_asks_its_own_question():
    """A find-out move is a question to you already: it is asked as it is, never wrapped in a confirmation."""
    review = _review("You told us he asked for the roadmap", "Find out whether Neel wants the roadmap first",
                     draft=None)
    review = ExpertReview.from_mapping({**review.as_mapping(), "mode": "find_out"})
    checked = _check(review, YOUR_NO)
    assert checked.fate == C.SHOWN and checked.question == "Find out whether Neel wants the roadmap first"
    assert not any(v.reason == C.ON_YOUR_ANSWER for v in checked.verdicts)


@pytest.mark.parametrize("words,yes", [("Yes", True), ("yes, go ahead", True), ("Sure.", True), ("OK", True),
                                       ("No", False), ("Yes, but later", False), ("Yes — not the SAFE terms", False), ("Not this one", False),
                                       ("Maybe", False), ("", False)])
def test_what_confirms(words, yes):
    assert V.confirms(words) is yes


def test_the_question_card_says_why_it_asks():
    checked = _check(_review("Neel asked for the deck", "Send Neel the deck"), YOUR_NO)
    row = SimpleNamespace(review=_review("Neel asked for the deck", "Send Neel the deck"), checked=checked)
    assert asks.question_words(row) == (_confirmation("Send Neel the deck"), asks.WHY_CONFIRM)
    assert asks.WHY_CONFIRM in asks.WHYS


# ── a question card's headline is our question, never a ground ────────────────────────────────────────────

def _card(card_id: str, headline: str, *, rule_id: str | None) -> PriorCard:
    return PriorCard(card_id=card_id, subject_node_id=T.NEEL_FILE, headline=headline, level="observation",
                     state="resolved", created_at=T.NOW - timedelta(days=3), resolved_at=T.NOW - timedelta(days=2),
                     events=(), verdicts=(), rule_id=rule_id)


ITS_QUESTION = f"Is it so: “{T.DENIED}”? It is not in what it cites."


def _judged(*cards: PriorCard) -> FileJudgments:
    return FileJudgments(file_id=T.NEEL_FILE, cards=tuple(cards))


def test_b2_a_question_cards_headline_grounds_nothing():
    """X05's own counter-example, pure: the question card's line prints the claim its check dropped."""
    judged = _judged(_card("card_q1", ITS_QUESTION, rule_id=D.QUESTION_CARD_RULE))
    checked = _check(_review(T.DENIED, "Send Neel the deck and the 2M SAFE terms from Sequoia",
                             cites=("card:card_q1",), draft=None), YOUR_NO, judgments=judged)
    assert checked.fate != C.SHOWN and checked.words.headline is None, checked.verdicts
    assert next(v for v in checked.verdicts if v.line == "fact:1").reason == C.UNSUPPORTED


def test_a_claim_on_a_question_card_alone_is_confirmed_with_you():
    """A claim the blanked line still holds rests on our question only — no mail: it is asked, not shown."""
    judged = _judged(_card("card_q1", ITS_QUESTION, rule_id=D.QUESTION_CARD_RULE))
    checked = _check(_review("Neel was asked about it", "Send Neel the deck", cites=("card:card_q1",)),
                     judgments=judged)
    assert checked.fate == C.HELD and checked.question == "Should we go ahead with “Send Neel the deck”?"


def test_a_decision_cards_headline_still_grounds_what_it_says():
    """The control (golden F07, F29 cite a decision card for what it asked the founder): only a question card
    is blanked."""
    judged = _judged(_card("card_d1", "Send Neel the SAFE terms", rule_id="expert.file_review"))
    checked = _check(_review("A card asking you to send Neel the SAFE terms was shown", "Send Neel the deck",
                             also=({"claim": "Neel asked for the product roadmap", "evidence": [T.NEEL_MAIL],
                                    "quote": "Could you send me the product roadmap"},),
                             cites=("card:card_d1",)), judgments=judged)
    assert next(v for v in checked.verdicts if v.line == "fact:1").verdict == C.KEPT, checked.verdicts


def test_the_files_people_name_its_question_cards_and_its_answers():
    judged = _judged(_card("card_q1", ITS_QUESTION, rule_id=D.QUESTION_CARD_RULE),
                     _card("card_d1", "Send Neel the deck", rule_id="expert.file_review"))
    _, people = T._neel(YOUR_NO, judgments=judged)
    assert people.question_cards == ("card:card_q1",) and D.QUESTION_CARD_RULE == asks.QUESTION_RULE
    assert people.answered == (D.Answered(ref=CITE, question=ASKED, words=T.YOUR_NO),)


# ── the database path (`notes/ska/test_f5_card2.py`, the second crosscheck's red) ─────────────────────────────

@pytest.mark.pg
def test_b2_the_resolved_question_card_never_grounds_the_claim_it_asked_about(world):
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
    with store.engine.connect() as c:
        parts = D.read_parts(c, org, anchor, now=K.NOW + timedelta(hours=2))
    dossier = D.build_dossier(parts)
    people = D.people_of(parts, us=SelfIdentity.of(addresses=("founder@meridian.test",), domains=("meridian.test",)))
    card_ref = re.search(r"\[(card:[^\]]+)\]", dossier.text).group(1)
    answer_ref = re.search(r"\[(answer:[^\]]+)\]", dossier.text).group(1)
    assert claim in dossier.text, "the question card's line prints the claim — the expert is shown it"
    assert people.question_cards == (card_ref,)
    raw = K._review(sorted(events)[0])
    for cites in ([card_ref], [card_ref, answer_ref]):
        mapping = dict(raw, facts=[{"claim": claim, "evidence": cites}])
        mapping["next_move"] = dict(raw["next_move"], rests_on=["fact:1"],
                                    what="Send Arjun the deck and the 2M SAFE terms from Sequoia")
        checked = check_review(ExpertReview.from_mapping(mapping), dossier.text, people)
        assert checked.fate != C.SHOWN and checked.words.headline is None, (cites, checked.verdicts)
