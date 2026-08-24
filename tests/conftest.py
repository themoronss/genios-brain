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
    from genios_engine.platform.migrate import apply_migrations
    apply_migrations(database_url=url)
    from genios_engine.context.graph_store import GraphStore
    return GraphStore(url)
