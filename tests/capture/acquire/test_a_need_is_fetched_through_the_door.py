"""GeniOS-008 L1 E2 · the evidence-need fetchers: armed only on purpose, through the capture door, and a
provider refusal is never "nothing found".

    pytest tests/capture/acquire/test_a_need_is_fetched_through_the_door.py -q
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.acquire import need_executor as NX
from genios_engine.capture.acquire import need_fetchers as NF
from genios_engine.capture.acquire.evidence_need import BACKFILL_WINDOW, FETCH_THREAD, execute
from genios_engine.capture.connectors.base import SourceBatch
from genios_engine.capture.connectors.composio_base import ProviderRefused
from genios_engine.contracts.evidence import EvidenceNeed

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def _need(subject="thread:th_123", **kw):
    return EvidenceNeed(need_id="l2need:x", org_id="org_x", trace_id="tr", question="was it sent?",
                        why_it_matters="then nothing is owed", subject_ref=subject, max_cost_usd=0.05, **kw)


class _Connector:
    _account = "acct_1"

    def __init__(self, result=None, objects=("m1",)):
        self.result = result if result is not None else {"successful": True, "data": {"messages": []}}
        self.objects = list(objects)
        self.calls = []

    def _execute(self, slug, args):
        self.calls.append((slug, args))
        return self.result

    def _fetch(self, *, max_results, query=None):
        self.calls.append(("GMAIL_FETCH_EMAILS", {"query": query, "max_results": max_results}))
        return self.result

    def _to_batch(self, result):
        return SourceBatch(objects=list(self.objects))


class _Summary:
    emitted, duplicate = 1, 0


def test_unarmed_the_executor_still_refuses(monkeypatch):
    monkeypatch.delenv(NF.FETCHERS_ENV, raising=False)
    NX.register_fetcher_factory(lambda org: {FETCH_THREAD: lambda n: {"source": "gmail"}})
    try:
        assert NX.build_fetchers("org_x") == {}
    finally:
        NX.register_fetcher_factory(None)


def test_armed_without_a_factory_wires_nothing(monkeypatch):
    monkeypatch.setenv(NF.FETCHERS_ENV, "on")
    NX.register_fetcher_factory(None)
    assert NX.build_fetchers("org_x") == {}


def test_armed_with_a_factory_wires_its_fetchers(monkeypatch):
    monkeypatch.setenv(NF.FETCHERS_ENV, "on")
    NX.register_fetcher_factory(lambda org: {FETCH_THREAD: "f"})
    try:
        assert NX.build_fetchers("org_x") == {FETCH_THREAD: "f"}
    finally:
        NX.register_fetcher_factory(None)


def test_the_routes_register_the_factory():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[3] / "genios_engine" / "api" / "routes.py").read_text()
    assert "register_fetcher_factory(_need_fetchers)" in src


def test_a_thread_is_fetched_by_its_id_and_carried_through_the_door():
    conn, carried = _Connector(), []
    fetchers = NF.make_fetchers(connector_for=lambda: conn, sync=lambda scoped: carried.append(scoped) or _Summary())
    found = fetchers[FETCH_THREAD](_need("thread:thread:th_123"))
    assert found["source"] == "gmail" and found["captured"] == 1
    slug, args = conn.calls[0]
    assert slug == NF.THREAD_SLUG and args["thread_id"] == "th_123" and args["connected_account_id"] == "acct_1"
    scoped = carried[0]
    assert scoped.incremental_changes().objects == ["m1"]
    assert scoped.incremental_changes().objects == []          # once — a second page is never the same batch


def test_an_empty_thread_is_nothing_found_not_an_error():
    fetchers = NF.make_fetchers(connector_for=lambda: _Connector(objects=()), sync=lambda s: _Summary())
    assert fetchers[FETCH_THREAD](_need()) is None


def test_a_provider_refusal_closes_the_need_with_its_reason_never_as_empty():
    refused = _Connector(result={"successful": False, "error": "rate limited"})
    fetchers = NF.make_fetchers(connector_for=lambda: refused, sync=lambda s: _Summary())
    with pytest.raises(ProviderRefused):
        fetchers[FETCH_THREAD](_need())
    outcome = execute(_need(), fetchers=fetchers, eval_time=NOW)
    assert outcome.state == "unavailable" and "found nothing" not in (outcome.reason or "")


def test_a_window_is_asked_in_gmails_own_words():
    conn = _Connector()
    fetchers = NF.make_fetchers(connector_for=lambda: conn, sync=lambda s: _Summary())
    need = _need(subject="signal:s1", window_from=datetime(2026, 10, 1, tzinfo=timezone.utc),
                 window_to=datetime(2026, 10, 8, tzinfo=timezone.utc))
    assert fetchers[BACKFILL_WINDOW](need)["kind"] == BACKFILL_WINDOW
    assert conn.calls[0][1]["query"] == "after:2026/10/01 before:2026/10/08"
