"""Layer 3 Domain Expertise compiler — shadow pass over live Layer 2 situations.

This is the design's mandated first activation step: compile the real, already-qualified L2
situations into ``ExpertisePackage``s on live traffic and MEASURE route hits, coverage and misses
— WITHOUT persisting anything and WITHOUT feeding Layer 4. It never changes a decision, so it is
safe to run behind ``get_settings().use_domain_compiler`` in the normal sweep. Driving L4 from the
package (which needs an ExpertisePackage->CapabilityManifest adapter and per-tenant cutover) is a
separate, later step gated on the parity this pass produces.

In the measurement pass the publisher is ``None``, so ``compile()`` returns the package without any
DB write; the only reads are the authored catalog (immutable) and the tenant's active
``learned_brain_entries`` runtime brains. ``live=True`` is the cutover pass: it publishes the
package, commits the reasoning audit bundle, and emits a ``signals`` row bound to that bundle — see
``_persist_live``.
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
from genios_engine.packs.wiring import make_registry
from genios_engine.platform.ids import new_id
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.store import ReasoningStore

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


class _TxnExpertisePublisher:
    """Publish each package in its OWN transaction, off the loop's read connection.

    Obstacle 1, learned the hard way: one transaction wrapping the whole loop meant a single
    unroutable situation aborted the other 58 with ``InFailedSqlTransaction``. The compiler is
    built once and holds its publisher for the entire pass, so the PUBLISHER has to own the
    transaction boundary — the loop cannot.
    """

    def __init__(self, engine) -> None:
        self.engine = engine

    def publish(self, package):
        with self.engine.begin() as conn:
            return PostgresExpertisePublisher(conn).publish(package)


def _tenant_pack(registry, store, org_id: str, pack_id: str) -> dict | None:
    """The tenant's ACTIVE pack authority for ``pack_id``, or None when it holds none.

    A compiled signal cannot invent its own authority lane. Delivery reads a card's right to exist
    from ``AUTHORITATIVE_SIGNAL_PREDICATE``, which joins signal -> config_snapshot -> tenant_packs
    and requires all of: the config snapshot's ``pack_id`` equals the capability's ``domain``, its
    ``effective.version`` equals the tenant pack's version, the pack is ``active``, and the
    signal's ``authority_pack_revision`` equals the pack's current ``authority_revision``.

    So the compiled lane binds to the SAME effective config the legacy lane already mints through
    ``registry.effective`` — not to a synthetic snapshot. The two brains still cannot evict each
    other: the ON CONFLICT key includes ``rule_id``, and a capability id (``expertise.opportunity``)
    is not a legacy rule id.
    """
    effective, snapshot_id = registry.effective(org_id, pack_id)
    if not effective or not snapshot_id or str(effective.get("state") or "") != "active":
        return None
    with store.engine.connect() as conn:
        row = conn.execute(text(
            "select authority_revision from tenant_packs "
            "where org_id=:o and pack_id=:p and state='active'"),
            {"o": org_id, "p": pack_id}).first()
    if row is None or int(row.authority_revision) <= 0:   # obstacle 3: revision must be > 0
        return None
    return {"pack_id": pack_id, "version": str(effective["version"]),
            "revision": int(row.authority_revision), "snapshot_id": snapshot_id,
            "rule_ids": {str(rule.get("id")) for rule in (effective.get("rules") or ())}}


def _emit_capability_signal(conn, *, org_id: str, node_id: str, package, execution, bundle,
                            eval_time, pack: dict) -> str:
    """Write the compiled brain's decision as signal.v1, tagged with the capability that made it.

    The delivery side has always been able to render this — card_builder reads
    ``signal["capability_id"]`` for a card's capability_key — but `signals` had no such column, so
    the read returned None and every card looked like legacy output. Migration 0074 adds it; this
    is the only writer.

    EVERY audit id comes from ``bundle``, never from the in-memory decision. That is obstacle 9:
    ``signals`` carries an FK into ``reasoning_candidates (org_id, run_id, candidate_id)``, and the
    id stored there is NOT the contract id the decision holds. ``ReasoningStore._prepare_candidates``
    mints a persistence id as ``stable_id("cand", {run_id, candidate_hash})`` — deliberately, since
    a contract candidate id is semantic and repeats across replays while the DB key is tenant-wide —
    and keeps the contract id only as an in-memory alias that is never written. So
    ``decision.selected_candidate_id`` names a row that cannot exist, on a fresh run as much as on
    an idempotent replay. ``bundle["output"]["selected_candidate_id"]`` is that same contract id
    already resolved through the alias, i.e. the row's real key. The decision hash has the same
    split (``reasoning_run_outputs.decision_hash`` is the store's, not the contract's), and the
    config snapshot must be the one the RUN recorded, or ``signals_reasoning_run_config_fk`` fails.
    Reading all four off the persisted bundle also makes an idempotent reuse correct for free: the
    ids then belong to whichever run actually holds the rows.

    Returns what happened — emitted / standing / nothing_to_emit / rule_id_collision /
    race_lost — so the pass's tally distinguishes "no advice" from "advice already standing" from
    "a concurrent pass won". The caller counts; this never raises.
    """
    run = bundle.get("run") or {}
    output = bundle.get("output") or {}
    run_id = run.get("run_id")
    candidate_id = output.get("selected_candidate_id")
    decision_hash = output.get("decision_hash")
    config_snapshot_id = run.get("config_snapshot_id")
    if not (run_id and candidate_id and decision_hash and config_snapshot_id):
        return "nothing_to_emit"                # no_action / blocked / insufficient_context
    decision = execution.decision
    # The authority predicate derives a card's rule from the capability
    # (`s.rule_id = regexp_replace(rr.capability_id, '^.*\\.', '')`), so the signal's rule_id is
    # the capability id's last segment — `expertise.opportunity` -> `opportunity`. The FULL id
    # still travels in `capability_id`, which is what the cutover is measured on.
    rule_id = str(decision.capability_id).rsplit(".", 1)[-1]
    if rule_id in pack["rule_ids"]:
        # A situation type that shares a name with one of the tenant's own pack rules would make
        # the two brains evict each other on a shared node (the open-signal uniqueness key is
        # (org, pack, pack_version, rule_id, node)). Refuse and count it: losing a legacy card to
        # a silent overwrite is worse than not emitting this one, and the collision is a corpus
        # naming question a human has to settle.
        logger.warning("compiled capability %s collides with pack rule %s; not emitted",
                       decision.capability_id, rule_id)
        return "rule_id_collision"
    selected = next((c for c in decision.candidates
                     if c.candidate_id == decision.selected_candidate_id), None)
    selected_row = next((c for c in bundle.get("candidates") or ()
                         if c.get("candidate_id") == candidate_id), None)
    if selected_row is None:
        return "nothing_to_emit"
    # review_state lives in the package's METADATA, not at its top level and not in the semantic
    # dict. Both lookups above returned None on every real package, so the `or "draft"` fallback
    # fired every time — and `draft` is what makes a card an observation instead of an
    # instruction. Fifty-three cards told the design partner "Context incomplete — open the
    # source and review it before acting" while the packages behind them were all `accepted`
    # with zero admission gaps. The authority was earned and then thrown away by a lookup that
    # could not find it; a default that silently downgrades has to read the real field first.
    metadata = package.metadata if isinstance(getattr(package, "metadata", None), dict) else \
        dict(getattr(package, "metadata", {}) or {})
    review_state = str(metadata.get("review_state") or "draft")
    # The legacy lane will not re-publish a rule/node inside its cooldown window; without the same
    # discipline the sweep would expire and rebuild every compiled card on every run — a queue that
    # reshuffles under the user each sweep, and an LLM render paid for each time. The compiled
    # equivalent of a cooldown is the decision's OWN authority window: while an open signal for
    # this (pack, rule, node) is still within it, the advice stands and is left alone. A decision
    # hash comparison cannot serve here — `expires_at` is derived from the evaluation time, so the
    # hash differs on every sweep even when nothing about the situation changed.
    standing = conn.execute(text(
        "select signal_id from signals where org_id=:o and pack_id=:p and pack_version=:pv "
        "and rule_id=:r and subject_node_id=:n and status='open' "
        "and authority_expires_at > :now limit 1"),
        {"o": org_id, "p": pack["pack_id"], "pv": pack["version"], "r": rule_id,
         "n": node_id, "now": eval_time}).first()
    if standing is not None:
        return "standing"
    # One OPEN compiled signal per (pack, rule, node), same discipline as the legacy `_emit`: once
    # the window has passed, the refreshed advice replaces the stale row rather than colliding.
    retired = conn.execute(text(
        "update signals set status='expired' where org_id=:o and pack_id=:p and pack_version=:pv "
        "and rule_id=:r and subject_node_id=:n and status='open' returning signal_id"),
        {"o": org_id, "p": pack["pack_id"], "pv": pack["version"],
         "r": rule_id, "n": node_id}).fetchall()
    if retired:
        conn.execute(text(
            "update cards set state='expired' where org_id=:o and signal_id=any(:ids) "
            "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
            {"o": org_id, "ids": [item.signal_id for item in retired]})
    row = conn.execute(text(
        "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, rule_version, "
        "level, subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
        "config_snapshot_id, reasoning_run_id, reasoning_candidate_id, reasoning_decision_hash, "
        "authority_expires_at, authority_binding_version, authority_pack_revision, "
        "do_nothing_consequence, uncertainty, outcome_window_days, "
        "capability_id, capability_version, capability_review_state) "
        "values (:id,:o,:pack,:packv,:r,:rv,:lv,:n,:s,cast(:si as jsonb),:rc,cast(:ev as jsonb),"
        ":play,:et,:cfg,:run,:cand,:dhash,:exp,1,:rev,:dnc,cast(:unc as jsonb),:owd,"
        ":cap,:capv,:caprev) "
        "on conflict (org_id,pack_id,pack_version,rule_id,subject_node_id) "
        "where status='open' do nothing returning signal_id"), {
            "id": new_id("sig"), "o": org_id,
            # The tenant's own pack lane. `rule_version` is INTEGER (obstacle 2) and names the
            # authority binding, not the capability — the capability's hash is text and travels in
            # `capability_version`, which is the column the cutover is actually measured on.
            "pack": pack["pack_id"], "packv": pack["version"],
            "r": rule_id, "rv": 1,
            "lv": "prescriptive" if review_state == "accepted" else "observation",
            "n": node_id,
            # NOT the decision's confidence: the delivery authority predicate re-derives the
            # score from the selected candidate's utility
            # (`s.score = (selected_rc.final_utility_bp + 50) / 100`) and drops any signal whose
            # score it cannot reproduce. A projected number that disagrees with the audited
            # decision is exactly what that check exists to catch, so the projection has to come
            # from the same place the check reads.
            "s": (int(selected_row["final_utility_bp"]) + 50) // 100,
            "si": json.dumps({"confidence_bp": decision.confidence_bp,
                              "final_utility_bp": selected_row["final_utility_bp"],
                              "initial_utility_bp": selected_row.get("initial_utility_bp")}),
            # Same law as the score: the gate recomputes a non-legacy signal's reason_code from
            # the capability id, so the projection must be that, not the candidate's own label.
            "rc": rule_id,
            "ev": json.dumps(list(getattr(execution, "evidence_ids", ()) or []), default=str),
            "play": getattr(selected, "play_id", None),
            "et": eval_time, "cfg": config_snapshot_id,
            "run": run_id, "cand": candidate_id, "dhash": decision_hash,
            "exp": decision.expires_at, "rev": pack["revision"],
            "dnc": decision.do_nothing_consequence,
            "unc": json.dumps(list(decision.uncertainty)),
            "owd": decision.outcome_window_days,
            "cap": decision.capability_id, "capv": decision.capability_version,
            "caprev": review_state,
        }).first()
    return "emitted" if row is not None else "race_lost"


def _persist_live(*, store: GraphStore, reasoning_store: ReasoningStore, org_id: str,
                  node_id: str, package, execution, eval_time, pack: dict) -> str:
    """Commit the audit bundle, then the signal built from it. Two transactions, in that order.

    The audit bundle FIRST and through ``persist_execution``, never by hand: ``signals`` carries six
    FKs into the reasoning audit tables (run, candidate, decision, config, and the run/config pair),
    so a hand-made run id fails all of them (obstacle 5). Only once those rows exist can a signal
    legally point at them.
    """
    bundle = persist_execution(store=reasoning_store, execution=execution)
    with store.engine.begin() as conn:
        return _emit_capability_signal(
            conn, org_id=org_id, node_id=node_id, package=package, execution=execution,
            bundle=bundle, eval_time=eval_time, pack=pack)


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
    registry = make_registry() if live else None
    reasoning_store = ReasoningStore(engine=store.engine) if live else None
    packs: dict[str, dict | None] = {}      # capability domain -> the tenant's active pack lane

    # READS only on this connection, in both modes. Every live write (package, audit bundle,
    # signal) opens its own transaction per situation, so one unroutable row can never abort the
    # rest of the pass.
    with store.engine.connect() as conn:
        situations = conn.execute(text(_ACTIVE_SITUATIONS),
                                  {"o": org_id, "lim": limit}).mappings().all()
        compiler = DomainCompiler(
            catalog=catalog,
            runtime_brains=PostgresRuntimeBrains(conn),
            # shadow: never write an expertise_packages row. live: write it, or the compiled
            # brain has no durable authority for delivery to read back.
            publisher=_TxnExpertisePublisher(store.engine) if live else None,
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
                node_ctx = _load_context(store, org_id, anchor, row["anchor_type"])
                neighbor = _neighborhood(anchor, adj, obs_idx, fact_idx)
                # Attach the neighbourhood to the context the CAPABILITY reasons over, not just to
                # the slice the compiler reads. Every situation here anchors on a `company`, and a
                # company node holds no facts of its own — 15 of 18 had literally zero. Everything a
                # capability asks for (thread.ball_in_court, deal.status, commitment.due_at) is
                # extracted correctly by L2 and stored on the PEOPLE and THREADS that constitute the
                # relationship. Without this the reasoner saw an empty company and every decision
                # came back INSUFFICIENT_CONTEXT — which is why the compiled brain has never
                # produced a single card while the data it needed was already in the graph.
                node_ctx = replace(node_ctx, edge_count=neighbor[0],
                                   neighbor_obs=set(neighbor[1]),
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
                    org_id=org_id, situation=row, facts=node_ctx.facts,
                    observations=node_ctx.obs,
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
                        package, root_entity_type=node_ctx.node_type,
                        # The delivery authority predicate reads this flag off the persisted
                        # capability snapshot. False (the measurement default) means no card can
                        # ever be built from the decision, however complete its audit bundle is.
                        live_delivery_enabled=live)
                    pack = None
                    if live:
                        # The config snapshot must EXIST before reasoning and be passed in, not
                        # injected afterwards: `request_id` is derived from request content, so a
                        # `dataclasses.replace` after the fact invalidates it (obstacle 7).
                        if manifest.domain not in packs:
                            packs[manifest.domain] = _tenant_pack(
                                registry, store, org_id, manifest.domain)
                        pack = packs[manifest.domain]
                        if pack is None:
                            # The tenant holds no active pack in this capability's domain, so
                            # nothing can grant the decision authority. Counted, never guessed.
                            counts["no_tenant_pack"] += 1
                            continue
                    execution = reason_native_capability(
                        org_id=org_id, context=node_ctx, capability=manifest,
                        evaluation_time=eval_time, graph_version=graph_version,
                        config_snapshot_id=(pack["snapshot_id"] if pack else None),
                        mode=ExecutionMode.LIVE if live else ExecutionMode.SHADOW)
                    counts["reasoned"] += 1
                    if execution.decision is None:
                        continue
                    counts["decided"] += 1
                    if not live:
                        continue
                    try:
                        counts[_persist_live(
                            store=store, reasoning_store=reasoning_store, org_id=org_id,
                            node_id=anchor, package=package, execution=execution,
                            eval_time=eval_time, pack=pack)] += 1
                    except Exception:
                        counts["persist_error"] += 1
                        logger.exception("domain-compiler live: persist %s failed",
                                         row["situation_id"])
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
