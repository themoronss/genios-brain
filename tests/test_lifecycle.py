"""The signal lifecycle. Before `capture/lifecycle.py` every signal ever captured stayed
equally current forever: a meeting that finished in March reached the reasoning engine as
live evidence beside this morning's email.

Expiry is decay, not deletion — the ledger row, the trace and the facts all survive.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.lifecycle import (ACTIVE, EXPIRED, NEW, SATISFIED,
                                             expires_at_for, is_expired)
from genios_engine.capture.pipeline import capture_event

_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _raw(source="gmail", object_type="email_message", occurred=_T0, kind=None, **raw):
    return RawObject(source=source, object_type=object_type, source_object_id="o1",
                     occurred_at=occurred, actor_email="priya@chat360.io",
                     actor_type="external_contact", internal_kind=kind,
                     raw={"body": "hello", "subject": "s", **raw})


def _event(**kw):
    return to_source_event(_raw(**kw), org_id="org_a", connection_id="c1")


# ── shelf life, per family ──────────────────────────────────────────────────────────
def test_an_email_decays_after_a_month():
    assert expires_at_for(_event()) == _T0 + timedelta(days=30)


def test_a_document_outlives_a_message():
    """A doc stays true far longer than a message — the horizons are per family, not one
    global constant, because 'still current' means different things for each."""
    doc = expires_at_for(_event(source="notion", object_type="page"))
    mail = expires_at_for(_event())
    assert doc is not None and mail is not None and doc > mail


def test_company_canon_never_expires():
    """A refund policy is true until the org writes down a different one — and that
    arrives as a supersede, not as a clock running out. Expiring canon would silently
    drain the organisation's own account of itself."""
    assert expires_at_for(_event(source="internal", object_type="policy", kind="policy")) is None


def test_a_meeting_expires_when_it_ends_not_on_a_family_default():
    end = "2026-08-02T11:00:00+00:00"
    got = expires_at_for(_event(source="gcal", object_type="calendar_event", end=end),
                         raw={"end": end})
    assert got == datetime(2026, 8, 3, 11, tzinfo=timezone.utc)      # end + 1 day grace


def test_a_meeting_with_only_a_start_still_gets_a_horizon_from_it():
    start = "2026-08-02T10:00:00+00:00"
    got = expires_at_for(_event(source="gcal", object_type="calendar_event", start=start),
                         raw={"start": start})
    assert got == datetime(2026, 8, 3, 10, tzinfo=timezone.utc)


def test_an_unparseable_date_falls_back_to_the_family_default_rather_than_none():
    got = expires_at_for(_event(source="gcal", object_type="calendar_event"),
                         raw={"end": "not-a-date"})
    assert got is not None


def test_is_expired_treats_never_as_not_expired():
    assert is_expired(None) is False
    assert is_expired(_T0, now=_T0 + timedelta(seconds=1)) is True
    assert is_expired(_T0, now=_T0 - timedelta(seconds=1)) is False


# ── the state machine ───────────────────────────────────────────────────────────────
def test_capture_stamps_new_and_a_horizon_on_the_emitted_signal():
    repo = InMemorySourceEventRepository()
    res = capture_event(_raw(), org_id="org_a", connection_id="c1", repo=repo)
    assert res.gated.signal_state == NEW
    assert res.gated.expires_at == _T0 + timedelta(days=30)


def test_the_sweep_expires_what_is_due_and_leaves_the_rest():
    repo = InMemorySourceEventRepository()
    old = _event(occurred=_T0 - timedelta(days=90))
    fresh = _event(occurred=_T0)
    for e in (old, fresh):
        e.expires_at = expires_at_for(e)
        e.dedup_key = f"{e.dedup_key}:{e.occurred_at.isoformat()}"   # distinct rows
        repo.add(e, outcome="emitted")

    moved = repo.expire_due(now=_T0)
    assert moved == 1
    assert old.signal_state == EXPIRED
    assert fresh.signal_state == NEW


def test_the_sweep_is_idempotent():
    repo = InMemorySourceEventRepository()
    e = _event(occurred=_T0 - timedelta(days=90))
    e.expires_at = expires_at_for(e)
    repo.add(e, outcome="emitted")
    assert repo.expire_due(now=_T0) == 1
    assert repo.expire_due(now=_T0) == 0            # second run changes nothing


def test_a_settled_signal_is_never_re_opened_by_the_sweep():
    """`satisfied` means something above confirmed the outcome. The clock must not
    overwrite a conclusion the reasoning layers reached."""
    repo = InMemorySourceEventRepository()
    e = _event(occurred=_T0 - timedelta(days=90))
    e.expires_at = expires_at_for(e)
    e.signal_state = SATISFIED
    repo.add(e, outcome="emitted")
    assert repo.expire_due(now=_T0) == 0
    assert e.signal_state == SATISFIED


def test_an_active_signal_can_still_expire():
    repo = InMemorySourceEventRepository()
    e = _event(occurred=_T0 - timedelta(days=90))
    e.expires_at = expires_at_for(e)
    e.signal_state = ACTIVE
    repo.add(e, outcome="emitted")
    assert repo.expire_due(now=_T0) == 1
    assert e.signal_state == EXPIRED


def test_canon_is_untouched_by_the_sweep_however_old_it_is():
    repo = InMemorySourceEventRepository()
    e = _event(source="internal", object_type="policy", kind="policy",
               occurred=_T0 - timedelta(days=3650))
    e.expires_at = expires_at_for(e)
    repo.add(e, outcome="emitted")
    assert repo.expire_due(now=_T0) == 0
    assert e.signal_state == NEW
