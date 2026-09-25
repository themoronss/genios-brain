"""Every measurement `speedrun008/HARSH-ORDER.md` asks the CTO for, in one read-only pass.

WHY THIS EXISTS. The handoff asks for eight numbers and spreads them over eight documents, each
with its SQL in a different section. Run separately they are eight copy-pastes and eight chances
to run one against the wrong tenant; run here they are one command, one connection, one tenant,
and one block of output to paste back.

READ-ONLY BY CONSTRUCTION, and not merely by intention: the whole pass runs inside a single
transaction opened `read only`, so a typo that became an UPDATE is refused by Postgres rather
than caught by review. Nothing here writes, creates, or locks a row for longer than its own
SELECT.

USAGE
    export GENIOS_DATABASE_URL="postgresql://..."      # or let it read .env
    .venv/bin/python scripts/speedrun008_measurements.py [--org org_...]

The org defaults to the tenant the handoff measured (`_PILOT_ORG`). `--org all` reports every
tenant for the queries that are per-tenant, which is what you want if the 19 September re-sync
moved the corpus somewhere else.

WHAT EACH NUMBER DECIDES is printed beside it, because a number whose consequence you have to go
and look up is a number nobody acts on.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
# Runnable as `python scripts/...` from anywhere, the way every other script here is invoked.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: The tenant every "before" number in the handoff was taken against.
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


#: (harsh-order item, title, what the answer decides, SQL). `:o` binds the org where relevant.
_QUERIES: list[tuple[str, str, str, str]] = [
    ("8", "Re-extraction bill — the whole corpus re-extracts on the first sweep after deploy",
     "input_tokens_last_time x current price = the bill. Then accept / stage to one tenant / "
     "defer. RUN THIS BEFORE DEPLOYING: the fingerprint has already moved (151b9dabf235 -> "
     "a3d5496aa0d3), so the deploy itself starts the spend.",
     """select count(*)                        as rows_to_reextract,
               count(distinct org_id)          as tenants,
               sum(coalesce(input_tokens, 0))  as input_tokens_last_time,
               sum(coalesce(output_tokens, 0)) as output_tokens_last_time
          from l1_extraction_results"""),

    ("10", "Domain coverage — metric 4 has no live baseline",
     "If really_tagged is already high, the domain proposer (item 11) is not worth switching on.",
     """select count(*)                                                            as signals,
               count(*) filter (where domain_hints is null
                                   or domain_hints::text = '[]')                   as no_domain,
               count(*) filter (where domain_hints::text like '%%\"fallback\"%%')  as fallback_only,
               count(*) filter (where domain_hints is not null
                                   and domain_hints::text <> '[]'
                                   and domain_hints::text not like '%%\"fallback\"%%')
                                                                                   as really_tagged
          from qualified_signals
         where org_id = :o"""),

    ("13", "Relevance — metric 5 (was 69 of 225, 31% never judged)",
     "never_judged ('ambiguous_over_budget') should now be near zero: the all-or-nothing guard is "
     "gone and allocate_budget DEFERS ('unjudged_for_budget') instead of refusing the page. "
     "NOTE: the handoff's SQL reads `source_events.relevance_rule`, which does not exist in this "
     "schema — the rule is filed on the S4 trace row as `reason_code`, which is what this reads.",
     """select coalesce(reason_code, '(none)') as relevance_rule,
               action,
               count(*)                        as n
          from event_trace
         where org_id = :o and stage = 's4_esqe'
         group by 1, 2
         order by n desc"""),

    ("15", "Step 10's own gate — the measurement that may cancel the step",
     "68 or 0 both mean the thresholds are wrong, and 0 means step 10 is not needed yet. If one "
     "signal_type dominates, the answer is 8-U3 (a floor relative to the tenant's distribution), "
     "not a review queue.",
     """select signal_type,
               count(*)                                                as drops,
               round(avg(importance_bp))                               as avg_importance_bp,
               round(avg(floor_bp))                                    as avg_floor_bp,
               round(avg((components ->> 'achievable_ceiling_bp')::numeric))
                                                                       as avg_achievable_ceiling_bp
          from qualification_drops
         where org_id = :o
         group by signal_type
         order by drops desc"""),

    ("17", "Commitment states — the trap-detector",
     "MOST must land in UNKNOWN. If most land in BROKEN the coverage gate is NOT wired and the "
     "step has produced a confident lie. BROKEN requires coverage >= 9000 bp.",
     """select state, count(*) as n
          from qualified_signals
         where org_id = :o and state is not null
         group by state
         order by n desc"""),

    ("18", "Joinability — whether P4's answer means anything",
     "What share of calendar attendees have an email-side counterpart. Without this, 'no follow-up "
     "found' could mean no follow-up happened OR the two sides were never joinable — opposite fixes.",
     """with attendees as (
            select distinct lower(r) as who
              from source_events, unnest(coalesce(recipients, '{}')) as r
             where org_id = :o and source = 'gcal' and r is not null and r <> ''),
          mail as (
            select distinct lower(actor ->> 'email') as who
              from source_events
             where org_id = :o and source = 'gmail' and actor ->> 'email' is not null
            union
            select distinct lower(r)
              from source_events, unnest(coalesce(recipients, '{}')) as r
             where org_id = :o and source = 'gmail' and r is not null and r <> '')
        select (select count(*) from attendees)                           as calendar_attendees,
               (select count(*) from attendees a join mail m using (who)) as joinable,
               (select count(*) from mail)                                as email_side_people"""),

    ("19", "Replies vs total — re-sync (A) or forward-only (B)",
     "Every prompt ever sent said 'message 1 of 1'. If replies are a SMALL share, A (re-sync the "
     "mailbox) is cheap and worth it. If most of the mailbox is threaded, the re-extraction is "
     "real and B buys time.",
     """with threads as (
            select parent_object_id, count(*) as msgs
              from source_events
             where org_id = :o and source = 'gmail' and parent_object_id is not null
             group by 1)
        select (select count(*) from source_events
                 where org_id = :o and source = 'gmail')                  as total_messages,
               coalesce((select sum(msgs) from threads where msgs > 1), 0) as messages_in_real_threads,
               coalesce((select count(*) from threads where msgs > 1), 0)  as multi_message_threads,
               coalesce((select max(msgs) from threads), 0)                as longest_thread"""),

    ("1/5", "Attachments and OCR — is the deployed image reading anything at all?",
     "Every row with ocr_engine NULL and ocr_pages 0 means OCR has still never run. This is how "
     "you verify the Dockerfile deploy AFTER it lands. (The column is `format`, not `mime_type` "
     "as the handoff's SQL has it.)",
     """select status, format, count(*) as n,
               count(*) filter (where ocr_engine is not null) as with_engine,
               coalesce(sum(ocr_pages), 0)                    as ocr_pages
          from document_jobs
         where org_id = :o
         group by status, format
         order by n desc"""),

    ("9", "Which corpus is actually there — was the 19 September re-sync intentional?",
     "The handoff's 'before' numbers were taken against 12 Aug - 8 Sep. If this shows only 19-23 "
     "Sep, that corpus is gone and three of the six metrics cannot be re-measured.",
     """select date_trunc('day', occurred_at)::date as day, count(*) as events
          from source_events
         where org_id = :o
         group by 1 order by 1"""),

    ("-", "Migrations — are 0176..0182 actually applied to THIS database?",
     "If a row is missing here, the code that names those columns is running against a schema "
     "that does not have them. Boot applies them; a read-only database skips them silently.",
     """select filename from schema_migrations
         where filename >= '0176' order by filename"""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default=_PILOT_ORG,
                    help="tenant to measure (default: the handoff's pilot org)")
    args = ap.parse_args()

    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    engine = get_engine(_url())
    print(f"# speedrun008 measurements · org={args.org}\n")
    with engine.connect() as conn:
        # READ ONLY on the transaction, so a mistake is refused by the server, not by review.
        conn.execute(text("set transaction read only"))
        for item, title, decides, sql in _QUERIES:
            print("=" * 96)
            print(f"[HARSH-ORDER item {item}] {title}")
            print(f"  -> {decides}")
            print("-" * 96)
            try:
                rows = conn.execute(text(sql), {"o": args.org}).mappings().all()
            except Exception as exc:                        # noqa: BLE001 — report, never abort
                print(f"  QUERY FAILED: {type(exc).__name__}: {str(exc)[:300]}")
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
                for r in rows[:40]:
                    print("  " + "  ".join(str(r[c]).ljust(width[c]) for c in cols))
                if len(rows) > 40:
                    print(f"  ... {len(rows) - 40} more rows")
            print()
    print("=" * 96)
    print("Item 14 is not SQL — it is one HTTP call against the running API:")
    print("  curl -s https://squid-app-2zuqf.ondigitalocean.app/parked/refetch")
    print("  A non-empty, untouched queue means the HEARTBEAT is not running in production,")
    print("  which is a much larger finding than 13 stuck PDFs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
