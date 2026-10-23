"""GeniOS-011 S06.U1 · a junk archive is re-judged, never re-admitted on its snippet.

    pytest tests/capture/test_a_junk_archive_is_rejudged_not_readmitted.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q      (the drain → re-read path)

`capture/parked/drain.drain_parked`, `capture/landing/unread`, `capture/gate/gate.run_gate` (audit
`l1-junk-verdict-readmitted-on-snippet`). The drain flipped every archived `llm_junk` mail that had a
payload back to `emitted` on every heartbeat, without the gate (`YC-II W27/03` F55); the re-read ladder
then read it as a KEPT mail, so S2 never ran again; and on the Gmail fast path a confident junk verdict
keeps only the list snippet (`connectors/composio.py`), so marketing snippets became extraction claims.
The junk filter delayed mail instead of filtering it.

Now a junk verdict STANDS until a different filter judges the mail. S2 records which filter judged it
(`JUNK_GATE_VERSION`, a digest of the filter's prompts and its threshold), and the drain files an archive
for re-judgment only when that version differs from today's — it flips nothing. A re-judgment is read
through the ladder on the WHOLE message, fetched again and never rebuilt from the stored snippet, and
meets today's gate with S2 included. An archive with no recorded version (every verdict written before
this unit) stays archived.

THE RULE FOR `llm_junk_unconfident`, stated here because the brief asks for it: an unconfident junk
verdict is NOT a verdict that stands. The gate parked the mail because the model was not sure (RULE 04 —
uncertainty routes, it never deletes), and the connector fetched the whole body before the gate parked it
(`connectors/composio._skip_body`: only a CONFIDENT drop keeps its snippet). So the drain re-admits it on
the next heartbeat to be READ, with no version check, and its re-read does not meet the classifier that
was unsure (STEP-05, W-06). `test_an_unconfident_junk_park_is_read_and_not_judged_again` holds it.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import JUNK_GATE_VERSION
from genios_engine.capture.gate.gate import junk_gate_version
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import DROP_BELOW_RELEVANCE
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.landing import unread
from genios_engine.capture.parked.drain import LLM_JUNK_REJUDGE
from genios_engine.capture.parked.drain import NEEDS_REEXTRACTION
from genios_engine.capture.parked.drain import RE_ADJUDICABLE
from genios_engine.capture.parked.drain import drain_parked
from genios_engine.contracts.source_event import Actor
from genios_engine.contracts.source_event import SourceEvent
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.contracts.trace import EventTrace
from genios_engine.platform.crypto import encrypt

#: What a CONFIDENT junk verdict keeps on the Gmail fast path: the list fields and the snippet.
_LIGHT = {"subject": "Intro: Pankaj and Meera", "snippet": "Pankaj asked to meet",
          "labelIds": ["INBOX"]}
#: The same message fetched whole — the words the snippet never had.
_WHOLE_BODY = ("Hi Rohit, Pankaj asked to meet you about the pilot contract. He can do Thursday "
               "afternoon; Meera will send the draft terms before then.")
_WHOLE = {**_LIGHT, "body": _WHOLE_BODY}
_UNSUBSCRIBE = {**_WHOLE, "headers": {"List-Unsubscribe": "<mailto:u@boardy.test>"}}


class _Filter:
    """Today's junk filter: answers one disposition and records every text it was asked about."""

    def __init__(self, disposition: str = "keep", relevance: float = 0.9) -> None:
        self.disposition, self.relevance = disposition, relevance
        self.read: list[str] = []

    def classify(self, ctx, prepared):
        self.read.append(prepared.clean_text if prepared is not None else "")
        return RelevanceVerdict(self.disposition == "keep", self.relevance,
                                disposition=self.disposition, reason="test filter")


def _junk() -> _Filter:
    return _Filter("drop", 0.05)


def _event() -> SourceEvent:
    return SourceEvent(
        event_id="evt_rj", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email="intros@boardy.test"),
        occurred_at=datetime(2026, 10, 6, tzinfo=timezone.utc))


def _gate(raw: dict, *, rereading: str | None, relevance=None):
    trace = EventTrace(org_id="o", event_id="evt_rj")
    return run_gate(GateContext(event=_event(), raw=raw, rereading=rereading), trace,
                    relevance=relevance), trace


def _s2(trace: EventTrace):
    return next(r for r in trace.records if r.stage == "S2")


# ── the verdict says which filter made it ─────────────────────────────────────────────────────

