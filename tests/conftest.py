"""Hermetic test environment. Tests must pass on a fresh clone with no .env — CI has no
secrets. Anything a test needs from Settings is set HERE, deterministically, before the
lru_cached get_settings() is first materialized."""
from __future__ import annotations

import os

import pytest

# Fixed, well-formed Fernet key (test-only — never a real secret). Set at import time so
# even module-level get_settings() calls in application code see it.
_TEST_FERNET_KEY = "sxpepd0Y2jFCXW0Vjbb-EK_dQ9Yv9keeVdOOoNTk0eE="
os.environ.setdefault("GENIOS_CRYPTO_KEY", _TEST_FERNET_KEY)


# THE TEST PROCESS MUST NOT BE ABLE TO REACH PRODUCTION AT ALL.
#
# `.env` is loaded by `SettingsConfigDict(env_file=".env")`, so on any developer machine
# `get_settings().database_url` is the production Supabase URL. Test code then reaches it without
# ever naming it: `make_registry()` with no argument resolves its URL from global settings and
# REGISTERS EVERY PACK IN `BUILTIN_PACKS` into whatever it finds. That is how a draft `admin@1.0.0`
# reached production's `pack_registry`, and nine test modules do it at import time — they failed at
# collection the day the project went read-only, which is the only reason anyone noticed.
#
# Setting GENIOS_DATABASE_URL here, before the lru_cached `get_settings()` is first materialized,
# makes the whole question moot for every seam at once — the `conn` fixtures, `make_registry()`,
# and any future code that asks settings for a database:
#
#   * with GENIOS_TEST_DATABASE_URL set, the scratch database IS the configured database, so tests
#     that want to write can write, against a database that is theirs;
#   * without it, the configured database is empty — exactly the state CI has always run in, where
#     these tests skip.
#
# `os.environ` rather than a settings monkeypatch because pydantic-settings reads the environment
# at construction, and application code constructs its own Settings in places a fixture cannot see.
# The schema is applied HERE, at conftest import, and not in the `pg_store` fixture alone: the
# same nine modules call `make_registry()` while pytest is still COLLECTING, which is before any
# fixture has run. Pointing them at an empty scratch database only trades "wrote packs into
# production" for "relation pack_registry does not exist". Migrations are idempotent, so paying for
# them once at import costs a second and removes the ordering question entirely.
if os.environ.get("GENIOS_TEST_DATABASE_URL"):
    os.environ["GENIOS_DATABASE_URL"] = os.environ["GENIOS_TEST_DATABASE_URL"]
    from genios_engine.platform.migrate import apply_migrations as _apply

    _apply(database_url=os.environ["GENIOS_TEST_DATABASE_URL"])
else:
    os.environ["GENIOS_DATABASE_URL"] = ""


@pytest.fixture(autouse=True, scope="session")
def _settings_env():
    """Clear the settings cache once so the env above is what every test observes."""
    from genios_engine.platform.config import get_settings
    get_settings.cache_clear()
    yield


@pytest.fixture(scope="session")
def pg_store():
    """A real-Postgres GraphStore for BEHAVIOURAL L2 tests (migrations applied). Set
    GENIOS_TEST_DATABASE_URL (a local / docker-compose Postgres) to enable; without it these tests
    SKIP, so the hermetic suite still passes on a fresh clone with no DB. The store is constructed
    DIRECTLY from the URL — no global settings/env mutation — so hermetic tests are never touched.
    This is the seam that turns the L2 SQL from "never executed" into continuously verified."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L2 tests skipped")
    from genios_engine.context.graph_store import GraphStore
    return GraphStore(url)          # schema applied at conftest import; apply_migrations is idempotent


@pytest.fixture(scope="session")
def live_db_url():
    """Injected into every transaction-scoped `conn` fixture. A fixture rather than an import
    because `tests/` is not a package — and because making the target a declared dependency is
    what stops the next such fixture from silently reaching for production again."""
    return live_test_database_url()


_PREPARED_URLS: set[str] = set()


def live_test_database_url():
    """The URL the transaction-scoped `conn` fixtures may open a transaction against.

    GENIOS_TEST_DATABASE_URL WINS over the configured `database_url`, and that ordering is the
    entire point of this function. Those fixtures were written as "live PostgreSQL, rolled back",
    and on a developer machine with a real .env the live PostgreSQL they found was PRODUCTION.
    Rolling back at the end does not make that safe:

      * for the length of the test the transaction holds real row and tuple locks on a paying
        tenant's `execution_outcomes`, `learning_runs` and `delivery_*` tables, so a sync running
        at the same moment queues behind a test;
      * a pytest process killed mid-test — a CI timeout, a ^C, an agent harness that backgrounds
        a slow command — never reaches the rollback, and the connection stays `idle in
        transaction` holding those locks. Supabase runs with
        `idle_in_transaction_session_timeout = 0`, so nothing ever reclaims it. One such leak
        blocked this suite for hours: every later run's INSERT waited on a transaction id that
        belonged to a dead process.

    Pointing them at the scratch database costs nothing — they assert on rows they seeded
    themselves — and removes a class of production incident that only shows up under the exact
    conditions (slow machine, interrupted run) where nobody is watching.

    There is deliberately NO fallback to `get_settings().database_url`. These tests seed every row
    they assert on, so production offers them nothing a scratch database does not — it was only
    ever the database that happened to be reachable. Without GENIOS_TEST_DATABASE_URL they skip,
    which is the same contract `pg_store` already has, and the same answer CI already gives.
    """
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        return None
    if url not in _PREPARED_URLS:
        from genios_engine.platform.migrate import apply_migrations
        apply_migrations(database_url=url)
        _seed_scratch_org(url)
        _PREPARED_URLS.add(url)
    return url


def _seed_scratch_org(url: str) -> None:
    """These fixtures start with `select id from orgs limit 1` and skip when it is empty. On a
    production database that always found a real tenant; on a fresh scratch database it finds
    nothing, and nine files of coverage would quietly become nine files of skips. Seed one org so
    the guard passes for the right reason. NOT-NULL columns are discovered rather than listed, so
    a later migration adding one does not turn these tests into skips again."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    with get_engine(url).begin() as conn:
        if conn.execute(text("select id from orgs limit 1")).scalar():
            return
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": "org_scratch_tests"}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb")
                                   else "scratch")
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                          "on conflict (id) do nothing"), vals)
