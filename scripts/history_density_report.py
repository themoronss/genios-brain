"""H1's second gate command — *is `metric_history` bounded, on the data that is actually there?*

    python -m scripts.history_density_report --org <pilot> --database-url <url>

WHY A SCRIPT AND NOT A TEST. `tests/context/analytic/test_metric_history.py` proves the four
bounding mechanisms hold for the rows a test writes. It cannot prove they hold for the rows a
TENANT accumulates, because the multiplier that matters — how many (node, metric) series a real
graph opens — is a property of the tenant, not of the code. `expertise_packages` reached 181 MB
over 345 rows and took production read-only with every one of its tests green; the number that
would have caught it was rows-and-bytes on the live table, and nobody was printing one.

WHAT IT PRINTS, and why each line is here rather than in a dashboard nobody opens:

* **rows, series, bytes** — the three numbers the incident was about. Bytes come from
  `pg_total_relation_size` filtered by nothing, so it is the WHOLE table including its three
  indexes; the per-org share is prorated by row count, which is honest about being an estimate.
* **points per series** (max / p50) against `MAX_RETAINED_PERIODS`. Mechanism 3 caps this on the
  write path, so a series ABOVE the cap is a trim that did not run — the loudest failure this
  table has, and invisible in a row total.
* **rows written per period** — the actual monthly arrival rate for this tenant, measured rather
  than modelled, plus the steady state it implies: `arrivals x retention`. That is the number to
  compare against the sampler's declared budget.
* **the oldest period held** against the `RETENTION_MONTHS` horizon. A row older than the horizon
  is a prune that has not run — which happens to a tenant that stopped draining, and is exactly
  the case mechanism 4 exists for.
* **duplicate period keys** — always 0, because the primary key makes it so. Printed anyway: it
  is the double-sweep claim stated as a measurement, and if it is ever non-zero the primary key
  has been altered and every trend in the system is arithmetic over incomparable readings.

READ-ONLY, BY CONSTRUCTION. Every statement here is a `select`. The script never prunes, never
trims and never writes: it reports, and a human decides. It reads its target through
`scripts/_db.py`, so it cannot reach production without two deliberate acts, and it takes
`--as-of` rather than a clock so two operators comparing notes are comparing the same window.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context.analytic.history import (HISTORY_TABLE, MAX_RETAINED_PERIODS,
                                                    RETENTION_MONTHS, months_before)
from genios_engine.platform.db import get_engine
from scripts._db import add_database_argument, resolve_database_url

#: One row of `metric_history` on disk, INCLUDING its three indexes. Measured, not estimated:
#: 110,000 rows written to a real Postgres gave 140 B/row of heap and 249 B/row of index. The
#: index cost being larger than the row is the whole reason this constant is not the 120 B a
#: column-width calculation gives — and a projection built on 120 understates a tenant by 3.25x,
#: which on this table is the difference between "25 MB" and "81 MB".
NOMINAL_ROW_BYTES = 390


def _fetch(conn, org: str, as_of: datetime) -> dict:
    horizon = months_before(as_of, RETENTION_MONTHS)
    totals = conn.execute(text(f"""
        select count(*) as rows,
               count(distinct (subject_node_id, metric)) as series,
               count(distinct subject_node_id) as nodes,
               count(distinct metric) as metrics,
               min(observed_at) as oldest,
               max(observed_at) as newest,
               count(*) filter (where observed_at < :horizon) as past_horizon
          from {HISTORY_TABLE} where org_id = :o"""), {"o": org, "horizon": horizon}).one()

    per_series = conn.execute(text(f"""
        select max(n) as longest,
               (percentile_disc(0.5) within group (order by n))::int as median
          from (select count(*) as n from {HISTORY_TABLE} where org_id = :o
                 group by subject_node_id, metric) s"""), {"o": org}).one()

    per_period = conn.execute(text(f"""
        select observed_at, count(*) as rows from {HISTORY_TABLE}
         where org_id = :o group by observed_at order by observed_at desc limit 6"""),
        {"o": org}).all()

    # Always 0 while the primary key stands. Asked anyway — see the module docstring.
    duplicates = conn.execute(text(f"""
        select count(*) from (select 1 from {HISTORY_TABLE} where org_id = :o
                               group by subject_node_id, metric, observed_at
                              having count(*) > 1) d"""), {"o": org}).scalar()

    table_bytes = conn.execute(text(
        "select pg_total_relation_size(:t)"), {"t": HISTORY_TABLE}).scalar() or 0
    all_rows = conn.execute(text(f"select count(*) from {HISTORY_TABLE}")).scalar() or 0
    return {"totals": totals, "per_series": per_series, "per_period": per_period,
            "duplicates": int(duplicates or 0), "table_bytes": int(table_bytes),
            "all_rows": int(all_rows), "horizon": horizon}


def _org_bytes(table_bytes: int, org_rows: int, all_rows: int) -> int:
    """This org's prorated share of the table, including indexes. Integer arithmetic, and the
    empty table answers with the nominal row size rather than dividing by zero."""
    if all_rows <= 0 or table_bytes <= 0:
        return org_rows * NOMINAL_ROW_BYTES
    return table_bytes * org_rows // all_rows


def _retained_periods(per_period) -> tuple[int, str]:
    """How many periods retention keeps for THIS series, read off the data's own spacing.

    The two caps are not interchangeable and using the wrong one is a 4x error in the projection:
    a weekly series keeps `MAX_RETAINED_PERIODS` (104) points and a monthly one keeps
    `RETENTION_MONTHS` (24). The grain is a property of the metric definition, but this report is
    deliberately read only off the TABLE — a projection that trusted the registry would keep
    reporting the intended shape after a definition changed and the rows on disk did not. Two
    consecutive `observed_at` values no more than eight days apart is a weekly series; anything
    else is monthly. Falls back to monthly (the SMALLER retention, so the projection is never
    flattered) when there is only one period to look at.
    """
    if len(per_period) < 2:
        return RETENTION_MONTHS, "period"
    gap_days = abs((per_period[0].observed_at - per_period[1].observed_at).days)
    if gap_days <= 8:
        return MAX_RETAINED_PERIODS, "week"
    return RETENTION_MONTHS, "month"


def render(report: dict, org: str, as_of: datetime) -> list[str]:
    """The report as lines. Separated from printing so a test can assert on it, and so a caller
    that wants to file the output somewhere does not have to capture stdout."""
    t, s = report["totals"], report["per_series"]
    rows, series = int(t.rows or 0), int(t.series or 0)
    longest = int(s.longest or 0)
    org_bytes = _org_bytes(report["table_bytes"], rows, report["all_rows"])

    out = [f"{HISTORY_TABLE} density · org={org} · as_of={as_of.isoformat()}",
           f"  rows                {rows}",
           f"  series (node,metric){series:>8}   over {int(t.nodes or 0)} nodes "
           f"x {int(t.metrics or 0)} metrics",
           f"  size (prorated)     {org_bytes // 1024} KiB "
           f"(whole table {report['table_bytes'] // 1024} KiB incl. indexes)"]

    if series:
        out.append(f"  points/series       max {longest}, median {int(s.median or 0)}   "
                   f"cap {MAX_RETAINED_PERIODS}")
        if longest > MAX_RETAINED_PERIODS:
            out.append(f"  !! a series holds {longest} points and the cap is "
                       f"{MAX_RETAINED_PERIODS} — mechanism 3 (the per-series trim on `put`) is "
                       "not running")

    if report["per_period"]:
        out.append("  arrivals per period (newest first):")
        for row in report["per_period"]:
            out.append(f"    {row.observed_at.date()}  {int(row.rows)}")
        newest = int(report["per_period"][0].rows)
        retained, grain = _retained_periods(report["per_period"])
        out.append(f"  steady state        ~{newest * retained} rows "
                   f"({newest}/{grain} x {retained} periods retained) "
                   f"~= {newest * retained * NOMINAL_ROW_BYTES // 1024} KiB "
                   f"at {NOMINAL_ROW_BYTES} B/row incl. indexes")

    out.append(f"  oldest period held  {t.oldest.date() if t.oldest else '-'}   "
               f"horizon {report['horizon'].date()}")
    if int(t.past_horizon or 0):
        out.append(f"  !! {int(t.past_horizon)} rows are older than the {RETENTION_MONTHS}-month "
                   "horizon — mechanism 4 (the prune on the drain) has not run for this org")
    out.append(f"  duplicate period keys {report['duplicates']}"
               + ("" if not report["duplicates"] else
                  "   !! the primary key is not holding — re-sampling has doubled a series"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--org", required=True, help="the tenant to report on")
    ap.add_argument("--as-of", default=None,
                    help="ISO-8601 instant the retention horizon is measured from "
                         "(default: now, UTC). Given explicitly, two operators compare the same "
                         "window.")
    add_database_argument(ap)
    args = ap.parse_args()

    as_of = (datetime.fromisoformat(args.as_of) if args.as_of
             else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    url = resolve_database_url(args, purpose="metric_history density report (read-only)")
    with get_engine(url).connect() as conn:
        report = _fetch(conn, args.org, as_of)
    for line in render(report, args.org, as_of):
        print(line)
    # Exit 1 when a bounding mechanism is demonstrably not running, so this is usable in a
    # deploy gate and not only by a human reading it.
    breached = (report["duplicates"] > 0
                or int(report["totals"].past_horizon or 0) > 0
                or int(report["per_series"].longest or 0) > MAX_RETAINED_PERIODS)
    return 1 if breached else 0


if __name__ == "__main__":
    raise SystemExit(main())
