"""L1.3.8-U1 — the wiring, which is the part that decides whether any of this ever runs.

A resolver nothing calls closes no gap. The drain rides the existing heartbeat (a new Celery
periodic task would spend the quota-limited Upstash broker on a pass that is cheap and idempotent
here), and the admin surface is two routes. What is tested here is the seam between them and the
engine: the failure modes of resolving a connector, and the refusal to pretend in a deployment
that has no database.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.api import routes
from genios_engine.capture.parked.refetch_policy import ParkStatus, RefetchCandidate

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


def _candidate(connection_id="conn_1", org_id="org_1") -> RefetchCandidate:
    return RefetchCandidate(
        event_id="evt_1", org_id=org_id, reason_code="DOC-05",
        status=ParkStatus.PENDING.value, object_type="email_attachment", source="gmail",
        source_object_id="m1::a1", parent_object_id="m1", connection_id=connection_id,
        parked_at=NOW)


class _Conn:
    def __init__(self, org_id="org_1"):
        self.org_id = org_id
        self.connection_id = "conn_1"
        self.source_type = "gmail"


def test_an_unknown_connection_resolves_to_no_connector(monkeypatch):
    monkeypatch.setattr(routes._connections, "get", lambda _cid: None)
    assert routes._attachment_connector_for(_candidate()) is None


def test_a_connection_belonging_to_another_org_resolves_to_no_connector(monkeypatch):
    """Tenant isolation at the one place a refetch could cross it: the bytes are fetched with
    somebody's credentials, so the connection has to belong to the org that parked the event."""
    monkeypatch.setattr(routes._connections, "get", lambda _cid: _Conn(org_id="org_other"))
    assert routes._attachment_connector_for(_candidate()) is None


def test_a_connector_that_cannot_fetch_attachments_resolves_to_none(monkeypatch):
    """Better a transient miss than an AttributeError classified as a retryable provider error
    and burning all five rungs of the ladder."""
    class _NoFetch:
        pass

    monkeypatch.setattr(routes._connections, "get", lambda _cid: _Conn())
    monkeypatch.setattr(routes, "make_connector_for", lambda _c: _NoFetch())
    assert routes._attachment_connector_for(_candidate()) is None


def test_a_gmail_connector_is_accepted(monkeypatch):
    class _Gmail:
        def fetch_attachment(self, message_id, attachment_id):
            return b"bytes"

    connector = _Gmail()
    monkeypatch.setattr(routes._connections, "get", lambda _cid: _Conn())
    monkeypatch.setattr(routes, "make_connector_for", lambda _c: connector)
    assert routes._attachment_connector_for(_candidate()) is connector


def test_the_heartbeat_pass_says_it_skipped_rather_than_pretending(monkeypatch):
    """With no database there is no queue, and reporting zeros would read as an empty backlog."""
    monkeypatch.setattr(routes, "_attachment_refetch_queue", lambda: None)
    assert routes._drain_attachment_refetch(NOW) == {"skipped": "no database"}


def test_the_heartbeat_pass_reports_what_the_drain_did(monkeypatch):
    from genios_engine.capture.parked.refetch import InMemoryRefetchQueue

    queue = InMemoryRefetchQueue()
    monkeypatch.setattr(routes, "_attachment_refetch_queue", lambda: queue)
    monkeypatch.setattr(routes, "_attachment_connector_for", lambda _c: None)
    assert routes._drain_attachment_refetch(NOW) == {
        "claimed": 0, "recovered": 0, "dead_lettered": 0, "retry_scheduled": 0,
        "text_chars_recovered": 0, "failures_by_kind": {}}


def test_the_requeue_route_refuses_when_there_is_no_database(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(routes, "_attachment_refetch_queue", lambda: None)
    with pytest.raises(HTTPException) as exc:
        routes.requeue_attachment_dead_letters(org_id="org_1")
    assert exc.value.status_code == 503


def test_the_status_route_says_it_is_unavailable_rather_than_empty(monkeypatch):
    monkeypatch.setattr(routes, "_attachment_refetch_queue", lambda: None)
    body = routes.attachment_refetch_status(org_id="org_1")
    assert body["available"] is False and body["dead_letters"] == []
