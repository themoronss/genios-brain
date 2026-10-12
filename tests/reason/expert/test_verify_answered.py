"""STEP-13 · an answered ask drops its move, not the file (crosscheck X14, X21).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_answered.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U15 (`reason/expert/verify`, `reason/expert/dossier.people_of`). "Already
answered" was read only for a MEETING ask the move NAMED (`answers`), and any meeting on the file dated after
the ask answered it — one booked before the ask, one with somebody else; and the suppression then silenced the
WHOLE file, the deck still owed with it (X14). Our own reply in the ask's thread answered nothing (X21).

Now the ask a move answers is the one it names — or, naming none, the one open ask waiting on us that the
facts it rests on cite. An ask is answered by our reply in its thread after it, or — a meeting ask — by a
meeting with the asker (set up by them, or by us on their own file) booked after the ask. A move whose ask is
answered is moot: suppressed when nothing else waits on us; when another ask still does, the file keeps its
card — held, asking what the next move on that ask is.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

BOOK = {"what": "Book the call Marco asked for", "answers": W.ASK_MEET, "rests_on": ["fact:1"]}
AFTER = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)          # the call, booked ahead
BEFORE_THE_ASK = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)  # Marco asked on 11 Aug, 09:20
REPLIED = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict | None:
    return next((v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED), None)


def test_x14_a_meeting_booked_before_the_ask_answers_nothing():
    """Dated after the ask, booked before it: it cannot be the answer to it."""
    checked = _check({"asks_a_call": True, "asks_the_deck": False, "meeting_at": AFTER,
                      "meeting_booked_at": BEFORE_THE_ASK}, move=BOOK)
    assert _verdict(checked, "answers").verdict == C.KEPT and checked.fate == C.SHOWN


def test_x14_a_meeting_with_somebody_else_answers_nothing():
    checked = _check({"asks_a_call": True, "asks_the_deck": False, "meeting_at": AFTER,
                      "meeting_by": "priya@altavia.test"}, move=BOOK)
    assert _verdict(checked, "answers").verdict == C.KEPT and checked.fate == C.SHOWN


def test_a_meeting_we_set_up_on_the_askers_own_file_answers_their_ask():
    checked = _check({"asks_a_call": True, "asks_the_deck": False, "meeting_at": AFTER,
                      "meeting_by": "arjun@nimbuslabs.test"}, move=BOOK)
    assert checked.fate == C.SUPPRESSED and checked.because == f"answered:{W.MEETING}"


def test_x14_the_deck_still_owed_keeps_the_file_s_card():
    """X14's run: the call is answered by the meeting, the deck is not — the file is not silenced: the
    move drops, and the file asks what the next move on the deck is."""
    checked = _check({"asks_a_call": True, "meeting_at": AFTER}, move=BOOK)
    assert _verdict(checked, "answers") == C.LineVerdict("answers", C.DROPPED, C.ANSWERED,
                                                         f"{W.ASK_MEET} by {W.MEETING}")
    assert checked.fate == C.HELD and checked.because == f"answered:{W.MEETING}"
    assert checked.words.headline is None and checked.words.draft is None
    assert "question" in checked.question and "11 Aug" in checked.question


def test_x21_our_reply_in_the_thread_answers_the_ask():
    """X21's run: we sent the deck on 12 Aug, in the thread Marco asked in; "Send Marco the short deck"
    is moot."""
    checked = _check({"replied_at": REPLIED})
    assert _verdict(checked, "answers") == C.LineVerdict("answers", C.DROPPED, C.ANSWERED,
                                                         f"{W.ASK_DECK} by evt_reply")
    assert checked.fate == C.SUPPRESSED and checked.words.headline is None


def test_x21_a_move_that_names_no_ask_is_held_to_the_ask_its_ground_cites():
    """The move names no `answers`, but rests on fact 2, which cites the deck's ask: that is its ask."""
    checked = _check({"replied_at": REPLIED}, move={"answers": None})
    assert _verdict(checked, "answers") == C.LineVerdict("answers", C.DROPPED, C.ANSWERED,
                                                         f"{W.ASK_DECK} by evt_reply")
    assert checked.fate == C.SUPPRESSED


def test_a_fact_saying_the_ask_was_answered_is_no_ground_to_answer_it_again():
    """Golden F45's shape: the ask still shows open, and a fact the move rests on cites it WITH our reply
    that answered it — the fact says the loop is stale; the move (the file's next step) is not moot."""
    checked = _check({"replied_at": REPLIED}, move={"answers": None},
                     fact2={"claim": "His ask for the deck still shows open, though we sent the deck",
                            "evidence": [W.ASK_DECK, "evt_reply"], "quote": "Here is the short deck"})
    assert _verdict(checked, "answers") is None and checked.fate == C.SHOWN


def test_a_move_whose_ground_cites_no_ask_is_not_read_as_answering_one():
    checked = _check({"replied_at": REPLIED}, move={"answers": None, "rests_on": ["fact:1"]})
    assert _verdict(checked, "answers") is None and checked.fate == C.SHOWN


def test_our_reply_before_the_ask_or_in_another_thread_answers_nothing():
    early = _check({"replied_at": datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)})
    assert early.fate == C.SHOWN and _verdict(early, "answers").verdict == C.KEPT
    elsewhere = _check({"replied_at": REPLIED, "replied_in": "t_other"})
    assert elsewhere.fate == C.SHOWN and _verdict(elsewhere, "answers").verdict == C.KEPT


