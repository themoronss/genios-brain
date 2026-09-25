#!/usr/bin/env python3
"""L2-4-U0/U5 · what Layer 2 mints that no corpus can read, and what would end it — read-only.

    python scripts/unroutable_report.py --corpus-only          # no database, runnable today
    python scripts/unroutable_report.py --org <id> --database-url <url>

⛔ **THE STEP'S PREMISE WAS OUT OF DATE AND THIS IS WHAT FOUND IT.** step-04 §1 says *"no
fundraising corpus exists"*; `_L2_TO_L3_DOMAIN`'s own comment says *"no corpus was authored for
them"*. Measured against the catalog: `sales.sit.live_investor_relationship` and
`sales.sit.live_investor_contact` are **authored, stable and approved**, and behind them sits
`sales.investor_relations.investor_relations` — *"reading and running the relationships with the
people who might fund the company"*.

**The doctrine exists. One `None` makes it unreachable from the pilot's dominant domain.**

READ-ONLY, AND STRUCTURALLY SO — through `scripts/_db.py`, which has no fallback to `Settings`,
and every statement here is a `select`.

THE `--corpus-only` HALF NEEDS NO DATABASE, and it is the half that carries the finding: which
corpora exist, which dark domain has a candidate route with evidence, and which authored
situations are still `draft` and therefore cannot instruct.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url  # noqa: E402

_UNROUTABLE = """
select domain, situation_type, count(*) as situations
  from context_situations
 where org_id = :org and status = 'active' and domain = any(:domains)
 group by domain, situation_type
 order by count(*) desc
"""


def _corpus_section(corpus_root: str) -> list[str]:
    from genios_engine.context.domain_silence import DARK_DOMAINS, reason_for
    from genios_engine.context.domain_spec import registered_domains, spec_for
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    from genios_engine.packs.compiler.capability_resolver import situation_admission_reason
    from genios_engine.reason.domain_shadow import CANDIDATE_ROUTES, _L2_TO_L3_DOMAIN

    catalog = ExpertBrainCatalog(corpus_root)
    out = ["LAYER 2 · WHAT NO AUTHORED CORPUS CAN READ", "=" * 68, "",
           "ROUTING  (every registered L2 domain, zeros and Nones shown on purpose)", "-" * 68]
    for domain in sorted(registered_domains()):
        corpus = _L2_TO_L3_DOMAIN.get(domain)
        candidate = CANDIDATE_ROUTES.get(domain)
        mark = f"→ {corpus}" if corpus else ("⛔ DARK" + (f"  (candidate: {candidate.corpus})"
                                                         if candidate else ""))
        out.append(f"  {domain:<16}{mark}")

    out += ["", "WHY EACH DARK DOMAIN IS DARK  (they are not the same reason)", "-" * 68]
    for domain in sorted(DARK_DOMAINS):
        types = sorted(set(spec_for(domain).situation_types.values()))
        out.append(f"  {domain}  — mints {', '.join(types)}")
        why = reason_for(domain) or ""
        # PRINT FROM THE MOVER BACKWARDS. The first sentences are context; the part somebody acts
        # on is the ENDS WHEN, and truncating from the front is how a report gets read as "this
        # is just broken" instead of "here is the one line that fixes it".
        head, sep, mover = why.partition("ENDS WHEN")
        # A CORRECTION TRUNCATION CAN HIDE IS A CORRECTION NOBODY READS. Split it out and always
        # print it, whatever the context above it costs in lines.
        context, marker, correction = head.partition("⛔ CORRECTED")
        out += textwrap.wrap(context.strip(), 96, initial_indent="      ",
                             subsequent_indent="      ", max_lines=3, placeholder=" …")
        if marker:
            out += textwrap.wrap(marker + correction, 96, initial_indent="      ",
                                 subsequent_indent="      ")
        if sep:
            out += textwrap.wrap(sep + mover, 96, initial_indent="      ⇒ ",
                                 subsequent_indent="        ")
        if domain in CANDIDATE_ROUTES:
            out.append(f"      ⇒ CANDIDATE ROUTE: {CANDIDATE_ROUTES[domain].corpus} "
                       f"— declared, evidenced, NOT armed")
        out.append("")

    out += ["THE 24 AUTHORED SITUATIONS THAT CANNOT INSTRUCT  (L2-0, still open)", "-" * 68,
            "  a `draft` situation makes its package `review_state='draft'`; "
            "`_apply_abstention`",
            "  then downgrades the card to an OBSERVATION — it describes, it does not instruct.",
            ""]
    for domain_id, record in sorted(catalog.domains.items()):
        drafts = sorted(sid for sid, doc in record.situations.items()
                        if situation_admission_reason(doc.content))
        out.append(f"  {domain_id:<18}{len(drafts):>3} of {len(record.situations):<3} draft")
        for sid in drafts:
            out.append(f"       {sid}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org")
    parser.add_argument("--corpus-root", default="Domain Expertise")
    parser.add_argument("--corpus-only", action="store_true")
    add_database_argument(parser)
    args = parser.parse_args()

    lines = _corpus_section(args.corpus_root)

    if not args.corpus_only:
        if not args.org:
            parser.error("--org is required unless --corpus-only is given")
        url = resolve_database_url(args, purpose="L2-4 unroutable report (read-only)")

        from sqlalchemy import create_engine, text

        from genios_engine.context.domain_silence import DARK_DOMAINS

        engine = create_engine(url)
        with engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(
                text(_UNROUTABLE), {"org": args.org, "domains": sorted(DARK_DOMAINS)})]

        lines += ["", "ON THIS TENANT  (situations minted that route nowhere)", "-" * 68,
                  f"  {'domain':<16}{'situation type':<28}{'situations':>12}"]
        # PER TYPE, NOT PER DOMAIN — a corpus is authored per situation type, and the totals
        # differ by an order of magnitude between types inside one domain.
        for row in rows:
            lines.append(f"  {str(row['domain']):<16}{str(row['situation_type'] or '?'):<28}"
                         f"{int(row['situations']):>12}")
        lines += ["-" * 68,
                  f"  TOTAL PRODUCING NOTHING: {sum(int(r['situations']) for r in rows)}"]

    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
