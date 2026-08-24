"""Admin console + metric dictionary (ANALYTICS_V3_PLAN Phase 1-2).

Two things are worth locking down here. First the boundary: these are the only cross-org reads in
the engine, so a route that ships without `require_admin` leaks every tenant's revenue — that is
asserted structurally, not per-route, so a future endpoint cannot forget. Second the definitions:
if the SQL and the Python price the same tokens differently, the console and PostHog will quote
two numbers for one question, which is exactly how the previous analytics generation lost its
credibility.

The Postgres-backed cases run only with GENIOS_TEST_DATABASE_URL set (pg_store fixture); the rest
are hermetic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsMarker
from sqlalchemy import text

from genios_engine.api import admin_routes as A
from genios_engine.platform import metrics as M
from genios_engine.platform.auth import AuthCtx, require_admin

NOW = datetime.now(timezone.utc)


# ── the boundary ────────────────────────────────────────────────────────────────────────
def _declares_require_admin(endpoint) -> bool:
    import inspect
    return any(isinstance(p.default, DependsMarker) and p.default.dependency is require_admin
               for p in inspect.signature(endpoint).parameters.values())


def test_every_admin_route_is_gated_by_require_admin():
    """Structural, not per-route: a new endpoint added to this router inherits the assertion."""
    assert A.router.routes, "admin router registered no routes"
    for route in A.router.routes:
        assert _declares_require_admin(route.endpoint), \
            f"{route.path} is a cross-org route without require_admin"


def test_superadmin_comes_from_env_not_from_a_customer_row(monkeypatch):
    """Granting staff access must never require writing to a tenant's account. The env list alone
    is enough, and it is matched case-insensitively on the JWT's email."""
    from genios_engine.platform import auth as AUTH
    from genios_engine.platform.config import get_settings
    monkeypatch.setenv("GENIOS_SUPERADMIN_EMAILS", "Me@genios.ai, other@genios.ai")
    get_settings.cache_clear()
    try:
        assert AUTH.superadmin_emails() == {"me@genios.ai", "other@genios.ai"}
        # no database is configured in this test — reaching the DB fallback would raise, so a
        # returned ctx proves the env list short-circuited before any tenant lookup
        ctx = AUTH.require_admin(AuthCtx(org_id="org_any", actor_id="ME@genios.ai", source="jwt"))
        assert ctx.org_id == "org_any"
    finally:
        get_settings.cache_clear()


def test_empty_superadmin_list_grants_nobody(monkeypatch):
    """The default must be closed: an unset env var is not a wildcard."""
    from genios_engine.platform import auth as AUTH
    from genios_engine.platform.config import get_settings
    monkeypatch.setenv("GENIOS_SUPERADMIN_EMAILS", "")
    get_settings.cache_clear()
    try:
        assert AUTH.superadmin_emails() == set()
    finally:
        get_settings.cache_clear()


def test_scoped_api_key_can_never_reach_the_admin_console():
    """An agent/extension key is a customer credential. Even if its org were flagged internal, it
    must be refused before any database lookup happens."""
    with pytest.raises(HTTPException) as exc:
        require_admin(AuthCtx(org_id="org_x", scopes=["read:context"], source="api_key"))
    assert exc.value.status_code == 403


def test_sort_parameter_is_whitelisted_not_interpolated():
    with pytest.raises(HTTPException) as exc:
        A.accounts(sort="created_at; drop table orgs", _ctx=None)
    assert exc.value.status_code == 422


# ── the metric dictionary ───────────────────────────────────────────────────────────────
def test_unknown_model_prices_at_the_cheapest_family_not_zero():
    """A model we forgot to add must under-report, never vanish: 0 would silently hide spend."""
    assert M.llm_price("some-future-model") == M.LLM_PRICE["haiku"]
    assert M.cost_usd("some-future-model", 1_000_000, 0) > 0


def test_dated_model_ids_still_price_by_family():
    assert M.llm_price("claude-sonnet-5-20260101") == M.LLM_PRICE["sonnet"]
    assert M.llm_price("claude-haiku-4-5-20251001") == M.LLM_PRICE["haiku"]


def test_mrr_counts_only_paying_active_accounts():
    assert M.mrr_inr("startup", "active") == 25_000.0
    assert M.mrr_inr("early", "active") == 4_500.0
    assert M.mrr_inr("trial", "trial") == 0.0            # a trial is growth, not revenue
    assert M.mrr_inr("startup", "suspended") == 0.0      # suspended stops billing


