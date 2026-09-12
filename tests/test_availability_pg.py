"""Availability against a REAL Postgres (pg_store — skipped unless GENIOS_TEST_DATABASE_URL is set).

The whole path, not a stub of it: an out-of-office email with an OOO subject goes through L1 (no
longer dropped), lands in source_events + raw_payloads, is drained by the L2 runner, and becomes a
`person.availability` window with the right dates on the right person. Then the windowed-fact
semantics the hermetic suite cannot reach: coexistence, supersede-on-restate, corroboration,
out-of-order history, the calendar lane, and the health / merge invariants."""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
from genios_engine.capture.payload_store import PostgresRawPayloadStore
from genios_engine.capture.pipeline import capture_event
from genios_engine.context.availability import (AVAILABILITY_FIELD, availability_for_person,
                                                load_org_windows, org_availability,
                                                owner_availability_facts)
from genios_engine.context.health import _INTEGRITY_CHECKS
from genios_engine.context.merge import _resolve_duplicate_facts
from genios_engine.capture.gate.rules import availability_marker
from genios_engine.context.pipeline import process_event
from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.context.structured import commit_structured
from tests.test_l2_db_e2e import _FakeLLM, _seed_org

NOW = datetime(2026, 9, 10, 9, tzinfo=timezone.utc)
_DUPES_SQL = next(sql for kind, _, sql in _INTEGRITY_CHECKS if kind == "duplicate_active_fact")
#: Per-run suffix: the ledger dedups by (org, source object) and windows persist, so fixed org ids
#: would make a second run against the same scratch database test the first run's leftovers.
_RUN = uuid.uuid4().hex[:8]


def _org(name: str) -> str:
    return f"{name}_{_RUN}"


def _canned(availability, **kw) -> dict:
    out = {"relevance": 0.15, "noise_type": "automated", "domains": [], "entity_mentions": [],
           "roles": [], "fact_candidates": [], "commitments": [], "scheduling_proposals": [],
           "questions": [], "observations": [], "availability": availability}
    out.update(kw)
    return out


def _windows(store, org: str, status: str = "active") -> list:
    with store.engine.connect() as c:
        return c.execute(text(
            "select f.subject_node_id, f.fact_id, f.value, f.authority_rank, n.canonical_key "
            "from graph_facts f join graph_nodes n on n.node_id = f.subject_node_id "
            "where f.org_id=:o and f.field=:f and f.status=:st order by f.value->>'from'"),
            {"o": org, "f": AVAILABILITY_FIELD, "st": status}).fetchall()


def _dupes(store, org: str) -> int:
    with store.engine.connect() as c:
        return int(c.execute(text(_DUPES_SQL), {"o": org}).scalar() or 0)


def _email(store, org, eid, *, at, body, claims, marker="leave_notice", sender="anisha@acme.io"):
    return process_event(org_id=org, event_id=eid, source="gmail", content=body,
                         sender_email=sender, occurred_at=at, llm=_FakeLLM(_canned(claims)),
                         store=store, is_inbound=True, availability_marker=marker)


