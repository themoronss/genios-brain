"""STEP-14 · the lines code writes for the card — why now, what remains, who and what the file is, its window.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_card_lines.py

Tree `yc2_w27_s14` M43.C2.L-logic.V0.U02 (`reason/expert/card_lines`; STEP-14 §8.4 item 5, s14-F6, s14-F9; `03` F64,
F179). The gold card's middle was empty on all 39 golden cards: why now (0/39), what remains (0/39), the role
(0/39); a bare domain as the subject on 21; the window the 7-day default on 20 (every move with no date). The review's
triggers, from which a why-now is built, are machine text ("new since the last review: evt_bcd6…", "the next
meeting: <=336 → <=48"). These lines are CODE's — no model writes them, so the card has the same shape whichever
model reviewed — pure over the dossier's parts, the review and its triggers:

  why now       the trigger as a sentence: the new touch's who and day, the meeting's title and its days away —
                never "first look", never an id;
  what remains  the file's open asks, ours and theirs, each with who and since when;
  subject/role  the file's counterparty person and company — never a bare domain where a person is named — and the
                brief's kind of work and role;
  window        the move's date, else the playbook stage's prior, else the file's measured reply time, else seven
                days, labelled a default.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from genios_engine.context.workstreams import Ask
from genios_engine.context.workstream_timeline import Touch
from genios_engine.reason.expert import card_lines as L
from genios_engine.reason.expert.triggers import Trigger
from tests.reason.expert.test_the_dossier import KUNAL, NOW, _parts, _playbook, _review, _touch

pytestmark = pytest.mark.unit


def _lines(parts=None, review=None, triggers=(), **over):
    parts = parts or _parts()
    if over:
        parts = dataclasses.replace(parts, **over)
    return L.card_lines(parts, review, triggers)


def _with_asks(*asks):
    parts = _parts()
    return dataclasses.replace(parts, file=dataclasses.replace(parts.file, open_asks=tuple(asks)))


# ── why now ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_new_touch_is_said_by_who_wrote_and_when():
    parts = _parts()
    newest = parts.timeline.touches[-1]                   # we wrote — "Thanks Kunal, I will book it again tonight."
    said = _lines(parts, triggers=[Trigger("new_evidence", f"new since the last review: {newest.event_id}")]).why_now
    assert said == f"You wrote to Meridian Ventures on {L.day(newest.at)}"
    inbound = parts.timeline.touches[1]
    said = _lines(parts, triggers=[Trigger("new_evidence", f"new since the last review: {inbound.event_id}")]).why_now
    assert said == f"Kunal Shah wrote on {L.day(inbound.at)}"
    assert "evt_" not in said


def test_a_meeting_closing_in_is_said_by_its_title_and_its_days_away():
    parts = _parts()
    meeting = Touch(at=NOW + timedelta(days=2, hours=1), kind="meeting", direction="meeting", who=KUNAL,
                    who_name="Kunal Shah", event_id="evt_next", thread=None, outcome="emitted", words=None)
    parts = dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline, upcoming=(meeting,)),
                                meeting_titles={"evt_next": "Partner meeting — Meridian"})
    said = _lines(parts, triggers=[Trigger("date_closing_in", "the next meeting: <=336 → <=72")]).why_now
    assert said == f"Your meeting “Partner meeting — Meridian” is in 2 days, on {L.day(meeting.at)}"
    untitled = dataclasses.replace(parts, meeting_titles={})
    assert _lines(untitled, triggers=[Trigger("date_closing_in", "the next meeting: <=336 → <=72")]).why_now == \
        f"Your meeting with Kunal Shah is in 2 days, on {L.day(meeting.at)}"


def test_a_quiet_past_their_usual_is_said_in_days():
    parts = _parts()
    said = _lines(parts, triggers=[Trigger("reply_overdue", "their move, quiet 9 days — past the 2 days they usually "
                                                            "take")]).why_now
    assert said == "Kunal Shah has not replied in 59 days — past the 1.92 days they usually take"


def test_a_first_look_is_never_said_as_one():
    """A file never judged: why now is the newest thing on it, never "first look"."""
    parts = _parts()
    newest = parts.timeline.touches[-1]
    for trigger in (Trigger("first_look", "never judged"), Trigger("version_moved", "the check moved: a → b")):
        said = _lines(parts, triggers=[trigger]).why_now
        assert said == f"You wrote to Meridian Ventures on {L.day(newest.at)}" and "look" not in said.lower()


def test_the_founder_asking_is_said_as_you_asked():
    assert _lines(triggers=[Trigger("founder_asked", "the founder asked about it")]).why_now == "You asked about it"


def test_triggers_as_stored_are_read_too():
    parts = _parts()
    newest = parts.timeline.touches[-1]
    stored = [("new_evidence", f"new since the last review: {newest.event_id}")]
    assert _lines(parts, triggers=stored).why_now.startswith("You wrote to")


# ── what remains ─────────────────────────────────────────────────────────────────────────────────────────────
def test_what_remains_is_each_open_ask_ours_and_theirs_with_who_and_since_when():
    opened = NOW - timedelta(days=9)
    parts = _with_asks(Ask(loop_id="l1", kind="information_requested", asked_by="node_0", owed_by="us",
                           thread_id="t_k", opened_at=opened),
                       Ask(loop_id="l2", kind="meeting_request", asked_by="node_0", owed_by="them",
                           thread_id="t_k", opened_at=None))
    remains = _lines(parts).what_remains
    assert remains == (f"Partner 0 asked for information — waiting on you since {L.day(opened)}",
                       "A meeting — waiting on Partner 0")


def test_an_ask_by_someone_unnamed_is_said_as_the_files():
    parts = _with_asks(Ask(loop_id="l1", kind="question", asked_by="node_unknown", owed_by="us", thread_id=None,
                           opened_at=None))
    assert _lines(parts).what_remains == ("Meridian Ventures asked a question — waiting on you",)


def test_nothing_open_remains_nothing():
    assert _lines().what_remains == ()


# ── subject and role ────────────────────────────────────────────────────────────────────────────────────────
def test_the_subject_is_the_person_and_the_company_never_a_bare_domain():
    lines = _lines()
    assert (lines.subject, lines.company) == ("Kunal Shah", "Meridian Ventures")
    assert (lines.kind_of_work, lines.role) == ("investor", None)
    parts = _parts()
    bare = dataclasses.replace(parts, file=dataclasses.replace(parts.file, counterparty="meridianvc.test"))
    assert (_lines(bare).subject, _lines(bare).company) == ("Kunal Shah", "meridianvc.test")
    nobody = dataclasses.replace(bare, timeline=dataclasses.replace(bare.timeline, touches=tuple(
        dataclasses.replace(t, who_name=None) for t in bare.timeline.touches)), numbers=None)
    assert _lines(nobody).subject == "meridianvc.test", "with no person named, the company — as it is"


# ── the window ───────────────────────────────────────────────────────────────────────────────────────────────
def test_the_window_is_the_moves_date_first():
    review = _review("evt_005", "Hi Kunal")
    move = dataclasses.replace(review.next_move, by_when=(NOW + timedelta(days=3)).date())
    lines = _lines(review=dataclasses.replace(review, next_move=move))
    assert (lines.window_days, lines.window_from) == (3, L.MOVE_DATE)


def _undated(*, stage=None):
    review = _review("evt_005", "Hi Kunal")
    return dataclasses.replace(review, next_move=dataclasses.replace(review.next_move, by_when=None),
                               expected_vs_actual=dataclasses.replace(review.expected_vs_actual, stage=stage))


def test_else_the_playbook_stages_prior():
    lines = _lines(review=_undated(stage="first_call"))
    assert (lines.window_days, lines.window_from) == (21, L.STAGE_PRIOR)
    assert _lines(review=_undated(stage="no_such_stage")).window_from == L.REPLY_TIME, "a stage it does not declare"


def test_else_the_files_measured_reply_time_else_a_default_said_so():
    review = _undated()
    lines = _lines(review=review)
    assert (lines.window_days, lines.window_from) == (2, L.REPLY_TIME), "1.92 days, rounded up"
    parts = _parts()
    unmeasured = dataclasses.replace(parts, numbers=None, timeline=dataclasses.replace(
        parts.timeline, usual_gap=dataclasses.replace(parts.timeline.usual_gap, n=0, value=None)))
    lines = _lines(unmeasured, review=review)
    assert (lines.window_days, lines.window_from) == (L.DEFAULT_WINDOW_DAYS, L.DEFAULT) == (7, "default")
    assert L.WINDOW_SAID[L.DEFAULT] == "a default — nothing on the file sets it"


def test_a_review_with_no_move_still_has_a_window():
    assert _lines(review=None).window_days >= 1


# ── kept beside the check ────────────────────────────────────────────────────────────────────────────────────
def test_the_lines_read_back_as_stored():
    review = _review("evt_005", "Hi Kunal")
    lines = _lines(review=review, triggers=[Trigger("founder_asked", "the founder asked about it")])
    assert L.CardLines.from_mapping(lines.as_mapping()) == lines
    import json
    assert L.CardLines.from_mapping(json.loads(json.dumps(lines.as_mapping()))) == lines


def test_the_lines_are_pure():
    review = _review("evt_005", "Hi Kunal")
    assert _lines(review=review) == _lines(review=review)
    assert _playbook  # the dossier's fixtures are the lines' inputs
    assert _touch(0).event_id == "evt_000"


def test_the_subject_is_who_last_wrote_to_us_never_our_own_name():
    """Our own outgoing touch carries a name too — the founder's: never the card's subject."""
    parts = _parts()
    ours = tuple(dataclasses.replace(t, who_name="Arjun Rao") if t.direction == "out" else t
                 for t in parts.timeline.touches)
    assert _lines(dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline, touches=ours))).subject \
        == "Kunal Shah"
    unnamed = tuple(dataclasses.replace(t, who_name=None) for t in parts.timeline.touches)
    assert _lines(dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline, touches=unnamed))).subject \
        == "Partner 0", "else a person its numbers name"


def test_of_several_new_touches_the_newest_is_said():
    parts = _parts()
    first, second, _third = parts.timeline.touches
    said = _lines(parts, triggers=[Trigger("new_evidence", f"new since the last review: {second.event_id}, "
                                                           f"{first.event_id}")]).why_now
    assert said == f"Kunal Shah wrote on {L.day(second.at)}", "the newest of them, whatever order they are named in"


def test_your_answer_is_said_as_your_answer():
    said = _lines(triggers=[Trigger("new_evidence", "new since the last review: answer:fq_1")]).why_now
    assert said == "You answered its question"


def test_a_window_from_nowhere_is_refused():
    lines = _lines()
    with pytest.raises(ValueError):
        L.CardLines.from_mapping({**lines.as_mapping(), "window": {"days": 3, "from": "a guess"}})
    with pytest.raises(ValueError):
        L.CardLines.from_mapping({**lines.as_mapping(), "window": {"days": 0, "from": "default"}})
