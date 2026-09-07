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
# THE TEST PROCESS MUST NOT BE ABLE TO REACH A REAL MODEL EITHER, AND FOR THE SAME REASON.
#
# The block above pins the DATABASE. It does not pin the MODEL, and `Settings.use_real_llm` is
# `bool(anthropic_api_key)` — which `.env` sets on every developer machine. `l1_llm_gate`
# defaults to True, so `platform/wiring.make_relevance_classifier` builds a real
# `LLMRelevanceClassifier(LLMClient(api_key=...))`, and EVERY `pg`-marked test that drives
# `api/routes._sync_connection` therefore made billed Anthropic calls — one per ambiguous event,
# on a 96-message corpus, on every run. The capture tree's `_hermetic_by_default` socket guard
# cannot catch it: `pg` and `llm` are exactly the markers it stands down for.
#
# Cleared here rather than monkeypatched in a fixture, for the reason the database block gives:
# application code constructs its own `Settings` in places a fixture cannot see, and
# pydantic-settings reads the environment at construction. A test that genuinely wants a model
# sets the key itself and carries the `llm` marker.
os.environ["GENIOS_ANTHROPIC_API_KEY"] = ""

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


# THE SCRATCH ORG IS SEEDED AT IMPORT, BESIDE THE MIGRATIONS — not by a fixture.
#
# `_seed_scratch_org` used to run only inside `live_test_database_url()`, so the row existed only
# once some test had asked for the `live_db_url` fixture. Six real-Postgres tests
# (`tests/capture/coverage/*`, `tests/capture/test_semantic_activation.py`) read
# GENIOS_TEST_DATABASE_URL straight out of the environment and name `org_scratch_tests` in a
# comment that says "seeded by tests/conftest.py" — they depend on no fixture at all. In file
# order they run BEFORE anything that pulls `live_db_url`, so on a fresh scratch database the org
# did not exist yet and every one of them died on a foreign key:
#
#     ForeignKeyViolation: insert or update on table "l1_semantic_activation" violates foreign
#     key constraint "l1_semantic_activation_org_cascade_fk"
#     DETAIL: Key (org_id)=(org_scratch_tests) is not present in table "orgs".
#
# The row is part of the SCHEMA these tests were written against, exactly as the migrations are,
# so it is created in the same place and on the same terms. Idempotent (`on conflict do nothing`),
# and it does nothing at all without GENIOS_TEST_DATABASE_URL.
if os.environ.get("GENIOS_TEST_DATABASE_URL"):
    _seed_scratch_org(os.environ["GENIOS_TEST_DATABASE_URL"])
    _PREPARED_URLS.add(os.environ["GENIOS_TEST_DATABASE_URL"])


@pytest.fixture
def l1_pending():
    """Declares a Layer 1 v2 acceptance gate that cannot be built yet, and SKIPS it by naming
    the wave that will.

    The gates in `01-Layer-1-Plan/09-Build-Order-and-Acceptance.md` are commands, not
    aspirations: `pytest tests/capture/validate -q`, `pytest tests/capture/esqe -q`. Half of
    those paths did not exist, so every one of them failed with pytest's usage error — "file or
    directory not found" — which is the same red as a genuinely broken gate and tells the reader
    nothing about which of the two it is. The tree exists from day one so that a gate command
    always RUNS, and what it reports is the honest state: skipped, because W5 has not landed.

    The reason string carries the wave, the gate id and the modules that fill it, because a
    bare "not implemented" in a suite of 180 files is indistinguishable from a test somebody
    disabled to make CI green. A skip is not a pass — the plan says so in those words — so these
    are counted, not ignored: `pytest tests/capture -q` printing 14 skipped IS the build's
    progress bar, and the wave that lands the code deletes the placeholder and writes the gate.

    Lives here rather than in `tests/capture/conftest.py` because tests/contracts and
    tests/golden/l1 need it too, and `tests/` is the only conftest all three inherit from.
    """
    def _pending(wave: str, gate: str, builds: str) -> None:
        pytest.skip(f"{gate} pending — {wave} has not landed ({builds}). The wave that builds "
                    f"it replaces this placeholder with the real gate.")
    return _pending


@pytest.fixture
def l2_pending():
    """Declares a Layer 2 v2 acceptance gate that cannot be built yet, and SKIPS it by naming
    the wave that will.

    Same mechanism and same reasoning as `tests/conftest.py::l1_pending` — the gates in
    `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` are COMMANDS (`pytest
    tests/context/analytic/test_trend.py -q`), so a path that does not exist makes the gate
    fail with pytest's usage error, which is the same red as a genuinely broken gate and tells
    the reader nothing about which of the two it is.

    A separate fixture from `l1_pending` rather than a reused one, because the wave vocabulary
    is different and that difference is load-bearing: Layer 1 counts **W**0-W10 and Layer 2
    counts **X**0-X8, the two run in parallel (doc 09: "X0 through X4 can be built while Layer
    1 is still in progress"), and a skip reason that said "W1" in the context tree would send
    the reader to the wrong build order. The signature carries the L2 gate id (H0-H8) for the
    same reason.

    A skip is not a pass. `pytest tests/context -q` printing N skipped IS Layer 2's progress
    bar, and the wave that lands the code DELETES the placeholder and writes the real gate in
    its place — it does not add a passing test beside it.
    """
    def _pending(wave: str, gate: str, builds: str) -> None:
        pytest.skip(f"{gate} pending — {wave} has not landed ({builds}). The wave that builds "
                    f"it replaces this placeholder with the real gate.")
    return _pending
