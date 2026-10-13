"""STEP-13 · an ask asked again is not answered by the reply before it (second crosscheck B1).

    .venv/bin/python -m pytest -q tests/reason/expert/test_an_ask_asked_again.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U17 (`reason/expert/verify.answered_by`, `reason/expert/dossier`,
`context/workstreams.Ask`). 9d35bbd1 (U15) let any reply of ours in an ask's thread AFTER `opened_at` answer
it — and the ledger's upsert (`context/open_loops.record_ask`) REOPENS an ask asked again after our reply
without moving `opened_at`. So: Marco asks for the deck on 11 Aug, we write on 12 Aug, Marco chases on 18
Aug — the loop still says "open since 11 Aug", our 12 Aug mail "answered" it, the move was SUPPRESSED and the
file's card cleared exactly when the counterparty chased (be27bffe showed the card: the red here).

Now the ledger's `last_seen_at` rides into `Ask` and `AskSeen`, the dossier prints it when the ask was asked
again, and the check answers an ask only by a reply — or, a meeting ask, a meeting — AFTER its latest asking.
A stale loop never asked again (golden F45's shape) keeps its answer.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.verify import answered_by, check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

U = timezone.utc
REPLIED = datetime(2026, 8, 12, 10, 0, tzinfo=U)          # our mail, after Marco's ask of 11 Aug 09:20
AGAIN = datetime(2026, 8, 18, 9, 0, tzinfo=U)             # Marco asks for the deck again
CHASE = {"claim": "Marco asked again for the short deck", "evidence": [W.ASKED_AGAIN],
         "quote": "still waiting on the short deck"}


def _check(world_kw, **over) -> C.CheckedReview:
    dossier, people = W.world(**world_kw)
    return check_review(W.review(**over), dossier.text, people)


def _answers(checked: C.CheckedReview) -> C.LineVerdict | None:
    return next((v for v in checked.verdicts if v.line == "answers"), None)


@pytest.mark.parametrize("answers", [W.ASK_DECK, None], ids=["names-the-ask", "its-ground-cites-it"])
def test_b1_a_chase_after_our_reply_is_not_answered_by_that_reply(answers):
    """The crosscheck's run: our 12 Aug mail, Marco's 18 Aug chase — the deck is still owed, the card stands."""
    checked = _check({"replied_at": REPLIED, "asked_again_at": AGAIN}, fact1=CHASE,
                     move={"what": "Send Marco the short deck", "answers": answers})
    assert checked.fate == C.SHOWN, (checked.fate, checked.because, checked.verdicts)
    assert checked.words.headline == "Send Marco the short deck"
    assert not any(v.reason == C.ANSWERED for v in checked.verdicts)
    if answers:
        assert _answers(checked) == C.LineVerdict("answers", C.KEPT)


def test_b1_the_faithful_review_of_a_chased_file_is_shown():
    checked = _check({"replied_at": REPLIED, "asked_again_at": AGAIN})
    assert checked.fate == C.SHOWN and _answers(checked).verdict == C.KEPT


def test_a_stale_loop_never_asked_again_keeps_its_answer():
    """F45's shape: our reply after the ask, and no asking since — the ask is answered, the move moot."""
    checked = _check({"replied_at": REPLIED})
    assert checked.fate == C.SUPPRESSED and checked.because == f"{C.ANSWERED}:evt_reply"


def test_a_reply_after_the_latest_asking_answers_it():
    checked = _check({"replied_at": datetime(2026, 8, 19, 8, 0, tzinfo=U), "asked_again_at": AGAIN})
    assert checked.fate == C.SUPPRESSED and checked.because == f"{C.ANSWERED}:evt_reply"


def test_the_dossier_says_when_an_ask_was_asked_again():
    dossier, _ = W.world(replied_at=REPLIED, asked_again_at=AGAIN)
    [line] = [ln for ln in dossier.text.splitlines() if f"[{W.ASK_DECK}]" in ln and ln.startswith("- ")]
    assert line == ("- [loop:ask_deck] question, they wait on us, open since 2026-08-11 09:20 UTC, "
                    "last asked 2026-08-18 09:00 UTC")


def test_an_ask_never_asked_again_is_printed_as_before():
    """Its `last_seen_at` is when it was opened: the line is byte for byte the one before STEP-13's U17."""
    dossier, people = W.world()
    [line] = [ln for ln in dossier.text.splitlines() if f"[{W.ASK_DECK}]" in ln and ln.startswith("- ")]
    assert line == "- [loop:ask_deck] question, they wait on us, open since 2026-08-11 09:20 UTC"
    assert next(a for a in people.asks if a.ref == W.ASK_DECK).last_asked_at is None


def test_the_files_people_carry_when_an_ask_was_last_asked():
    _, people = W.world(asked_again_at=AGAIN)
    deck = next(a for a in people.asks if a.ref == W.ASK_DECK)
    assert deck.opened_at == datetime(2026, 8, 11, 9, 20, tzinfo=U) and deck.last_asked_at == AGAIN


def _meeting_ask_asked_again(meeting_at: datetime) -> tuple[D.Dossier, D.FilePeople]:
    """Marco asks for a call on 11 Aug, a meeting with him is booked on 12 Aug, he asks for a call again on 18 Aug."""
    p = W.parts(asks_a_call=True, asks_the_deck=False, meeting_at=meeting_at,
                meeting_booked_at=datetime(2026, 8, 12, 10, 0, tzinfo=U))
    asks = tuple(dataclasses.replace(a, last_seen_at=AGAIN) if a.loop_id == "ask_meet" else a
                 for a in p.file.open_asks)
    p = dataclasses.replace(p, file=dataclasses.replace(p.file, open_asks=asks))
    return D.build_dossier(p), D.people_of(p, us=W.US, our_names=W.OUR_NAMES)


def test_a_meeting_held_before_the_ask_was_asked_again_answers_nothing():
    dossier, people = _meeting_ask_asked_again(datetime(2026, 8, 14, 15, 0, tzinfo=U))
    assert answered_by(dossier.text, W.ASK_MEET, people) is None


def test_a_meeting_ahead_of_the_latest_asking_still_answers_it():
    dossier, people = _meeting_ask_asked_again(datetime(2026, 8, 25, 15, 0, tzinfo=U))
    assert answered_by(dossier.text, W.ASK_MEET, people) == W.MEETING
