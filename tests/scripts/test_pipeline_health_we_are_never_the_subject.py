"""STEP-04 · C6 — the health check that we are never a card's subject or a thread's name.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_we_are_never_the_subject.py -q

Tree `yc2_w27_s04/M22.C6.L-interface.V3.U01`. `scripts/pipeline_health.check_we_are_never_the_subject`
reads production after the deploy and the repair: open cards whose subject is one of us, and threads
named after one of us — both 0. It judges by `platform/self_identity.names_us`, the same test the card
builder refuses by, so the check and the builder cannot disagree.
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "s04_health_subject"
OWNER = "founder.s04subject@gmail.com"
NOW = datetime.now(timezone.utc)


def _health():
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def conn():
    """A real-Postgres transaction, rolled back."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    c = engine.connect()
    tx = c.begin()
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    c.execute(text("insert into orgs (id, name, email, first_name, last_name) values "
                   "(:o, 'Kitebird', :e, 'Meera', 'Iyer')"), {"o": ORG, "e": OWNER})
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                   "(:o, 'address', 'ceo@kitebird.test', 'test'), (:o, 'domain', 'kitebird.test', 'test')"),
              {"o": ORG})
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _card(c, card_id: str, subject: str, state: str = "queued") -> None:
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
        "score, why, actions, artifact, state, expires_at, business_subject) values "
        "(:c, :s, :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), cast('[]' as jsonb), "
        "cast('{}' as jsonb), :st, :exp, :subj)"),
        {"c": card_id, "s": f"sig_{card_id}", "o": ORG, "st": state,
         "exp": NOW + timedelta(days=3), "subj": subject})


def _thread(c, node_id: str, label: str) -> None:
    c.execute(text(
        "insert into graph_nodes (org_id, node_id, node_type, canonical_key, display_name) "
        "values (:o, :n, 'thread', :k, :d)"), {"o": ORG, "n": node_id, "k": f"thread:{node_id}", "d": label})


def test_a_card_and_a_thread_about_us_are_caught(conn):
    _card(conn, "c_us", "Ms Meera Iyer")
    _card(conn, "c_ours_addr", "ceo@kitebird.test — awaiting reply")
    _card(conn, "c_gone", "Meera Iyer", state="dismissed")          # closed: not counted
    _card(conn, "c_them", "Ira Shah (Northwind)")
    _thread(conn, "t_us", "Meera Iyer — Seed round for Kitebird")
    _thread(conn, "t_them", "Ira Shah — Seed round for Kitebird")
    check = _health().check_we_are_never_the_subject(conn, ORG)
    assert check.ok is False
    assert check.measured == "2 open card(s) about us, 1 thread(s) named after us", check.measured
    assert any("c_us" in d for d in check.detail) and any("t_us" in d for d in check.detail)
    assert not any("c_them" in d or "t_them" in d or "c_gone" in d for d in check.detail)


def test_after_the_repair_it_is_green(conn):
    _card(conn, "c_them", "Ira Shah (Northwind)")
    _thread(conn, "t_them", "Ira Shah — Seed round for Kitebird")
    _thread(conn, "t_plain", "Seed round for Kitebird")
    check = _health().check_we_are_never_the_subject(conn, ORG)
    assert check.ok is True, check.detail
    assert check.measured == "0 open card(s) about us, 0 thread(s) named after us"


def test_it_runs_with_every_other_check():
    assert _health().check_we_are_never_the_subject in _health().CHECKS
