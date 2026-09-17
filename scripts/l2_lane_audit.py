"""Does every lane in Layer 2 actually produce — and where it does not, is the silence explained?

READ-ONLY, and it runs the layer's own code: `_gather` fills the same `held` dict the sweep fills,
and every registered reading is dispatched through the same wrapper the sweep dispatches. The
question a lane cannot answer for itself is the one this asks: a reading that returns [] because
the tenant genuinely has nothing looks identical, from the card side, to one that returns []
because a name it reads is bound nowhere.

THREE VERDICTS, and only the third is a defect:
  PRODUCING   — the lane emitted findings this run.
  DORMANT     — it emitted none AND its silence is declared somewhere a reader can find:
                `patterns.routing.UNROUTED_PATTERN_TYPES`, or a MOVES WHEN in its own module.
  UNEXPLAINED — it emitted none and nothing says why. This is the class that has cost five lanes
                in this codebase, every one of them found by accident.
"""
import os, sys, io, json, contextlib, traceback
from datetime import datetime, timezone
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text
from genios_engine.platform.db import get_engine
from genios_engine.context.graph_store import GraphStore
import genios_engine.context.outreach_situations as OS
from genios_engine.context.lane_health import DORMANT_LANES, revived, undeclared
from genios_engine.context.domain_spec import domains_declaring, spec_for

ORG = os.environ.get("GENIOS_AUDIT_ORG") or sys.argv[1]
engine = get_engine(os.environ["GENIOS_DATABASE_URL"])
store = GraphStore(engine=engine)
now = datetime.now(timezone.utc)

# ── fill `held` exactly the way the sweep does, capturing the gather's own warnings ───────────
warnings = io.StringIO()
import logging
h = logging.StreamHandler(warnings); h.setLevel(logging.WARNING)
logging.getLogger("genios.l2").addHandler(h)

held, counts, employers = OS._gather(store, ORG, now=now)

gather_warnings = [l for l in warnings.getvalue().splitlines() if l.strip()]

rows = {}
for anchor, reader in OS.READINGS:
    try:
        findings = reader(held, now, employers)
        rows[anchor] = {"findings": len(findings), "error": None}
    except Exception as exc:
        rows[anchor] = {"findings": 0, "error": f"{type(exc).__name__}: {exc}"}

# ── what the graph currently holds, per lane ─────────────────────────────────────────────────
with engine.connect() as c:
    live = dict(c.execute(text(
        "select situation_type, count(*) from context_situations "
        "where org_id=:o and status='active' group by 1"), {"o": ORG}).fetchall())

def stype(anchor):
    for d in domains_declaring(anchor):
        t = spec_for(d).situation_types.get(anchor)
        if t:
            return t
    return None

print("=" * 96)
print(f"{'lane':<22}{'situation type':<26}{'findings':>9}{'live cards':>12}   verdict")
print("=" * 96)
unexplained = []
for anchor, r in rows.items():
    t = stype(anchor) or "?"
    n, cards = r["findings"], live.get(t, 0)
    if r["error"]:
        verdict = f"ERROR — {r['error'][:60]}"
        unexplained.append((anchor, verdict))
    elif n or cards:
        verdict = "PRODUCING"
    else:
        why = DORMANT_LANES.get(anchor)
        verdict = f"DORMANT — {why.split('.')[0][:58]}" if why else "UNEXPLAINED ZERO"
        if not why:
            unexplained.append((anchor, "produced nothing and nothing says why"))
    print(f"{anchor:<22}{t:<26}{n:>9}{cards:>12}   {verdict}")

print()
print("GATHER WARNINGS THIS RUN (a swallowed gather is how four of the five were hidden):")
for w in gather_warnings or ["   none"]:
    print("  ", w[:150])

print()
print("=" * 96)
produced = {a: r["findings"] for a, r in rows.items()}
stale = revived(produced)
if unexplained:
    print(f"UNEXPLAINED LANES: {len(unexplained)}")
    for a, why in unexplained:
        print(f"   {a:<24} {why}")
else:
    print("NO UNEXPLAINED LANES — every reading either produced, or its silence is declared")
    print("with a reason and a MOVES WHEN in context/lane_health.py.")
if stale:
    print()
    print(f"DECLARED DORMANT BUT PRODUCING (the entry is now a lie): {list(stale)}")
