"""STEP-10 · your own reply time exists — per counterparty and overall, with its n.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_your_reply_time.py -q

`context/waiting.compute_waiting` (tree `yc2_w27_s10 · M29.C1.L-logic.V2.U03`). Measured (`STEP-10` §8.1):
the founder's own reply time existed nowhere — `outreach_situations` says a reply-owed threshold "needs our
own cadence, which nothing derives yet" and uses a fixed 2 days — and the whole golden set holds one founder
reply to an inbound mail (F14, 5 days, n = 1). Now waiting measures it as the mirror of theirs: from a mail
someone WROTE us to our next mail to them in the same conversation. Per counterparty
(`party.our_reply_days` + `party.our_reply_n`) and overall on the tenant node (`derived.our_reply_days` +
`derived.our_reply_n`) — each written only at `NORMAL_AT` (5) replies, retired below it. "Us" is the
pipeline's direction, which is STEP-04's identity. An introduction is no mail they wrote.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.periodic import _ensure_tenant_node
from genios_engine.context.waiting import compute_waiting, our_reply_gaps_of

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, brief, mention, process,
                               reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s10_your_reply_time"
NOW = T0 + timedelta(days=90)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        _ensure_tenant_node(pg_store, c, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _they_wrote_we_answered(store, who: str, gaps: tuple[float, ...], tag: str):
    for i, gap in enumerate(gaps):
        asked = T0 + timedelta(days=10 * i)
        process(store, ORG, event_id=f"evt_{tag}_in_{i}", sender=who, thread=f"t_{tag}_{i}",
                at=asked)
        process(store, ORG, event_id=f"evt_{tag}_out_{i}", sender=FOUNDER, recipients=(who,),
                thread=f"t_{tag}_{i}", at=asked + timedelta(days=gap))


def _facts(store, key: str, prefix: str) -> dict:
    with store.engine.connect() as c:
        return {r.field: r.value for r in c.execute(text(
            "select f.field, f.value from graph_facts f join graph_nodes n "
            "  on n.org_id = f.org_id and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = :k and f.valid_to is null "
            "   and f.field like :p"), {"o": ORG, "k": key, "p": prefix + "%"})}


def test_the_mirror_of_their_reply_time_is_pure():
    from datetime import datetime, timezone
    t = datetime(2026, 9, 1, tzinfo=timezone.utc)
    timeline = [("in", t), ("in", t + timedelta(days=1)), ("out", t + timedelta(days=2)),
                ("out", t + timedelta(days=3)), ("in", t + timedelta(days=4)),
                ("out", t + timedelta(days=4.5))]
    assert our_reply_gaps_of(timeline) == [2.0, 0.5], "the first inbound of a run is what we answer"
    assert our_reply_gaps_of(timeline[::-1]) == [2.0, 0.5], "rows arrive unordered; time orders them"


def test_five_answers_to_one_person_are_your_normal_with_them(store):
    _they_wrote_we_answered(store, "priya@northwind.test", (0.5, 1, 1, 2, 3), "p")
    compute_waiting(store, ORG, now=NOW)
    assert _facts(store, "priya@northwind.test", "party.our_reply") == {
        "party.our_reply_days": 1.0, "party.our_reply_n": 5}


def test_four_answers_are_too_few_to_call_normal(store):
    _they_wrote_we_answered(store, "priya@northwind.test", (0.5, 1, 1, 2), "p")
    compute_waiting(store, ORG, now=NOW)
    assert _facts(store, "priya@northwind.test", "party.our_reply") == {}
    assert _facts(store, f"tenant:{ORG}", "derived.our_reply") == {}, "four overall are too few too"


def test_overall_your_reply_time_pools_every_counterparty(store):
    """Three answers to Priya and two to Ana: neither is a habit alone; five overall are."""
    _they_wrote_we_answered(store, "priya@northwind.test", (1, 2, 4), "p")
    _they_wrote_we_answered(store, "ana@southwind.test", (3, 5), "a")
    compute_waiting(store, ORG, now=NOW)
    assert _facts(store, f"tenant:{ORG}", "derived.our_reply") == {
        "derived.our_reply_days": 3.0, "derived.our_reply_n": 5}
    assert _facts(store, "priya@northwind.test", "party.our_reply") == {}


def test_your_reply_time_the_evidence_no_longer_carries_is_retired(store):
    _they_wrote_we_answered(store, "priya@northwind.test", (0.5, 1, 1, 2, 3), "p")
    compute_waiting(store, ORG, now=NOW)
    with store.engine.begin() as c:     # the window moves on: four of the five fall out of it
        c.execute(text("update source_events set occurred_at = occurred_at - interval '400 days' "
                       " where org_id = :o and event_id like 'evt_p_%' "
                       "   and event_id not in ('evt_p_in_4', 'evt_p_out_4')"), {"o": ORG})
    compute_waiting(store, ORG, now=NOW)
    assert _facts(store, "priya@northwind.test", "party.our_reply") == {}
    assert _facts(store, f"tenant:{ORG}", "derived.our_reply") == {}


def test_an_introduction_is_not_a_mail_they_wrote_us(store):
    """Introly introduced Rahul; we wrote to him a day later. That answered no mail of his."""
    for i in range(5):
        process(store, ORG, event_id=f"evt_intro_{i}", sender=CONNECTOR, sender_name="Introly",
                recipients=(FOUNDER, f"contact{i}@fund{i}.test"), thread=f"t_intro_{i}",
                headers=UNSUBSCRIBE, mentions=(mention(f"Contact {i}"),), company_brief=brief(ORG),
                at=T0 + timedelta(days=10 * i))
        process(store, ORG, event_id=f"evt_mine_{i}", sender=FOUNDER,
                recipients=(f"contact{i}@fund{i}.test",), thread=f"t_intro_{i}",
                company_brief=brief(ORG), at=T0 + timedelta(days=10 * i + 1))
    compute_waiting(store, ORG, now=NOW)
    assert _facts(store, f"tenant:{ORG}", "derived.our_reply") == {}


def test_without_a_tenant_node_the_overall_number_waits(store):
    """Before the first periodic pass the tenant node does not exist: nothing overall, no error."""
    with store.engine.begin() as c:
        c.execute(text("update graph_nodes set valid_to = now() where org_id = :o "
                       "   and node_type = 'tenant'"), {"o": ORG})
    _they_wrote_we_answered(store, "priya@northwind.test", (0.5, 1, 1, 2, 3), "p")
    compute_waiting(store, ORG, now=NOW)
    assert _facts(store, "priya@northwind.test", "party.our_reply") != {}
