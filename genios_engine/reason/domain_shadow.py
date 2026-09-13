"""Layer 3 Domain Expertise compiler — shadow pass over live Layer 2 situations.

This is the design's mandated first activation step: compile the real, already-qualified L2
situations into ``ExpertisePackage``s on live traffic and MEASURE route hits, coverage and misses
— WITHOUT persisting anything and WITHOUT feeding Layer 4. It never changes a decision, so it is
safe to run in the normal sweep for any tenant switched on in ``l1_semantic_activation`` — the
per-tenant row ``reason/runner.run_all`` now enters this pass through (``l1_seam_enabled``), rather
than the global ``use_domain_compiler`` that gated it while it was set in no environment. Driving L4 from the
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
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore
from genios_engine.context.importance import read_l1_scoring_live
from genios_engine.context.quality.lens import read_coverage_lens
from genios_engine.context.quality.missing import read_absences
from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_brain_subject_keys,
    gather_evidence_and_signals,
    gather_l1_signals_bulk,
    gather_members,
    gather_pattern_fires,
    gather_visibility,
    stored_importance,
)
from genios_engine.context.situation_publisher import publish_situation
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
from genios_engine.platform.l4_activation import (
    CROSS_LAYER_EFFECTS,
    FEATURE_BUNDLE,
    FEATURE_RANKING_V2,
    FEATURE_ROSTER_V2,
    is_l4_activated,
    missing_cross_layer_preconditions,
)
from genios_engine.platform.ids import new_id
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.interpretation import make_interpreter
from genios_engine.reason.adapters.situation_projection import project_situation
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.store import ReasoningStore

logger = logging.getLogger(__name__)

# One tenant-scoped read of the active situations, with the correlation id (for evidence) and the
# anchor node type (for context loading) that active_situations() does not itself return.
_ACTIVE_SITUATIONS = (
    "select s.situation_id, s.situation_type, s.domain, s.status, s.correlation_id, "
    "       s.confidence_overall, s.coverage, s.missing, s.first_seen_at, s.last_seen_at, "
    # L2.7.8 · THE OTHER FIVE CONFIDENCE AXES, and who closed the situation. Selected because the
    # BSO carries the VECTOR now, not the minimum alone (doc 09's "must not regress" row 3: the
    # confidence vector is never collapsed to a scalar). Reading only `confidence_overall` here
    # meant `situation_bso.situation_confidence_vector` could report five of the six axes as
    # unassessed on the one path that actually publishes — a vector that passes its own gate
    # structurally while saying nothing. Columns only; the WHERE clause is untouched.
    "       s.confidence_evidence, s.confidence_freshness, s.confidence_consistency, "
    "       s.confidence_identity, s.confidence_analytic, s.resolved_by, "
    # BLG-18's stored composition. SELECTED, not recomputed: `refresh_situations` ran steps 2..6
    # once for the whole org and stored the arithmetic, and re-deriving it here would be five
    # reads per situation for a number that is already on the row being read.
    "       s.importance_bp, s.importance_components, "
    "       s.anchor_node_id, n.display_name as anchor_name, n.node_type as anchor_type "
    "from context_situations s "
    "left join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id "
    "     and n.valid_to is null "
    "where s.org_id = :o and s.status in ('active', 'partial') "
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


def _rejected_candidates(decision, selected) -> list[dict]:
    """The losing candidates, each with the authored doctrine that removed it.

    `eliminated_by` is read off `decision.constraints_applied`, which the contract has already
    checked: a rule may only name a candidate that IS eliminated on this decision, and the quote
    it carries has already been proven byte-identical to the authored artifact. So the card layer
    renders an expert rule verbatim without ever opening the corpus, and this function cannot
    invent an attribution of its own.
    """
    by_candidate: dict[str, list[dict]] = {}
    for applied in decision.constraints_applied or ():
        for candidate_id in applied.get("eliminated_candidate_ids") or ():
            by_candidate.setdefault(str(candidate_id), []).append({
                "rule_id": applied["rule_id"],
                "severity": applied["severity"],
                "statement": applied.get("statement"),
            })
    selected_play = getattr(selected, "play_id", None)
    return [{"play_id": candidate.play_id,
             "disposition": candidate.disposition.value,
             "utility_bp": candidate.utility_bp,
             "eliminated_by": by_candidate.get(str(candidate.candidate_id), [])}
            for candidate in decision.candidates
            if candidate.play_id != selected_play]


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
        "capability_id, capability_version, capability_review_state, rejected_candidates, "
        "citations) "
        "values (:id,:o,:pack,:packv,:r,:rv,:lv,:n,:s,cast(:si as jsonb),:rc,cast(:ev as jsonb),"
        ":play,:et,:cfg,:run,:cand,:dhash,:exp,1,:rev,:dnc,cast(:unc as jsonb),:owd,"
        ":cap,:capv,:caprev,cast(:rej as jsonb),cast(:cit as jsonb)) "
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
            # WHAT WAS CONSIDERED AND REJECTED, which the compiled lane has never written. The
            # legacy runner has filled this column since migration 0070 and the API renders it as
            # `alternatives_rejected`; a compiled card's "why not X?" therefore came back empty
            # however completely Layer 3's doctrine had answered it. Each rejected candidate now
            # carries the corpus rules that eliminated it, quoted — which is the J1 row "a
            # blocking rule eliminating a candidate, NAMED in alternatives_rejected".
            "rej": json.dumps(_rejected_candidates(decision, selected)),
            # THE EXPERT'S OWN WORDS, one hop further than they used to travel. CLG-08 quoted
            # these at the weld and the contract re-checked every `statement_hash` against the
            # statement again at the decision, so what lands here is provably the authored text —
            # but `ReasoningDecision.citations` was an in-memory field with no writer, and a claim
            # that reaches no row reaches no card. That made J5's headline measurement ("a card
            # carrying a heuristic/rule citation") structurally unreachable rather than merely
            # unmet: no tenant and no seven days would ever have produced one. The rule half has
            # landed since `rejected_candidates`; this is the claim half, same shape, same writer.
            #
            # NULL rather than `[]` when there are none, so "this decision quoted nothing" and
            # "this lane does not quote" stay different answers in the column.
            "cit": (json.dumps([dict(c) for c in decision.citations])
                    if decision.citations else None),
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


#: Layer 2 names a situation's domain in its OWN vocabulary (`context/domain_spec.py`), and
#: `platform/l3_activation.L3_DOMAINS` names the three authored corpora. They agree on two words
#: out of five and disagree on the third, so the translation is written down once, here, rather
#: than being a string comparison that silently never matches.
#:
#: `fundraising` and `general` map to NOTHING and that is not an oversight: no corpus was authored
#: for them, so there is no domain an operator could activate, and mapping them onto `admin` to
#: "get some coverage" would put Admin doctrine on a fundraising situation.
_L2_TO_L3_DOMAIN = {"admin": "admin", "sales": "sales", "support": "customer_support",
                    "customer_support": "customer_support"}


def l3_domain_for(l2_domain: Any) -> str | None:
    """The activatable corpus for one L2 domain, or None when no corpus claims it."""
    return _L2_TO_L3_DOMAIN.get(str(l2_domain or "").strip().lower())


def shadow_compile(*, store: GraphStore, org_id: str, eval_time: datetime | None = None,
                   limit: int = 200, live: bool = False, registry=None,
                   live_domains: frozenset[str] | Iterable[str] = ()) -> dict:
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

    ``live_domains`` is the row-driven half of the same switch, and it is the one that actually
    turns Layer 3 on for a customer. ``live=True`` is the GLOBAL flag — one boolean,
    ``platform/config.use_domain_compiler``, set in no environment, which moves every tenant at
    once or nobody. ``live_domains`` is ``platform/l3_activation.activated_domains(engine, org)``:
    a set of corpus names a person switched on for THIS tenant, which is what makes "Admin on,
    Sales off" expressible at all.

    **THIS IS THE DEFECT THE ACTIVATION TABLE SHIPPED WITH.** `l3_activation` landed with a reader,
    a fail-closed gate, an erasure row, an admin API and a J5 report — and no caller. `runner.py`
    still read `get_settings().use_domain_compiler` and nothing else, so an operator could POST an
    activation, see it in the console, read `EFFECTS` telling them the compiler's live pass now
    compiles that corpus, and get a shadow pass: no package published, no signal emitted, no card.
    A switch that reports itself as on and changes nothing is worse than no switch, because the
    next person debugging it starts from the belief that Layer 3 was tried.

    The two are OR-ed PER SITUATION, never globally: a tenant with `admin` activated runs its Admin
    situations live and its Sales situations in shadow, in the same sweep, from the same read.
    """
    eval_time = eval_time or datetime.now(timezone.utc)
    live_domains = frozenset(str(d) for d in (live_domains or ()))
    # ANY live lane at all — the global flag, or at least one activated corpus. Everything that
    # only a live compile needs (a tenant pack registry, a reasoning store, an admission-gated
    # compiler with a publisher) is built when this is true and never otherwise, so a tenant with
    # no activation row pays exactly what it paid before.
    any_live = bool(live or live_domains)
    # Local imports: the shadow pass depends on the runner's context loaders, and the runner
    # imports this module behind the flag — a module-level import would be a cycle.
    from copy import deepcopy

    from genios_engine.reason.runner import (
        _bulk_load_facts, _bulk_load_obs, _graph_version, _load_context, _neighbor_index,
        _neighborhood,
    )

    catalog = expert_catalog()
    graph_version = _graph_version(store, org_id)
    adj, _node_types, obs_idx, fact_idx = _neighbor_index(store, org_id)
    # Every anchor's facts and observations in TWO org-wide reads instead of two per situation
    # (up to 400 round trips per sweep). The bulk loaders use the per-node load's filters and
    # ordering (`runner._load_context` relies on the same equivalence), so each context is the
    # one the per-node read built. Copied per situation below: the bulk dicts are shared, and one
    # situation's context must never be able to see another's edits.
    facts_by_node = _bulk_load_facts(store, org_id)
    obs_by_node = _bulk_load_obs(store, org_id)
    counts: Counter = Counter()
    # `registry` is injectable for the same reason `run()` takes one: `make_registry()` resolves
    # its URL from global settings, so a caller holding a DIFFERENT store (a test on a scratch
    # Postgres, a one-off script against another tenant's database) would silently resolve the
    # tenant pack from the WRONG database and count every capability as `no_tenant_pack` — the
    # exact symptom this pass exists to remove, arriving from the harness instead of the code.
    registry = (registry or make_registry()) if any_live else None
    reasoning_store = ReasoningStore(engine=store.engine) if any_live else None
    # WAVE Z1 · the staged roster, per tenant, read ONCE for the pass rather than per situation:
    # a switch that flipped halfway through a sweep would make two situations in one pass
    # incomparable. Fail-closed by construction (`platform/l4_activation`), so a tenant that is
    # not switched on — or a database that cannot answer — reasons through exactly the six-unit
    # DAG it reasons through today.
    roster_v2 = is_l4_activated(store.engine, org_id, FEATURE_ROSTER_V2)
    counts["roster_v2"] = int(roster_v2)
    # WAVE Z3 · the six-weight utility model, read once for the pass for the reason above and
    # fail-closed for the reason above. Independent of `roster_v2` at this seam even though
    # `l4_activation.PRECONDITIONS` orders the two waves: the precondition is reported at the
    # activation console, and a gate that silently ignored an operator's switch because a
    # different switch was off would be harder to diagnose than the ordering it enforced.
    ranking_v2 = is_l4_activated(store.engine, org_id, FEATURE_RANKING_V2)
    counts["ranking_v2"] = int(ranking_v2)
    # WAVE Z4 · R-1, the ambiguity interpreter. Built once per pass for the reason the two switches
    # above are read once, and only on the LIVE lane: a shadow pass exists to measure what the
    # deterministic half does, and buying interpretations for a decision nobody will ever see is the
    # "just in case" spend doc 11 guard 7 forbids. Gated on `bundle` — the narrative spend is one
    # opt-in per tenant (doc 01 C5 step 1), not four switches an operator has to keep consistent.
    #
    # The interpreter itself is inert on a tenant with nothing ambiguous to read: `find_ambiguities`
    # is a pure read of the snapshot, and a situation with no hedged claim on a field the plan reads
    # costs nothing at all.
    # WAVE ORDER, ACROSS LAYERS, MADE VISIBLE WHERE THE WORK HAPPENS. Reported and NOT enforced,
    # on the same argument the two reads above make for ignoring `PRECONDITIONS`: a gate that
    # silently ignored an operator's switch because a different switch was off is harder to
    # diagnose than the ordering it enforced. What was missing was not enforcement — it was the
    # REPORT. `ranking_v2` on a tenant whose Layer 1 has never been activated is the six-weight
    # model permanently reweighing five, and the console said only `live`. Now the sweep says so
    # too, in its own counts, once per pass.
    for _feature, _flag in ((FEATURE_ROSTER_V2, roster_v2), (FEATURE_RANKING_V2, ranking_v2)):
        if not _flag:
            continue
        _unmet = missing_cross_layer_preconditions(store.engine, org_id, _feature)
        counts[f"{_feature}_cross_layer_unmet"] = len(_unmet)
        if _unmet:
            logger.warning(
                "Layer 4 %s is LIVE for org=%s while its cross-layer preconditions are unmet: %s "
                "— the feature runs, and these are the reasons it cannot do what its EFFECTS say: "
                "%s", _feature, org_id, ", ".join(_unmet),
                " | ".join(CROSS_LAYER_EFFECTS[item] for item in _unmet))

    interpreter = None
    if any_live and is_l4_activated(store.engine, org_id, FEATURE_BUNDLE):
        interpreter = make_interpreter(org_id=org_id, engine=store.engine,
                                       record_cost=store.record_cost)
    counts["r1_interpreter"] = int(interpreter is not None)
    packs: dict[str, dict | None] = {}      # capability domain -> the tenant's active pack lane

    # READS only on this connection, in both modes. Every live write (package, audit bundle,
    # signal) opens its own transaction per situation, so one unroutable row can never abort the
    # rest of the pass.
    with store.engine.connect() as conn:
        situations = conn.execute(text(_ACTIVE_SITUATIONS),
                                  {"o": org_id, "lim": limit}).mappings().all()
        l1_by_correlation = gather_l1_signals_bulk(
            conn, org_id,
            [str(row["correlation_id"]) for row in situations if row["correlation_id"]])
        # THE RECEIPTS AN ABSENCE SITUATION ALREADY HAS, fetched here because this is the path
        # that decides publication and it never fetched them.
        #
        # `backfill_absence_l1` was called from ONE place — `compose_org_importance`, the
        # importance sweep — so on the publish path `l1` stayed `None` for every situation that
        # claims a silence, and `_preflight` raised `qes_required` AND
        # `verified_evidence_required` on all of them. Measured read-only on the pilot: 504 held
        # against 28 admitted, and 480 of those holds carry exactly that pair. Both are
        # downstream of the same `None`.
        #
        # ADDITIVE ONLY. A correlation the bulk read already answered is never touched, and a
        # situation with no receipt behind it keeps its `None` and stays held — which is correct.
        # What stops happening is refusing claims whose receipts nobody fetched.
        #
        # Never fatal: this is a refinement of the evidence, and a sweep that could not fetch it
        # publishes exactly what it published before.
        try:
            from genios_engine.context.situation_bso import backfill_absence_l1
            l1_by_correlation = backfill_absence_l1(
                conn, org_id, situations, l1_by_correlation)
        except Exception:      # noqa: BLE001 — evidence refinement, retried next sweep
            logger.exception("absence receipt backfill failed for org=%s", org_id)
        # L2.5.8 · IS LAYER 1's SCORER LIVE FOR THIS TENANT AT ALL? Measured ONCE for the sweep,
        # TENANT-SCOPED, with one `select exists` against `qualified_signals`.
        #
        # THIS USED TO FOLD THE SWEEP'S OWN SLICE — `any(l1.importance_bp is not None for l1 in
        # l1_by_correlation.values())` — over at most `limit` (default 500) situations, while its
        # comment claimed the result was "a property of the tenant's supply, never of one
        # situation". It was neither: a tenant whose Layer 1 IS scoring, whose sweep window
        # happened to hold only unscored situations, got the relaxed gate for that batch and its
        # candidates were admitted carrying `ImportanceBasis.UNSCORED` rather than held for a
        # retry that would have worked. Worse, on an EMPTY slice it answered False while
        # `context/importance.assess_l1_supply` answered True for the same tenant on the same
        # sweep — one question, two modules, opposite answers.
        #
        # `read_l1_scoring_live` is now the single tenant-scoped answer and fails STRICT (see its
        # docstring); `assess_l1_supply` keeps the flatness question it was always actually
        # answering, on the sample it was always actually folding.
        #
        # It conditions ONE hold reason (`qes_required`) and nothing else. On a tenant Layer 1 IS
        # scoring, a situation that carries no score is a real, retryable gap and the gate holds
        # it. On a tenant Layer 1 has never scored, the same absence is structural: no sweep will
        # ever repair it, so holding costs that tenant its whole L3/L4 lane in exchange for
        # nothing. The candidate is admitted carrying `ImportanceBasis.UNSCORED`, and doc 04's
        # honesty guard (`decision_maker.IMPORTANCE_ABSENT_REASON`) reweighs the remaining five
        # components and names why on every decision. See `situation_publisher.decide_publication`.
        l1_scoring_active = read_l1_scoring_live(conn, org_id)
        counts["l1_scoring_active"] = int(l1_scoring_active)
        # The sweep's own reading, kept BESIDE the tenant fact rather than instead of it: the two
        # disagreeing is the interesting case ("Layer 1 scores here, but nothing in this window
        # carries a score") and it is exactly what the old fold silently collapsed.
        counts["l1_scored_in_sweep"] = int(any(l1.importance_bp is not None
                                               for l1 in l1_by_correlation.values()))
        # L2.5.5 · the typed absences the drain wrote, for the WHOLE pass, in one read — the
        # same shape as every other gather here, and for the same reason: there are as many
        # absence rows as there are expected fields across the tenant's situations, and a
        # per-situation query would be one round trip per situation to answer a question the
        # table can answer once. Grouped by situation so the slice builder is a dict lookup.
        #
        # WHY THIS IS ON THIS PATH. `{absent: thread.last_inbound}` — "they never replied" —
        # evaluated TRUE for every situation of an org with no mailbox connected, because the
        # only thing the adapter could ask was whether the fact was in the slice. These rows are
        # what let it ask the second question instead. `coverage_ready` per domain comes off the
        # same lens, tri-state, so an unassessed domain withdraws nothing.
        absences_by_situation: dict[str, list] = {}
        coverage_lens = None
        try:
            coverage_lens = read_coverage_lens(conn, org_id)
            for absence in read_absences(
                    conn, org_id,
                    situation_ids=[str(r["situation_id"]) for r in situations],
                    current={d: e for d, e in coverage_lens.epochs.items()}):
                absences_by_situation.setdefault(absence.situation_id, []).append(absence)
        except Exception:      # noqa: BLE001 — absence typing is a refinement; the pass is the product
            logger.exception("could not read typed absences for org=%s", org_id)
        # L2.6 · which declared pattern matched each anchor, for the WHOLE pass, in one read.
        # SHADOW BY DEFAULT: `pattern_fires.activated` is false until a tenant activates the
        # pattern, and `situation_bso._situation_type` refuses to rename a situation on an
        # unactivated fire — `context/patterns/store.py`'s stated migration rule ("compare fire
        # sets on a pilot for 7 days before switching; do not delete the anchor path in this
        # wave"). What the fire always carries is its per-condition evidence, which is what makes
        # that comparison possible and is H8's third bold row.
        #
        # Wrapped like the absence read above and for the same reason: pattern matching is a
        # refinement of a pass whose product is the package, and a failure to read one must not
        # cost the tenant every situation.
        pattern_fires: dict = {}
        try:
            pattern_fires = gather_pattern_fires(
                conn, org_id, [str(r["anchor_node_id"]) for r in situations
                               if r["anchor_node_id"]])
        except Exception:      # noqa: BLE001 — the package is the product; the pattern is context
            logger.exception("could not read pattern fires for org=%s", org_id)
        # L2.3 · CROSS DOMAIN. Which situations are contradicted by another domain's situation
        # about the same subject, read ONCE for the sweep beside every other bulk gather above.
        #
        # `correlation_domain` returns findings and deletes nothing; the decision is
        # `situation_publisher._preflight`'s, which HOLDS a contradicted candidate exactly as it
        # holds one carrying Layer 1 `conflict_ids`. Measured on the pilot: three counterparties
        # were simultaneously "they owe us a reply" (admin) and "we never answered them"
        # (support), and both cards would have gone out saying opposite things about one person.
        #
        # NEVER FATAL, and the same reason the pattern read above is not: a correlator is a
        # refinement of a pass whose product is the package. A failure to read one must not cost
        # the tenant every situation — it costs only the contradiction guard for this sweep, and
        # the next sweep reads it again.
        contradicted: dict[str, list[str]] = {}
        try:
            from genios_engine.context.correlation_domain import read_contradictions

            for finding in read_contradictions(conn, org_id):
                # BOTH SIDES when nothing settles it, the LOSER alone when something does. An
                # unresolved contradiction is not a reason to trust either claim, and picking one
                # by coin toss is worse than telling a reviewer the system cannot tell.
                blocked = ([sid for _key, sid in finding.sides] if not finding.resolved
                           else [sid for key, sid in finding.sides if key == finding.loser])
                for situation_id in blocked:
                    contradicted.setdefault(situation_id, []).append(
                        f"{finding.exclusion.left}|{finding.exclusion.right}")
        except Exception:      # noqa: BLE001 — a correlator is context, not the product
            logger.exception("could not read cross-domain contradictions for org=%s", org_id)
        counts["contradicted_situations"] = len(contradicted)
        brains = PostgresRuntimeBrains(conn)
        # TWO COMPILERS, ONE CONNECTION, chosen PER SITUATION by the situation's own domain.
        #
        # The three things that separate a live compile from a measurement — a publisher, the
        # fail-closed admission gate, and (below) LIVE execution with an emitted signal — are set
        # at construction, so a single compiler cannot serve a tenant that has Admin activated and
        # Sales not. Building both is cheap: they share the catalog and the same runtime-brain
        # reader on the same connection, and the shadow one is what every unactivated situation
        # already used.
        compiler_measure = DomainCompiler(
            catalog=catalog,
            runtime_brains=brains,
            # shadow: never write an expertise_packages row.
            publisher=None,
            # MEASUREMENT mode: draft content may compile so route coverage is measurable, but
            # the package carries review_state='draft' and the delivery abstention gate keeps
            # anything built from it non-prescriptive.
            require_admission=False,
        )
        compiler_live = DomainCompiler(
            catalog=catalog,
            runtime_brains=brains,
            # live: write the package, or the compiled brain has no durable authority for
            # delivery to read back.
            publisher=_TxnExpertisePublisher(store.engine),
            # Authority compiles use the fail-closed default — a text-editor stub flip can no
            # longer grant production authority.
            require_admission=True,
            # ...AND THE SAME FOR THE CORPUS IT COMPILES FROM. The comment above says a single
            # compiler cannot serve a tenant that has Admin activated and Sales not, and that was
            # true of the publisher and the admission gate but not of the capability route: with
            # no domain hint the resolver considered every authored domain, and with hints it
            # took them whole. On the pilot — only `admin` activated — `relationship` situations
            # routed to ["admin", "customer_support", "sales"], and the four capabilities in the
            # most packages were all `customer_support`, followed by eight
            # `sales.post_sale_and_growth.*` on a founder's fundraising inbox. That is also where
            # Layer 4's ballot came from: 270 of 512 candidates were sales plays, because L4's
            # plays come from the capabilities compiled here.
            #
            # The MEASUREMENT compiler above stays unfiltered on purpose. Its whole job is to
            # report what a tenant WOULD get from corpora it has not switched on, and filtering
            # it would make route coverage unmeasurable for exactly the domains an operator is
            # deciding whether to activate.
            activated_domains=live_domains,
        ) if any_live else None
        counts["l3_activated_domains"] = len(live_domains)
        # THE VARIANT DECLARATION, read once per sweep per live domain — the same shape and
        # source as `live_domains` itself. `()` for every domain that declared nothing.
        from genios_engine.platform.l3_activation import declared_variants
        variants_by_domain = {d: declared_variants(store.engine, org_id, d) for d in live_domains}
        for row in situations:
            counts["situations"] += 1
            # WHICH LANE THIS SITUATION IS ON. The global flag still forces live for a deployment
            # that has already set it — its behaviour is unchanged — and otherwise the answer is
            # the tenant's activation row for THIS situation's corpus. A domain with no corpus
            # (`fundraising`, `general`) resolves to None and can never be live, which is the
            # fail-closed direction: an unactivatable domain compiles and measures exactly as it
            # does today.
            row_domain = l3_domain_for(row["domain"])
            live_row = bool(live or (row_domain is not None and row_domain in live_domains))
            counts["live_situations" if live_row else "shadow_situations"] += 1
            if row_domain is None:
                # UNACTIVATABLE, AND SILENT UNTIL NOW. A situation whose L2 domain no corpus
                # claims compiles in measurement mode, publishes no package and emits no signal —
                # on EVERY tenant configuration, including one with every corpus switched on.
                # There was no count for it, so "shadow_situations" absorbed it alongside rows a
                # tenant could switch on tomorrow, and the two are not the same fact.
                #
                # It is not a small set. `general:relationship` is the most-authored type in the
                # corpus (15 situations across the three domains) and the largest on the pilot
                # (55 rows); `fundraising:investor_relationship` and `investor_contact` are the
                # other two. Everything they compile is measurement, forever.
                #
                # THE MAP IS NOT THE DEFECT. Pointing `general` at `admin` "to get some coverage"
                # would put Admin doctrine on a general situation, which is worse than silence.
                # The two honest routes are to author a `general` corpus, or to decide that
                # activation should govern the corpus that SERVES a situation rather than the
                # domain that produced it — a cutover decision, not a bug fix. This counts the
                # cost so the decision can be made against a number.
                counts["unactivatable_domain"] = counts.get("unactivatable_domain", 0) + 1
            compiler = compiler_live if (live_row and compiler_live is not None) \
                else compiler_measure
            anchor = row["anchor_node_id"]
            if not anchor:
                counts["no_anchor"] += 1
                continue
            try:
                node_ctx = _load_context(store, org_id, anchor, row["anchor_type"],
                                         facts_by_node=facts_by_node, obs_by_node=obs_by_node)
                node_ctx = replace(node_ctx, facts=deepcopy(node_ctx.facts),
                                   obs=[dict(o) for o in node_ctx.obs])
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
                # WHAT LAYER 1 PUBLISHED about these same events. Read on the same connection as
                # every other gather, and handed to the builder rather than re-derived: the score,
                # the receipts and the conflict pointers are Layer 1's decisions, and this pass
                # used to stamp a constant over all three. `None` here (a tenant with no qualified
                # signals yet) is the pre-activation path, unchanged.
                l1 = l1_by_correlation.get(str(row["correlation_id"]))
                # STEPS 2..6, read back off the row. `None` for a tenant whose sweep predates the
                # composer — the BSO then carries Layer 1's base alone, which is exactly what this
                # pass published before BLG-18 and is still correct.
                composed = stored_importance(row)
                trace_id = new_id("trace")
                candidate = build_business_situation(
                    org_id=org_id, situation=row,
                    signal_ids=signal_ids, evidence=evidence, trace_id=trace_id,
                    members=members, visibility=situation_visibility, l1=l1,
                    composed=composed, pattern=pattern_fires.get(str(anchor)),
                    # THE BRAIN ADDRESS, resolved on the same connection as every other gather
                    # above and for the same reason. This is the writer
                    # `packs/compiler/runtime_brains._selectors` has read for and never had: it
                    # turns the situation's email-keyed members into the graph node ids the
                    # Behaviour brain publishes under, so the tenant's own learned knowledge can
                    # finally be selected for the situation it is about.
                    brain_subject_keys=gather_brain_subject_keys(conn, org_id, row, members),
                    # Empty for all but the contradicted few, which is the behaviour this pass had
                    # before the correlator existed.
                    contradicted_by=tuple(contradicted.get(str(row["situation_id"]), ())),
                    # Which authored business-model overlay this situation's domain runs under.
                    # Empty for every tenant that has declared nothing — the key is then absent
                    # from the situation's metadata and nothing re-mints.
                    variant_ids=variants_by_domain.get(str(row.get("domain") or ""), ()))
                current_absences = tuple(
                    absence.fact
                    for absence in absences_by_situation.get(str(row["situation_id"]), ())
                    if not (absence.fact.is_finding and absence.stale_coverage)
                )
                publication = publish_situation(
                    store.engine, candidate, decided_at=eval_time,
                    missing_facts=current_absences,
                    l1_scoring_active=l1_scoring_active,
                    # THE RECEIPT IS THE LIVE PUBLISHER'S, NOT THE MEASUREMENT'S. `record=True`
                    # unconditionally made this pass INSERT into `situation_admission_decisions`,
                    # and a shadow pass persists nothing by definition -- everything else on this
                    # branch is gated on `live`. Two costs, both real: a measurement rewrote the
                    # durable ledger of what the live lane had decided, and
                    # `scripts/unit_reachability_report.py` -- the K1a gate command, read-only AT
                    # THE SERVER on purpose -- raised `ReadOnlySqlTransaction` on the first
                    # situation. `shadow_compile` catches per situation, so the gate did not
                    # crash: it reported `reasoned=0`, "units emitting findings: 0" and
                    # UNRECEIPTED SILENCE for all twenty units, and declared K1a FAIL on a tenant
                    # whose roster was in fact fully awake.
                    record=live_row)
                counts[f"admission_{publication.outcome.value}"] += 1
                if not publication.admitted or publication.situation is None:
                    # HOLD/REJECT is the output.  Nothing above Layer 2 receives a weak object;
                    # the durable ledger says exactly what the next sweep may repair.
                    continue
                bso = publication.situation
                context_slice = build_context_slice(
                    visibility=situation_visibility,
                    org_id=org_id, situation=row, facts=node_ctx.facts,
                    observations=node_ctx.obs,
                    neighbor=neighbor, graph_version=graph_version,
                    eval_time=eval_time, trace_id=trace_id,
                    absences=tuple(absences_by_situation.get(str(row["situation_id"]), ())),
                    coverage_ready=(coverage_lens.ready_for(row["domain"])
                                    if coverage_lens is not None else None))
                package = compiler.compile(bso, context_slice)
                counts["compiled"] += 1
                counts["capabilities_total"] += len(package.capabilities)
                # L3 -> L4 weld: adapt the package into a CapabilityManifest and reason over it.
                # SHADOW mode + live_delivery_enabled=False on the manifest -> a decision is
                # produced and measured but never delivered or persisted as a signal.
                try:
                    # WAVE Z5 · DLG-06. Layer 2's own readings, in snapshot shape, built ONCE
                    # and handed to both consumers: the manifest DECLARES the projected fields
                    # and the snapshot SUPPLIES them, so two derivations would be two chances to
                    # disagree. Gated on `roster_v2` because the six-unit DAG declares no
                    # projected fact — injecting facts nothing reads would move an unactivated
                    # tenant's context snapshot id, and therefore its decision hashes, for
                    # nothing.
                    projection = (project_situation(
                        situation=bso, context=context_slice, root_entity_id=node_ctx.node_id)
                        if roster_v2 else None)
                    if projection is not None:
                        counts["projected_situation_facts"] += len(projection.facts)
                        counts["projected_unknown_fields"] += len(projection.unknown_fields)
                    manifest = expertise_capability_manifest(
                        package, root_entity_type=node_ctx.node_type,
                        # The delivery authority predicate reads this flag off the persisted
                        # capability snapshot. False (the measurement default) means no card can
                        # ever be built from the decision, however complete its audit bundle is.
                        live_delivery_enabled=live_row,
                        # WHAT THE CORPUS'S RULES BIND AGAINST (CLG-06). The package carries the
                        # knowledge that was selected; only these two carry the facts it was
                        # selected FOR, and only the frozen slice knows which absences are
                        # UNKNOWABLE — the difference between a blocking rule firing and a
                        # blocking rule honestly abstaining. Both are already in scope here, and
                        # passing them is what makes the weld bound rather than declared.
                        situation=bso, context=context_slice,
                        # The full family, or the six-unit DAG. Never a global flag: the roster
                        # changes which units observe a tenant's data, and that is a per-tenant
                        # decision an operator makes and can undo.
                        roster_v2=roster_v2,
                        # WAVE Z3 · importance becomes the sixth utility component and the
                        # authored corpus priority stops replacing the formula.
                        ranking_v2=ranking_v2,
                        # WAVE Z5 · the same object the snapshot below is built from.
                        projection=projection)
                    pack = None
                    if live_row:
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
                        mode=ExecutionMode.LIVE if live_row else ExecutionMode.SHADOW,
                        projection=projection,
                        # R-1. None on the shadow lane and on any tenant without `bundle`, and
                        # `augment` returns the SAME request when it reads nothing — so a run with
                        # no interpretation hashes to exactly what it hashed to before this seam.
                        interpreter=interpreter)
                    counts["reasoned"] += 1
                    if execution.decision is None:
                        continue
                    counts["decided"] += 1
                    if not live_row:
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
            finally:
                # ONE connection serves the whole loop, and SQLAlchemy opens an implicit
                # transaction on it at first use. A statement that raises leaves that transaction
                # invalid, and every later statement on the same connection then fails with
                # PendingRollbackError — so a single bad situation silently takes every situation
                # after it. Measured on the design partner's org: one persist_error was followed by
                # five cascade failures, and `compiled` came back 50 against the measurement pass's
                # 56. The six missing situations were not unroutable; they were never attempted.
                #
                # This is the same failure the per-situation transaction fixed for WRITES
                # (obstacle 1 in NEW_BRAIN_CUTOVER), reappearing on the READ connection, where the
                # comment above asserts "READS only" and reads alone are enough to poison it.
                #
                # rollback() on a healthy connection is a no-op, so this is unconditional rather
                # than guarded on a flag we would have to keep correct.
                conn.rollback()

    result = dict(counts)
    logger.info("domain-compiler %s org=%s domains=%s %s",
                "LIVE" if live else ("PILOT" if live_domains else "shadow"),
                org_id, sorted(live_domains) or "-", result)
    return result


__all__ = ["shadow_compile"]
