from __future__ import annotations

from genios_engine.capture.events_store import InMemoryAgentRegistryStore
from genios_engine.contracts.events import AGENT_ACTIONS, AGENT_API_SCOPES
from genios_engine.platform.auth import (AuthCtx, hash_key, hash_password, jwt_decode,
                                         jwt_encode, new_api_key, verify_password,
                                         verify_webhook_hmac)
from genios_engine.platform.cache import NullCache, get_cache, l2key, okey

# Foundations for Part A (auth/cache port). Offline: NullCache graceful path + org-scoped keys
# + the agent-scope grant/verify that unblocks the metered /v1/signals* surface.


def test_cache_is_nullcache_without_redis_url():
    c = get_cache()
    # No GENIOS_REDIS_URL in the test env → graceful NullCache, every op a safe no-op/miss.
    assert isinstance(c, NullCache)
    assert c.enabled is False
    assert c.get("anything") is None
    c.setex("k", 60, "v")            # no-op, must not raise
    c.delete("k")
    assert c.get_json("k") is None


def test_cache_keys_are_org_scoped():
    # the cross-tenant cache-leak fix: two orgs, same content hash → different keys
    assert l2key("orgA", "deadbeef") != l2key("orgB", "deadbeef")
    assert l2key("orgA", "deadbeef").startswith("l2:orgA:")
    assert okey("orgA", "readmodel", "deal_1") == "org:orgA:readmodel:deal_1"


def test_l5_agent_scopes_are_a_distinct_grant_family():
    assert AGENT_API_SCOPES == {"signals.read", "artifacts.read", "signals.claim", "signals.result"}
    assert AGENT_API_SCOPES.isdisjoint(AGENT_ACTIONS)          # separate families
    # the route now accepts either family:
    allowed = AGENT_ACTIONS | AGENT_API_SCOPES
    assert {"signals.read", "email_sent"} <= allowed


def test_agent_registry_grants_and_verifies_l5_scope():
    reg = InMemoryAgentRegistryStore()
    reg.register("orgA", "sdr_bot", "gn_secret", ["signals.read", "signals.claim"])
    assert reg.verify("orgA", "sdr_bot", "gn_secret", "signals.read") is True
    assert reg.verify("orgA", "sdr_bot", "gn_secret", "signals.claim") is True
    assert reg.verify("orgA", "sdr_bot", "gn_secret", "signals.result") is False   # not granted
    assert reg.verify("orgA", "sdr_bot", "wrong_key", "signals.read") is False      # bad key


# ── stdlib auth primitives (no DB) ──────────────────────────────────────────

def test_jwt_roundtrip_and_tamper_and_expiry():
    tok = jwt_encode({"org_id": "org_x", "exp": 9_999_999_999}, "sekret")
    assert jwt_decode(tok, "sekret")["org_id"] == "org_x"
    assert jwt_decode(tok, "wrong-secret") is None                 # signature check
    assert jwt_decode(tok[:-2] + "xy", "sekret") is None           # tampered sig
    assert jwt_decode(jwt_encode({"org_id": "y", "exp": 1}, "s"), "s") is None   # expired


def test_password_hash_is_salted_and_verifies():
    h1, h2 = hash_password("correct horse"), hash_password("correct horse")
    assert h1 != h2 and h1.startswith("pbkdf2$")                   # unique salt each time
    assert verify_password("correct horse", h1) is True
    assert verify_password("wrong", h1) is False
    assert verify_password("x", None) is False


def test_api_key_shape_and_hash():
    raw, key_hash, prefix = new_api_key()
    assert raw.startswith("gn_live_") and prefix == raw[:12]
    assert key_hash == hash_key(raw) and len(key_hash) == 64       # sha256 hex
    assert new_api_key()[0] != new_api_key()[0]                    # random each time


def test_authctx_scope_semantics():
    owner = AuthCtx(org_id="o", scopes=None)                       # dashboard/owner = all scopes
    scoped = AuthCtx(org_id="o", scopes=["signals.read"])
    assert owner.has_scope("anything") is True
    assert scoped.has_scope("signals.read") and not scoped.has_scope("signals.claim")


def test_webhook_hmac_verify():
    import hashlib
    import hmac
    body = b'{"event":"new_email"}'
    good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    assert verify_webhook_hmac(body, good, "whsec") is True
    assert verify_webhook_hmac(body, "sha256=" + good, "whsec") is True   # prefix tolerated
    assert verify_webhook_hmac(body, "v1," + good, "whsec") is True
    assert verify_webhook_hmac(body, "deadbeef", "whsec") is False        # forged
    assert verify_webhook_hmac(body, None, "whsec") is False              # unsigned
    assert verify_webhook_hmac(b"tampered", good, "whsec") is False       # body changed


def test_connection_secret_fields_sealed_at_rest():
    from genios_engine.capture.connections.store import _open_config, _seal_config
    raw = {"db_url": "postgresql://u:SECRETpw@h/d", "table": "deals", "token": "tok_live_x"}
    sealed = _seal_config(raw)
    assert sealed["db_url"].startswith("enc:") and "SECRETpw" not in sealed["db_url"]
    assert sealed["token"].startswith("enc:") and sealed["table"] == "deals"   # non-secret intact
    assert _open_config(sealed) == raw                                         # decrypts back
    assert _seal_config(sealed) == sealed                                      # idempotent (no double-seal)


def test_client_db_connector_rejects_sql_injection_identifiers():
    from genios_engine.capture.connectors.database import ClientDatabaseConnector
    # valid identifiers construct fine (engine is lazy — no connection here)
    ClientDatabaseConnector(database_url="postgresql://x/y", table="public.deals",
                            identity_field="id", watermark_col="updated_at")
    for bad in [{"table": "deals; drop table users"},
                {"watermark_col": "updated_at; select 1"},
                {"identity_field": "(select secret from vault)"}]:
        kw = {"table": "deals", "identity_field": "id", "watermark_col": "updated_at", **bad}
        try:
            ClientDatabaseConnector(database_url="postgresql://x/y", **kw)
            raise AssertionError(f"expected ValueError for {bad}")
        except ValueError:
            pass
