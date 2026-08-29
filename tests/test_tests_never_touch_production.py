"""A test suite that can reach production is a production incident waiting for a slow machine.

Nine `conn` fixtures in this directory were written as "live PostgreSQL, rolled back". On CI, with
no `.env`, they skipped and looked harmless. On a developer machine the live PostgreSQL they found
was the paying tenant's: every run opened a transaction against `execution_outcomes`,
`learning_runs` and the `delivery_*` tables, held real locks there for the length of the test, and
relied on reaching the rollback. A run killed mid-test — a CI timeout, a ^C, an agent harness that
backgrounds a slow command — never reaches it, and Supabase runs with
`idle_in_transaction_session_timeout = 0`, so the locks are held until a human notices.

The fix is one line per fixture. This test is what keeps it one line: the next fixture written from
the same template fails here instead of in a tenant's database six months from now.
"""
from __future__ import annotations

import pathlib

TESTS = pathlib.Path(__file__).parent

# conftest.py owns the decision about what a test may connect to, so it is the one file allowed to
# name the setting. Everything else asks it via the `live_db_url` fixture.
_ALLOWED = {"conftest.py", pathlib.Path(__file__).name}


def test_no_test_resolves_its_database_from_production_settings():
    offenders = sorted(
        p.name for p in TESTS.glob("test_*.py")
        if p.name not in _ALLOWED and "get_settings().database_url" in p.read_text())
    assert not offenders, (
        "these tests resolve a connection from the configured (production) database_url instead of "
        "the `live_db_url` fixture: " + ", ".join(offenders))


def test_the_shared_resolver_has_no_production_fallback():
    """The guard above is only worth having while the thing it points at is safe. If
    `live_test_database_url` ever grows a fallback to the configured URL, every fixture that
    obediently uses the fixture starts reaching production again — and this file would still
    pass. Checked against the function's CODE, not its prose: the docstring is allowed to name
    what it refuses to do."""
    source = (TESTS / "conftest.py").read_text()
    body = source[source.index("def live_test_database_url"):]
    body = body[:body.index("\ndef ")]
    code = body[body.index('"""', body.index('"""') + 3) + 3:]   # past the docstring
    assert "get_settings" not in code, (
        "live_test_database_url must not fall back to the configured database_url; it did:\n" + code)
