"""S4 · the hourly short screen-memory update via the Message Batches API, against real Postgres.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/scratch pytest tests/test_screen_memory_batch_pg.py

Threads are promoted through the promoter's default doors (instant mode, no model key); the
Anthropic batch client is a fake — no network.
"""
from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from tests.test_screen_promoter_pg import URL, _chat, _doors, _drain, _engine, _insert, _org
from tests.test_screen_promoter_pg import _CountingLLM

pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]


class FakeBatches:
    """`client.messages.batches`: create / retrieve / results, answered by `respond(job_id)`."""

    def __init__(self, respond=None):
        self.created: list[list[dict]] = []
        self.ended: set[str] = set()
        self.respond = respond or (lambda jid: _errored())
        self.retrieved = 0

    def create(self, *, requests):
        requests = list(requests)
        self.created.append(requests)
        return SimpleNamespace(id=f"msgbatch_{len(self.created)}",
                               processing_status="in_progress")

    def retrieve(self, batch_id):
        self.retrieved += 1
        return SimpleNamespace(id=batch_id, processing_status="ended" if batch_id in self.ended
                               else "in_progress")

    def results(self, batch_id):
        n = int(batch_id.rsplit("_", 1)[1])
        return iter([SimpleNamespace(custom_id=r["custom_id"], result=self.respond(r["custom_id"]))
                     for r in self.created[n - 1]])


def _client(batches):
    return SimpleNamespace(messages=SimpleNamespace(batches=batches))


def _ok(payload: dict):
    msg = SimpleNamespace(model="claude-haiku-4-5",
                          content=[SimpleNamespace(type="text", text=json.dumps(payload))],
                          usage=SimpleNamespace(input_tokens=1000, output_tokens=100))
    return SimpleNamespace(type="succeeded", message=msg)


def _errored():
    return SimpleNamespace(type="errored", error=SimpleNamespace(
        type="error", error=SimpleNamespace(type="overloaded_error")))


@pytest.fixture(autouse=True)
def _isolate():
    """The queue is global: park every other test's open jobs so a tick sees only this test's."""
    with _engine().begin() as c:
        c.execute(text("update screen_memory_jobs set status = 'failed', text_enc = null, "
                       "error = 'isolated by test' where status in ('queued', 'submitted')"))
    yield


def _jobs(org):
    with _engine().connect() as c:
        return c.execute(text(
            "select id, thread_key, event_id, status, attempts, batch_id, text_enc, error, "
            "created_at, result from screen_memory_jobs where org_id = :o order by created_at"),
            {"o": org}).fetchall()


def _promote(org, seat, sessions):
    _insert(org, seat, sessions)
    _drain(_doors(_CountingLLM()))


def _verdict(org, seat, thread, work, memory):
    from datetime import datetime, timezone
    with _engine().begin() as c:
        c.execute(text("insert into screen_thread_verdicts (org_id, seat_id, thread_key, work, "
                       "memory, judged_at) values (:o, :s, :t, :w, :m, :now)"),
                  {"o": org, "s": seat, "t": thread, "w": work, "m": memory,
                   "now": datetime.now(timezone.utc)})


# ── enqueue ─────────────────────────────────────────────────────────────────────────────────────
def test_a_promoted_work_thread_is_queued_once_and_a_personal_one_is_not():
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import decrypt
    org, seat, _ = _org()
    _verdict(org, seat, "li:conv:fam", False, False)
    _verdict(org, seat, "li:conv:nomem", True, False)
    _promote(org, seat, [_chat(),                                        # unjudged → queued
                         {**_chat(key="k2", text_="Dinner at 8?"), "thread_key": "li:conv:fam"},
                         {**_chat(key="k3"), "thread_key": "li:conv:nomem"}])
    (job,) = _jobs(org)
    assert (job.thread_key, job.status, job.attempts) == ("li:conv:abc", "queued", 0)
    body = decrypt(bytes(job.text_enc), get_settings().crypto_key)
    assert "Can you send the deck?" in body and len(body) <= 6000
    with _engine().connect() as c:
        assert c.execute(text("select event_ids from screen_session_deltas where org_id=:o "
                              "and thread_key='li:conv:abc'"), {"o": org}).scalar() == [
            job.event_id]


def test_nothing_is_queued_when_the_batch_update_is_off(monkeypatch):
    from genios_engine.platform.config import get_settings
    monkeypatch.setattr(get_settings(), "screen_memory_batch_enabled", False)
    org, seat, _ = _org()
    _promote(org, seat, [_chat()])
    assert _jobs(org) == []


