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

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore
from genios_engine.reason.unroutable import tally_unroutable


from genios_engine.context.importance import read_l1_scoring_live
from genios_engine.context.quality.lens import read_coverage_lens
from genios_engine.context.quality.missing import read_absences
from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_brain_subject_keys,
    gather_evidence_and_signals,
    gather_l1_signals_bulk,
    l1_refusal,
    gather_members,
    gather_pattern_fires,
    gather_visibility,
    stored_importance,
)
from genios_engine.context.situation_publisher import publish_situation
from genios_engine.contracts.reasoning import DecisionOutcome, ExecutionMode
from genios_engine.packs.compiler import DomainCompiler, PostgresRuntimeBrains
from genios_engine.packs.compiler.errors import (
    NoExpertiseRoute,
    RequiredKnowledgeMissing,
    SituationContextConflict,
    SituationContextIncomplete,
    UnsupportedCoverage,
)
from genios_engine.packs.compiler.expertise_publisher import PostgresExpertisePublisher
from genios_engine.packs.compiler.playbook_reader import KIND_CAPABILITY
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
from genios_engine.platform import card_lifecycle
from genios_engine.platform.ids import new_id
from genios_engine.platform.self_identity import identity_for
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import native_context_snapshot, reason_native_capability
from genios_engine.reason.interpretation import make_interpreter
from genios_engine.reason.adapters.situation_projection import project_situation
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.expert.cover import Covers, cover_of
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
            "rule_ids": {str(rule.get("id")) for rule in (effective.get("rules") or ())},
            # THE DAILY CAP, carried from the same effective config the legacy lane reads. The
            # budget is ORG-WIDE and not per pack — `runner._budget_used` counts every signal the
            # tenant published today whatever wrote it, and `packs/general_v1` says so in as many
            # words: "the daily signal budget is shared org-wide, so matching numbers keeps the
            # cap combined, not doubled". Whichever pack resolves first therefore sets it.
            "budget_per_day": int((effective.get("scoring") or {}).get("budget_per_user_day", 7))}


def _daily_allowance(store, org_id: str, eval_time, pack: Mapping[str, Any]) -> int:
    """How many more signals this tenant may publish today, across every lane.

    THE SAME SUBTRACTION THE OTHER THREE LANES MAKE, read from the same two helpers, so there is
    one cap rather than a second one hidden behind it: `budget_per_day * active_seats` minus
    everything already published today. `_budget_used` counts by DATE and by org, not by pack, so
    a legacy signal written an hour ago is already subtracted here.

    NEVER NEGATIVE, and never an exception. A tenant whose seats cannot be read, or whose used
    count cannot be, gets the pack's own per-day figure rather than zero — refusing to publish
    because a COUNT failed would turn a transient database hiccup into a silent day with no
    advice, which is a worse failure than one card over a soft cap.
    """
    from genios_engine.reason.runner import _active_seats, _budget_used

    per_day = int(pack.get("budget_per_day") or 7)
    try:
        cap = per_day * _active_seats(store, org_id)
        return max(0, cap - _budget_used(store, org_id, eval_time))
    except Exception:      # noqa: BLE001 — see NEVER NEGATIVE above
        logger.exception("domain-compiler: could not read the daily budget for org=%s", org_id)
        return per_day


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
                            eval_time, pack: dict, situation_id: str | None = None,
                            replace_unless_from: str | None = None,
                            same_advice: Callable[[str | None], bool] | None = None) -> str:
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

    ``replace_unless_from`` — STEP-12 M33: a covered file's decision (`reason/expert/decide`) is
    the review's, and the file holds ONE (M33.C1.L-integration.V2.U12, `03` F174). Its open decision
    is read whatever pack it was bound to — the file's home moves between domains from sweep to
    sweep, and a decision per pack was two cards for one file — and it STANDS while its window holds
    and it came from this same review (the run's ``trigger_ref``, the review's fingerprint) or from an
    earlier review that gave the same advice (``same_advice``, handed the standing run's fingerprint):
    the card's words did not change, so no card is torn down and rebuilt for them. Other advice
    replaces every open decision of the file, in every pack, its cards with it. Every other caller
    passes None: the authority window rules, as before.
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
    if replace_unless_from is None:
        standing = conn.execute(text(
            "select signal_id from signals where org_id=:o and pack_id=:p and pack_version=:pv "
            "and rule_id=:r and subject_node_id=:n and status='open' "
            "and authority_expires_at > :now limit 1"),
            {"o": org_id, "p": pack["pack_id"], "pv": pack["version"], "r": rule_id,
             "n": node_id, "now": eval_time}).first()
        if standing is not None:
            return "standing"
        # One OPEN compiled signal per (pack, rule, node), same discipline as the legacy `_emit`:
        # once the window has passed, the refreshed advice replaces the stale row rather than
        # colliding.
        retired = conn.execute(text(
            "update signals set status='expired' where org_id=:o and pack_id=:p and pack_version=:pv "
            "and rule_id=:r and subject_node_id=:n and status='open' returning signal_id"),
            {"o": org_id, "p": pack["pack_id"], "pv": pack["version"],
             "r": rule_id, "n": node_id}).fetchall()
    else:
        # STEP-12 M33 · THE FILE'S ONE DECISION, in whichever pack it stands (see the docstring).
        held = conn.execute(text(_FILE_DECISIONS),
                            {"o": org_id, "r": rule_id, "n": node_id}).fetchall()
        if any(row.authority_expires_at is not None and row.authority_expires_at > eval_time
               and (row.trigger_ref == replace_unless_from
                    or (same_advice is not None and same_advice(row.trigger_ref)))
               for row in held):
            return "standing"
        retired = conn.execute(text(_RETIRE_FILE_DECISIONS),
                               {"o": org_id, "r": rule_id, "n": node_id}).fetchall()
    if retired:
        # STEP-06: the refreshed advice replaces the stale signal — its cards say so.
        card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                    signal_ids=[item.signal_id for item in retired])
    row = conn.execute(text(
        "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, rule_version, "
        "level, subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
        "config_snapshot_id, reasoning_run_id, reasoning_candidate_id, reasoning_decision_hash, "
        "authority_expires_at, authority_binding_version, authority_pack_revision, "
        "do_nothing_consequence, uncertainty, outcome_window_days, "
        # ⛔ L2-S3 · migration 0189. The lane is what the card renders AS — a thing to do, to find out,
        # to rule on, to watch, or deliberately withheld. NULLABLE, and the NULL is an answer: a signal
        # written before routing existed was never routed, and a default lane would claim a decision
        # nobody made. Same rule `situation_id` above states for UNINTERPRETED.
        "output_lane, lane_reason, "
        "capability_id, capability_version, capability_review_state, rejected_candidates, "
        # ⛔ L2-7 · migration 0182. NULLABLE, and the NULL is an answer: a signal whose situation
        # never formed still reaches the founder, labelled UNINTERPRETED by
        # `deliver/card_source.classify`. Fewer cards must come from merging, never from dropping.
        "citations, situation_id) "
        "values (:id,:o,:pack,:packv,:r,:rv,:lv,:n,:s,cast(:si as jsonb),:rc,cast(:ev as jsonb),"
        ":play,:et,:cfg,:run,:cand,:dhash,:exp,1,:rev,:dnc,cast(:unc as jsonb),:owd,:lane,:lreason,"
        ":cap,:capv,:caprev,cast(:rej as jsonb),cast(:cit as jsonb),:sit) "
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
            # Carried, not re-derived. Re-routing here from the projected columns could disagree with
            # the audited decision — which is the same failure `score` and `reason_code` above are
            # commented against.
            "lane": (decision.output_lane.value if decision.output_lane is not None else None),
            "lreason": decision.lane_reason,
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
            # NULL rather than "" for the same reason `cit` is: "no situation formed" and "this
            # caller did not say" must not become the same row. `classify` reads both as
            # UNINTERPRETED today, and a later reader that wants to tell them apart still can.
            "sit": (str(situation_id).strip() or None) if situation_id else None,
        }).first()
    return "emitted" if row is not None else "race_lost"


def _persist_live(*, store: GraphStore, reasoning_store: ReasoningStore, org_id: str,
                  node_id: str, package, execution, eval_time, pack: dict,
                  situation_id: str | None = None, replace_unless_from: str | None = None,
                  same_advice: Callable[[str | None], bool] | None = None,
                  bundle_out: dict | None = None) -> str:
    """Commit the audit bundle, then the signal built from it. Two transactions, in that order.

    The audit bundle FIRST and through ``persist_execution``, never by hand: ``signals`` carries six
    FKs into the reasoning audit tables (run, candidate, decision, config, and the run/config pair),
    so a hand-made run id fails all of them (obstacle 5). Only once those rows exist can a signal
    legally point at them.
    """
    bundle = persist_execution(store=reasoning_store, execution=execution)
    if bundle_out is not None:
        bundle_out.update(bundle)               # the audited run, for what the caller files beside it
    with store.engine.begin() as conn:
        return _emit_capability_signal(
            conn, org_id=org_id, node_id=node_id, package=package, execution=execution,
            bundle=bundle, eval_time=eval_time, pack=pack, situation_id=situation_id,
            replace_unless_from=replace_unless_from, same_advice=same_advice)


