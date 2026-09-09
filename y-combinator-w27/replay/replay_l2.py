"""Run the SHIPPED Layer 2 readings against the live graph. READ ONLY, server-enforced."""
import os
from datetime import datetime, timezone
from sqlalchemy import bindparam, create_engine, text

from genios_engine.context.outreach_situations import _gather, read_awaiting_response
from genios_engine.context.waiting import _ASK_KINDS, _ASKS
from genios_engine.context.situation_bso import (absence_receipt_event_ids,
                                                 gather_l1_signals_for_events)

ORG = "org_e97e86f858ad48b2bbf64b8a"
NOW = datetime.now(timezone.utc)
url = os.environ["GENIOS_TARGET_DATABASE_URL"]
if url.startswith("postgresql://"): url = "postgresql+psycopg://" + url[len("postgresql://"):]
eng = create_engine(url, connect_args={"connect_timeout": 20,
                                       "options": "-c default_transaction_read_only=on"})

class _Store:
    engine = eng

held, counts, employers = _gather(_Store(), ORG)
findings = read_awaiting_response(held, NOW, employers)

with eng.connect() as c:
    asked = {r[0] for r in c.execute(
        text(_ASKS).bindparams(bindparam("kinds", expanding=True)),
        {"o": ORG, "kinds": sorted(_ASK_KINDS)}).all()}
    # anchor node id per outreach finding -> the node it concerns
    node_of = {f.concerns_node: f for f in findings}

print(f"\n{'='*78}\nLAYER 2 — the shipped readings, run on the live graph\n{'='*78}")
print(f"  rows the gather held            {len(held):>4}")
print(f"  awaiting_response findings      {len(findings):>4}   (was 41 on the stored run)")
print(f"  nodes we actually ASKED         {len(asked):>4}   (was 1 by the old rule)")

def facts_of(f):
    return {n: v for n, v, _k in f.facts}

rows = []
for f in findings:
    fx = facts_of(f)
    rows.append((fx.get("outreach.days_waiting", 0), fx.get("outreach.counterparty", "?"),
                 fx.get("outreach.follow_up_count", 0), f.concerns_node in asked))
rows.sort(key=lambda r: -int(r[0]))

print(f"\n  {'DAYS':>4}  {'FU':>2}  {'ASKED':<5}  COUNTERPARTY")
print(f"  {'-'*4}  {'-'*2}  {'-'*5}  {'-'*46}")
for days, who, fu, was_asked in rows:
    print(f"  {days:>4}  {fu:>2}  {'YES' if was_asked else '·':<5}  {who}")

# ---- the absence receipt, on the real anchors ------------------------------------------------
print(f"\n  --- absence receipts, resolved by the shipped resolver ---")
with eng.connect() as c:
    sits = c.execute(text(
        "select situation_id, anchor_node_id, situation_type from context_situations "
        "where org_id=:o and situation_type in "
        "('awaiting_response','first_response_overdue','commitment_overdue')"), {"o": ORG}).all()
    
    got = miss = 0
    bps = []
    for sid, anchor, stype in sits:
        events = absence_receipt_event_ids(c, ORG, str(anchor or ""), str(stype))
        bundle = gather_l1_signals_for_events(c, ORG, events) if events else None
        if bundle is not None and bundle.importance_bp is not None:
            got += 1; bps.append(bundle.importance_bp)
        else:
            miss += 1
    print(f"   situations checked              {len(sits):>4}")
    print(f"   now carry a real L1 bundle      {got:>4}   (was 0 — all held at the 4000 default)")
    print(f"   still no receipt                {miss:>4}")
    if bps:
        print(f"   importance now spans            {min(bps)}–{max(bps)} bp "
              f"across {len(set(bps))} distinct values")
