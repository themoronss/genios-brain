"""The whole stack's activation state for one tenant, in one read.

    python scripts/stack_activation.py --org <tenant> --database-url postgresql://…
    python scripts/stack_activation.py --all --database-url postgresql://…

**WHY THIS EXISTS.** Four layers ship four activation mechanisms with four different shapes:

    Layer 1   `l1_semantic_activation`   one row per tenant, a boolean in disguise
    Layer 2   `l2_v2_activation`         one row per tenant, TWO switches as column pairs
    Layer 3   `l3_activation`            one row per (tenant, DOMAIN) — three domains
    Layer 4   `l4_activation`            one row per (tenant, FEATURE) — five features

Each has a reader, an admin route and a console view, and there was **no way to ask the one
question an operator actually has**: *is this tenant switched on, end to end, and if not where does
the chain break?* Answering it meant four API calls against four shapes and holding the wave order
in your head — and the wave order across layers was not written down in code at all until
`l4_activation.CROSS_LAYER_PRECONDITIONS`.

The cost of that gap is not hypothetical. A tenant can have `ranking_v2` live — console green,
`EFFECTS` describing a six-component utility model — while Layer 1's semantic lane has never been
activated, so `qualified_signals` carries no scores, Layer 2 composes no importance, and the
formula silently reweighs its remaining five components on every decision. Every individual
console was telling the truth. Nothing put them side by side.

**THIS IS A READ. IT ACTIVATES NOTHING.** No writes, no switches, no side effects — it opens a
read-only connection and prints. Turning something on is `POST /v1/admin/{l1,l2,l3,l4}-activation`,
behind `require_admin`, audited there. A report that could also flip a switch is a report nobody
can safely run against production while they are trying to work out what is wrong.

**THE CHAIN, and what "broken" means at each link.** Reported in dependency order, because that is
the order the answer is useful in — the FIRST unmet link is the one to fix, and everything below it
is a consequence rather than a separate problem:

    L1 semantic ─▶ L2 importance ─▶ L3 domain ─▶ L4 roster_v2 ─▶ ranking_v2 ─▶ bundle/critique/brief

`--all` sweeps every tenant that has ANY activation row anywhere in the stack, so a tenant switched
on at one layer and forgotten at every other one appears rather than having to be guessed at.
"""

from __future__ import annotations

import argparse
import json
import sys

from _db import add_database_argument, resolve_database_url
from _gate import read_only_connection

#: The chain, in dependency order, as (label, what makes it live). Kept here as DATA rather than as
#: a sequence of `if` blocks so the printed order, the "first broken link" search and the JSON keys
#: cannot disagree about what the chain is.
CHAIN = ("l1_semantic", "l2_analytic", "l2_patterns", "l3_domains",
         "l4_roster_v2", "l4_ranking_v2", "l4_bundle", "l4_critique", "l4_brief")

#: The links whose absence actually BREAKS what comes after, as opposed to the ones that are
#: independent switches at the same level. `l2_analytic` is deliberately NOT here: it is a
#: declaration, not a gate (see `platform/l2_activation.EFFECTS` — the analytic stratum already
#: runs for every tenant and the switch only records the pilot window that `l2_shadow_diff` reads),
#: so a tenant with it off is not broken and saying so would send an operator to fix nothing.
BLOCKING = ("l1_semantic", "l3_domains", "l4_roster_v2", "l4_ranking_v2")

#: What to DO about each broken link — the half a status report usually leaves out. An operator
#: reading "l1_semantic: off" needs the next command, not a lookup in four modules.
REMEDY = {
    "l1_semantic": "POST /v1/admin/semantic-activation/{org}  (table l1_semantic_activation)",
    "l2_analytic": "POST /v1/admin/l2-activation/{org} switch=analytic  — declaration only",
    "l2_patterns": "POST /v1/admin/l2-activation/{org} switch=patterns",
    "l3_domains": "POST /v1/admin/l3-activation/{org} domain=admin|customer_support|sales",
    "l4_roster_v2": "POST /v1/admin/l4-activation/{org} feature=roster_v2",
    "l4_ranking_v2": "POST /v1/admin/l4-activation/{org} feature=ranking_v2",
    "l4_bundle": "POST /v1/admin/l4-activation/{org} feature=bundle",
    "l4_critique": "POST /v1/admin/l4-activation/{org} feature=critique",
    "l4_brief": "POST /v1/admin/l4-activation/{org} feature=brief",
}


