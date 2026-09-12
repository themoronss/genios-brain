"""P0.0 — where does the time go between "an email is in L1" and "its card exists"?

Times the server's chain (provision → L2 → L4 → cards) on a LOCAL copy of production, per stage,
with the number of DB statements each stage sent. The local copy answers in ~0.1 ms, production
is a network hop away, so the script also prints an estimate: local ms + statements × RTT.

Two runs, same org:
  idle   nothing pending — the fixed cost every warm-lane run pays even for one email.
  new N  the N most recent processed events are made pending again (their L2 ledger row and the
         L2-own extraction cache are deleted, so L2 really re-reads them and pays the model),
         then the same chain runs.

    GENIOS_DATABASE_URL="$(scripts/dev_localdb.sh url)" GENIOS_POSTHOG_API_KEY= \
    GENIOS_OPS_ALERT_WEBHOOK= GENIOS_L4_LLM_DECISION_MAKER=false PYTHONPATH=. \
    .venv/bin/python scripts/measure_chain.py <org_id> [--events 50] [--rtt-ms 2,5,20]

REFUSES any database that is not on localhost. Afterwards `scripts/dev_localdb.sh restore`
returns the copy to its dump.
"""
import argparse
import logging
import sys
import time

from sqlalchemy import text

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")

ap = argparse.ArgumentParser()
ap.add_argument("org_id")
ap.add_argument("--events", type=int, default=50)
ap.add_argument("--rtt-ms", default="2,5,20")
ap.add_argument("--breakdown", action="store_true",
                help="also time every L2 pass and L4 unit by name (idle run is enough)")
args = ap.parse_args()
ORG = args.org_id
RTTS = [float(x) for x in args.rtt_ms.split(",") if x.strip()]

from genios_engine.platform import wiring as W  # noqa: E402
from genios_engine.platform.config import get_settings  # noqa: E402

s = get_settings()
if "@localhost:" not in s.database_url and "@127.0.0.1:" not in s.database_url:
    sys.exit("refusing: GENIOS_DATABASE_URL is not a localhost database")

from genios_engine.context.runner import _pull, process_pending  # noqa: E402
from genios_engine.deliver.pipeline import build_cards_for_org  # noqa: E402
from genios_engine.platform.intelligence_onboarding import provision_intelligence  # noqa: E402
from genios_engine.platform.stage_timer import count_statements, stage  # noqa: E402
from genios_engine.reason.runner import run_all  # noqa: E402

graph = W.make_graph_store()
llm = W.make_llm_client()
registry = W.make_pack_registry()
card_store = W.make_card_store()
count_statements(graph.engine)
print(f"org={ORG} | db=local | L4 LLM decision maker={s.l4_llm_decision_maker}", flush=True)


BREAK: dict[str, list[int]] = {}      # label -> [calls, ms, db]
_TARGETS = {
    "genios_engine.context.runner": ["_convergence_state_hash", "_internal_emails",
                                     "_record_convergence"],
    "genios_engine.context.derived": ["compute", "compute_deal_view", "compute_account_view"],
    "genios_engine.context.waiting": ["compute_waiting"],
    "genios_engine.context.periodic": ["refresh_period_situations"],
    "genios_engine.context.support_situations": ["refresh_support_situations"],
    "genios_engine.context.meeting_touch": ["refresh_channel_touch_situations"],
    "genios_engine.context.outreach_situations": ["refresh_state_situations"],
    "genios_engine.context.document_register": ["refresh_document_situations"],
    "genios_engine.context.correlation_resource": ["refresh_contract_spend"],
    "genios_engine.context.correlation_history": ["publish_histories"],
    "genios_engine.context.analytic.history": ["prune_history_for_drain"],
    "genios_engine.context.attention": ["refresh_attention"],
    "genios_engine.context.situations": ["refresh_situations", "age_uncorrelated_situations"],
    "genios_engine.context.lifecycle": ["detect_resolutions"],
    "genios_engine.context.analytic.sampler": ["backfill_history_for_drain", "sample_org"],
    "genios_engine.context.analytic.trend": ["refresh_trend_facts"],
    "genios_engine.context.analytic.anomaly": ["refresh_anomaly_facts"],
    "genios_engine.context.analytic.cohort": ["refresh_cohorts_for_drain"],
    "genios_engine.context.analytic.peer_baseline": ["refresh_baselines_for_drain"],
    "genios_engine.context.analytic.comparator": ["refresh_comparison_facts"],
    "genios_engine.context.correlation_dependency": ["refresh_dependency_chains"],
    "genios_engine.context.correlation_timeline": ["refresh_dormant_conditions"],
    "genios_engine.context.analytic.gap_reason": ["refresh_gap_corrected_trends"],
    "genios_engine.context.situation_bso": ["refresh_situation_importance"],
    "genios_engine.context.patterns.store": ["evaluate_org"],
    "genios_engine.reason.domain_shadow": ["shadow_compile"],
    "genios_engine.reason.runner": ["run", "_graph_version", "persist_execution"],
    "genios_engine.reason.bundle": ["narrate_published"],
}


