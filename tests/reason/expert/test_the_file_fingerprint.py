"""STEP-12 · a file's fingerprint — the same file a quarter of an hour later is the same file; a new mail is not.

    pytest tests/reason/expert/test_the_file_fingerprint.py -q

`reason/expert/fingerprint.py` (tree `yc2_w27_s12` M32.C2.L-logic.V2.U05, STEP-12 §8.4 item 3). The expert
reviews a file once per fingerprint, so the fingerprint is what decides when it thinks again: the file's
events, its open asks, whose move it is, how long it has been quiet and how soon its next meeting is —
each clock as a RUNG, never an instant (`reason/fingerprint` — STEP-02's rule), with a 72-hour rung added
so a meeting moving from four days away to three re-thinks it — the brief's version, the playbook's
version, the founder's verdicts on its people's cards, the dossier's version, and who decides: the model
and the prompt version (`06` D48). The expert's own past reviews are NOT in it: a review must never be
the reason for the next one.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from genios_engine.context.file_judgments import Verdict
from genios_engine.context.workstream_timeline import Touch
from genios_engine.context.workstreams import Ask
from genios_engine.reason.expert import fingerprint as F
from tests.reason.expert.test_the_dossier import NOW, _judgments, _parts, _playbook, _touch

pytestmark = pytest.mark.unit

MODEL, PROMPT = "claude-sonnet-5", "expert-review.v1"


def _fp(parts, *, model=MODEL, prompt=PROMPT) -> str:
    return F.file_fingerprint(parts, model=model, prompt_version=prompt)


def _later(parts, minutes: float):
    """The same file, read `minutes` later: every clock moves, nothing else does."""
    tl = parts.timeline
    quiet = None if tl.days_quiet is None else round(tl.days_quiet + minutes / 1440, 2)
    return dataclasses.replace(parts, as_of=parts.as_of + timedelta(minutes=minutes),
                               timeline=dataclasses.replace(tl, days_quiet=quiet))


def _quiet(parts, days: float):
    return dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline, days_quiet=days))


def _meeting_in(parts, days: float):
    meeting = Touch(at=parts.as_of + timedelta(days=days), kind="meeting", direction="meeting",
                    who=None, who_name=None, event_id="evt_call", thread=None)
    return dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline,
                                                                    upcoming=(meeting,)))


def test_the_same_file_is_the_same_fingerprint_and_it_reads_as_one():
    one, two = _fp(_parts()), _fp(_parts())
    assert one == two and one.startswith("ffp-") and len(one) == len("ffp-") + 24


def test_a_quarter_of_an_hour_later_is_the_same_file():
    assert _fp(_later(_parts(), 15)) == _fp(_parts())


def test_a_new_mail_is_a_different_file():
    touches = (_touch(0, direction="out"), _touch(3), _touch(5, direction="out"), _touch(9))
    assert _fp(_parts(touches=touches)) != _fp(_parts())


@pytest.mark.parametrize("before, after, moves", [
    (6.0, 7.0, True),          # STEP-02's own case: a wait crossing from 6 to 7 days re-thinks
    (6.0, 6.9, False),         # within a rung: the same file
    (13.0, 14.5, True),
    (0.2, 0.9, False),
])
def test_how_long_it_has_been_quiet_counts_by_its_rung(before, after, moves):
    assert (_fp(_quiet(_parts(), before)) != _fp(_quiet(_parts(), after))) is moves


@pytest.mark.parametrize("before, after, moves", [
    (4.0, 3.0, True),          # the 72-hour rung: a meeting four days away, then three
    (10.0, 9.0, False),        # both inside the fortnight
    (1.5, 0.5, False),         # both within two days
    (2.5, 1.9, True),          # crossing into two days
])
def test_how_soon_the_next_meeting_is_counts_by_its_rung(before, after, moves):
    assert (_fp(_meeting_in(_parts(), before)) != _fp(_meeting_in(_parts(), after))) is moves


def test_the_brief_the_playbook_and_who_decides_are_inputs():
    base = _parts()
    assert _fp(_parts(brief=False)) != _fp(base)
    assert _fp(_parts(playbook=_playbook(reviewed=True))) != _fp(base)
    assert _fp(base, model="claude-sonnet-6") != _fp(base)
    assert _fp(base, prompt="expert-review.v2") != _fp(base)


def test_an_ask_and_whose_move_are_inputs():
    base = _parts()
    asked = _parts(asks=(Ask(loop_id="lp_9", kind="request", asked_by="node_kunal", owed_by="us",
                             thread_id="t_k", opened_at=NOW),))
    assert _fp(asked) != _fp(base)
    theirs = dataclasses.replace(base, file=dataclasses.replace(base.file, whose_move="theirs"))
    assert _fp(theirs) != _fp(base)


def test_a_new_verdict_on_its_peoples_cards_is_an_input():
    base = _parts()
    j = _judgments()
    card = dataclasses.replace(j.cards[0], verdicts=j.cards[0].verdicts + (
        Verdict(cause="wrong", reason="bad_timing", at=NOW),))
    judged = dataclasses.replace(base, judgments=dataclasses.replace(j, cards=(card,)))
    assert _fp(judged) != _fp(base)


def test_the_experts_own_past_review_is_never_the_reason_for_the_next():
    base = _parts()
    j = base.judgments
    review = dataclasses.replace(j.reviews[0], fingerprint="fp_newer", status="refused",
                                 reason="number_not_in_dossier: 32")
    reviewed = dataclasses.replace(base, judgments=dataclasses.replace(j, reviews=j.reviews + (review,)))
    assert _fp(reviewed) == _fp(base)


def test_the_inputs_are_readable_and_carry_no_instant():
    inputs = F.fingerprint_inputs(_meeting_in(_quiet(_parts(), 6.0), 4.0), model=MODEL,
                                  prompt_version=PROMPT)
    assert inputs["quiet"] == ">=5" and inputs["next_meeting"] == "<=168"
    assert inputs["who_decides"] == {"model": MODEL, "prompt_version": PROMPT,
                                     "dossier_version": "dossier.v1"}
    assert "as_of" not in inputs and "reviews" not in inputs
    assert F.HOURS_UNTIL[:3] == (0, 48, 72)
