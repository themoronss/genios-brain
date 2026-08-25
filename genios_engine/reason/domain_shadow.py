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

import json
import logging
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore
from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
    gather_members,
    gather_visibility,
)
from genios_engine.contracts.reasoning import ExecutionMode
from genios_engine.packs.compiler import DomainCompiler, PostgresRuntimeBrains
from genios_engine.packs.compiler.errors import (
    NoExpertiseRoute,
    RequiredKnowledgeMissing,
    SituationContextConflict,
    SituationContextIncomplete,
    UnsupportedCoverage,
)
from genios_engine.packs.compiler.expertise_publisher import PostgresExpertisePublisher
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


_EXPERTISE_PACK = "expertise"          # the compiled brain's lane in signals.pack_id


def _emit_capability_signal(conn, *, org_id: str, node_id: str, package, execution,
                            eval_time) -> bool:
    """Write the compiled brain's decision as signal.v1, tagged with the capability that made it.

    The delivery side has always been able to render this — card_builder reads
    ``signal["capability_id"]`` for a card's capability_key — but `signals` had no such column, so
    the read returned None and every card looked like legacy output. Migration 0074 adds it; this
    is the only writer.

    ``pack_id='expertise'`` keeps the compiled brain in its own lane, so the ON CONFLICT that keeps
    one open signal per (org, pack, rule, node) cannot make a capability signal and a legacy rule
    signal evict each other. Both may stand on the same node during the cutover — which is the
    point, since that is how the two are compared.

    Returns False when a concurrent pass already emitted this one; the caller counts, never raises.
    """
    decision = execution.decision
    selected = next((c for c in decision.candidates
                     if c.candidate_id == decision.selected_candidate_id), None)
    if selected is None:                        # no_action / blocked / insufficient_context
        return False                            # nothing to advise → nothing to deliver
    review_state = str((package.review_state if hasattr(package, "review_state")
                        else (package.to_semantic_dict() or {}).get("review_state")) or "draft")
    row = conn.execute(text(
        "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, rule_version, "
        "level, subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
        "reasoning_run_id, reasoning_candidate_id, reasoning_decision_hash, authority_expires_at, "
        "authority_binding_version, do_nothing_consequence, uncertainty, outcome_window_days, "
        "capability_id, capability_version, capability_review_state) "
        "values (:id,:o,:pack,:packv,:r,:rv,:lv,:n,:s,cast(:si as jsonb),:rc,cast(:ev as jsonb),"
        ":play,:et,:run,:cand,:dhash,:exp,1,:dnc,cast(:unc as jsonb),:owd,:cap,:capv,:caprev) "
        "on conflict (org_id,pack_id,pack_version,rule_id,subject_node_id) "
        "where status='open' do nothing returning signal_id"), {
            "id": new_id("sig"), "o": org_id,
            "pack": _EXPERTISE_PACK, "packv": decision.capability_version,
            "r": decision.capability_id, "rv": decision.capability_version,
            "lv": "prescriptive" if review_state == "accepted" else "observation",
            "n": node_id,
            "s": decision.confidence_bp / 100.0,
            "si": json.dumps({"confidence_bp": decision.confidence_bp}),
            "rc": getattr(selected, "reason_code", None) or decision.capability_id,
            "ev": json.dumps(list(getattr(execution, "evidence_ids", ()) or []), default=str),
            "play": getattr(selected, "play_id", None),
            "et": eval_time, "run": getattr(execution, "run_id", None),
            "cand": decision.selected_candidate_id,
            "dhash": getattr(execution, "decision_hash", None),
            "exp": decision.expires_at,
            "dnc": decision.do_nothing_consequence,
            "unc": json.dumps(list(decision.uncertainty)),
            "owd": decision.outcome_window_days,
            "cap": decision.capability_id, "capv": decision.capability_version,
            "caprev": review_state,
        }).first()
    return row is not None


