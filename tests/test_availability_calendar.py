"""Calendar → availability, deterministically (no LLM): an outOfOffice event or an all-day
"Leave"/"OOO"/"Vacation"/"Holiday" block is its owner's window. Anything we cannot attribute to a
named owner stays the meeting node it already is."""
from __future__ import annotations

from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
from genios_engine.capture.structured.apply import calendar_availability


def _raw(**kw):
    base = {"summary": "Out of office", "start": "2026-09-15T09:00:00+05:30",
            "end": "2026-09-17T18:00:00+05:30", "status": "confirmed", "attendees": [],
            "eventType": "outOfOffice", "organizer": "anisha@acme.io",
            "calendar_owner": "anisha@acme.io", "updated": "2026-09-01T10:00:00Z"}
    base.update(kw)
    return base


def test_out_of_office_event_is_an_ooo_window_for_the_owner():
    a = calendar_availability(_raw())
    assert (a["person"], a["kind"], a["from"], a["to"], a["cancelled"]) == (
        "anisha@acme.io", "ooo", "2026-09-15", "2026-09-17", False)
    assert a["updated"] == "2026-09-01T10:00:00Z"


def test_all_day_leave_block_end_date_is_exclusive():
    a = calendar_availability(_raw(summary="Leave", eventType="default",
                                   start="2026-09-15", end="2026-09-23"))
    assert (a["kind"], a["from"], a["to"]) == ("leave", "2026-09-15", "2026-09-22")


def test_single_all_day_sick_day():
    a = calendar_availability(_raw(summary="Sick", eventType="default",
                                   start="2026-09-15", end="2026-09-16"))
    assert (a["kind"], a["from"], a["to"]) == ("sick", "2026-09-15", "2026-09-15")


def test_timed_ooo_ending_at_midnight_ends_the_day_before():
    a = calendar_availability(_raw(start="2026-09-15T00:00:00+00:00",
                                   end="2026-09-18T00:00:00+00:00"))
    assert (a["from"], a["to"]) == ("2026-09-15", "2026-09-17")


def test_vacation_title_travel_title():
    assert calendar_availability(_raw(summary="Vacation 🌴", eventType="default",
                                      start="2026-10-01", end="2026-10-05"))["kind"] == "leave"
    assert calendar_availability(_raw(summary="Travelling - Mumbai", eventType="default",
                                      start="2026-10-01", end="2026-10-02"))["kind"] == "travel"


def test_ordinary_events_are_not_availability():
    assert calendar_availability(_raw(summary="Holiday party", eventType="default",
                                      start="2026-12-20", end="2026-12-21")) is None
    assert calendar_availability(_raw(summary="Leave policy review", eventType="default",
                                      start="2026-09-15", end="2026-09-16")) is None
    # a TIMED meeting that mentions leave is a meeting
    assert calendar_availability(_raw(summary="Leave planning", eventType="default")) is None
    assert calendar_availability(_raw(summary="Acme sync", eventType="default",
                                      start="2026-09-15", end="2026-09-16")) is None


def test_unattributable_blocks_are_skipped():
    # no self flag, and the organizer invited others → a shared event, not the organizer's leave
    assert calendar_availability(_raw(calendar_owner=None, summary="OOO", eventType="default",
                                      start="2026-09-15", end="2026-09-16",
                                      attendees=["team@acme.io", "anisha@acme.io"])) is None
    # a group / holiday calendar is not a person
    assert calendar_availability(_raw(
        calendar_owner=None, organizer="en.indian#holiday@group.v.calendar.google.com",
        summary="Holiday", eventType="default", start="2026-10-20", end="2026-10-21")) is None


def test_organizer_owns_a_personal_block_without_self_flag():
    a = calendar_availability(_raw(calendar_owner=None, summary="PTO", eventType="default",
                                   start="2026-09-15", end="2026-09-16", attendees=[]))
    assert a["person"] == "anisha@acme.io"


def test_cancelled_block_is_flagged_for_retirement():
    assert calendar_availability(_raw(status="cancelled"))["cancelled"] is True


def test_connector_carries_event_type_and_owner():
    conn = ComposioCalendarConnector.__new__(ComposioCalendarConnector)
    obj = conn._to_raw({
        "id": "ev1", "summary": "Out of office", "eventType": "outOfOffice",
        "start": {"dateTime": "2026-09-15T09:00:00Z"}, "end": {"dateTime": "2026-09-17T18:00:00Z"},
        "organizer": {"email": "anisha@acme.io", "self": True}, "updated": "2026-09-01T10:00:00Z",
        "status": "confirmed"})
    assert obj.raw["eventType"] == "outOfOffice"
    assert obj.raw["calendar_owner"] == "anisha@acme.io"
    assert calendar_availability(obj.raw)["person"] == "anisha@acme.io"
