"""GeniOS-012 U12-04 · the evidence fetchers read through the connection's own saved window.

    PYTHONPATH=. pytest -q tests/api/test_need_fetchers_use_the_saved_window.py

`api/routes._need_fetchers` built its Gmail connection with `config={}`, so when L2 asked for "the earlier
mail", the window fetcher searched the module default (60 days) even on a connection whose window an operator
had widened to 365 — the very mail the request was for. It now carries the stored `capture_scope`, the way
`_saved_connection_config` already made every backfill honour it.
"""
from __future__ import annotations

from genios_engine.api import routes
from genios_engine.capture.acquire import need_fetchers


def _built_connection(monkeypatch, saved: dict):
    seen: list = []
    monkeypatch.setattr(routes, "_saved_connection_config",
                        lambda org_id, source_type: dict(saved) if source_type == "gmail" else {})
    monkeypatch.setattr(routes, "make_connector_for", lambda conn: seen.append(conn) or object())

    def _make_fetchers(*, connector_for, sync):
        connector_for()
        return {}
    monkeypatch.setattr(need_fetchers, "make_fetchers", _make_fetchers)
    routes._need_fetchers("org_u12_04")
    [conn] = seen
    return conn


def test_the_fetcher_connection_carries_the_saved_window(monkeypatch):
    conn = _built_connection(monkeypatch, {"backfill_days": 365})
    assert conn.config.get("backfill_days") == 365
    assert conn.org_id == "org_u12_04" and conn.source_type == "gmail"


def test_with_nothing_saved_the_default_window_stands(monkeypatch):
    conn = _built_connection(monkeypatch, {})
    assert dict(conn.config or {}) == {}
