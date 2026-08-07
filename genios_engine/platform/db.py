from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text


@lru_cache
def get_engine(database_url: str) -> Engine:
    """One pooled SQLAlchemy engine for the process. Supabase Postgres via psycopg.
    pool_pre_ping survives Supabase idle-connection drops."""
    url = database_url
    # normalize the Supabase URI to the psycopg (v3) driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    # Connection budget: Supabase's SESSION pooler caps this project at 15 concurrent client
    # connections (FATAL EMAXCONNSESSION beyond that). Every app connection holds one slot, so the
    # WHOLE engine must stay comfortably under 15 — the old pool_size=12+overflow=8=20 blew past it
    # under load (8 L2 workers + per-request verify_bearer + status polls) and 500'd every request.
    # 8+4=12 leaves headroom for other clients (migrations, a psql session). If more throughput is
    # needed, move DATABASE_URL to the TRANSACTION pooler (port 6543) which multiplexes many clients.
    # pool_timeout: fast-fail (15s) instead of the 30s default so a saturated pool errors clearly.
    return create_engine(url, pool_pre_ping=True, pool_size=8, max_overflow=4,
                         pool_recycle=1800, pool_timeout=15)


def lock_tenant_for_mutation(conn, org_id: str) -> None:
    """Hold the tenant root before locking or writing any tenant-owned row.

    Account reset/deletion takes the same ``orgs`` row ``FOR UPDATE`` before it walks child
    tables.  Every transaction that can create or mutate a child row must therefore take this
    compatible root lock first.  Besides preventing post-erasure resurrection, the common order
    removes the graph/policy/object-to-org foreign-key deadlocks that otherwise appear when an
    erasure and a normal write overlap.
    """
    held = conn.execute(
        text("select id from orgs where id=:o for share"), {"o": org_id}).first()
    if held is None:
        raise LookupError("organization not found")


__all__ = ["get_engine", "lock_tenant_for_mutation"]