def test_a_junk_verdict_records_the_filter_that_judged_it():
    result, trace = _gate(_WHOLE, rereading=None, relevance=_junk())
    assert (result.action, result.reason_code) == ("archive", "llm_junk")
    assert _s2(trace).detail["gate_version"] == JUNK_GATE_VERSION
    unsure = _Filter("drop", DROP_BELOW_RELEVANCE + 0.1)
    result, trace = _gate(_WHOLE, rereading=None, relevance=unsure)
    assert (result.action, result.reason_code) == ("park", "llm_junk_unconfident")
    assert _s2(trace).detail["gate_version"] == JUNK_GATE_VERSION


def test_the_filter_version_is_a_digest_of_what_judges_never_a_literal():
    """A hand-typed version is the one somebody forgets to bump (`semantic/profiles.py` U3: 260
    cached extractions survived a prompt fix). Any edit to either prompt or to the threshold that
    turns a "drop" into an archive is a different filter."""
    from genios_engine.capture.gate import relevance as R

    assert junk_gate_version() == JUNK_GATE_VERSION
    assert junk_gate_version(single=R._GATE_PROMPT + " ") != JUNK_GATE_VERSION
    assert junk_gate_version(batch=R._GATE_BATCH_PROMPT.replace("KEEP", "Keep")) != JUNK_GATE_VERSION
    assert junk_gate_version(drop_below=DROP_BELOW_RELEVANCE + 0.05) != JUNK_GATE_VERSION


# ── the gate judges a re-judgment again, S2 included ──────────────────────────────────────────

def test_a_rejudgment_meets_todays_filter_again():
    """The re-read skip (STEP-05) is for a mail already KEPT. A junk archive was never kept."""
    model = _junk()
    result, trace = _gate(_WHOLE, rereading=LLM_JUNK_REJUDGE, relevance=model)
    assert len(model.read) == 1, "a re-judgment was waved through without the junk filter"
    assert (result.action, result.reason_code) == ("archive", "llm_junk")
    assert result.whitelist_code != "W-06", "a re-judgment is not a re-read of a kept mail"
    assert _s2(trace).detail["gate_version"] == JUNK_GATE_VERSION
    assert _s2(trace).detail.get("rejudging") == LLM_JUNK_REJUDGE
    keep = _Filter("keep")
    result, _ = _gate(_WHOLE, rereading=LLM_JUNK_REJUDGE, relevance=keep)
    assert (result.action, result.route, len(keep.read)) == ("route", "needs_extraction", 1)


def test_a_rejudgment_meets_todays_rules_too():
    """Re-judging is the CURRENT gate on the whole message — a rule the whole headers now trip
    archives it under its own code, a fact that is never re-admitted."""
    result, _ = _gate(_UNSUBSCRIBE, rereading=LLM_JUNK_REJUDGE, relevance=_Filter("keep"))
    assert (result.action, result.reason_code) == ("archive", "N-02")


def test_a_kept_mail_read_again_still_never_meets_the_filter():
    """The control: every other re-read keeps STEP-05's skip."""
    model = _junk()
    result, _ = _gate(_WHOLE, rereading=unread.EXTRACTION_NEVER_RAN, relevance=model)
    assert (result.action, result.whitelist_code, model.read) == ("route", "W-06", [])


# ── the ladder never rebuilds a re-judgment from its snippet ─────────────────────────────────

def _ladder_row(reason_code: str, payload: dict, key: str, **over) -> SimpleNamespace:
    return SimpleNamespace(**{
        "event_id": "evt_rj", "connection_id": "c", "source": "gmail",
        "object_type": "email_message", "source_object_id": "m1", "parent_object_id": None,
        "dedup_key": "gmail:email_message:m1", "internal_kind": None, "recipients": [],
        "actor": {"type": "external_contact", "email": "intros@boardy.test"},
        "occurred_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
        "enc_content": encrypt(json.dumps(payload), key), "reason_code": reason_code, **over})


def _whole_object(row) -> RawObject:
    return RawObject(source="gmail", object_type="email_message",
                     source_object_id=row.source_object_id, occurred_at=row.occurred_at,
                     actor_email="intros@boardy.test", raw=dict(_WHOLE))


