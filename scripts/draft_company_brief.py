"""Draft a tenant's company brief from memory patterns — proposals only, never accepted (STEP-07).

    python scripts/draft_company_brief.py --org <org_id> --database-url postgresql://… --patterns
    python scripts/draft_company_brief.py --org <org_id> --database-url postgresql://…
    python scripts/draft_company_brief.py --org <org_id> --database-url postgresql://… --apply

`--patterns` prints what the drafter would be shown — counts, names, domains, dates
(`reason/brief_patterns`) — and calls no model. Without a flag it is a DRY RUN: one Sonnet-class call
(`reason/brief_drafter`, about $0.05, recorded in `llm_costs` as `company_brief_draft`), and it prints
every proposed line with the patterns it rests on, and every refused line with its reason — writing no
line. `--apply` makes the same call and writes the lines as PROPOSALS; nothing reaches a prompt until
the founder accepts it (`scripts/company_brief.py`, or the dashboard's screen).

Every database door goes through `scripts/_db.py`: no fallback to the application's database, and
`GENIOS_ALLOW_PROD_WRITE=1` for a production host.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="the one tenant whose brief is drafted")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--patterns", action="store_true",
                      help="print what the drafter would be shown, and call no model")
    mode.add_argument("--apply", action="store_true",
                      help="write the proposed lines as proposals (nothing is accepted)")
    return ap.parse_args(argv)


def render(outcome, patterns: dict[str, Any], *, applied: bool) -> str:
    """The proposals and what each rests on, then the refusals — never a message."""
    by_id = {i["id"]: i for i in patterns.get("items", ())}
    if outcome.skipped:
        return f"no draft: {outcome.skipped}"
    out = [f"{len(outcome.lines)} line(s) proposed by {outcome.model} "
           f"({outcome.input_tokens} in / {outcome.output_tokens} out tokens)"
           + (f" — {outcome.proposed} written as proposals" if applied
              else " — a dry run, nothing written")]
    for p in outcome.lines:
        named = p.address or p.domain
        out.append(f"  [{p.section}] {p.text}" + (f" <{named}>" if named else ""))
        for e in p.evidence:
            item = {k: v for k, v in by_id.get(e, {}).items() if k != "id"}
            out.append(f"      rests on {e}: {json.dumps(item, ensure_ascii=False, sort_keys=True)}")
    if outcome.refused:
        out += ["", f"refused ({len(outcome.refused)}):"] + [f"  {r}" for r in outcome.refused]
    return "\n".join(out)


def main(argv: list[str] | None = None, *, llm: Any = None) -> int:
    args = parse_args(argv)
    url = resolve_database_url(args, purpose="draft a tenant's company brief")
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.db import get_engine
    from genios_engine.reason.brief_drafter import draft_company_brief
    from genios_engine.reason.brief_patterns import patterns_for

    engine = get_engine(url)
    now = datetime.now(timezone.utc)
    with engine.connect() as c:
        patterns = patterns_for(c, args.org, now=now)
    if args.patterns:
        print(f"{len(patterns['items'])} pattern(s) for {args.org} over {patterns['window_days']} days "
              f"— company {patterns['company'] or '(none)'}, founder {patterns['founder'] or '(none)'}")
        for item in patterns["items"]:
            print("  " + json.dumps(item, ensure_ascii=False, sort_keys=True))
        return 0
    if llm is None:
        from genios_engine.platform.wiring import make_company_brief_client
        llm = make_company_brief_client()
    if llm is None:
        print("no model is configured (GENIOS_ANTHROPIC_API_KEY, with real LLM calls on) — "
              "--patterns shows what it would read")
        return 2
    outcome = draft_company_brief(engine, args.org, llm, now=now,
                                  cost_sink=GraphStore(engine=engine).record_cost,
                                  proposed_by="drafter", apply=args.apply)
    print(render(outcome, patterns, applied=args.apply))
    return 1 if outcome.skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
