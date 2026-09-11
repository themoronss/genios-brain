"""All 50 pilot events called external organisers staff; membership must decide."""
import pytest

from genios_engine.capture.connectors.calendar import ComposioCalendarConnector


def _event(email):
    return {"id": "calendar-1", "start": {"dateTime": "2026-08-11T10:00:00Z"},
            "organizer": {"email": email}, "updated": "2026-08-01T10:00:00Z"}


@pytest.mark.parametrize("email, expected", [
    ("theresa.hoffmann@antler.co", "external_contact"),
    (" OWNER@EXAMPLE.COM ", "internal_user"),
    ("seat@example.com", "internal_user"),
    (None, "external_contact"),
])
def test_calendar_organiser_membership_comes_from_the_tenant_identity_set(email, expected):
    connector = ComposioCalendarConnector(api_key="fixture", user_id="fixture",
        internal_emails=frozenset({"Owner@Example.com", "seat@example.com"}))
    raw = connector._to_raw(_event(email))
    assert raw.actor_type == expected
    assert raw.actor_email == email
    assert raw.watermark_at.isoformat() == "2026-08-01T10:00:00+00:00"


def test_a_known_empty_identity_set_does_not_turn_an_external_organiser_into_staff():
    connector = ComposioCalendarConnector(api_key="fixture", user_id="fixture",
                                         internal_emails=frozenset())
    assert connector._to_raw(_event("external@example.net")).actor_type == "external_contact"


def test_an_unavailable_refinement_keeps_the_original_connector_behaviour():
    connector = ComposioCalendarConnector(api_key="fixture", user_id="fixture")
    assert connector._to_raw(_event("external@example.net")).actor_type == "internal_user"


def test_webhook_and_poll_classify_the_same_organiser_identically():
    connector = ComposioCalendarConnector(api_key="fixture", user_id="fixture",
                                         internal_emails=frozenset({"owner@example.com"}))
    event = _event("external@example.net")
    assert connector.webhook_objects({"event": event})[0] == connector._to_batch(
        {"items": [event]}).objects[0]
