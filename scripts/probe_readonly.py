"""READ-ONLY probe: which orgs exist, their connections, current graph baseline, and where
Piyush / 3one4 lives. Only SELECTs — writes/deletes nothing."""
from __future__ import annotations

from sqlalchemy import text

from genios_engine.platform.wiring import make_graph_store


def rows(conn, sql, **p):
    try:
        return conn.execute(text(sql), p).fetchall()
    except Exception as e:      # noqa: BLE001
        return [("(n/a)", str(e)[:60])]


def main() -> None:
    eng = make_graph_store().engine
    with eng.connect() as c:
        print("== connections by org × source ==")
        for r in rows(c, "select org_id, source_type, status, count(*) "
                         "from connections group by org_id, source_type, status "
                         "order by org_id"):
            print("  ", r)

        print("\n== graph_nodes by org (totals) ==")
        for r in rows(c, "select org_id, count(*) from graph_nodes where valid_to is null "
                         "group by org_id order by 2 desc"):
            print("  ", r)

        print("\n== graph_edges by org ==")
        for r in rows(c, "select org_id, count(*) from graph_edges group by org_id order by 2 desc"):
            print("  ", r)

        print("\n== where does 3one4 / piyush live? (node → org) ==")
        for r in rows(c, "select org_id, node_type, canonical_key, display_name "
                         "from graph_nodes where valid_to is null and "
                         "(lower(canonical_key) like '%3one4%' or lower(canonical_key) like '%piyush%' "
                         " or lower(display_name) like '%piyush%') limit 20"):
            print("  ", r)

        print("\n== source_events by org × source × outcome (what L1 captured) ==")
        for r in rows(c, "select org_id, source, outcome, count(*) from source_events "
                         "group by org_id, source, outcome order by org_id, source"):
            print("  ", r)


if __name__ == "__main__":
    main()
