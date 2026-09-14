"""A backfilled event names a throwaway connection id; the re-read still finds the tenant's own.

    pytest tests/capture/test_reread_connection.py -q
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from genios_engine.api import routes as R

pytestmark = pytest.mark.unit

ORG = "org_a"


class _Store:
    def __init__(self, conns):
        self.conns = {c.connection_id: c for c in conns}

    def get(self, connection_id):
        return self.conns.get(connection_id)

    def list_active(self, source_type=None):
        return list(self.conns.values())


def _conn(cid, org=ORG, source="gmail"):
    return SimpleNamespace(connection_id=cid, org_id=org, source_type=source)


def _row(cid, source="gmail"):
    return SimpleNamespace(connection_id=cid, source=source)


@pytest.fixture
def store(monkeypatch):
    s = _Store([_conn(f"con_{ORG}_gmail"), _conn("con_seat", source="gcal"),
                _conn("con_other_org", org="org_b")])
    monkeypatch.setattr(R, "_connections", s)
    return s


def test_a_stored_connection_is_used_as_is(store):
    assert R._reread_connection(ORG, _row("con_seat", "gcal"), {}).connection_id == "con_seat"


def test_a_throwaway_backfill_id_falls_back_to_the_tenants_own_connection(store):
    assert R._reread_connection(ORG, _row("con_bc00df"), {}).connection_id == f"con_{ORG}_gmail"


def test_an_unnamed_source_falls_back_to_any_active_connection_of_the_tenant(store):
    assert R._reread_connection(ORG, _row("con_gone", "gcal"), {}).connection_id == "con_seat"


def test_another_tenants_connection_is_never_used(store):
    assert R._reread_connection(ORG, _row("con_other_org"), {}).connection_id == f"con_{ORG}_gmail"


def test_no_connection_for_the_source_is_a_skip(store):
    assert R._reread_connection(ORG, _row("con_x", "slack"), {}) is None


def test_the_re_read_publishes_in_batches_and_restores_each_one(store, monkeypatch):
    """60 unread emails → three batches, each set aside, captured, published, then restored."""
    from genios_engine.capture.landing import unread

    rows = [SimpleNamespace(event_id=f"evt_{i}", connection_id="con_bc00df", source="gmail")
            for i in range(60)]
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(R, "_graph", SimpleNamespace(engine=object()))
    monkeypatch.setattr(R, "_llm_over_daily_cap", lambda org: False)
    monkeypatch.setattr(R, "_push_wiring_for", lambda conn: "wiring")
    monkeypatch.setattr(R, "_l1_stores", lambda: None)
    monkeypatch.setattr(unread, "recover_orphans", lambda e, o: 0)
    monkeypatch.setattr(unread, "find_unread", lambda e, o, limit: rows)
    monkeypatch.setattr(unread, "to_raw_object", lambda row, key: row.event_id)
    monkeypatch.setattr(unread, "set_aside", lambda e, o, ids: calls.append(("aside", len(ids))))
    monkeypatch.setattr(unread, "restore", lambda e, o, ids: calls.append(("restore", len(ids))))
    monkeypatch.setattr(R, "ingest_pushed_objects", lambda objs, **kw: (
        calls.append(("ingest", len(objs))) or SimpleNamespace(
            results=[SimpleNamespace(outcome="emitted")] * len(objs))))
    monkeypatch.setattr(R, "finalize_l1", lambda sweep, **kw: calls.append(("publish", sweep.scanned)))

    assert R._reread_unread(ORG) == 60
    assert calls == [step for n in (25, 25, 10)
                     for step in (("aside", n), ("ingest", n), ("publish", n), ("restore", n))]