# ── submit → results ────────────────────────────────────────────────────────────────────────────
def test_tick_submits_after_the_wait_and_a_later_tick_writes_memory(monkeypatch):
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.identity import observe_person_name
    from genios_engine.reason.llm_sites import tier_model
    from genios_engine.reason.moments import screen_memory_batch as B
    org, seat, email = _org()
    with _engine().begin() as c:
        priya = GraphStore(engine=_engine()).find_or_create_node(
            c, org_id=org, node_type="person", canonical_key="priya@acme.test",
            display_name="Priya Shah", event_id=None)
        observe_person_name(c, org_id=org, node_id=priya, name="Priya Shah")
    _promote(org, seat, [_chat(text_="Can you send the deck by Friday? Pricing next week.")])
    (job,) = _jobs(org)
    payload = {"work": True, "summary": "Priya (Acme) wants the deck.\nPricing comes next week.",
               "items": [
                   {"kind": "ask", "text": "Send Priya the deck", "who": "Priya Shah",
                    "due": None, "quote": "Can you send the deck by Friday?"},
                   {"kind": "their_promise", "text": "Priya shares pricing next week",
                    "who": email, "due": None, "quote": "Pricing next week"},
                   {"kind": "risk", "text": "Invented", "who": None, "due": None,
                    "quote": "words that are not on the screen"}]}
    fake = FakeBatches(lambda jid: _ok(payload))
    client = _client(fake)

    assert B.tick(_engine(), now=job.created_at + timedelta(minutes=5), client=client)[
        "submitted"] == 0                                      # the oldest waited only 5 min
    assert B.tick(_engine(), now=job.created_at + timedelta(minutes=11), client=client)[
        "submitted"] == 1
    ((req,),) = fake.created
    assert req["custom_id"] == job.id
    p = req["params"]
    assert (p["model"], p["temperature"], p["max_tokens"]) == (tier_model("T1"), 0, 500)
    prompt = p["messages"][0]["content"]
    assert email in prompt and "The next 14 days" in prompt and "Can you send the deck" in prompt
    (sub,) = _jobs(org)
    assert (sub.status, sub.batch_id) == ("submitted", "msgbatch_1") and sub.text_enc is not None

    later = job.created_at + timedelta(minutes=30)
    assert B.tick(_engine(), now=later, client=client)["results"] == {}   # still processing
    fake.ended.add("msgbatch_1")
    assert B.tick(_engine(), now=later, client=client)["results"] == {"done": 1}

    (done,) = _jobs(org)
    assert done.status == "done" and done.text_enc is None
    assert done.result["items"] == 2 and done.result["summary"] is True
    with _engine().connect() as c:
        fus = {r.kind: r for r in c.execute(text(
            "select kind, who, quote, graph_written_at, subject_node_id, thread_key "
            "from screen_followups where org_id = :o"), {"o": org})}
        obs = c.execute(text(
            "select kind from graph_observations where org_id = :o and created_by_event_id = :e "
            "and kind like 'screen.%' order by kind"), {"o": org, "e": job.event_id}).scalars().all()
        summary = B.thread_summary(c, org_id=org, seat_id=seat, thread_key="li:conv:abc",
                                   now=later)
        costs = c.execute(text("select model, input_tokens, output_tokens from llm_costs "
                               "where org_id = :o and purpose = 'screen_memory_batch'"),
                          {"o": org}).fetchall()
    assert set(fus) == {"ask", "their_promise"}                   # the ungrounded risk dropped
    assert fus["ask"].quote == "Can you send the deck by Friday?"
    assert fus["ask"].subject_node_id == priya and fus["ask"].graph_written_at is not None
    assert fus["their_promise"].who is None                       # the manager is never "who"
    assert obs == ["screen.ask", "screen.their_promise"]
    assert summary == "Priya (Acme) wants the deck.\nPricing comes next week."
    assert [(c.model, c.input_tokens, c.output_tokens) for c in costs] == [
        ("claude-haiku-4-5", 1000, 100)]

    # idempotent: a crashed tick that re-reads the same result writes nothing twice
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt
    with _engine().begin() as c:
        c.execute(text("update screen_memory_jobs set status = 'submitted', text_enc = :t "
                       "where id = :i"),
                  {"t": encrypt("Can you send the deck by Friday? Pricing next week.",
                                get_settings().crypto_key), "i": job.id})
    assert B.tick(_engine(), now=later + timedelta(minutes=1), client=client)["results"] == {
        "done": 1}
    assert B.tick(_engine(), now=later + timedelta(minutes=2), client=client)["results"] == {}
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from screen_followups where org_id=:o"),
                         {"o": org}).scalar() == 2
        assert c.execute(text("select count(*) from graph_observations where org_id=:o "
                              "and kind like 'screen.%'"), {"o": org}).scalar() == 2
        assert c.execute(text("select count(*) from screen_thread_summaries where org_id=:o"),
                         {"o": org}).scalar() == 1