def read_stack(engine, org_id: str) -> dict:
    """Every layer's switch state for one tenant, through each layer's OWN reader.

    Deliberately not one hand-written join across four tables. Each `platform/*_activation` module
    owns what "live" means for its own table — L4 filters stamped-off rows, L3 filters unknown
    domains, L1 has its own erasure semantics — and a join here would be a fifth definition that
    drifts from all four. The cost is a few small queries; the benefit is that this script cannot
    disagree with the engine about who is switched on.

    Takes an ENGINE, not a connection: every `platform/*_activation` reader opens its own
    `engine.connect()`, so handing one a live `Connection` fails at the first call. They are all
    pure SELECTs, which is why this is safe to point at a production replica — but the read-only
    guard still belongs on the one query this module writes itself (`_tenants`).
    """
    from genios_engine.platform.activation import is_semantic_activated
    from genios_engine.platform.l2_activation import get_l2_activation
    from genios_engine.platform.l3_activation import activated_domains
    from genios_engine.platform.l4_activation import (CROSS_LAYER_EFFECTS, L4_FEATURES,
                                                      activated_features,
                                                      missing_cross_layer_preconditions,
                                                      missing_preconditions)
    l2 = get_l2_activation(engine, org_id)
    domains = sorted(activated_domains(engine, org_id))
    features = activated_features(engine, org_id)
    state = {
        "l1_semantic": is_semantic_activated(engine, org_id),
        "l2_analytic": bool(l2 and l2.analytic_live),
        "l2_patterns": bool(l2 and l2.patterns_live),
        "l3_domains": bool(domains),
        **{f"l4_{name}": (name in features) for name in L4_FEATURES},
    }
    # The first BLOCKING link that is off. Everything after it is a consequence, and reporting five
    # "problems" when there is one cause is how a status report gets ignored.
    broken = next((name for name in CHAIN if name in BLOCKING and not state[name]), None)
    unmet = {name: list(missing_cross_layer_preconditions(engine, org_id, name.removeprefix("l4_")))
             for name in state if name.startswith("l4_") and state[name]}
    return {
        "org_id": org_id,
        "state": state,
        "l3_live_domains": domains,
        "l4_live_features": sorted(features),
        "fully_activated": all(state[name] for name in BLOCKING),
        "first_broken_link": broken,
        "remedy": REMEDY.get(broken) if broken else None,
        "l4_missing_preconditions": {
            name: list(missing_preconditions(engine, org_id, name.removeprefix("l4_")))
            for name in state if name.startswith("l4_") and state[name]},
        "l4_missing_cross_layer_preconditions": {k: v for k, v in unmet.items() if v},
        "cross_layer_effects": {item: CROSS_LAYER_EFFECTS[item]
                                for items in unmet.values() for item in items},
    }


def _tenants(conn) -> list[str]:
    """Every tenant with an activation row ANYWHERE in the stack.

    A union rather than a scan of `orgs`: the question is "who has been switched on at some layer",
    and listing every tenant that was never in any pilot buries the handful that were. A tenant
    switched on at exactly one layer and forgotten at the rest is the case this most needs to
    surface, and a union is the only read that finds it.
    """
    from sqlalchemy import text
    statement = text(
        "select org_id from l1_semantic_activation union "
        "select org_id from l2_v2_activation union "
        "select org_id from l3_activation union "
        "select org_id from l4_activation order by 1")
    return [row[0] for row in conn.execute(statement)]


def render(report: dict) -> str:
    lines = [f"── {report['org_id']}",
             f"   {'FULLY ACTIVATED' if report['fully_activated'] else 'INCOMPLETE'}"]
    for name in CHAIN:
        live = report["state"][name]
        mark = "on " if live else "OFF"
        note = ""
        if name == "l3_domains" and live:
            note = f"  [{', '.join(report['l3_live_domains'])}]"
        if name == "l2_analytic":
            note = "  (declaration only — not a gate)"
        if not live and name not in BLOCKING and name != "l2_analytic":
            note = "  (optional at this stage)"
        lines.append(f"   {mark}  {name}{note}")
    if report["first_broken_link"]:
        lines.append(f"   ↳ FIRST BROKEN LINK: {report['first_broken_link']}")
        lines.append(f"     remedy: {report['remedy']}")
    for feature, items in report["l4_missing_cross_layer_preconditions"].items():
        lines.append(f"   ! {feature} is LIVE but its preconditions are not: {', '.join(items)}")
    for item, effect in report["cross_layer_effects"].items():
        lines.append(f"     {item}: {effect}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--org", help="the tenant to report on")
    ap.add_argument("--all", action="store_true",
                    help="every tenant with an activation row at any layer")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    add_database_argument(ap)
    args = ap.parse_args(argv)
    if not args.org and not args.all:
        ap.error("name a tenant with --org, or sweep them all with --all")

    url = resolve_database_url(args, purpose="read stack activation state")
    from sqlalchemy import create_engine
    engine = create_engine(url)
    if args.org:
        orgs = [args.org]
    else:
        with read_only_connection(engine) as conn:
            orgs = _tenants(conn)
    reports = [read_stack(engine, org) for org in orgs]

    if args.json:
        print(json.dumps(reports, indent=2, default=str))
    else:
        for report in reports:
            print(render(report))
        incomplete = [r["org_id"] for r in reports if not r["fully_activated"]]
        print(f"\n{len(reports) - len(incomplete)} of {len(reports)} tenants fully activated")
        if incomplete:
            print(f"incomplete: {', '.join(incomplete)}")
    # Exit 0 always: this is a REPORT, not a gate. A status read that fails CI because a tenant is
    # mid-rollout is a status read people stop running.
    return 0


if __name__ == "__main__":
    sys.exit(main())
