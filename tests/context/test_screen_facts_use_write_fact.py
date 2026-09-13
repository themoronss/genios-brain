"""SCREEN_INTEL_P2 §1.6 / acceptance (7) — P-06/07/08 need no graph change: a screen-derived fact
goes through `write_fact` and corroborates, raises a discrepancy, or supersedes exactly like mail.

    pytest tests/context/test_screen_facts_use_write_fact.py -q
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

T = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)


def _setup(pg_store):
    from genios_engine.platform.ids import new_id
    node = new_id("node_scr")
    with pg_store.engine.begin() as c:
        org = c.execute(text("select id from orgs order by id limit 1")).scalar()
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key) values (:n,1,:o,'deal',:n)"), {"n": node, "o": org})
    return org, node


def _cleanup(pg_store, org, node):
    with pg_store.engine.begin() as c:
        c.execute(text("delete from graph_source_refs where org_id=:o and fact_version_id in "
                       "(select fact_version_id from graph_facts where subject_node_id=:n)"),
                  {"o": org, "n": node})
        for table in ("graph_facts", "discrepancies"):
            c.execute(text(f"delete from {table} where org_id=:o and subject_node_id=:n"),
                      {"o": org, "n": node})
        c.execute(text("delete from graph_nodes where node_id=:n"), {"n": node})


def _write(pg_store, c, org, node, value, *, rank, event, source, at):
    return pg_store.write_fact(
        c, org_id=org, subject_node_id=node, field="deal.status", value=value,
        value_type="enum", confidence=0.8, occurred_at=at, event_id=event,
        evidence={"text": value}, source=source, authority_rank=rank)


def test_p06_screen_corroborates_mail(pg_store):
    org, node = _setup(pg_store)
    try:
        with pg_store.engine.begin() as c:
            held = _write(pg_store, c, org, node, "negotiating", rank=2, event="ev_mail",
                          source="gmail", at=T)
            assert _write(pg_store, c, org, node, "negotiating", rank=2, event="ev_scr",
                          source="screen_session", at=T + timedelta(hours=1)) is None
            refs = c.execute(text("select source from graph_source_refs where fact_version_id=:f "
                                  "order by source"), {"f": held}).scalars().all()
        assert refs == ["gmail", "screen_session"]
    finally:
        _cleanup(pg_store, org, node)


def test_p07_screen_disagreeing_with_a_system_of_record_is_a_discrepancy(pg_store):
    org, node = _setup(pg_store)
    try:
        with pg_store.engine.begin() as c:
            _write(pg_store, c, org, node, "open", rank=3, event="ev_crm", source="hubspot", at=T)
            assert _write(pg_store, c, org, node, "lost", rank=2, event="ev_scr",
                          source="screen_session", at=T + timedelta(hours=1)) is None
            disc = c.execute(text("select status from discrepancies where org_id=:o and "
                                  "subject_node_id=:n and field='deal.status'"),
                             {"o": org, "n": node}).scalars().all()
            active = c.execute(text("select value from graph_facts where subject_node_id=:n and "
                                    "status='active' and valid_to is null"),
                               {"n": node}).scalars().all()
        assert disc == ["open"] and active == ["open"]
    finally:
        _cleanup(pg_store, org, node)


def test_p08_newer_screen_fact_supersedes_an_equal_rank_one(pg_store):
    org, node = _setup(pg_store)
    try:
        with pg_store.engine.begin() as c:
            _write(pg_store, c, org, node, "negotiating", rank=2, event="ev_mail",
                   source="gmail", at=T)
            new = _write(pg_store, c, org, node, "lost", rank=2, event="ev_scr",
                         source="screen_session", at=T + timedelta(hours=1))
            rows = c.execute(text("select value, status from graph_facts where subject_node_id=:n "
                                  "order by created_at"), {"n": node}).fetchall()
        assert new and [(r.value, r.status) for r in rows] == [
            ("negotiating", "superseded"), ("lost", "active")]
    finally:
        _cleanup(pg_store, org, node)
