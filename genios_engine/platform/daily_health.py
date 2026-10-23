"""One health row per org per day, with alerts (GeniOS-011 S05.U1).

⛔ WHY THIS EXISTS. Nothing measured production card volume or quality daily
(`process-no-daily-production-card-health`). `scripts/pipeline_health.py`, `scripts/runtime_receipts.py` and
`scripts/l2_shadow_report.py` are manual CLIs that nothing runs; the funnel writes its five numbers on every
pass and `funnel.read_sweep` / `read_latest` have no caller; `pipeline_health.check_cards_reach_the_app` counts
live cards only, with no "cards per day against a baseline"; and `ops_alert` fired on a sweep crash, a sync
failure, the LLM cap and warm-lane parks — never on card volume or quality. Meanwhile the database reached its
500 MB tier twice in 17 days (9a51d0ea on 2 Oct, 7cab0ad4 on 19 Oct: 999 MB, `cross-db-tier-never-budgeted`)
with no daily size line anywhere. A release gate (S05.U3) needs all of it, and so does an operator.

WHAT IT WRITES. Once a day, for every tenant that can produce cards, one `daily_health` row (migration 0251)
for YESTERDAY in UTC — a whole day, never one still in progress — computed from the tables that already hold
the facts, so nothing upstream changes to feed it:

    cards              cards               {builder_version: {output_lane: n}}
    card_refusals      card_refusals       {rule: n}
    expert_reviews     expert_reviews      {status: n}
    reasoning_results  reasoning_results   {status: n}
    l2_admissions      l2_admissions       {decision: n}
    funnel             pipeline_counters   {stage: n | None} — the day's sweeps summed; None = no sweep wrote it
    llm_*              llm_costs           calls, failures (`not success`), truncations (the client's error)
    r_site_calls       l4_r_site_calls     {outcome: n}
    database_bytes     pg_database_size    when the row was written

and the alerts the row raised, kept on the row and sent through `ops_alert`:

    cards_below_half_median   cards that day < half the median of the 14 days before (zeros counted)
    lane_no_data              a lane whose 14-day median is above zero — it ran on most days — read
                              nothing for the whole day: NO DATA for 24 h
    database_over_ceiling     pg_database_size past the ceiling (once per run, not once per org)
    plan_expired              the tenant's plan was EXPIRED at the end of the day, so every scheduled sweep
                              skipped it (`api/routes._plan_expired`, since 7075014c) — GeniOS-012 U12-01

⛔ AN EXPIRED PLAN IS NEVER SILENT AGAIN (GeniOS-012 U12-01). The sweep skips a lapsed tenant entirely, which is
right for spend and was invisible: the founder's own org stopped on 21 Sep and nobody saw it for a month. The row
carries `plan_state` (`active` | `grace` | `expired`, `platform/billing.expiry_state`, read at the end of the
row's day) and an expired tenant raises `plan_expired` — once a day, by the row's own key.

⛔ THE BASELINE IS READ FROM THE SOURCE TABLES, NOT FROM EARLIER ROWS. The row's day and the 14 before it are
one grouped read per table, so the drop alert works on the first day the job runs, and a day the job missed
(a deploy, a crashed tick) does not shorten the baseline. The median the alert used is stored on the row, so
"why did this fire" is answered by the row itself.

⛔ A LANE IS NO DATA ONLY IF IT USUALLY HAS DATA. "Had data once in 14 days" would make every sparse lane — the
conflict lane, a shadow feature that wrote twice — alert most days, and an alert that fires every day is read
by nobody. The same median as the volume alert decides: a lane whose median day is zero is not expected.
A funnel stage is present when a sweep WROTE it, even a zero (0188: zero = it ran, no row = nobody looked).

ONCE A DAY MEANS ONCE. The row's key is (org, day) and the insert is `on conflict do nothing`: a second heavy
tick, a second replica or a re-run writes nothing and sends nothing, and an alert is sent only for a row this
run inserted. Orgs that already have the day's row are skipped before any read.

BOUNDED. The run that writes deletes rows older than `RETENTION_DAYS`: a few months per tenant, never a row per
sweep — the 500 MB plan this row exists to watch.

NEVER RAISES. `run_daily_health` returns what happened, an `error` included; one tenant's failure is counted
and the rest are still measured. The scheduler runs it after the heavy tick under its own guard.
"""
from __future__ import annotations

