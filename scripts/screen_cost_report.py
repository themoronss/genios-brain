#!/usr/bin/env python3
"""What screen intelligence COSTS, per org, per person, per laptop.

WHY THIS EXISTS. The owner asked a question the ledger could not answer: for one org with two
people reading screens, "ye Harsh ke MacBook se aaya ya Rohit ke MacBook se?". Measured on the
design-partner org 12 Oct 2026, three devices are registered and ALL THREE sit on `seat_owner`,
because both people sign the desktop app in with the same account. So `seat_id` — which has been
on `llm_costs` since 0175 — names a seat that is really two laptops, and a lane whose entire job
is to read ONE person's screen had no way to say whose.

Migration 0212 adds `llm_costs.device_id` and `moment_routes` fills it from the device token the
request already arrives on. This reads it back.

ROWS WRITTEN BEFORE 0212 HAVE device_id NULL. They are reported as "(before 0212)" rather than
folded into one laptop or quietly dropped — a backfill would have to invent the answer, and the
honest shape of this table is that attribution starts the day it was deployed.

Read-only. Takes the database URL the same deliberate way every other script here does.

    python scripts/screen_cost_report.py --database-url "$GENIOS_DATABASE_URL" [--days 14]
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import create_engine, text

#: USD per MILLION tokens, from the published Anthropic price list. Cache reads are 0.1x input and
#: cache writes 1.25x, and `input_tokens` on this table is ALREADY the cost-equivalent count — so
#: the cache columns are reported, never re-priced (see `GraphStore.record_cost`).
PRICES = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-5": (15.0, 75.0),
}
#: Only for printing a second, more familiar number next to the dollars.
USD_TO_INR = 88.0

#: The lanes this report is about. Everything screen intelligence spends money on, and nothing
#: else — an org's mail ingestion is a different question with a different answer.
SCREEN = "(purpose like 'screen%' or purpose like 'moment.screen%' or purpose = 'moment.screen_insight')"


def price(model: str, tin: int, tout: int) -> float:
    """USD for one row's tokens. An unknown model prices at Haiku rather than at zero: a new
    model silently costing nothing is the failure mode that hides a bill."""
    pin, pout = PRICES.get(model or "", PRICES["claude-haiku-4-5"])
    return (tin or 0) / 1e6 * pin + (tout or 0) / 1e6 * pout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--org", default=None, help="one org id; default every org with screen spend")
    a = ap.parse_args()

    url = a.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    eng = create_engine(url)

    where_org = " and org_id = :org" if a.org else ""
    params = {"d": f"{a.days} days", **({"org": a.org} if a.org else {})}

    with eng.connect() as c:
        has_device = c.execute(text(
            "select 1 from information_schema.columns "
            "where table_name = 'llm_costs' and column_name = 'device_id'")).first() is not None

        dev_col = "device_id" if has_device else "cast(null as text) as device_id"
        rows = list(c.execute(text(
            f"select org_id, seat_id, {dev_col}, model, purpose, "
            "count(*) n, sum(input_tokens) tin, sum(output_tokens) tout, "
            "sum(coalesce(cache_read_tokens,0)) cr, sum(coalesce(cache_write_tokens,0)) cw "
            f"from llm_costs where created_at > now() - cast(:d as interval) and {SCREEN}{where_org} "
            "group by 1,2,3,4,5"), params))

        # device_id -> a name a person recognises. `devices` carries the label the app registered.
        names = {r.device_id: (r.device_name or r.platform or "?")
                 for r in c.execute(text("select device_id, device_name, platform from devices"))}
        # `device_id` IS globally unique (a random dev_… token), so a flat map is correct here —
        # unlike `seat_id` above, which is only unique inside its org.
        # Keyed on (org, seat), not on seat alone: `seat_owner` is a per-org id and several orgs
        # have one, so a seat-only key printed a DIFFERENT org's email next to this org's spend.
        seats = {(r.org_id, r.seat_id): r.email
                 for r in c.execute(text("select org_id, seat_id, email from org_seats"))}

    if not rows:
        print(f"No screen spend in the last {a.days} days.")
        return 0
    if not has_device:
        print("!! llm_costs.device_id does not exist here — migration 0212 is not applied yet.")
        print("   Per-laptop numbers will all read '(before 0212)'.\n")

    by_org: dict[str, list] = defaultdict(list)
    for r in rows:
        by_org[r.org_id].append(r)

    for org, rs in sorted(by_org.items(), key=lambda kv: -sum(price(x.model, x.tin, x.tout) for x in kv[1])):
        total = sum(price(r.model, r.tin, r.tout) for r in rs)
        calls = sum(r.n for r in rs)
        print(f"\n{'=' * 78}\nORG {org}   ·   last {a.days} days")
        print(f"  ${total:.2f}  (₹{total * USD_TO_INR:,.0f})   {calls:,} calls   "
              f"→ ₹{total * USD_TO_INR / max(a.days, 1):,.1f}/day")

        print(f"\n  {'PER PERSON (seat)':<44} {'calls':>7} {'USD':>9} {'INR':>9}")
        per_seat: dict[str, list] = defaultdict(list)
        for r in rs:
            per_seat[r.seat_id or "(no seat — background)"].append(r)
        for seat, srs in sorted(per_seat.items(), key=lambda kv: -sum(price(x.model, x.tin, x.tout) for x in kv[1])):
            u = sum(price(x.model, x.tin, x.tout) for x in srs)
            who = seats.get((org, seat), "")
            label = f"{seat} {('· ' + who) if who else ''}".strip()
            print(f"  {label:<44} {sum(x.n for x in srs):>7,} {u:>9.3f} {u * USD_TO_INR:>9,.0f}")

        print(f"\n  {'PER LAPTOP (device)':<44} {'calls':>7} {'USD':>9} {'INR':>9}")
        per_dev: dict[str, list] = defaultdict(list)
        for r in rs:
            per_dev[r.device_id or "(before 0212 — not recorded)"].append(r)
        for dev, drs in sorted(per_dev.items(), key=lambda kv: -sum(price(x.model, x.tin, x.tout) for x in kv[1])):
            u = sum(price(x.model, x.tin, x.tout) for x in drs)
            nice = names.get(dev)
            label = f"{dev[:24]} {('· ' + nice) if nice else ''}".strip()
            print(f"  {label:<44} {sum(x.n for x in drs):>7,} {u:>9.3f} {u * USD_TO_INR:>9,.0f}")

        print(f"\n  {'PER LANE (purpose)':<44} {'calls':>7} {'USD':>9} {'INR':>9}")
        per_lane: dict[str, list] = defaultdict(list)
        for r in rs:
            per_lane[r.purpose].append(r)
        for lane, lrs in sorted(per_lane.items(), key=lambda kv: -sum(price(x.model, x.tin, x.tout) for x in kv[1])):
            u = sum(price(x.model, x.tin, x.tout) for x in lrs)
            print(f"  {lane:<44} {sum(x.n for x in lrs):>7,} {u:>9.3f} {u * USD_TO_INR:>9,.0f}")

        cr = sum(r.cr or 0 for r in rs)
        cw = sum(r.cw or 0 for r in rs)
        if cr or cw:
            print(f"\n  prompt cache: {cr:,} read · {cw:,} written "
                  "(already inside the input count above, never re-priced)")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
