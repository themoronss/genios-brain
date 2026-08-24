"""Clone one org's connections into a NEW org (additive INSERT only — deletes nothing), so we can
backfill the same mailbox into a clean namespace and verify the new code without touching real data."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from genios_engine.capture.connections.store import Connection
from genios_engine.platform.wiring import make_connection_store

SRC = sys.argv[1] if len(sys.argv) > 1 else "org_moronss"
DST = sys.argv[2] if len(sys.argv) > 2 else "org_verify_moronss"

store = make_connection_store()
srcs = [c for c in store.list_active() if c.org_id == SRC]
if not srcs:
    print(f"no active connections on {SRC}"); sys.exit(1)
for c in srcs:
    store.add(Connection(
        connection_id=f"con_verify_{c.source_type}", org_id=DST,
        provider=c.provider, source_type=c.source_type,
        composio_user_id=c.composio_user_id, config=c.config,
        status="connected", created_at=datetime.now(timezone.utc)))
    print(f"cloned {c.source_type}  {SRC} -> {DST}")
print("done")
