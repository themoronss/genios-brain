"""STEP-03 · the decision ledger keeps a mail's attention tier and the reason for it.

    pytest tests/capture/test_the_repository_keeps_attention.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_the_repository_keeps_attention.py -q

`capture/landing/repository.py` (tree `yc2_w27_s03/M21.C3.L-data.V2.U01`) and `pg_repository.py`
(`M21.C3.L-data.V2.U02`). The pipeline hands `add` the tier `capture/attention.attention_for` gave the
mail — `archive` with the rule that archived it, or `deep` with what let it through — and the ledger
row carries it, beside the outcome. Both stores accept the same vocabulary and refuse the same typo:
the in-memory store mirrors migration 0192's check, so a test on it fails where Postgres would.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.source_event import Actor, SourceEvent

ORG = "repo_attention_org"


def _event(key: str) -> SourceEvent:
    return SourceEvent(
        event_id=f"evt_{key}", org_id=ORG, connection_id="conn_ra", source="gmail",
        object_type="email_message", source_object_id=key, dedup_key=f"gmail:email_message:{key}",
        actor=Actor(type="external_contact", email="intros@boardy.test"),
        occurred_at=datetime(2026, 10, 6, tzinfo=timezone.utc))


# ── in memory ───────────────────────────────────────────────────────────────────────────────────

def test_the_in_memory_ledger_keeps_the_tier_and_its_reason():
    repo = InMemorySourceEventRepository()
    ev = _event("m1")
    repo.add(ev, outcome="archived", attention="archive", attention_reason="N-02")
    decision = repo._decision[(ORG, ev.dedup_key)]
    assert (decision["attention"], decision["attention_reason"]) == ("archive", "N-02")
    assert repo._outcome[(ORG, ev.dedup_key)] == "archived"


def test_a_caller_that_names_no_tier_writes_none():
    """Every caller written before STEP-03 still works — and its row says it carries no tier."""
    repo = InMemorySourceEventRepository()
    ev = _event("m2")
    repo.add(ev, outcome="dropped")
    decision = repo._decision[(ORG, ev.dedup_key)]
    assert (decision["attention"], decision["attention_reason"]) == (None, None)


@pytest.mark.parametrize("tier", ["deep", "skim", "archive"])
def test_every_tier_is_accepted_in_memory(tier):
    InMemorySourceEventRepository().add(_event(f"ok_{tier}"), outcome="emitted", attention=tier,
                                        attention_reason="passed")


def test_a_tier_outside_the_vocabulary_is_refused_in_memory_as_postgres_refuses_it():
    repo = InMemorySourceEventRepository()
    with pytest.raises(ValueError, match="later"):
        repo.add(_event("bad"), outcome="emitted", attention="later")
    assert repo.count() == 0, "a refused write lands nothing"


# ── Postgres ────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def pg():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository

    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'ra@example.test')"),
                  {"o": ORG})
    yield PostgresSourceEventRepository(url), eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _row(eng, ev: SourceEvent):
    with eng.connect() as c:
        return c.execute(text(
            "select outcome, attention, attention_reason from source_events "
            "where org_id = :o and dedup_key = :d"), {"o": ORG, "d": ev.dedup_key}).one()


@pytest.mark.pg
def test_postgres_keeps_the_tier_and_its_reason(pg):
    repo, eng = pg
    ev = _event("p1")
    repo.add(ev, outcome="archived", attention="archive", attention_reason="llm_junk")
    assert tuple(_row(eng, ev)) == ("archived", "archive", "llm_junk")


@pytest.mark.pg
def test_postgres_writes_null_for_a_caller_that_names_no_tier(pg):
    repo, eng = pg
    ev = _event("p2")
    repo.add(ev, outcome="dropped")
    assert tuple(_row(eng, ev)) == ("dropped", None, None)


@pytest.mark.pg
def test_postgres_refuses_a_tier_outside_the_vocabulary(pg):
    from sqlalchemy.exc import IntegrityError

    repo, eng = pg
    ev = _event("p3")
    with pytest.raises(IntegrityError):
        repo.add(ev, outcome="emitted", attention="later")
    with eng.connect() as c:
        assert c.execute(text("select count(*) from source_events where org_id = :o"),
                         {"o": ORG}).scalar() == 0