import json
import os
import statistics
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone
from typing import Any

from sqlalchemy import text

from genios_engine.platform import funnel
from genios_engine.platform import ops_alert
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.daily_health")

UNIT = "GeniOS-011 S05.U1"

#: The baseline: the 14 whole days before the row's day.
WINDOW_DAYS = 14

#: ⛔ THE THRESHOLD. Cards that day below this fraction of the 14-day median alert. Strictly below: at
#: exactly half, nothing fires (the audit's words: "fall below half of the 14-day median").
BELOW_MEDIAN_FRACTION = 0.5

#: Rows kept per tenant. The admin chart shows 30 days and the baseline reads 14; four months covers both
#: with room for a month-on-month comparison, and stays a few hundred rows per tenant.
RETENTION_DAYS = 120

#: The database ceiling. The plan's tier is 500 MB and production sat at 446 MB after the 19 Oct purge
#: (7cab0ad4); 450 MB says "you are within 10% of read-only" while there is still time to purge. An
#: operator moves it with this variable (megabytes), without a deploy of code.
DEFAULT_CEILING_MB = 450
CEILING_ENV = "GENIOS_DB_SIZE_CEILING_MB"

#: `llm_costs.error` for a cut answer starts with `context/llm/client.TRUNCATED` ("truncated: the model hit
#: max_tokens …"). Counted by the error and not by `success`: a cut the lenient parser closed is written
#: `success=True` with the error set (client.py, M50.C1.L-contract.V0.U01). A prefix rather than an import:
#: `platform/` sits below `context/` in the layer topology. `test_daily_health_pg` holds the two together.
TRUNCATED_PREFIX = "truncated:"

#: A card with no builder_version / output_lane is still a card; it is counted under these names.
NO_BUILDER = "none"
NO_LANE = "unrouted"

ALERT_CARDS = "cards_below_half_median"
ALERT_LANE = "lane_no_data"
ALERT_DB = "database_over_ceiling"
ALERT_PLAN = "plan_expired"


# ── the reads ───────────────────────────────────────────────────────────────────────────────────
# Every per-tenant read covers [start, end): the row's day and the WINDOW_DAYS before it, grouped by UTC day.
# The same read is S01.U1's `scripts/g011_prod_readings` per-day SQL with a closed window.

_ORGS = text(
    "select org_id from connections where status = 'connected' "
    "union select org_id from tenant_packs where state = 'active'")

_ALREADY_WRITTEN = text("select org_id from daily_health where day = :day")

_CARDS = text(
    "select (created_at at time zone 'UTC')::date as day, coalesce(builder_version, :nb) as k1, "
    "coalesce(output_lane, :nl) as k2, count(*) as n from cards "
    "where org_id = :org and created_at >= :start and created_at < :end group by 1, 2, 3")

_REFUSALS = text(
    "select (refused_at at time zone 'UTC')::date as day, rule as k, count(*) as n from card_refusals "
    "where org_id = :org and refused_at >= :start and refused_at < :end group by 1, 2")

_EXPERT = text(
    "select (reviewed_at at time zone 'UTC')::date as day, status as k, count(*) as n from expert_reviews "
    "where org_id = :org and reviewed_at >= :start and reviewed_at < :end group by 1, 2")

_REASONING = text(
    "select (reasoned_at at time zone 'UTC')::date as day, status as k, count(*) as n from reasoning_results "
    "where org_id = :org and reasoned_at >= :start and reasoned_at < :end group by 1, 2")

_ADMISSIONS = text(
    "select (decided_at at time zone 'UTC')::date as day, decision as k, count(*) as n from l2_admissions "
    "where org_id = :org and decided_at >= :start and decided_at < :end group by 1, 2")

#: `rows` is how many sweeps wrote the stage; `n` the day's sum. A stage present with n = 0 RAN.
_FUNNEL = text(
    "select (sweep_at at time zone 'UTC')::date as day, stage as k, count(*) as rows, sum(n) as n "
    "from pipeline_counters where org_id = :org and sweep_at >= :start and sweep_at < :end group by 1, 2")

_LLM = text(
    "select (created_at at time zone 'UTC')::date as day, count(*) as calls, "
    "count(*) filter (where not success) as failed, "
    "count(*) filter (where error like :cut) as truncated from llm_costs "
    "where org_id = :org and created_at >= :start and created_at < :end group by 1")

