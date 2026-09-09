"""Measure M3.C1 against the stored packages, and render the feed. READ ONLY."""
import json, os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import _gather, read_awaiting_response
from genios_engine.context.situation_bso import (absence_receipt_event_ids,
                                                 gather_l1_signals_for_events)

ORG = "org_e97e86f858ad48b2bbf64b8a"
NOW = datetime.now(timezone.utc)
url = os.environ["GENIOS_TARGET_DATABASE_URL"]
if url.startswith("postgresql://"): url = "postgresql+psycopg://" + url[len("postgresql://"):]
eng = create_engine(url, connect_args={"connect_timeout": 20,
                                       "options": "-c default_transaction_read_only=on"})

with eng.connect() as c:
    live = {r[0] for r in c.execute(text(
        "select domain from l3_activation where org_id=:o and disabled_at is null"),
        {"o": ORG}).all()}
    pkgs = c.execute(text(
        "select payload->'metadata'->>'domain_ids' d, payload->'capabilities' caps "
        "from expertise_packages where org_id=:o"), {"o": ORG}).all()

print(f"\n{'='*78}\nLAYER 3 — activation gating, measured on the 381 stored packages\n{'='*78}")
print(f"  activated domains: {sorted(live)}")
before, after = {}, {}
kept_pkgs = 0
for d, caps in pkgs:
    routed = set(json.loads(d) if d else [])
    caps = caps if isinstance(caps, list) else json.loads(caps or "[]")
    survives = bool(routed & live)
    kept_pkgs += survives
    for cap in caps:
        cid = (cap or {}).get("id", "?")
        pack = cid.split(".")[0]
        before[pack] = before.get(pack, 0) + 1
        if survives and cid.split(".")[0] in live:
            after[pack] = after.get(pack, 0) + 1
print(f"  packages that survive the filter   {kept_pkgs} of {len(pkgs)}")
print(f"\n  {'PACK':<18} {'CAPABILITY SLOTS BEFORE':>24} {'AFTER':>8}")
for pack in sorted(set(before) | set(after), key=lambda p: -before.get(p, 0)):
    print(f"  {pack:<18} {before.get(pack,0):>24} {after.get(pack,0):>8}")

# ---------------------------------------------------------------- THE FEED
class _Store: engine = eng
held, counts, employers = _gather(_Store(), ORG)
findings = read_awaiting_response(held, NOW, employers)

with eng.connect() as c:
    anchors = {str(r[0]): (str(r[1]), str(r[2])) for r in c.execute(text(
        "select anchor_node_id, situation_id, situation_type from context_situations "
        "where org_id=:o and situation_type='awaiting_response'"), {"o": ORG}).all()}
    concerns = {str(r[0]): str(r[1]) for r in c.execute(text(
        "select from_node_id, to_node_id from graph_edges where org_id=:o "
        "and edge_type='concerns' and valid_to is null"), {"o": ORG}).all()}
    by_target = {}
    for a, t in concerns.items():
        by_target.setdefault(t, a)

    feed = []
    for f in findings:
        fx = {n: v for n, v, _k in f.facts}
        anchor = by_target.get(f.concerns_node)
        bp = None
        if anchor:
            ev = absence_receipt_event_ids(c, ORG, anchor, "awaiting_response")
            b = gather_l1_signals_for_events(c, ORG, ev) if ev else None
            bp = b.importance_bp if b is not None else None
        feed.append((bp if bp is not None else 0, int(fx.get("outreach.days_waiting", 0)),
                     fx.get("outreach.counterparty", "?"),
                     int(fx.get("outreach.follow_up_count", 0) or 0)))
feed.sort(key=lambda r: (-r[0], -r[1]))
print(f"\n{'='*78}\nTHE FEED — awaiting_response, ranked by the receipt it now carries\n{'='*78}")
print(f"  {'RANK':>4}  {'bp':>5}  {'DAYS':>4}  {'FU':>2}  COUNTERPARTY")
for i, (bp, days, who, fu) in enumerate(feed, 1):
    print(f"  {i:>4}  {bp if bp else '   —':>5}  {days:>4}  {fu:>2}  {who}")
