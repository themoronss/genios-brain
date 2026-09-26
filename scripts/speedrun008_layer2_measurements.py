"""Layer 2's measurements (M1, M3, M4) in one read-only pass.

WHY THIS EXISTS ALONGSIDE `scripts/l2_refusal_report.py` AND FRIENDS. Those four scripts are the
canonical reports and this file does not replace them — it carries their SQL, unchanged, into the
same single `read only` transaction the Layer 1 measurements use. Their own guard
(`scripts/_db.resolve_database_url`) refuses any production target unless `GENIOS_ALLOW_PROD_WRITE`
is set, and that variable is named for writes because it was written for writes: it does not
distinguish a `select` from an `update`. Setting it to run a report that only reads is the wrong
shape of permission, and an agent should not be the one to decide that.

So: same queries, same tenant, no bypass flag, and the transaction itself is `read only` — a
statement that tried to write would be refused by Postgres rather than by a reviewer.

NOT COVERED HERE, deliberately:

  * **M2** (`slice_weight.py`) builds a context slice per situation. That is compute against the
    live graph, not a read of a table, so it belongs in its own invocation with its own decision.
  * **M6** (the shadow tallies) requires a sweep — `shadow_compile` has to RUN. A shadow pass
    persists nothing, but it reasons, and reasoning can spend. Whoever runs it should mean to.

USAGE
    .venv/bin/python scripts/speedrun008_layer2_measurements.py [--org org_...]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: The tenant every Layer 1 and Layer 2 number in the handoff was taken against.
_PILOT_ORG = "org_e97e86f858ad48b2bbf64b8a"


def _url() -> str:
    url = os.environ.get("GENIOS_DATABASE_URL")
    if url:
        return url
    env = _ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GENIOS_DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    sys.exit("GENIOS_DATABASE_URL is not set and .env does not carry one")


_QUERIES: list[tuple[str, str, str, str]] = [
    ("M1a", "What Layer 2 admitted, held and rejected",
     "The denominator for every Layer 2 number. Until this exists every later claim is measured "
     "against an unknown.",
     """select outcome, count(*) as n
          from situation_admission_decisions
         where org_id = :o
         group by outcome
         order by n desc"""),

    ("M1b", "WHY it held — every reason, most common first",
     "`BY LAW` is what arms V-9 and V-10 (decision D2). A low count means arm them; a high count "
     "means the producers owe receipts first.",
     """select trim(both '\"' from jsonb_array_elements_text(
                    case jsonb_typeof(reasons) when 'array' then reasons
                    else '[]'::jsonb end)) as reason,
               count(*) as n
          from situation_admission_decisions
         where org_id = :o
         group by 1
         order by n desc
         limit 30"""),

    ("M3", "The domains no authored corpus can read",
     "Every active situation sitting in a domain that routes to nothing. This is decision D3's "
     "denominator — how much the one `fundraising` line is actually worth.",
     """select domain, situation_type, count(*) as situations
          from context_situations
         where org_id = :o and status = 'active'
         group by domain, situation_type
         order by count(*) desc
         limit 40"""),

    ("M3b", "Active situations per domain, whether routable or not",
     "The shape of the tenant. `fundraising` and `general` are the two that route to nothing today.",
     """select domain, count(*) as situations
          from context_situations
         where org_id = :o and status = 'active'
         group by domain
         order by situations desc"""),

    ("M4", "What the founder actually sees — signals with no card",
     "Needs migration 0182 (`signals.situation_id`). Without it this reports the uninterpreted "
     "total only, which is still the number that matters: open signals nothing put in front of "
     "anybody.",
     """select count(*) as open_signals_without_a_card,
               count(distinct s.rule_id) as distinct_rules,
               count(distinct s.subject_node_id) as distinct_subjects
          from signals s
          left join cards k on k.org_id = s.org_id and k.signal_id = s.signal_id
               and k.state not in ('expired','dismissed')
         where s.org_id = :o and s.status = 'open' and k.card_id is null"""),

    ("M4b", "The same, split by rule — which doctrine is producing unseen signals",
     "A rule near the top is one whose output never reaches a card.",
     """select s.rule_id, count(*) as signals
          from signals s
          left join cards k on k.org_id = s.org_id and k.signal_id = s.signal_id
               and k.state not in ('expired','dismissed')
         where s.org_id = :o and s.status = 'open' and k.card_id is null
         group by s.rule_id
         order by signals desc
         limit 15"""),

    ("—", "Migrations 0176..0185 — which are actually applied to THIS database?",
     "Every item above is measured against whatever schema is really deployed.",
     """select filename from schema_migrations
         where filename >= '0176' order by filename"""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default=_PILOT_ORG)
    args = ap.parse_args()

    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    engine = get_engine(_url())
    print(f"# speedrun008 · Layer 2 measurements · org={args.org}\n")
    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))
        for item, title, decides, sql in _QUERIES:
            print("=" * 96)
            print(f"[{item}] {title}")
            print(f"  -> {decides}")
            print("-" * 96)
            try:
                rows = conn.execute(text(sql), {"o": args.org}).mappings().all()
            except Exception as exc:                        # noqa: BLE001 — report, never abort
                print(f"  QUERY FAILED: {type(exc).__name__}: {str(exc)[:280]}")
                conn.rollback()
                conn.execute(text("set transaction read only"))
                print()
                continue
            if not rows:
                print("  (no rows)")
            else:
                cols = list(rows[0].keys())
                width = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
                print("  " + "  ".join(c.ljust(width[c]) for c in cols))
                for r in rows:
                    print("  " + "  ".join(str(r[c]).ljust(width[c]) for c in cols))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
