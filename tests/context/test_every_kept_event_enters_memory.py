"""STEP-05 · every kept event enters memory, each by its own road, and no road calls a model.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_every_kept_event_enters_memory.py -q

Tree `yc2_w27_s05 · M23.C3.L-logic.V2.U03`. The drain now pulls every kept event (U01) — and then handed
each one to the signal's road, where a mail the floor did not publish and an archive came back
`held_missing_qes_extraction` on every sweep. `context/runner._process_one` asks
`context/memory_lanes.lane_for` which road an event takes and walks that one: a signal's extraction, as
before; below the floor, the event's own L1 extraction (U01's adapter); an archive as metadata only
(U02); a calendar record as a meeting, whatever its signal. The drain is run here with no model at all.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import runner
from genios_engine.context.pipeline import RELEVANCE_FLOOR
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import encrypt
from tests.context.test_qes_adapter import QUOTE, extraction

pytestmark = pytest.mark.pg

ORG = "every_kept_event_enters_memory_org"
NOW = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
FOUNDER = "founder.memory@gmail.com"
ACME = "dana@acme.example"                       # a signal: the renewal mail
NEEL = "neel@insight.test"                       # below the floor: the same words, no signal
INTROLY, PANKAJ = "hello@introly.test", "pankaj@saka.test"
ARCHIVED_WORDS = "Pankaj, meet the founder of a company you will like"
SCREEN_CONTACT = "lena@screen.test"


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        for tbl in ("context_correlation_members", "context_situations", "context_correlations"):
            c.execute(text(f"delete from {tbl} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _event(c, event_id: str, *, sender: str, recipients: list[str], payload: dict,
           outcome: str = "emitted", source: str = "gmail", object_type: str = "email_message",
           prepared: str | None = None) -> None:
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, recipients, occurred_at, outcome, parent_object_id) "
        "values (:e, :o, 'conn_memory', :s, :t, :sid, :e, cast(:a as jsonb), :r, :at, :out, :thr)"),
        {"e": event_id, "o": ORG, "s": source, "t": object_type,
         "sid": payload.get("id") or event_id,
         "a": json.dumps({"type": "external_contact", "email": sender}), "r": recipients,
         "at": NOW, "out": outcome, "thr": f"thr_{event_id}"})
    c.execute(text(
        "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
        "values (:id, :o, :e, 'application/json', :enc, :exp)"),
        {"id": f"pay_{event_id}", "o": ORG, "e": event_id,
         "enc": encrypt(json.dumps(payload), get_settings().crypto_key),
         "exp": NOW + timedelta(days=180)})
    if prepared is not None:
        c.execute(text(
            "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
            "values (:e, :o, :id, :t)"), {"e": event_id, "o": ORG, "id": f"pc_{event_id}",
                                          "t": prepared})


def _extraction(c, event_id: str) -> None:
    """Layer 1's extraction of the mail, as its writer files it (a profile, so not L2's own)."""
    c.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output, profile_id, "
        "tier) values (:k, :o, :e, cast(:out as jsonb), 'email', 'T2')"),
        {"k": f"x_{event_id}", "o": ORG, "e": event_id,
         "out": json.dumps(extraction().model_dump(mode="json"))})


def _signal(c, event_id: str) -> None:
    c.execute(text(
        "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
        "importance_bp, importance_version, confidence_bp, visibility, extraction_ref, evidence_refs, "
        "state, occurred_at) values (:s, :o, :e, :t, 'approval_requested', 6000, 'alg17-v1', 8000, "
        "cast('{\"scope\": \"org\"}' as jsonb), :x, cast('[\"ev\"]' as jsonb), 'active', :at)"),
        {"s": f"sig_{event_id}", "o": ORG, "e": event_id, "t": f"trace_{event_id}",
         "x": f"x_{event_id}", "at": NOW})


def _mail(sender: str, body: str) -> dict:
    return {"subject": "Renewal", "body": body, "to": [FOUNDER], "labelIds": ["INBOX"]}


@pytest.fixture
def drained(pg_store):
    """One of each road, plus a screen item with none — drained once, by the real drain, no model."""
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Meera Iyer', :e)"),
                  {"o": ORG, "e": FOUNDER})
        _event(c, "e_signal", sender=ACME, recipients=[FOUNDER], payload=_mail(ACME, QUOTE),
               prepared=f"Renewal\n\n{QUOTE}")
        _extraction(c, "e_signal")
        _signal(c, "e_signal")
        _event(c, "e_below", sender=NEEL, recipients=[FOUNDER], payload=_mail(NEEL, QUOTE),
               prepared=f"Renewal\n\n{QUOTE}")
        _extraction(c, "e_below")
        _event(c, "e_archived", sender=INTROLY, recipients=[FOUNDER, PANKAJ], outcome="archived",
               payload={"subject": "Founder <> Pankaj", "body": ARCHIVED_WORDS,
                        "to": [FOUNDER, PANKAJ], "labelIds": ["INBOX"]})
        _event(c, "e_archived_sent", sender=FOUNDER, recipients=[PANKAJ], outcome="archived",
               payload={"subject": "Re: Founder <> Pankaj", "body": ARCHIVED_WORDS,
                        "to": [PANKAJ]})               # no labels: direction is who sent it
        _event(c, "e_meeting", sender=NEEL, recipients=[FOUNDER], source="gcal",
               object_type="calendar_event",
               payload={"id": "gcal_insight_1", "summary": "Insight intro call",
                        "start": "2026-10-08T10:00:00+05:30", "end": "2026-10-08T10:30:00+05:30",
                        "status": "confirmed",
                        "attendees": [{"email": NEEL}, {"email": FOUNDER}]})
        _event(c, "e_screen", sender=SCREEN_CONTACT, recipients=[FOUNDER], source="screen_session",
               object_type="screen_chat_thread", payload={"text": "see you Friday"})
        _extraction(c, "e_screen")
    first = runner.process_pending(org_id=ORG, store=pg_store, llm=None,
                                   crypto_key=get_settings().crypto_key, eval_time=NOW)
    second = runner.process_pending(org_id=ORG, store=pg_store, llm=None,
                                    crypto_key=get_settings().crypto_key, eval_time=NOW)
    yield pg_store, first, second
    _reset(pg_store)


def _rows(store, sql: str, **params) -> list:
    with store.engine.connect() as c:
        return c.execute(text(sql), {"o": ORG, **params}).fetchall()


def test_every_kept_event_takes_its_road_once(drained):
    store, first, second = drained
    assert first["outcomes"] == {"committed": 2, "committed_metadata": 2,
                                 "committed_structured": 1}, first["outcomes"]
    runs = {r.event_id: r.status for r in _rows(
        store, "select event_id, status from l2_processing_runs where org_id = :o")}
    assert runs == {e: "done" for e in ("e_signal", "e_below", "e_archived", "e_archived_sent",
                                        "e_meeting")}, runs
    assert second["processed"] == 0, f"a settled event was pulled again: {second['outcomes']}"


def test_below_the_floor_its_words_enter_ranked_low(drained):
    store, _, _ = drained
    relevance = {r.event: float(r.relevance) for r in _rows(
        store, "select created_by_event_id as event, max(relevance) as relevance from graph_facts "
               "where org_id = :o and relevance is not null group by created_by_event_id")}
    assert relevance["e_below"] < RELEVANCE_FLOOR <= relevance["e_signal"], relevance
    # The relevance is the whole mark (U06): nothing the mail did not say is filed as if said.
    invented = _rows(store, "select kind from graph_observations where org_id = :o "
                            "and created_by_event_id = 'e_below' and kind like 'l1.%'")
    assert not invented, invented


def test_an_archive_enters_with_its_names_and_without_its_words(drained):
    store, _, _ = drained
    people = {r.canonical_key for r in _rows(
        store, "select canonical_key from graph_nodes where org_id = :o and node_type = 'person' "
               "and valid_to is null")}
    assert {INTROLY, PANKAJ} <= people, sorted(people)
    words = "%" + ARCHIVED_WORDS[:24] + "%"
    readable = _rows(
        store, "select 'fact' from graph_facts where org_id = :o and value::text ilike :w "
               "union all select 'ref' from graph_source_refs where org_id = :o "
               "  and evidence::text ilike :w "
               "union all select 'node' from graph_nodes where org_id = :o "
               "  and (display_name ilike :w or attributes::text ilike :w)", w=words)
    assert not readable, f"an archive's words are readable in the graph: {readable}"
    read = _rows(store, "select event_id from l1_extraction_results where org_id = :o "
                        "and event_id like 'e_archived%' union all select event_id "
                        "from prepared_content where org_id = :o and event_id like 'e_archived%'")
    assert not read, f"an archive was read: {read}"


def test_an_archive_we_sent_is_ours_by_who_sent_it(drained):
    """The archived payload carries no `SENT` label; the direction is the identity's answer, so
    the recipient — not us — is the one in the conversation."""
    store, _, _ = drained
    joined = {r.canonical_key for r in _rows(
        store, "select p.canonical_key from graph_nodes t "
               "  join graph_edges e on e.org_id = t.org_id and e.to_node_id = t.node_id "
               "       and e.edge_type = 'corresponded_with' and e.valid_to is null "
               "  join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
               "       and p.valid_to is null "
               " where t.org_id = :o and t.canonical_key = 'thread:thr_e_archived_sent'")}
    assert joined == {PANKAJ}, joined


def test_a_calendar_event_with_no_signal_is_a_meeting(drained):
    store, _, _ = drained
    meetings = {r.canonical_key for r in _rows(
        store, "select canonical_key from graph_nodes where org_id = :o and node_type = 'meeting' "
               "and valid_to is null")}
    assert meetings == {"gcal:gcal_insight_1"}


def test_a_screen_item_takes_no_road_on_its_own(drained):
    store, _, _ = drained
    assert not _rows(store, "select 1 from l2_processing_runs where org_id = :o "
                            "and event_id = 'e_screen'")
    assert not _rows(store, "select 1 from graph_nodes where org_id = :o and canonical_key = :k",
                     k=SCREEN_CONTACT), "a screen contact became a person"
