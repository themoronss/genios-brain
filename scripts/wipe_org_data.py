"""Wipe ONE org's data-plane while keeping its identity/config/billing.

KEEPS:  orgs row, org_seats, connections (gmail/gcal stay connected), tenant_packs,
        org_channels, llm_costs + credit_ledger + subscriptions (spend/billing history),
        config_snapshots, learning_policies, api_keys, agent_registry.
WIPES:  everything else org-scoped — events, payloads, graph, situations, signals, cards,
        deliveries, executions, learning objects, cursors (so the next Sync is a full
        fresh backfill through the new engine).

Usage:
    python scripts/wipe_org_data.py org_xxx            # dry run — counts only
    python scripts/wipe_org_data.py org_xxx --execute  # actually delete
"""
import os
import sys

from sqlalchemy import text

from genios_engine.platform.db import get_engine

KEEP = {"orgs", "org_seats", "connections", "tenant_packs", "org_channels",
        "llm_costs", "credit_ledger", "subscriptions", "payments", "config_snapshots",
        "orgs_archive", "users", "api_keys", "agent_registry", "learning_policies"}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    org = sys.argv[1]
    execute = "--execute" in sys.argv
    e = get_engine(os.environ["GENIOS_DATABASE_URL"])
    with e.begin() as c:
        views = {r[0] for r in c.execute(text(
            "select table_name from information_schema.views where table_schema='public'"))}
        tables = [r[0] for r in c.execute(text(
            "select distinct table_name from information_schema.columns "
            "where column_name='org_id' and table_schema='public'"))]
        wipe = [t for t in tables if t not in KEEP and t not in views]

        if not execute:
            total = 0
            for t in sorted(wipe):
                n = c.execute(text(f"select count(*) from {t} where org_id=:o"),
                              {"o": org}).scalar() or 0
                if n:
                    print(f"  would delete {n:>6} from {t}")
                    total += n
            print(f"DRY RUN — {total} rows across data-plane tables. "
                  f"Re-run with --execute to delete.")
            return 0

        remaining, deleted = set(wipe), {}
        for _ in range(8):                          # FK-safe multi-pass
            progressed = False
            for t in sorted(remaining):
                try:
                    with c.begin_nested():
                        n = c.execute(text(f"delete from {t} where org_id=:o"),
                                      {"o": org}).rowcount
                    deleted[t] = n
                    remaining.discard(t)
                    progressed = True
                except Exception:
                    pass
            if not remaining or not progressed:
                break
        if remaining:
            raise RuntimeError(f"could not clear (FK cycle?): {sorted(remaining)}")
        c.execute(text(
            "insert into graph_versions (org_id, graph_version) values (:o, 1) "
            "on conflict (org_id) do update set graph_version = 1"), {"o": org})
        print(f"DELETED {sum(deleted.values())} rows across "
              f"{sum(1 for v in deleted.values() if v)} tables. graph_versions reset to 1.")
    with e.connect() as c:
        print("kept connections:", c.execute(text(
            "select source_type, status from connections where org_id=:o"), {"o": org}).fetchall())
        print("kept packs:", c.execute(text(
            "select pack_id, version from tenant_packs where org_id=:o"), {"o": org}).fetchall())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
