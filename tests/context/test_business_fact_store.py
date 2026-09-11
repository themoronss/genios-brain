"""Actual SQL fact/ref writes; SQLite clock is a fixed fixture, not the wall clock."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event, text

from genios_engine.context.graph_store import GraphStore
from .test_event_presence_store import presence_schema
from .test_support_derived_provenance import NOW


def fact_schema(c):
    presence_schema(c)
    c.execute(text("""create table graph_facts (fact_version_id text primary key, fact_id text,
        org_id text, subject_node_id text, field text, value text, value_type text, status text,
        authority_rank integer, confidence real, relevance real, occurred_at timestamp,
        created_by_event_id text, derivation_type text, trace_id text, schema_version text,
        source_authority text, provenance_refs text, valid_from text default '2026-09-10',
        valid_to text)"""))
    c.execute(text("""create table discrepancies (id text, org_id text, subject_node_id text,
        field text, held text, challenger text, status text default 'open')"""))


@pytest.fixture
def fact_store():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.create_function("now", 0, lambda: NOW.isoformat()))
    store = object.__new__(GraphStore)
    store._engine = engine
    with engine.begin() as c:
        fact_schema(c)
    yield store
    engine.dispose()


def write(store, c, *, standing="observed", value="fundraising", at=NOW, event_id="e", **kw):
    return store.write_fact(c, org_id="o", subject_node_id="thread", field="thread.objective",
        value=value, value_type="string", confidence=0.85 if standing == "observed" else 0.4,
        occurred_at=at, event_id=event_id, evidence={"text": value, "standing": standing},
        source="gmail", authority_rank=2 if standing == "observed" else 1, **kw)


def active(c):
    return c.execute(text("select * from graph_facts where status='active' and valid_to is null")).mappings().one()


@pytest.mark.parametrize("reverse", [False, True])
def test_a_stated_business_purpose_beats_a_newer_judgement_in_either_arrival_order(fact_store, reverse):
    with fact_store.engine.begin() as c:
        candidates = [dict(standing="observed", value="fundraising", at=NOW - timedelta(days=1)),
                      dict(standing="judgement", value="selling", at=NOW, event_id="later")]
        for candidate in reversed(candidates) if reverse else candidates:
            write(fact_store, c, **candidate)
        held = active(c)
        assert json.loads(held["value"]) == "fundraising"
        assert held["authority_rank"] == 2
        refs = c.execute(text("select * from graph_source_refs where fact_version_id=:f"), {"f":held["fact_version_id"]}).mappings().all()
        assert len(refs) == 1 and refs[0]["event_id"] == "e"
        assert json.loads(refs[0]["evidence"])["standing"] == "observed"


def test_confirmation_promotes_an_inferred_value_so_a_later_guess_cannot_replace_it(fact_store):
    with fact_store.engine.begin() as c:
        write(fact_store, c, standing="judgement")
        write(fact_store, c, event_id="stated")
        write(fact_store, c, standing="judgement", value="selling", event_id="guess")
        assert active(c)["authority_rank"] == 2
        assert json.loads(active(c)["value"]) == "fundraising"
        held, challenger = c.execute(text("select held,challenger from discrepancies where status='open'")).one()
        assert json.loads(held)["value"] == "fundraising"
        assert json.loads(challenger)["value"] == "selling"


def test_replay_still_cannot_change_an_active_business_fact(fact_store):
    with fact_store.engine.begin() as c:
        write(fact_store, c, standing="judgement", value="selling")
        write(fact_store, c, replay=True)
        assert json.loads(active(c)["value"]) == "selling"


def test_a_postgres_native_json_string_opens_a_discrepancy_without_json_decode_failure():
    from types import SimpleNamespace
    from tests.test_corroboration import _FakeConn
    c = _FakeConn(held=SimpleNamespace(fact_version_id="held", value="fundraising",
        authority_rank=2, occurred_at=NOW))
    s = object.__new__(GraphStore)
    # psycopg returns decoded JSON scalars. SQLite and PG must feed the same authority policy.
    assert write(s, c, standing="judgement", value="selling") is None
