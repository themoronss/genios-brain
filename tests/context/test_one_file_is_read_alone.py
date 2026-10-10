"""STEP-12 · one file is read alone — its own correlations, never every file of the tenant filtered.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_one_file_is_read_alone.py -q

`context/workstreams.file_for` (tree `yc2_w27_s12` M32.C2.L-data.V0.U01). The expert's dossier reads ONE
file per review, and `GET /v1/workstreams/{file_id}` showed one file by building every file of the
tenant and keeping the one asked for — a read that grows with the tenant for an answer about one piece
of work. `file_for` reads the members of that file's anchor alone and builds it the way `files_for`
builds each of its files, so the two never disagree; a file the tenant does not hold is None.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event

from genios_engine.context.workstreams import file_for, files_for

from .workstream_world import (CONNECTOR, FOUNDER, UNSUBSCRIBE, WATCHED, brief, later, mention,
                               process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s12_one_file"
OTHER = "org_s12_one_file_other"
RAHUL, FARAH, PRIYA = "rahul@kestrelcap.test", "farah@kitepath.test", "priya@northwind.test"
NOW = later(10)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    tenant(pg_store, OTHER)
    yield pg_store
    reset(pg_store, ORG)
    reset(pg_store, OTHER)


def _world(store):
    """An introduction of two, a reply on it, the connector's own ask, a portal's notice and an
    ordinary correspondent — files of five kinds."""
    b = brief(ORG)
    for kw in (
            dict(event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL, FARAH),
                 thread="t_intro", headers=UNSUBSCRIBE,
                 mentions=(mention("Rahul Menon"), mention("Farah Qureshi"),
                           mention("Kestrel Capital", "organization"),
                           mention("Kitepath", "organization"))),
            dict(event_id="evt_farah", sender=FARAH, recipients=(FOUNDER, CONNECTOR),
                 thread="t_intro", at=later(1)),
            dict(event_id="evt_ask", sender=CONNECTOR, thread="t_ask", headers=UNSUBSCRIBE,
                 at=later(4)),
            dict(event_id="evt_notice", sender=f"updates@{WATCHED}", at=later(5)),
            dict(event_id="evt_priya", sender=PRIYA, thread="t_priya", at=later(6))):
        process(store, ORG, company_brief=b, **kw)
    return b


def test_one_file_is_the_file_the_list_gives(store):
    b = _world(store)
    with store.engine.connect() as c:
        listed = files_for(c, ORG, now=NOW, company_brief=b).files
        assert len(listed) == 5, [f.counterparty_key for f in listed]
        for f in listed:
            assert file_for(c, ORG, f.file_id, now=NOW, company_brief=b) == f, f.counterparty_key


def test_the_accepted_brief_is_read_when_none_is_handed_in(store):
    """The brief the founder accepted, read on the connection — so the connector's file is a
    connector's and the portal's is watched, exactly as the list says."""
    from genios_engine.platform import company_brief_store as briefs
    _world(store)
    with store.engine.begin() as c:
        briefs.add(c, org_id=ORG, section="connectors", words="Introly — introduces the founder",
                   address=CONNECTOR, decided_by="test", at=NOW)
        briefs.add(c, org_id=ORG, section="watchlist", words="StartupSetu — a portal",
                   domain=WATCHED, decided_by="test", at=NOW)
    from genios_engine.platform.company_brief import invalidate
    invalidate(ORG)
    with store.engine.connect() as c:
        listed = files_for(c, ORG, now=NOW).files
        kinds = {f.counterparty_key: f.kind for f in listed}
        assert (kinds["introly.test"], kinds[WATCHED]) == ("connector", "watched"), kinds
        for f in listed:
            assert file_for(c, ORG, f.file_id, now=NOW) == f


def test_a_file_the_tenant_does_not_hold_is_none(store):
    b = _world(store)
    with store.engine.connect() as c:
        mine = files_for(c, ORG, now=NOW, company_brief=b).files[0]
        assert file_for(c, ORG, "node_nobody_holds", now=NOW, company_brief=b) is None
        assert file_for(c, OTHER, mine.file_id, now=NOW) is None


def test_one_file_reads_the_members_of_its_own_anchor_alone(store):
    b = _world(store)
    with store.engine.connect() as c:
        target = next(f for f in files_for(c, ORG, now=NOW, company_brief=b).files
                      if f.counterparty_key == "kitepath.test")
    seen: list[dict] = []

    def _spy(conn, cursor, statement, parameters, context, executemany):
        if "from context_correlations k" in statement and "context_correlation_members" in statement:
            seen.append(dict(parameters))
    event.listen(store.engine, "before_cursor_execute", _spy)
    try:
        with store.engine.connect() as c:
            assert file_for(c, ORG, target.file_id, now=NOW, company_brief=b) == target
    finally:
        event.remove(store.engine, "before_cursor_execute", _spy)
    assert [p.get("a") for p in seen] == [target.file_id], seen
