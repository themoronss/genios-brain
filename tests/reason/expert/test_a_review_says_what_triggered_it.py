"""STEP-12 · a review says what triggered it — and a file nothing touched is not reviewed.

    pytest tests/reason/expert/test_a_review_says_what_triggered_it.py -q

`reason/expert/triggers.py` (tree `yc2_w27_s12` M32.C3.L-logic.V1.U09, `05` §5). Against what the last
standing review SAW (its kept inputs, 0198): new evidence — and a meeting it saw booked, held since; a
date closing in — the next meeting or the nearest promised date a rung closer; their reply overdue
against the time they usually take; a number past the file's normal — the longest gap it ever had, or
the time we usually take on our move; the founder asking; and a first look at a file never judged.
Each crossing only once: what was already overdue at the last review triggers nothing. Moving the
brief, the playbook, a verdict or who decides ALONE re-thinks nothing (`06` D48's default).
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta
from types import SimpleNamespace

import pytest

from genios_engine.context.workstream_numbers import PersonNumbers
from genios_engine.context.workstream_timeline import Touch
from genios_engine.contracts.measured import PLAYBOOK_PRIOR, Measured
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert import triggers as T
from tests.reason.expert.test_the_dossier import NOW, _parts, _playbook, _touch
from tests.reason.expert.test_the_file_fingerprint import _promise

pytestmark = pytest.mark.unit

MODEL, PROMPT = "claude-sonnet-5", "expert-review.v1"


def _inputs(parts, *, prompt=PROMPT):
    return F.fingerprint_inputs(parts, model=MODEL, prompt_version=prompt)


def _last(parts, *, hours_ago: float = 1.0, kept: bool = True):
    """The last standing review, as the store reads it back: what it saw is JSON — lists, not tuples."""
    import json
    seen = json.loads(json.dumps(_inputs(parts))) if kept else None
    return SimpleNamespace(inputs=seen, reviewed_at=NOW - timedelta(hours=hours_ago))


def _kinds(found):
    return [t.kind for t in found]


def _at(parts, *, quiet: float, move: str):
    tl = dataclasses.replace(parts.timeline, days_quiet=quiet)
    return dataclasses.replace(parts, timeline=tl,
                               file=dataclasses.replace(parts.file, whose_move=move))


def _meeting(parts, days: float, event_id: str = "evt_call"):
    meeting = Touch(at=NOW + timedelta(days=days), kind="meeting", direction="meeting", who=None,
                    who_name=None, event_id=event_id, thread=None)
    if days > 0:
        return dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline,
                                                                        upcoming=(meeting,)))
    return dataclasses.replace(parts, timeline=dataclasses.replace(
        parts.timeline, touches=parts.timeline.touches + (meeting,), upcoming=()))


# ── a first look, and nothing ──────────────────────────────────────────────────────────────────

def test_a_file_never_judged_is_a_first_look():
    found = T.triggers_for(_parts(), _inputs(_parts()))
    assert _kinds(found) == [T.FIRST_LOOK] and found[0].says == "never judged"


def test_a_review_whose_inputs_were_not_kept_is_looked_at_again():
    found = T.triggers_for(_parts(), _inputs(_parts()), last=_last(_parts(), kept=False))
    assert _kinds(found) == [T.FIRST_LOOK] and "not kept" in found[0].says


def test_a_file_nothing_touched_is_not_reviewed():
    assert T.triggers_for(_parts(), _inputs(_parts()), last=_last(_parts())) == ()


@pytest.mark.parametrize("moved", ["brief", "playbook", "prompt"])
def test_what_a_review_stood_on_moving_alone_re_thinks_nothing(moved):
    """`06` D48 is open; its default — wait for the inputs — holds for all four."""
    now = {"brief": _parts(brief=False), "playbook": _parts(playbook=_playbook(reviewed=True)),
           "prompt": _parts()}[moved]
    inputs = _inputs(now, prompt="expert-review.v2" if moved == "prompt" else PROMPT)
    assert inputs != _last(_parts()).inputs
    assert T.triggers_for(now, inputs, last=_last(_parts())) == ()


# ── new evidence ───────────────────────────────────────────────────────────────────────────────

def test_a_new_mail_is_new_evidence_and_says_which():
    before = _parts()
    now = _parts(touches=before.timeline.touches + (_touch(9),))
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert _kinds(found) == [T.NEW_EVIDENCE] and found[0].says == "new since the last review: evt_009"


def test_mail_that_arrived_late_is_new_evidence_however_old_it_is():
    """A resync brings a mail from before the last review: a cut by time would miss it."""
    before = _parts()
    old = dataclasses.replace(_touch(1), event_id="evt_resynced")
    now = _parts(touches=tuple(sorted(before.timeline.touches + (old,), key=lambda t: t.at)))
    assert old.at < NOW - timedelta(days=30)
    assert "evt_resynced" in T.triggers_for(now, _inputs(now), last=_last(before))[0].says


def test_a_meeting_it_saw_booked_and_held_since_is_new_evidence():
    before, now = _meeting(_parts(), 0.5), _meeting(_parts(), -0.1)
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert _kinds(found) == [T.NEW_EVIDENCE] and "held" in found[0].says and "evt_call" in found[0].says


def test_a_long_backfill_is_listed_then_counted():
    before = _parts()
    fresh = tuple(dataclasses.replace(_touch(40 + n), event_id=f"evt_b{n:02d}") for n in range(13))
    now = _parts(touches=before.timeline.touches + fresh)
    says = T.triggers_for(now, _inputs(now), last=_last(before))[0].says
    assert says.endswith(" and 3 more") and says.count("evt_b") == T.LISTED


# ── a date closing in ──────────────────────────────────────────────────────────────────────────

def test_the_next_meeting_a_rung_closer_is_a_date_closing_in():
    before, now = _meeting(_parts(), 4.0), _meeting(_parts(), 2.9)
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert _kinds(found) == [T.DATE_CLOSING_IN]
    assert found[0].says == "the next meeting: <=168 → <=72"


def test_beyond_the_last_rung_is_further_than_the_last_rung():
    before, now = _meeting(_parts(), 95.0), _meeting(_parts(), 85.0)      # 2,280 h, then 2,040 h
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert [t.says for t in found] == ["the next meeting: >2160 → <=2160"]


def test_a_meeting_moved_further_away_closes_in_on_nothing():
    before, now = _meeting(_parts(), 2.9), _meeting(_parts(), 4.0)
    assert T.triggers_for(now, _inputs(now), last=_last(before)) == ()


def test_a_meeting_booked_since_is_new_and_closing_in():
    before, now = _parts(), _meeting(_parts(), 2.0)
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert _kinds(found) == [T.NEW_EVIDENCE, T.DATE_CLOSING_IN]
    assert found[1].says == "the next meeting: none → <=48"


def test_a_promised_date_a_rung_closer_is_a_date_closing_in():
    before = _parts(promises=(_promise(100.0),))
    now = _parts(promises=(_promise(70.0),))
    found = T.triggers_for(now, _inputs(now), last=_last(before))
    assert _kinds(found) == [T.DATE_CLOSING_IN]
    assert found[0].says == "the nearest promised date: <=168 → <=72"


# ── a reply overdue, a number past normal ──────────────────────────────────────────────────────

def test_their_reply_overdue_against_their_own_time_triggers_once():
    """Kunal usually replies in 1.92 days (`_numbers`): quiet 1.0 at the last review, 2.5 now."""
    assert T.their_usual(_parts()) == 1.92
    before = _at(_parts(), quiet=1.0, move="theirs")
    now = _at(_parts(), quiet=2.5, move="theirs")
    found = T.triggers_for(now, _inputs(now), last=_last(before, hours_ago=36))
    assert T.REPLY_OVERDUE in _kinds(found)
    assert next(t for t in found if t.kind == T.REPLY_OVERDUE).says == (
        "their move, quiet 2.5 days — past the 1.92 days they usually take")
    # already overdue at the last review: nothing new crossed
    again = _at(_parts(), quiet=3.0, move="theirs")
    assert T.REPLY_OVERDUE not in _kinds(T.triggers_for(again, _inputs(again),
                                                         last=_last(now, hours_ago=12)))


def test_on_our_move_their_reply_time_is_no_trigger_but_ours_is():
    """We usually answer in 0.4 days (`_numbers`): our move, quiet 0.3 then and 1.2 now."""
    before = _at(_parts(), quiet=0.3, move="ours")
    now = _at(_parts(), quiet=1.2, move="ours")
    found = T.triggers_for(now, _inputs(now), last=_last(before, hours_ago=21.6))
    assert T.REPLY_OVERDUE not in _kinds(found)
    assert any(t.kind == T.PAST_NORMAL and t.says == "our move, quiet 1.2 days — past the 0.4 days we "
               "usually take" for t in found)


def test_their_move_turning_ours_is_measured_by_ours_alone():
    """Quiet 0.5 days at the last review was past our 0.4 — but it was their move then, not ours."""
    before = _at(_parts(), quiet=0.5, move="theirs")
    now = _at(_parts(), quiet=0.7, move="ours")
    found = T.triggers_for(now, _inputs(now), last=_last(before, hours_ago=4.8))
    assert any(t.kind == T.PAST_NORMAL and t.says.startswith("our move") for t in found)


def _person(i: int, *, theirs: Measured, yours: Measured) -> PersonNumbers:
    return PersonNumbers(node_id=f"node_{i}", key=f"p{i}@meridianvc.test", name=None,
                         their_reply_time=theirs, their_normal=None, your_reply_time=yours,
                         your_normal=None, bounced_at=None)


def _days(value, n=1):
    return Measured(value=value, n=n, basis="person", unit="days")


def _with_people(*people, overall=None):
    parts = _parts()
    return dataclasses.replace(parts, numbers=dataclasses.replace(
        parts.numbers, people=tuple(people), your_normal_overall=overall))


def test_their_usual_is_the_longest_any_of_its_people_take_measured_here():
    two = _with_people(_person(0, theirs=_days(1.0), yours=_days(None, 0)),
                       _person(1, theirs=_days(3.0), yours=_days(None, 0)))
    assert T.their_usual(two) == 3.0
    prior = Measured(value=9.0, n=0, basis="playbook", source=PLAYBOOK_PRIOR, unit="days")
    assert T.their_usual(_with_people(_person(0, theirs=prior, yours=_days(None, 0)),
                                      _person(1, theirs=_days(2.0), yours=_days(None, 0)))) == 2.0


def test_with_no_reply_measured_their_usual_is_the_files_usual_gap():
    nobody = _with_people(_person(0, theirs=_days(None, 0), yours=_days(None, 0)))
    gap = nobody.timeline.usual_gap
    assert gap.n > 0 and T.their_usual(nobody) == gap.value


def test_our_usual_is_the_longest_we_take_here_else_our_normal_overall():
    two = _with_people(_person(0, theirs=_days(None, 0), yours=_days(0.2, 2)),
                       _person(1, theirs=_days(None, 0), yours=_days(0.9, 4)))
    assert T.our_usual(two) == 0.9
    overall = Measured(value=0.6, n=12, basis="tenant", unit="days")
    none_here = _with_people(_person(0, theirs=_days(None, 0), yours=_days(None, 0)), overall=overall)
    assert T.our_usual(none_here) == 0.6
    assert T.our_usual(_with_people(_person(0, theirs=_days(None, 0), yours=_days(None, 0)))) is None


def test_quiet_past_the_longest_gap_it_ever_had_is_past_normal_once():
    parts = _parts()
    longest = parts.timeline.longest_gap_days
    before = _at(parts, quiet=longest - 0.05, move="none")
    now = _at(parts, quiet=longest + 0.05, move="none")
    found = T.triggers_for(now, _inputs(now), last=_last(before, hours_ago=2.4))
    assert [t.kind for t in found] == [T.PAST_NORMAL] and "the longest gap it ever had" in found[0].says
    later = _at(parts, quiet=longest + 1, move="none")
    assert T.triggers_for(later, _inputs(later), last=_last(now, hours_ago=22)) == ()


def test_with_no_pattern_yet_nothing_is_overdue():
    parts = _parts(touches=(_touch(0),))
    bare = dataclasses.replace(parts, numbers=None)
    assert T.their_usual(bare) is None and T.our_usual(bare) is None
    now = _at(bare, quiet=30.0, move="theirs")
    assert T.triggers_for(now, _inputs(now), last=_last(_at(bare, quiet=1.0, move="theirs"),
                                                          hours_ago=29 * 24)) == ()


# ── the founder ────────────────────────────────────────────────────────────────────────────────

def test_the_founder_asking_is_a_trigger_of_its_own():
    found = T.triggers_for(_parts(), _inputs(_parts()), last=_last(_parts()), asked=True)
    assert _kinds(found) == [T.FOUNDER_ASKED]
    assert _kinds(T.triggers_for(_parts(), _inputs(_parts()), asked=True)) == [T.FIRST_LOOK,
                                                                               T.FOUNDER_ASKED]


def test_every_kind_is_named_once():
    assert len(T.KINDS) == len(set(T.KINDS)) == 6
