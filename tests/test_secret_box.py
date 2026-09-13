"""P6 · agent webhook signing secrets are encrypted at rest.

Sealed values carry `enc:v1:`; rows written before the change (plain text) keep working and are
sealed in place by the startup backfill. A secret that cannot be opened gives "" rather than a
wrong signature.
"""

from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet

from genios_engine.platform import config as C
from genios_engine.platform import secret_box as S


@pytest.fixture
def key(monkeypatch):
    k = Fernet.generate_key().decode()
    monkeypatch.setenv("GENIOS_CRYPTO_KEY", k)
    C.get_settings.cache_clear()
    yield k
    monkeypatch.delenv("GENIOS_CRYPTO_KEY", raising=False)
    C.get_settings.cache_clear()


def test_a_sealed_secret_round_trips_and_hides_the_value(key):
    sealed = S.seal("gnwh_abc123")
    assert sealed.startswith(S.PREFIX) and "gnwh_abc123" not in sealed
    assert S.unseal(sealed) == "gnwh_abc123"
    assert S.seal(sealed) == sealed, "sealing twice must not double-encrypt"


def test_a_legacy_plain_text_row_still_works(key):
    assert S.unseal("gnwh_plain") == "gnwh_plain"
    assert S.unseal(None) == "" and S.seal(None) is None


def test_a_changed_key_gives_empty_not_garbage(key, monkeypatch):
    sealed = S.seal("gnwh_x")
    monkeypatch.setenv("GENIOS_CRYPTO_KEY", Fernet.generate_key().decode())
    C.get_settings.cache_clear()
    assert S.unseal(sealed) == ""


def test_without_a_key_the_value_is_stored_as_given(monkeypatch):
    monkeypatch.delenv("GENIOS_CRYPTO_KEY", raising=False)
    C.get_settings.cache_clear()
    try:
        assert S.seal("gnwh_dev") == "gnwh_dev"
    finally:
        C.get_settings.cache_clear()


def test_a_row_is_opened_for_the_channel(key):
    row = {"agent_id": "a1", "webhook_url": "https://x.test/h", "webhook_secret": S.seal("s1")}
    assert S.unsealed_row(row)["webhook_secret"] == "s1"


@pytest.mark.pg
def test_the_backfill_seals_plain_rows_in_place_once(key, live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres backfill test skipped")
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    with engine.connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    assert org, "scratch org missing — conftest seeds one"
    aid = "agt_box_" + uuid.uuid4().hex[:8]
    try:
        with engine.begin() as c:
            c.execute(text(
                "insert into agent_registry (id, org_id, agent_id, key_hash, allowed_actions, name, "
                "status, webhook_url, webhook_secret) values (:i, :o, :a, :kh, "
                "cast(:acts as text[]), :n, 'active', 'https://agent.box.test/hook', 'gnwh_legacy')"),
                {"i": "agt_" + uuid.uuid4().hex[:10], "o": org, "a": aid,
                 "kh": "kh_" + uuid.uuid4().hex, "acts": ["signals.read"], "n": aid})
        assert S.backfill_agent_webhook_secrets(engine) >= 1
        with engine.connect() as c:
            stored = c.execute(text("select webhook_secret from agent_registry "
                                    "where org_id=:o and agent_id=:a"), {"o": org, "a": aid}).scalar()
        assert stored.startswith(S.PREFIX) and S.unseal(stored) == "gnwh_legacy"
        assert S.backfill_agent_webhook_secrets(engine) == 0, "second run must change nothing"
    finally:
        with engine.begin() as c:
            c.execute(text("delete from agent_registry where org_id=:o and agent_id=:a"),
                      {"o": org, "a": aid})