def test_activity_excludes_page_views_by_construction():
    """'Active' must mean a product action. If a pageview-ish action ever enters this tuple the
    DAU number stops being defensible."""
    assert "user_logged_in" in M.ACTIVITY_ACTIONS
    assert not any("view" in a or "page" in a for a in M.ACTIVITY_ACTIONS)


# ── Postgres: the SQL actually runs, and internal accounts are excluded ─────────────────
def _seed(store, org: str, *, internal: bool, tier: str = "trial", activated: bool = True):
    """Seed exactly one account's worth of rows. Clears first: the pg fixture is session-scoped and
    the database outlives the run, so an append-only seed would double this org's spend on every
    re-run and quietly break the price-parity assertion."""
    with store.engine.begin() as c:
        for tbl in ("llm_costs", "audit_log", "orgs_archive"):
            c.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})
        c.execute(text("delete from orgs where id=:o"), {"o": org})
        c.execute(text("insert into orgs (id,name,company,email,subscription_tier,plan_status,"
                       "is_internal,created_at,activated_at) values "
                       "(:o,:n,:n,:e,:t,'active',:i,:ca,:ac)"),
                  {"o": org, "n": org, "e": f"{org}@t.io", "t": tier, "i": internal,
                   "ca": NOW - timedelta(days=5),
                   "ac": (NOW - timedelta(days=4)) if activated else None})
        c.execute(text("insert into audit_log (org_id,actor_type,action,timestamp) "
                       "values (:o,'user','user_logged_in',:t)"), {"o": org, "t": NOW})
        c.execute(text("insert into llm_costs (org_id,model,purpose,input_tokens,output_tokens) "
                       "values (:o,'claude-sonnet-5','intelligence_query',1000,100)"), {"o": org})