_R_SITE = text(
    "select (created_at at time zone 'UTC')::date as day, outcome as k, count(*) as n from l4_r_site_calls "
    "where org_id = :org and created_at >= :start and created_at < :end group by 1, 2")

_DB_SIZE = text("select pg_database_size(current_database())")

_PLAN = text("select plan_status, plan_expires_at, grace_until from orgs where id = :org")

_INSERT = text(
    "insert into daily_health (org_id, day, cards, cards_total, card_refusals, expert_reviews, "
    "reasoning_results, l2_admissions, funnel, llm_calls, llm_failures, llm_truncations, r_site_calls, "
    "database_bytes, cards_median_14d, alerts, measured_at, plan_state) values (:org, :day, cast(:cards as jsonb), "
    ":cards_total, cast(:card_refusals as jsonb), cast(:expert_reviews as jsonb), "
    "cast(:reasoning_results as jsonb), cast(:l2_admissions as jsonb), cast(:funnel as jsonb), :llm_calls, "
    ":llm_failures, :llm_truncations, cast(:r_site_calls as jsonb), :database_bytes, :cards_median_14d, "
    "cast(:alerts as jsonb), :measured_at, :plan_state) on conflict (org_id, day) do nothing returning org_id")

_PURGE = text("delete from daily_health where day < :cutoff")


# ── the pure rules ──────────────────────────────────────────────────────────────────────────────

def ceiling_bytes() -> int:
    """The database ceiling in bytes: `GENIOS_DB_SIZE_CEILING_MB`, or 450 MB when unset or unreadable."""
    raw = os.environ.get(CEILING_ENV, "").strip()
    try:
        mb = float(raw) if raw else float(DEFAULT_CEILING_MB)
    except ValueError:
        _log.warning("%s=%r is not a number of megabytes; using %s", CEILING_ENV, raw, DEFAULT_CEILING_MB)
        mb = float(DEFAULT_CEILING_MB)
    return int(mb * 1024 * 1024)


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def cards_alert(cards_today: int, baseline: Sequence[int]) -> dict | None:
    """The volume alert, or None: cards that day strictly below half the baseline median.

    A median of zero never alerts — nothing is below half of nothing — so a new or quiet tenant is silent
    until it has a volume to fall from."""
    median = _median(baseline)
    if median > 0 and cards_today < median * BELOW_MEDIAN_FRACTION:
        return {"kind": ALERT_CARDS, "cards": cards_today, "median_14d": median,
                "threshold": median * BELOW_MEDIAN_FRACTION}
    return None


def lanes_no_data(today: Mapping[str, int], baseline: Sequence[Mapping[str, int]]) -> list[str]:
    """The lanes whose 14-day median is above zero and that read nothing on the row's day, sorted."""
    names = set(today)
    for day in baseline:
        names.update(day)
    return sorted(name for name in names
                  if today.get(name, 0) == 0 and _median([day.get(name, 0) for day in baseline]) > 0)


# ── the measurement ─────────────────────────────────────────────────────────────────────────────

def plan_state(conn, org_id: str, at: datetime) -> dict:
    """The tenant's plan at `at`: {"state": active|grace|expired|None, "plan_expires_at", "grace_until"}.

    `state` is None when the org row cannot be read — unknown, never guessed as active or expired."""
    from genios_engine.platform.billing import expiry_state
    row = conn.execute(_PLAN, {"org": org_id}).first()
    if row is None:
        return {"state": None, "plan_expires_at": None, "grace_until": None}
    return {"state": expiry_state(row.plan_status, row.plan_expires_at, row.grace_until, now=at),
            "plan_expires_at": row.plan_expires_at, "grace_until": row.grace_until}


def plan_alert(plan: Mapping[str, Any]) -> dict | None:
    """`plan_expired` when the plan was expired, else None. Pure."""
    if plan.get("state") != "expired":
        return None
    def iso(value):
        return value.isoformat() if hasattr(value, "isoformat") else value
    return {"kind": ALERT_PLAN, "plan_expires_at": iso(plan.get("plan_expires_at")),
            "grace_until": iso(plan.get("grace_until")),
            "says": "every scheduled sweep skipped this tenant: no capture, no reasoning, no cards"}


def _days(day: date) -> list[date]:
    """The baseline days, oldest first, then the row's day last."""
    return [day - timedelta(days=back) for back in range(WINDOW_DAYS, -1, -1)]


