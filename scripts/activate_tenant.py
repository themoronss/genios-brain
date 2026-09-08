"""Switch ONE tenant onto Layers 1-4, in the only order that works.

    python scripts/activate_tenant.py --org <org_id> --database-url postgresql://…          # dry run
    python scripts/activate_tenant.py --org <org_id> --database-url postgresql://… --apply
    python scripts/activate_tenant.py --org <org_id> --database-url postgresql://… --status

**WHY A SCRIPT AND NOT FOUR CURL CALLS.** Four layers ship four independent switch tables — one row
for L1, two switches for L2, one row per DOMAIN for L3, one row per FEATURE for L4 — which is nine
writes for one tenant. Each table is right to be separate; what was missing is the thing that knows
their ORDER. Every one of those docstrings warns about the same failure in the same words:
activation without its supply "would LOOK successful while producing generic output". Nine manual
calls is nine chances to produce exactly that, and the symptom is not an error — it is a console
that says the tenant is live and a product that says nothing.

**THE ORDER, AND WHY IT IS THE ORDER.**

    1. L1 semantic      the model reads prose -> claims carry VERIFIED evidence spans
    2. L2 analytic      situations are admitted; without step 1 they are HELD at
                        `verified_evidence_required`, which is 424 of 429 on production today
    3. L2 patterns      pattern matching replaces anchor detection, once the analytic pass is trusted
    4. L3 <domain>      the authored corpus compiles for this tenant, one domain at a time
    5. L4 features      roster_v2 -> ranking_v2 -> bundle -> critique -> brief, in WAVE order:
                        the roster decides which units run, the formula ranks what they produced,
                        the narrative explains what was ranked. Reversed, each one has nothing to
                        work on and publishes a confident nothing.

Layer 1 first is not a preference. Its lane is the only producer of the verified spans L2's
admission gate requires, so on a tenant where it is off, every layer above it is fed held
situations — the switches go green and the pipeline stays empty.

**WHAT THIS SCRIPT DOES NOT DO.** It does not sync, and it does not backfill. Activation changes
what the NEXT sweep does; the mail already captured under the old lane stays as it was until it is
re-swept. It prints the follow-up command rather than running it, because a backfill is a spend
decision on a tenant and belongs to whoever is watching the bill.

**COST.** Step 1 puts a model call on every message of every sweep for this tenant. That is the
whole point of a per-tenant switch, and it is why `--apply` is not the default.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: The nine switches, in the order they must be flipped. `(layer, kind, name)` — `name` is the
#: value the layer's own `require_*` validator accepts, so a typo here is refused by the module
#: that owns the vocabulary rather than written as a row nothing reads.
PLAN: tuple[tuple[str, str, str], ...] = (
    ("L1", "semantic", "semantic"),
    ("L2", "switch", "analytic"),
    ("L2", "switch", "patterns"),
    ("L3", "domain", "admin"),
    ("L4", "feature", "roster_v2"),
    ("L4", "feature", "ranking_v2"),
    ("L4", "feature", "bundle"),
    ("L4", "feature", "critique"),
    ("L4", "feature", "brief"),
)

#: One line per switch, in the words an operator needs to decide whether to flip it today.
EFFECT = {
    ("L1", "semantic"): "prose is extracted by a model; claims start carrying verified spans (SPENDS)",
    ("L2", "analytic"): "situations are admitted and scored; the L3/L4 lane starts receiving supply",
    ("L2", "patterns"): "pattern matching replaces anchor-based detection",
    ("L3", "admin"): "the Admin corpus compiles for this tenant",
    ("L3", "sales"): "the Sales corpus compiles for this tenant",
    ("L3", "customer_support"): "the Customer Support corpus compiles for this tenant",
    ("L4", "roster_v2"): "the staged unit roster replaces the six hardcoded units",
    ("L4", "ranking_v2"): "the six-component utility formula ranks candidates",
    ("L4", "bundle"): "published decisions get their narrative (SPENDS)",
    ("L4", "critique"): "the critique seam scores an external agent's proposed action",
    ("L4", "brief"): "the daily book-level re-rank",
}


def _state(engine, org: str) -> dict[tuple[str, str], bool]:
    """What is live for this tenant right now, read through each layer's own reader."""
    from genios_engine.platform.activation import is_semantic_activated
    from genios_engine.platform.l2_activation import (SWITCH_ANALYTIC, activated_orgs,
                                                      is_patterns_activated)
    from genios_engine.platform.l3_activation import activated_domains
    from genios_engine.platform.l4_activation import activated_features

    domains = activated_domains(engine, org)
    features = activated_features(engine, org)
    live: dict[tuple[str, str], bool] = {
        ("L1", "semantic"): is_semantic_activated(engine, org),
        # L2 ships a reader for `patterns` and, for `analytic`, only the cross-org set the sweep
        # itself filters on. Asking the same question the sweep asks is the point: a switch this
        # script calls live and the sweep does not read is the fake success every one of these
        # modules warns about.
        ("L2", "analytic"): org in activated_orgs(engine, SWITCH_ANALYTIC),
        ("L2", "patterns"): is_patterns_activated(engine, org),
    }
    # EVERY domain and EVERY feature, not only the ones this run intends to flip. `--status` is
    # the surface an operator checks a tenant on, and a report that lists what it was asked about
    # cannot answer "is Sales on for this tenant?" — which is the question somebody asks precisely
    # when they think it should be off.
    from genios_engine.platform.l3_activation import L3_DOMAINS
    from genios_engine.platform.l4_activation import L4_FEATURES

    for domain in L3_DOMAINS:
        live[("L3", domain)] = domain in domains
    for feature in L4_FEATURES:
        live[("L4", feature)] = feature in features
    return live


