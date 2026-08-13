"""Update 3 — cross-tool meeting lifecycle honesty.

A person's card must surface the connected Calendar meeting, and it must reconcile the lifecycle
honestly: a past scheduled event proves the meeting was SCHEDULED, never that it was HELD. 'Held'
needs attendance/transcript/follow-up evidence we do not have.
"""
from datetime import datetime, timedelta, timezone

from genios_engine.api.routes import _meeting_lifecycle

NOW = datetime(2026, 8, 13, tzinfo=timezone.utc)


def test_cancelled_meeting_is_cancelled():
    assert _meeting_lifecycle("cancelled", "2026-07-20T13:00:00+05:30", NOW) == ("cancelled", "Cancelled")


def test_future_meeting_is_scheduled():
    future = (NOW + timedelta(days=3)).isoformat()
    assert _meeting_lifecycle("confirmed", future, NOW)[0] == "scheduled"


def test_past_scheduled_is_never_claimed_held():
    state, label = _meeting_lifecycle("confirmed", "2026-07-20T13:00:00+05:30", NOW)
    assert state == "past_scheduled"
    assert "unverified" in label.lower()
    assert "held" not in label.lower()  # occurrence must not be asserted without evidence


def test_missing_start_falls_back_to_scheduled_not_held():
    assert _meeting_lifecycle("confirmed", None, NOW) == ("scheduled", "Scheduled")


def test_unparseable_start_does_not_crash():
    assert _meeting_lifecycle("confirmed", "not-a-date", NOW)[0] == "scheduled"