def test_a_rejudgment_is_never_rebuilt_from_its_stored_snippet():
    key = os.environ["GENIOS_CRYPTO_KEY"]
    row = _ladder_row(LLM_JUNK_REJUDGE, _LIGHT, key)
    assert unread.to_raw_object(row, key) is None, "rebuilt from the snippet it was judged on"

    def _fails(_row):
        raise RuntimeError("provider refused")

    def _another(r):
        return replace(_whole_object(r), source_object_id="m2")

    for reader in (lambda _row: None, _fails, _another):
        assert unread.to_raw_object(row, key, whole=reader) is None

    asked: list[str] = []

    def _reader(r):
        asked.append(r.source_object_id)
        return _whole_object(r)

    raw = unread.to_raw_object(row, key, whole=_reader)
    assert asked == ["m1"]
    assert raw is not None and raw.rereading == LLM_JUNK_REJUDGE
    assert raw.raw["body"] == _WHOLE_BODY


def test_a_kept_mail_is_still_read_from_what_was_stored():
    key = os.environ["GENIOS_CRYPTO_KEY"]
    raw = unread.to_raw_object(_ladder_row(unread.EXTRACTION_NEVER_RAN, _WHOLE, key), key,
                               whole=lambda _row: pytest.fail("a kept mail was fetched again"))
    assert raw is not None and raw.rereading == unread.EXTRACTION_NEVER_RAN


def test_the_rejudge_code_belongs_to_the_reread_ladder():
    """In a drain class, or it is counted and walked past (D2); the ladder's, because the ladder
    is the door that reads it — the drain only files it."""
    assert LLM_JUNK_REJUDGE in NEEDS_REEXTRACTION
    assert LLM_JUNK_REJUDGE not in RE_ADJUDICABLE
    assert "llm_junk" in RE_ADJUDICABLE and "llm_junk_unconfident" in RE_ADJUDICABLE


# ── the drain → re-read path, on Postgres ─────────────────────────────────────────────────────

_TABLES = ("event_trace", "raw_payloads", "prepared_content", "parked_events", "source_events",
           "l1_semantic_activation")


@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres drain tests skipped")
    from genios_engine.capture.connectors.push_ingest import PushIngestWiring
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.capture.parked.store import PostgresParkedStore
    from genios_engine.capture.payload_store import PostgresRawPayloadStore
    from genios_engine.capture.prepared_store import PostgresPreparedContentStore
    from genios_engine.capture.trace_store import PostgresTraceRepository
    from genios_engine.platform.db import get_engine

    org = f"org_rejudge_{uuid.uuid4().hex[:10]}"
    engine = get_engine(live_db_url)
    # Read when the test runs, an hour ahead: the ladder takes nothing captured in its last
    # `UNREAD_GRACE`, and the rows here are captured at the database's own `now()`.
    now = datetime.now(timezone.utc) + timedelta(hours=1)
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'junk re-judgment')"), {"o": org})
        c.execute(text("insert into l1_semantic_activation (org_id, enabled_at, enabled_by) "
                       "values (:o, :at, 'test')"), {"o": org, "at": now - timedelta(days=30)})
    key = os.environ["GENIOS_CRYPTO_KEY"]

    def wiring(relevance):
        return PushIngestWiring(
            repo=PostgresSourceEventRepository(live_db_url),
            trace_repo=PostgresTraceRepository(live_db_url),
            payload_store=PostgresRawPayloadStore(live_db_url, key),
            prepared_store=PostgresPreparedContentStore(live_db_url),
            parked_store=PostgresParkedStore(live_db_url), relevance=relevance)

    yield SimpleNamespace(engine=engine, org=org, key=key, now=now, wiring=wiring)
    with engine.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _capture(pg, oid: str, raw: dict, relevance):
    """One message through the real door, judged by `relevance` — the event it landed as."""
    from genios_engine.capture.connectors.push_ingest import ingest_pushed_objects

    obj = RawObject(source="gmail", object_type="email_message", source_object_id=oid,
                    occurred_at=pg.now - timedelta(days=2), actor_email="intros@boardy.test",
                    raw=dict(raw))
    out = ingest_pushed_objects((obj,), org_id=pg.org, connection_id="conn_gmail",
                                wiring=pg.wiring(relevance))
    return out.results[0]


def _judged_by_an_older_filter(pg, event_id: str) -> None:
    with pg.engine.begin() as c:
        assert c.execute(text(
            "update event_trace set detail = jsonb_set(detail, '{gate_version}', "
            "       to_jsonb(cast('junk-older' as text))) "
            " where org_id = :o and event_id = :e and stage = 'S2' and action = 'archive'"),
            {"o": pg.org, "e": event_id}).rowcount == 1