@pytest.fixture()
def admin_client(pg_store, monkeypatch):
    """Drive the routes over HTTP rather than calling them directly: query-parameter parsing and
    validation are part of what these endpoints do, and a direct call silently skips them."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setattr(A, "_graph", pg_store)
    app = FastAPI()
    app.include_router(A.router)
    app.dependency_overrides[require_admin] = lambda: AuthCtx(org_id="org_admin")
    return TestClient(app), pg_store


def test_admin_sql_runs_and_internal_accounts_are_excluded(admin_client):
    client, store = admin_client
    _seed(store, "adm_real", internal=False)
    _seed(store, "adm_us", internal=True)

    listed = {a["org_id"] for a in client.get("/admin/accounts?limit=200").json()["accounts"]}
    assert "adm_real" in listed and "adm_us" not in listed
    with_internal = {a["org_id"] for a in
                     client.get("/admin/accounts?limit=200&include_internal=true")
                     .json()["accounts"]}
    assert {"adm_real", "adm_us"} <= with_internal

    g = client.get("/admin/growth?days=90").json()
    assert g["signups"]["total"] >= 1
    assert [s["step"] for s in g["funnel"]] == ["Signed up", "Connected", "Synced", "Asked GeniOS"]
    # funnel steps are supersets — never more activated accounts than signups
    assert g["funnel"][3]["accounts"] <= g["funnel"][0]["accounts"]

    m = client.get("/admin/money?days=90").json()
    assert m["inr_per_usd"] == M.INR_PER_USD
    assert m["spend"]["usd"] > 0                     # our seeded tokens are priced, not dropped


def test_sql_and_python_price_the_same_tokens_identically(admin_client):
    """The console's per-account rollup is a SQL aggregate while everything else prices in Python.
    They are generated from one table; this proves they agree to the cent."""
    _client, store = admin_client
    _seed(store, "adm_price", internal=False)
    with store.engine.connect() as c:
        sql_usd = float(c.execute(text(
            f"select {M.cost_usd_sql('lc')} from llm_costs lc where lc.org_id='adm_price'")
        ).scalar() or 0)
    assert round(sql_usd, 8) == round(M.cost_usd("claude-sonnet-5", 1000, 100), 8)


def test_spend_survives_account_deletion(admin_client):
    """The whole point of dropping the cascade: money we actually spent must not disappear when a
    customer deletes their account."""
    client, store = admin_client
    _seed(store, "adm_gone", internal=False)
    with store.engine.begin() as c:
        c.execute(text("insert into orgs_archive (org_id,name,company,email,subscription_tier,"
                       "created_at) select id,name,company,email,subscription_tier,created_at "
                       "from orgs where id='adm_gone'"))
        c.execute(text("delete from orgs where id='adm_gone'"))
        kept = c.execute(text("select count(*) from llm_costs where org_id='adm_gone'")).scalar()
    assert kept == 1
    detail = client.get("/admin/accounts/adm_gone").json()
    assert detail["account"]["status"] == "deleted"
    assert detail["economics"]["spend_usd"] > 0


# ── handover hardening (security review, 2026-08-18) ────────────────────────────────────
def test_login_is_rate_limited_but_fails_open_without_a_cache(monkeypatch):
    """A customer's whole workspace sits behind one password, so repeated guesses must be capped.
    The cap must never become a lockout when Redis is down — that would be a worse outage than the
    attack it prevents."""
    from fastapi import HTTPException

    from genios_engine.api import auth_routes as A2

    class _Counter:
        def __init__(self):
            self.n = 0

        def incr_window(self, key, ttl):
            self.n += 1
            return self.n

    counter = _Counter()
    monkeypatch.setattr(A2, "get_cache", lambda: counter)
    for _ in range(A2._LOGIN_ATTEMPTS):
        A2._login_throttle("a@b.com")                      # inside the cap → allowed
    with pytest.raises(HTTPException) as exc:
        A2._login_throttle("a@b.com")
    assert exc.value.status_code == 429

    class _Broken:
        def incr_window(self, key, ttl):
            raise RuntimeError("redis down")

    monkeypatch.setattr(A2, "get_cache", lambda: _Broken())
    A2._login_throttle("a@b.com")                          # must not raise


def test_public_scorecard_hides_the_tenant_count_below_min_n():
    """The scorecard is public by design, but the raw tenant count is a disclosure about us, not a
    statement about the product. It reports the gate until there are enough tenants to anonymise."""
    from genios_engine.api import benchmarks_routes as B

    class _Conn:
        def execute(self, *a, **k):
            class R:
                @staticmethod
                def scalar():
                    return 2
            return R()

    scale = B._scale(_Conn())
    assert scale["orgs"] is None and scale["orgs_reason"] == "below_min_n"
    assert B._MIN_N >= 30


def test_the_dev_ingest_endpoint_is_not_reachable_without_the_internal_token():
    """An unauthenticated POST that runs the capture pipeline has no place on a customer deployment."""
    import inspect

    from genios_engine.api import routes as R
    from genios_engine.platform.auth import require_internal
    from fastapi.params import Depends as DependsMarker

    sig = inspect.signature(R.ingest_sample)
    assert any(isinstance(p.default, DependsMarker) and p.default.dependency is require_internal
               for p in sig.parameters.values())


# ── LLM spend guardrails (token-abuse review) ───────────────────────────────────────────
def test_an_oversized_question_is_refused_before_any_spend():
    """The cheapest attack on an LLM product is one enormous prompt: ~1MB of text is ~250k input
    tokens, and the burst limit still allows 20 of those a minute. Refused on size, before the
    credit check, before the model call."""
    from fastapi import HTTPException

    from genios_engine.api import intelligence_routes as I

    with pytest.raises(HTTPException) as exc:
        I._enforce_input_limits("x" * (I._MAX_QUESTION_CHARS + 1), None)
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "QUESTION_TOO_LONG"

    with pytest.raises(HTTPException) as exc:
        I._enforce_input_limits("fine", {"blob": "y" * (I._MAX_FACTS_BYTES + 100)})
    assert exc.value.detail["code"] == "FACTS_TOO_LARGE"

    I._enforce_input_limits("What should I focus on this week?", {"deal": "acme"})   # allowed


def test_every_plan_has_a_daily_call_ceiling_below_its_credit_pool():
    """Credits are not a spend ceiling: a trial holds 10,000 of them, so a balance check alone
    permitted 10,000 model calls. The daily ceiling has to be the tighter of the two."""
    from genios_engine.api import intelligence_routes as I
    from genios_engine.platform.billing import PLAN_CREDITS

    assert I._DAILY_QUERIES["trial"] < PLAN_CREDITS["trial"]
    for tier, limit in I._DAILY_QUERIES.items():
        assert limit > 0, tier
    assert I._DAILY_QUERIES_DEFAULT <= min(I._DAILY_QUERIES.values())


def test_platform_wide_cap_is_configured_and_disableable(monkeypatch):
    """Per-org caps bound one tenant; only this bounds their sum. It must be on by default and
    tunable without a code change."""
    from genios_engine.platform.config import get_settings

    assert get_settings().daily_llm_usd_cap > 0
    monkeypatch.setenv("GENIOS_DAILY_LLM_USD_CAP", "0")
    get_settings.cache_clear()
    try:
        from genios_engine.api import intelligence_routes as I
        I._platform_spend_ceiling()        # 0 = disabled → returns without touching the DB
    finally:
        get_settings.cache_clear()
