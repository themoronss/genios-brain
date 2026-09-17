"""`raw_payloads` had one index — its primary key — and nothing looks a payload up by it.

Every reader filters on the event, most on the tenant too, and not one on `id`. So every read was
a sequential scan. Measured on production 2026-09-17 with 3,594 rows:

    Seq Scan on raw_payloads  (actual time=0.021..351.475 rows=1)
      Rows Removed by Filter: 3593
      Execution Time: 351.534 ms

351 milliseconds to fetch ONE payload, and the L2 drain joins this once per event. The table is
25 MB at 3,594 rows; a tenant with 50,000 events carries ~350 MB of it and pays the scan every
time. That is the first thing that falls over under load, and it falls over as latency rather
than as an error — which is why nothing had reported it.

Migration 0173 adds `(org_id, event_id)`. After it: 351.5ms -> 2.9ms on the lookup, and
113.6ms -> 1.4ms on the parked drain's join.

THE INDEX IS ONLY HALF OF IT. It leads on `org_id`, so a join that matches on `event_id` alone
cannot use it — and three of them did exactly that, one of them the L2 drain, sitting directly
above a `prepared_content` join that DOES carry the org. That asymmetry is the thing this file
pins: a payload belongs to a tenant, and a join that does not say so is relying on
`new_id("evt")` never colliding across orgs to stay correct.
"""
from __future__ import annotations

import io
import re

import pytest

pytest.importorskip("sqlalchemy")

#: Every module that joins `raw_payloads`, and the alias it gives the row it joins FROM.
_JOINS = [
    ("genios_engine/context/runner.py", "se"),
    ("genios_engine/capture/parked/drain.py", "pe"),
    ("genios_engine/capture/parked/drain.py", "se"),
]


def _sql_text(path: str) -> str:
    """The module's SQL as one string, comments stripped.

    Stripping matters: this file's own reason for existing is quoted in a comment beside each
    join, and a check that matched prose would pass on the explanation instead of the query."""
    src = io.open(path, encoding="utf-8").read()
    src = "\n".join(line for line in src.splitlines() if not line.strip().startswith("#"))
    return " ".join(src.split())


@pytest.mark.parametrize("path,alias", _JOINS)
def test_every_payload_join_carries_the_tenant(path, alias):
    """`on rp.event_id = X.event_id` with no `rp.org_id` — the shape that both loses the index
    and drops the isolation its neighbour keeps."""
    sql = _sql_text(path)
    naked = re.findall(
        r"join raw_payloads rp on rp\.event_id = " + alias + r"\.event_id(?! and rp\.org_id)", sql)

    assert not naked, (
        f"{path}: a raw_payloads join on {alias}.event_id alone. It cannot use "
        f"raw_payloads_org_event_idx (which leads on org_id) and it says a payload is findable "
        f"across tenants — which the prepared_content join beside it does not.")


def test_the_index_the_joins_depend_on_is_shipped():
    """The scoping is only worth anything with the index, and the index is only reachable with
    the scoping. Losing either quietly restores a 351ms sequential scan."""
    ddl = " ".join(io.open("migrations/0173_raw_payloads_is_looked_up_by_event.sql",
                           encoding="utf-8").read().split()).lower()

    assert "create index" in ddl
    assert "raw_payloads (org_id, event_id)" in ddl, (
        "the index no longer leads on org_id, so every org-scoped join falls back to a scan")


def test_the_migration_can_run_inside_the_runners_transaction():
    """`platform/migrate.apply_migrations` wraps each file and its ledger row in ONE transaction.
    `CREATE INDEX CONCURRENTLY` cannot run in a transaction block, so a concurrent build here
    would not be safer — it would raise, and `main.lifespan` applies migrations before the API
    serves, so the raise is a boot failure."""
    from genios_engine.platform.migrate import _split_statements

    sql = io.open("migrations/0173_raw_payloads_is_looked_up_by_event.sql",
                  encoding="utf-8").read()
    # THE STATEMENTS, not the file. The word appears in the comment that explains why it is not
    # used, and a check against the prose passes on the explanation instead of the DDL — which is
    # the same mistake `test_the_funnel_report_counts_losses_from_the_declared_set` had to fix.
    statements = _split_statements(sql)

    assert len(statements) == 1, "one statement, so one transaction is enough"
    assert "concurrently" not in statements[0].lower()
