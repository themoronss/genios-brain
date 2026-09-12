"""L2 -> L3/L4 -> cards for one org — the server's `_process_and_reason_tracked`, run locally.

Called by `scripts/dev_localdb.sh run <org_id>`. REFUSES any database that is not on localhost:
this exists to iterate against a local copy of production, and a typo in an env var must not
turn a debugging run into a write against paying tenants.
"""
import logging
import os
import sys
import time
from collections import Counter

from sqlalchemy import text

logging.basicConfig(level=logging.WARNING,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

ORG = os.environ.get("GENIOS_DEV_ORG", "").strip()
if not ORG:
    sys.exit("GENIOS_DEV_ORG is required")

from genios_engine.platform import wiring as W  # noqa: E402
from genios_engine.platform.config import get_settings  # noqa: E402

s = get_settings()
if "@localhost:" not in s.database_url and "@127.0.0.1:" not in s.database_url:
    sys.exit("refusing: GENIOS_DATABASE_URL is not a localhost database")
print(f"org={ORG} | db=local | LLM decision maker={s.l4_llm_decision_maker} "
      f"model={s.l4_llm_decision_model or s.anthropic_model}", flush=True)

graph = W.make_graph_store()
llm = W.make_llm_client()
registry = W.make_pack_registry()
card_store = W.make_card_store()

t0 = time.time()
from genios_engine.platform.intelligence_onboarding import provision_intelligence  # noqa: E402
provision_intelligence(graph.engine, ORG)

from genios_engine.context.runner import process_pending  # noqa: E402
t = time.time()
processed = 0
while True:
    out = process_pending(org_id=ORG, store=graph, llm=llm, registry=registry,
                          crypto_key=s.crypto_key, max_total=500,
                          on_progress=lambda n: print(f"  L2 +{n}", flush=True))
    n = int(out.get("processed", 0))
    processed += n
    if n == 0:
        break
print(f"L2 done: processed={processed} in {time.time() - t:.0f}s", flush=True)

t = time.time()
from genios_engine.reason.runner import run_all  # noqa: E402
result = run_all(org_id=ORG, store=graph, registry=registry)
print(f"L3/L4 done in {time.time() - t:.0f}s: {result}", flush=True)

if card_store is not None:
    from genios_engine.deliver.pipeline import build_cards_for_org  # noqa: E402
    print(f"cards: {build_cards_for_org(graph=graph, card_store=card_store, org_id=ORG, llm=llm, registry=registry)}",
          flush=True)

from genios_engine.reason import llm_decision_maker as m  # noqa: E402
print(f"LLM decision calls: {dict(m._calls_by_org_day)}", flush=True)

# What the run actually decided, straight from the rows it wrote.
with graph.engine.connect() as c:
    since = {"o": ORG, "t": t0}
    rows = c.execute(text(
        "select o.outcome_kind, "
        "exists (select 1 from reasoning_candidates rc where rc.org_id=o.org_id "
        "and rc.run_id=o.run_id and rc.score_components ? 'llm_utility') as llm "
        "from reasoning_run_outputs o "
        "where o.org_id=:o and o.created_at >= to_timestamp(:t)"), since).fetchall()
    print(f"decisions this run: {dict(Counter((r.outcome_kind, 'llm' if r.llm else 'formula') for r in rows))}",
          flush=True)
    by_state = dict(c.execute(text("select state, count(*) from cards where org_id=:o "
                                   "group by state"), {"o": ORG}).fetchall())
    print(f"cards by state now: {by_state} | total {time.time() - t0:.0f}s", flush=True)