def test_subject_ooo_email_flows_l1_to_l2_and_writes_the_window(pg_store):
    org = _org("avail_e2e")
    _seed_org(pg_store, org)
    url, key = os.environ["GENIOS_TEST_DATABASE_URL"], os.environ["GENIOS_CRYPTO_KEY"]
    body = ("I am on leave from 15th to 22nd September with limited access to email. "
            "Is this urgent? For the audit docs please contact Priya.")
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="ooo-msg-1",
                    occurred_at=NOW, actor_email="anisha@acme.io",
                    actor_type="external_contact", recipients=("founder@us.io",),
                    raw={"subject": "Automatic reply: audit docs due 19th", "body": body,
                         "snippet": body[:120], "to": ["founder@us.io"], "labelIds": ["INBOX"]})

    # L1 — the OOO subject used to be an N-05 DROP. Now: emitted, marked, drained last.
    res = capture_event(raw, org_id=org, connection_id="conn_gmail",
                        repo=PostgresSourceEventRepository(url),
                        payload_store=PostgresRawPayloadStore(url, key))
    assert res.outcome == "emitted"
    assert res.gated.availability_marker == "auto_reply"
    with pg_store.engine.connect() as c:
        outcome = c.execute(text("select outcome from source_events where org_id=:o "
                                 "and event_id=:e"), {"o": org, "e": res.event.event_id}).scalar()
    assert outcome == "emitted"

    # S4 no longer reads the responder's Auto-Submitted header as a broadcast.
    assert res.esqe.relevance.relevant and res.esqe.relevance.rule == "availability_notice"

    # L2 — through the production seam: Layer 1's typed extraction (the `availability` lane,
    # quoted words only) adapted without another model call, marker re-derived from the payload.
    qualified = adapt_qes_extraction({
        "intent": "inform", "stance": "neutral", "model_snapshot": "test-snapshot",
        "prompt_version": "test", "schema_version": "1", "extraction_profile": "email",
        "input_tokens": 0, "output_tokens": 0,
        "questions": ["Is this urgent?"],
        "availability": [{"person": "sender", "kind": "leave", "from": "from 15th",
                          "to": "22nd September", "coverage_person": "Priya",
                          "evidence_text": "I am on leave from 15th to 22nd September"}]},
        confidence_bp=3500)
    l2 = process_event(org_id=org, event_id=res.event.event_id, source="gmail",
                       content=body, sender_email="anisha@acme.io",
                       recipient_emails=["founder@us.io"], occurred_at=NOW, llm=None,
                       store=pg_store, is_inbound=True, qualified_extraction=qualified,
                       availability_marker=availability_marker(raw.raw))
    assert l2.outcome == "committed"

    [w] = _windows(pg_store, org)
    assert w.canonical_key == "anisha@acme.io"
    assert w.value == {"kind": "leave", "from": "2026-09-15", "to": "2026-09-22",
                       "cover": "Priya"}
    assert w.authority_rank == 2 and w.fact_id == f"avail:{w.subject_node_id}:2026-09-15"

    # An auto-reply is not the counterparty answering: no reply-needed state, no open question.
    with pg_store.engine.connect() as c:
        thread_facts = c.execute(text(
            "select count(*) from graph_facts where org_id=:o and subject_node_id=:n "
            "and field like 'thread.%'"), {"o": org, "n": w.subject_node_id}).scalar()
        questions = c.execute(text(
            "select count(*) from graph_observations where org_id=:o and kind='question'"),
            {"o": org}).scalar()
        noise_kind = c.execute(text(
            "select kind from graph_observations where org_id=:o and kind like 'email_noise:%'"),
            {"o": org}).scalar()
    assert thread_facts == 0 and questions == 0
    assert noise_kind == "email_noise:auto_reply"

    # Reads: the person view, the team view, and the reasoners' owner facts.
    with pg_store.engine.connect() as c:
        mine = availability_for_person(c, org_id=org, email="Anisha@acme.io",
                                       on=date(2026, 9, 12))
        team = org_availability(c, org_id=org, start=date(2026, 9, 18), end=date(2026, 9, 20))
        idx = load_org_windows(c, org_id=org)
    assert [x.value()["from"] for x in mine] == ["2026-09-15"]
    assert [x.person_key for x in team] == ["anisha@acme.io"]
    owner = owner_availability_facts({"deal.owner": {"value": "anisha@acme.io"}}, idx,
                                     on=date(2026, 9, 19))
    assert owner["owner.availability"]["value"] == "on_leave"
    assert owner["owner.availability_bp"]["value"] == 0