def _ledger(pg) -> dict[str, tuple]:
    with pg.engine.connect() as c:
        return {r.event_id: (r.outcome, r.route, r.reason_code, r.status) for r in c.execute(text(
            "select se.event_id, se.outcome, se.route, pe.reason_code, pe.status "
            "  from source_events se left join parked_events pe on pe.event_id = se.event_id "
            " where se.org_id = :o"), {"o": pg.org})}


def _hand_written_judgment(pg, *, outcome: str, action: str, detail: dict) -> str:
    """A judged stop the way an older gate wrote it — no version in its trace."""
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    with pg.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, payload_ref) "
            "values (:e, :o, 'conn_gmail', 'gmail', 'email_message', :e, :dk, "
            " cast('{}' as jsonb), :at, :at, :out, :pay)"),
            {"e": event_id, "o": pg.org, "dk": compute_dedup_key("gmail", "email_message",
                                                                 event_id, None),
             "at": pg.now - timedelta(days=9), "out": outcome, "pay": f"pay_{event_id}"})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:p, :o, :e, 'application/json', :enc, :exp)"),
            {"p": f"pay_{event_id}", "o": pg.org, "e": event_id,
             "enc": encrypt(json.dumps(_LIGHT), pg.key), "exp": pg.now + timedelta(days=90)})
        c.execute(text(
            "insert into event_trace (org_id, event_id, stage, action, reason_code, detail) "
            "values (:o, :e, 'S2', :a, 'llm_junk', cast(:d as jsonb))"),
            {"o": pg.org, "e": event_id, "a": action, "d": json.dumps(detail)})
    return event_id


@pytest.mark.pg
def test_a_junk_verdict_with_no_recorded_filter_stands(pg):
    """Every verdict written before this unit: archived, and a legacy drop — neither re-admitted."""
    archived = _hand_written_judgment(pg, outcome="archived", action="archive",
                                      detail={"relevance": 0.05})
    dropped = _hand_written_judgment(pg, outcome="dropped", action="drop", detail={})

    out = drain_parked(pg.engine, org_id=pg.org, now=pg.now)

    assert (out["reinjected"], out["rejudge"], out["examined"]) == (0, 0, 0)
    ledger = _ledger(pg)
    assert ledger[archived] == ("archived", None, None, None)
    assert ledger[dropped] == ("dropped", None, None, None)


@pytest.mark.pg
def test_a_junk_verdict_todays_filter_made_stands(pg):
    res = _capture(pg, "m_today", _LIGHT, _junk())
    assert res.outcome == "archived"

    for _ in range(2):                                    # every heartbeat, not only the first
        out = drain_parked(pg.engine, org_id=pg.org, now=pg.now)
        assert (out["reinjected"], out["rejudge"], out["examined"]) == (0, 0, 0)
    assert _ledger(pg)[res.event.event_id] == ("archived", None, None, None)


def _reread(pg, row, relevance, *, whole):
    """The ladder's own steps, in `api/routes._reread_unread`'s order: rebuild, set aside, capture
    through the push door, restore what did not land, settle."""
    from genios_engine.capture.connectors.push_ingest import ingest_pushed_objects

    obj = unread.to_raw_object(row, pg.key, whole=whole)
    handed = [] if obj is None else [row.event_id]
    out = None
    if obj is not None:
        assert unread.set_aside(pg.engine, pg.org, handed) == 1
        out = ingest_pushed_objects((obj,), org_id=pg.org, connection_id="conn_gmail",
                                    wiring=pg.wiring(relevance))
    restored = unread.restore(pg.engine, pg.org, handed)
    settled = unread.settle_parked_extractions(pg.engine, pg.org, [row.event_id], now=pg.now)
    return out, restored, settled


