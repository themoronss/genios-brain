"""Promote a tenant (or every existing tenant) to the CURRENT built-in pack versions.

Why this exists: `ensure_default` only applies a pack to an org that has NONE — an org already on
an older pinned version keeps it until *explicitly* promoted (packs/wiring.py: "zero-deploy
lifecycle"). That is deliberate (a background L3 run must never silently clobber an admin override),
but it means orgs onboarded before a pack ships new rules stay on the OLD rule set after deploy.

A brand-new trial org is unaffected — it gets DEFAULT_PACK_VERSION on first touch. This script is the
explicit-admin promotion path for the PRE-EXISTING orgs (test, founder, Inkbox…) so their deep rules
light up too.

Safety: promotion only bumps tenant_packs.version. Tenant lvl2/lvl3 overrides + pins live in separate
columns and are untouched, so an admin's scoring overrides survive the version bump. Dry by default.

Usage:  python -m scripts.promote_packs --org org_xxx [--apply]
        python -m scripts.promote_packs --all-existing [--apply]
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from genios_engine.packs.wiring import DEFAULT_PACKS, make_registry


def _rule_count(reg, org: str, pack: str) -> int:
    eff, _ = reg.effective(org, pack)
    return len(eff["rules"]) if eff else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--org", help="promote a single org")
    g.add_argument("--all-existing", action="store_true",
                   help="promote every org that already has any tenant_packs row")
    ap.add_argument("--apply", action="store_true", help="actually write (else dry-run)")
    args = ap.parse_args()

    reg = make_registry()
    if args.org:
        orgs = [args.org]
    else:
        with reg._engine.connect() as c:
            orgs = [r[0] for r in c.execute(text("select distinct org_id from tenant_packs"))]
    print(f"targets: {len(orgs)} org(s) · packs: {[f'{p}=={v}' for p, v in DEFAULT_PACKS]}")

    for org in orgs:
        for pack_id, version in DEFAULT_PACKS:
            before = _rule_count(reg, org, pack_id)
            if args.apply:
                reg.apply_to_tenant(org, pack_id, version, state="active")
                after = _rule_count(reg, org, pack_id)
                print(f"  {org} · {pack_id}: {before} → {after} rules (v{version})")
            else:
                print(f"  {org} · {pack_id}: {before} rules now → would set v{version}")
    if not args.apply:
        print("\nDRY RUN — re-run with --apply to promote.")


if __name__ == "__main__":
    main()
