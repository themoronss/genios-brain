"""GeniOS-008 L2 I1 · the shadow report — what the new L2 concluded, beside what today's path shows.

    python scripts/l2_shadow_report.py --org <org_id> [--days 7] [--json]

READ-ONLY. For each subject the judgment pass reasoned in the window (`reasoning_results`, 0243) it prints
the NEW path's reading — lane, intervention, depth, frame, next move, confidence levels, the needs it asked,
the check's fate, the cost — and, beside it, TODAY's path for the same file: the open cards on the file's
anchor (`cards` ⋈ `signals`) and the expert's latest review mode (`expert_reviews`). This is what Rohit and
Harsh read to decide whether a situation type can switch (`speedrun008/GeniOS-008/01-RULES.md` Rule 2), before
the golden set scores both.

It writes nothing and calls no model. The target is NAMED (`scripts/_db`): `--database-url` or
`GENIOS_TARGET_DATABASE_URL`; production also needs `GENIOS_ALLOW_PROD_WRITE=1` (the resolver's word — this script
only reads). Run it with a read-only role.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts._db import add_database_argument, resolve_database_url  # noqa: E402

_ROWS = text(
    "select subject_ref, status, reason, depth, lane, result, receipt, cost_micro_usd, reasoned_at "
    "  from reasoning_results where org_id = :o and reasoned_at >= :since "
    " order by reasoned_at desc")
_CARDS = text(
    "select c.headline, c.state from cards c join signals s on s.signal_id = c.signal_id and s.org_id = c.org_id "
    " where c.org_id = :o and s.subject_node_id = :f and c.state not in ('resolved', 'expired') "
    " order by c.created_at desc limit 3")
_REVIEW = text(
    "select review ->> 'mode' as mode, review -> 'next_move' ->> 'what' as move from expert_reviews "
    " where org_id = :o and file_id = :f and status = 'valid' order by reviewed_at desc limit 1")


def _today(conn, org: str, subject_ref: str) -> dict:
    if not subject_ref.startswith("file:"):
        return {"cards": [], "expert": None}
    f = subject_ref.split(":", 1)[1]
    cards = [f"{r.headline} [{r.state}]" for r in conn.execute(_CARDS, {"o": org, "f": f})]
    rev = conn.execute(_REVIEW, {"o": org, "f": f}).first()
    return {"cards": cards, "expert": (f"{rev.mode}: {rev.move or '—'}" if rev is not None else None)}


def report(engine, org: str, *, days: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    with engine.connect() as conn:
        for r in conn.execute(_ROWS, {"o": org, "since": since}):
            result = r.result if isinstance(r.result, dict) else {}
            review, judgment = result.get("review") or {}, result.get("judgment") or {}
            move = review.get("next_move") or {}
            out.append({
                "subject": r.subject_ref, "status": r.status, "reason": r.reason, "depth": r.depth, "lane": r.lane,
                "intervention": judgment.get("intervention_mode"),
                "frame": (review.get("frames") or {}).get("primary"),
                "next_move": f"{move.get('what')} (by {move.get('by_when')})" if move else None,
                "confidence": {k: v.get("level") for k, v in (judgment.get("confidence") or {}).items()},
                "needs": [n.get("question") for n in judgment.get("evidence_needs") or [] if n.get("decision_changing")],
                "check": result.get("check_fate"), "cost_usd": round((r.cost_micro_usd or 0) / 1e6, 4),
                "at": r.reasoned_at.isoformat(), "today": _today(conn, org, r.subject_ref)})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--org", required=True)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    add_database_argument(ap)
    args = ap.parse_args(argv)
    url = resolve_database_url(args, purpose="L2 shadow report (read-only)", stream=sys.stderr)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    rows = report(create_engine(url), args.org, days=args.days)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    if not rows:
        print(f"no L2 results for {args.org} in the last {args.days} day(s) — is `l2_reasoning` switched on?")
        return 0
    spent = sum(r["cost_usd"] for r in rows)
    print(f"{len(rows)} subject(s) reasoned, ${spent:.2f}\n")
    for r in rows:
        print(f"■ {r['subject']}  [{r['status']}] lane={r['lane']} depth={r['depth']} check={r['check']}")
        if r["status"] != "result":
            print(f"    why: {r['reason']}")
        else:
            print(f"    NEW   frame: {r['frame']}")
            print(f"          move:  {r['next_move']}  ({r['intervention']})")
            print(f"          conf:  " + ", ".join(f"{k}={v}" for k, v in r["confidence"].items()))
            if r["needs"]:
                print(f"          asks:  " + " | ".join(r["needs"]))
        today = r["today"]
        print(f"    TODAY expert: {today['expert'] or '—'}; open cards: {'; '.join(today['cards']) or 'none'}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
