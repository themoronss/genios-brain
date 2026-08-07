from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event

# A vendor invoice/receipt routinely arrives from noreply@ or with a List-Unsubscribe header — the
# noise gate used to hard-drop it on those bulk signals, silently losing the invoice. Now a message
# carrying a real attachment survives those signals (relevance/L2 decides); without one it still drops.


def _mail(*, has_attachment: bool, sender: str = "noreply@vendor.com") -> RawObject:
    return RawObject(source="gmail", object_type="email", source_object_id="n1",
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_type="external_contact", actor_email=sender,
                     raw={"body": "Your invoice is attached.", "subject": "Invoice #123",
                          "headers": {"List-Unsubscribe": "<mailto:u@vendor.com>"},
                          "has_attachment": has_attachment})


def _capture(raw: RawObject):
    return capture_event(raw, org_id="o", connection_id="c", repo=InMemorySourceEventRepository())


def test_noreply_with_attachment_is_not_dropped():
    res = _capture(_mail(has_attachment=True))
    assert res.outcome != "dropped"          # invoice PDF survives → routed to L2


def test_noreply_without_attachment_still_drops():
    res = _capture(_mail(has_attachment=False))
    assert res.outcome == "dropped"          # plain bulk/no-reply mail is still noise