def test_windows_coexist_supersede_corroborate_and_keep_history(pg_store):
    org = _org("avail_windows")
    _seed_org(pg_store, org)
    b1 = "Heads up: I am on leave from 15th to 22nd September."
    _email(pg_store, org, "w1", at=NOW, body=b1,
           claims=[{"person": "sender", "kind": "leave", "from": "from 15th",
                    "to": "22nd September", "evidence_text": b1[10:]}])
    b2 = "Also travelling 5-7 Oct for the Bengaluru offsite."
    _email(pg_store, org, "w2", at=NOW + timedelta(days=1), body=b2,
           claims=[{"person": "sender", "kind": "travel", "from": "5-7 Oct",
                    "evidence_text": "travelling 5-7 Oct"}])
    assert [w.value["from"] for w in _windows(pg_store, org)] == ["2026-09-15", "2026-10-05"]

    # a later message MOVES the leave: the overlapping earlier window is superseded, not stacked
    b3 = "Update: my leave is now 16th to 24th September."
    _email(pg_store, org, "w3", at=NOW + timedelta(days=2), body=b3,
           claims=[{"person": "sender", "kind": "leave", "from": "16th",
                    "to": "24th September", "evidence_text": "my leave is now 16th to 24th"}])
    active = _windows(pg_store, org)
    assert [(w.value["from"], w.value["to"]) for w in active] == [
        ("2026-09-16", "2026-09-24"), ("2026-10-05", "2026-10-07")]
    assert [w.value["from"] for w in _windows(pg_store, org, "superseded")] == ["2026-09-15"]

    # an undated auto-reply on the 17th is the same absence seen again — corroboration only
    b4 = "I am out of office with limited access to email."
    _email(pg_store, org, "w4", at=datetime(2026, 9, 17, 8, tzinfo=timezone.utc), body=b4,
           marker="auto_reply",
           claims=[{"person": "sender", "kind": "ooo", "evidence_text": "I am out of office"}])
    assert len(_windows(pg_store, org)) == 2
    with pg_store.engine.connect() as c:
        corroborations = c.execute(text(
            "select count(*) from graph_source_refs where org_id=:o and event_id='w4' "
            "and evidence->>'corroborates' = 'true'"), {"o": org}).scalar()
    assert corroborations == 1

    # restating the SAME start with a new end supersedes in place and keeps the fact identity
    held_id = _windows(pg_store, org)[0].fact_id
    b5 = "Extending: leave 16th to 25th September."
    _email(pg_store, org, "w5", at=NOW + timedelta(days=3), body=b5,
           claims=[{"person": "sender", "kind": "leave", "from": "16th",
                    "to": "25th September", "evidence_text": "leave 16th to 25th September"}])
    first = _windows(pg_store, org)[0]
    assert first.value["to"] == "2026-09-25" and first.fact_id == held_id

    # an OLDER message replayed late never overwrites the current window — it lands as history
    b6 = "Leave 16th to 18th September."
    _email(pg_store, org, "w6", at=NOW - timedelta(days=5), body=b6,
           claims=[{"person": "sender", "kind": "leave", "from": "16th",
                    "to": "18th September", "evidence_text": "Leave 16th to 18th September"}])
    assert _windows(pg_store, org)[0].value["to"] == "2026-09-25"
    assert "2026-09-18" in [w.value["to"] for w in _windows(pg_store, org, "historical")]

    # two active windows on one (person, field) are NOT a duplicate, and a merge keeps both
    assert _dupes(pg_store, org) == 0
    with pg_store.engine.begin() as c:
        assert _resolve_duplicate_facts(c, org, first.subject_node_id) == []


