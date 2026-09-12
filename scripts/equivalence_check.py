"""Prove a performance change did not change what the engine concluded.

    dump  — run provision → L2 → L4 → cards for one org at a PINNED instant with no LLM, then write
            every output table's rows for that org to a JSON file.
    diff  — compare two dumps of the OLD code (a, a2) with one of the NEW code (b). Columns that
            differ between a and a2 are run-to-run noise (timestamps, random ids) and are named and
            skipped; every other column must match row for row between a and b.

Local copy only (refuses any non-localhost DB). Typical use, restoring the copy before each dump:

    scripts/dev_localdb.sh restore
    GENIOS_DATABASE_URL="$(scripts/dev_localdb.sh url)" GENIOS_ANTHROPIC_API_KEY= \
      GENIOS_POSTHOG_API_KEY= GENIOS_OPS_ALERT_WEBHOOK= GENIOS_L4_LLM_DECISION_MAKER=false \
      PYTHONPATH=<old or new checkout> .venv/bin/python scripts/equivalence_check.py dump <org> a.json
    ... (again for a2.json with the old code, and b.json with the new)
    .venv/bin/python scripts/equivalence_check.py diff a.json a2.json b.json

No LLM so the run is deterministic; the changes this checks are DB-access changes, not prompts.
`--l2-calls` repeats `process_pending` to reproduce a caller that looped (the old drain loop).
"""
import json
import sys
from collections import Counter
from datetime import datetime

TABLES = ("graph_nodes", "graph_facts", "graph_edges", "graph_source_refs", "graph_observations",
          "context_situations", "context_correlations", "context_correlation_members",
          "context_attention", "metric_history", "l2_convergence", "signals", "cards",
          "signal_suppression_log", "reasoning_runs", "reasoning_run_outputs",
          "situation_admission_decisions", "expertise_packages")
EVAL_TIME = "2026-09-12T13:00:00+00:00"


def dump(org: str, path: str, l2_calls: int) -> None:
    from sqlalchemy import text

    import genios_engine
    from genios_engine.context.runner import process_pending
    from genios_engine.deliver.pipeline import build_cards_for_org
    from genios_engine.platform import wiring as W
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.intelligence_onboarding import provision_intelligence
    from genios_engine.reason.runner import run_all

    s = get_settings()
    if "@localhost:" not in s.database_url and "@127.0.0.1:" not in s.database_url:
        sys.exit("refusing: GENIOS_DATABASE_URL is not a localhost database")
    if s.use_real_llm:
        sys.exit("refusing: set GENIOS_ANTHROPIC_API_KEY= so the run is deterministic")
    print(f"code: {genios_engine.__file__}", flush=True)
    at = datetime.fromisoformat(EVAL_TIME)
    graph, registry, cards = W.make_graph_store(), W.make_pack_registry(), W.make_card_store()
    provision_intelligence(graph.engine, org)
    for _ in range(l2_calls):
        process_pending(org_id=org, store=graph, llm=None, registry=registry,
                        crypto_key=s.crypto_key, max_total=500, eval_time=at)
    print(f"run_all: {run_all(org_id=org, store=graph, registry=registry, eval_time=at)}",
          flush=True)
    if cards is not None:
        build_cards_for_org(graph=graph, card_store=cards, org_id=org, llm=None,
                            registry=registry, eval_time=at)
    out = {}
    with graph.engine.connect() as c:
        for t in TABLES:
            has_org = c.execute(text("select 1 from information_schema.columns where "
                                     "table_name=:t and column_name='org_id'"), {"t": t}).first()
            if not has_org:
                print(f"  skip {t}: no org_id column")
                continue
            res = c.execute(text(f"select * from {t} where org_id=:o"), {"o": org})
            cols = list(res.keys())
            out[t] = {"cols": cols,
                      "rows": [[json.dumps(v, default=str, sort_keys=True) for v in r] for r in res]}
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"wrote {path}: " + ", ".join(f"{t}={len(v['rows'])}" for t, v in out.items()))


def _column(tab: dict, col: str) -> list:
    i = tab["cols"].index(col)
    return sorted(r[i] for r in tab["rows"])


def diff(pa: str, pa2: str, pb: str) -> None:
    a, a2, b = (json.load(open(p)) for p in (pa, pa2, pb))
    bad = 0
    for t in a:
        if t not in b:
            print(f"{t}: missing from new dump")
            bad += 1
            continue
        ta, ta2, tb = a[t], a2[t], b[t]
        if len(ta["rows"]) != len(ta2["rows"]):
            print(f"{t}: NOISY row count in the old code itself ({len(ta['rows'])} vs "
                  f"{len(ta2['rows'])}) — cannot judge this table")
            continue
        noisy = [c for c in ta["cols"] if _column(ta, c) != _column(ta2, c)]
        keep = [c for c in ta["cols"] if c not in noisy]
        key = lambda tab: Counter(tuple(r[tab["cols"].index(c)] for c in keep) for r in tab["rows"])
        ka, kb = key(ta), key(tb)
        status = "same" if (ka == kb and len(ta["rows"]) == len(tb["rows"])) else "DIFFERENT"
        if status != "same":
            bad += 1
        print(f"{t}: {status} rows old={len(ta['rows'])} new={len(tb['rows'])} "
              f"compared={len(keep)} cols, skipped noise={noisy}")
        if status != "same":
            for row, n in list((ka - kb).items())[:3]:
                print(f"   only in old ({n}x): {dict(zip(keep, row))}")
            for row, n in list((kb - ka).items())[:3]:
                print(f"   only in new ({n}x): {dict(zip(keep, row))}")
    print("\nRESULT:", "IDENTICAL" if bad == 0 else f"{bad} table(s) differ")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "dump":
        calls = int(sys.argv[sys.argv.index("--l2-calls") + 1]) if "--l2-calls" in sys.argv else 1
        dump(sys.argv[2], sys.argv[3], calls)
    elif len(sys.argv) == 5 and sys.argv[1] == "diff":
        diff(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)
