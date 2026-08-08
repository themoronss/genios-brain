"""Layer 3 Domain Expertise compiler — shadow pass over live Layer 2 situations.

This is the design's mandated first activation step: compile the real, already-qualified L2
situations into ``ExpertisePackage``s on live traffic and MEASURE route hits, coverage and misses
— WITHOUT persisting anything and WITHOUT feeding Layer 4. It never changes a decision, so it is
safe to run behind ``get_settings().use_domain_compiler`` in the normal sweep. Driving L4 from the
package (which needs an ExpertisePackage->CapabilityManifest adapter and per-tenant cutover) is a
separate, later step gated on the parity this pass produces.

Publisher is ``None`` so ``compile()`` returns the package without any DB write; the only reads are
the authored catalog (immutable) and the tenant's active ``learned_brain_entries`` runtime brains.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore
from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.contracts.reasoning import ExecutionMode
from genios_engine.packs.compiler import DomainCompiler, PostgresRuntimeBrains
from genios_engine.packs.compiler.errors import (
    NoExpertiseRoute,
    RequiredKnowledgeMissing,
    SituationContextConflict,
    SituationContextIncomplete,
)
from genios_engine.packs.domain_wiring import expert_catalog
from genios_engine.platform.ids import new_id
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability

logger = logging.getLogger(__name__)

# One tenant-scoped read of the active situations, with the correlation id (for evidence) and the
# anchor node type (for context loading) that active_situations() does not itself return.
_ACTIVE_SITUATIONS = (
    "select s.situation_id, s.situation_type, s.domain, s.status, s.correlation_id, "
    "       s.confidence_overall, s.coverage, s.missing, s.first_seen_at, s.last_seen_at, "
    "       s.anchor_node_id, n.display_name as anchor_name, n.node_type as anchor_type "
    "from context_situations s "
    "left join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id "
    "     and n.valid_to is null "
    "where s.org_id = :o and s.status = 'active' "
    "order by s.confidence_overall desc, s.last_seen_at desc nulls last limit :lim"
)


def shadow_compile(*, store: GraphStore, org_id: str, eval_time: datetime | None = None,
                   limit: int = 200) -> dict:
    """Compile every active L2 situation into an ExpertisePackage; return route/coverage tallies.

    Nothing is persisted and no decision is touched. Per-situation failures are counted, never
    raised, so one unroutable situation cannot abort the pass (or the sweep that called it).
    """
    eval_time = eval_time or datetime.now(timezone.utc)
    # Local imports: the shadow pass depends on the runner's context loaders, and the runner
    # imports this module behind the flag — a module-level import would be a cycle.
    from genios_engine.reason.runner import (
        _graph_version, _load_context, _neighbor_index, _neighborhood,
    )

    catalog = expert_catalog()
    graph_version = _graph_version(store, org_id)
    adj, _node_types, obs_idx, fact_idx = _neighbor_index(store, org_id)
    counts: Counter = Counter()

    with store.engine.connect() as conn:
        situations = conn.execute(text(_ACTIVE_SITUATIONS),
                                  {"o": org_id, "lim": limit}).mappings().all()
        compiler = DomainCompiler(
            catalog=catalog,
            runtime_brains=PostgresRuntimeBrains(conn),
            publisher=None,          # shadow: never write an expertise_packages row
        )
        for row in situations:
            counts["situations"] += 1
            anchor = row["anchor_node_id"]
            if not anchor:
                counts["no_anchor"] += 1
                continue
            try:
                ctx = _load_context(store, org_id, anchor, row["anchor_type"])
                neighbor = _neighborhood(anchor, adj, obs_idx, fact_idx)
                signal_ids, evidence = gather_evidence_and_signals(
                    conn, org_id, row["correlation_id"], str(row["situation_id"]))
                trace_id = new_id("trace")
                bso = build_business_situation(
                    org_id=org_id, situation=row,
                    signal_ids=signal_ids, evidence=evidence, trace_id=trace_id)
                context_slice = build_context_slice(
                    org_id=org_id, situation=row, facts=ctx.facts, observations=ctx.obs,
                    neighbor=neighbor, graph_version=graph_version,
                    eval_time=eval_time, trace_id=trace_id)
                package = compiler.compile(bso, context_slice)
                counts["compiled"] += 1
                counts["capabilities_total"] += len(package.capabilities)
                # L3 -> L4 weld: adapt the package into a CapabilityManifest and reason over it.
                # SHADOW mode + live_delivery_enabled=False on the manifest -> a decision is
                # produced and measured but never delivered or persisted as a signal.
                try:
                    manifest = expertise_capability_manifest(
                        package, root_entity_type=ctx.node_type)
                    execution = reason_native_capability(
                        org_id=org_id, context=ctx, capability=manifest, evaluation_time=eval_time,
                        graph_version=graph_version, config_snapshot_id=None,
                        mode=ExecutionMode.SHADOW)
                    counts["reasoned"] += 1
                    if execution.decision is not None:
                        counts["decided"] += 1
                except Exception:
                    counts["reason_error"] += 1
                    logger.exception("domain-compiler shadow: reasoning for %s failed",
                                     row["situation_id"])
            except NoExpertiseRoute:
                counts["no_route"] += 1
            except SituationContextIncomplete:
                counts["incomplete"] += 1
            except SituationContextConflict:
                counts["conflict"] += 1
            except RequiredKnowledgeMissing:
                counts["required_missing"] += 1
            except Exception:
                counts["error"] += 1
                logger.exception("domain-compiler shadow: situation %s failed",
                                 row["situation_id"])

    result = dict(counts)
    logger.info("domain-compiler shadow org=%s %s", org_id, result)
    return result


__all__ = ["shadow_compile"]