def shadow_compile(*, store: GraphStore, org_id: str, eval_time: datetime | None = None,
                   limit: int = 200, live: bool = False) -> dict:
    """Compile every active L2 situation into an ExpertisePackage; return route/coverage tallies.

    ``live=False`` (the default, and every existing caller) is unchanged: nothing is persisted and
    no decision is touched. Per-situation failures are counted, never raised, so one unroutable
    situation cannot abort the pass (or the sweep that called it).

    ``live=True`` is the cutover. Three things flip together, because any one of them alone leaves
    the compiled brain unable to reach a user:

    * a real publisher, so ``expertise_packages`` is written rather than the package being built
      and dropped on the floor;
    * ``require_admission=True``, so only capabilities a named reviewer accepted may carry
      authority — the fail-closed default the measurement mode deliberately relaxes;
    * ``ExecutionMode.LIVE`` and an emitted ``signals`` row carrying the capability's identity, so
      delivery can build a card from it and the card can say which brain authored it.

    Until this existed the corpus was 152 authored capabilities that could not produce a single
    card: the compile ran (behind a flag that is off), published nothing, and reasoned in SHADOW.
    Every card on every tenant came from the legacy pack rules, which is exactly what the product
    was showing.
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

    # A live pass writes (packages, signals); a shadow pass only reads. begin() for the former so
    # a package and the signal built from it cannot land apart.
    ctx = store.engine.begin() if live else store.engine.connect()
    with ctx as conn:
        situations = conn.execute(text(_ACTIVE_SITUATIONS),
                                  {"o": org_id, "lim": limit}).mappings().all()
        compiler = DomainCompiler(
            catalog=catalog,
            runtime_brains=PostgresRuntimeBrains(conn),
            # shadow: never write an expertise_packages row. live: write it, or the compiled
            # brain has no durable authority for delivery to read back.
            publisher=PostgresExpertisePublisher(conn) if live else None,
            # MEASUREMENT mode: draft content may compile so route coverage is measurable, but
            # the package carries review_state='draft' and the delivery abstention gate keeps
            # anything built from it non-prescriptive. Authority compiles use the fail-closed
            # default — a text-editor stub flip can no longer grant production authority.
            require_admission=bool(live),
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
                # Attach the neighbourhood to the context the CAPABILITY reasons over, not just to
                # the slice the compiler reads. Every situation here anchors on a `company`, and a
                # company node holds no facts of its own — 15 of 18 had literally zero. Everything a
                # capability asks for (thread.ball_in_court, deal.status, commitment.due_at) is
                # extracted correctly by L2 and stored on the PEOPLE and THREADS that constitute the
                # relationship. Without this the reasoner saw an empty company and every decision
                # came back INSUFFICIENT_CONTEXT — which is why the compiled brain has never
                # produced a single card while the data it needed was already in the graph.
                ctx = replace(ctx, edge_count=neighbor[0], neighbor_obs=set(neighbor[1]),
                              neighbor_facts=dict(neighbor[2]))
                signal_ids, evidence = gather_evidence_and_signals(
                    conn, org_id, row["correlation_id"], str(row["situation_id"]))
                members = gather_members(conn, org_id, row["correlation_id"])
                situation_visibility = gather_visibility(conn, org_id, row["correlation_id"])
                trace_id = new_id("trace")
                bso = build_business_situation(
                    org_id=org_id, situation=row,
                    signal_ids=signal_ids, evidence=evidence, trace_id=trace_id,
                    members=members, visibility=situation_visibility)
                context_slice = build_context_slice(
                    visibility=situation_visibility,
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
                        mode=ExecutionMode.LIVE if live else ExecutionMode.SHADOW)
                    counts["reasoned"] += 1
                    if execution.decision is not None:
                        counts["decided"] += 1
                        if live and _emit_capability_signal(
                                conn, org_id=org_id, node_id=anchor, package=package,
                                execution=execution, eval_time=eval_time):
                            counts["emitted"] += 1
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
            except UnsupportedCoverage as exc:
                # An honest "we do not cover this yet" — a route matched but every capability
                # behind it is an unauthored stub. This used to fall into the catch-all below,
                # indistinguishable from an actual compiler bug, which is exactly the confusion
                # the route-coverage metric exists to resolve. Counted by REASON so "all_stub"
                # (authoring debt) reads apart from "no_route" (nothing claims this situation).
                counts[f"unsupported_{exc.reason}"] += 1
            except Exception:
                counts["error"] += 1
                logger.exception("domain-compiler shadow: situation %s failed",
                                 row["situation_id"])

    result = dict(counts)
    logger.info("domain-compiler %s org=%s %s", "LIVE" if live else "shadow", org_id, result)
    return result


__all__ = ["shadow_compile"]
