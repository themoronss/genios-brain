from __future__ import annotations

import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from genios_engine.capture.documents.native import extract_native_text
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.capture.structured.apply import apply_mapping, apply_relations
from genios_engine.capture.structured.registry import get_mapping
from genios_engine.context.graph_store import GraphStore
from genios_engine.context.llm.client import LLMClient
from genios_engine.context.pipeline import process_event
from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.context.read_models import build_entity_360
from genios_engine.context.structured import commit_structured
from genios_engine.platform.crypto import decrypt

# B0 — intake + L1→L2 handoff. PRODUCTION: drains EVERY pending emitted event (no test
# cap), processes them CONCURRENTLY (the LLM call is the bottleneck — parallel = 5-6x),
# then rebuilds affected read models. Idempotent: an event already in the extraction
# ledger is skipped, so it's safe to run after every L1 sync, in the background.

def _default_l2_workers() -> int:
    """Concurrent extraction workers, derived from the pooler — same reasoning as L1.

    The 15-client cap this was written for belongs to the SESSION pooler. On the transaction
    pooler a backend is returned per transaction, and L2 is dominated by LLM round-trip wait
    anyway: three workers left the model idle most of the sweep. Still env-overridable, so a
    local run sharing the prod DB can dial itself down and not starve the live app.
    """
    from genios_engine.platform.config import get_settings
    url = (getattr(get_settings(), "database_url", "") or "")
    return 8 if ":6543/" in url else 3


_MAX_WORKERS = int(os.environ.get("GENIOS_L2_WORKERS", "0")) or _default_l2_workers()
_BATCH = 40
_MAX_ATTEMPTS = 3          # transient extract failures retry up to this, then park model_unavailable
# outcomes that mean "this event needs no more work" → written to the run ledger as terminal
_DONE_OUTCOMES = {"committed_structured", "committed", "committed_structural",
                  "parked_low_relevance", "skipped_no_llm",
                  "no_op", "committed_facts", "committed_observation"}


def _clean_for_llm(raw: dict, event_id: str, prepared_text: str | None = None) -> str:
    """Prefer the SEAM: L1 already computed the PII-masked prepared text (+offset map)
    at ingestion — subject INCLUDED, masked with the body — and persisted it to
    prepared_content. Used as-is: prepending the raw subject here would reintroduce
    unmasked subject-line PII to the LLM. Fallback re-derivation only for pre-seam rows."""
    if prepared_text:
        return prepared_text
    body = raw.get("body") or raw.get("snippet") or ""
    stripped = extract_native_text(mime="text/html", data=body) or body
    prepared = preprocess((raw.get("subject") or "") + "\n\n" + stripped,
                          event_id=event_id, mask_phone=False)
    return prepared.clean_text


def _internal_emails(store: GraphStore, org_id: str) -> frozenset[str]:
    """Every address that is US: seats, the owner, and the connected mailboxes themselves.

    This used to read `org_seats` alone. A self-serve tenant never fills that table — it had
    zero rows for the design partner — so the set was empty, and an empty "us" set does not fail
    loudly: every guard written against it silently passes. The consequences all looked like
    separate bugs. Inbound thread state was written for every sender, so `ball_in_court='us'`
    landed on addresses nobody was corresponding with. The account owner's own node became a
    counterparty, accumulating 237 observations that the reasoner then self-excluded. And the
    product's own onboarding mail was modelled as a prospect asking for a demo.

    The connected mailbox is the one identity that cannot be missing: an org that has synced
    Gmail has, by construction, told us which address it owns. Deriving from the connection
    makes "who are we" a property of the integration rather than of a table someone has to
    remember to populate.
    """
    with store.engine.connect() as c:
        rows = c.execute(text(
            # 1) explicitly configured seats — correct when populated, empty on self-serve
            "select lower(email) as e from org_seats "
            "where org_id=:o and active and email is not null "
            "union "
            # 2) the account owner. The one identity that always exists, because signup
            #    collected it: for the design partner this alone covers 57 outbound messages
            #    that were being read as mail from a stranger.
            "select lower(email) from orgs where id=:o and email is not null "
            "union "
            # 3) the connected mailbox, once the connector records which address it holds.
            #    `external_account_id` is the right home for it and is not yet populated by
            #    every provider path, so this contributes nothing today rather than failing —
            #    the union degrades, it does not break.
            "select lower(external_account_id) from connections "
            "where org_id=:o and external_account_id is not null "
            "and external_account_id like '%@%'"), {"o": org_id}).fetchall()
    return frozenset(r.e for r in rows if r.e)


def _process_one(row, *, org_id, store, llm, crypto_key, internal_emails=frozenset(),
                 effective=None):
    """Route + process ONE event. Returns (outcome, affected_node_id | None)."""
    raw = json.loads(decrypt(bytes(row.enc_content), crypto_key)) if row.enc_content else {}
    mapping = get_mapping(row.source, row.object_type)
    if mapping is not None:                          # structured lane (B1, no LLM)
        fields = apply_mapping(mapping, raw)
        display_name = fields.get(mapping.name_field) if mapping.name_field else None
        relations = apply_relations(mapping, raw)    # attendees/participants → graph edges
        res = commit_structured(store, org_id=org_id, event_id=row.event_id, source=row.source,
                                source_object_id=row.source_object_id, structured_fields=fields,
                                node_type=mapping.node_type, occurred_at=row.occurred_at,
                                display_name=display_name, relations=relations,
                                internal_emails=internal_emails,
                                domain_hints=getattr(row, "domain_hints", None))
        store.cache_set(processing_key=f"struct:{row.event_id}", org_id=org_id,
                        event_id=row.event_id, output={"structured": True},
                        input_tokens=0, output_tokens=0, model="structured")
        return "committed_structured", res.node_id
    content = _clean_for_llm(raw, row.event_id,      # unstructured lane (B3, LLM)
                             prepared_text=getattr(row, "prepared_text", None))
    is_inbound = "SENT" not in (raw.get("labelIds") or [])   # direction → thread state
    # recipients (To + Cc, captured in L1) → sender↔recipient correspondence edges in L2
    recipients = [e for e in ((raw.get("to") or []) + (raw.get("cc") or [])) if e]
    qes_output = getattr(row, "qes_output", None)
    if qes_output is None:
        # A QES whose extraction pointer cannot be resolved is incomplete input, not permission
        # for Layer 2 to reinterpret the raw message.  Leave it retryable: cache repair or an L1
        # replay can fill the pointer and the next drain will pick it up.
        return "held_missing_qes_extraction", None
    if not isinstance(qes_output, dict):
        qes_output = json.loads(qes_output)
    qualified = adapt_qes_extraction(
        qes_output,
        confidence_bp=int(getattr(row, "qes_confidence_bp", 0) or 0),
        domain_hints=getattr(row, "qes_domain_hints", None) or (),
        signal_types=getattr(row, "qes_signal_types", None) or (),
    )
    res = process_event(org_id=org_id, event_id=row.event_id, source=row.source, content=content,
                        sender_email=row.sender, recipient_emails=recipients,
                        sender_name=getattr(row, "sender_name", None),
                        occurred_at=row.occurred_at, llm=None, store=store,
                        is_inbound=is_inbound, internal_emails=internal_emails,
                        internal_kind=getattr(row, "internal_kind", None),
                        thread_id=getattr(row, "parent_object_id", None),
                        domain_hints=getattr(row, "domain_hints", None),
                        canon_meta=raw,
                        # The tenant's own pack vocabulary. Without it the extractor runs one
                        # hardcoded B2B-SaaS ontology for everyone, and a rule reading
                        # `deal.status` is dead because the model was never told the name.
                        effective=effective, qualified_extraction=qualified)
    return res.outcome, res.primary_node


#: The extraction-cache rows that mean "LAYER 2 already read this message".
#:
#: `l1_extraction_results` has TWO writers and they mean opposite things to this drain.
#: `GraphStore.cache_set` — L2's own writer, three files away — files the row this loop must not
#: pay for twice, and it writes no `profile_id` because the L2 lane has no profiles.
#: `capture/semantic/cache.PostgresExtractionCache` files Layer 1's extraction and ALWAYS carries
#: one (`cache_key` refuses a blank component, and the structured mapper files `structured`).
#:
#: The guard used to be `event_id not in (select event_id from l1_extraction_results)` with no
#: discriminator, which was correct for exactly as long as L2 was the only writer. Migration 0080
#: moved the table to Layer 1 and L1 v2 began filing every event it extracts — so the guard
#: silently inverted its meaning: the events Layer 1 understood BEST became the events Layer 2
#: refused to drain. Nothing errors in that state. The sweep reports a clean run, the drain
#: returns `processed: 0`, and the graph simply stops growing — which makes switching activation
#: on strictly WORSE than leaving it off, rather than incomplete.
#:
#: `profile_id is null` is the discriminator rather than a name pattern or a date cutoff because
#: it is a property of the WRITER, not of a convention either side could drift from.
_L2_OWN_EXTRACTIONS = ("select event_id from l1_extraction_results "
                       "where org_id=:o and profile_id is null")