# =================================================================================================
# STEP-12 M33 · A COVERED FILE DECIDES ONCE (tree `yc2_w27_s12` M33.C1.L-integration.V1.U02, `06` D1)
#
# The expert pass (`reason/expert/sweep`) says which files a VALID review now answers — `covered`,
# file → the review's fingerprint. Each such file is decided ONCE, from that review
# (`reason/expert/decide`): its mode the outcome, its next move the play, code's confidence, the
# appraisal's urgency and importance — an ordinary audited Layer 4 run, persisted and emitted
# exactly as a situation's is, its anchor the subject. No decider and no R-1 are asked for it, and
# none for any situation of the file the review EXPLAINS: those stand down, their end recorded
# (`decided`, `covered_by_review`), and a signal one of them left open is replaced by the file's.
#
# EXPLAINS, MEASURED, NOT ASSUMED (STEP-12 §8.7: "one review per file must not erase a situation the
# file does not explain"). A situation stands down when every event behind it was in the file the
# review judged — the events the stored review's fingerprint inputs name (`expert_reviews.inputs`,
# 0198). A situation resting on an event the review never saw — a private one, one the file does not
# hold, one from after a review that still stands because nothing material moved — keeps its own
# decision on today's path. WHICH FILE'S review (M33.C1.L-integration.V2.U13, `03` F173) is
# `reason/expert/cover`'s rule, the one the pack rules read too: a situation anchored on the file or on
# one of its people is its own file's; one anchored on a node no one owns — the thread, the meeting's
# reading, the dependency the mail stated — any covered file's whose review saw it all. Anchored on the
# file alone, the review had left all of those to be decided beside it — a second card each, the
# decider asked for each.
# =================================================================================================

#: The end a covered situation is given: it was decided — by its file's review.
COVERED_BY_REVIEW = "covered_by_review"

#: STEP-12 M33.C1.L-integration.V1.U09, `03` F104 — every anchor's measured baselines, each with its n:
#: the file's numbers a corpus `{baseline: …}` threshold reads. A cold start is a default, never a
#: measurement, and is not read.
_ANCHOR_BASELINES = (
    "select key, value, sample_size from baselines "
    " where org_id = :o and not cold_start "
    "   and (key like 'write_interval:%' or key like 'contact_rate_per_account:%')")

#: Each baseline the corpus names, the level it is measured at and its unit.
_BASELINE_BASIS = {"write_interval": ("person", "days"), "contact_rate_per_account": ("company", "per week")}


def _measured_baselines(conn, org_id: str) -> dict[str, dict[str, Any]]:
    """{node: {baseline: Measured}} — read once a pass, handed to each situation's manifest by its
    anchor (`expertise_capability_manifest(baselines=…)`, which passes on only a normal). Fails open
    to none: a threshold that cannot be answered answers UNKNOWN, as it did before F104."""
    from genios_engine.contracts.measured import Measured

    out: dict[str, dict[str, Any]] = {}
    try:
        rows = conn.execute(text(_ANCHOR_BASELINES), {"o": org_id}).fetchall()
    except Exception:      # noqa: BLE001 — no numbers is the pass before F104, never a failed pass
        logger.exception("domain-compiler: the anchors' baselines could not be read org=%s", org_id)
        conn.rollback()
        return out
    for row in rows:
        metric, _, node = str(row.key).partition(":")
        basis, unit = _BASELINE_BASIS[metric]
        out.setdefault(node, {})[metric] = Measured(value=float(row.value), n=int(row.sample_size or 0),
                                                    basis=basis, unit=unit)
    return out

#: What `_emit_capability_signal` reads off a package: its review state. A covered file's decision
#: is the expert's VALIDATED review (`contracts/expert_review.validate`, D1) — prescriptive, as an
#: accepted corpus package's is.
_REVIEWED = SimpleNamespace(metadata={"review_state": "accepted"})

#: STEP-12 M33.C1.L-integration.V2.U12 · a file's open decisions, in every pack, each with its window
#: and the review its run was triggered by (an expert run's trigger is its review's fingerprint).
_FILE_DECISIONS = (
    "select s.signal_id, s.authority_expires_at, r.trigger_ref from signals s "
    "  left join reasoning_runs r on r.org_id = s.org_id and r.run_id = s.reasoning_run_id "
    " where s.org_id = :o and s.rule_id = :r and s.subject_node_id = :n and s.status = 'open' "
    " order by s.signal_id")

#: …replaced, in every pack, when the file's new decision gives other advice.
_RETIRE_FILE_DECISIONS = (
    "update signals set status = 'expired' where org_id = :o and rule_id = :r "
    "   and subject_node_id = :n and status = 'open' returning signal_id")

#: …and cleared when its new review names no move now — every open decision an EARLIER review made.
_CLEAR_FILE_DECISIONS = (
    "update signals s set status = 'expired' from reasoning_runs r "
    " where s.org_id = :o and s.rule_id = :r and s.subject_node_id = :n and s.status = 'open' "
    "   and r.org_id = s.org_id and r.run_id = s.reasoning_run_id "
    "   and r.trigger_ref is distinct from :fp returning s.signal_id")

#: The outcomes a review CHOOSES when it names no move now: wait or blocked (DEFER — a move held under
#: the confidence floor too), find out (INSUFFICIENT_CONTEXT), nothing (NO_ACTION). Never FAILED or
#: BLOCKED: those are ours (`reason/output_lane`), and our failure must not take the founder's card down.
_NO_MOVE = frozenset({DecisionOutcome.DEFER, DecisionOutcome.INSUFFICIENT_CONTEXT,
                      DecisionOutcome.NO_ACTION})

#: Each covered file's home: its anchor's type, and the situation its decision is filed under — an
#: active one first, then the latest. Its domain is the corpus, and so the tenant pack, it binds to.
#: A file with no situation anchored on it is filed under one of those it stood down
#: (`_STOOD_DOWN_HOME`, M33.C1.L-integration.V2.U13).
_FILES_HOME = (
    "select distinct on (s.anchor_node_id) s.anchor_node_id, s.situation_id, s.domain, n.node_type "
    "  from context_situations s join graph_nodes n on n.org_id = s.org_id "
    "       and n.node_id = s.anchor_node_id and n.valid_to is null "
    " where s.org_id = :o and s.anchor_node_id = any(:files) "
    " order by s.anchor_node_id, (s.status in ('active', 'partial')) desc, "
    "          s.last_seen_at desc nulls last, s.situation_id")

#: …or, anchored on none, one of the situations it stood down — on its people or a node no one owns.
_STOOD_DOWN_HOME = (
    "select n.node_id as anchor_node_id, s.situation_id, s.domain, n.node_type "
    "  from context_situations s join graph_nodes n on n.org_id = s.org_id and n.node_id = :f "
    "       and n.valid_to is null "
    " where s.org_id = :o and s.situation_id = any(:sids) "
    " order by (s.status in ('active', 'partial')) desc, s.last_seen_at desc nulls last, "
    "          s.situation_id limit 1")

#: The open signals a covered file's stood-down situations left — replaced by the file's decision,
#: whatever their subject: a stood-down situation may be anchored on one of the file's people or on a
#: node no one owns, and its signal on that node (U13).
_STOOD_DOWN_SIGNALS = (
    "update signals set status = 'expired' where org_id = :o and status = 'open' "
    # The file's own question (STEP-13) is the file's, filed under its home situation — never one of
    # the situation signals its decision replaces.
    "   and rule_id <> :r and rule_id <> 'founder_question' and situation_id = any(:sids) "
    "returning signal_id")


def _covered_reviews(conn, org_id: str, covered: Mapping[str, str] | None) -> dict[str, Any]:
    """Each covered file's VALID review, read once. A row gone, or not valid, covers nothing."""
    from genios_engine.reason.expert import store as reviews

    out: dict[str, Any] = {}
    for file_id, fingerprint in sorted((covered or {}).items()):
        row = reviews.read_review(conn, org_id, str(file_id), str(fingerprint))
        if row is not None and row.status == reviews.VALID and row.review is not None:
            out[str(file_id)] = row
    return out


def _advice(row) -> tuple:
    """What a stored review advises, as its check let it stand (STEP-13): the mode the check leaves and
    the move it shows — who, what, for whom, by when. The card says exactly these; two reviews that say
    them alike gave the same advice. A review with no check advises nothing anybody was shown."""
    from genios_engine.reason.expert import decide as expert

    checked, review = row.checked, row.review
    if checked is None:
        return (None, None)
    move = review.next_move
    shown = move is not None and checked.fate == "shown" and checked.words.headline
    return (expert.mode_of(review, checked),
            (move.who, checked.words.headline, move.for_whom, move.by_when) if shown else None)


def _same_advice(conn, org_id: str, file_id: str, fingerprint: str | None, row) -> bool:
    """Did the review behind a standing decision (`fingerprint`, its run's trigger) advise what the
    stored review `row` advises? A review gone, or never valid, gave no advice to keep."""
    from genios_engine.reason.expert import store as reviews

    if not fingerprint:
        return False
    prior = reviews.read_review(conn, org_id, file_id, str(fingerprint))
    return prior is not None and prior.review is not None and _advice(prior) == _advice(row)