def _wrap(mod, attr: str, label: str) -> None:
    import functools
    fn = getattr(mod, attr, None)
    if not callable(fn):
        print(f"  (breakdown: {label} not found, skipped)")
        return

    @functools.wraps(fn)
    def timed(*a, **k):
        rec = None
        try:
            with stage(label, ORG) as rec:
                return fn(*a, **k)
        finally:
            if rec is not None:
                agg = BREAK.setdefault(label, [0, 0, 0])
                agg[0] += 1
                agg[1] += rec.get("ms", 0)
                agg[2] += rec.get("db", 0)
    setattr(mod, attr, timed)


if args.breakdown:
    import importlib
    for modname, attrs in _TARGETS.items():
        m = importlib.import_module(modname)
        for a in attrs:
            _wrap(m, a, f"{modname.split('.')[-1]}.{a}")


def print_breakdown(label: str) -> None:
    if not BREAK:
        return
    print(f"\n-- breakdown: {label} (nested: reason.run includes _graph_version/persist_execution)")
    print(f"{'unit':<46}{'calls':>7}{'ms':>9}{'db':>8}{'@2ms':>9}")
    for name, (n, ms, db) in sorted(BREAK.items(), key=lambda kv: -kv[1][2])[:30]:
        print(f"{name:<46}{n:>7}{ms:>9}{db:>8}{(ms + db * 2) / 1000:>8.1f}s")
    BREAK.clear()


def pending() -> int:
    return len(_pull(graph, ORG, 100000))


def llm_calls_since(t0: float) -> dict:
    with graph.engine.connect() as c:
        rows = c.execute(text("select purpose, count(*) from llm_costs where org_id=:o "
                              "and created_at >= to_timestamp(:t) group by 1"),
                         {"o": ORG, "t": t0}).fetchall()
    return {r[0]: r[1] for r in rows}


def chain(label: str) -> list[dict]:
    recs, t0 = [], time.time()
    with stage("provision", ORG) as r:
        provision_intelligence(graph.engine, ORG)
    recs.append(r)
    with stage("l2.drain", ORG) as r:
        done, settled = 0, False
        while True:                          # same stop rule as the server's drain loop
            n = int(process_pending(org_id=ORG, store=graph, llm=llm, registry=registry,
                                    crypto_key=s.crypto_key, max_total=500).get("processed", 0))
            done += n
            if settled or n == 0:
                break
            if n < 500:
                settled = True
        r["processed"] = done
    recs.append(r)
    with stage("l4.run_all", ORG) as r:
        run_all(org_id=ORG, store=graph, registry=registry)
    recs.append(r)
    if card_store is not None:
        with stage("deliver.build_cards", ORG) as r:
            build_cards_for_org(graph=graph, card_store=card_store, org_id=ORG, llm=llm,
                                registry=registry)
        recs.append(r)
    report(label, recs, llm_calls_since(t0))
    return recs


def report(label: str, recs: list[dict], calls: dict) -> None:
    head = f"{'stage':<22}{'local ms':>10}{'db stmts':>10}" + "".join(
        f"{f'@{rtt:g}ms RTT':>14}" for rtt in RTTS)
    print(f"\n== {label}\n{head}")
    tot_ms = tot_db = 0
    for r in recs:
        tot_ms += r["ms"]
        tot_db += r.get("db", 0)
        est = "".join(f"{(r['ms'] + r.get('db', 0) * rtt) / 1000:>13.1f}s" for rtt in RTTS)
        extra = f"  processed={r['processed']}" if "processed" in r else ""
        print(f"{r['stage']:<22}{r['ms']:>10}{r.get('db', 0):>10}{est}{extra}")
    est = "".join(f"{(tot_ms + tot_db * rtt) / 1000:>13.1f}s" for rtt in RTTS)
    print(f"{'TOTAL':<22}{tot_ms:>10}{tot_db:>10}{est}")
    print(f"LLM calls this run: {calls or 'none'}", flush=True)


before = pending()
print(f"pending before idle run: {before}"
      + ("  (NOT idle — the first run also drains these)" if before else ""), flush=True)
chain(f"idle (pending={before})")
print_breakdown("idle")
if args.events <= 0:
    sys.exit(0)

with graph.engine.begin() as c:
    ids = [r[0] for r in c.execute(text(
        "select se.event_id from source_events se "
        "where se.org_id=:o and se.outcome='emitted' "
        "and exists (select 1 from qualified_signals qs where qs.org_id=se.org_id "
        "            and qs.event_id=se.event_id and qs.state='active' "
        "            and qs.extraction_ref is not null) "
        "and exists (select 1 from l2_processing_runs r where r.org_id=se.org_id "
        "            and r.event_id=se.event_id and r.status='done') "
        "order by se.occurred_at desc limit :n"), {"o": ORG, "n": args.events}).fetchall()]
    c.execute(text("delete from l2_processing_runs where org_id=:o and event_id = any(:ids)"),
              {"o": ORG, "ids": ids})
    c.execute(text("delete from l1_extraction_results where org_id=:o and profile_id is null "
                   "and event_id = any(:ids)"), {"o": ORG, "ids": ids})
print(f"\nre-queued {len(ids)} events; pending now {pending()}", flush=True)
chain(f"new events (N={len(ids)})")
print_breakdown(f"new events (N={len(ids)})")