def _pull(store: GraphStore, org_id: str, limit: int):
    """Pull only events that crossed Layer 1's QES publication boundary.

    One event may publish several signals; the lateral fold chooses its highest-importance live
    signal for confidence/domain metadata and retains every signal type.  All signals for one
    event point at the same cached extraction, so the expensive artifact is joined once.
    """
    with store.engine.connect() as c:
        return c.execute(text(
            "select se.event_id, se.source, se.object_type, se.actor->>'email' as sender, "
            "se.actor->>'name' as sender_name, "
            "se.occurred_at, se.source_object_id, se.triage_lane, se.internal_kind, "
            "se.parent_object_id, se.domain_hints, "
            "q.qes_confidence_bp, q.qes_signal_types, q.qes_domain_hints, "
            "xr.output as qes_output, "
            "rp.enc_content, "
            "pc.clean_text as prepared_text "
            "from source_events se "
            "join raw_payloads rp on rp.event_id = se.event_id "
            "left join prepared_content pc on pc.event_id = se.event_id and pc.org_id = se.org_id "
            "join lateral ("
            "  select max(qs.confidence_bp)::int as qes_confidence_bp, "
            "         array_agg(distinct qs.signal_type order by qs.signal_type) as qes_signal_types, "
            "         (array_agg(qs.domain_hints order by qs.importance_bp desc, qs.signal_id))[1] "
            "             as qes_domain_hints, "
            "         (array_agg(qs.extraction_ref order by qs.importance_bp desc, qs.signal_id))[1] "
            "             as qes_extraction_ref "
            "  from qualified_signals qs "
            "  where qs.org_id = se.org_id and qs.event_id = se.event_id "
            "    and qs.state = 'active'"
            ") q on q.qes_extraction_ref is not null "
            "left join l1_extraction_results xr on xr.org_id = se.org_id "
            "     and xr.processing_key = q.qes_extraction_ref "
            "where se.org_id=:o and se.outcome='emitted' "
            # RESTORED. The QES rewrite of this query dropped this clause and left the constant,
            # its eighteen-line rationale and the other consumer (`api/routes._pending_count`)
            # standing — so the drain and the progress bar disagreed again, which is the exact
            # drift the discriminator was written to end. The new lateral join is about L1's
            # extraction (`profile_id` NOT null, reached through `qes_extraction_ref`); this
            # clause is about L2's OWN (`profile_id is null`, written by `GraphStore.cache_set`).
            # They are different rows and the second one is what stops the model being paid twice
            # for one message on every sweep, for ever.
            f"and se.event_id not in ({_L2_OWN_EXTRACTIONS}) "
            "and se.event_id not in (select event_id from l2_processing_runs "
            "                        where org_id=:o and status in ('done','parked')) "
            "order by coalesce(se.triage_lane, 'P3') asc, se.occurred_at asc "
            "limit :lim"), {"o": org_id, "lim": limit}).fetchall()


def _record_done(store, org_id: str, event_id: str) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into l2_processing_runs (org_id, event_id, status, attempts) "
            "values (:o,:e,'done',1) on conflict (org_id, event_id) do update set "
            "status='done', attempts=l2_processing_runs.attempts+1, updated_at=now()"),
            {"o": org_id, "e": event_id})


def _record_failure(store, org_id: str, event_id: str, error: str | None) -> int:
    """Upsert a transient failure, bump attempts, and PARK (terminal) once the cap is hit so the
    drain loop stops re-charging the LLM. Returns the new attempt count."""
    with store.engine.begin() as c:
        n = c.execute(text(
            "insert into l2_processing_runs (org_id, event_id, status, attempts, last_error) "
            "values (:o,:e,'failed',1,:err) on conflict (org_id, event_id) do update set "
            "attempts=l2_processing_runs.attempts+1, last_error=:err, updated_at=now() "
            "returning attempts"), {"o": org_id, "e": event_id, "err": (error or "")[:400]}).scalar()
        if int(n) >= _MAX_ATTEMPTS:
            c.execute(text("update l2_processing_runs set status='parked', "
                           "last_error=coalesce(:err,'model_unavailable') where org_id=:o and event_id=:e"),
                      {"o": org_id, "e": event_id, "err": (error or "model_unavailable")[:400]})
    return int(n)


