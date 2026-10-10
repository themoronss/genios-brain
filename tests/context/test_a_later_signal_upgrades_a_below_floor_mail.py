"""STEP-05's "a later signal upgrades it" — measured: no door can publish one, so the clause is struck.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_later_signal_upgrades_a_below_floor_mail.py -q

`yc2_w27_align` M34.C2.L-logic.V0.U06. STEP-05 §3.2 promised that a mail which entered memory with no
signal — below the floor since `06` D20 — would be "upgraded rather than skipped" when a signal landed
for it later; nothing built or tested it (`10-BEFORE-STEP-12` §2). Measured first, as the unit asked:
can a signal be published for such a mail after its run is settled?

  * a second read of the same mail, by any sync, is a duplicate, and a duplicate never reaches S4: it
    carries no signal for the floor to judge (`capture/pipeline.CaptureResult.esqe`);
  * the floor judges a capture's own results and nothing else (`capture/esqe/qualification.
    scored_signals_for`), at every door that publishes (`finalize_l1` — a sweep, a push, an upload, a
    screen session, a re-read);
  * the re-read ladder takes only a kept mail nothing ever read — no extraction, which a below-floor
    mail always has (`capture/landing/unread._NEVER_READ`) — and what it does read again lands as a
    NEW event, the old row set aside `superseded`, which is no kept outcome, so it leaves the queue.

No later signal can reach a settled below-floor mail, so the clause is struck from STEP-05 with this
file as its measurement. The last test states what a door that one day did publish one would meet —
a settled run is never pulled again — so such a door must bring the re-read with it.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.esqe.qualification import scored_signals_for
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.context.memory_lanes import KEPT_OUTCOMES
from genios_engine.contracts.source_event import compute_dedup_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
FOUNDER = "founder.u06@gmail.com"
NEEL = "neel@insight.test"


class _Mailbox:
    source = "gmail"

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return self.incremental_changes()

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=[RawObject(
            source="gmail", object_type="email_message", source_object_id="m_u06",
            occurred_at=NOW - timedelta(days=3), actor_email=NEEL, recipients=(FOUNDER,),
            raw={"subject": "Insight", "body": "Good to meet you last week.", "thread_depth": 1})],
            next_cursor=None)

    def fetch_content(self, object_ref: str) -> dict:
        return {}


def test_a_second_read_of_the_same_mail_is_a_duplicate_with_nothing_to_publish():
    repo = InMemorySourceEventRepository()
    first = run_sync(_Mailbox(), org_id="org_u06", connection_id="con_u06", repo=repo,
                     mailbox_owner=FOUNDER)
    again = run_sync(_Mailbox(), org_id="org_u06", connection_id="con_u06", repo=repo,
                     mailbox_owner=FOUNDER)
    assert [r.outcome for r in first.results] == ["emitted"]
    assert [r.outcome for r in again.results] == ["duplicate"]
    assert again.results[0].esqe is None, "a duplicate reached S4"
    assert scored_signals_for(again, scorer=None, eval_time=NOW) == ()


# ── a below-floor mail, settled by the real drain ────────────────────────────────────────────────

@pytest.fixture
def settled(pg_store):
    """One mail Layer 1 read and the floor did not publish — its extraction, no signal — drained."""
    from genios_engine.context import runner
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt
    from tests.context.test_qes_adapter import QUOTE, extraction

    org, event_id = f"org_u06_{uuid.uuid4().hex[:8]}", f"evt_u06_{uuid.uuid4().hex[:8]}"
    key = get_settings().crypto_key
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Meera Iyer', :e)"),
                  {"o": org, "e": FOUNDER})
        c.execute(text("insert into l1_semantic_activation (org_id, enabled_at, enabled_by) "
                       "values (:o, :at, 'test')"), {"o": org, "at": NOW - timedelta(days=30)})
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, recipients, occurred_at, captured_at, outcome, "
            " parent_object_id) values (:e, :o, 'con_u06', 'gmail', 'email_message', :mid, :dk, "
            " cast(:a as jsonb), :r, :at, :at, 'emitted', :thr)"),
            {"e": event_id, "o": org, "mid": f"m_{event_id}",
             "dk": compute_dedup_key("gmail", "email_message", f"m_{event_id}"),
             "a": json.dumps({"type": "external_contact", "email": NEEL}),
             "r": [FOUNDER], "at": NOW - timedelta(days=3), "thr": f"thr_{event_id}"})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": org, "e": event_id, "exp": NOW + timedelta(days=180),
             "enc": encrypt(json.dumps({"subject": "Renewal", "body": QUOTE, "to": [FOUNDER],
                                        "labelIds": ["INBOX"]}), key)})
        c.execute(text(
            "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
            "values (:e, :o, :id, :t)"), {"e": event_id, "o": org, "id": f"pc_{event_id}",
                                          "t": f"Renewal\n\n{QUOTE}"})
        c.execute(text(
            "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
            " profile_id, tier) values (:k, :o, :e, cast(:out as jsonb), 'email', 'T2')"),
            {"k": f"x_{event_id}", "o": org, "e": event_id,
             "out": json.dumps(extraction().model_dump(mode="json"))})
    runner.process_pending(org_id=org, store=pg_store, llm=None, crypto_key=key, eval_time=NOW)
    yield pg_store, org, event_id
    from genios_engine.api.account_routes import _wipe
    with pg_store.engine.begin() as c:
        _wipe(c, org)
        for table in ("context_correlation_members", "context_situations", "context_correlations",
                      "l1_semantic_activation"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _run(store, org, event_id) -> str | None:
    with store.engine.connect() as c:
        return c.execute(text("select status from l2_processing_runs where org_id = :o "
                              " and event_id = :e"), {"o": org, "e": event_id}).scalar()


@pytest.mark.pg
def test_the_mail_entered_memory_below_the_floor_and_its_run_is_settled(settled):
    store, org, event_id = settled
    assert _run(store, org, event_id) == "done"
    with store.engine.connect() as c:
        assert c.execute(text("select count(*) from qualified_signals where org_id = :o"),
                         {"o": org}).scalar() == 0


@pytest.mark.pg
def test_the_re_read_ladder_never_takes_a_mail_layer_1_read(settled):
    from genios_engine.capture.landing import unread
    store, org, event_id = settled
    assert unread.queue_unread(store.engine, org, now=NOW) == 0
    with store.engine.begin() as c:                     # the control: unread, the ladder takes it
        c.execute(text("delete from l1_extraction_results where org_id = :o and event_id = :e"),
                  {"o": org, "e": event_id})
    assert unread.queue_unread(store.engine, org, now=NOW) == 1


@pytest.mark.pg
def test_a_mail_read_again_is_a_new_event_and_the_old_row_leaves_the_queue(settled):
    """What the ladder reads again lands under its own key as a new event; the old row it set aside
    is `superseded`, which no road takes."""
    from genios_engine.capture.landing import unread
    from genios_engine.context.runner import _pull
    store, org, event_id = settled
    assert unread.SUPERSEDED not in KEPT_OUTCOMES
    with store.engine.begin() as c:
        c.execute(text("delete from l2_processing_runs where org_id = :o and event_id = :e"),
                  {"o": org, "e": event_id})
    assert event_id in {r.event_id for r in _pull(store, org, 50)}, "the control: unsettled, it is pulled"
    assert unread.set_aside(store.engine, org, [event_id]) == 1
    assert event_id not in {r.event_id for r in _pull(store, org, 50)}


@pytest.mark.pg
def test_a_signal_no_door_publishes_would_never_be_read_so_such_a_door_brings_the_re_read(settled):
    """Stated, not wished: if a signal ever did land for a settled below-floor mail, the drain would
    not read the mail again — the run is `done` — and memory would keep its below-floor reading."""
    from genios_engine.context.runner import _pull
    store, org, event_id = settled
    with store.engine.begin() as c:
        c.execute(text(
            "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
            " importance_bp, importance_version, confidence_bp, visibility, extraction_ref, "
            " evidence_refs, state, occurred_at) values (:s, :o, :e, :t, 'approval_requested', 6000, "
            " 'alg17-v1', 8000, cast('{\"scope\": \"org\"}' as jsonb), :x, cast('[\"ev\"]' as jsonb), "
            " 'active', :at)"),
            {"s": f"sig_{event_id}", "o": org, "e": event_id, "t": f"t_{event_id}",
             "x": f"x_{event_id}", "at": NOW})
    assert event_id not in {r.event_id for r in _pull(store, org, 50)}
    assert _run(store, org, event_id) == "done"
    with store.engine.begin() as c:                     # the control: unsettled, its signal is read
        c.execute(text("delete from l2_processing_runs where org_id = :o and event_id = :e"),
                  {"o": org, "e": event_id})
    assert [r.has_signal for r in _pull(store, org, 50) if r.event_id == event_id] == [True]
