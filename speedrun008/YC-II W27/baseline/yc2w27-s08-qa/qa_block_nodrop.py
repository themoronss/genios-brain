"""QA for one named block of tree.yaml — the harness's `tree` and `units` families, applied to a
block `_tree.py` cannot see (it walks the root `milestones` only). Exit codes only.

    python qa_block.py <block> <out.json>
"""
import json, os, subprocess, sys, time
import yaml

REPO = "/Users/rohitswerashi/Downloads/Artifacts/Product/genios-brain (yc)/genios-brain"
block, out_path = sys.argv[1], sys.argv[2]
tree = yaml.safe_load(open(os.path.join(REPO, "tree.yaml")))
units = []
for m in tree[block]["milestones"]:
    for c in m["categories"]:
        for l in c["layers"]:
            for v in l["levels"]:
                for u in v["units"]:
                    units.append(u)
lines, results = [], []

def emit(state, family, uid, detail, secs=0.0):
    line = f"{state:<5} {family:<6} {uid:<34} {detail}  {secs:.1f}s"
    print(line, flush=True); lines.append(line)
    results.append({"state": state, "family": family, "id": uid, "detail": detail, "secs": secs})

# ── family 1 · tree ───────────────────────────────────────────────────────────────────────────
ids = [u["id"] for u in units]
dupes = sorted({i for i in ids if ids.count(i) > 1})
emit("PASS" if not dupes else "FAIL", "tree", block, f"ids unique ({len(ids)})" if not dupes else f"duplicate ids {dupes}")
known = set(ids)
missing = sorted({d for u in units for d in (u.get("depends_on") or []) if d not in known})
emit("PASS" if not missing else "FAIL", "tree", block, "every depends_on resolves" if not missing else f"unresolved {missing}")
noverify = sorted(u["id"] for u in units if not u.get("verify") and "retired" not in u)
emit("PASS" if not noverify else "FAIL", "tree", block, "every live unit has a verify" if not noverify else f"no verify {noverify}")
graph = {u["id"]: list(u.get("depends_on") or []) for u in units}
state = {}
def cyc(n):
    if state.get(n) == 1: return True
    if state.get(n) == 2: return False
    state[n] = 1
    if any(cyc(d) for d in graph.get(n, []) if d in graph): return True
    state[n] = 2; return False
cycle = any(cyc(n) for n in graph)
emit("PASS" if not cycle else "FAIL", "tree", block, "graph acyclic" if not cycle else "cycle found")

# ── family 2 · units — every live unit's own verify, a fresh database before each that uses one ──
RUN = time.strftime("%H%M%S", time.gmtime())
_seq = [0]
def fresh_db():
    """A NEW empty database for this unit — created, never dropped (auto mode refuses drops; a
    database nobody else ever used is as empty as a recreated one). Returns its name."""
    _seq[0] += 1
    name = f"genios_qa_{RUN}_{_seq[0]:02d}"
    subprocess.run(["docker", "exec", "genios-yc2w27-pg", "psql", "-U", "postgres", "-q", "-c",
                    f"create database {name}"], check=True, capture_output=True)
    return name

env = {k: v for k, v in os.environ.items() if not k.startswith("GENIOS_")}
for u in units:
    if "retired" in u:
        emit("RETIRED", "unit", u["id"], "retired: " + " ".join(str(u["retired"]).split())[:80]); continue
    verify = u["verify"]
    if "GENIOS_TEST_DATABASE_URL" in verify:
        # The verify, verbatim, pointed at a database created for it — the same command on an
        # empty database, as the tree's genios_test was recreated empty before each unit.
        assert "/genios_test " in verify, verify
        verify = verify.replace("/genios_test ", f"/{fresh_db()} ")
    t0 = time.time()
    p = subprocess.run(["bash", "-c", verify], cwd=REPO, env=env, capture_output=True, text=True)
    secs = time.time() - t0
    tail = (p.stdout.strip().splitlines() or [""])[-1][:110]
    emit("PASS" if p.returncode == 0 else "FAIL", "unit", u["id"], f"exit={p.returncode} | {tail}", secs)

summary = {s: sum(r["state"] == s for r in results) for s in ("PASS", "FAIL", "SKIP", "RETIRED")}
json.dump({"block": block, "summary": summary, "results": results}, open(out_path, "w"), indent=1)
print(f"\n{summary['PASS']} pass / {summary['FAIL']} fail / {summary['SKIP']} skip  ({summary['RETIRED']} retired, not run)")
sys.exit(1 if summary["FAIL"] else (2 if summary["SKIP"] else 0))