def _record_hold(store, org_id: str, event_id: str, reason: str) -> None:
    """Persist recoverable L1->L2 incompleteness without consuming the failure retry budget."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into l2_processing_runs (org_id, event_id, status, attempts, last_error) "
            "values (:o,:e,'held',0,:reason) on conflict (org_id, event_id) do update set "
            "status='held', last_error=:reason, updated_at=now()"),
            {"o": org_id, "e": event_id, "reason": reason[:400]})


# =================================================================================================
# L-4 · THE DRAIN LOOP GUARDS — a bounded fixpoint over Layer 2's one internal feedback loop
# =================================================================================================
#
# Doc 13 names the cycle and this is it, verbatim from the plan:
#
#     new event joins a situation -> the member set changes -> importance is recomputed (BLG-18)
#     -> lifecycle is re-derived (BLG-19) -> an observation is emitted -> observations are an
#     INPUT to correlation -> re-correlation -> back to the top
#
# "Left unguarded this does not terminate. Worse, it does not OBVIOUSLY not terminate — it looks
# like a slow sweep, then a slower one."
#
# THE PASS IS THE SWEEP. Doc 13's own L-1 row reads "drain loop — one pass per sweep", and that is
# what `process_pending` is: it drains, derives, scores and re-ranks exactly once. So the fixpoint
# iterates ACROSS sweeps, and the guard is a hash of the state at the end of one sweep compared
# with the hash at the start of the next. The alternative — running the derive/score block three
# times inside one call — costs three times the analytic budget on every healthy tenant in order
# to detect a condition that is a design defect rather than a runtime state, and doc 13 is explicit
# that publishing a slightly-stale situation is the correct trade ("a slightly-stale situation is
# recoverable on the next drain while a hung worker is not").
#
# WHAT IS HASHED, AND WHAT DELIBERATELY IS NOT. Doc 13 hashes "situations, memberships, lifecycle
# states". Scores are NOT in that list and must not be: importance is composed against `eval_time`,
# so on a perfectly quiet org it drifts every sweep, and a hash that included it would report every
# tenant in the system as non-convergent within three sweeps. An alert that fires on everyone fires
# on no one.
#
# WHAT COUNTS AS A PASS. Only movement with NO NEW INPUT. A sweep that drained events and changed
# the state has an external cause and resets the counter; a sweep that drained nothing and still
# moved the state is a turn of the fixpoint. Without that distinction the counter measures how busy
# a tenant is rather than whether their derivations settle.

#: Doc 13, L-4. Three consecutive no-input sweeps that still move the state is a genuine derivation
#: cycle, and doc 13 is emphatic that `l2_convergence_exceeded` "is an alert, not a log line — a
#: tenant that never converges has a genuine derivation cycle, and that is a design defect to find,
#: not a runtime condition to tolerate."
MAX_PASSES = 3

#: How many still-moving situation ids travel in the breach receipt. Doc 13 asks for "the
#: situations still changing" and this is a `jsonb` column on a one-row-per-org table, so the
#: receipt is capped rather than an unbounded dump of a large tenant's situation table.
MAX_UNCONVERGED_REPORTED = 20

#: The semantic fingerprint of doc 13's three things. `md5` over an ORDERED, delimited projection:
#: `string_agg` without `order by` is not deterministic across plans, and a hash that changed with
#: the planner's mood would report convergence as failure on a big enough tenant.
#:
#: The columns are the state, never the scores and never a timestamp. `context_situations` gives
#: identity, lifecycle status and anchor; `context_correlation_members` gives membership;
#: `context_node_lifecycle` gives the per-node state BLG-19 derives. `importance_bp`,
#: `confidence_*` and every `updated_at` are excluded on purpose — see the block comment above.
_CONVERGENCE_HASH_SQL = """
select md5(
    coalesce((select string_agg(situation_id || '|' || status || '|' || anchor_node_id, ',' order by situation_id)
              from context_situations where org_id = :o), '')
    || '#' ||
    coalesce((select string_agg(correlation_id || '|' || event_id, ',' order by correlation_id, event_id)
              from context_correlation_members where org_id = :o), '')
    || '#' ||
    coalesce((select string_agg(node_id || '|' || lifecycle, ',' order by node_id)
              from context_node_lifecycle where org_id = :o), '')
) as state_hash
"""


def _convergence_state_hash(store: GraphStore, org_id: str) -> str | None:
    """Doc 13's `hash(situations, memberships, lifecycle states)`. `None` if it cannot be read.

    Never fatal and never a reason to skip the drain: a guard that could stop ingestion would be a
    worse failure than the loop it watches for. A `None` here disables the check for this sweep and
    leaves the stored counter exactly as it was, so a transient read error cannot manufacture a
    breach or silently clear one.
    """
    try:
        with store.engine.connect() as c:
            return c.execute(text(_CONVERGENCE_HASH_SQL), {"o": org_id}).scalar()
    except Exception:      # noqa: BLE001 — a convergence probe must never break ingestion
        return None


def _unconverged_situations(store: GraphStore, org_id: str, since) -> list[str]:
    """The situation ids that moved during this sweep — doc 13's "the situations still changing".

    Read off `computed_at`, which is exactly the column the state hash refuses to hash: as an
    ORDERING it says which rows a sweep touched, which is what a receipt needs; as an INPUT to the
    fingerprint it would make every sweep look like a change. Capped, ordered, and best-effort.
    """
    try:
        with store.engine.connect() as c:
            return [r[0] for r in c.execute(text(
                "select situation_id from context_situations "
                "where org_id = :o and computed_at >= :since "
                "order by computed_at desc, situation_id limit :n"),
                {"o": org_id, "since": since, "n": MAX_UNCONVERGED_REPORTED})]
    except Exception:      # noqa: BLE001 — a receipt is never a reason to fail a sweep
        return []


def _record_convergence(store: GraphStore, org_id: str, *, before: str | None, after: str | None,
                        drained: bool, sweep_at) -> dict:
    """The bounded fixpoint's bookkeeping. Returns the ledger entry this sweep produced.

    Three outcomes, and the middle one is the whole reason the counter exists:

    * `after == before` — the sweep changed nothing. CONVERGED; the counter resets to zero and any
      standing breach is cleared, because `exceeded_at` must always mean "still breaching" rather
      than "breached once, in 2024".
    * the state moved and this sweep DRAINED — an external cause. Also a reset: new evidence is
      supposed to move the graph, and counting it would measure activity, not convergence.
    * the state moved with NO new input — a turn of the fixpoint. `passes` increments, and at
      `MAX_PASSES` the breach is recorded with both hashes and the situations still moving.

    Doc 13: *"Do NOT keep iterating. Publish what pass 3 produced."* Across sweeps that means the
    sweep is not repeated and nothing is rolled back — what this pass produced is published, and
    the breach is raised so a human finds the cycle. Refusing to drain would be strictly worse: it
    would stop a tenant's ingestion over a derived-view defect.
    """
    if before is None or after is None:
        return {"checked": False}

    converged = after == before
    reset = converged or drained
    with store.engine.begin() as c:
        if reset:
            passes = 0
            c.execute(text(
                "insert into l2_convergence (org_id, state_hash, passes, last_pass_at, "
                "exceeded_at, detail) values (:o, :h, 0, :at, null, '{}'::jsonb) "
                "on conflict (org_id) do update set state_hash = excluded.state_hash, "
                "passes = 0, last_pass_at = excluded.last_pass_at, exceeded_at = null, "
                "detail = '{}'::jsonb"), {"o": org_id, "h": after, "at": sweep_at})
        else:
            passes = int(c.execute(text(
                "insert into l2_convergence (org_id, state_hash, passes, last_pass_at) "
                "values (:o, :h, 1, :at) on conflict (org_id) do update set "
                "state_hash = excluded.state_hash, passes = l2_convergence.passes + 1, "
                "last_pass_at = excluded.last_pass_at returning passes"),
                {"o": org_id, "h": after, "at": sweep_at}).scalar() or 1)

    exceeded = passes >= MAX_PASSES
    entry = {"checked": True, "converged": converged, "passes": passes, "exceeded": exceeded,
             "state_hash": after}
    if exceeded:
        still_moving = _unconverged_situations(store, org_id, sweep_at)
        detail = {"state_hash_before": before, "state_hash_after": after,
                  "situations_still_changing": still_moving, "max_passes": MAX_PASSES}
        try:
            with store.engine.begin() as c:
                c.execute(text(
                    "update l2_convergence set exceeded_at = :at, detail = cast(:d as jsonb) "
                    "where org_id = :o"),
                    {"o": org_id, "at": sweep_at, "d": json.dumps(detail, sort_keys=True)})
        except Exception:      # noqa: BLE001 — the alert below is the part that must not be lost
            pass
        from genios_engine.platform.logging import get_logger
        # An ALERT, not a log line — doc 13's words. The name is stable and greppable so an
        # operator can page on it; the payload is the receipt doc 13 asks for.
        get_logger("genios.l2").error(
            "l2_convergence_exceeded org=%s passes=%s before=%s after=%s situations=%s",
            org_id, passes, before, after, still_moving)
        entry["situations_still_changing"] = still_moving
    return entry


def _safe_process_one(row, *, org_id, store, llm, crypto_key, internal_emails=frozenset(),
                      effective=None):
    """Isolation wrapper: ONE event's failure never aborts the batch (§L2 'drain every event')."""
    try:
        outcome, node = _process_one(row, org_id=org_id, store=store, llm=llm, crypto_key=crypto_key,
                                     internal_emails=internal_emails, effective=effective)
        return outcome, node, None
    except Exception as e:      # noqa: BLE001 — quarantine this event, keep the batch alive
        return "error", None, str(e)[:400]


def _effective_packs(store: GraphStore, org_id: str, registry) -> dict | None:
    """Every active pack's effective config, keyed by pack id.

    Returns None when no registry is wired or nothing resolves — the extractor then falls back
    to the engine's own vocabulary rather than extracting nothing, so an unmigrated caller keeps
    working exactly as before.
    """
    if registry is None:
        return None
    try:
        with store.engine.connect() as c:
            pack_ids = [r[0] for r in c.execute(text(
                "select pack_id from tenant_packs where org_id=:o and state in ('active','shadow')"),
                {"o": org_id})]
        out = {}
        for pid in pack_ids:
            eff, _ = registry.effective(org_id, pid)
            if eff:
                out[pid] = eff
        return out or None
    except Exception:      # noqa: BLE001 — vocabulary is an enrichment, never a reason to stop
        return None


