"""Segments CRUD + membership against a real Postgres (skips unless GENIOS_TEST_DATABASE_URL set)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("GENIOS_TEST_DATABASE_URL"),
    reason="GENIOS_TEST_DATABASE_URL not set")


def _seed(engine, org):
    with engine.begin() as c:
        c.execute(text("insert into orgs (id,name,subscription_tier) values (:o,'S','startup') "
                       "on conflict (id) do update set subscription_tier='startup'"), {"o": org})
        for nid, nt, name in [("p1", "person", "Priya"), ("c1", "company", "Acme")]:
            c.execute(text("insert into graph_nodes (node_id,org_id,node_type,display_name) "
                           "values (:n,:o,:t,:d) on conflict do nothing"),
                      {"n": nid, "o": org, "t": nt, "d": name})


def test_segments_full_lifecycle():
    from genios_engine.api import segments_routes as S
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.migrate import apply_migrations
    apply_migrations(database_url=url)
    S._graph = GraphStore(url)                       # point the module store at the test DB
    org = "seg_org"
    _seed(S._graph.engine, org)

    # create
    seg = S.create_segment(S.CreateSegment(name="Investors", cluster_type="Investor"), org=org)
    assert seg["cluster_type"] == "Investor" and seg["member_count"] == 0
    sid = seg["id"]

    # list
    listing = S.list_segments(org=org)
    assert listing["plan_tier"] == "startup" and listing["max_allowed"] == 10
    assert any(s["id"] == sid for s in listing["segments"])

    # add members (only real nodes counted; a bogus id is ignored)
    added = S.add_members(sid, S.AddMembers(contact_ids=["p1", "c1", "ghost"]), org=org)
    assert added["added"] == 2

    members = S.list_members(sid, org=org)
    assert members["count"] == 2 and {m["contact_id"] for m in members["members"]} == {"p1", "c1"}

    # remove one
    S.remove_member(sid, "c1", org=org)
    assert S.list_members(sid, org=org)["count"] == 1

    # update
    up = S.update_segment(sid, S.UpdateSegment(name="Key Investors"), org=org)
    assert up["name"] == "Key Investors"

    # contact override → moves p1 to a second segment
    seg2 = S.create_segment(S.CreateSegment(name="Customers", cluster_type="Customer"), org=org)
    S.set_contact_segment("p1", S.ContactSegment(segment_id=seg2["id"]), org=org)
    assert S.list_members(sid, org=org)["count"] == 0            # override cleared old membership
    assert S.list_members(seg2["id"], org=org)["count"] == 1

    # sync stamps last_synced_at
    assert S.sync_segment(sid, org=org)["synced"] is True

    # delete
    assert S.delete_segment(sid, org=org)["deleted"] is True
    with pytest.raises(Exception):
        S.update_segment(sid, S.UpdateSegment(name="x"), org=org)   # 404 now
