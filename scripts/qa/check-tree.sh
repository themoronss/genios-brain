#!/usr/bin/env bash
# Preconditions build-up refuses to start without. Exit 0 = safe to build.
set -uo pipefail
cd "$(dirname "$0")/../.."
"${GENIOS_PY:-python3}" - <<'PY'
import sys, yaml, collections
try: t = yaml.safe_load(open("tree.yaml"))
except Exception as e: print("FAIL parse:", e); sys.exit(1)
units, dep, retired = {}, {}, set()
for m in t["milestones"]:
    for c in m["categories"]:
        for l in c["layers"]:
            for lv in l["levels"]:
                for u in lv["units"]:
                    if u.get("retired"): retired.add(u["id"]); continue
                    units[u["id"]] = u; dep[u["id"]] = u.get("depends_on") or []
bad = []
for uid, u in units.items():
    if not (u.get("verify") or "").strip(): bad.append(f"{uid}: empty verify")
for uid, ds in dep.items():
    for d in ds:
        if d not in units: bad.append(f"{uid}: dangling depends_on {d}")
WHITE, GREY, BLACK = 0, 1, 2
colour = collections.defaultdict(int)
def visit(n, stack):
    if colour[n] == BLACK: return
    if colour[n] == GREY: bad.append("cycle: " + " -> ".join(stack + [n])); return
    colour[n] = GREY
    for d in dep.get(n, []): visit(d, stack + [n])
    colour[n] = BLACK
for n in units: visit(n, [])
if bad:
    print("TREE NOT BUILDABLE"); [print("  -", b) for b in bad]; sys.exit(1)
print(f"tree.yaml OK — {len(units)} live units ({len(retired)} retired), all verifies non-empty, graph acyclic")
PY
