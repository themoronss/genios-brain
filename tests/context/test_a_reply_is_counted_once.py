"""STEP-10 · a reply is counted once, and "their normal" needs five of them.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_reply_is_counted_once.py -q

`context/waiting.compute_waiting` (tree `yc2_w27_s10 · M29.C1.L-logic.V1.U02`). Measured on the golden set
(`STEP-10` §8.1): the only "normal reply times" that existed (F17: 35.98 days, F25: 1.92) each rested on ONE
reply, counted twice — the timeline read `thread.last_*` on every node, and the pipeline writes both on the
person and on the *"Thread with …"* node — so the tenant level's two-gap minimum was met by one message, and
the number was written on everyone who had never replied, with no n beside it. Now the cascade pools person
nodes only, needs `NORMAL_AT` (5, `06` D37) replies at the level it uses, writes the n beside the days and the
basis, and retires a cadence the evidence no longer carries. And since STEP-09 an introduction writes the turn
on the person introduced: the connector's mail is not THEIR message (`STEP-10` §8.3 N3), so it is no reply and
no "heard from".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.waiting import compute_waiting

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, brief, mention, node, process,
                               reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s10_counted_once"
NOW = T0 + timedelta(days=60)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _exchange(store, who: str, thread: str, asked: datetime, replied: datetime | None, i: int):
    process(store, ORG, event_id=f"evt_out_{i}", sender=FOUNDER, recipients=(who,), thread=thread,
            at=asked)
    if replied is not None:
        process(store, ORG, event_id=f"evt_in_{i}", sender=who, thread=thread, at=replied)


def _cadence(store, key: str) -> dict:
    """The current reply-cadence facts on the node keyed `key`: field → value."""
    with store.engine.connect() as c:
        return {r.field: r.value for r in c.execute(text(
            "select f.field, f.value from graph_facts f join graph_nodes n "
            "  on n.org_id = f.org_id and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = :k and f.valid_to is null "
            "   and f.field like 'party.reply_cadence%'"), {"o": ORG, "k": key})}


def _thread_cadence(store) -> int:
    with store.engine.connect() as c:
        return c.execute(text(
            "select count(*) from graph_facts f join graph_nodes n "
            "  on n.org_id = f.org_id and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.node_type = 'thread' and f.valid_to is null "
            "   and f.field like 'party.reply_cadence%'"), {"o": ORG}).scalar()


def test_one_reply_is_no_ones_normal(store):
    """F25's shape: one reply, which the double count made a tenant "normal" written on everyone."""
    _exchange(store, "kavitha@inboxmail.test", "t_offer", T0, T0 + timedelta(days=1.92), 0)
    _exchange(store, "priya@northwind.test", "t_priya", T0, None, 1)
    compute_waiting(store, ORG, now=NOW)
    assert _cadence(store, "kavitha@inboxmail.test") == {}
    assert _cadence(store, "priya@northwind.test") == {}, "a stranger was given a tenant normal"


def test_a_thread_node_never_carries_a_cadence(store):
    for i in range(6):
        _exchange(store, "kavitha@inboxmail.test", f"t_{i}", T0 + timedelta(days=5 * i),
                  T0 + timedelta(days=5 * i + 1), i)
    compute_waiting(store, ORG, now=NOW)
    assert _thread_cadence(store) == 0


def test_five_replies_are_a_persons_normal_with_their_n(store):
    for i, gap in enumerate((1, 2, 2, 3, 9)):
        _exchange(store, "kavitha@inboxmail.test", f"t_{i}", T0 + timedelta(days=10 * i),
                  T0 + timedelta(days=10 * i + gap), i)
    compute_waiting(store, ORG, now=NOW)
    assert _cadence(store, "kavitha@inboxmail.test") == {
        "party.reply_cadence_days": 2.0, "party.reply_cadence_basis": "person",
        "party.reply_cadence_n": 5}


