"""Merge queue adapter over identity proposals (skips unless GENIOS_TEST_DATABASE_URL set)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("GENIOS_TEST_DATABASE_URL"),
    reason="GENIOS_TEST_DATABASE_URL not set")


def _seed(engine, org):
    with engine.begin() as c:
        c.execute(text("insert into orgs (id,name) values (:o,'S') on conflict do nothing"),
                  {"o": org})
        for nid, name in [("na", "Rohit Sharma"), ("nb", "Rohit S")]:
            c.execute(text("insert into graph_nodes (node_id,org_id,node_type,display_name,"
                           "canonical_key) values (:n,:o,'person',:d,:k) on conflict do nothing"),
                      {"n": nid, "o": org, "d": name, "k": f"{nid}@x.io"})
        c.execute(text("insert into merge_proposals (id,org_id,left_node_id,right_node_id,"
                       "node_type,reason,status) values ('mp1',:o,'na','nb','person',"
                       "'same_name_same_company','open')"), {"o": org})


def test_merge_queue_and_execute():
    from genios_engine.api import merge_routes as M
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.migrate import apply_migrations
    apply_migrations(database_url=url)
    M._graph = GraphStore(url)
    org = "merge_org"
    _seed(M._graph.engine, org)

    q = M.merge_queue(org, org=org)
    assert q["count"] == 1
    item = q["queue"][0]
    assert item["id"] == "mp1" and item["status"] == "open"
    assert item["match_reason"] == "same_name_same_company"
    assert 0 < item["match_score"] <= 1
    assert {item["contact_a"]["id"], item["contact_b"]["id"]} == {"na", "nb"}

    res = M.execute_merge(org, "mp1", org=org)
    assert res["status"] == "merged"
    assert res["kept"] == "na" and res["archived"] == "nb"      # more-connected node survived

    # queue now empty
    assert M.merge_queue(org, org=org)["count"] == 0