def test_an_errored_result_is_retried_then_failed_after_three_attempts():
    from genios_engine.reason.moments import screen_memory_batch as B
    org, seat, _ = _org()
    _promote(org, seat, [_chat()])
    (job,) = _jobs(org)
    class Ended(FakeBatches):                                     # every result errored, at once
        def retrieve(self, batch_id):
            return SimpleNamespace(id=batch_id, processing_status="ended")
    fake = Ended()
    now = job.created_at + timedelta(minutes=11)
    for i in range(4):
        B.tick(_engine(), now=now + timedelta(minutes=i), client=_client(fake))
    (j,) = _jobs(org)
    assert (j.status, j.attempts) == ("failed", 3) and j.text_enc is None
    assert j.error.startswith("errored") and len(fake.created) == 3
    B.tick(_engine(), now=now + timedelta(minutes=9), client=_client(fake))
    assert len(fake.created) == 3                                 # a failed job is never resent


def test_a_personal_result_is_skipped_and_the_thread_becomes_personal():
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import screen_memory_batch as B
    org, seat, _ = _org()
    _promote(org, seat, [_chat()])
    (job,) = _jobs(org)
    fake = FakeBatches(lambda jid: _ok({"work": False, "summary": None, "items": []}))
    now = job.created_at + timedelta(minutes=11)
    B.tick(_engine(), now=now, client=_client(fake))
    fake.ended.add("msgbatch_1")
    assert B.tick(_engine(), now=now, client=_client(fake))["results"] == {"skipped": 1}
    (j,) = _jobs(org)
    assert j.status == "skipped" and j.text_enc is None
    with _engine().connect() as c:
        v = F.thread_verdict(c, org_id=org, seat_id=seat, thread_key="li:conv:abc", now=now)
        assert c.execute(text("select count(*) from screen_followups where org_id=:o"),
                         {"o": org}).scalar() == 0
    assert v == {"work": False, "memory": False}
    assert B.personal(v)


def test_without_a_model_nothing_queued_is_lost(monkeypatch):
    from genios_engine.platform.config import get_settings
    from genios_engine.reason.moments import screen_memory_batch as B
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")      # no model configured
    org, seat, _ = _org()
    _promote(org, seat, [_chat()])
    (job,) = _jobs(org)
    assert B.default_client() is None
    out = B.tick(_engine(), now=job.created_at + timedelta(days=2))
    assert out == {"submitted": 0, "results": {}}
    (j,) = _jobs(org)
    assert (j.status, j.attempts) == ("queued", 0) and j.text_enc is not None


def test_summary_is_read_for_seven_days_only():
    from datetime import datetime, timezone
    from genios_engine.reason.moments import screen_memory_batch as B
    org, seat, _ = _org()
    now = datetime.now(timezone.utc)
    with _engine().begin() as c:
        c.execute(text("insert into screen_thread_summaries (org_id, seat_id, thread_key, summary, "
                       "updated_at) values (:o, :s, 't1', 'old news', :at)"),
                  {"o": org, "s": seat, "at": now - timedelta(days=8)})
        assert B.thread_summary(c, org_id=org, seat_id=seat, thread_key="t1", now=now) is None
        assert B.thread_summary(c, org_id=org, seat_id=seat, thread_key="t1",
                                now=now - timedelta(days=2)) == "old news"


def test_the_daemon_ticks_at_most_every_poll_interval(monkeypatch):
    from genios_engine.platform import screen_promoter as SP
    from genios_engine.reason.moments import screen_memory_batch as B
    calls = []
    monkeypatch.setattr(B, "tick", lambda engine, *a, **k: calls.append(1))
    monkeypatch.setitem(SP._housekeeping, "memory_batch", -1e18)
    assert SP.memory_batch_tick(_engine(), now=1000.0) is True
    assert SP.memory_batch_tick(_engine(), now=1030.0) is False
    assert SP.memory_batch_tick(_engine(), now=1061.0) is True
    assert len(calls) == 2
