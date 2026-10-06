"""STEP-03 · the parked drain re-admits an archived `llm_junk` mail exactly as it re-admitted a dropped one.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/parked/test_the_drain_reads_archived_judgments.py -q

`capture/parked/drain.drain_parked` (tree `yc2_w27_s03/M21.C4.L-logic.V4.U03`). Before STEP-03 the
AI filter's confident junk was DROPPED with its body kept for 90 days, and the drain — on every
heartbeat — flipped each such judged drop back to `emitted` without re-running the gate (03 F55).
STEP-03 changes what the gate does, not what the founder sees, so the drain must find the same
mail now that it is ARCHIVED: same codes (`RE_ADJUDICABLE`), payload present, same flip. A mail a
RULE archived (N-02, N-06 …) was never re-admitted — a provider's label is a fact, not an opinion —
and is still not touched. A judged drop written before the deploy is still re-admitted.

Rows are made by the real pipeline on Postgres where it can still make them; the legacy drop is
written by hand, because nothing writes one any more.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.parked.drain import RE_ADJUDICABLE, drain_parked
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_drain_archived"
AT = datetime(2026, 10, 6, 9, tzinfo=timezone.utc)
_TABLES = ("event_trace", "raw_payloads", "prepared_content", "parked_events", "source_events")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres drain tests skipped")
    eng = get_engine(live_db_url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'da@example.test')"),
                  {"o": ORG})
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    with eng.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


class _Junk:
    def classify(self, ctx, prepared):
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated matchmaking")


def _capture(url: str, oid: str, raw: dict, *, relevance=None):
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.capture.payload_store import PostgresRawPayloadStore
    from genios_engine.capture.prepared_store import PostgresPreparedContentStore
    from genios_engine.capture.trace_store import PostgresTraceRepository

    return P.capture_event(
        RawObject(source="gmail", object_type="email_message", source_object_id=oid,
                  occurred_at=AT, actor_email="hello@boardy.test", raw=raw),
        org_id=ORG, connection_id="conn_gmail", repo=PostgresSourceEventRepository(url),
        payload_store=PostgresRawPayloadStore(url, os.environ["GENIOS_CRYPTO_KEY"]),
        prepared_store=PostgresPreparedContentStore(url), trace_repo=PostgresTraceRepository(url),
        relevance=relevance)


def _row(eng, event_id: str):
    with eng.connect() as c:
        return c.execute(text("select outcome, route, triage_lane, attention, attention_reason "
                              "from source_events where org_id = :o and event_id = :e"),
                         {"o": ORG, "e": event_id}).one()


def test_the_judged_codes_are_still_the_models():
    assert {"llm_junk", "llm_junk_unconfident", "low_relevance"} <= RE_ADJUDICABLE
    assert not {c for c in RE_ADJUDICABLE if c.startswith("N-")}, "a rule's code is not a judgment"


def test_an_archived_llm_junk_mail_is_re_admitted_as_a_dropped_one_was(engine, live_db_url):
    res = _capture(live_db_url, "j1", {"subject": "Boardy here", "body": "More investor intros?"},
                   relevance=_Junk())
    assert res.outcome == "archived"

    out = drain_parked(engine, org_id=ORG, now=AT)

    assert out["reinjected"] == 1 and out["by_reason"]["llm_junk"] == {"seen": 1, "reinjected": 1}
    row = _row(engine, res.event.event_id)
    assert (row.outcome, row.route, row.triage_lane) == ("emitted", "needs_extraction", "P3")
    # It is about to be read, so it no longer says nobody reads it — and it says why.
    assert (row.attention, row.attention_reason) == ("deep", "readmitted:llm_junk")
    with engine.connect() as c:
        assert c.execute(text("select count(*) from parked_events where org_id = :o"),
                         {"o": ORG}).scalar() == 0, "a re-admitted archive is not a park"


def test_a_rule_archived_mail_is_not_touched(engine, live_db_url):
    res = _capture(live_db_url, "r1", {"subject": "Intro: Pankaj", "body": "Pankaj asked to meet.",
                                       "headers": {"List-Unsubscribe": "<mailto:u@b.test>"}})
    assert res.outcome == "archived"

    out = drain_parked(engine, org_id=ORG, now=AT)

    assert out["examined"] == 0
    assert _row(engine, res.event.event_id).outcome == "archived"


def test_a_judged_drop_written_before_step_03_is_still_re_admitted(engine):
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, payload_ref) "
            "values ('evt_legacy', :o, 'conn_gmail', 'gmail', 'email_message', 'legacy', "
            "'gmail:email_message:legacy', cast('{}' as jsonb), :at, :at, 'dropped', 'pay_legacy')"),
            {"o": ORG, "at": AT})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values ('pay_legacy', :o, 'evt_legacy', 'application/json', 'x', :exp)"),
            {"o": ORG, "exp": datetime(2027, 1, 1, tzinfo=timezone.utc)})
        c.execute(text(
            "insert into event_trace (org_id, event_id, stage, action, reason_code) "
            "values (:o, 'evt_legacy', 'S2', 'drop', 'llm_junk')"), {"o": ORG})

    out = drain_parked(engine, org_id=ORG, now=AT)

    assert out["reinjected"] == 1
    row = _row(engine, "evt_legacy")
    assert (row.outcome, row.attention, row.attention_reason) == (
        "emitted", "deep", "readmitted:llm_junk")


def test_a_re_admitted_archive_is_not_re_admitted_twice(engine, live_db_url):
    res = _capture(live_db_url, "j2", {"subject": "Boardy here", "body": "More investor intros?"},
                   relevance=_Junk())
    first = drain_parked(engine, org_id=ORG, now=AT)
    second = drain_parked(engine, org_id=ORG, now=AT)
    assert (first["reinjected"], second["reinjected"], second["examined"]) == (1, 0, 0)
    assert _row(engine, res.event.event_id).outcome == "emitted"