@pytest.mark.pg
@pytest.mark.parametrize("today, lands_as", [("keep", "emitted"), ("drop", "archived")])
def test_an_older_filters_junk_is_rejudged_on_its_whole_message(pg, today, lands_as):
    old = _capture(pg, f"m_older_{today}", _LIGHT, _junk())
    assert old.outcome == "archived"
    _judged_by_an_older_filter(pg, old.event.event_id)

    # 1 · The drain files it for re-judgment and flips NOTHING: the archive is still read by no model.
    out = drain_parked(pg.engine, org_id=pg.org, now=pg.now)
    assert (out["rejudge"], out["reinjected"]) == (1, 0)
    assert _ledger(pg)[old.event.event_id] == ("archived", None, LLM_JUNK_REJUDGE, "pending")
    assert drain_parked(pg.engine, org_id=pg.org, now=pg.now)["rejudge"] == 0, "filed twice"

    # 2 · A re-read that cannot fetch the whole message never takes it — it waits, unspent.
    assert unread.queue_unread(pg.engine, pg.org, now=pg.now) == 0
    assert unread.find_parked_extractions(pg.engine, pg.org, now=pg.now) == []
    due = unread.find_parked_extractions(pg.engine, pg.org, now=pg.now, rejudge=True)
    assert [r.event_id for r in due] == [old.event.event_id]

    # 3 · Read on the WHOLE message, through today's gate — S2 included.
    fetched: list[str] = []

    def _whole(row):
        fetched.append(row.source_object_id)
        return replace(_whole_object(row), occurred_at=pg.now - timedelta(days=2))

    model = _Filter(today, 0.9 if today == "keep" else 0.05)
    landed, restored, settled = _reread(pg, due[0], model, whole=_whole)

    assert fetched == [f"m_older_{today}"]
    assert len(model.read) == 1, "today's filter never judged the re-judgment"
    assert "pilot contract" in model.read[0], "judged on the snippet, not the whole message"
    new = landed.results[0]
    assert new.outcome == lands_as and restored == 0 and settled["superseded"] == 1
    ledger = _ledger(pg)
    assert ledger[old.event.event_id] == ("superseded", None, LLM_JUNK_REJUDGE, "superseded")
    assert ledger[new.event.event_id][0] == lands_as
    if lands_as == "emitted":
        assert ledger[new.event.event_id][1] == "needs_extraction"

    # 4 · Today's verdict, whichever it is, now stands: nothing is filed again.
    out = drain_parked(pg.engine, org_id=pg.org, now=pg.now)
    assert (out["rejudge"], out["reinjected"]) == (0, 0)


@pytest.mark.pg
def test_a_rejudgment_whose_whole_message_never_comes_stays_archived(pg):
    old = _capture(pg, "m_unfetchable", _LIGHT, _junk())
    _judged_by_an_older_filter(pg, old.event.event_id)
    drain_parked(pg.engine, org_id=pg.org, now=pg.now)
    row = unread.find_parked_extractions(pg.engine, pg.org, now=pg.now, rejudge=True)[0]

    landed, restored, settled = _reread(pg, row, _Filter("keep"), whole=lambda _row: None)

    assert (landed, restored, settled["advanced"]) == (None, 0, 1)
    assert _ledger(pg)[old.event.event_id] == ("archived", None, LLM_JUNK_REJUDGE, "pending")
    # The ladder is bounded: past it the re-judgment is given up, and the archive still stands.
    with pg.engine.begin() as c:
        c.execute(text("update parked_events set refetch_attempts = :n where event_id = :e"),
                  {"n": unread.MAX_EXTRACTION_ATTEMPTS, "e": old.event.event_id})
    assert unread.give_up_parked_extractions(pg.engine, pg.org, now=pg.now) == 0, (
        "a caller that cannot read a re-judgment must not spend it")
    assert unread.give_up_parked_extractions(pg.engine, pg.org, now=pg.now, rejudge=True) == 1
    assert _ledger(pg)[old.event.event_id] == ("archived", None, LLM_JUNK_REJUDGE, "dead_letter")
    with pg.engine.connect() as c:
        why = c.execute(text("select refetch_last_error from parked_events where event_id = :e"),
                        {"e": old.event.event_id}).scalar()
    assert "re-judg" in why and "archive" in why, why
    assert drain_parked(pg.engine, org_id=pg.org, now=pg.now)["rejudge"] == 0


@pytest.mark.pg
def test_a_set_aside_rejudgment_goes_back_as_an_archive(pg):
    """`restore` and the orphan recovery put a row back as `emitted` — right for a kept mail, a
    silent re-admission for an archive under re-judgment."""
    old = _capture(pg, "m_aside", _LIGHT, _junk())
    _judged_by_an_older_filter(pg, old.event.event_id)
    drain_parked(pg.engine, org_id=pg.org, now=pg.now)

    assert unread.set_aside(pg.engine, pg.org, [old.event.event_id]) == 1
    assert unread.restore(pg.engine, pg.org, [old.event.event_id]) == 1
    assert _ledger(pg)[old.event.event_id][0] == "archived"

    assert unread.set_aside(pg.engine, pg.org, [old.event.event_id]) == 1
    assert unread.recover_orphans(pg.engine, pg.org) == 1
    assert _ledger(pg)[old.event.event_id][0] == "archived"


