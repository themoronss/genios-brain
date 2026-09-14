"""Screen promoter against real Postgres — P2 acceptance 1, 2, 9, 10 + P9 K3 (one memory build
per page / chat per interval, verdict routing, the runaway guard).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/scratch pytest tests/test_screen_promoter_pg.py

Deltas are inserted through P1's own `CaptureStore.insert_deltas` (encrypted), and promoted
through the promoter's DEFAULT doors — the Composio webhook's wiring over the scratch database —
with the relevance gate's model replaced by a stub that counts calls.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


class _CountingLLM:
    model = "stub"

    def __init__(self):
        self.calls = 0
        self._lock = threading.Lock()

    def call(self, prompt, max_tokens=None):
        with self._lock:
            self.calls += 1
        return SimpleNamespace(ok=True, model="stub", usage=None,
                               parsed={"disposition": "keep", "relevance": 0.9, "reason": "s"})


def _doors(llm):
    from genios_engine.capture.gate.relevance import LLMRelevanceClassifier
    from genios_engine.capture.screen.relevance import ScreenDocRelevance
    from genios_engine.platform import screen_promoter as SP
    base = SP.default_doors()

    def wiring_for(org_id, seat_email, connection_id):
        w = base.wiring_for(org_id, seat_email, connection_id)
        assert w.semantic is None                 # no model key in tests → no extraction lane
        # the stub model replaces the org's gate; the thread verdicts (C9 / K3) stay wired
        return replace(w, relevance=ScreenDocRelevance(LLMRelevanceClassifier(llm),
                                                       w.relevance.verdicts))
    return SP.Doors(wiring_for=wiring_for, stores=base.stores, enqueue=base.enqueue)


def _org(activated=True, tz="Asia/Kolkata"):
    org = f"org_scr_{uuid.uuid4().hex[:8]}"
    seat, email = f"seat_{uuid.uuid4().hex[:6]}", f"rohit_{uuid.uuid4().hex[:4]}@acme.test"
    with _engine().begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, vals = ["id"], {"id": org}
        for r in reqd:
            cols.append(r.column_name)
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt) else False
                                   if dt == "boolean" else "{}" if dt in ("json", "jsonb")
                                   else f"x_{org}")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                       f"({', '.join(':' + x for x in cols)})"), vals)
        c.execute(text("update orgs set timezone = :tz where id = :o"), {"tz": tz, "o": org})
        c.execute(text("insert into org_seats (org_id, seat_id, email) values (:o, :s, :e)"),
                  {"o": org, "s": seat, "e": email})
        if activated:
            c.execute(text("insert into l1_semantic_activation (org_id, enabled_by) "
                           "values (:o, 'test')"), {"o": org})
    return org, seat, email


def _chat(key="li:conv:abc:2026-09-17T10", wm=5, text_="Can you send the deck?", out=False):
    return {"session_key": key, "thread_key": "li:conv:abc", "app": "linkedin",
            "title": "Priya Shah",
            "participants": [{"name": "Priya Shah",
                              "linkedin_url": "https://www.linkedin.com/in/priyashah"},
                             {"self": True, "name": "Rohit"}],
            "messages": [{"sender": "self" if out else "Priya Shah",
                          "ts": "2026-09-17T10:41:40+05:30", "text": text_,
                          "is_outgoing": out}],
            "message_watermark": wm, "captured_at": "2026-09-17T10:42:03+05:30"}


def _doc(i):
    return {"session_key": f"doc:erp:{i}", "thread_key": f"doc:erp.acme.test/inv/{i}",
            "app": "generic", "title": f"Invoice {i}", "bundle_id": "com.acme.erp",
            "blocks": [{"role": "kv", "label": "Invoice", "value": f"INV-{i}"},
                       {"role": "kv", "label": "Due", "value": "2026-09-30"},
                       {"role": "kv", "label": "Status", "value": "Unpaid"}],
            "message_watermark": 1, "captured_at": "2026-09-17T10:42:03+05:30"}


def _insert(org, seat, sessions, device="dev_1"):
    from genios_engine.platform.capture_policy import CaptureStore
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt
    rows = [{"session_key": s["session_key"], "message_watermark": s["message_watermark"],
             "seat_id": seat, "app": s["app"], "thread_key": s["thread_key"],
             "payload_enc": encrypt(json.dumps(s), get_settings().crypto_key),
             "message_count": len(s.get("messages") or s.get("blocks")),
             "captured_at": s["captured_at"]} for s in sessions]
    return CaptureStore(_engine()).insert_deltas(rows, org_id=org, device_id=device,
                                                 now=datetime.now(timezone.utc))


def _rows(org):
    with _engine().connect() as c:
        return c.execute(text(
            "select session_key, message_watermark, device_id, status, attempts, event_ids, "
            "not_before, last_error from screen_session_deltas where org_id=:o "
            "order by received_at, session_key, message_watermark"), {"o": org}).fetchall()


def _events(org):
    with _engine().connect() as c:
        return c.execute(text(
            "select event_id, source_object_id, visibility_scope, visibility_principals, "
            "visibility_derived_from, connection_id, outcome from source_events "
            "where org_id=:o and source='screen_session' order by source_object_id"),
            {"o": org}).fetchall()


def _drain(doors, worker="w1", **kw):
    from genios_engine.platform import screen_promoter as SP
    kw.setdefault("interval_minutes", 0)          # P2 acceptance: promote at once unless asked
    n = 0
    while SP.run_once(_engine(), worker, doors=doors, **kw):
        n += 1
        assert n < 50
    return n


# ── acceptance 1 ────────────────────────────────────────────────────────────────────────────
def test_two_promoters_racing_one_delta_promote_it_once():
    from genios_engine.platform import screen_promoter as SP
    org, seat, email = _org()
    _insert(org, seat, [_chat()])
    llm = _CountingLLM()
    doors = _doors(llm)
    barrier = threading.Barrier(2)
    ran = []

    def go(w):
        barrier.wait()
        ran.append(SP.run_once(_engine(), w, doors=doors, interval_minutes=0))
    threads = [threading.Thread(target=go, args=(f"w{i}",)) for i in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    _drain(doors)                    # whatever the other racers left (other orgs' rows too)
    rows = _rows(org)
    assert [(r.status, r.attempts) for r in rows] == [("promoted", 1)]
    ev = _events(org)
    assert len(ev) == 1 and rows[0].event_ids == [ev[0].event_id]
    assert (ev[0].visibility_scope, list(ev[0].visibility_principals),
            ev[0].visibility_derived_from, ev[0].connection_id) == (
        "private", [email], "device:screen_session:seat", f"screen:{seat}")
    assert ev[0].outcome == "emitted"
    assert llm.calls == 1
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from l2_work_queue where org_id=:o "
                              "and source='screen_session'"), {"o": org}).scalar() == 1


def test_an_expired_lease_is_reclaimed_and_a_live_one_is_not():
    from genios_engine.platform import screen_promoter as SP
    org, seat, _ = _org()
    _insert(org, seat, [_chat()])
    e = _engine()
    claims = []
    while True:                                   # claim until OUR org's batch is the one taken
        got = SP.claim_batch(e, "A")
        assert got is not None
        claims.append(got)
        if got[0] == org:
            break
    assert SP.claim_batch(e, "B") is None or SP.claim_batch(e, "B")[0] != org
    with e.begin() as c:
        c.execute(text("update screen_session_deltas set lease_until = now() - interval '1 s' "
                       "where org_id=:o"), {"o": org})
    again = SP.claim_batch(e, "B")
    while again is not None and again[0] != org:
        again = SP.claim_batch(e, "B")
    assert again is not None and again[2][0].attempts == 2
    with e.begin() as c:                          # release every row this test claimed
        c.execute(text("update screen_session_deltas set lease_until = null, claimed_by = null "
                       "where claimed_by in ('A', 'B')"))


def test_an_unactivated_org_stays_held():
    org, seat, _ = _org(activated=False)
    _insert(org, seat, [_chat()])
    _drain(_doors(_CountingLLM()))
    assert [(r.status, r.attempts) for r in _rows(org)] == [("held", 0)]
    assert _events(org) == []


# ── acceptance 2 ────────────────────────────────────────────────────────────────────────────
def test_watermark_five_then_nine_is_two_events_and_a_replay_of_nine_is_none():
    org, seat, _ = _org()
    doors = _doors(_CountingLLM())
    _insert(org, seat, [_chat(wm=5, text_="Can you send the deck?")])
    _drain(doors)
    _insert(org, seat, [_chat(wm=9, text_="Also the pricing, please")])
    _drain(doors)
    assert [e.source_object_id for e in _events(org)] == ["li:conv:abc#5#in", "li:conv:abc#9#in"]
    assert _insert(org, seat, [_chat(wm=9)]) == set()      # same device: the upload's own PK
    _insert(org, seat, [_chat(wm=9, text_="Also the pricing, please")], device="dev_2")
    _drain(doors)
    assert len(_events(org)) == 2
    last = _rows(org)[-1]
    assert (last.device_id, last.status, last.last_error) == ("dev_2", "skipped", "duplicate")


# ── acceptance 9 (P9 K3: the runaway guard replaces the generic daily cap) ─────────────────────
def test_over_the_runaway_guard_a_thread_is_deferred_to_local_midnight_and_reported():
    from genios_engine.platform import screen_promoter as SP
    from genios_engine.platform.capture_policy import CaptureStore
    from genios_engine.platform.config import get_settings
    assert get_settings().screen_memory_max_builds_per_day == 400
    assert get_settings().screen_memory_interval_minutes == 60
    assert not hasattr(get_settings(), "screen_generic_daily_cap")
    org, seat, _ = _org(tz="Asia/Kolkata")
    llm = _CountingLLM()
    doors = _doors(llm)
    _insert(org, seat, [_doc(i) for i in range(41)])
    now = datetime.now(timezone.utc)
    _drain(doors, cap=40)
    rows = _rows(org)
    assert sum(r.status == "promoted" for r in rows) == 40
    deferred = [r for r in rows if r.status == "deferred"]
    assert len(deferred) == 1 and deferred[0].last_error == SP.DAILY_GUARD
    assert deferred[0].attempts == 0                          # a deferral is not a failure
    assert deferred[0].not_before == SP.next_local_midnight(now, "Asia/Kolkata")
    assert llm.calls == 0                                     # record-shaped: the rule decided
    assert len(_events(org)) == 40
    assert CaptureStore(_engine()).catching_up(org, seat) == 1      # K6
    _drain(doors, cap=40)                                     # still today: nothing moves
    assert sum(r.status == "deferred" for r in _rows(org)) == 1
    with _engine().begin() as c:                              # … the next local day
        c.execute(text("update screen_session_deltas set not_before = now() - interval '1 s' "
                       "where org_id=:o and status='deferred'"), {"o": org})
        c.execute(text("update rate_counters set window_start = window_start - 1 "
                       "where scope_key = :k"), {"k": SP.seat_scope(org, seat)})
    _drain(doors, cap=40)
    assert {r.status for r in _rows(org)} == {"promoted"}
    assert len(_events(org)) == 41
    assert CaptureStore(_engine()).catching_up(org, seat) == 0


# ── P9 K3 ───────────────────────────────────────────────────────────────────────────────────
def test_one_chat_is_one_memory_build_per_interval_with_all_its_messages(monkeypatch):
    from genios_engine.capture.connectors import push_ingest
    from genios_engine.platform import screen_promoter as SP
    org, seat, _ = _org()
    llm = _CountingLLM()
    doors = _doors(llm)
    seen = []
    real = push_ingest.ingest_pushed_objects

    def spy(objects, **kw):
        seen.append(objects)
        return real(objects, **kw)
    monkeypatch.setattr(push_ingest, "ingest_pushed_objects", spy)

    _insert(org, seat, [_chat(wm=5, text_="Can you send the deck?"),
                        _chat(wm=6, text_="And the pricing sheet"),
                        _chat(wm=7, text_="By Friday please")])
    _drain(doors, interval_minutes=60)
    rows = _rows(org)
    assert {(r.status, r.last_error, r.attempts) for r in rows} == {
        ("held", SP.INTERVAL_WAIT, 0)}                        # waiting is not an attempt
    assert len({r.not_before for r in rows}) == 1 and _events(org) == [] and seen == []
    _insert(org, seat, [_chat(wm=8, text_="Thanks!")])        # later content: the SAME clock
    _drain(doors, interval_minutes=60)
    assert len({r.not_before for r in _rows(org)}) == 1
    with _engine().begin() as c:                              # … the hour passes
        c.execute(text("update screen_session_deltas set not_before = now() - interval '1 s', "
                       "received_at = received_at - interval '61 minutes' where org_id=:o"),
                  {"o": org})
    _drain(doors, interval_minutes=60)
    rows = _rows(org)
    ev = _events(org)
    assert [e.source_object_id for e in ev] == ["li:conv:abc#8#in"]      # ONE event
    assert {r.status for r in rows} == {"promoted"}
    assert all(r.event_ids == [ev[0].event_id] for r in rows)
    ((obj,),) = seen
    for line in ("Can you send the deck?", "And the pricing sheet", "By Friday please",
                 "Thanks!"):
        assert line in obj.raw["body"]
    assert llm.calls == 1                                     # one gate call for the chat
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from rate_counters where scope_key=:k "
                              "and kind=:kind"), {"k": SP.seat_scope(org, seat),
                                                  "kind": SP.MEMORY_KIND}).scalar() == 1


def test_a_memory_verdict_routes_the_thread_with_no_gate_call():
    org, seat, _ = _org()
    now = datetime.now(timezone.utc)
    with _engine().begin() as c:
        for thread, work, memory in (("li:conv:abc", True, False), ("li:conv:keep", True, True),
                                     ("li:conv:fam", False, False)):
            c.execute(text("insert into screen_thread_verdicts (org_id, seat_id, thread_key, "
                           "work, memory, judged_at) values (:o, :s, :t, :w, :m, :now)"),
                      {"o": org, "s": seat, "t": thread, "w": work, "m": memory, "now": now})
    llm = _CountingLLM()
    _insert(org, seat, [_chat(), {**_chat(key="k2"), "thread_key": "li:conv:keep"},
                        {**_chat(key="k3"), "thread_key": "li:conv:fam"}])
    _drain(_doors(llm))
    assert llm.calls == 0                                     # every verdict decided alone
    out = {e.source_object_id: e.outcome for e in _events(org)}
    assert out["li:conv:keep#5#in"] == "emitted"
    assert out["li:conv:abc#5#in"] != "emitted" and out["li:conv:fam#5#in"] != "emitted"
    with _engine().connect() as c:                  # parked = KEPT (recoverable), never dropped
        assert c.execute(text("select count(*) from parked_events where org_id=:o"),
                         {"o": org}).scalar() == 2


# ── acceptance 10 ───────────────────────────────────────────────────────────────────────────
def test_seat_removal_shreds_deltas_and_screen_payloads_but_not_another_seats():
    from genios_engine.platform.capture_policy import shred_seat_capture
    org, seat, _ = _org()
    other = f"seat_{uuid.uuid4().hex[:6]}"
    with _engine().begin() as c:
        c.execute(text("insert into org_seats (org_id, seat_id, email) values (:o, :s, :e)"),
                  {"o": org, "s": other, "e": f"{other}@acme.test"})
    doors = _doors(_CountingLLM())
    _insert(org, seat, [_chat(out=True, text_="I'll send the proposal by Friday")])
    _insert(org, other, [_chat(key="li:conv:zz:1", text_="Pricing attached?")], device="dev_9")
    _drain(doors)
    ev = {e.connection_id: e.event_id for e in _events(org)}
    assert set(ev) == {f"screen:{seat}", f"screen:{other}"}

    def counts(event_id):
        with _engine().connect() as c:
            return tuple(c.execute(text(f"select count(*) from {t} where event_id=:e"),
                                   {"e": event_id}).scalar()
                         for t in ("raw_payloads", "prepared_content"))
    assert counts(ev[f"screen:{seat}"]) == (1, 1)
    with _engine().begin() as c:
        assert shred_seat_capture(c, org_id=org, seat_id=seat) == 1
    assert counts(ev[f"screen:{seat}"]) == (0, 0)
    assert counts(ev[f"screen:{other}"]) == (1, 1)
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from screen_session_deltas where org_id=:o "
                              "and seat_id=:s"), {"o": org, "s": seat}).scalar() == 0
        assert c.execute(text("select count(*) from screen_session_deltas where org_id=:o "
                              "and seat_id=:s"), {"o": org, "s": other}).scalar() == 1


def test_undecryptable_payload_parks_at_once():
    org, seat, _ = _org()
    _insert(org, seat, [_chat()])
    with _engine().begin() as c:
        c.execute(text("update screen_session_deltas set payload_enc = 'garbage'::bytea "
                       "where org_id=:o"), {"o": org})
    _drain(_doors(_CountingLLM()))
    r = _rows(org)[0]
    assert r.status == "parked" and r.last_error.startswith("undecryptable")


# ── SCREEN_INTEL_SYSTEM_DESIGN phase 1 · the one judge's items become graph memory (S3) ────────
def test_instant_mode_writes_the_judges_items_on_their_person_once_with_no_model_call():
    from genios_engine.platform import screen_promoter as SP
    from genios_engine.platform.config import get_settings
    assert get_settings().screen_memory_mode == "instant"
    org, seat, email = _org()
    assert SP.default_doors().wiring_for(org, email, f"screen:{seat}").semantic is None
    now = datetime.now(timezone.utc)
    with _engine().begin() as c:
        c.execute(text("insert into screen_thread_verdicts (org_id, seat_id, thread_key, work, "
                       "memory, judged_at) values (:o, :s, 'li:conv:abc', true, true, :now)"),
                  {"o": org, "s": seat, "now": now})
        for fid, kind, who, quote in (("fu_a", "ask", "Priya Shah (Acme)", "send the deck"),
                                      ("fu_b", "deadline", None, "the board meets Friday")):
            c.execute(text(
                "insert into screen_followups (id, org_id, seat_id, thread_key, kind, text, who, "
                "topic_key, quote) values (:i, :o, :s, 'li:conv:abc', :k, :t, :w, :tk, :q)"),
                {"i": fid + org[-6:], "o": org, "s": seat, "k": kind, "t": f"{kind} note",
                 "w": who, "tk": fid + org, "q": quote})
    llm = _CountingLLM()
    _insert(org, seat, [_chat()])
    _drain(_doors(llm))
    assert llm.calls == 0                        # the verdict decided; no heavy read, no AI gate
    (ev,) = [e for e in _events(org) if e.outcome == "emitted"]
    with _engine().connect() as c:
        rows = c.execute(text("select kind, graph_written_at, subject_node_id from "
                              "screen_followups where org_id=:o order by kind"), {"o": org}).all()
        obs = c.execute(text(
            "select o.kind, o.subject_node_id, n.display_name from graph_observations o "
            "left join graph_nodes n on n.org_id = o.org_id and n.node_id = o.subject_node_id "
            "and n.valid_to is null where o.org_id=:o and o.created_by_event_id=:e "
            "and o.kind like 'screen.%' order by o.kind"), {"o": org, "e": ev.event_id}).all()
    assert all(r.graph_written_at is not None for r in rows)
    assert [o.kind for o in obs] == ["screen.ask", "screen.deadline"]
    assert obs[0].display_name == "Priya Shah" and obs[0].subject_node_id == rows[0].subject_node_id
    # once: the next promotion of the same chat writes nothing again
    _insert(org, seat, [_chat(key="li:conv:abc:2026-09-17T11", wm=9, text_="any update?")])
    _drain(_doors(llm))
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from graph_observations where org_id=:o "
                              "and kind like 'screen.%'"), {"o": org}).scalar() == 2