def _keyed(conn, statement, params: Mapping[str, Any]) -> dict[date, dict[str, int]]:
    out: dict[date, dict[str, int]] = {}
    for r in conn.execute(statement, dict(params)):
        out.setdefault(r.day, {})[r.k] = int(r.n)
    return out


def measure_day(conn, org_id: str, day: date) -> dict:
    """The row's numbers for `day`, and the per-day lanes and card totals of the 14 days before it.

    Returns {"row": {...the daily_health columns...}, "cards_by_day": [int, ...], "lanes_by_day": [...]},
    both lists oldest first with the row's day last."""
    start = datetime.combine(day - timedelta(days=WINDOW_DAYS), time.min, tzinfo=timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone.utc)
    p = {"org": org_id, "start": start, "end": end}

    cards: dict[date, dict[str, dict[str, int]]] = {}
    for r in conn.execute(_CARDS, {**p, "nb": NO_BUILDER, "nl": NO_LANE}):
        cards.setdefault(r.day, {}).setdefault(r.k1, {})[r.k2] = int(r.n)
    refusals = _keyed(conn, _REFUSALS, p)
    expert = _keyed(conn, _EXPERT, p)
    reasoning = _keyed(conn, _REASONING, p)
    admissions = _keyed(conn, _ADMISSIONS, p)
    funnel_rows: dict[date, dict[str, tuple[int, int]]] = {}
    for r in conn.execute(_FUNNEL, p):
        funnel_rows.setdefault(r.day, {})[r.k] = (int(r.rows), int(r.n))
    llm = {r.day: (int(r.calls), int(r.failed), int(r.truncated))
           for r in conn.execute(_LLM, {**p, "cut": TRUNCATED_PREFIX + "%"})}
    r_site = _keyed(conn, _R_SITE, p)

    def lanes(d: date) -> dict[str, int]:
        out: dict[str, int] = {}
        for builder, by_lane in cards.get(d, {}).items():
            for lane, n in by_lane.items():
                out[f"cards.builder:{builder}"] = out.get(f"cards.builder:{builder}", 0) + n
                out[f"cards.lane:{lane}"] = out.get(f"cards.lane:{lane}", 0) + n
        out["expert_reviews"] = sum(expert.get(d, {}).values())
        out["reasoning_results"] = sum(reasoning.get(d, {}).values())
        out["l2_admissions"] = sum(admissions.get(d, {}).values())
        out["llm_calls"] = llm.get(d, (0, 0, 0))[0]
        for stage in funnel.STAGES:
            out[f"funnel:{stage}"] = funnel_rows.get(d, {}).get(stage, (0, 0))[0]
        return out

    days = _days(day)
    calls, failed, truncated = llm.get(day, (0, 0, 0))
    row = {
        "cards": cards.get(day, {}),
        "cards_total": sum(sum(by_lane.values()) for by_lane in cards.get(day, {}).values()),
        "card_refusals": refusals.get(day, {}),
        "expert_reviews": expert.get(day, {}),
        "reasoning_results": reasoning.get(day, {}),
        "l2_admissions": admissions.get(day, {}),
        "funnel": {stage: (funnel_rows[day][stage][1] if stage in funnel_rows.get(day, {}) else None)
                   for stage in funnel.STAGES},
        "llm_calls": calls, "llm_failures": failed, "llm_truncations": truncated,
        "r_site_calls": r_site.get(day, {}),
        # GeniOS-012 U12-01 · the plan at the END of the row's day — what the day's last sweep saw.
        "plan": plan_state(conn, org_id, end),
    }
    return {"row": row,
            "cards_by_day": [sum(sum(v.values()) for v in cards.get(d, {}).values()) for d in days],
            "lanes_by_day": [lanes(d) for d in days]}


def orgs_to_measure(conn) -> list[str]:
    """Every tenant that can produce cards: a connected source, or an active pack.

    Both, on purpose: a tenant whose only connection broke is exactly the one whose cards stop, and
    "connected only" would stop measuring it on the day it matters."""
    return sorted({r[0] for r in conn.execute(_ORGS)})