def _flip(engine, org: str, layer: str, kind: str, name: str, *, by: str, notes: str) -> None:
    """One switch, through the module that owns it — never a raw insert.

    Each module's `activate` is idempotent on a live row (it keeps the ORIGINAL `enabled_at`,
    because "since when has this tenant been on" is the question a pilot diff is read against) and
    validates its own vocabulary. Going around them with SQL would lose both.
    """
    if kind == "semantic":
        from genios_engine.platform.activation import activate_semantic
        activate_semantic(engine, org, by=by, notes=notes)
    elif kind == "switch":
        from genios_engine.platform.l2_activation import activate as activate_l2
        activate_l2(engine, org, switch=name, by=by, notes=notes)
    elif kind == "domain":
        from genios_engine.platform.l3_activation import activate as activate_l3
        activate_l3(engine, org, domain=name, by=by, notes=notes)
    elif kind == "feature":
        from genios_engine.platform.l4_activation import activate as activate_l4
        activate_l4(engine, org, feature=name, by=by, notes=notes)
    else:                                                        # pragma: no cover - PLAN is closed
        raise ValueError(f"unknown switch kind {kind!r}")


def _plan_for(domains: tuple[str, ...], features: tuple[str, ...]) -> list[tuple[str, str, str]]:
    """PLAN, with the caller's domain and feature selection substituted in ORDER-PRESERVING form.

    EVERY NAME IS VALIDATED BEFORE THE FIRST ONE IS FLIPPED. The plan runs bottom-up, so a typo
    discovered when the plan reaches it would leave L1 and L2 already on and the tenant
    half-activated — an activated Layer 1 spending on a tenant whose Layer 3 was never switched on,
    because somebody typed `admn`. The layers' own validators are called here, up front: a bad name
    is a refusal with nothing written.
    """
    from genios_engine.platform.l3_activation import require_domain
    from genios_engine.platform.l4_activation import require_feature

    domains = tuple(require_domain(d) for d in domains)
    features = tuple(require_feature(f) for f in features)
    out: list[tuple[str, str, str]] = []
    for layer, kind, name in PLAN:
        if kind == "domain":
            if name == "admin":                       # the anchor row expands to the selection
                out.extend(("L3", "domain", d) for d in domains)
        elif kind == "feature":
            if name in features:
                out.append((layer, kind, name))
        else:
            out.append((layer, kind, name))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the tenant to switch on")
    ap.add_argument("--apply", action="store_true", help="write the rows (default is a dry run)")
    ap.add_argument("--status", action="store_true", help="print what is live and exit")
    ap.add_argument("--domains", default="admin",
                    help="L3 corpora, comma separated (admin,sales,customer_support)")
    ap.add_argument("--features", default="roster_v2,ranking_v2",
                    help="L4 features, comma separated. The default is the pair that makes the "
                         "formula decide; 'bundle' spends on a narrative per decision")
    ap.add_argument("--by", default=os.environ.get("USER", "operator"),
                    help="who is switching this on — stored on every row")
    ap.add_argument("--notes", default="pilot activation", help="why, stored on every row")
    args = ap.parse_args()
    url = resolve_database_url(args, purpose=f"activate layers 1-4 for {args.org}")

    from genios_engine.platform.db import get_engine

    engine = get_engine(url)
    live = _state(engine, args.org)

    print(f"\ntenant: {args.org}")
    print(f"{'switch':22} {'now':>8}   effect")
    for (layer, name), on in live.items():
        print(f"  {layer} {name:18} {'LIVE' if on else 'off':>6}   "
              f"{EFFECT.get((layer, name), '')}")
    if args.status:
        return 0

    domains = tuple(d.strip() for d in args.domains.split(",") if d.strip())
    features = tuple(f.strip() for f in args.features.split(",") if f.strip())
    todo = [(layer, kind, name) for layer, kind, name in _plan_for(domains, features)
            if not live.get((layer, name), False)]

    if not todo:
        print("\nnothing to do — every requested switch is already live")
        return 0

    print(f"\n{'WILL FLIP' if args.apply else 'WOULD FLIP'}, in this order:")
    for index, (layer, _kind, name) in enumerate(todo, 1):
        print(f"  {index}. {layer} {name:18} {EFFECT.get((layer, name), '')}")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply.")
        return 0

    for layer, kind, name in todo:
        _flip(engine, args.org, layer, kind, name, by=args.by, notes=args.notes)
        print(f"  ON  {layer} {name}")

    print("\nActivation changes what the NEXT sweep does. Nothing is backfilled. Next:")
    print("  POST /integrations/sync-all        (owner JWT, runs in the background)")
    print("\nThen check, in this order — each answers the layer below it:")
    print(f"  select count(*) from qualified_signals where org_id = '{args.org}';")
    print("  select outcome, count(*) from situation_admission_decisions "
          f"where org_id = '{args.org}' group by 1;")
    print(f"  select count(*) from reasoning_candidates where org_id = '{args.org}' "
          "and final_utility_bp is not null;")
    return 0


if __name__ == "__main__":       # pragma: no cover - operator entry point
    raise SystemExit(main())