@pytest.mark.pg
def test_a_promotion_overtakes_a_pending_rejudgment(pg):
    """A promotion is a decision someone made; a re-judgment must not archive it again. The kept
    mail joins the ladder as a mail nothing read, and its re-read never meets the filter."""
    from genios_engine.capture.landing.promote import promote_archived

    old = _capture(pg, "m_promoted", _LIGHT, _junk())
    _judged_by_an_older_filter(pg, old.event.event_id)
    drain_parked(pg.engine, org_id=pg.org, now=pg.now)
    assert promote_archived(pg.engine, pg.org, rule="llm_junk", apply=True,
                            now=pg.now).promoted == 1

    assert unread.queue_unread(pg.engine, pg.org, now=pg.now) == 1
    due = unread.find_parked_extractions(pg.engine, pg.org, now=pg.now, rejudge=True)
    assert [(r.event_id, r.reason_code) for r in due] == [(old.event.event_id,
                                                           unread.EXTRACTION_NEVER_RAN)]


@pytest.mark.pg
def test_an_unconfident_junk_park_is_read_and_not_judged_again(pg):
    """The stated rule for `llm_junk_unconfident` (module docstring): re-admitted on the next
    heartbeat, no version check, read without meeting the filter that was unsure."""
    unsure = _Filter("drop", DROP_BELOW_RELEVANCE + 0.1)
    res = _capture(pg, "m_unsure", _WHOLE, unsure)
    assert res.outcome == "parked"

    out = drain_parked(pg.engine, org_id=pg.org, now=pg.now)
    assert out["by_reason"]["llm_junk_unconfident"] == {"seen": 1, "reinjected": 1}
    assert unread.queue_unread(pg.engine, pg.org, now=pg.now) == 1
    due = unread.find_parked_extractions(pg.engine, pg.org, now=pg.now)
    assert [(r.event_id, r.reason_code) for r in due] == [(res.event.event_id,
                                                           unread.EXTRACTION_NEVER_RAN)]

    model = _junk()
    landed, _restored, settled = _reread(pg, due[0], model, whole=None)
    assert model.read == [], "an unconfident verdict met the filter again"
    assert landed.results[0].outcome == "emitted" and settled["superseded"] == 1


@pytest.mark.pg
def test_until_the_reread_can_fetch_whole_messages_a_rejudgment_waits(pg, monkeypatch):
    """Production today: `api/routes._reread_unread` hands the ladder no whole-message reader, so
    a filed re-judgment is neither read on its snippet nor spent — it waits, `pending`, counted."""
    from genios_engine.api import routes

    old = _capture(pg, "m_waiting", _LIGHT, _junk())
    _judged_by_an_older_filter(pg, old.event.event_id)
    drain_parked(pg.engine, org_id=pg.org, now=pg.now)

    conn = SimpleNamespace(connection_id="conn_gmail", org_id=pg.org, source_type="gmail")
    handed: list = []
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=pg.engine))
    monkeypatch.setattr(routes, "_connections", SimpleNamespace(
        get=lambda cid: conn if cid == conn.connection_id else None,
        list_active=lambda source_type=None: [conn]))
    monkeypatch.setattr(routes, "_llm_over_daily_cap", lambda _org: False)
    monkeypatch.setattr(routes, "_push_wiring_for", lambda _conn: "wiring")
    monkeypatch.setattr(routes, "_l1_stores", lambda: None)
    monkeypatch.setattr(routes, "ingest_pushed_objects",
                        lambda objs, **_kw: handed.extend(objs) or SimpleNamespace(results=[]))
    monkeypatch.setattr(routes, "finalize_l1", lambda *_a, **_k: None)

    assert routes._reread_unread(pg.org) == 0
    assert handed == []
    assert _ledger(pg)[old.event.event_id] == ("archived", None, LLM_JUNK_REJUDGE, "pending")
    with pg.engine.connect() as c:
        assert c.execute(text("select refetch_attempts from parked_events where event_id = :e"),
                         {"e": old.event.event_id}).scalar() == 0
    out = drain_parked(pg.engine, org_id=pg.org, now=pg.now)
    assert out["needs_reextraction"] == 1 and out["by_reason"][LLM_JUNK_REJUDGE]["seen"] == 1