def test_four_replies_lend_their_firm_nothing_until_a_fifth(store):
    """Two partners at one fund, two and two replies — four between them is still too few."""
    for i, (who, gap) in enumerate((("ana@fund.test", 1), ("ana@fund.test", 3),
                                     ("raj@fund.test", 2), ("raj@fund.test", 4))):
        _exchange(store, who, f"t_{i}", T0 + timedelta(days=10 * i),
                  T0 + timedelta(days=10 * i + gap), i)
    compute_waiting(store, ORG, now=NOW)
    assert _cadence(store, "ana@fund.test") == {}
    _exchange(store, "raj@fund.test", "t_9", T0 + timedelta(days=45), T0 + timedelta(days=50), 9)
    compute_waiting(store, ORG, now=NOW)
    assert _cadence(store, "ana@fund.test") == {
        "party.reply_cadence_days": 3.0, "party.reply_cadence_basis": "firm",
        "party.reply_cadence_n": 5}


def test_a_cadence_the_evidence_no_longer_carries_is_retired(store):
    """A tenant holds the doubled "normal" an earlier pass wrote: the next pass takes it back."""
    _exchange(store, "kavitha@inboxmail.test", "t_offer", T0, T0 + timedelta(days=2), 0)
    kavitha = node(store, ORG, "kavitha@inboxmail.test").node_id
    with store.engine.begin() as c:
        for field, value in (("party.reply_cadence_days", "2.0"),
                             ("party.reply_cadence_basis", '"tenant"')):
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
                " value, value_type, status, authority_rank, confidence, occurred_at, valid_from) "
                "values (:v, :f, :o, :n, :field, cast(:val as jsonb), 'number', 'active', 2, 0.9, "
                "        :at, :at)"),
                {"v": f"fv_old_{field}", "f": f"fid_old_{field}", "o": ORG, "n": kavitha,
                 "field": field, "val": value, "at": T0})
    compute_waiting(store, ORG, now=NOW)
    assert _cadence(store, "kavitha@inboxmail.test") == {}


def test_an_introduction_is_not_the_persons_message(store):
    """STEP-09 writes our turn on Rahul from Introly's introduction. We heard ABOUT him, not from him."""
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, "rahul@kestrelcap.test"), thread="t_intro", headers=UNSUBSCRIBE,
            mentions=(mention("Rahul Menon"),), company_brief=brief(ORG), at=T0)
    compute_waiting(store, ORG, now=NOW)
    with store.engine.connect() as c:
        heard = c.execute(text(
            "select count(*) from graph_facts f join graph_nodes n on n.org_id = f.org_id "
            "   and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = 'rahul@kestrelcap.test' "
            "   and f.field = 'thread.last_heard_days' and f.valid_to is null"),
            {"o": ORG}).scalar()
    assert heard == 0, "the connector's introduction was read as Rahul writing"


def test_his_own_reply_after_the_introduction_is_his(store):
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, "rahul@kestrelcap.test"), thread="t_intro", headers=UNSUBSCRIBE,
            mentions=(mention("Rahul Menon"),), company_brief=brief(ORG), at=T0)
    process(store, ORG, event_id="evt_mine", sender=FOUNDER, recipients=("rahul@kestrelcap.test",),
            thread="t_intro", company_brief=brief(ORG), at=T0 + timedelta(days=1))
    process(store, ORG, event_id="evt_his", sender="rahul@kestrelcap.test", thread="t_intro",
            company_brief=brief(ORG), at=T0 + timedelta(days=3))
    compute_waiting(store, ORG, now=T0 + timedelta(days=5))
    with store.engine.connect() as c:
        [heard] = c.execute(text(
            "select f.value from graph_facts f join graph_nodes n on n.org_id = f.org_id "
            "   and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = 'rahul@kestrelcap.test' "
            "   and f.field = 'thread.last_heard_days' and f.valid_to is null"),
            {"o": ORG}).scalars().all()
    assert heard == 2, "heard from him 2 days ago — his reply, not the introduction"


def test_now_is_pinned_in_these_tests():
    assert NOW.tzinfo is timezone.utc