def _clear_file_decision(store, org_id: str, file_id: str, fingerprint: str, rule_id: str) -> int:
    """The file's new review names no move now: what an earlier review decided is cleared — its cards
    RULE_CLEARED (STEP-06), the rule that fired no longer holding on its subject."""
    with store.engine.begin() as conn:
        cleared = conn.execute(text(_CLEAR_FILE_DECISIONS), {
            "o": org_id, "r": rule_id, "n": file_id, "fp": fingerprint}).fetchall()
        if cleared:
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.RULE_CLEARED,
                                        signal_ids=[item.signal_id for item in cleared])
    return len(cleared)


# ── STEP-13 · a held file asks its one question (`yc2_w27_s13` M36.C2.L-integration.V2.U03) ─────────────
#
# A covered file decided INSUFFICIENT on its answer — its review's move HELD by the check, or a review that
# must find out first — asks the founder ONE question (`06` D60, `03` F184): filed in `founder_questions`
# by the run that asked it, and carried by a question signal — the Investigation lane, bound to that run's
# decision (binding 0: no candidate, no selected move), authorised as a question
# (`reason/authority.QUESTION_SIGNAL_PREDICATE`) and never as a decision. One open question signal per
# file: the same question asked again keeps its signal, RE-BOUND to the run asking it now — its card is
# not torn down and rebuilt; a new question replaces it, its card REPLACED; any other decision retires
# the file's question and expires its signal.
QUESTION_RULE = "founder_question"

_OPEN_QUESTION_SIGNAL = (
    "select signal_id from signals where org_id = :o and rule_id = 'founder_question' "
    "and subject_node_id = :n and status = 'open'")


def _question_words(review) -> tuple[str, str]:
    """What the file asks, and why — the check's own question and its reason; a review that must find
    out first asks its own move, because the file cannot be read on without its answer."""
    checked = review.checked
    move = review.review.next_move
    question = (checked.question if checked is not None and checked.question else None) \
        or (move.what if move is not None else review.review.frames.primary)
    why = (checked.because if checked is not None and checked.because else None) \
        or "the expert cannot read this file on without your answer: " + review.review.frames.primary
    return question, why


def _ask_the_founder(store, *, org_id: str, file_id: str, review, decision, bundle: dict, pack: dict,
                     eval_time, situation_id: str | None) -> str:
    """File the file's question and its signal: `asked`, or `standing` (re-bound to this run)."""
    from genios_engine.context import founder_questions as questions

    run, output = bundle.get("run") or {}, bundle.get("output") or {}
    question, why = _question_words(review)
    with store.engine.begin() as conn:
        before = questions.open_question(conn, org_id, file_id)
        asked = questions.ask(conn, org_id=org_id, file_id=file_id, fingerprint=review.fingerprint,
                              run_id=run.get("run_id"), question=question, why=why, at=eval_time)
        standing = conn.execute(text(_OPEN_QUESTION_SIGNAL), {"o": org_id, "n": file_id}).first()
        bound = {"o": org_id, "run": run.get("run_id"), "dhash": output.get("decision_hash"),
                 "exp": decision.expires_at, "cfg": run.get("config_snapshot_id"), "et": eval_time}
        if standing is not None and before is not None and before.question_id == asked.question_id:
            conn.execute(text(
                "update signals set reasoning_run_id = :run, reasoning_decision_hash = :dhash, "
                "authority_expires_at = :exp, config_snapshot_id = :cfg, eval_time = :et "
                "where org_id = :o and signal_id = :s"), {**bound, "s": standing.signal_id})
            return "standing"
        if standing is not None:
            conn.execute(text("update signals set status = 'expired' where org_id = :o and signal_id = :s"),
                         {"o": org_id, "s": standing.signal_id})
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                        signal_ids=[standing.signal_id])
        conn.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, rule_version, level, "
            "subject_node_id, score, reason_code, evidence, eval_time, config_snapshot_id, reasoning_run_id, "
            "reasoning_decision_hash, authority_expires_at, authority_binding_version, output_lane, "
            "lane_reason, capability_id, capability_version, situation_id) values (:id, :o, :pack, :packv, "
            "'founder_question', 1, 'observation', :n, 0, 'founder_question', cast(:ev as jsonb), :et, :cfg, "
            ":run, :dhash, :exp, 0, :lane, :lreason, :cap, :capv, :sit)"), {
                # Its id is its content's — the question and the run asking it — so asking mints no id
                # another part of the run would have minted (`03` F170's rule).
                **bound, "id": "sig_" + hashlib.sha256(
                    f"{org_id}\x1f{asked.question_id}\x1f{run.get('run_id')}".encode()).hexdigest()[:24],
                "pack": pack["pack_id"], "packv": pack["version"],
                "n": file_id,
                "ev": json.dumps([{"field": "founder_question", "value": asked.question_id}]),
                "lane": decision.output_lane.value if decision.output_lane is not None else None,
                "lreason": decision.lane_reason,
                "cap": decision.capability_id, "capv": decision.capability_version,
                "sit": (str(situation_id).strip() or None) if situation_id else None})
    return "asked"


def _retire_question(store, *, org_id: str, file_id: str, eval_time) -> bool:
    """A decision that is no question: the file's open question retires, and its signal and card with it."""
    from genios_engine.context import founder_questions as questions

    with store.engine.begin() as conn:
        retired = questions.retire(conn, org_id=org_id, file_id=file_id, why=questions.NO_LONGER_ASKED,
                                   at=eval_time)
        expired = conn.execute(text(
            "update signals set status = 'expired' where org_id = :o and rule_id = 'founder_question' "
            "and subject_node_id = :n and status = 'open' returning signal_id"),
            {"o": org_id, "n": file_id}).fetchall()
        if expired:
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                        signal_ids=[item.signal_id for item in expired])
    return bool(retired or expired)


def work_the_needs(store, org_id: str, *, eval_time=None, fetchers=None):
    """STEP-13 (`yc2_w27_s13` M36.C2.L-integration.V2.U03; §1 claim 5): the needs queue has its reader at
    last. `capture/acquire/need_executor.run_needs` works the queue and `context/evidence_need_store` holds
    it, and neither may import the other (`capture` is layer 1, `context` 2) — so the composition root
    joins the two halves here, a layer above both. With no connector wired (`build_fetchers` is honestly
    empty — Harsh's integration) the pass REFUSES and closes nothing: a need closed "not connected" would
    be a question destroyed. A question to the founder never waits on it — it is `founder_questions`'."""
    from genios_engine.capture.acquire.need_executor import build_fetchers, run_needs
    from genios_engine.context.evidence_need_store import close_need, read_open_needs

    def read_open(org: str, *, limit: int):
        with store.engine.connect() as conn:
            return read_open_needs(conn, org, limit=limit)

    def close(need_id: str, *, state: str, reason: str | None = None) -> bool:
        with store.engine.begin() as conn:
            return close_need(conn, need_id, state=state, reason=reason)

    return run_needs(org_id, read_open=read_open, close=close,
                     fetchers=build_fetchers(org_id) if fetchers is None else fetchers,
                     eval_time=eval_time)


def _retire_stood_down(store, org_id: str, situation_ids, rule_id: str) -> int:
    """Expire what the file's stood-down situations left open — their cards REPLACED (STEP-06)."""
    if not situation_ids:
        return 0
    with store.engine.begin() as conn:
        retired = conn.execute(text(_STOOD_DOWN_SIGNALS), {
            "o": org_id, "r": rule_id, "sids": list(situation_ids)}).fetchall()
        if retired:
            card_lifecycle.expire_cards(conn, org_id=org_id, cause=card_lifecycle.REPLACED,
                                        signal_ids=[item.signal_id for item in retired])
    return len(retired)


