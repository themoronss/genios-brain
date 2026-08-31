from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine


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
    #
    # psycopg (v3) auto-uses server-side PREPARED STATEMENTS. The TRANSACTION pooler (6543) gives
    # each transaction a different backend, so a statement prepared on one is gone on the next →
    # "prepared statement does not exist". Disabling them (prepare_threshold=None) is REQUIRED for
    # the transaction pooler and harmless on the session pooler, so we set it unconditionally — this
    # is the one code change needed to safely move DATABASE_URL from :5432 (session) to :6543.
    # Resilience over a slow/flaky link (e.g. a laptop reaching a remote Supabase region):
    # without TCP keepalives and timeouts, a silently-dropped connection makes libpq block on a
    # socket read FOREVER — the process sits at 0% CPU, no query active, looking "hung". These
    # connect_args make a dead connection surface as an error in seconds instead of never:
    #   keepalives*        — probe idle connections; drop-detect within ~30s
    #   tcp_user_timeout   — cap unacked in-flight sends (ms) so a mid-query death fails fast
    #   connect_timeout    — bound the initial connect
    #   statement_timeout  — no single server query can run unbounded (server-side, ms)
    # Every argument below is psycopg-specific. Passing them to any other driver is not a
    # degraded experience, it is a TypeError at connect time — which is why the migration
    # ledger's own test suite could not run against sqlite: `apply_migrations` accepts a URL,
    # and the first thing it did with a valid one was crash. Pooling arguments are equally
    # Postgres-shaped; SQLAlchemy's sqlite default pool is the right one there.
    if not url.startswith("postgresql"):
        return create_engine(url)

    # Sized to the pooler we are ACTUALLY pointed at, not to the one we used to use.
    #
    # The 8+4 budget above is the SESSION-pooler answer (15 concurrent clients, hard cap). The
    # deployment moved to the TRANSACTION pooler — the very thing the comment above recommends —
    # and nothing re-read the numbers, so the whole capture path kept throttling itself against a
    # limit that no longer exists. That is why "we already made this fast" and "it is slow again"
    # were both true: nobody regressed it, the calibration simply went stale where it could not
    # be seen. Deriving it from the port means it cannot go stale again.
    #
    # Transaction mode hands each TRANSACTION a backend and returns it immediately, so client
    # slots are not held for the life of a connection and a larger app-side pool is exactly what
    # it is built for.
    transaction_pooler = ":6543/" in url
    pool_size, overflow = (24, 12) if transaction_pooler else (8, 4)
    return create_engine(url, pool_pre_ping=True, pool_size=pool_size, max_overflow=overflow,
                         pool_recycle=1800, pool_timeout=15,
                         connect_args={
                             "prepare_threshold": None,
                             "connect_timeout": 10,
                             "keepalives": 1,
                             "keepalives_idle": 30,
                             "keepalives_interval": 10,
                             "keepalives_count": 5,
                             "tcp_user_timeout": 30000,
                             "options": "-c statement_timeout=120000",
                         })
