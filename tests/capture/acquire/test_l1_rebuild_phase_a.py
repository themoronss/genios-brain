"""L1 rebuild Phase A — the sync doors (`api/routes.py`).

A1  every door that hands a connector to `run_sync` / `backfill_drain` gives it the SAME
    classifier the pipeline gates with, so every door takes the snippet-first fast path.
A3  the onboarding backfill drains several pages per `run_sync` call (the condition for its
    prefetch) while `max_rounds` stays a PAGE budget — the ~5000-mail ceiling and the checkpoint's
    page count do not move.
A4  inside the scheduler's sweep a connection that is not due is skipped BEFORE its per-connection
    setup (coverage declaration, org baseline, lanes) is built.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
from genios_engine.capture.acquire.sync_runner import scheduled_sweep
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.connection import Connection


# ── A1 · the call sites ──────────────────────────────────────────────────────────────────────

def _door_calls():
    from genios_engine.api import routes
    tree = ast.parse(inspect.getsource(routes))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("run_sync", "backfill_drain") and node.args):
            continue
        first = node.args[0]
        if (isinstance(first, ast.Call) and isinstance(first.func, ast.Name)
                and first.func.id == "make_connector_for"):
            yield node, first


def test_every_door_hands_its_classifier_to_the_connector():
    doors = list(_door_calls())
    assert len(doors) >= 4, "the sweep, manual sync, /ingest/all and /backfill doors"
    for outer, inner in doors:
        given = {k.arg: k.value for k in inner.keywords}
        assert "relevance" in given, (
            f"line {inner.lineno}: make_connector_for(...) without relevance= — this door "
            "full-fetches every message")
        passed = {k.arg: k.value for k in outer.keywords}.get("relevance")
        assert passed is not None and ast.dump(passed) == ast.dump(given["relevance"]), (
            f"line {outer.lineno}: the connector and the pipeline must hold the SAME classifier "
            "(the pipeline reuses the verdicts the connector primed)")


# ── A3 · onboarding pages per round ──────────────────────────────────────────────────────────

def test_onboarding_drains_several_pages_per_call_within_the_page_budget(monkeypatch):
    from genios_engine.api import routes

    calls: list[int] = []

    def fake_run_sync(connector, **kw):
        calls.append(kw["max_pages"])
        return SimpleNamespace(scanned=25 * kw["max_pages"], emitted=0, next_cursor="more")

    monkeypatch.setattr(routes, "run_sync", fake_run_sync)
    monkeypatch.setattr(routes, "_BACKFILL_PAGES_PER_ROUND", 4)
    monkeypatch.setattr(routes, "_saved_connection_config", lambda *a, **kw: {})
    for name in ("make_relevance_classifier", "make_connector_for",
                 "_coverage_fn_for", "_esqe_stage_for", "_semantic_lane_for",
                 "_structured_lane_for", "_mailbox_owner_for", "_sender_resolver_for"):
        monkeypatch.setattr(routes, name, lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_source_count", lambda *a, **kw: 0)
    saved: list[int] = []

    scanned, _emitted, capped = routes._backfill_one_source(
        "org_a", "gmail", 25, max_rounds=10, on_cursor=lambda c, rounds: saved.append(rounds))

    assert calls == [4, 4, 2], "prefetch needs >1 page per call; the budget is still 10 pages"
    assert saved == [4, 8, 10], "the checkpoint keeps counting PAGES, so a resume stays exact"
    assert scanned == 250 and capped is True


# ── A4 · not due → nothing built ─────────────────────────────────────────────────────────────

class _Store:
    def __init__(self, *conns):
        self._c = list(conns)

    def list_active(self, source_type=None):
        return list(self._c)

    def get(self, cid):
        return next((c for c in self._c if c.connection_id == cid), None)


class _Mailbox:
    source = "gmail"

    def __init__(self):
        self.fetches = 0

    def incremental_changes(self, cursor, limit, since=None):
        from genios_engine.capture.connectors.base import SourceBatch
        self.fetches += 1
        return SourceBatch(objects=[], next_cursor=None)


def test_a_connection_that_is_not_due_builds_no_setup(monkeypatch):
    from genios_engine.api import routes

    conn = Connection(org_id="org_q", connection_id="con_q", source_type="gmail",
                      composio_user_id="org_q")
    cursors = InMemoryCursorStore(clock=lambda: datetime.now(timezone.utc) - timedelta(minutes=1))
    cursors.save("org_q", "con_q", "gmail", cursor=None, watermark=None)   # polled a minute ago
    built: list[str] = []

    monkeypatch.setattr(routes, "_connections", _Store(conn))
    monkeypatch.setattr(routes, "_cursors", cursors)
    monkeypatch.setattr(routes, "_repo", InMemorySourceEventRepository())
    for name in ("_parked", "_trace_repo", "_payload_store", "_prepared_store", "_documents",
                 "_graph"):
        monkeypatch.setattr(routes, name, None)
    box = _Mailbox()
    monkeypatch.setattr(routes, "make_connector_for", lambda c, **_: box)
    monkeypatch.setattr(routes, "make_relevance_classifier", lambda *a, **kw: None)
    for name in ("_coverage_fn_for", "_esqe_stage_for", "_semantic_lane_for"):
        monkeypatch.setattr(routes, name, lambda *a, _n=name, **kw: built.append(_n))
    for name in ("_structured_lane_for", "_sender_resolver_for", "_run_ledger", "_run_l2"):
        monkeypatch.setattr(routes, name, lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_semantic_activated_orgs", lambda *a, **kw: frozenset())

    with scheduled_sweep():
        res = routes.run_sync_sweep()

    assert res["l1_skipped_not_due"] == 1
    assert box.fetches == 0
    assert built == [], f"setup was built for a connection that is not due: {built}"
