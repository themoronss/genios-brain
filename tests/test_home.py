"""Home aggregations: network-health + first-scan against real Postgres (skips without DB)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("GENIOS_TEST_DATABASE_URL"),
    reason="GENIOS_TEST_DATABASE_URL not set")


def test_network_health_and_first_scan():
    from genios_engine.api import home_routes as H
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.migrate import apply_migrations
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    apply_migrations(database_url=url)
    H._graph = GraphStore(url)
    org, now = "home_org", datetime.now(timezone.utc)
    with H._graph.engine.begin() as c:
        c.execute(text("insert into orgs (id,name) values (:o,'S') on conflict do nothing"),
                  {"o": org})
        c.execute(text("insert into graph_nodes (node_id,org_id,node_type,display_name) "
                       "values ('p1',:o,'person','Priya') on conflict do nothing"), {"o": org})
        c.execute(text("insert into graph_facts (fact_version_id,fact_id,org_id,subject_node_id,"
                       "field,value,value_type,status,occurred_at) values "
                       "('fv','f',:o,'p1','commitment.due_at',cast(:v as jsonb),'string','active',:t)"),
                  {"o": org, "v": '"2020-01-01"', "t": now - timedelta(days=5)})

    nh = H.network_health(org, org=org)
    assert nh["network_health"]["total_contacts"] == 1
    assert nh["network_health"]["active_now"] == 1              # active within 7 days
    assert nh["open_commitments"] == {"total": 1, "overdue": 1}

    fs = H.first_scan(org, org=org)
    assert fs["footprint"]["entities"] == 1 and fs["footprint"]["facts"] == 1
    assert "generated_at" in fs and "findings" in fs
