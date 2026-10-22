"""GeniOS-011 S14.U1 · a reply after a reading joins its counterparty's file — a reading's membership
is never a file, so it is never inherited, never skipped and never counted filed.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_reply_after_a_reading_joins_the_file_pg.py -q

Audit item `l3-thread-inherits-reading-correlations`. A reading writes `context_correlation_members`
rows under its own synthetic id (`outreach:{node}`, `stated:{hash}`, … — `joined_via = 'reading'`,
`context/correlation_membership.declare_finding_events`), and no `context_correlations` row owns that
id: *"a reading only claims its own correlation"*. A file is one anchor's ENGINE-owned correlations
(`context/workstreams._MEMBERS` joins `context_correlations`), so a reading's id is in no file.

Three readers took any membership for a file's:
  * `correlation.thread_correlations` — a reply whose thread's only earlier event a reading had
    declared inherited the reading's id, joined it alone, and landed in no file; in a thread that also
    held a file, a reply naming no party joined every reading's id beside it;
  * `backfill.backfill_correlations` (not a rebuild) — skipped such an event as already grouped;
  * `workstreams._NAMED_MAIL` — counted it `filed`, so the health check never named it unfiled.
Each now counts only an id a `context_correlations` row owns.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context.backfill import backfill_correlations
from genios_engine.context.correlation import correlate_event
from genios_engine.context.correlation_membership import declare_finding_events
from genios_engine.context.workstreams import files_for

from .workstream_world import FOUNDER
from .workstream_world import anchors
from .workstream_world import brief
from .workstream_world import later
from .workstream_world import ledger
from .workstream_world import process
from .workstream_world import reset
from .workstream_world import tenant

pytestmark = pytest.mark.pg

ORG = f"org_g011_s14u1_{uuid.uuid4().hex[:8]}"
PRIYA = "priya@northwind.test"
#: A reading's synthetic correlation — the shape `outreach_situations` mints. No engine row owns it.
READING = "outreach:node_priya"
NOW = later(10)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _a_reading_declares(store, *event_ids: str) -> None:
    """A reading's finding resting on exactly these events, written as its membership."""
    with store.engine.begin() as c:
        written = declare_finding_events(c, org_id=ORG, correlation_id=READING,
                                         finding=SimpleNamespace(event_ids=tuple(event_ids)))
    assert written == len(event_ids), "the reading wrote no membership: the test proves nothing"


def _unfile(store, event_id: str) -> None:
    """The event in no file, as an event the drain never correlated (held, parked, or read before
    the graph knew its counterparty) — its engine membership and the then-empty correlations gone."""
    with store.engine.begin() as c:
        c.execute(text("delete from context_correlation_members where org_id = :o "
                       "   and event_id = :e"), {"o": ORG, "e": event_id})
        c.execute(text("delete from context_correlations where org_id = :o"), {"o": ORG})
    assert anchors(store, ORG, event_id) == set()


def _memberships(store, event_id: str) -> set[str]:
    with store.engine.connect() as c:
        return {r.correlation_id for r in c.execute(text(
            "select correlation_id from context_correlation_members "
            " where org_id = :o and event_id = :e"), {"o": ORG, "e": event_id})}


def _file(store, key: str, company_brief=None):
    with store.engine.connect() as c:
        ws = files_for(c, ORG, now=NOW, company_brief=company_brief or brief(ORG))
    return {f.counterparty_key: f for f in ws.files}.get(key), ws


def test_a_reply_whose_thread_only_a_reading_declared_joins_the_counterpartys_file(store):
    """Our outreach was read by a reading and filed by nothing else; Priya's reply in that thread is
    filed under Northwind — and listed there — never under the reading's id alone."""
    ledger(store, ORG, event_id="evt_ours", sender=FOUNDER, thread="t_out", recipients=(PRIYA,))
    _a_reading_declares(store, "evt_ours")

    process(store, ORG, event_id="evt_reply", sender=PRIYA, sender_name="Priya Shah",
            recipients=(FOUNDER,), thread="t_out", at=later(1), company_brief=brief(ORG))

    assert anchors(store, ORG, "evt_reply") == {"northwind.test"}
    assert READING not in _memberships(store, "evt_reply"), "the reply joined the reading's id"
    northwind, _ws = _file(store, "northwind.test")
    assert northwind is not None and "evt_reply" in northwind.events


def test_a_reply_naming_no_party_joins_the_file_and_not_the_readings(store):
    """A thread holding one file and a reading's id: a reply that names no party keeps its whole
    CONVERSATION — the file — and never joins the reading's id beside it."""
    process(store, ORG, event_id="evt_priya", sender=PRIYA, sender_name="Priya Shah",
            recipients=(FOUNDER,), thread="t_conv", company_brief=brief(ORG))
    [the_file] = _memberships(store, "evt_priya")
    _a_reading_declares(store, "evt_priya")

    ledger(store, ORG, event_id="evt_bare", sender=FOUNDER, thread="t_conv", at=later(1))
    with store.engine.begin() as c:
        joined = correlate_event(c, org_id=ORG, event_id="evt_bare", occurred_at=later(1),
                                 thread_id="t_conv", node_types={}, domain_hints=None)
    assert joined == [the_file]
    assert _memberships(store, "evt_bare") == {the_file}


def test_the_backfill_files_an_event_only_a_reading_declared(store):
    """The incremental backfill skips an event already GROUPED — a reading's membership is not."""
    process(store, ORG, event_id="evt_priya", sender=PRIYA, sender_name="Priya Shah",
            recipients=(FOUNDER,), thread="t_priya", company_brief=brief(ORG))
    _unfile(store, "evt_priya")
    _a_reading_declares(store, "evt_priya")

    result = backfill_correlations(store, ORG)

    assert result["events_correlated"] == 1, result
    assert anchors(store, ORG, "evt_priya") == {"northwind.test"}


def test_mail_only_a_reading_declared_is_not_counted_filed(store):
    """A named person whose only mail sits under a reading's id has mail and no file — `unfiled`,
    which the health check names (`scripts/pipeline_health`)."""
    named = brief(ORG, people=(PRIYA,))
    process(store, ORG, event_id="evt_priya", sender=PRIYA, sender_name="Priya Shah",
            recipients=(FOUNDER,), thread="t_priya", company_brief=named)
    _northwind, ws = _file(store, "northwind.test", named)
    assert {n.named: (n.mail, n.filed) for n in ws.named}[f"person:{PRIYA}"] == (1, 1)

    _unfile(store, "evt_priya")
    _a_reading_declares(store, "evt_priya")

    _northwind, ws = _file(store, "northwind.test", named)
    assert {n.named: (n.mail, n.filed) for n in ws.named}[f"person:{PRIYA}"] == (1, 0)
    assert f"person:{PRIYA}" in [n.named for n in ws.unfiled]
