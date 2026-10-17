"""Layer 1 · a provider that says "no" must never read as a mailbox with nothing in it.

    pytest tests/capture/connectors/test_a_provider_refusal_is_never_an_empty_page.py -q

THE DEFECT. Composio reports a tool failure inside the envelope — `{"successful": false,
"error": …}` — instead of raising. The Gmail list call and the shared `ComposioExec` (Calendar,
Drive, HubSpot, Linear, Notion) handed that envelope on as data: no messages, no next page. That
is exactly what an exhausted provider returns, so `run_sync` filed the sweep as finished and empty
(`cursor_exhausted=True`, no error) and the coverage read called the window SUCCESS_EMPTY — an
expired login read as a quiet inbox, which is the benchmark's "unknown is not absent" failure
(the attachment fetch alone checked the flag, `composio.py` `GMAIL_GET_ATTACHMENT`).
"""
from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.unit

_REFUSAL = {"successful": False, "error": "Connected account is not active", "data": {}}


def _gmail(response: Any):
    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector(api_key="k", user_id="u")
    connector._execute = lambda slug, arguments: response  # type: ignore[method-assign]
    return connector


def _exec(response: Any):
    from genios_engine.capture.connectors.composio_base import ComposioExec

    x = ComposioExec(api_key="k", user_id="u")
    x._raw_execute = lambda slug, arguments: response  # type: ignore[method-assign]
    return x


def test_a_refused_gmail_list_raises_and_names_the_error():
    from genios_engine.capture.connectors.composio_base import ProviderRefused

    with pytest.raises(ProviderRefused, match="Connected account is not active"):
        _gmail(_REFUSAL).incremental_changes(None, 50)
    with pytest.raises(ProviderRefused):
        _gmail(_REFUSAL).initial_snapshot(None, 50)


def test_a_successful_empty_gmail_list_is_still_an_empty_page():
    """The negative control: a real empty answer stays an empty, exhausted page."""
    batch = _gmail({"successful": True, "data": {"messages": []}}).incremental_changes(None, 50)
    assert batch.objects == [] and batch.next_cursor is None


def test_the_shared_executor_raises_on_a_refusal_and_passes_data_through_otherwise():
    from genios_engine.capture.connectors.composio_base import ProviderRefused

    with pytest.raises(ProviderRefused, match="GOOGLECALENDAR_EVENTS_LIST"):
        _exec(_REFUSAL).execute("GOOGLECALENDAR_EVENTS_LIST", {})
    assert _exec({"successful": True, "data": {"items": [1]}}).execute("X", {}) == {"items": [1]}
    # An envelope without the flag is not a refusal — older shapes carry no `successful` at all.
    assert _exec({"data": {"items": []}}).execute("X", {}) == {"items": []}


def test_a_refused_calendar_list_raises():
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
    from genios_engine.capture.connectors.composio_base import ProviderRefused

    cal = ComposioCalendarConnector(api_key="k", user_id="u")
    cal._x._raw_execute = lambda slug, arguments: _REFUSAL  # type: ignore[method-assign]
    with pytest.raises(ProviderRefused):
        cal.incremental_changes(None, 50)


def test_a_refused_sweep_is_never_filed_as_finished():
    """END TO END through `run_sync`: the refusal is retried, then surfaces — the caller's ledger
    writes the run WITH its error — and the watermark does not move."""
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.connectors.composio_base import ProviderRefused
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    connector = _gmail(_REFUSAL)
    with pytest.raises(ProviderRefused):
        run_sync(connector, org_id="org_r", connection_id="con_r",
                 repo=InMemorySourceEventRepository(), source="gmail", fetch_retries=1,
                 fetch_backoff=0.0, _sleep=lambda s: None)


def test_a_poll_that_ran_out_of_pages_says_we_stopped():
    """An incremental run whose page budget ran out with a live cursor is truncated BY US — not
    `None`, which reads as "not applicable" (a webhook)."""
    from datetime import datetime, timezone

    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.connectors.base import RawObject, SourceBatch
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    class _Endless:
        source = "fake"

        def _page(self, cursor):
            n = int(cursor or 0)
            return SourceBatch(
                objects=[RawObject(source="fake", object_type="note", source_object_id=f"o{n}",
                                   occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                                   actor_email="a@example.com", raw={"snippet": f"p{n}"})],
                next_cursor=str(n + 1))

        def initial_snapshot(self, cursor=None, limit=100):
            return self._page(cursor)

        def incremental_changes(self, cursor=None, limit=100, since=None):
            return self._page(cursor)

        def fetch_content(self, object_ref):
            return {}

    summary = run_sync(_Endless(), org_id="org_t", connection_id="con_t",
                       repo=InMemorySourceEventRepository(), source="fake", max_pages=2,
                       respect_cadence=False)
    assert summary.cursor_exhausted is False
    assert summary.page_budget_spent is True
    assert summary.next_cursor == "2"