def test_named_person_and_unknown_person(pg_store):
    org = _org("avail_named")
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as c:
        ravi = pg_store.find_or_create_node(c, org_id=org, node_type="person",
                                            canonical_key="ravi@acme.io", display_name="Ravi",
                                            event_id=None)
        from genios_engine.context.identity import observe_person_name
        observe_person_name(c, org_id=org, node_id=ravi, name="Ravi", event_id=None)
    body = "Team: Ravi kal se 3 din chutti pe hai. Some Stranger is away next week."
    _email(pg_store, org, "n1", at=NOW, body=body, sender="lead@acme.io",
           claims=[{"person": "Ravi", "kind": "chutti", "from": "kal se 3 din",
                    "evidence_text": "Ravi kal se 3 din chutti"},
                   {"person": "Some Stranger", "kind": "ooo", "from": "next week",
                    "evidence_text": "Some Stranger is away next week"}])
    [w] = _windows(pg_store, org)                  # the unknown name anchors nothing
    assert w.subject_node_id == ravi
    assert (w.value["from"], w.value["to"]) == ("2026-09-11", "2026-09-13")


def test_calendar_block_writes_moves_and_cancels_without_touching_email_windows(pg_store):
    org = _org("avail_cal")
    _seed_org(pg_store, org)
    body = "Sick today, back tomorrow."
    _email(pg_store, org, "mail1", at=NOW, body=body,
           claims=[{"person": "sender", "kind": "sick", "from": "today",
                    "evidence_text": "Sick today"}])

    def _cal(eid, start, end, status="confirmed", updated="2026-09-01T10:00:00Z"):
        return commit_structured(
            pg_store, org_id=org, event_id=eid, source="gcal", source_object_id="cal_ooo_1",
            structured_fields={"meeting.title": "Out of office", "meeting.status": status},
            node_type="meeting", occurred_at=NOW, display_name="Out of office",
            availability={"person": "anisha@acme.io", "kind": "ooo", "from": start, "to": end,
                          "cancelled": status == "cancelled", "title": "Out of office",
                          "updated": updated})

    _cal("c1", "2026-10-01", "2026-10-03")
    cal = [w for w in _windows(pg_store, org) if w.value["kind"] == "ooo"]
    assert [(w.value["from"], w.authority_rank) for w in cal] == [("2026-10-01", 3)]

    _cal("c2", "2026-10-02", "2026-10-04", updated="2026-09-05T10:00:00Z")   # block moved
    assert [(w.value["from"], w.value["to"]) for w in _windows(pg_store, org)
            if w.value["kind"] == "ooo"] == [("2026-10-02", "2026-10-04")]

    _cal("c3", "2026-10-02", "2026-10-04", status="cancelled")               # block cancelled
    remaining = _windows(pg_store, org)
    assert [w.value["kind"] for w in remaining] == ["sick"]                  # email window intact
    assert _dupes(pg_store, org) == 0