def _decide_covered_files(*, store, conn, org_id: str, reviews: Mapping[str, Any],
                          stood_down: Mapping[str, list[str]], gate, counts, eval_time,
                          graph_version: int, live: bool, live_domains, registry, reasoning_store,
                          packs: dict, remaining: list, decided: dict | None = None) -> None:
    """Each covered file, decided once from its review; its decision persisted and emitted on the live
    lane, measured on the shadow one. Never raises past a file. ``decided`` collects the files decided
    on the LIVE lane — file → its review's fingerprint — whatever the decision said, or standing from an
    earlier pass (M33.C1.L-integration.V2.U12): what a pack rule may stand down for (`reason/runner`)."""
    decided = decided if decided is not None else {}
    from genios_engine.platform.canonical import semantic_hash
    from genios_engine.reason.change_gate import should_skip
    from genios_engine.reason.expert import decide as expert

    if not reviews:
        return
    homes = {str(r.anchor_node_id): r for r in conn.execute(
        text(_FILES_HOME), {"o": org_id, "files": list(reviews)})}
    for file_id in sorted(set(reviews) - set(homes)):
        if stood_down.get(file_id):
            home = conn.execute(text(_STOOD_DOWN_HOME), {
                "o": org_id, "f": file_id, "sids": list(stood_down[file_id])}).first()
            if home is not None:
                homes[file_id] = home
    rule_id = expert.CAPABILITY_ID.rsplit(".", 1)[-1]
    for file_id, review in sorted(reviews.items()):
        home = homes.get(file_id)
        if home is None:
            # No situation was ever formed on it, so no corpus — and no pack — to bind a decision to.
            counts["covered_without_situation"] += 1
            continue
        try:
            domain = l3_domain_for(home.domain)
            live_file = live_lane(forced=live, domain=domain, activated=live_domains)
            pack = None
            if live_file:
                if domain not in packs:
                    packs[domain] = _tenant_pack(registry, store, org_id, domain)
                pack = packs[domain]
                if pack is None:
                    counts["expert_no_tenant_pack"] += 1
                    continue
            # THE CHANGE GATE, ON THE FILE: the review, the decision's own version, where it binds.
            # The same review in the same lane is the same decision — skipped while it stands.
            key = f"{file_id}|{expert.CAPABILITY_ID}"
            fingerprint = semantic_hash({
                "review": review.fingerprint, "decide": expert.DECIDE_VERSION, "domain": domain,
                "live": live_file, "config": pack["snapshot_id"] if pack else None,
                # STEP-13: the same review checked again under a new check version is decided again.
                "check": review.checked.version if review.checked is not None else None})
            if gate.ready:
                standing = (gate.expiries.get((pack["pack_id"], pack["version"], rule_id, file_id))
                            if pack else None)
                verdict = should_skip(gate.stored.get(key), fingerprint, live=live_file,
                                      standing_expires_at=standing, eval_time=eval_time)
                if verdict.skip:
                    counts["expert_unchanged"] += 1
                    gate.skipped.add(key)
                    if live_file:
                        decided[file_id] = review.fingerprint
                    continue
            request = expert.request_for(
                review, org_id=org_id, root_entity_type=str(home.node_type),
                domain=domain or str(home.domain), eval_time=eval_time,
                graph_version=graph_version,
                mode=ExecutionMode.LIVE if live_file else ExecutionMode.SHADOW,
                live_delivery_enabled=live_file,
                config_snapshot_id=pack["snapshot_id"] if pack else None)
            execution = expert.decide(request)
            counts["expert_decided"] += 1
            run_id = execution.trace.run_id
            if not live_file:
                counts["expert_shadow"] += 1
                gate.record(key, fingerprint, "shadow", run_id)
                continue
            # THE SAME DAILY CAP, the same pool (see the situation loop above).
            if remaining[0] is None:
                remaining[0] = _daily_allowance(store, org_id, eval_time, pack)
                counts["budget_allowance"] = remaining[0]
            if remaining[0] <= 0:
                counts["budget_exhausted"] += 1
                gate.record(key, fingerprint, "indeterminate", run_id)
                continue
            bundle: dict = {}
            outcome = _persist_live(
                store=store, reasoning_store=reasoning_store, org_id=org_id, node_id=file_id,
                package=_REVIEWED, execution=execution, eval_time=eval_time, pack=pack,
                situation_id=str(home.situation_id), replace_unless_from=review.fingerprint,
                same_advice=lambda prior, _file=file_id, _row=review: _same_advice(
                    conn, org_id, _file, prior, _row), bundle_out=bundle)
            counts[f"expert_{outcome}"] += 1
            # STEP-13 (M36.C2.L-integration.V2.U03): a file decided INSUFFICIENT on its answer asks the
            # founder its one question; any other decision retires the question it asked before.
            if execution.decision.outcome == DecisionOutcome.INSUFFICIENT_CONTEXT:
                counts[f"expert_question_{_ask_the_founder(store, org_id=org_id, file_id=file_id, review=review, decision=execution.decision, bundle=bundle, pack=pack, eval_time=eval_time, situation_id=str(home.situation_id))}"] += 1
            elif _retire_question(store, org_id=org_id, file_id=file_id, eval_time=eval_time):
                counts["expert_question_retired"] += 1
            if outcome != "rule_id_collision":
                decided[file_id] = review.fingerprint
            if outcome == "nothing_to_emit" and execution.decision.outcome in _NO_MOVE:
                cleared = _clear_file_decision(store, org_id, file_id, review.fingerprint, rule_id)
                if cleared:
                    counts["expert_cleared"] += cleared
            gate.record(key, fingerprint, _gate_outcome(execution, outcome), run_id)
            if outcome == "emitted":
                remaining[0] -= 1
            counts["covered_signals_replaced"] += _retire_stood_down(
                store, org_id, stood_down.get(file_id), rule_id)
        except Exception:      # noqa: BLE001 — one file's decision is never the pass
            counts["expert_error"] += 1
            logger.exception("domain-compiler: the covered file %s could not be decided org=%s",
                             file_id, org_id)


# =================================================================================================
# THE L2 → L3 DOMAIN TRANSLATION
#
# Layer 2 names a situation's domain in its OWN vocabulary (`context/domain_spec.py`), and
# `platform/l3_activation.L3_DOMAINS` names the three authored corpora. They agree on two words
# out of five and disagree on the third, so the translation is written down once, below, rather
# than being a string comparison that silently never matches.
#
# ⛔ THE SENTENCE THAT USED TO CLOSE THIS BLOCK — "no corpus was authored for them" — WAS WRONG,
# and L2-4 corrected it in `CANDIDATE_ROUTES` and in `DARK_DOMAINS` while leaving this copy
# behind. It is deleted rather than edited: two paragraphs stating one fact is how the fact goes
# stale in the one nobody reads. `fundraising` and `general` are dark for two DIFFERENT reasons
# and each states its own, immediately below.
# =================================================================================================


@dataclass(frozen=True, slots=True)
class CandidateRoute:
    """A corpus that COULD serve a dark domain, with the evidence, and not armed.

    ⛔ Same shape as L2-2's `OBSERVE` laws and for the same reason: the claim is believed, the
    blast radius is not measured, and arming it before somebody has the number is how a cutover
    looks like a breakage.
    """

    corpus: str
    evidence: str


#: ⛔ **RETIRED 2026-10-09 — THE ONE CANDIDATE ROUTE THERE WAS** (STEP-11, `06` D2,
#: M30.C1.L-logic.V1.U02). It said `fundraising`'s doctrine existed, in the Sales corpus, "one line
#: from live". The doctrine has since moved to a corpus of its own — the Founder Office (`Domain
#: Expertise/Founder Office Expertise/`, M30.C6.L-data.V1.U01), whose card lane needs no engine code
#: (`packs/wiring._corpus_packs`) — and `_L2_TO_L3_DOMAIN` maps `fundraising` there below: the one line,
#: to the right corpus. Its two switches are unchanged in kind: `live_lane` still needs the TENANT to
#: have activated the corpus (the pilot org alone, D2), and the live compile still admits only what a
#: named reviewer accepted (D45) — so until the founder's review, a fundraising situation on the pilot
#: is refused as `unreviewed`, said, rather than dark, unsaid. The Sales copy is retired with it
#: (M30.C6.L-data.V2.U03). Kept as an empty table so the next dark domain's candidate has its shape.
CANDIDATE_ROUTES: dict[str, CandidateRoute] = {}

#: Why each candidate route that went live ended — one line of history per route.
RETIRED_CANDIDATE_ROUTES: dict[str, str] = {
    "fundraising": "ENDED 2026-10-09 (STEP-11, `06` D2): the L2 `fundraising` domain maps to the "
                   "`founder_office` corpus, where investor relations moved; the Sales copy it "
                   "pointed at is retired (M30.C6.L-data.V2.U03).",
}

#: ⛔ **KEYS THAT ARE NOT LAYER 2 DOMAINS.** Accepted defensively so a caller that already
#: translated is not punished for it. Declared rather than noticed, because a key nobody can
#: account for is how a map stops being checkable.
CORPUS_ID_ALIASES: dict[str, str] = {
    "customer_support": "the CORPUS id, not an L2 domain. `support` is the Layer 2 domain and "
                        "maps here; this row accepts a caller that already translated.",
}

#: ⛔ **TOTAL OVER `domain_spec.registered_domains()`, AND THE `None`s ARE `DARK_DOMAINS`.**
#:
#: Written out in full — including the two that map to nothing — because `.get()` answers `None`
#: for a domain somebody DECIDED about and for one somebody FORGOT, and those are different facts.
#: `support` was forgotten once and 33 situations died silently for it.
#:
#: `tests/reason/test_domain_mapping_is_total.py` binds this table to the registry in one
#: direction and to `context/domain_silence.DARK_DOMAINS` in the other, so the three places that
#: state this one fact can no longer agree by coincidence.
_L2_TO_L3_DOMAIN: dict[str, str | None] = {
    "admin": "admin",
    "sales": "sales",
    "support": "customer_support",
    "customer_support": "customer_support",   # see CORPUS_ID_ALIASES
    # STEP-11 (`06` D2) · the founder's own work — investors, and the programmes Layer 1 hints into
    # this domain — reads the Founder Office corpus, switched on for the pilot org alone. It was dark
    # until 2026-10-09: see RETIRED_CANDIDATE_ROUTES above.
    "fundraising": "founder_office",
    # ⛔ `general` IS STILL DARK, AND FOR ITS OWN REASON: `relationship` is claimed by ALL THREE
    # older corpora, so a route is a CHOICE nobody has made. Not a missing corpus.
    # `DARK_DOMAINS` carries the reason and the ENDS WHEN.
    "general": None,
}


