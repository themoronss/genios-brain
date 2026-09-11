"""The Sync backfill honours the window saved on the connection.

`_backfill_one_source` and `_backfill_full` used to build their connection with `config={}`, so a
connection's `backfill_days` was never read on the path a user's Sync actually takes and every
first Sync used the module default. These pin the read the backfills now go through.

    pytest tests/capture/connectors/test_backfill_reads_saved_window.py -q
"""
from __future__ import annotations

from genios_engine.api import routes
from genios_engine.capture.connections.store import InMemoryConnectionStore
from genios_engine.capture.connectors.backfill import (DEFAULT_BACKFILL_DAYS,
                                                       backfill_window_for)
from genios_engine.contracts.connection import Connection

ORG = "org_bf_saved"


def _store(*conns: Connection) -> InMemoryConnectionStore:
    store = InMemoryConnectionStore()
    for c in conns:
        store.add(c)
    return store


def test_the_saved_window_is_read_by_the_deterministic_connection_id(monkeypatch):
    saved = Connection(connection_id=f"con_{ORG}_gcal", org_id=ORG, composio_user_id=ORG,
                       source_type="gcal", status="connected", config={"backfill_days": 30})
    monkeypatch.setattr(routes, "_connections", _store(saved))
    config = routes._saved_connection_config(ORG, "gcal")
    assert config == {"backfill_days": 30}
    rebuilt = Connection(org_id=ORG, composio_user_id=ORG, source_type="gcal", config=config)
    assert backfill_window_for(rebuilt).days == 30


def test_a_connection_under_another_id_is_found_by_org_and_source(monkeypatch):
    saved = Connection(connection_id="con_random", org_id=ORG, composio_user_id=ORG,
                       source_type="gmail", status="connected", config={"backfill_days": 45})
    other = Connection(connection_id="con_other", org_id="org_someone_else",
                       composio_user_id="org_someone_else", source_type="gmail",
                       status="connected", config={"backfill_days": 900})
    monkeypatch.setattr(routes, "_connections", _store(other, saved))
    assert routes._saved_connection_config(ORG, "gmail") == {"backfill_days": 45}


def test_nothing_saved_falls_back_to_the_two_month_default(monkeypatch):
    monkeypatch.setattr(routes, "_connections", _store())
    config = routes._saved_connection_config(ORG, "gmail")
    assert config == {}
    rebuilt = Connection(org_id=ORG, composio_user_id=ORG, source_type="gmail", config=config)
    assert backfill_window_for(rebuilt).days == DEFAULT_BACKFILL_DAYS == 60


def test_an_unreadable_store_never_blocks_the_sync(monkeypatch):
    class Broken:
        def get(self, _id):
            raise RuntimeError("store down")

        def list_active(self, _source=None):
            raise RuntimeError("store down")

    monkeypatch.setattr(routes, "_connections", Broken())
    assert routes._saved_connection_config(ORG, "gmail") == {}
