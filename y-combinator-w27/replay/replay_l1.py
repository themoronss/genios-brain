"""Replay the shipped L1 guards over every stored qualified signal. READ ONLY."""
import json, os, re
from sqlalchemy import create_engine, text

from genios_engine.capture.preprocess.quoted import _ATTRIBUTION, _QUOTE_LINE
from genios_engine.capture.semantic.evidence_binder import substantive

ORG = "org_e97e86f858ad48b2bbf64b8a"
url = os.environ["GENIOS_TARGET_DATABASE_URL"]
if url.startswith("postgresql://"): url = "postgresql+psycopg://" + url[len("postgresql://"):]
eng = create_engine(url, connect_args={"connect_timeout": 20,
                                       "options": "-c default_transaction_read_only=on"})

# The lane a stored signal's receipt was bound under is not stored, so the date rule is applied
# in its STRICTEST form here (never date-bearing) and separately in its most lenient. The truth
# is between them and both bounds are reported.
DATEY = {"deadline_stated", "commitment_due"}

with eng.connect() as c:
    rows = c.execute(text(
        "select signal_type, importance_bp, evidence_refs from qualified_signals "
        "where org_id=:o order by importance_bp desc"), {"o": ORG}).mappings().all()

kept = hist = thin_strict = thin_lenient = 0
examples = {"history": [], "thin": []}
for r in rows:
    refs = r["evidence_refs"] or []
    if isinstance(refs, str): refs = json.loads(refs)
    quote = (refs[0] or {}).get("quote", "") if refs else ""
    is_hist = bool(_ATTRIBUTION.search(quote or "")) or bool(_QUOTE_LINE.search(quote or ""))
    if is_hist:
        hist += 1
        if len(examples["history"]) < 6:
            examples["history"].append((r["signal_type"], r["importance_bp"], quote[:70]))
        continue
    strict = substantive(quote, None)
    lenient = substantive(quote, "dates_mentioned" if r["signal_type"] in DATEY else None)
    if not strict: thin_strict += 1
    if not lenient:
        thin_lenient += 1
        if len(examples["thin"]) < 6:
            examples["thin"].append((r["signal_type"], r["importance_bp"], quote[:70]))
    else:
        kept += 1

print(f"\n{'='*78}\nLAYER 1 — the shipped guards replayed over all {len(rows)} stored signals\n{'='*78}")
print(f"  refused as REPLY HISTORY          {hist:>4}")
print(f"  refused as a THIN RECEIPT         {thin_lenient:>4}   (strictest reading: {thin_strict})")
print(f"  survive                           {kept:>4}   ({kept*100//len(rows)}% of {len(rows)})")
print(f"\n  --- refused as history (top by importance) ---")
for t, bp, q in examples["history"]: print(f"   {bp:>5} bp  {t:<22} {q!r}")
print(f"\n  --- refused as a thin receipt ---")
for t, bp, q in examples["thin"]: print(f"   {bp:>5} bp  {t:<22} {q!r}")