def live_lane(*, forced: bool, domain: str | None, activated: frozenset[str] | Iterable[str]) -> bool:
    """Is THIS situation on the live lane — publishing a package and emitting a signal?

    THE UNACTIVATABLE DOMAIN LOSES TO EVERYTHING, and that is the property this function exists to
    hold. `domain is None` means no corpus claims this situation's L2 domain, so there is no
    doctrine to compile and nothing that could author a card. The comment beside the caller has
    always said such a situation "publishes no package and emits no signal — on EVERY tenant
    configuration"; the expression it described did not, because it read
    ``live or (domain is not None and domain in activated)`` and the global flag is checked FIRST.
    With `use_domain_compiler` on, an unactivatable situation was handed the live compiler — the
    one configuration in which the stated safety property is false is the one a global flag
    creates.

    TWO SWITCHES, AND ONLY ONE OF THEM IS A WAY BACK. `activated` is
    `platform/l3_activation.activated_domains` — per tenant, per corpus, and reversible by
    deleting the row. `forced` is `platform/config.use_domain_compiler`, one boolean for every
    tenant at once; it is set in no environment and has never been true anywhere. It only ever
    turns lanes ON: switching it off does not take an activated tenant off the live lane, because
    the second clause still answers yes. It is therefore not a kill switch for the activation
    table, whatever it is called elsewhere — the way back is the erasure row.

    Kept rather than deleted because deleting it is a separate, gated decision (the L3 plan's
    "retired, not extended", after a pilot passes J5). What this removes is its ability to
    contradict the fail-closed rule while it waits.
    """
    if domain is None:
        return False
    return bool(forced or domain in activated)


def l3_domain_for(l2_domain: Any) -> str | None:
    """The activatable corpus for one L2 domain, or None when no corpus claims it."""
    return _L2_TO_L3_DOMAIN.get(str(l2_domain or "").strip().lower())


# =================================================================================================
# STEP-11 · A PROGRAMME OR A PORTAL IS NEVER DECIDED AS AN INVESTOR
# (`yc2_w27_align` M34.C2.L-logic.V0.U10)
#
# Layer 2 has no situation type for an application (`06` D32), and its hint files accelerators,
# incubators and cohorts under `fundraising` by construction (`capture/domain/hints.py`), so a
# programme's mail and a government portal's form `investor_relationship` / `investor_contact` and
# route to the investor capability — F17's accelerator, F24's, F01's and F02's portal (STEP-11 §8.1).
# The capability's own situation file calls that a misfile. Nothing showed it, because the capability
# is unreviewed and the live compile refused every fundraising file `unreviewed`; with the investor
# sheet admitted (`06` D45) the programme was compiled, decided and EMITTED as a fund — measured on
# a test corpus admitted by the founder's own ceremony.
#
# So the brief decides. A file whose in-motion line names its kind of work `program` or `compliance`
# (`06` D31) is refused `misfiled_kind` when the investor capability is the one its route reaches:
# after admission, so its end is recorded, and before the compile, so no investor package is
# published for it. On both lanes — the shadow lane measures what the live one would do. A brief that
# names no such line refuses nothing and costs no read; one that cannot be read is no brief
# (`platform/company_brief.current`), and the file is read as it was. Which playbook such a file
# reads instead is STEP-12's, per file (`packs/compiler/playbook_reader`).
# =================================================================================================

#: The capability that reads a file as an investor's (`06` D2, D31).
INVESTOR_CAPABILITY: str = str(KIND_CAPABILITY["investor"])
#: The kinds of work it may never decide — a programme's file and a portal's.
NOT_AN_INVESTOR: frozenset[str] = frozenset({"program", "compliance"})
#: The refusal, counted under this name; its end is `unsupported` with this reason.
MISFILED_KIND = "misfiled_kind"

_ANCHOR_KEYS = ("select node_id, canonical_key from graph_nodes "
                " where org_id = :o and node_id = any(:ids) and valid_to is null")


def file_kinds(conn, org_id: str, brief, anchors: Iterable[str]) -> dict[str, str]:
    """Anchor node id → `program` or `compliance`, for each file the brief names as such work.

    By the rule a file is filed by everywhere else (`context/workstreams._work_kind`, read by the
    anchor's own key as `platform/kind_windows` reads D33's window): the first in-motion line the
    founder accepted that names the anchor's address, or its domain or a parent of it. So a file a
    founder named as a fund first stays a fund's. No read at all when no line names such work."""
    from genios_engine.context.workstreams import _anchor_domain, _work_kind, _work_lines

    work = _work_lines(brief)
    ids = sorted({str(a) for a in anchors if a})
    if not ids or not any(line.kind in NOT_AN_INVESTOR for line in work):
        return {}
    out: dict[str, str] = {}
    for r in conn.execute(text(_ANCHOR_KEYS), {"o": org_id, "ids": ids}):
        key = str(r.canonical_key or "").strip().lower()
        kind = _work_kind(work, {key} if "@" in key else set(), _anchor_domain(key)) if key else None
        if kind in NOT_AN_INVESTOR:
            out[str(r.node_id)] = kind
    return out


def misfiled_kind(catalog, *, domain: str | None, situation_type: Any, kind: str | None) -> bool:
    """Would the investor capability decide this file, which the brief names a programme's or a
    portal's? The route is the corpus's own (`registry/situation-capability-map.yaml`)."""
    if kind not in NOT_AN_INVESTOR or domain is None:
        return False
    corpus = (getattr(catalog, "domains", None) or {}).get(domain)
    route = (getattr(corpus, "routes", None) or {}).get(str(situation_type or "")) or {}
    return INVESTOR_CAPABILITY in (route.get("capabilities") or ())


# =================================================================================================
# STEP-02 · THE CHANGE GATE, COMPILED LANE (`yc2_w27_s02/M20.C3.L-integration.V2.U02`)
#
# Every sweep re-decided every situation, and on a sweep that brought nothing new it paid the decider
# and R-1 again for the same answer — on the golden runner F13 2 calls, F29 12, no card changed
# (`speedrun008/YC-II W27/` STEP-02 §8.1). The gate asks, just before `reason_native_capability`,
# whether what this decision depends on is what the last decision saw (`reason/fingerprint`), and
# skips it when `reason/change_gate.should_skip` says it may. Live and shadow rows alike: a shadow
# row's model calls were the same spend, discarded.
#
# ⛔ IT FAILS OPEN, EVERYWHERE. A gate that cannot load, a request that cannot be fingerprinted, a
# store write that fails — each costs the saving, never the decision: the subject is decided as if
# the gate did not exist. And its memory is written once, after the pass, in one transaction, so a
# pass that dies half way leaves the rows it did not reach to be decided next sweep.
# =================================================================================================
_OPEN_SIGNAL_EXPIRY = (
    "select pack_id, pack_version, rule_id, subject_node_id, "
    "       max(authority_expires_at) as expires_at "
    "  from signals where org_id = :o and status = 'open' group by 1, 2, 3, 4")


def _gate_outcome(execution, persisted: str | None) -> str:
    """What a live compiled row came to, in the store's vocabulary (`reason/fingerprint_store`)."""
    from genios_engine.contracts.reasoning import DecisionOutcome
    from genios_engine.reason import fingerprint_store as fs
    from genios_engine.reason.llm_decision_maker import LLM_UNAVAILABLE_REASON

    if persisted == "emitted":
        return fs.EMITTED
    if persisted == "standing":
        return fs.STANDING
    if persisted in ("nothing_to_emit", "rule_id_collision"):
        decision = getattr(execution, "decision", None)
        if decision is not None and decision.outcome == DecisionOutcome.DEFER:
            unavailable = any(str(u).startswith(LLM_UNAVAILABLE_REASON)
                              for u in (decision.uncertainty or ()))
            return fs.INDETERMINATE if unavailable else fs.DEFERRED
        return fs.SUPPRESSED
    return fs.INDETERMINATE          # race_lost, an error, a cap, anything unnamed: decide again


