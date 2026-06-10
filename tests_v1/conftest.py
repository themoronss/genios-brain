"""
Shared pytest fixtures for genios-brain tests.

These tests hit the REAL API (localhost:8000) with a REAL API key.
They're integration tests, not unit tests. The brain must be running.

Set GENIOS_TEST_API_KEY and GENIOS_TEST_BASE_URL in env or .env.
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_URL = os.getenv("GENIOS_TEST_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("GENIOS_TEST_API_KEY", os.getenv("GENIOS_API_KEY"))


@pytest.fixture(scope="session")
def api():
    """Provides a configured API helper for the test session."""
    if not API_KEY:
        pytest.skip("GENIOS_TEST_API_KEY not set — can't run integration tests")

    class Api:
        def __init__(self):
            self.base = BASE_URL.rstrip("/")
            self.headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            }

        def get(self, path, **kwargs):
            return requests.get(f"{self.base}{path}", headers=self.headers, timeout=20, **kwargs)

        def post(self, path, json=None, **kwargs):
            return requests.post(f"{self.base}{path}", headers=self.headers, json=json, timeout=20, **kwargs)

    client = Api()
    # Smoke check: can we reach the brain?
    try:
        r = client.get("/v1/org")
        if r.status_code != 200:
            pytest.skip(f"Brain returned {r.status_code} on /v1/org — not running?")
    except requests.ConnectionError:
        pytest.skip("Brain not running on localhost:8000")

    return client