def _alerts(measured: Mapping[str, Any], database_bytes: int | None, ceiling: int) -> list[dict]:
    out: list[dict] = []
    cards_by_day = measured["cards_by_day"]
    volume = cards_alert(cards_by_day[-1], cards_by_day[:-1])
    if volume:
        out.append(volume)
    dark = lanes_no_data(measured["lanes_by_day"][-1], measured["lanes_by_day"][:-1])
    if dark:
        out.append({"kind": ALERT_LANE, "lanes": dark})
    if database_bytes is not None and database_bytes > ceiling:
        out.append({"kind": ALERT_DB, "bytes": database_bytes, "ceiling_bytes": ceiling})
    lapsed = plan_alert(measured["row"].get("plan") or {})
    if lapsed:
        out.append(lapsed)
    return out


def _write(engine, org_id: str, day: date, measured: Mapping[str, Any], *, database_bytes: int | None,
           alerts: list[dict], measured_at: datetime) -> bool:
    row = measured["row"]
    params = {"org": org_id, "day": day, "measured_at": measured_at, "database_bytes": database_bytes,
              "cards_median_14d": _median(measured["cards_by_day"][:-1]),
              "alerts": json.dumps(alerts), "cards_total": row["cards_total"],
              "llm_calls": row["llm_calls"], "llm_failures": row["llm_failures"],
              "llm_truncations": row["llm_truncations"],
              "plan_state": (row.get("plan") or {}).get("state")}
    for column in ("cards", "card_refusals", "expert_reviews", "reasoning_results", "l2_admissions",
                   "funnel", "r_site_calls"):
        params[column] = json.dumps(row[column])
    with engine.begin() as c:
        return c.execute(_INSERT, params).first() is not None


def run_daily_health(engine, *, now: datetime | None = None, orgs: Iterable[str] | None = None,
                     ceiling: int | None = None) -> dict:
    """Write yesterday's row for every tenant that has none yet, and send the alerts those rows raised.

    `orgs` narrows the run (tests, an operator); by default every tenant `orgs_to_measure` names. `ceiling`
    (bytes) overrides `ceiling_bytes()`. Never
    raises: an `error` key says the run itself failed, `failed` names the tenants whose row could not be
    measured."""
    try:
        return _run(engine, now=now or datetime.now(timezone.utc), orgs=orgs,
                    ceiling=ceiling if ceiling is not None else ceiling_bytes())
    except Exception as exc:                                   # noqa: BLE001 — a health read never fails a tick
        _log.exception("daily health run failed")
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}


def _run(engine, *, now: datetime, orgs: Iterable[str] | None, ceiling: int) -> dict:
    day = now.astimezone(timezone.utc).date() - timedelta(days=1)
    with engine.connect() as c:
        wanted = sorted(set(orgs)) if orgs is not None else orgs_to_measure(c)
        done = {r[0] for r in c.execute(_ALREADY_WRITTEN, {"day": day})}
        todo = [o for o in wanted if o not in done]
        database_bytes = int(c.execute(_DB_SIZE).scalar() or 0) if todo else None
    written: list[str] = []
    failed: list[str] = []
    db_alert: dict | None = None
    for org in todo:
        try:
            with engine.connect() as c:
                measured = measure_day(c, org, day)
            alerts = _alerts(measured, database_bytes, ceiling)
            if not _write(engine, org, day, measured, database_bytes=database_bytes, alerts=alerts,
                          measured_at=now):
                continue                                       # another tick or replica wrote it first
        except Exception:                                      # noqa: BLE001 — one tenant ≠ the rest
            _log.exception("daily health failed org=%s day=%s", org, day)
            failed.append(org)
            continue
        written.append(org)
        for alert in alerts:
            if alert["kind"] == ALERT_DB:
                db_alert = alert
                continue
            ops_alert.notify(f"daily_health_{alert['kind']}", org_id=org, day=day.isoformat(),
                             **{k: v for k, v in alert.items() if k != "kind"})
    if db_alert:
        # A fact about the server, not the tenant: once per run, however many rows carry it.
        ops_alert.notify(f"daily_health_{ALERT_DB}", day=day.isoformat(), bytes=db_alert["bytes"],
                         ceiling_bytes=db_alert["ceiling_bytes"], orgs=len(written))
    purged = 0
    if written:
        with engine.begin() as c:
            purged = c.execute(_PURGE, {"cutoff": day - timedelta(days=RETENTION_DAYS)}).rowcount or 0
    return {"day": day.isoformat(), "written": len(written), "already_written": len(wanted) - len(todo),
            "failed": failed, "database_bytes": database_bytes, "purged": purged}