class _CompiledGate:
    """One pass's view of the change gate: loaded once, consulted per row, written once."""

    def __init__(self, *, stored=None, inputs=None, expiries=None, ready: bool = False) -> None:
        from genios_engine.reason.fingerprint_inputs import InputsIndex

        self.stored = stored or {}
        self.inputs = inputs or InputsIndex()
        self.expiries = expiries or {}
        self.ready = ready
        self.decided: dict[str, tuple[str, str, str | None]] = {}
        self.skipped: set[str] = set()

    @classmethod
    def load(cls, conn, org_id: str) -> "_CompiledGate":
        from genios_engine.reason.fingerprint_inputs import read_inputs
        from genios_engine.reason.fingerprint_store import load_all

        try:
            expiries = {(r.pack_id, r.pack_version, r.rule_id, r.subject_node_id): r.expires_at
                        for r in conn.execute(text(_OPEN_SIGNAL_EXPIRY), {"o": org_id})}
            return cls(stored=load_all(conn, org_id), inputs=read_inputs(conn, org_id),
                       expiries=expiries, ready=True)
        except Exception:      # noqa: BLE001 — the gate fails open: every row is decided
            logger.exception("change gate unavailable for org=%s — deciding every situation",
                             org_id)
            try:
                conn.rollback()
            except Exception:      # noqa: BLE001
                pass
            return cls()

    def check(self, *, org_id: str, situation_id: str, manifest, node_ctx, projection, pack,
              live: bool, eval_time, graph_version, interpreted: bool = False):
        """(subject key, fingerprint, verdict) — or a None fingerprint when the gate cannot judge."""
        from genios_engine.reason.change_gate import should_skip
        from genios_engine.reason.fingerprint import material_fingerprint

        key = f"{situation_id}|{manifest.capability_id}"
        if not self.ready:
            return key, None, None
        try:
            snapshot = native_context_snapshot(
                org_id=org_id, context=node_ctx, capability=manifest,
                evaluation_time=eval_time, graph_version=graph_version, projection=projection)
            pack_id = pack["pack_id"] if pack else manifest.domain
            fingerprint = material_fingerprint(
                manifest, snapshot,
                config_snapshot_id=(pack["snapshot_id"] if pack else None),
                mode=ExecutionMode.LIVE if live else ExecutionMode.SHADOW,
                inputs=self.inputs.for_situation(pack_id, situation_id, manifest.capability_id,
                                                 interpreted=interpreted))
        except Exception:      # noqa: BLE001 — unfingerprintable: decide it
            logger.exception("change gate could not fingerprint %s for org=%s", key, org_id)
            return key, None, None
        standing = None
        if live and pack:
            rule_id = str(manifest.capability_id).rsplit(".", 1)[-1]
            standing = self.expiries.get((pack["pack_id"], pack["version"], rule_id,
                                          node_ctx.node_id))
        verdict = should_skip(self.stored.get(key), fingerprint, live=live,
                              standing_expires_at=standing, eval_time=eval_time)
        return key, fingerprint, verdict

    def record(self, key: str, fingerprint: str | None, outcome: str, run_id: str | None) -> None:
        if fingerprint is not None:
            self.decided[key] = (fingerprint, outcome, run_id)

    def flush(self, *, store, org_id: str, eval_time, counts) -> None:
        from genios_engine.reason import fingerprint_store as fs

        if not (self.decided or self.skipped):
            return
        try:
            with store.engine.begin() as conn:
                for key, (fingerprint, outcome, run_id) in self.decided.items():
                    fs.record_decided(conn, org_id=org_id, subject_key=key, lane="compiled",
                                      fingerprint=fingerprint, outcome=outcome, run_id=run_id,
                                      decided_at=eval_time)
                for key in self.skipped:
                    fs.record_skipped(conn, org_id=org_id, subject_key=key, checked_at=eval_time)
        except Exception:      # noqa: BLE001 — a lost memory costs one re-decision next sweep
            counts["gate_write_failed"] += 1
            logger.exception("change gate could not record the pass for org=%s", org_id)


class _SituationEnds:
    """STEP-06 · what came of each admitted LIVE candidate in this pass — noted, then written once.

    The admission ledger says admit / hold / reject; the change gate's rows say what was decided.
    What ended in between was a counter in this pass's log line. Each admitted live candidate now
    leaves one `situation_outcomes` row (0194), keyed on its admission `decision_id`: `decided` with
    the change gate's word for it, or the stop and its reason. Written once, after the pass, in one
    transaction, failing open — the change gate's discipline (`_CompiledGate.flush`): a lost write
    costs a record, never the pass. A shadow row is never noted: its candidate was never recorded.
    """

    def __init__(self) -> None:
        self.ends: dict[str, tuple[str, str, str | None]] = {}
        self.seen: dict[str, str] = {}

    def note(self, decision_id: str | None, situation_id: str, outcome: str,
             reason: str | None = None) -> None:
        if decision_id:
            self.ends[decision_id] = (situation_id, outcome, reason)

    def unchanged(self, decision_id: str | None, situation_id: str) -> None:
        """The change gate skipped it: the end it was given stands; only its clock moves."""
        if decision_id:
            self.seen[decision_id] = situation_id

    def flush(self, *, store, org_id: str, eval_time, counts) -> None:
        from genios_engine.reason import situation_outcome_store as so

        if not (self.ends or self.seen):
            return
        try:
            with store.engine.begin() as conn:
                for decision_id, (situation_id, outcome, reason) in self.ends.items():
                    so.record(conn, org_id=org_id, decision_id=decision_id,
                              situation_id=situation_id, outcome=outcome, reason=reason,
                              at=eval_time)
                for decision_id, situation_id in self.seen.items():
                    if decision_id not in self.ends:
                        so.record_seen(conn, org_id=org_id, decision_id=decision_id,
                                       situation_id=situation_id, at=eval_time)
        except Exception:      # noqa: BLE001 — a lost record never costs the pass
            counts["outcome_write_failed"] += 1
            logger.exception("situation ends could not be recorded for org=%s", org_id)


