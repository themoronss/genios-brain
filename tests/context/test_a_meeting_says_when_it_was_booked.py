"""STEP-13 · a meeting says when it was first booked, and who set it up — what "already answered?" reads.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_meeting_says_when_it_was_booked.py -q

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U15 (`context/workstream_timeline.Touch.booked_at`,
`reason/expert/dossier.people_of`). A meeting dated after an ask answered it, whenever it was booked (crosscheck
X14): one booked BEFORE the ask, and only moved after it, is no answer to it. The calendar's first version of
a meeting is when the file first saw it booked; every later version is an edit of the same booking. The
file's people then carry, for the check: each open ask (its thread, who asked), each mail we wrote, each
meeting — when booked, and who set it up. Nothing of it is printed: the dossier is unchanged.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.context.workstream_timeline import timeline_for

from .test_a_file_has_a_timeline import ORG, PRIYA, _file, _meeting, store  # noqa: F401 — the fixture
from .workstream_world import FOUNDER, T0, process

pytestmark = pytest.mark.pg


def test_a_moved_meeting_was_booked_when_its_first_version_came(store):
    process(store, ORG, event_id="evt_ask", sender=PRIYA, thread="t_np", at=T0)
    _meeting(store, "evt_call_v2", meeting="call_moved", start=T0 + timedelta(days=10),
             captured=T0 + timedelta(days=2))
    _meeting(store, "evt_call_v1", meeting="call_moved", start=T0 + timedelta(days=9),
             captured=T0 + timedelta(days=1))
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=20))
    [meeting] = [t for t in tl.touches if t.kind == "meeting"]
    assert meeting.event_id == "evt_call_v2" and meeting.booked_at == T0 + timedelta(days=1)
    assert all(t.booked_at is None for t in tl.touches if t.kind == "mail")


def test_a_meeting_still_to_come_says_when_it_was_booked(store):
    process(store, ORG, event_id="evt_ask", sender=PRIYA, thread="t_np", at=T0)
    _meeting(store, "evt_next", meeting="next_call", start=T0 + timedelta(days=45),
             captured=T0 + timedelta(days=3), organizer=PRIYA)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=10))
    [booked] = tl.upcoming
    assert booked.booked_at == T0 + timedelta(days=3) and booked.who == PRIYA
    assert FOUNDER != booked.who
