"""Screen promoter — the pure policy (hermetic). Real-Postgres behaviour: test_screen_promoter_pg."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.source_registry import catalog, descriptor_of, is_mutable, offer_of
from genios_engine.platform import screen_promoter as SP

pytestmark = pytest.mark.unit
NOW = datetime(2026, 9, 17, 20, 0, tzinfo=timezone.utc)       # 01:30 IST on the 18th


def _d(attempts=1, app="linkedin"):
    return SP.Delta("o", "dev", "k", 1, "s", app, "t", b"", None, NOW, attempts=attempts)


def test_next_local_midnight_is_the_org_zone_not_utc():
    assert SP.next_local_midnight(NOW, "Asia/Kolkata") == \
        datetime(2026, 9, 18, 18, 30, tzinfo=timezone.utc)
    assert SP.local_day(NOW, "Asia/Kolkata").isoformat() == "2026-09-18"
    assert SP.next_local_midnight(NOW, "UTC") == datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert SP.next_local_midnight(NOW, "Not/AZone") == datetime(2026, 9, 18, tzinfo=timezone.utc)


def test_failures_back_off_then_park():
    o = SP.failure_outcome(_d(attempts=1), "boom", now=NOW)
    assert o.status == "held" and o.not_before == NOW + timedelta(seconds=30)
    assert SP.failure_outcome(_d(attempts=3), "boom", now=NOW).not_before == \
        NOW + timedelta(seconds=120)
    assert SP.failure_outcome(_d(attempts=SP.MAX_ATTEMPTS), "boom", now=NOW).status == "parked"


def test_generic_detection():
    assert _d(app="generic").generic and _d(app="web").generic and not _d().generic


def test_alias_candidates_are_emails_profiles_and_full_names():
    c = SP.alias_candidates({
        "participants": [{"name": "Priya Shah", "email": "Priya@Acme.test",
                          "linkedin_url": "https://linkedin.com/in/PriyaS/"},
                         {"name": "Me", "self": True}],
        "messages": [{"sender": "Bo", "text": "cc ana@vendor.test please"}]})
    assert ("email", "priya@acme.test") in c and ("email", "ana@vendor.test") in c
    assert ("linkedin_url", "https://www.linkedin.com/in/priyas") in c
    assert ("person_name", "priya shah") in c
    assert ("person_name", "bo") not in c                   # a single name is not an identity


def test_screen_session_is_registered_mutable_and_never_offered():
    d = descriptor_of("screen_session")
    assert d is not None and d.family == "communication" and not d.buildable
    assert d.capability is None and d.version_field == "message_watermark"
    assert set(d.object_types) == {"screen_chat_thread", "screen_email_thread", "screen_doc"}
    assert is_mutable("screen_session")
    assert offer_of("screen_session") is None
    assert "screen_session" not in {o.source for o in catalog()}
