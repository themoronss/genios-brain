"""STEP-05 · an archived mail enters memory as metadata only.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_an_archived_mail_is_metadata_only.py -q

Tree `yc2_w27_s05 · M23.C3.L-logic.V2.U02`. The gate archives what it calls noise (STEP-03) — and an
archived Boardy introduction is still the only place Pankaj is named. `process_event(metadata_only=True)`
writes who wrote to whom, their companies and the thread they belong to — and nothing a reader could take
for the mail's words or for a reason to act: no text, no relevance observation, no ball-in-court or
waiting fact, no correlation (`03` F37, F57: an archive's words stay unreadable).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction
from genios_engine.platform.self_identity import identity_for

pytestmark = pytest.mark.pg

ORG = "archived_is_metadata_only_org"
NOW = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
FOUNDER = "founder.meta@gmail.com"
CONNECTOR = "hello@introly.test"
PANKAJ = "pankaj@saka.test"


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        for tbl in ("context_correlation_members", "context_situations", "context_correlations"):
            c.execute(text(f"delete from {tbl} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": ORG, "e": FOUNDER})
    yield pg_store
    _reset(pg_store)


def _empty() -> Extraction:
    return Extraction(ok=True, relevance=0.0, noise_type="none", domains=[], entity_mentions=[],
                      fact_candidates=[], commitments=[], questions=[], observations=[])


def _intro(store, event_id: str, *, metadata_only: bool):
    us = identity_for(store, ORG)
    return pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content="", sender_email=CONNECTOR,
        sender_name="Introly", recipient_emails=[FOUNDER, PANKAJ], occurred_at=NOW, llm=None,
        store=store, is_inbound=True, internal_emails=us.addresses, self_identity=us,
        thread_id=f"thr_{event_id}", qualified_extraction=_empty(), metadata_only=metadata_only)


def _rows(store, sql: str) -> list:
    with store.engine.connect() as c:
        return c.execute(text(sql), {"o": ORG}).fetchall()


def test_the_people_and_their_companies_enter_memory(store):
    res = _intro(store, "evt_meta_intro", metadata_only=True)
    assert res.outcome == "committed_metadata"
    people = {r.canonical_key for r in _rows(store, "select canonical_key from graph_nodes "
                                                    "where org_id = :o and node_type = 'person'")}
    assert {CONNECTOR, PANKAJ} <= people, sorted(people)
    companies = {r.canonical_key for r in _rows(store, "select canonical_key from graph_nodes "
                                                       "where org_id = :o and node_type = 'company'")}
    assert "saka.test" in companies
    edges = _rows(store, "select edge_type from graph_edges where org_id = :o "
                         "and edge_type = 'corresponded_with'")
    assert edges, "who wrote to whom was not recorded"
    assert _in_thread(store, "thr_evt_meta_intro") == {CONNECTOR}, "the thread was not recorded"


def test_an_archived_mail_we_sent_puts_its_recipients_in_its_thread(store):
    us = identity_for(store, ORG)
    res = pipeline.process_event(
        org_id=ORG, event_id="evt_meta_sent", source="gmail", content="", sender_email=FOUNDER,
        recipient_emails=[PANKAJ], occurred_at=NOW, llm=None, store=store, is_inbound=False,
        internal_emails=us.addresses, self_identity=us, thread_id="thr_evt_meta_sent",
        qualified_extraction=_empty(), metadata_only=True)
    assert res.outcome == "committed_metadata"
    assert _in_thread(store, "thr_evt_meta_sent") == {PANKAJ}
    facts = _rows(store, "select field from graph_facts where org_id = :o")
    assert not [f.field for f in facts if f.field.startswith("thread.")]


def _in_thread(store, thread_id: str) -> set[str]:
    """Who the graph says took part in one conversation."""
    with store.engine.connect() as c:
        return {r.canonical_key for r in c.execute(text(
            "select p.canonical_key from graph_nodes t "
            "  join graph_edges e on e.org_id = t.org_id and e.to_node_id = t.node_id "
            "       and e.edge_type = 'corresponded_with' and e.valid_to is null "
            "  join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
            "       and p.valid_to is null "
            " where t.org_id = :o and t.node_type = 'thread' and t.valid_to is null "
            "   and t.canonical_key = :k"), {"o": ORG, "k": f"thread:{thread_id}"})}


def test_nothing_a_reader_could_take_for_its_words_or_a_reason_to_act(store):
    _intro(store, "evt_meta_quiet", metadata_only=True)
    facts = _rows(store, "select field from graph_facts where org_id = :o")
    assert not [f.field for f in facts if f.field.startswith("thread.")], (
        f"a waiting or ball-in-court fact from an archive: {sorted(f.field for f in facts)}")
    kinds = {r.kind for r in _rows(store, "select kind from graph_observations where org_id = :o")}
    assert "email_relevance" not in kinds and not any(k.startswith("email_noise") for k in kinds)
    members = _rows(store, "select 1 from context_correlation_members where org_id = :o")
    assert not members, "an archive was correlated into a situation"


def test_the_same_mail_kept_would_have_done_all_of_that(store):
    """The control: the flag, and only the flag, is what keeps an archive quiet."""
    res = _intro(store, "evt_meta_control", metadata_only=False)
    assert res.outcome == "committed"
    facts = {r.field for r in _rows(store, "select field from graph_facts where org_id = :o")}
    assert any(f.startswith("thread.") for f in facts)
