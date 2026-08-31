"""READ-ONLY route-coverage probe for the compiled brain's corpus.

Runs the same resolution the live compile does — the real catalog, the real generated registry,
the real L2 situations — and reports the outcome PER SITUATION TYPE. `shadow_compile` already
returns totals; totals cannot say which authored gap to close next, which is the one question
the corpus work order asks after every item.

Writes nothing: no package is published, no signal emitted, no decision persisted.

    python scripts/corpus_route_probe.py [org_id]
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.packs.compiler.domain_compiler import DomainCompiler
from genios_engine.packs.compiler.errors import (
    AuthoringIntegrityError,
    NoExpertiseRoute,
    RequiredKnowledgeMissing,
    SituationContextConflict,
    SituationContextIncomplete,
    UnsupportedCoverage,
)
from genios_engine.packs.compiler.runtime_brains import PostgresRuntimeBrains
from genios_engine.platform.wiring import make_graph_store
from genios_engine.reason.domain_shadow import (
    _ACTIVE_SITUATIONS,
    build_business_situation,
    build_context_slice,
    expert_catalog,
    gather_evidence_and_signals,
    gather_members,
    gather_visibility,
)
from genios_engine.platform.ids import new_id

DEFAULT_ORG = "org_e97e86f858ad48b2bbf64b8a"


def main() -> int:
    org_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ORG
    eval_time = datetime.now(timezone.utc)
    from genios_engine.reason.runner import (
        _graph_version, _load_context, _neighbor_index, _neighborhood,
    )

    store = make_graph_store()
    catalog = expert_catalog()
    graph_version = _graph_version(store, org_id)
    adj, _types, obs_idx, fact_idx = _neighbor_index(store, org_id)

    by_type: dict[str, Counter] = defaultdict(Counter)
    caps_by_type: dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    samples: dict[str, str] = {}   # one verbatim reason per (type, outcome) — the actionable half

    with store.engine.connect() as conn:
        situations = conn.execute(text(_ACTIVE_SITUATIONS), {"o": org_id, "lim": 200}).mappings().all()
        compiler = DomainCompiler(catalog=catalog, runtime_brains=PostgresRuntimeBrains(conn),
                                  publisher=None, require_admission=False)
        for row in situations:
            stype = row["situation_type"]
            totals["situations"] += 1
            by_type[stype]["seen"] += 1
            anchor = row["anchor_node_id"]
            if not anchor:
                by_type[stype]["no_anchor"] += 1
                totals["no_anchor"] += 1
                continue
            try:
                node_ctx = _load_context(store, org_id, anchor, row["anchor_type"])
                neighbor = _neighborhood(anchor, adj, obs_idx, fact_idx)
                node_ctx = replace(node_ctx, edge_count=neighbor[0], neighbor_obs=set(neighbor[1]),
                                   neighbor_facts=dict(neighbor[2]))
                signal_ids, evidence = gather_evidence_and_signals(
                    conn, org_id, row["correlation_id"], str(row["situation_id"]))
                members = gather_members(conn, org_id, row["correlation_id"])
                vis = gather_visibility(conn, org_id, row["correlation_id"])
                trace_id = new_id("trace")
                bso = build_business_situation(org_id=org_id, situation=row, signal_ids=signal_ids,
                                               evidence=evidence, trace_id=trace_id, members=members,
                                               visibility=vis)
                slice_ = build_context_slice(visibility=vis, org_id=org_id, situation=row,
                                             facts=node_ctx.facts, observations=node_ctx.obs,
                                             neighbor=neighbor, graph_version=graph_version,
                                             eval_time=eval_time, trace_id=trace_id)
                package = compiler.compile(bso, slice_)
                by_type[stype]["ROUTED"] += 1
                totals["ROUTED"] += 1
                for cap in package.capabilities:
                    cid = cap["id"] if isinstance(cap, Mapping) else getattr(cap, "id", cap)
                    caps_by_type[stype][str(cid)] += 1
            except NoExpertiseRoute as exc:
                # Three different failures wear one exception, and they need three different
                # fixes: a domain hint the corpus has no folder for, a type no situation binds,
                # or a bound type whose authored `when` predicate rejected this instance.
                text_ = str(exc)
                if "unknown domains" in text_:
                    key = "unknown_domain_hint"
                elif "no authored" in text_:
                    key = "no_route_predicate"
                else:
                    key = "no_route_type"
                by_type[stype][key] += 1
                totals[key] += 1
                samples.setdefault(f"{stype}/{key}", text_[:200])
            except SituationContextIncomplete as exc:
                by_type[stype]["incomplete"] += 1
                totals["incomplete"] += 1
                samples.setdefault(f"{stype}/incomplete", str(exc)[:200])
            except SituationContextConflict:
                by_type[stype]["conflict"] += 1
                totals["conflict"] += 1
            except RequiredKnowledgeMissing as exc:
                by_type[stype]["required_missing"] += 1
                totals["required_missing"] += 1
                samples.setdefault(f"{stype}/required_missing", str(exc)[:200])
            except UnsupportedCoverage as exc:
                by_type[stype][f"unsupported_{exc.reason}"] += 1
                totals[f"unsupported_{exc.reason}"] += 1
            except AuthoringIntegrityError as exc:
                by_type[stype]["AUTHORING_ERROR"] += 1
                totals["AUTHORING_ERROR"] += 1
                print(f"  !! authoring: {stype}: {exc}")
            except Exception as exc:                    # noqa: BLE001
                by_type[stype]["error"] += 1
                totals["error"] += 1
                print(f"  !! error: {stype}: {type(exc).__name__}: {str(exc)[:120]}")

    n = totals["situations"]
    routed = totals["ROUTED"]
    print(f"\norg {org_id} — {routed}/{n} situations route "
          f"({100 * routed // max(1, n)}%)\n")
    print(f"{'situation_type':<26}{'seen':>5}{'routed':>8}  outcome")
    for stype in sorted(by_type, key=lambda t: -by_type[t]["seen"]):
        c = by_type[stype]
        rest = ", ".join(f"{k}={v}" for k, v in sorted(c.items())
                         if k not in {"seen", "ROUTED"})
        print(f"{stype:<26}{c['seen']:>5}{c['ROUTED']:>8}  {rest or '-'}")
    print("\ntotals:", dict(totals))
    if samples:
        print("\nwhy each non-routing outcome happened (one sample each):")
        for k in sorted(samples):
            print(f"  {k}\n      {samples[k]}")
    print("\ncapabilities reached, per type:")
    for stype in sorted(caps_by_type):
        for cap, k in sorted(caps_by_type[stype].items()):
            print(f"  {stype:<24} {cap}  x{k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
