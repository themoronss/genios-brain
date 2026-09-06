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


def test_no_test_process_holds_a_real_model_key():
    """The same rule for the MODEL, which is the half this file did not cover.

    Pinning the database made the suite unable to WRITE to a paying tenant. It left the suite
    perfectly able to SPEND on one: `Settings.use_real_llm` is `bool(anthropic_api_key)`, `.env`
    sets that key on every developer machine, `l1_llm_gate` defaults to True, and
    `platform/wiring.make_relevance_classifier` therefore returns a real
    `LLMRelevanceClassifier(LLMClient(api_key=...))`. Every `pg`-marked test that drives
    `api/routes._sync_connection` — the acceptance gates, the ALG-17 wiring tests — then made one
    billed Anthropic call per ambiguous event, on every run, and the only visible symptom was
    that the suite was slow.

    `tests/capture/conftest.py`'s socket guard cannot catch this: `pg` and `llm` are exactly the
    two markers it stands down for, which is correct — a pg test needs a socket — and is why the
    key has to be absent rather than the socket blocked.
    """
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.wiring import make_relevance_classifier

    settings = get_settings()
    assert not settings.use_real_llm, (
        "the test process holds a real Anthropic key; tests/conftest.py must clear "
        "GENIOS_ANTHROPIC_API_KEY at import, before the lru_cached get_settings() materialises")
    assert make_relevance_classifier("org_any") is None, (
        "the production wiring built a live relevance classifier inside the test process")


def test_the_key_is_cleared_before_settings_can_be_materialised():
    """The guard above passes for the wrong reason if the clearing ever moves into a fixture:
    `get_settings` is `lru_cache`d and application code constructs its own `Settings`, so a
    fixture-time monkeypatch is already too late for anything imported at collection. Asserted
    against conftest's CODE, on the same terms as the resolver check above."""
    source = (TESTS / "conftest.py").read_text()
    assign = 'os.environ["GENIOS_ANTHROPIC_API_KEY"] = ""'
    assert assign in source, "conftest.py no longer clears the Anthropic key"
    assert source.index(assign) < source.index("@pytest.fixture"), (
        "the key is cleared after the first fixture — it must happen at IMPORT, before any "
        "module-level get_settings() call in application code can materialise the cache")
