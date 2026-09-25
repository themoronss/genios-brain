#!/usr/bin/env python3
"""L2-3-U0 · what a real context slice weighs — read-only.

    python scripts/slice_weight.py --org <org_id> --database-url <url> --sample 10

⛔ **THIS NUMBER IS L2-5's COST CHECK.** The step file: *"take ten real candidates and compute the
slice size in tokens. The cost check for L2-5 depends on this number, and **guessing it would make
that check theatre**."* And §2: *"the difference between a 10,000-token thread and a 900-token
slice is the whole bill."*

READ-ONLY, AND STRUCTURALLY SO. The target resolves through `scripts/_db.py`, which has no
fallback to `Settings` — *"nothing in the invocation names production; you get it by running the
script at all"* — and every statement here is a `select`. It builds slices exactly the way
`domain_shadow` does, through `_bulk_load_facts` / `_bulk_load_obs` and `build_context_slice`, so
what it weighs is what the reasoner would actually be handed rather than an approximation of it.

THE SHAPE IS COMPUTED SOMEWHERE ELSE. `context/slice_weight.py` is pure and tested without a
database; this file only assembles slices and prints what that module returns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url  # noqa: E402

_SITUATIONS = """
select situation_id, anchor_node_id, anchor_type, domain, situation_type
  from context_situations
 where org_id = :org and status = 'active'
 order by situation_id
 limit :limit
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True)
    parser.add_argument("--sample", type=int, default=10,
                        help="how many active situations to weigh")
    add_database_argument(parser)
    args = parser.parse_args()

    url = resolve_database_url(args, purpose="L2-3 slice weight (read-only)")

    from sqlalchemy import create_engine, text

    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.situation_bso import build_context_slice
    from genios_engine.context.slice_weight import (
        CHARS_PER_TOKEN, SLICE_TOKEN_BUDGET, budget_reason, over_budget, weigh,
        weigh_all,
    )
    from genios_engine.reason.runner import (
        _bulk_load_facts, _bulk_load_obs, _graph_version, _load_context, _neighbor_index,
        _neighborhood,
    )

    engine = create_engine(url)
    store = GraphStore(engine)

    # ONE org-wide read each, exactly as the sweep does — not one query per situation. Weighing a
    # slice built a different way would measure a slice nothing produces.
    facts_by_node = _bulk_load_facts(store, args.org)
    obs_by_node = _bulk_load_obs(store, args.org)
    adj, _node_types, obs_idx, fact_idx = _neighbor_index(store, args.org)
    graph_version = _graph_version(store, args.org)

    from datetime import UTC, datetime
    eval_time = datetime.now(UTC)

    slices, rows = [], []
    with engine.connect() as conn:
        for row in conn.execute(text(_SITUATIONS), {"org": args.org, "limit": args.sample}):
            record = dict(row._mapping)
            anchor = str(record["anchor_node_id"])
            node_ctx = _load_context(store, args.org, anchor, record["anchor_type"],
                                     facts_by_node=facts_by_node, obs_by_node=obs_by_node)
            neighbor = _neighborhood(anchor, adj, obs_idx, fact_idx)
            built = build_context_slice(
                org_id=args.org, situation=record, facts=node_ctx.facts,
                observations=node_ctx.obs, neighbor=neighbor, graph_version=graph_version,
                eval_time=eval_time, trace_id="slice-weight-readonly")
            slices.append(built)
            rows.append((record["situation_id"], record.get("situation_type"), weigh(built)))

    print("LAYER 2 · WHAT A CONTEXT SLICE WEIGHS")
    print("=" * 62)
    print(f"estimate: characters // {CHARS_PER_TOKEN}  (declared, so the arithmetic is auditable)")
    print("-" * 62)
    for situation_id, situation_type, weight in sorted(rows, key=lambda r: -r[2].tokens):
        flag = " ⛔" if over_budget(weight) else ""
        print(f"  {str(situation_id)[:28]:<28} {str(situation_type or '')[:18]:<18}"
              f"{weight.tokens:>8} tok{flag}")
    print("-" * 62)
    report = weigh_all(slices)
    print(f"  {report.sentence}")
    if report.over_budget:
        # THE BUDGET REPORTS AND NEVER TRUNCATES. Dropping facts to hit a number is how a
        # reasoner concludes from evidence nobody chose to remove.
        print(f"\n  ⛔ {report.over_budget} slice(s) over {SLICE_TOKEN_BUDGET} tokens.")
        print(f"     {budget_reason()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
