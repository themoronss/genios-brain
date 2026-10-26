"""G012 H-27 · a file's card — and the question it asks — names the sources its work came through.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_files_card_names_the_sources_of_its_work_pg.py -q

On the design partner's org (local copy, 25 Oct) 12 of 23 file cards and every one of 67 question cards named no source
(`context_tags` empty): the node's facts carried no source ref, and the question card hard-coded none. The founder's own
cards each name theirs ("Gmail · 6 messages · read in full"). The sources are the recorded `source_events.source` of the
events in the files anchored on the node — never a guess.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.deliver import card_builder as CB

ORG = "org_h27_card_sources"
AT = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(pg_store):
    def _clean(c):
        for t in ("context_correlation_members", "context_correlations", "source_events"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    with pg_store.engine.begin() as c:
        _clean(c)
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
        c.execute(text("insert into context_correlations (correlation_id, org_id, anchor_node_id) "
                       "values ('corr_h27', :o, 'node_fund')"), {"o": ORG})
        for event_id, source, scope in (("evt_mail", "gmail", "org"), ("evt_meet", "gcal", "org"),
                                        ("evt_private", "screen_session", "private")):
            c.execute(text("insert into source_events (event_id, org_id, connection_id, source, object_type, "
                           "source_object_id, dedup_key, actor, occurred_at, visibility_scope) values (:e, :o, 'c', "
                           ":s, 'email_message', :e, :e, cast('{}' as jsonb), :at, :v)"),
                      {"e": event_id, "o": ORG, "s": source, "at": AT, "v": scope})
            c.execute(text("insert into context_correlation_members (org_id, correlation_id, event_id) "
                           "values (:o, 'corr_h27', :e)"), {"o": ORG, "e": event_id})
    yield pg_store
    with pg_store.engine.begin() as c:
        _clean(c)


@pytest.mark.pg
def test_a_node_whose_facts_carry_no_source_names_its_files_sources(store):
    assert CB.real_sources(store, ORG, "node_fund") == {"gmail", "gcal"}, "a private capture names nothing"
    assert CB.source_tags(CB.real_sources(store, ORG, "node_fund")) == ["app:gmail", "app:googlecalendar"]
    assert CB.real_sources(store, ORG, "node_nobody") == set()


@pytest.mark.unit
def test_the_question_card_names_its_files_sources():
    from genios_engine.deliver import pipeline
    assert '"context_tags": _file_source_tags(graph, org_id, node)' in inspect.getsource(pipeline.question_card)
