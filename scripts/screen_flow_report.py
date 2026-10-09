#!/usr/bin/env python
"""SCREEN FLOW REPORT — read-only. Where does screen intelligence actually get to, per org?

The question this answers, which nothing else did: a manager's screen is being read — so how far
does what it saw travel? There are four gates between a laptop and the company graph, and when
one of them is shut the symptom is identical to "the product found nothing":

    1. a device is registered and signed in          → `devices`
    2. capture is enabled for the org                → `capture_policies.enabled`
    3. the org's L1 semantic lane is activated       → `l1_semantic_activation`
       (the promoter's claim filters on this: an unactivated org's rows stay `held` forever)
    4. the delta is promoted into a source event     → `screen_session_deltas.status`
                                                     → `source_events where source='screen_session'`

and then, separately from reaching the graph, whether anything was ever SHOWN:

    5. `capture_policies.moments_display` off ⇒ every moment is stored with
       `suppressed_reason='shadow'` — intelligence runs, nobody sees it.

Nothing here writes. Run:  .venv/bin/python scripts/screen_flow_report.py [--org org_xxx]
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text


def engine():
    url = os.environ.get("GENIOS_DATABASE_URL")
    if not url:
        for name in (".env.production", ".env"):
            try:
                for line in open(name):
                    if line.startswith("GENIOS_DATABASE_URL"):
                        url = line.split("=", 1)[1].strip().strip('"')
                        break
            except OSError:
                continue
            if url:
                print(f"# using {name}", file=sys.stderr)
                break
    if not url:
        sys.exit("GENIOS_DATABASE_URL not set and no .env found")
    for old in ("postgresql://", "postgres://"):
        if url.startswith(old):
            url = url.replace(old, "postgresql+psycopg://", 1)
            break
    return create_engine(url, connect_args={"connect_timeout": 20})


#: (heading, sql). `:org` is bound when --org is given, else the clause is dropped.
QUERIES: list[tuple[str, str]] = [
    ("1. seats (who could be captured)",
     "select org_id, seat_id, email from org_seats {where} order by org_id, email limit 50"),
    ("2. devices registered",
     "select org_id, seat_id, platform, created_at, last_seen_at, revoked_at from devices "
     "{where} order by created_at limit 50"),
    ("3. capture policy per org",
     "select org_id, enabled, moments_display, generic_web_allowed, draft_assist_allowed, "
     "allowed_apps from capture_policies {where} order by org_id"),
    ("4. L1 semantic lane activated?",
     "select org_id, enabled_at, disabled_at from l1_semantic_activation {where} order by org_id"),
    ("5. screen deltas — WHERE THE DATA IS",
     "select org_id, status, count(*) n, min(received_at) first_seen, max(received_at) last_seen "
     "from screen_session_deltas {where} group by 1, 2 order by 1, 2"),
    ("6. reached the graph (source events)",
     "select org_id, count(*) events, max(captured_at) last_event from source_events "
     "where source = 'screen_session' {and_org} group by 1 order by 1"),
    # `capability_id` is "moment.screen_insight" / "moment.draft_review" — NOT prefixed "screen",
    # which is why an earlier version of this query reported nothing and looked like a verdict.
    ("7. moments from screen — shown vs shadow",
     "select org_id, capability_id, display, coalesce(suppressed_reason, '-') reason, count(*) n, "
     "max(created_at) last from moments where capability_id in "
     "('moment.screen_insight', 'moment.draft_review', 'moment.counterparty_recall', "
     " 'moment.duplicate_outreach') {and_org} group by 1, 2, 3, 4 order by 1, 5 desc"),
    ("7b. every moment, by capability",
     "select org_id, capability_id, display, count(*) n, max(created_at) last from moments "
     "{where} group by 1, 2, 3 order by 1, 4 desc limit 20"),
    ("8. follow-ups the screen produced",
     "select org_id, app, kind, count(*) n, "
     "count(*) filter (where resolved_at is not null) resolved, max(created_at) last "
     "from screen_followups {where} group by 1, 2, 3 order by 1, 4 desc limit 30"),
    ("9. what the screen lanes cost",
     "select org_id, purpose, count(*) calls, sum(input_tokens) in_tok, sum(output_tokens) out_tok, "
     "max(created_at) last from llm_costs where purpose like 'screen%' {and_org} "
     "group by 1, 2 order by 1, 3 desc"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", help="limit to one org_id")
    args = ap.parse_args()
    eng = engine()
    params = {"org": args.org} if args.org else {}
    where = "where org_id = :org" if args.org else ""
    and_org = "and org_id = :org" if args.org else ""
    for heading, sql in QUERIES:
        q = sql.format(where=where, and_org=and_org)
        print(f"\n== {heading}")
        try:
            with eng.connect() as c:
                rows = list(c.execute(text(q), params))
        except Exception as exc:                      # a missing table is an answer too
            print("   ERROR:", str(exc).splitlines()[0][:160])
            continue
        if not rows:
            print("   (no rows)")
            continue
        for r in rows:
            print("  ", {k: v for k, v in r._mapping.items()})
    print("\n-- read-only; nothing above writes.")


if __name__ == "__main__":
    main()
