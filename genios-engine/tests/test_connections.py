from __future__ import annotations

from genios_engine.capture.connections.store import InMemoryConnectionStore
from genios_engine.contracts.connection import Connection


def test_many_orgs_each_have_their_own_connection():
    store = InMemoryConnectionStore()
    # 30 startups, each its own org_id + composio_user_id — all in the store, not .env
    for i in range(30):
        store.add(Connection(org_id=f"org_{i}", composio_user_id=f"gmail_user_{i}"))

    active = store.list_active("gmail")
    assert len(active) == 30
    assert {c.org_id for c in active} == {f"org_{i}" for i in range(30)}
    # each carries its own Composio identity
    c5 = next(c for c in active if c.org_id == "org_5")
    assert c5.composio_user_id == "gmail_user_5"


def test_paused_connection_excluded():
    store = InMemoryConnectionStore()
    c = Connection(org_id="o", composio_user_id="u", status="paused")
    store.add(c)
    assert store.list_active() == []