def process_pending(*, org_id: str, store: GraphStore, llm: LLMClient | None,
                    crypto_key: str, max_total: int = 5000, registry=None,
                    eval_time=None) -> dict:
    """Drain, derive, and sample. `eval_time` is the sweep's ONE instant.

    The clock is read here, at the process boundary, and nowhere below it. Every measured pass
    this function calls takes the instant as a parameter — the situation refresh already did, and
    L2.4.2's sampler requires it — so a sweep is replayable: the same graph at the same
    `eval_time` produces the same situations and byte-identical metric points, which is what makes
    a re-run an overwrite rather than a second, disagreeing observation of the same period.

    (The passes below are located by name in a couple of source-reading tests. Naming one of them
    in this docstring would make `source.index(...)` land here instead of on the call, so they are
    described rather than spelled.)
    """
    from datetime import datetime as _dt
    from datetime import timezone as _tz
    sweep_at = eval_time or _dt.now(_tz.utc)
    # L-4 · the fixpoint's "before". Taken BEFORE anything in this function writes, so the
    # comparison at the bottom is over what THIS sweep did and not over what the last one left.
    # See the block comment above `MAX_PASSES` for why the pass is the sweep.
    state_hash_before = _convergence_state_hash(store, org_id)
    out: Counter = Counter()
    affected: set[str] = set()
    seen: set[str] = set()                            # attempted THIS call → no intra-call re-pull
    done = 0
    internal_emails = _internal_emails(store, org_id)  # once per drain, not per event
    # The tenant's pack vocabulary, resolved ONCE per drain for the same reason. A tenant is
    # bound to several packs (sales + general) and the extractor must see the union: a field
    # named by one pack and missed because only the other was consulted is the same silent loss
    # the seam fix exists to prevent.
    effective = _effective_packs(store, org_id, registry)
    while done < max_total:
        rows = [r for r in _pull(store, org_id, _BATCH) if r.event_id not in seen]
        if not rows:
            break
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:   # parallel graph commits
            results = list(ex.map(
                lambda r: _safe_process_one(r, org_id=org_id, store=store, llm=llm,
                                            crypto_key=crypto_key,
                                            internal_emails=internal_emails,
                                            effective=effective), rows))
        for row, (outcome, node, err) in zip(rows, results):
            seen.add(row.event_id)
            out[outcome] += 1
            if node:
                affected.add(node)
            if outcome in ("error", "extract_failed"):
                n = _record_failure(store, org_id, row.event_id, err)
                out["parked_model_unavailable" if n >= _MAX_ATTEMPTS else "retry_pending"] += 1
            elif outcome.startswith("held_"):
                _record_hold(store, org_id, row.event_id, outcome)
            elif outcome in _DONE_OUTCOMES:
                _record_done(store, org_id, row.event_id)
        done += len(rows)

    for node_id in affected:                          # B9 rebuild affected read models
        build_entity_360(store, org_id=org_id, node_id=node_id)
    # derived.* — engagement / sentiment / momentum. Written HERE, after extraction and before
    # anything reasons, because they are counts over the observations this drain just committed.
    # Every rule and capability that reads them was previously gated on a field no writer existed
    # for, so the deep sales rules never fired and all 18 compiled capabilities returned
    # INSUFFICIENT_CONTEXT. Never fatal: a derive failure costs one cycle of freshness, and the
    # next drain recomputes from the same graph.
    derived_rows = 0
    # ONE BOUNDARY PER PASS, and there used to be ONE FOR ALL SEVEN.
    #
    # A failure in `compute_derived` — the first of them — skipped every pass behind it, and with
    # them every `_reconcile` in the sweep, so nothing closed for as long as the failure lasted.
    # `refresh_situations` and `detect_resolutions` still ran afterwards, so the sweep reported a
    # clean run: no exception reached the caller and the counts it prints are of the passes that
    # DID run. A tenant could lose its whole state-reading layer for a week and every log line
    # would look ordinary.
    #
    # The outer boundary stays as a backstop; these are the ones that keep a single bad pass from
    # taking the six behind it.
    #
    # RUNS EVERY PASS, not only when the drain committed something.
    #
    # This block used to sit behind `if done or affected`, and that was wrong for the half of it
    # that is measured against a CLOCK rather than against an event. `waiting.py` derives how many
    # days a thread has gone unanswered; `periodic.py` counts a moving window; the state readings
    # in `outreach_situations.py` are built on both. None of those change because new mail
    # arrived — they change because time passed, which is the entire premise of deriving silence.
    #
    # The consequence was visible: a counterparty who went quiet had their day count frozen at
    # whatever it was on the last drain that happened to have new mail, so a card could sit
    # reading "30 days waiting" for a week. An org with a quiet inbox — exactly the org whose
    # silence is worth surfacing — got the stalest numbers.
    #
    # The event-derived passes are windowed too (`_RECENT_DAYS` / `_BASELINE_DAYS` slide with the
    # clock), so they belong on the same schedule. Cost is a handful of bulk queries per org per
    # sweep, which is what the passes were already designed for — no per-node round-trips.
    try:
        from functools import partial

        from genios_engine.context.derived import compute as compute_derived
        from genios_engine.context.derived import compute_account_view, compute_deal_view
        # Bind the sweep clock once so every derived writer observes the same instant while
        # preserving the established two-argument invocation contract used by the drain gate.
        compute_derived = partial(compute_derived, now=sweep_at)
        derived_rows = (compute_derived(store, org_id)
                        + compute_deal_view(store, org_id, now=sweep_at))
        # ACCOUNT level, after the person level and for the same reason: it is an aggregate
        # of the facts the two passes above just committed, so it has to run behind them.
        # 33 of 40 companies on the design partner's org hold no fact row at all. The
        # reasoner still SEES their people's facts — `adapters/native.py` borrows a missing
        # root field from the 1-hop neighbourhood — so this is not the difference between
        # reasoning and not reasoning; it is the difference between the account's own
        # aggregate and whichever neighbour was written last, and between a row existing for
        # every non-reasoner reader and not. See `compute_account_view` for the measurement.
        try:
            derived_rows += compute_account_view(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "account view pass failed for org=%s — later passes still run", org_id)
        # WAITING state — the only facts in this layer derived from what did NOT happen.
        # Runs behind the person and account passes because it reads the same thread state
        # they commit, and ahead of the situation refresh below so a situation's coverage can
        # see them. Everything above records an event; nothing records silence, which is the
        # shape of most of what a user actually wants told to them.
        from genios_engine.context.waiting import compute_waiting
        try:
            derived_rows += compute_waiting(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "waiting pass failed for org=%s — later passes still run", org_id)
        # PERIOD aggregates and their situations, in the same pass and for the same reason:
        # they are computed from facts that now exist, they are cheap, and a period read that
        # is only refreshed by a separate schedule is a period read that is always stale.
        # Twenty-two authored capabilities are reachable only through these.
        from genios_engine.context.periodic import refresh_period_situations
        try:
            derived_rows += refresh_period_situations(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "period pass failed for org=%s — later passes still run", org_id)
        # The seven correspondence-derived support readings, in the same pass and for the
        # same reason: a first-response clock, an aging item and a repeat contact are all
        # computed from the thread state and open loops THIS drain just committed, and a
        # reading refreshed only by a separate schedule is a reading that is always stale.
        # Seven authored situation types were unroutable until these existed.
        from genios_engine.context.support_situations import refresh_support_situations
        try:
            derived_rows += refresh_support_situations(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "support pass failed for org=%s — later passes still run", org_id)
        # The one non-mail channel the graph actually holds. `demo` was unroutable not because
        # the corpus was thin but because a meeting with an outside party — 48 of them on the
        # design partner's org — reached no situation at all. Same pass, same reason: it reads
        # the calendar facts this drain just committed.
        from genios_engine.context.meeting_touch import refresh_channel_touch_situations
        try:
            derived_rows += refresh_channel_touch_situations(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "meeting touch pass failed for org=%s — later passes still run", org_id)
        # THE STATE READINGS, last of the derived passes because they read what every pass
        # above just wrote — the waiting arithmetic in particular. These are the only
        # situations in the system named after what is HAPPENING rather than who it is
        # about, which is what gives an authored "we wrote and nobody answered" capability
        # something to route on. Same self-correcting contract as the support readings: a
        # finding that stops being true is resolved by fact on the next sweep.
        from genios_engine.context.outreach_situations import refresh_state_situations
        try:
            derived_rows += refresh_state_situations(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "state readings pass failed for org=%s — later passes still run", org_id)
        # The records reading, in the same pass and for the same reason: a document's control
        # gaps are computed from the file metadata THIS drain just projected, and the copy
        # clustering has to re-run whenever a file lands or a second copy of one appears. It
        # costs two queries and returns immediately on an org with no file store connected.
        from genios_engine.context.document_register import refresh_document_situations
        try:
            derived_rows += refresh_document_situations(store, org_id, now=sweep_at)
        except Exception:      # noqa: BLE001 — one derived pass must not skip the rest
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "documents pass failed for org=%s — later passes still run", org_id)
    except Exception:      # noqa: BLE001 — derived view, recomputed next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("derived fact refresh failed for org=%s", org_id)

    # L2.3.5 · contract -> invoice/payment/spend.  This runs after structured/event projection
    # has populated the graph and before situations are refreshed, so finance situations read
    # this sweep's attribution.  The correlator never converts currency or guesses through an
    # unresolved vendor/reference; every decision is persisted with its input fact-version ids.
    resource_correlation: dict = {}
    try:
        from genios_engine.context.correlation_resource import refresh_contract_spend
        resource_correlation = refresh_contract_spend(
            store, org_id, eval_time=sweep_at).as_record()
        derived_rows += int(resource_correlation.get("summaries_written", 0))
    except Exception:      # noqa: BLE001 — a derived correlation retries from graph state
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception(
            "contract-spend correlation failed for org=%s", org_id)
    # L2.3.9 · CROSS HISTORY — what happened the LAST time this anchor was here.
    #
    # AFTER the correlations for this sweep are written, because it reads the generation chain
    # and the newest generation must be in it. Before situations refresh, so an authored `when:`
    # can gate on `derived.history.times_seen` in the same drain rather than one behind.
    #
    # ITS OWN BOUNDARY, like every pass above: a history read failing must not cost the sweep the
    # contract-spend correlation that follows it.
    try:
        from genios_engine.context.correlation_history import publish_histories
        derived_rows += publish_histories(store.engine, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — a derived correlation retries from graph state
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception(
            "cross-history correlation failed for org=%s", org_id)

    # RETENTION on `metric_history` (L2.4.1). The analytic stratum's history table is the one
    # store in L2 that only ever APPENDS, which is the exact shape that put this database into
    # read-only once before, so its 24-month horizon is enforced on a path that actually runs
    # rather than declared in a comment. Here, and not on a schedule, for two reasons: the Celery
    # broker is a quota-limited Upstash instance and this layer's rule is to prefer in-process
    # work on a sweep that already happens; and the drain is the only thing that knows an org is
    # active — an org that is not draining is not growing this table either.
    #
    # RUNS EVERY PASS, like the derived block above and for the same reason: retention is
    # measured against a CLOCK, not against an event, so an org whose inbox went quiet is exactly
    # the org whose oldest points would otherwise never expire. It costs one indexed probe
    # (`mh_retention`) when there is nothing to delete. Never fatal: a missed prune costs one
    # cycle of retention, and the next drain deletes the same rows.
    history_points_pruned = 0
    try:
        from genios_engine.context.analytic.history import prune_history_for_drain
        # `sweep_at`, not a fresh `now()`: the prune horizon and the sampler's period key are
        # computed from ONE instant, so a sweep cannot delete against one clock and write against
        # another — which at a month boundary is a point pruned and immediately rewritten.
        history_points_pruned = prune_history_for_drain(store, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — retention must never break ingestion
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("metric history prune failed for org=%s", org_id)

    # Attention refresh — L2 is the SOLE writer of context_attention. Full-org refresh:
    # recency decays even for untouched nodes, and it is a few bulk queries, not per-node
    # round-trips.
    #
    # RUNS EVERY PASS, and it used to sit behind `if done or affected:` — which contradicted the
    # sentence directly above it. Recency decaying for untouched nodes is precisely a CLOCK
    # quantity, so gating the refresh on new mail arriving froze every attention band on the one
    # kind of org whose quiet is the finding: nothing decayed, nothing re-ranked, and the bands a
    # reader sees were whatever the last day with inbound mail left behind. Same argument, and
    # the same fix, as the derived block above.
    #
    # THE HANDLER LOGS. It was a bare `except Exception: pass` — the only silent one in
    # `process_pending` — so a refresh that failed every sweep for a month would have looked
    # exactly like one that ran.
    attention_rows = 0
    try:
        from genios_engine.context.attention import refresh_attention
        attention_rows = refresh_attention(store, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — attention is an ordering hint, never fatal
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("attention refresh failed for org=%s", org_id)

    # Situations are rebuilt AFTER attention, from correlations the drain just extended.
    # Every value is derived, so a failure here costs a refresh cycle, not data — the
    # next drain recomputes it. Never fatal: a situation view being briefly stale must
    # not stop events from landing.
    #
    # RUNS EVERY PASS, for the reason the derived block above already records and this one used
    # to ignore. `decide_lifecycle` computes THREE clock-derived transitions —
    # `confidence_freshness`, active→dormant at 45 days, resolved→archived at 180 — and dormancy
    # is the ONLY mechanism that stops a stale situation compiling into a card. Gated on new
    # mail, a six-month-dead situation on a quiet tenant stayed `active` and kept reaching Layer
    # 3 forever, and a resolved one never left the working set. `detect_resolutions` below cannot
    # cover the gap: it `continue`s on STATEMENT_NONE, which is every situation on a quiet org.
    situation_rows = 0
    try:
        from genios_engine.context.situations import refresh_situations
        situation_rows = refresh_situations(store, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — derived view, rebuilt next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("situation refresh failed for org=%s", org_id)

    # THE OTHER FIVE SIXTHS OF THE TABLE. `refresh_situations` above derives everything from
    # `context_correlations`, so a situation whose correlation id is SYNTHETIC — the state
    # readings, the period sweep, meeting touch, the document register — never reached
    # `decide_lifecycle` at all. The block above claims dormancy is the only thing that stops a
    # stale situation compiling into a card; that was true only for the rows it could see, and
    # everything else stayed `active` forever and was served to Layer 3 on every sweep.
    #
    # Clock transitions only, and never a row somebody decided about. Same never-fatal contract
    # as the refresh it follows.
    try:
        from genios_engine.context.situations import age_uncorrelated_situations
        situation_rows += age_uncorrelated_situations(store, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — derived lifecycle, retried next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("uncorrelated ageing failed for org=%s", org_id)

    # L2.7.7-U1 · M-4 RESOLUTION DETECTION — the third way a situation can end.
    #
    # PLACED HERE, immediately behind the situation refresh, because it re-derives the statuses
    # that refresh just wrote: `refresh_situations` rebuilds every row from graph state and knows
    # nothing about resolution claims, so a statement-closed situation would come back ACTIVE if
    # this ran first. Running it second means one status write per sweep, in the right order.
    #
    # UNCONDITIONAL, unlike the two blocks above. Not because it always costs a model call — it
    # almost never does: the gate refuses every situation with no unexamined message, which on a
    # quiet org is all of them — but because the DETERMINISTIC half must run anyway. The claim
    # ledger is re-reduced on every sweep, and that is what makes a stated resolution reversible:
    # a contradiction recorded yesterday reopens the situation today even if today's sweep drained
    # nothing and could not afford a call.
    #
    # `internal_emails` is HANDED DOWN rather than re-derived. The drain already computed "who is
    # us" once, and that set decides whether a speaker is org-internal (0.8 weight) or an external
    # counterparty (0.6) — two answers to that question is how a vendor's "all done on our side"
    # would acquire the authority to close a live thread.
    #
    # Never fatal, exactly like the refresh above: this pass writes a derived lifecycle, and a
    # sweep that could not run it leaves every situation where it was. The cost of the failure is
    # one unnecessary nudge, which is the same direction every threshold inside it leans.
    resolutions = {}
    try:
        from genios_engine.context.lifecycle import detect_resolutions
        resolutions = detect_resolutions(store, org_id, llm=llm, eval_time=sweep_at,
                                         internal_emails=internal_emails).as_record()
    except Exception:      # noqa: BLE001 — a missed resolution must never break ingestion
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception(
            "resolution detection failed for org=%s", org_id)

    # L2.4.2 · THE METRIC SAMPLER. `graph_facts` has just been overwritten with what is true NOW;
    # this is the pass that records what was true THEN. Nothing else in the system writes
    # `metric_history`, so "engagement is declining" — the phrase in six of the six customer
    # expectations L2.4 exists for — has no input at all unless this line runs.
    #
    # PLACED HERE, behind the situation refresh, because BLG-07 row 2 samples a node DAILY while
    # it anchors an active situation, and reading `context_situations` before the refresh would
    # apply this sweep's cadence to last sweep's situations.
    #
    # UNCONDITIONAL, unlike the two blocks above, and for the same reason the derived pass is:
    # every one of the twelve trended metrics is measured against a CLOCK — a 28-day count, an
    # age, a days-since — so they change because time passed, not because new mail arrived. An
    # org with a quiet inbox is exactly the org whose decline is worth surfacing, and gating this
    # on `done or affected` would freeze its series at the last sweep that happened to have mail.
    #
    # `eval_time` is passed down rather than read inside: the sampler takes no clock, so sampling
    # the same graph twice at one instant produces byte-identical points and the primary key
    # turns the second write into an overwrite instead of a duplicate period. The per-sweep point
    # budget lives in the sampler (L2.4.2-U3) — this call cannot become a 500k-row insert.
    #
    # THE BACKFILL RUNS FIRST, and only on the sweep that finds this tenant's history empty.
    # BLG-08 needs four points and BLG-13 needs six, so without it a new org's every trend reads
    # `INSUFFICIENT_HISTORY` for its first four to six weeks — a seven-day pilot would end before
    # the analytic stratum said one thing. L1 already holds an 18-month event ledger; this is the
    # line that turns it into 18 months of computable series. Guarded on existence rather than a
    # marker (see `backfill_history_for_drain`), so it costs one index probe per drain thereafter.
    #
    # THE BACKFILL READS ITS OWN, WIDER SNAPSHOT and the live sampler keeps reading its own. The
    # sampler's window is 400 days and every metric it takes fits in 90; the backfill needs
    # eighteen months, so one shared read would cap the reconstruction at thirteen months and the
    # five it could not see would look like a quiet customer rather than a window that was too
    # small. That second read happens once in a tenant's life — after it, the guard is one index
    # probe — so the steady-state cost of this seam is unchanged.
    #
    # EVERY BUDGETED PASS BELOW REPORTS WHERE IT STOPPED, into `budgets`. Each of these passes
    # caps what one sweep may read or write, and until this ledger existed every one of those
    # ceilings was computed and then DISCARDED at this seam — `ComparisonSweep.budget_exhausted`
    # was read as `.facts` and thrown away. An org above a budget therefore looked exactly like an
    # org that had nothing to do, so the tail it never heard about was invisible to the operator
    # as well as to the tenant. Defaults are False and are set BEFORE the try blocks: a pass that
    # raised must not leave its own name out of the ledger, because a missing key reads as "fine".
    budgets: dict[str, bool] = {"metric_points": False, "anomaly": False, "cohorts": False,
                                "comparison": False, "dependency": False, "timeline": False}

    metric_points = 0
    history_backfilled = 0
    try:
        from genios_engine.context.analytic.sampler import (backfill_history_for_drain,
                                                            resolve_history_store, sample_org)
        metric_history = resolve_history_store(store)
        history_backfilled = backfill_history_for_drain(store, org_id, eval_time=sweep_at,
                                                        history=metric_history)
        sampled = sample_org(store, org_id=org_id, eval_time=sweep_at, history=metric_history)
        metric_points = sampled.written
        budgets["metric_points"] = sampled.budget_exhausted
    except Exception:      # noqa: BLE001 — a missed reading costs one period of a series, never
                           # an event. The next sweep resamples; ingestion must keep flowing.
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("metric sampling failed for org=%s", org_id)

    # L2.4.3 · THE TREND COMPUTER. The sampler above has just recorded what was true THIS period;
    # this is the pass that turns the accumulated periods into the word "declining" and writes it
    # back as `derived.trend.<metric>` so L3 and L4 read it like any other fact. Without this line
    # the trend computer is a function nothing calls, and no card can say a metric is moving.
    #
    # IMMEDIATELY AFTER THE SAMPLER, and on the same `sweep_at`: the trend reads its series with
    # `as_at=sweep_at`, so a sweep that sampled against one instant and trended against another
    # would compute this period's direction from a series that excludes the point it just wrote.
    #
    # BOUNDED BY CONSTRUCTION, which matters more here than anywhere else in this function. The
    # write is a version-keyed upsert into `graph_facts` (`fv_trend_<node>_<field>`), so a sweep
    # that runs twice in one period overwrites one row rather than appending two — the append
    # shape is what took `expertise_packages` to 181 MB and put this database into read-only. The
    # READ is capped at `MAX_TREND_FACTS_PER_SWEEP` ordered pairs, so one sweep cannot become
    # fifty thousand dense series reads on a large tenant.
    #
    # NEVER FATAL: a missed refresh leaves last sweep's trend in place for one cycle and the next
    # drain recomputes it. Ingestion must keep flowing.
    trend_facts = 0
    try:
        from genios_engine.context.analytic.trend import refresh_trend_facts
        trend_facts = refresh_trend_facts(store, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("trend refresh failed for org=%s", org_id)

    # L2.4.8 · THE ANOMALY DETECTOR (BLG-13). The trend above says which way a metric is moving;
    # this pass says whether THIS period's reading is unlike the node's own recent normal. They
    # are different questions and the second is the earlier signal: an account can be top-quartile
    # against its cohort and flat on trend while this month's reading sits twenty MADs off its own
    # six-month baseline, which is the "flagged 30+ days early" case. Without this line the
    # detector is a function nothing calls.
    #
    # IMMEDIATELY AFTER THE TREND, and on the SAME `sweep_at`: it reads the same series with
    # `as_at=sweep_at`, so a sweep that sampled against one instant and judged against another
    # would compare this period's reading to a baseline that excludes the point it just wrote.
    #
    # BOUNDED, AND POINT-IN-TIME SAFE, which are two properties and used to be conflated into one.
    # The write goes through `analytic/publish.publish_derived_fact`: a verdict that has not moved
    # writes NOTHING, one that moves inside an ISO week is corrected in place, and one that moves
    # in a later week closes the old row and opens a new one — so growth is one row per (node,
    # metric) per week in which the verdict ACTUALLY CHANGED (the append shape is what took
    # `expertise_packages` to 181 MB and put this database into read-only), and March's verdict is
    # still what `read_graph(as_of=March)` returns after September's sweep. The old writer here
    # bought the bound by moving `valid_from`, which paid for it with the audit.
    #
    # The READ is capped at `MAX_ANOMALY_FACTS_PER_SWEEP` pairs, ordered by STALENESS rather than
    # by id, so an org above that ceiling has a tail that ROTATES instead of a tail that is dark
    # for ever — and `budgets["anomaly"]` says out loud that the ceiling was reached.
    #
    # NEVER FATAL: a missed refresh leaves last sweep's verdict in place for one cycle and the
    # next drain recomputes it. Ingestion must keep flowing.
    anomaly_facts = 0
    try:
        from genios_engine.context.analytic.anomaly import refresh_anomaly_facts
        anomaly_sweep = refresh_anomaly_facts(store, org_id, eval_time=sweep_at)
        anomaly_facts = anomaly_sweep.facts_written
        budgets["anomaly"] = anomaly_sweep.budget_exhausted
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("anomaly refresh failed for org=%s", org_id)

    # L2.4.4 · THE COHORT PASS. The two passes above answer "what was true then" and "which way is
    # it moving"; this one decides WHO the reading is compared against. Without it, "your close
    # rate is 22%" never becomes "22% against a peer median of 31%", because no population is
    # declared to take a median of — cohort membership is the input every comparison in L2.4.5 and
    # L2.4.6 reads.
    #
    # PLACED HERE, behind the sampler and the trend, because the shipped quartile families are cut
    # from the facts this drain just derived and membership is evaluated against the same
    # in-memory snapshot: cutting boundaries from one read and membership from another would let a
    # node sit outside every quartile of the fact it was cut on.
    #
    # UNCONDITIONAL, like the two passes above and for the same reason: a predicate over
    # `within_days` or `node.tenure_days` changes because time passed, not because mail arrived,
    # so an org with a quiet inbox is exactly the org whose accounts age out of a cohort unseen.
    #
    # BOUNDED, and this is the pass where that needed the most care. `joined_at` is the ISO WEEK
    # key, so a node joining a cohort writes one row a week however many sweeps run in it and a
    # sweep replayed at one instant writes nothing new; hysteresis stops a flapping fact producing
    # a join/leave pair per sweep; a per-sweep write budget caps how many membership rows one org
    # may touch; and the same call prunes CLOSED stints older than 24 months, so there is no new
    # periodic task (the Celery broker is a quota-limited Upstash instance).
    #
    # M-9 — predicate authoring, this component's one model site — is deliberately unreachable
    # from here: it is on demand only and needs a human to approve what the model drafted. This
    # call takes no drafter, and the module's sweep path constructs no model client.
    #
    # NEVER FATAL: membership is state, not a queue. A failed pass leaves last sweep's membership
    # in place and the next drain re-evaluates the same predicates to the same answer.
    cohort_changes = 0
    try:
        from genios_engine.context.analytic.cohort import refresh_cohorts_for_drain
        cohort_sweep = refresh_cohorts_for_drain(store, org_id, eval_time=sweep_at)
        cohort_changes = cohort_sweep.changes
        budgets["cohorts"] = cohort_sweep.budget_exhausted
    except Exception:      # noqa: BLE001 — a stale cohort costs one cycle of freshness, never an
                           # event. Ingestion must keep flowing.
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("cohort refresh failed for org=%s", org_id)

    # L2.4.6 · THE PEER BASELINE PASS. The cohort pass above says WHO the reading is compared
    # against; this one computes WHAT NORMAL IS inside that population — the p10/p25/p50/p75/p90
    # ladder per (cohort, metric) — so "high" and "low" are said against something real rather
    # than against a number somebody guessed. It is also the input L1 v2's importance formula
    # (ALG-17) reads for the org's p50, on a path that cannot afford a percentile sweep per signal.
    #
    # AFTER the cohort pass, in the same sweep and against the same `sweep_at`: a ladder cut from
    # last week's membership and this week's readings is a distribution of a population that never
    # existed. One instant, one membership, one ladder.
    #
    # WITHIN ONE TENANT, ALWAYS. Every statement the call makes carries `org_id`, and doc 04
    # L2.4.6-U2 defers the cross-org baseline explicitly — `peer_baseline.cross_org_baseline`
    # exists in that module in order to refuse. A baseline under the k-anonymity floor is not
    # written at all: it is counted as a refusal, because a five-rung ladder over six members IS
    # the sorted population.
    #
    # BOUNDED: `computed_at` is the ISO WEEK START, so a week of drains writes one row per
    # (cohort, metric) however many sweeps run in it; the cross product is capped on both sides;
    # and the same call prunes ladders past the 24-month history horizon, so there is no new
    # periodic task (the Celery broker is a quota-limited Upstash instance).
    #
    # NEVER FATAL: a baseline is state, not a queue. A failed pass leaves last week's ladder in
    # place and the next drain recomputes the same numbers from the same points.
    baselines_written = 0
    try:
        from genios_engine.context.analytic.peer_baseline import refresh_baselines_for_drain
        baselines_written = refresh_baselines_for_drain(
            store, org_id, eval_time=sweep_at).written
    except Exception:      # noqa: BLE001 — a stale baseline costs one cycle of freshness, never
                           # an event. Ingestion must keep flowing.
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("peer baseline refresh failed for org=%s", org_id)

    # L2.4.5 · THE POPULATION COMPARATOR. The three passes above produce numbers; this is the one
    # that positions them. "your close rate is 22%" becomes "22%, the 31st percentile of the 47
    # accounts on your Growth plan", and the lookalike pass turns the shipped top-quartile
    # families into "these leads share traits with your best customers". Without this line the
    # comparator is a function nothing calls and every card is left holding a bare number.
    #
    # LAST IN THE ANALYTIC BLOCK, and against the same `sweep_at`: it reads the membership the
    # cohort pass just refreshed and the readings the sampler just wrote, so a position cut from
    # this week's population and last week's readings cannot happen. Point-in-time throughout —
    # every statement it makes is bounded by `observed_at <= sweep_at` and by the membership that
    # was open then, so replaying a past sweep reproduces that sweep's answer.
    #
    # BOUNDED the way the trend is: a version-keyed upsert on `graph_facts` keyed by (node,
    # field), so one row per node per metric for a position and one per node per reference cohort
    # for a lookalike, OVERWRITTEN every sweep rather than appended — the append shape is what
    # took `expertise_packages` to 181 MB and put this database into read-only. The pair, position
    # and lookalike budgets cap what one drain may touch; work not done is done by the next sweep.
    #
    # REFUSALS ARE WRITTEN TOO. A cohort that has since fallen below the five-member floor
    # overwrites its own "top decile" with "we cannot say", so a comparison the data no longer
    # supports retracts itself instead of sitting on a card forever.
    #
    # NEVER FATAL: a stale position costs one cycle of freshness, never an event.
    comparison_facts = 0
    try:
        from genios_engine.context.analytic.comparator import refresh_comparison_facts
        comparison_sweep = refresh_comparison_facts(store, org_id, eval_time=sweep_at)
        comparison_facts = comparison_sweep.facts
        budgets["comparison"] = comparison_sweep.budget_exhausted
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("comparison refresh failed for org=%s", org_id)

    # L2.3.8 · DEPENDENCY CORRELATION (BLG-05). The analytic block above says how a number is
    # moving and how it compares; this one says WHAT IS IN THE WAY. L1 v2 has published
    # `ExtractionResult.dependencies[]` — blocker, blocked, type, evidence — on every message it
    # extracts since that layer landed, and until this line NOTHING read it: L2.7.4's importance
    # modifier 3d (*N items blocked on this*) and Layer 4's Dependency unit both had no chain to
    # reason over, so a due date stayed a reminder that fires at whoever holds the deliverable
    # rather than at the node that is actually stuck.
    #
    # ON THE DRAIN, and UNCONDITIONAL like the passes above it. A chain changes because a blocking
    # was RESOLVED at least as often as because a new one was stated, so gating this on "did new
    # mail arrive" would freeze a resolved chain in place on exactly the quiet org whose stuck
    # work is worth surfacing. The read is one windowed, capped query per sweep — `baseline_reader`'s
    # shape — never a query per event.
    #
    # BOUNDED, and unusually strictly. Every row it writes is published under one `fv_dep:` prefix
    # and the sweep RETIRES that prefix for the org: a blocking that gets resolved has to
    # DISAPPEAR, or last week's chain sits on the node nagging about work that is done. Retired by
    # closing `valid_to`, never by deleting — and a blocking that is stated AGAIN months later
    # opens a NEW stint rather than reviving the closed one, which is the difference between a
    # timeline that reads `[March, April) ... [August, inf)` and one row claiming August was
    # always true.
    #
    # `eval_time` is passed down rather than read inside: it is the end of the read window, the
    # `valid_from` of every row this sweep OPENS and the `valid_to` of every row it closes — and
    # it never moves the `valid_from` of a row that already exists.
    #
    # NEVER FATAL: a missed pass leaves the previous sweep's chains for one cycle. Ingestion must
    # keep flowing.
    dependency_facts = 0
    try:
        from genios_engine.context.correlation_dependency import refresh_dependency_chains
        dependency_sweep = refresh_dependency_chains(store, org_id, eval_time=sweep_at)
        dependency_facts = dependency_sweep.facts_written
        budgets["dependency"] = dependency_sweep.budget_exhausted
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("dependency correlation failed for org=%s", org_id)

    # L2.3.4 · CROSS-TIMELINE CORRELATION (BLG-06). The dependency pass above says what is in the
    # way NOW; this one connects two moments MONTHS apart — "a partner said they'd revisit once you
    # had two enterprise references, and you closed the second eleven days ago". L1 v2 already
    # extracts `is_conditional` and `condition_text` on every commitment and nothing re-checked
    # them, so a conditional promise was parked at the moment it was made and never looked at
    # again; the two events share no thread, no window and no counterparty field, which is exactly
    # why no other join in this layer can find them.
    #
    # UNCONDITIONAL, and this is the pass where that matters most. A dormant condition becomes true
    # because the WORLD moved, never because new mail arrived about the promise. Gating it on
    # "did this thread get a reply" would guarantee the one surface Globe calls "the surface people
    # remember" fires only when it is no longer news.
    #
    # DETERMINISTIC ONLY. Doc 03 puts semantic condition parsing at M-5 and the group gate forbids
    # a model client anywhere in `context/correlation*.py`; both hold because dates, counts and
    # declared events are parsed by rule and everything else goes to a REVIEW QUEUE rather than
    # to a guess. An unparseable condition never auto-fires — a rhetorical aside turned into a
    # firing predicate is the failure mode that makes a founder stop reading our nudges.
    #
    # BOUNDED and CLOSED exactly like the pass above it: period-keyed rows under one `fv_tl:`
    # prefix, published through the shared writer so a re-confirmation costs nothing and a changed
    # answer supersedes rather than overwrites, and stale ones closed with `valid_to` rather than
    # deleted.
    #
    # NEVER FATAL: a missed pass leaves the previous sweep's conditions for one cycle.
    timeline_facts = 0
    try:
        from genios_engine.context.correlation_timeline import refresh_dormant_conditions
        timeline_sweep = refresh_dormant_conditions(store, org_id, eval_time=sweep_at)
        timeline_facts = timeline_sweep.facts_written
        budgets["timeline"] = timeline_sweep.budget_exhausted
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("timeline correlation failed for org=%s", org_id)

    # E-10 · THE GAP-REASON CORRECTION (doc 13). The trend pass above turned this org's series into
    # the word "declining". This pass asks the question that pass cannot: was the org even AWAKE in
    # the periods that produced it?
    #
    # Zero emails during Diwali week and zero emails because the Gmail token expired are the same
    # shape in `metric_history`, and a gap read as a decline is a false churn alarm about a real
    # customer, delivered with a confident receipt. Doc 13 calls it "the subtlest failure in Layer 2
    # and the one most likely to reach a customer"; doc 09's H6 gate makes it a number —
    # `DECLINING` trends across an org-wide silence window: 0.
    #
    # AFTER THE TREND AND BEFORE THE IMPORTANCE COMPOSER, and both halves of that are load-bearing.
    # After, because it corrects what `refresh_trend_facts` wrote, through that module's own
    # arithmetic and onto that module's own version-keyed row — one trend algorithm, one fact per
    # (node, metric). Before, because BLG-18's modifier 3a reads `derived.trend.*`, so a correction
    # landing after the composer would rank this sweep's situations on the claim we just withdrew.
    #
    # NEARLY FREE ON A HEALTHY ORG. It reads the event ledger for the trend window ONCE per grain;
    # if every period in it saw activity there is nothing to correct and the pass writes nothing at
    # all. The cost of the guard on a tenant that never goes quiet is one grouped query.
    #
    # DETERMINISTIC, NO MODEL, NO CALENDAR. Org-wide silence is measurable from the data itself,
    # which works for any org in any country with nothing to configure — and configuration is the
    # thing most likely to be missing on the tenant where it matters.
    #
    # NEVER FATAL: a missed correction leaves this sweep's uncorrected trend in place for one cycle
    # and the next drain re-examines the same window. Ingestion must keep flowing.
    gap_corrections = 0
    false_churn_withdrawn = 0
    # Its own key rather than a seventh entry in `budgets`. That ledger is X4's, and
    # `test_anomaly.test_the_drain_reports_the_budget_ledger_for_a_real_org` pins its key set
    # EXACTLY — deliberately, so a pass cannot quietly drop out of it. Adding a name would mean
    # editing another wave's ratchet to make my own pass fit, which is the wrong direction: the
    # ceiling is still reported, in a key that says whose it is.
    gap_budget_exhausted = False
    try:
        from genios_engine.context.analytic.gap_reason import refresh_gap_corrected_trends
        gap_sweep = refresh_gap_corrected_trends(store, org_id, eval_time=sweep_at)
        gap_corrections = gap_sweep.facts_corrected
        false_churn_withdrawn = gap_sweep.directional_claims_withdrawn
        gap_budget_exhausted = gap_sweep.budget_exhausted
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("gap-reason correction failed for org=%s", org_id)

    # L2.7.4 · SITUATION IMPORTANCE (BLG-18 steps 2..6). Every situation in the org gets its
    # composed 0..10000 ranking and the term-by-term record that explains it, written back to
    # `context_situations`. Without this line the composer is a function nothing calls and Layer 3
    # reasons over a tenant whose situations cannot be ordered — which is the state that put 193
    # of 223 signals on one number and left Layer 4's utility formula with nothing to rank on.
    #
    # LAST OF THE L2 PASSES, and the position is the whole design. Six modifiers read
    # `derived.trend.*`, `derived.cohort_position.*`, `derived.anomaly.*` and
    # `derived.dependency.blocked_count`; all four families are written by the passes ABOVE this
    # one. Placed any earlier it would compose against last sweep's analytic stratum, and on a
    # tenant's first sweep against an empty one — every modifier silent, the distribution flat,
    # and the cause nothing to do with the composer. It also has to run behind ALL SIX writers of
    # `context_situations` (this function calls five of them), because five never call
    # `score_situation` and would otherwise carry a null importance for ever.
    #
    # `sweep_at`, like every pass above: one instant for the whole drain, so the modifiers read
    # the same point-in-time graph the facts were written against and a replay reproduces it.
    #
    # BOUNDED: five bulk statements for the whole org plus one batched UPDATE, regardless of how
    # many situations the tenant holds — never a query per situation (`PERFORMANCE_HARDENING.md`
    # records that shape taking a Layer 3 pass past thirty minutes and blocking emission).
    #
    # NEVER FATAL: a failed pass leaves the previous sweep's ranking in place for one cycle and
    # the next drain recomputes it from the same graph. Ingestion must keep flowing.
    situations_ranked = 0
    try:
        from genios_engine.context.situation_bso import refresh_situation_importance
        situations_ranked = refresh_situation_importance(store, org_id, eval_time=sweep_at)
    except Exception:      # noqa: BLE001 — a derived view, recomputed on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("situation importance failed for org=%s", org_id)

    # X8 · L2.6 · THE PATTERN REGISTRY, IN SHADOW. `context/patterns` is a complete package —
    # registry, matcher, candidate builder, scorer, fire log, per-pattern activation guard — that
    # nothing on the drain called. `evaluate_org` was reachable only from
    # `POST /api/org/{id}/patterns/evaluate`, and `api/pattern_routes.py`'s own docstring says why
    # it stopped there: *"the drain call — one line in context/runner.process_pending — belongs to
    # the wave that switches situations over"*, because doc 06 requires the anchor path to keep
    # running for seven days first. X8 IS that wave. Its gate command
    # (`scripts/l2_shadow_diff.py --org <pilot> --days 7`) compares seven days of anchor-based
    # situations against seven days of pattern fires, and without this line `pattern_fires` is
    # empty on every tenant, so the comparison is a diff of the old path against nothing.
    #
    # GATED, AND THAT GATE IS THE POINT. `l2_v2_activation.patterns_enabled_at` (migration 0106) is
    # per tenant, in a table, exactly as doc 09's activation rule requires and for the reason it
    # gives — `use_domain_compiler=False` has been set in no environment since it was written and
    # has left 152 capabilities dark. Fail-closed: an unreadable switch is an OFF switch, so the
    # cost of every failure mode of the lookup is a tenant that does not accumulate fire evidence,
    # which is where every tenant is today.
    #
    # SHADOW BY CONSTRUCTION, twice over. `record_evaluation` writes ONLY the three `pattern_*`
    # tables migration 0100 creates; it does not touch `context_situations`, `context_correlations`
    # or anything `context/situations.py` owns, so the situations a founder sees are exactly the
    # ones the anchor path produced. And a fire is stamped `activated=false` unless somebody has
    # cleared that pattern through `patterns.store.activate`'s fire-rate guard, so nothing here
    # reaches a card.
    #
    # LAST OF THE L2 PASSES, AFTER THE COMPOSER, and the position is load-bearing: four of the
    # eight condition kinds (`trend`, `cohort`, `anomaly`, and the temporal reads) evaluate against
    # `derived.*` facts written by the analytic block above. Placed earlier it would match against
    # last sweep's stratum and, on a tenant's first sweep, against none at all — every trend and
    # cohort condition failing for a reason that has nothing to do with the pattern.
    #
    # `sweep_at`, like every pass above: one instant for the whole drain, so a replay reproduces
    # the same fires. `evaluate_org` reads the clock nowhere below this line.
    #
    # The two NEGATIVE condition kinds use the production typed-absence and explicit edge-coverage
    # providers.  Neither infers coverage from an empty query: an absence whose coverage epoch is
    # stale and an edge type with no declared capability both fail as `absence_not_licensed`.
    #
    # BOUNDED: `ANCHOR_BUDGET` slices per node type per pattern, `FIRE_WRITE_BUDGET` fire rows per
    # run (the TRUE count still lands on `pattern_runs.fires`, which is the number the guard
    # reads), and `record_evaluation` prunes past `FIRE_RETENTION_DAYS` on the same request that
    # writes. No periodic task: the Celery broker is a quota-limited Upstash instance.
    #
    # NEVER FATAL: a missed evaluation costs one sweep of fire evidence, never an event.
    pattern_fires = 0
    patterns_evaluated = 0
    try:
        from genios_engine.platform.l2_activation import is_patterns_activated
        if is_patterns_activated(store.engine, org_id):
            from genios_engine.context.patterns.store import evaluate_org
            report = evaluate_org(store, org_id, eval_time=sweep_at)
            patterns_evaluated = len(report.runs)
            pattern_fires = sum(run.fires for run in report.runs)
    except Exception:      # noqa: BLE001 — a shadow evaluation, retried on the next drain
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("pattern shadow evaluation failed for org=%s", org_id)

    # No extraction credit is charged here.  Semantic rows arrive with an L1 QES and are adapted
    # without a model call; structured rows are deterministic too.  Charging either at this seam
    # billed the same L1 interpretation twice.  The two remaining L2 model sites write their own
    # token/cost receipts through `context.model_audit`.
    # L-4 · the fixpoint's "after", and the bookkeeping. LAST, after every pass that can move a
    # situation, a membership or a lifecycle state — a hash taken before the composer would call a
    # sweep converged that had not finished changing the graph.
    #
    # `done` is the whole "was there new input" test: it is the count of events this sweep actually
    # drained, so a sweep that ingested nothing and still moved the state is the one that counts as
    # a turn of the fixpoint. Never fatal, and it deliberately does not gate the return: a guard
    # that could stop a drain reporting its work would be a worse failure than the loop it watches.
    try:
        convergence = _record_convergence(store, org_id, before=state_hash_before,
                                          after=_convergence_state_hash(store, org_id),
                                          drained=bool(done), sweep_at=sweep_at)
    except Exception:      # noqa: BLE001 — the convergence guard must never break ingestion
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").exception("convergence bookkeeping failed for org=%s", org_id)
        convergence = {"checked": False}

    return {"processed": done, "outcomes": dict(out), "read_models_built": len(affected),
            "attention_rows": attention_rows, "situation_rows": situation_rows,
            # L2.7.7's ledger: how many situations were examined, how many model calls that cost,
            # what closed, what reopened, and what is waiting for a human. Carried out of the
            # drain for the reason `budget_exhausted` is — a site that made no calls because it
            # ran out of budget must not look like a site with nothing to do.
            "resolutions": resolutions,
            "resource_correlation": resource_correlation,
            "derived_rows": derived_rows, "history_points_pruned": history_points_pruned,
            "history_backfilled": history_backfilled,
            "metric_points": metric_points, "trend_facts": trend_facts,
            "anomaly_facts": anomaly_facts, "cohort_changes": cohort_changes,
            "baselines_written": baselines_written,
            "comparison_facts": comparison_facts,
            "dependency_facts": dependency_facts,
            "timeline_facts": timeline_facts,
            "situations_ranked": situations_ranked,
            # X8. `patterns_evaluated` is 0 on every tenant whose `l2_v2_activation.
            # patterns_enabled_at` is not live, which is every tenant until an operator says
            # otherwise — so 0 here means "not in the pilot", and `pattern_fires` is the shadow
            # fire count `scripts/l2_shadow_diff.py` reads seven days of off `pattern_runs`.
            "patterns_evaluated": patterns_evaluated,
            "pattern_fires": pattern_fires,
            # E-10. `gap_corrections` is how many trend facts this sweep recomputed over a
            # corrected series; `false_churn_withdrawn` is the subset that stopped claiming a
            # direction — the number doc 09's H6 row ("DECLINING trends across an org-wide silence
            # window: 0") is actually about, carried out of the drain rather than dropped at its
            # edge.
            "gap_corrections": gap_corrections,
            "false_churn_withdrawn": false_churn_withdrawn,
            "gap_budget_exhausted": gap_budget_exhausted,
            # L-4. `passes` is doc 09's "drains exceeding MAX_PASSES" counter and `exceeded` is
            # the alert. `checked: False` means the probe could not read the state this sweep and
            # the counter was left exactly as it was — never silently reset.
            "convergence": convergence,
            # The ledger, carried out of the drain rather than dropped at its edge. `True` means
            # that pass hit its per-sweep ceiling and left work for the next one — which for the
            # analytic passes is now a real promise (they order their queues by staleness, so the
            # tail rotates) and is worth an operator's attention on any org where it stays True.
            "budget_exhausted": dict(budgets)}