def test_a_meeting_never_answers_a_question():
    """Replay 04: close the exact request — the deck is still owed after a call is booked."""
    checked = _check({"asks_a_call": True, "meeting_at": AFTER})
    assert checked.fate == C.SHOWN and _verdict(checked, "answers").verdict == C.KEPT


def test_the_files_people_carry_its_asks_our_mails_and_its_meetings():
    """What the check reads, from the file's parts (`dossier.people_of`): who asked — the counterparty
    for an ask of the file itself, a person by their node, nobody it cannot name — our mails with their
    threads, and each meeting with when it was booked and who set it up."""
    import dataclasses

    from genios_engine.context.workstreams import Ask
    from genios_engine.reason.expert import dossier as D
    parts = W.parts(replied_at=REPLIED, meeting_at=AFTER)
    file = dataclasses.replace(parts.file, open_asks=(
        *parts.file.open_asks,
        Ask(loop_id="ask_by_node", kind="question", asked_by=W.FILE, owed_by="us", thread_id="t_x",
            opened_at=REPLIED),
        Ask(loop_id="ask_by_nobody", kind="question", asked_by="node_unknown", owed_by="us",
            thread_id=None, opened_at=None)))
    numbers = dataclasses.replace(parts.numbers, people=(dataclasses.replace(parts.numbers.people[0],
                                                                             node_id="node_person_marco"),))
    file = dataclasses.replace(file, open_asks=(*file.open_asks, Ask(
        loop_id="ask_by_person", kind="question", asked_by="node_person_marco", owed_by="us", thread_id=None,
        opened_at=None)))
    people = D.people_of(dataclasses.replace(parts, file=file, numbers=numbers), us=W.US, our_names=W.OUR_NAMES)
    askers = {a.ref: a.asker for a in people.asks}
    assert askers["loop:ask_deck"] == people.counterparty and askers["loop:ask_by_node"] == people.counterparty
    assert askers["loop:ask_by_person"] == D.Person("Marco Ruiz", W.MARCO)
    assert askers["loop:ask_by_nobody"] is None
    assert [(a.ref, a.ours) for a in people.asks][:2] == [("loop:ask_deck", True), ("loop:ask_call", False)]
    assert [(r.event_id, r.thread) for r in people.replies] == [(W.OURS, "t_intro"), ("evt_reply", "t_intro")]
    [meeting] = people.meetings
    assert (meeting.event_id, meeting.booked_at, meeting.by) == (
        W.MEETING, datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc), D.Person("Marco Ruiz", W.MARCO))


def _people_with(people, **change):
    import dataclasses
    return dataclasses.replace(people, **change)


def _booked_world():
    return W.world(asks_a_call=True, asks_the_deck=False, meeting_at=AFTER)


def test_the_organiser_is_the_asker_by_address_or_by_name():
    import dataclasses

    from genios_engine.reason.expert import dossier as D
    dossier, people = _booked_world()
    for by in (D.Person(None, W.MARCO), D.Person("Marco Ruiz", "marco.ruiz@elsewhere.test")):
        changed = _people_with(people, meetings=(dataclasses.replace(people.meetings[0], by=by),))
        assert check_review(W.review(move=BOOK), dossier.text, changed).fate == C.SUPPRESSED, by
    other = _people_with(people, meetings=(dataclasses.replace(people.meetings[0],
                                                               by=D.Person("Priya", "priya@x.test")),))
    assert check_review(W.review(move=BOOK), dossier.text, other).fate == C.SHOWN


def test_a_meeting_we_set_up_answers_only_the_counterparty_s_ask():
    """On Marco's file, a call we set up is with Marco — not with an ask somebody else made there."""
    import dataclasses

    from genios_engine.reason.expert import dossier as D
    dossier, people = W.world(asks_a_call=True, asks_the_deck=False, meeting_at=AFTER,
                              meeting_by="arjun@nimbuslabs.test")
    asks = tuple(dataclasses.replace(a, asker=D.Person("Priya", "priya@altavia.test"))
                 if a.ref == W.ASK_MEET else a for a in people.asks)
    assert check_review(W.review(move=BOOK), dossier.text, _people_with(people, asks=asks)).fate == C.SHOWN


def test_an_other_ask_already_answered_keeps_no_card():
    """The deck's ask is answered too (we sent it on 12 Aug): nothing is left owed, the file goes quiet."""
    checked = _check({"asks_a_call": True, "meeting_at": AFTER, "replied_at": REPLIED}, move=BOOK)
    assert checked.fate == C.SUPPRESSED


def test_a_ground_citing_two_asks_names_neither():
    checked = _check({"asks_a_call": True, "replied_at": REPLIED}, move={"answers": None},
                     fact2={"evidence": [W.ASK_DECK, W.ASK_MEET]})
    assert _verdict(checked, "answers") is None and checked.fate == C.SHOWN


def test_an_ask_that_waits_on_them_is_no_ask_a_move_answers():
    checked = _check({"replied_at": REPLIED}, move={"answers": None}, fact2={"evidence": [W.ASK_CALL]})
    assert _verdict(checked, "answers") is None and checked.fate == C.SHOWN
