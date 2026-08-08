#!/usr/bin/env python3
"""Generate registry/situation-capability-map.yaml — the reverse index Layer 3's compiler reads
to turn a Layer 2 situation type into a capability set and an object load-set.

A situation now lives inside its owning capability and may serve others through `also_serves`,
so the map is a genuine many-to-many resolved here once rather than at every compile.

Also reports the coverage gaps nothing else will tell you:

  UNROUTED L2 TYPES     Layer 2 emits the type and no situation binds it. No capability will
                        ever compile for it, and nothing errors or logs — the compile just
                        produces nothing.
  ORPHAN CAPABILITIES   Authored but unreachable: no situation routes into them.
  UNREACHABLE OBJECTS   Authored but no objects.yaml loads them.

    python "Domain Expertise/_tools/index.py"
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import domains, load_set, load_vocabulary, walk  # noqa: E402

HEADER = """# GENERATED FILE — do not hand-edit.
#   regenerate:  python "Domain Expertise/_tools/index.py"
#
# The reverse index: Layer 2 emits a situation type, this map says which capabilities apply and
# which objects to load. Without it the compiler would scan every capability in the domain; with
# it the lookup is O(1) into the relevant slice — the single biggest performance win in Layer 3
# once a domain grows past a handful of capabilities.
#
# `load` is the union of the situation's own load-set and every serving capability's required
# objects, minus anything either marks never_load.
"""


def ylist(items, indent):
    if not items:
        return " []"
    pad = " " * indent
    return "\n" + "\n".join(f"{pad}- {i}" for i in sorted(items))


def main() -> int:
    vocab = load_vocabulary()
    all_l2 = list(vocab["substrate"]["l2_situation_types"])

    # Pre-pass. "Unrouted" means no situation ANYWHERE binds the type — it is a property of
    # the library, not of one domain. Computing it per domain made sense with one domain and
    # becomes actively misleading with two: Customer Support does not route `budget_freeze`
    # and never should, and listing that as a coverage gap trains people to ignore the list.
    bound_globally: set[str] = set()
    for droot in domains():
        for k, _, d in walk(droot):
            if k == "situation":
                bound_globally.update((d.get("matches") or {}).get("l2_situation_types") or [])

    unrouted = sorted(t for t in all_l2 if t not in bound_globally)

    for droot in domains():
        files = list(walk(droot))
        situations = {d["identity"]["id"]: d for k, _, d in files
                      if k == "situation" and d.get("identity")}
        caps = {d["identity"]["id"]: d for k, _, d in files
                if k == "capability" and d.get("identity")}
        capobjs = {d["capability"]: d for k, _, d in files
                   if k == "capability_objects" and d.get("capability")}
        objects = {d["identity"]["id"]: d for k, _, d in files
                   if k == "object" and d.get("identity")}

        by_type: dict[str, list[str]] = defaultdict(list)
        for sid, s in situations.items():
            for t in (s.get("matches") or {}).get("l2_situation_types") or []:
                by_type[t].append(sid)

        routed_caps: set[str] = set()
        loaded_objects: set[str] = set()
        lines = [HEADER, f"domain: {droot.name}", "", "map:"]

        for t in all_l2:
            sids = sorted(by_type.get(t) or [])
            if not sids:
                continue
            cap_ids, load, opt, never = set(), set(), set(), set()
            for sid in sids:
                s = situations[sid]
                owner = s["identity"].get("owner_capability")
                serving = ([owner] if owner else []) + list(s.get("also_serves") or [])
                cap_ids.update(serving)
                o = s.get("objects") or {}
                load.update(o.get("load") or [])
                opt.update(o.get("optional") or [])
                never.update(o.get("never_load") or [])
                for cid in serving:
                    co = capobjs.get(cid)
                    if not co:
                        continue
                    ls = load_set(co)
                    load.update(ls["required"])
                    opt.update(ls["optional"])
                    never.update(co.get("never_load") or [])

            routed_caps.update(cap_ids)
            load -= never
            opt -= never | load
            loaded_objects |= load | opt

            lines.append(f"  {t}:")
            lines.append(f"    situations:{ylist(sids, 6)}")
            lines.append(f"    capabilities:{ylist(cap_ids, 6)}")
            lines.append("    objects:")
            lines.append(f"      load:{ylist(load, 8)}")
            lines.append(f"      optional:{ylist(opt, 8)}")
            if never:
                lines.append(f"      never_load:{ylist(never, 8)}")
            lines.append("")

        # every object any capability loads, regardless of routing
        all_loaded = set()
        for co in capobjs.values():
            ls = load_set(co)
            all_loaded |= set(ls["required"]) | set(ls["optional"])

        # Types this domain binds, vs types nothing anywhere binds. Two different facts.
        routed_here = sorted(t for t in all_l2 if by_type.get(t))
        orphans = sorted(set(caps) - routed_caps)
        stubs = sorted(cid for cid, c in caps.items() if c["identity"].get("stub"))
        unreachable = sorted(set(objects) - all_loaded)
        core_n = sum(1 for o in objects.values() if o["identity"].get("scope") == "core")

        # Situations whose real trigger no pack emits. They route nothing today and are the
        # single most concrete statement of what this domain needs Layers 1 and 2 to build.
        pending: dict[str, list[str]] = defaultdict(list)
        for sid, s in situations.items():
            for p in (s.get("matches") or {}).get("pending_l2_situation_types") or []:
                if p.get("type"):
                    pending[p["type"]].append(sid)

        lines += [
            "# ── Blocked on Layers 1 and 2 ─────────────────────────────────────────────",
            "# These situations are authored and route NOTHING, because the type that would",
            "# trigger them is not in any shipped pack's signal_vocab. Not a defect in the",
            "# authoring — it is the requirement list, stated where the compiler can count it.",
            "pending_l2_types:",
        ]
        if not pending:
            lines[-1] = "pending_l2_types: {}"
        for t in sorted(pending):
            lines.append(f"  {t}:")
            lines.append(f"    situations:{ylist(sorted(pending[t]), 6)}")
        lines += [
            "",
            "# ── Coverage ──────────────────────────────────────────────────────────────",
            "# Types this domain routes.",
            f"routed_l2_types:{ylist(routed_here, 2)}", "",
            "# Layer 2 emits these and NO situation in ANY domain binds them. Each is a signal",
            "# that compiles to nothing, silently. Global, not this domain's fault.",
            f"unrouted_l2_types:{ylist(unrouted, 2)}", "",
            "# Authored but unreachable — no situation routes into them.",
            f"orphan_capabilities:{ylist(orphans, 2)}", "",
            "# Authored but no capability's objects.yaml loads them.",
            f"unreachable_objects:{ylist(unreachable, 2)}", "",
            "stats:",
            f"  l2_types_total: {len(all_l2)}",
            f"  l2_types_routed_here: {len(routed_here)}",
            f"  l2_types_unrouted_globally: {len(unrouted)}",
            f"  l2_types_pending: {len(pending)}",
            f"  situations: {len(situations)}",
            f"  capabilities: {len(caps)}",
            f"  capabilities_stub: {len(stubs)}",
            f"  capabilities_complete: {len(caps) - len(stubs)}",
            f"  capabilities_routed: {len(routed_caps)}",
            f"  objects_total: {len(objects)}",
            f"  objects_core: {core_n}",
            f"  objects_scoped: {len(objects) - core_n}",
            "",
        ]

        out = droot / "registry" / "situation-capability-map.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines))

        pct = 100 * len(routed_here) // max(1, len(all_l2))
        print(f"{droot.name}")
        print(f"  wrote {out.relative_to(droot.parent)}")
        print(f"  L2 routed here {len(routed_here)}/{len(all_l2)} ({pct}%)")
        print(f"  capabilities   {len(caps) - len(stubs)} complete, {len(stubs)} stub, "
              f"{len(routed_caps)} routed")
        print(f"  objects        {core_n} core, {len(objects) - core_n} scoped, "
              f"{len(unreachable)} unreachable")
        print(f"  situations     {len(situations)}, {len(pending)} blocked on a missing L2 type")
        if pending:
            print(f"  PENDING L2     {', '.join(sorted(pending))}")
        print()

    if unrouted:
        print(f"UNROUTED GLOBALLY ({len(unrouted)}) — emitted by Layer 2, bound by no domain:")
        print(f"  {', '.join(unrouted)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
