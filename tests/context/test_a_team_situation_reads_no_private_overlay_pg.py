"""A team situation is decided by org-visible facts only — never by one seat's private overlay.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_team_situation_reads_no_private_overlay_pg.py -q

L3 audit, 21 Oct 2026. A fact learned privately (a personal transcript, a seat's screen) is a SEAT OVERLAY: its own
active `graph_facts` version, `visibility_scope='private'`, beside the org version (`graph_store.write_fact`).
`refresh_situations` read every active version, unordered, into one dict — whichever came last won — so one seat's
private fact decided a team situation's coverage and could flip it between sweeps. Its two fact reads are now
org-visible on PostgreSQL, as `correlation_people`'s are.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from genios_engine.context import situations as S

pytestmark = pytest.mark.pg
ORG = f"org_no_overlay_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def store(pg_store):
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"), {"o": ORG, "e": f"{ORG}@x.test"})
        for fv, value, scope in (("fv_org", '"proposal"', "org"), ("fv_seat", '"closed_won"', "private")):
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, value_type, "
                "  status, authority_rank, confidence, occurred_at, visibility_scope, visibility_principals) "
                "values (:fv, :fv, :o, 'node_acme', 'deal.stage', cast(:v as jsonb), 'enum', 'active', 2, 0.85, now(), "
                "  :scope, :who)"),
                {"fv": fv, "o": ORG, "v": value, "scope": scope,
                 "who": ["rohit@acme.test"] if scope == "private" else []})
        # One correlation, so the refresh reaches its fact reads (it returns early on a tenant with none).
        c.execute(text("insert into context_correlations (correlation_id, org_id, anchor_node_id, anchor_type, domain, "
                       "  first_event_at, last_event_at, event_count) values (:c, :o, 'node_acme', 'company', 'sales', "
                       "  now(), now(), 1)"), {"c": f"corr_{ORG}", "o": ORG})
    yield pg_store
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def test_the_org_read_holds_the_org_value_only(store):
    with store.engine.connect() as c:
        rows = c.execute(text(S._ORG_FACTS), {"o": ORG}).fetchall()
        whole = c.execute(text(S._ALL_FACTS), {"o": ORG}).fetchall()
    assert [r.value for r in rows] == ["proposal"], "a seat's private overlay reached a team situation"
    assert len(whole) == 2, "the control: both versions are there to be read"


def test_the_refresh_reads_through_the_org_visible_statements_on_postgres(store, monkeypatch):
    """The call site, not only the constants: what `refresh_situations` actually sends on PostgreSQL."""
    sent: list[str] = []
    real = S._bulk

    def _spy(conn, sql, params):
        sent.append(sql)
        return real(conn, sql, params)
    monkeypatch.setattr(S, "_bulk", _spy)
    S.refresh_situations(store, ORG)
    assert S._ORG_FACTS in sent and S._ORG_MEMBER_FIELDS in sent
    assert S._ALL_FACTS not in sent and S._ALL_MEMBER_FIELDS not in sent