def test_ooo_email_goes_gate_l1_qes_l2_to_person_availability(pg_store, monkeypatch):
    """THE WHOLE ROAD, production entry points only: `run_sync` (the sync door, with
    `api/routes._run_ledger` as its ledger hook — where the floor, lifecycle and publication run)
    and `context/runner.process_pending` (the drain). Only the model and the mailbox are doubles.

    gate: the responder's OOO subject + Auto-Submitted header no longer drop (N-05), and skip
          the junk gate · L1: the semantic lane files an `availability` lane claim, S4 relevance
          keeps it (`availability_notice`), ALG-15 detects `availability_change`, the floor —
          the REAL default 2500, not a test floor — passes it, and it is published ·
    L2:   `_pull` finds it through `qualified_signals`, the adapter carries the lane, and the
          window lands as `person.availability` on the sender with no reply-needed state.
    """
    from genios_engine.api import routes
    from genios_engine.capture import pipeline as P
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.connectors.base import SourceBatch
    from genios_engine.capture.esqe import qualification as Q
    from genios_engine.capture.esqe.signal_store import PostgresSignalStore
    from genios_engine.capture.prepared_store import PostgresPreparedContentStore
    from genios_engine.capture.semantic.cache import PostgresExtractionCache
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings
    from tests.test_l2_reads_what_l1_publishes import _FakeLLM as _ModelDouble
    from tests.test_l2_reads_what_l1_publishes import _fresh_org

    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    org = _org("avail_qes")
    owner = "founder@us.test"
    _fresh_org(pg_store, org)
    subject = "Automatic reply: audit docs due 19th"
    body = ("Anisha here. I am on leave from 15th to 22nd September with limited access to "
            "email. For the audit docs please contact Priya.")

    def cite(quote: str) -> list[dict]:
        start = body.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    l1_answer = {
        "intent": "inform", "stance": "neutral",
        "entity_mentions": [{"surface_form": "Anisha", "entity_type": "person",
                             "evidence": cite("Anisha"), "confidence_bp": 9000}],
        "availability": [{"person": "sender", "kind": "leave", "from": "from 15th",
                          "to": "22nd September", "coverage_person": "Priya",
                          "evidence_text": "I am on leave from 15th to 22nd September"}],
    }

    class _Mailbox:
        source = "gmail"

        def validate_connection(self) -> bool:
            return True

        def _objects(self):
            return [RawObject(
                source="gmail", object_type="email_message", source_object_id=f"ooo_{org}",
                occurred_at=NOW, actor_email="anisha@acme.test", actor_type="external_contact",
                recipients=(owner,), parent_object_id=f"thr_{org}",
                raw={"subject": subject, "body": body, "to": [owner],
                     "headers": {"Auto-Submitted": "auto-replied"}})]

        def initial_snapshot(self, cursor=None, limit=50):
            return SourceBatch(objects=self._objects(), next_cursor=None)

        def incremental_changes(self, cursor=None, limit=50, since=None):
            return SourceBatch(objects=self._objects(), next_cursor=None)

    signals = PostgresSignalStore(url)
    monkeypatch.setattr(routes, "_graph", pg_store, raising=False)
    monkeypatch.setattr(routes, "_floor_store",
                        Q.InMemoryFloorStore({org: Q.DEFAULT_FLOOR_BP}), raising=False)
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger(), raising=False)
    monkeypatch.setattr(routes, "_lifecycle_store", None, raising=False)
    monkeypatch.setattr(routes, "_signal_store", signals, raising=False)
    summary = run_sync(
        _Mailbox(), org_id=org, connection_id=f"con_{org}", source="gmail", mode="backfill",
        repo=PostgresSourceEventRepository(url),
        payload_store=PostgresRawPayloadStore(url, get_settings().crypto_key),
        prepared_store=PostgresPreparedContentStore(url), mailbox_owner=owner,
        semantic=P.SemanticLane(llm=_ModelDouble(l1_answer), eval_time=NOW,
                                cache=PostgresExtractionCache(url)),
        esqe=P.EsqeStage(eval_time=NOW, org_domains=("us.test",)),
        run_ledger=routes._run_ledger)
    assert summary.emitted == 1, f"the OOO email did not get through L1: {summary}"

    published = [r for r in signals.list(org) if r.signal_type == "availability_change"]
    assert published, (f"Layer 1 published no availability_change: "
                       f"{[r.signal_type for r in signals.list(org)]}")

    out = process_pending(org_id=org, store=pg_store, llm=_ModelDouble({}),
                          crypto_key=get_settings().crypto_key)
    assert out["processed"] >= 1, f"the drain never read the published event: {out}"

    [w] = _windows(pg_store, org)
    assert w.canonical_key == "anisha@acme.test"
    assert w.value == {"kind": "leave", "from": "2026-09-15", "to": "2026-09-22",
                       "cover": "Priya"}
    with pg_store.engine.connect() as c:
        thread_facts = c.execute(text(
            "select count(*) from graph_facts where org_id=:o and subject_node_id=:n "
            "and field like 'thread.%'"), {"o": org, "n": w.subject_node_id}).scalar()
    assert thread_facts == 0, "an auto-reply put the ball in our court"
