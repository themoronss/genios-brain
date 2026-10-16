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

M32.C2.L-logic.V2.U09: a deadline closing in moves the file too — the nearest due date of a promise still
open in its mail, ours or theirs, as a rung of the same ladder as the next meeting; a *"soon"* is no
deadline (`06` D56) and a promise kept is owed no more.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from genios_engine.context.file_judgments import Verdict
from genios_engine.context.workstream_timeline import Touch
from genios_engine.context.workstreams import Ask
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert.dossier import Promise
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


def _promise(hours: float | None, *, words: str = "I will send the deck", status: str | None = "open",
             ours: bool = True, pid: str = "node_c1") -> Promise:
    return Promise(promise_id=pid, words=words, quote=None,
                   due_at=None if hours is None else NOW + timedelta(hours=hours), status=status,
                   owner="arjun@nimbuslabs.test" if ours else "kunal@meridianvc.test", ours=ours,
                   event_id="evt_005")


def _promised(*promises):
    return _parts(promises=promises)


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


@pytest.mark.parametrize("before, after, moves", [
    (100.0, 70.0, True),       # a promised date four days away, then three
    (100.0, 99.0, False),      # within its rung
    (30.0, -2.0, True),        # due, then past due: past due is a rung of its own
    (-30.0, -50.0, False),     # past due is past due
])
def test_a_deadline_closing_in_counts_by_its_rung(before, after, moves):
    assert (_fp(_promised(_promise(before))) != _fp(_promised(_promise(after)))) is moves


def test_the_nearest_open_promise_is_the_deadline_ours_or_theirs():
    near, far = _promise(70.0, pid="node_c1"), _promise(500.0, pid="node_c2", ours=False)
    inputs = F.fingerprint_inputs(_promised(far, near), model=MODEL, prompt_version=PROMPT)
    assert inputs["due"] == "<=72"
    theirs = F.fingerprint_inputs(_promised(_promise(70.0, ours=False)), model=MODEL,
                                  prompt_version=PROMPT)
    assert theirs["due"] == "<=72"
    assert F.nearest_due(_promised(far, near)) == NOW + timedelta(hours=70)


@pytest.mark.parametrize("status", [None, "", "open", "Open ", "OPEN"])
def test_a_promise_with_no_status_or_open_in_any_case_is_still_owed(status):
    """`commitment.status` defaults to open where nothing wrote it (`context/outreach_situations`)."""
    inputs = F.fingerprint_inputs(_promised(_promise(70.0, status=status)), model=MODEL,
                                  prompt_version=PROMPT)
    assert inputs["due"] == "<=72"


@pytest.mark.parametrize("promise", [
    _promise(None),                                                       # no date at all
    _promise(70.0, words="I will send the deck soon"),                    # "soon" is no deadline (D56)
    _promise(70.0, status="done"),                                        # kept: owed no more
    _promise(70.0, status="cancelled"),
])
def test_a_promise_that_is_no_deadline_moves_nothing(promise):
    assert F.fingerprint_inputs(_promised(promise), model=MODEL, prompt_version=PROMPT)["due"] is None
    assert _fp(_promised(promise)) == _fp(_parts())


def test_a_quarter_of_an_hour_later_a_deadline_is_the_same_deadline():
    assert _fp(_later(_promised(_promise(100.0)), 15)) == _fp(_promised(_promise(100.0)))


def test_the_inputs_are_readable_and_carry_no_instant():
    inputs = F.fingerprint_inputs(_meeting_in(_quiet(_parts(), 6.0), 4.0), model=MODEL,
                                  prompt_version=PROMPT)
    assert inputs["quiet"] == ">=5" and inputs["next_meeting"] == "<=168" and inputs["due"] is None
    assert inputs["who_decides"] == {"model": MODEL, "prompt_version": PROMPT,
                                     "dossier_version": "dossier.v2"}   # ⛔ RESTATED by STEP-13b M37.C3.L-interface.V4.U01: was dossier.v1
    assert "as_of" not in inputs and "reviews" not in inputs
    assert F.HOURS_UNTIL[:3] == (0, 48, 72)


# =================================================================================================
# STEP-16 · your correction moves the file (`yc2_w27_s16` M46.C4.L-logic.V3.U04)
# =================================================================================================
def _corrected(parts, *ids, scope="file"):
    from genios_engine.context.founder_corrections import Correction
    return dataclasses.replace(parts, corrections=tuple(Correction(
        correction_id=i, file_id="node_meridian", card_id=None, feedback_id=None, reason=None,
        words="news only on milestones", scope=scope, kind="investor" if scope == "kind" else None,
        brief_line_id=None, corrected_by="user_arjun", corrected_at=NOW, state="standing") for i in ids))


def test_a_file_with_no_correction_is_fingerprinted_as_before():
    parts = _parts()
    assert "corrections" not in F.fingerprint_inputs(parts, model=MODEL, prompt_version=PROMPT)
    assert _fp(_corrected(parts)) == _fp(parts)


@pytest.mark.parametrize("scope", ["file", "kind"])
def test_your_correction_of_the_file_or_its_kind_moves_it(scope):
    parts = _parts()
    one = _corrected(parts, "fc_a", scope=scope)
    assert _fp(one) != _fp(parts)
    assert F.fingerprint_inputs(one, model=MODEL, prompt_version=PROMPT)["corrections"] == ["corr:fc_a"]
    assert _fp(_corrected(parts, "fc_a", "fc_b", scope=scope)) != _fp(one), "another correction moves it again"


def test_the_same_corrections_in_another_order_are_the_same_file():
    parts = _parts()
    assert _fp(_corrected(parts, "fc_a", "fc_b")) == _fp(_corrected(parts, "fc_b", "fc_a"))
