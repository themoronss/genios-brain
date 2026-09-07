"""H6's gate command — *is any registered pattern firing on everything, and is any firing on
nothing?*

    python -m scripts.pattern_fire_report --org <pilot> --since 30d --database-url <url>

WHY A SCRIPT AND NOT A TEST. `tests/context/patterns/` proves the guard's arithmetic against
fixtures a test wrote. It cannot prove a pattern is well calibrated for a TENANT, because
calibration is a property of that tenant's data and not of the code: `vendor_renewal_unowned` is
tight on an org with forty subscriptions and may be noise on one with four thousand. Layer 1 shipped
fifteen of twenty-one deep sales rules gated on a field 9% of records carried — every test green,
every rule dead — and the number that would have caught it is a COUNT on real rows, which nobody
was printing.

WHAT IT PRINTS, and why each line is here rather than in a dashboard nobody opens:

* **fires / anchors / observed rate** per pattern, against the rate the pattern DECLARED and the
  10x ceiling. The rate is normalised to fires per 100 anchors per 30 days so two operators
  reading different windows are reading the same number.
* **ACTIVATED**, because the H6 gate row is *"0 patterns ACTIVATED while exceeding their expected
  fire rate 10x"*. A shadow pattern over its ceiling is a calibration note; an activated one is a
  queue full of noise, and only the second is a breach.
* **SILENT** — every registered pattern with zero fires in the window, which doc 06 asks be
  *"reported for review"*. Reported and not failed: a pattern can legitimately have nothing to
  say on a small tenant.
* **the failing condition**, for every silent pattern that was actually evaluated. This is the
  line that turns "this pattern is silent" into "condition 2 (`commitment.due_at`) failed on all
  412 anchors, reason `temporal_missing`" — the difference between a mystery and a fix.
* **patterns never evaluated at all**, which is a different fault from a silent one: it means no
  anchor of that node type exists here, or the evaluation has never been run.

READ-ONLY, BY CONSTRUCTION. Every statement is a `select`. It resolves its target through
`scripts/_db.py`, so it cannot inherit the production URL sitting in `.env`, and it takes `--as-of`
rather than a clock so two runs over the same window are comparable. Exit code 1 on a DEMONSTRATED
breach — an activated pattern over its ceiling — so this is usable in a deploy gate and not only
by a human reading it.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.patterns.registry import (FIRE_RATE_CAP_MULTIPLIER,
                                                     activation_decision,
                                                     observed_rate_per_100_anchors_30d,
                                                     seed_registry)
from genios_engine.context.patterns.store import fire_observations
from genios_engine.platform.db import get_engine
from scripts._db import add_database_argument, resolve_database_url

_SINCE = re.compile(r"^(\d+)\s*d(ays?)?$", re.IGNORECASE)


def parse_since(value: str) -> int:
    """`30d` → 30. The gate command writes `--since 30d`, so the script accepts that spelling
    rather than making an operator translate it and get it wrong once."""
    text_value = str(value).strip()
    if text_value.isdigit():
        return int(text_value)
    hit = _SINCE.match(text_value)
    if not hit:
        raise argparse.ArgumentTypeError(f"--since takes days, e.g. 30d or 30 (got {value!r})")
    return int(hit.group(1))


def _fetch(conn, org: str, *, since: datetime, until: datetime) -> dict:
    observations = fire_observations(conn, org, since=since, until=until)
    failures = {r["pattern_id"]: r for r in conn.execute(text(
        "select distinct on (pattern_id) pattern_id, top_failure_index, top_failure_reason, "
        "       top_failure_field, anchors_considered, evaluated_at "
        "from pattern_runs where org_id = :o and evaluated_at >= :since "
        "and evaluated_at <= :until order by pattern_id, evaluated_at desc"),
        {"o": org, "since": since, "until": until}).mappings().all()}
    activated = {r["pattern_id"] for r in conn.execute(text(
        "select pattern_id from pattern_activation "
        "where org_id = :o and activated_at is not null"), {"o": org}).mappings().all()}
    stored_fires = {r["pattern_id"]: int(r["n"]) for r in conn.execute(text(
        "select pattern_id, count(*) as n from pattern_fires where org_id = :o "
        "and evaluated_at >= :since and evaluated_at <= :until group by pattern_id"),
        {"o": org, "since": since, "until": until}).mappings().all()}
    return {"observations": observations, "failures": failures, "activated": activated,
            "stored_fires": stored_fires}


def activated_breaches(report: dict) -> list[str]:
    """The H6 gate row, as a list: patterns that are ACTIVATED for this tenant and have been
    measured firing above their ceiling.

    Computed once and read by both `render` and `main`, rather than `main` parsing the lines it
    just printed — a gate whose exit code is derived from its own prose fails the day somebody
    rewords a line.
    """
    registry = seed_registry()
    by_id = {o.pattern_id: o for o in report["observations"]}
    out = []
    for pattern in registry.all():
        observation = by_id.get(pattern.pattern_id)
        if observation is None or pattern.pattern_id not in report["activated"]:
            continue
        if not activation_decision(pattern, observation).allowed:
            out.append(pattern.pattern_id)
    return out


def render(report: dict, org: str, *, since: datetime, until: datetime) -> list[str]:
    """The report as lines. Separated from printing so a test can assert on it, and so an operator
    filing the output somewhere does not have to capture stdout."""
    registry = seed_registry()
    by_id = {o.pattern_id: o for o in report["observations"]}
    window_days = max(1, int((until - since).total_seconds()) // 86_400)
    out = [f"pattern fire report · org={org} · window={window_days}d "
           f"({since.date()} → {until.date()})",
           f"  registered patterns {len(registry)}   ceiling {FIRE_RATE_CAP_MULTIPLIER}x the "
           "declared rate"]

    breaches = activated_breaches(report)
    silent: list[str] = []
    unevaluated: list[str] = []
    for pattern in registry.all():
        observation = by_id.get(pattern.pattern_id)
        activated = pattern.pattern_id in report["activated"]
        mark = "ACTIVATED" if activated else "shadow   "
        if observation is None:
            unevaluated.append(pattern.pattern_id)
            out.append(f"  {mark}  {pattern.pattern_id:<26} never evaluated in this window")
            continue
        decision = activation_decision(pattern, observation)
        rate = observed_rate_per_100_anchors_30d(observation)
        stored = report["stored_fires"].get(pattern.pattern_id, 0)
        clipped = "" if stored >= observation.fires else f" (stored {stored}, budget-clipped)"
        out.append(
            f"  {mark}  {pattern.pattern_id:<26} fires {observation.fires:>5}"
            f" / anchors {observation.anchors:<6} {rate:>5} per100/30d "
            f"(declared {decision.expected_rate}, ceiling {decision.ceiling_rate}){clipped}")
        if not decision.allowed:
            # A shadow pattern over its ceiling is a calibration note. An ACTIVATED one is the
            # gate row, and only that one fails the command.
            out.append(f"      !! over ceiling — {decision.reason}")
        if observation.fires == 0:
            silent.append(pattern.pattern_id)
            failure = report["failures"].get(pattern.pattern_id)
            if failure is not None and failure["top_failure_reason"]:
                out.append(
                    f"      silent — condition {failure['top_failure_index']} "
                    f"({failure['top_failure_field']}) failed most often: "
                    f"{failure['top_failure_reason']}, over "
                    f"{failure['anchors_considered']} anchors")
            else:
                out.append("      silent — no failing condition recorded; the anchor population "
                           "may be empty")

    out.append(f"  silent patterns      {len(silent)}"
               + (f"  {silent}" if silent else "  (none)"))
    out.append(f"  never evaluated      {len(unevaluated)}"
               + (f"  {unevaluated}" if unevaluated else "  (none)"))
    out.append(f"  ACTIVATED over 10x   {len(breaches)}"
               + (f"  {breaches}   ← H6 gate row: must be 0" if breaches else "  ← H6 gate row"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--org", required=True, help="the tenant to report on")
    ap.add_argument("--since", default="30d", type=parse_since,
                    help="window in days, e.g. 30d (default 30d — the window every declared "
                         "expected_fire_rate is stated in)")
    ap.add_argument("--as-of", default=None,
                    help="ISO-8601 instant the window ends at (default: now, UTC). Given "
                         "explicitly, two operators compare the same window.")
    add_database_argument(ap)
    args = ap.parse_args()

    until = (datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc))
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    since = until - timedelta(days=args.since)

    url = resolve_database_url(args, purpose="pattern fire report (read-only)")
    with get_engine(url).connect() as conn:
        report = _fetch(conn, args.org, since=since, until=until)
    lines = render(report, args.org, since=since, until=until)
    for line in lines:
        print(line)
    # Exit 1 only on a DEMONSTRATED breach: a pattern that is activated for this tenant and has
    # been measured firing above its ceiling. A silent pattern is reported, never failed — doc 06
    # asks for review, not for a red build, and a gate that failed on silence would be red on
    # every small tenant on day one.
    return 1 if activated_breaches(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