def shadow_compile(*, store: GraphStore, org_id: str, eval_time: datetime | None = None,
                   limit: int = 200, live: bool = False, registry=None,
                   live_domains: frozenset[str] | Iterable[str] = (),
                   covered: Mapping[str, str] | None = None,
                   people: Mapping[str, Iterable[str]] | None = None) -> dict:
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

    ``covered`` — STEP-12 M33, `06` D1: the files a VALID expert review now answers (the expert
    pass's receipt, file → the review's fingerprint). Each is decided ONCE, from its review — no
    decider, no R-1 — and emitted as the file's own signal, its anchor the subject; every situation
    of the file the review explains stands down. See `_decide_covered_files`. None, or empty — every
    caller before M33, and every tenant whose expert pass did not run — is exactly the pass before.
    ``people`` — the same receipt's file → the file's people (M33.C1.L-integration.V2.U13): a situation
    anchored on one of them is its file's to explain (`reason/expert/cover`).
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

    # ⛔ R-6 IS RETIRED (`06` D51, STEP-12 `yc2_w27_s12` M32.C4.L-logic.V0.U02, `03` F141). It built a
    # gate and a model client here every sweep and consulted the Context Reasoner for every compiled
    # situation, shadow ones included, AHEAD of STEP-02's change gate — writing a
    # `situation_interpretations` row per situation per pass, with an empty proposal on every tenant,
    # because its feature was off everywhere. The expert pass reviews the FILE instead (STEP-12). No
    # gate, no client, no consult and no row are made here now; the module stays for its own tests.
    #
    # STEP-07 · THE COMPANY BRIEF, ONCE PER SWEEP: the kinds of work a file is filed under are read
    # from it (`file_kinds`). `current` reads on a connection of its own and fails open to the empty
    # brief.
    from genios_engine.platform.company_brief import current as current_company_brief
    company_brief = current_company_brief(store.engine, org_id)
    adj, _node_types, obs_idx, fact_idx = _neighbor_index(store, org_id)
    # Every anchor's facts and observations in TWO org-wide reads instead of two per situation
    # (up to 400 round trips per sweep). The bulk loaders use the per-node load's filters and
    # ordering (`runner._load_context` relies on the same equivalence), so each context is the
    # one the per-node read built. Copied per situation below: the bulk dicts are shared, and one
    # situation's context must never be able to see another's edits.
    facts_by_node = _bulk_load_facts(store, org_id)
    obs_by_node = _bulk_load_obs(store, org_id)
    counts: Counter = Counter()
    # ⛔ PLAIN DICTS, BESIDE THE COUNTER, NOT INSIDE IT. `counts` is a `Counter` and every other
    # value in it is an int; a mapping stored among them makes `most_common()` and `Counter.__add__`
    # raise on a type comparison the moment somebody reaches for either. The result is flattened
    # with `dict(counts)` at the end, so these merge in there instead.
    #
    # ⛔ AND THEY ARE ALWAYS PRESENT, EVEN EMPTY. A key that appears only when it fires is a key
    # nobody knows exists — `deliver/pipeline` prints its zeros for the same reason. An absent
    # `no_route_by_reason` reads as "this build does not measure that"; an empty one reads as
    # "nothing was refused", which is the fact.
    no_route_by_reason: dict[str, int] = {}
    no_route_by_type: dict[str, int] = {}
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
        gate = _CompiledGate.load(conn, org_id)
        # STEP-06 · beside the gate, and for the same reason: noted per row, written once.
        ends = _SituationEnds()
        # STEP-12 M33 · the reviews that decide their files, each read once for the pass — and what
        # each explains, over the file's people the expert pass named (`people`, U13).
        expert_reviews = _covered_reviews(conn, org_id, covered)
        covers = Covers(cover_of(row, people=(people or {}).get(file_id, ()))
                        for file_id, row in expert_reviews.items())
        # `03` F104 · each anchor's measured normals, read once for the pass.
        file_numbers = _measured_baselines(conn, org_id)
        counts["covered_files"] = len(expert_reviews)
        stood_down: dict[str, list[str]] = {}
        decided: dict[str, str] = {}
        counts["gate_ready"] = int(gate.ready)
        # WHO IS US, once for the sweep (STEP-04): `gather_members` leaves us out of a situation's
        # members, and read per situation that was one more statement for every situation.
        us = identity_for(conn, org_id)
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
        # STEP-11 · the files the brief names as a programme's or a portal's (`file_kinds`), for the
        # whole pass in one read. Never fatal: a failure costs this sweep the refusal, every file is
        # read as it was, and the rollback keeps the failed read from costing the next situation too.
        misfiled_kinds: dict[str, str] = {}
        try:
            misfiled_kinds = file_kinds(conn, org_id, company_brief,
                                        [str(r["anchor_node_id"]) for r in situations
                                         if r["anchor_node_id"]])
        except Exception:      # noqa: BLE001 — a brief that cannot be read is no brief
            conn.rollback()
            logger.exception("could not read the files' kinds of work for org=%s", org_id)
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
            # `or None` — AND THE TWO ARE NOT THE SAME ANSWER. `CapabilityResolver` reads
            # `activated_domains is not None` as "filter to this set"; an EMPTY frozenset
            # therefore means "this tenant has activated nothing" and refuses every situation
            # with `NoExpertiseRoute`. That is exactly right for the per-tenant switch — and
            # exactly wrong for `live=True`, which is the GLOBAL cutover flag documented above
            # as moving "every tenant at once". Reached through `live=True` with no activation
            # rows, the pass forced every situation onto the live lane (`live_lane(forced=...)`)
            # and then had the resolver refuse all of them: `no_route` for the whole tenant,
            # `counts` with no `emitted` key at all, and a global flag that silently compiles
            # nothing. `None` restores what "every tenant" has to mean — no filter.
            #
            # Production is unchanged: `reason/runner.py` passes `live_domains=l3_domains` read
            # from the activation table and `live=use_domain_compiler`, which is set in no
            # environment — so the live path here is reached with a NON-empty set and filters
            # exactly as before.
            activated_domains=live_domains or None,
        ) if any_live else None
        counts["l3_activated_domains"] = len(live_domains)
        # THE VARIANT DECLARATION, read once per sweep per live domain — the same shape and
        # source as `live_domains` itself. `()` for every domain that declared nothing.
        # ONE-ELEMENT LIST AND NOT AN INT, because the loop below both reads and writes it and
        # Python would otherwise need a `nonlocal` this function cannot give it. `None` means
        # "not looked up yet" — the lookup costs two queries and a tenant with no live situation
        # should not pay for them.
        _remaining: list[int | None] = [None]
        from genios_engine.platform.l3_activation import declared_variants
        variants_by_domain = {d: declared_variants(store.engine, org_id, d) for d in live_domains}
        for row in situations:
            counts["situations"] += 1
            # STEP-06: set once this candidate is admitted on the live lane; every end below is
            # noted against it. None for a shadow row, or one that ended before admission.
            admitted = None
            # WHICH LANE THIS SITUATION IS ON. The global flag still forces live for a deployment
            # that has already set it — its behaviour is unchanged — and otherwise the answer is
            # the tenant's activation row for THIS situation's corpus. A domain with no corpus
            # (`general`; `fundraising` until STEP-11) resolves to None and can never be live, which is the
            # fail-closed direction: an unactivatable domain compiles and measures exactly as it
            # does today.
            row_domain = l3_domain_for(row["domain"])
            live_row = live_lane(forced=live, domain=row_domain, activated=live_domains)
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
                # (55 rows); `fundraising:investor_relationship` and `investor_contact` were the
                # other two, until STEP-11 mapped `fundraising` to the Founder Office (2026-10-09).
                # Everything they compile is measurement, forever.
                #
                # THE MAP IS NOT THE DEFECT. Pointing `general` at `admin` "to get some coverage"
                # would put Admin doctrine on a general situation, which is worse than silence.
                # The two honest routes are to author a `general` corpus, or to decide that
                # activation should govern the corpus that SERVES a situation rather than the
                # domain that produced it — a cutover decision, not a bug fix. This counts the
                # cost so the decision can be made against a number.
                # ⛔ L2-4 · WITH ITS NAME. The scalar above answered "how many" and never
                # "which", so it could not say whether to author `fundraising` first or `general`
                # first — and `general:relationship` alone is 55 of the pilot's 159 situations.
                # `tally_unroutable` keeps the scalar and adds the domain and the situation type,
                # because a corpus is authored per TYPE. It also flags a domain that routes
                # nowhere and is not in `DARK_DOMAINS`, which is the `support` defect returning.
                tally_unroutable(counts, l2_domain=row["domain"],
                                 situation_type=row.get("situation_type"))
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
                members = gather_members(conn, org_id, row["correlation_id"], us=us)
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
                # WHY THIS SITUATION HAS NO LAYER 1 SIGNAL, when the answer is a refusal.
                # 63 of 159 live situations on the pilot are held before their content is read,
                # and `qes_required` and `verified_evidence_required` are the SAME cards — both
                # gates read what Layer 1 published and Layer 1 published nothing. The events
                # behind them scored 528-1920 against a floor of 2500. The gate is right; the
                # silence was not.
                refusal = (None if l1 is not None
                           else l1_refusal(conn, org_id, str(row["correlation_id"])))
                candidate = build_business_situation(
                    org_id=org_id, situation=row,
                    signal_ids=signal_ids, evidence=evidence, trace_id=trace_id,
                    members=members, visibility=situation_visibility, l1=l1,
                    refusal=refusal,
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
                    # Which authored overlay this situation's CORPUS runs under.
                    # Empty for every tenant that has declared nothing — the key is then absent
                    # from the situation's metadata and nothing re-mints.
                    #
                    # KEYED BY THE CORPUS DOMAIN, NOT LAYER 2'S. `variants_by_domain` is built
                    # from `live_domains`, which are corpus ids (`customer_support`); `row["domain"]`
                    # is Layer 2's (`support`). Looking one up with the other is the exact seam
                    # `l3_domain_for` exists to bridge, and it silently returned `()` for every
                    # support situation on the tenant — 33 of them — so that corpus could never
                    # receive an overlay however it was declared. `admin` and `sales` spell the
                    # same on both sides, which is why the miss was invisible.
                    variant_ids=variants_by_domain.get(row_domain or "", ()))
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
                if live_row and publication.admitted:
                    admitted = publication.decision_id
                if not publication.admitted or publication.situation is None:
                    # HOLD/REJECT is the output.  Nothing above Layer 2 receives a weak object;
                    # the durable ledger says exactly what the next sweep may repair.
                    if publication.admitted:
                        ends.note(admitted, str(row["situation_id"]), "error",
                                  "admitted_without_a_situation")
                    continue
                # STEP-12 M33 · ITS FILE'S REVIEW DECIDES IT. A situation whose every event the
                # review saw stands down here — before the compile, the decider and R-1 — and its
                # file is decided once, after the loop (`_decide_covered_files`).
                explained = covers.explaining(str(anchor), row["anchor_type"], signal_ids)
                if explained is not None:
                    counts["covered_situations"] += 1
                    stood_down.setdefault(explained.file_id, []).append(str(row["situation_id"]))
                    ends.note(admitted, str(row["situation_id"]), "decided", COVERED_BY_REVIEW)
                    continue
                bso = publication.situation
                # STEP-11 · a programme's or a portal's file is never decided as an investor: refused
                # here, its end recorded, before an investor package can be compiled for it.
                if misfiled_kind(catalog, domain=row_domain, situation_type=bso.type,
                                 kind=misfiled_kinds.get(str(anchor))):
                    counts[MISFILED_KIND] += 1
                    ends.note(admitted, str(row["situation_id"]), "unsupported", MISFILED_KIND)
                    continue
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
                        projection=projection,
                        # `03` F104 · the file's measured normals, for a corpus `{baseline: …}`.
                        baselines=file_numbers.get(str(anchor)))
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
                            ends.note(admitted, str(row["situation_id"]), "no_tenant_pack",
                                      manifest.domain)
                            continue
                    gate_key, gate_fp, gate_verdict = gate.check(
                        org_id=org_id, situation_id=str(row["situation_id"]), manifest=manifest,
                        node_ctx=node_ctx, projection=projection, pack=pack, live=live_row,
                        eval_time=eval_time, graph_version=graph_version,
                        interpreted=interpreter is not None)
                    if gate_verdict is not None and gate_verdict.skip:
                        counts["skipped_unchanged"] += 1
                        gate.skipped.add(gate_key)
                        ends.unchanged(admitted, str(row["situation_id"]))
                        continue
                    counts[f"gate_{gate_verdict.reason if gate_verdict else 'unjudged'}"] += 1
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
                    _run_id = getattr(getattr(execution, "trace", None), "run_id", None)
                    if execution.decision is None:
                        gate.record(gate_key, gate_fp, "indeterminate", _run_id)
                        ends.note(admitted, str(row["situation_id"]), "decided", "indeterminate")
                        continue
                    counts["decided"] += 1
                    if not live_row:
                        gate.record(gate_key, gate_fp, "shadow", _run_id)
                        continue
                    # ── THE DAILY CAP, WHICH THIS LANE HAS NEVER OBEYED ────────────────
                    #
                    # Legacy, native and composite all check `budget_per_day * seats -
                    # _budget_used` before publishing. This lane checked nothing, and it runs
                    # LAST — so it spent past a cap the others had already respected. Measured on
                    # the pilot 2026-09-15: 21 signals published on a day the cap said 15, the
                    # surplus being this lane's 8. A user received six cards the budget existed
                    # to prevent.
                    #
                    # SHARED POOL, NOT A SECOND ALLOWANCE. `_budget_used` counts every signal the
                    # tenant published today whatever wrote it, so taking the same subtraction
                    # keeps one cap rather than creating a second one behind it.
                    #
                    # RANKED BY THE ORDER THE PASS ALREADY WALKS, which is
                    # `confidence_overall desc` (see `_ACTIVE_SITUATIONS`). Not final utility —
                    # that is only known after the decision, and collecting every decision to
                    # sort them would mean holding each audit bundle unwritten until the last
                    # situation compiled. Confidence-descending is a principled order, and it is
                    # named here rather than left to be inferred from a query two hundred lines
                    # away.
                    if live_row and pack is not None:
                        if _remaining[0] is None:
                            _remaining[0] = _daily_allowance(store, org_id, eval_time, pack)
                            counts["budget_allowance"] = _remaining[0]
                        if _remaining[0] <= 0:
                            # Counted, never silent: a lane that stops publishing for a reason
                            # nobody can see is indistinguishable from one that had nothing to say.
                            counts["budget_exhausted"] += 1
                            # Tomorrow's budget may publish it: a clock the fingerprint does not
                            # carry, so the gate must decide it again.
                            gate.record(gate_key, gate_fp, "indeterminate", _run_id)
                            ends.note(admitted, str(row["situation_id"]), "budget_exhausted")
                            continue
                    try:
                        # ⛔ L2-7 · CARRY THE SITUATION. `row["situation_id"]` is read four times
                        # within twenty lines above and was dropped here, at the one seam where a
                        # card needs it — `not_carried`, the class of defect L1 step 18 named.
                        # Without it `deliver/pipeline` loops over signals and one situation that
                        # fires three rules becomes three cards that can never merge.
                        outcome = _persist_live(
                            store=store, reasoning_store=reasoning_store, org_id=org_id,
                            node_id=anchor, package=package, execution=execution,
                            eval_time=eval_time, pack=pack,
                            situation_id=str(row["situation_id"]))
                        counts[outcome] += 1
                        gate.record(gate_key, gate_fp, _gate_outcome(execution, outcome), _run_id)
                        ends.note(admitted, str(row["situation_id"]), "decided",
                                  _gate_outcome(execution, outcome))
                        # Only a row that actually reached a human's queue spends the budget.
                        # `standing` left yesterday's advice alone and `nothing_to_emit` concluded
                        # no action — neither put a card in front of anybody.
                        if outcome == "emitted" and _remaining[0] is not None:
                            _remaining[0] -= 1
                    except Exception:
                        counts["persist_error"] += 1
                        ends.note(admitted, str(row["situation_id"]), "error", "persist")
                        logger.exception("domain-compiler live: persist %s failed",
                                         row["situation_id"])
                except Exception:
                    counts["reason_error"] += 1
                    ends.note(admitted, str(row["situation_id"]), "error", "reasoning")
                    logger.exception("domain-compiler shadow: reasoning for %s failed",
                                     row["situation_id"])
            except NoExpertiseRoute as exc:
                # ⛔ THE FLAT TOTAL IS UNCHANGED, AND DELIBERATELY SO.
                # `tests/reason/test_the_cutover_is_declared_before_it_happens.py` asserts on
                # `"no_route": 0` and scripts read the same key. Replacing a counter to improve it
                # is how a measurement wave breaks the gate that was watching it.
                counts["no_route"] += 1
                # ⛔ AND NOW IT HAS ITS DIMENSIONS. "Twelve situations found no route" is one type
                # twelve times or twelve types once — opposite problems, opposite fixes, and the
                # same number. This layer's own rule, written in L1: *a count without its dimension
                # is not a measurement.*
                #
                # READ OFF THE EXCEPTION, NEVER OFF ITS MESSAGE. `NoExpertiseRoute` carries a
                # validated `reason` from a closed set of four; until it did, the only classifier
                # in the codebase (`scripts/corpus_route_probe.py`) told them apart with three
                # substring tests and an `else`, and reported `domain_not_activated` — an
                # operations fact — as `no_route_type`, an authoring gap.
                no_route_by_reason[exc.reason] = no_route_by_reason.get(exc.reason, 0) + 1
                # `None` is kept as a key rather than dropped: a refusal that could not name its
                # type is still a refusal, and a slice this pass could not dimension must be
                # visible as that rather than absent from the total.
                _type = exc.situation_type if exc.situation_type is not None else "unknown"
                no_route_by_type[_type] = no_route_by_type.get(_type, 0) + 1
                ends.note(admitted, str(row["situation_id"]), "no_route", exc.reason)
            except SituationContextIncomplete:
                counts["incomplete"] += 1
                ends.note(admitted, str(row["situation_id"]), "incomplete")
            except SituationContextConflict:
                counts["conflict"] += 1
                ends.note(admitted, str(row["situation_id"]), "conflict")
            except RequiredKnowledgeMissing:
                counts["required_missing"] += 1
                ends.note(admitted, str(row["situation_id"]), "required_missing")
            except UnsupportedCoverage as exc:
                # An honest "we do not cover this yet" — a route matched but every capability
                # behind it is an unauthored stub. This used to fall into the catch-all below,
                # indistinguishable from an actual compiler bug, which is exactly the confusion
                # the route-coverage metric exists to resolve. Counted by REASON so "all_stub"
                # (authoring debt) reads apart from "no_route" (nothing claims this situation).
                counts[f"unsupported_{exc.reason}"] += 1
                ends.note(admitted, str(row["situation_id"]), "unsupported", exc.reason)
            except Exception as exc:
                counts["error"] += 1
                ends.note(admitted, str(row["situation_id"]), "error", type(exc).__name__)
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
        # STEP-12 M33 · each covered file, decided once from its review.
        _decide_covered_files(
            store=store, conn=conn, org_id=org_id, reviews=expert_reviews, stood_down=stood_down,
            gate=gate, counts=counts, eval_time=eval_time, graph_version=graph_version,
            live=live, live_domains=live_domains, registry=registry,
            reasoning_store=reasoning_store, packs=packs, remaining=_remaining, decided=decided)

    # STEP-02 · the gate's memory, written once for the whole pass (see `_CompiledGate`).
    gate.flush(store=store, org_id=org_id, eval_time=eval_time, counts=counts)
    # STEP-06 · what came of each admitted live candidate, written once for the whole pass.
    ends.flush(store=store, org_id=org_id, eval_time=eval_time, counts=counts)
    # STEP-13 · the needs queue, worked once a pass — or refused, counted (`work_the_needs`).
    if live or live_domains:
        needs = work_the_needs(store, org_id, eval_time=eval_time)
        if needs.refused:
            counts["needs_refused"] += 1
        else:
            counts["needs_examined"] += needs.examined
            counts["needs_closed"] += needs.closed
            counts["needs_deferred"] += needs.deferred
    result = dict(counts)
    # STEP-12 M33 · the files decided on the live lane, file → its review's fingerprint (U12).
    result["decided"] = dict(sorted(decided.items()))
    result["no_route_by_reason"] = dict(sorted(no_route_by_reason.items()))
    result["no_route_by_type"] = dict(sorted(no_route_by_type.items()))
    # ⛔ THE RECEIPT: two breakdowns of one total, COMPARED. Two numbers that are supposed to agree
    # and are never compared eventually disagree — the argument `deliver/lane_recall` makes about
    # the per-lane tallies, and the reason a total that is never checked is a claim rather than a
    # measurement. Recorded rather than raised: a bookkeeping disagreement must never abort a pass
    # it is only observing, which is the rule `BundleStore.record_call` already states — *"a receipt
    # that can abort the thing it is a receipt for turns an accounting failure into a product
    # failure."*
    _flat = int(counts.get("no_route", 0))
    if sum(no_route_by_reason.values()) != _flat or sum(no_route_by_type.values()) != _flat:
        result["no_route_unbalanced"] = 1
        logger.warning("domain-compiler org=%s: no_route=%d but by_reason=%d and by_type=%d — a "
                       "refusal was counted in the total and not in a breakdown", org_id, _flat,
                       sum(no_route_by_reason.values()), sum(no_route_by_type.values()))
    logger.info("domain-compiler %s org=%s domains=%s %s",
                "LIVE" if live else ("PILOT" if live_domains else "shadow"),
                org_id, sorted(live_domains) or "-", result)
    return result


__all__ = ["shadow_compile"]
