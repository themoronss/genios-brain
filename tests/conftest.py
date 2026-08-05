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
