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
    if llm is None:
        return "skipped_no_llm", None
    content = _clean_for_llm(raw, row.event_id,      # unstructured lane (B3, LLM)
                             prepared_text=getattr(row, "prepared_text", None))
    is_inbound = "SENT" not in (raw.get("labelIds") or [])   # direction → thread state
    # recipients (To + Cc, captured in L1) → sender↔recipient correspondence edges in L2
    recipients = [e for e in ((raw.get("to") or []) + (raw.get("cc") or [])) if e]
    res = process_event(org_id=org_id, event_id=row.event_id, source=row.source, content=content,
                        sender_email=row.sender, recipient_emails=recipients,
                        sender_name=getattr(row, "sender_name", None),
                        occurred_at=row.occurred_at, llm=llm, store=store,
                        is_inbound=is_inbound, internal_emails=internal_emails,
                        internal_kind=getattr(row, "internal_kind", None),
                        thread_id=getattr(row, "parent_object_id", None),
                        domain_hints=getattr(row, "domain_hints", None),
                        canon_meta=raw,
                        # The tenant's own pack vocabulary. Without it the extractor runs one
                        # hardcoded B2B-SaaS ontology for everyone, and a rule reading
                        # `deal.status` is dead because the model was never told the name.
                        effective=effective)
    return res.outcome, res.primary_node


def _pull(store: GraphStore, org_id: str, limit: int):
    """Drain order = L1's triage lane FIRST (P0 preempts P3 — the lane was computed at
    ingestion and previously thrown away), then arrival time. Prepared text rides along
    from the seam so processing doesn't re-derive it."""
    with store.engine.connect() as c:
        return c.execute(text(
            "select se.event_id, se.source, se.object_type, se.actor->>'email' as sender, "
            "se.actor->>'name' as sender_name, "
            "se.occurred_at, se.source_object_id, se.triage_lane, se.internal_kind, "
            "se.parent_object_id, se.domain_hints, "
            "rp.enc_content, "
            "pc.clean_text as prepared_text "
            "from source_events se "
            "join raw_payloads rp on rp.event_id = se.event_id "
            "left join prepared_content pc on pc.event_id = se.event_id and pc.org_id = se.org_id "
            "where se.org_id=:o and se.outcome='emitted' "
            "and se.event_id not in (select event_id from l2_extraction_results where org_id=:o) "
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
                    crypto_key: str, max_total: int = 5000, registry=None) -> dict:
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
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:   # parallel LLM calls
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
    if done or affected:
        try:
            from genios_engine.context.derived import compute as compute_derived
            from genios_engine.context.derived import compute_deal_view
            derived_rows = compute_derived(store, org_id) + compute_deal_view(store, org_id)
            # PERIOD aggregates and their situations, in the same pass and for the same reason:
            # they are computed from facts that now exist, they are cheap, and a period read that
            # is only refreshed by a separate schedule is a period read that is always stale.
            # Twenty-two authored capabilities are reachable only through these.
            from genios_engine.context.periodic import refresh_period_situations
            derived_rows += refresh_period_situations(store, org_id)
            # The seven correspondence-derived support readings, in the same pass and for the
            # same reason: a first-response clock, an aging item and a repeat contact are all
            # computed from the thread state and open loops THIS drain just committed, and a
            # reading refreshed only by a separate schedule is a reading that is always stale.
            # Seven authored situation types were unroutable until these existed.
            from genios_engine.context.support_situations import refresh_support_situations
            derived_rows += refresh_support_situations(store, org_id)
            # The records reading, in the same pass and for the same reason: a document's control
            # gaps are computed from the file metadata THIS drain just projected, and the copy
            # clustering has to re-run whenever a file lands or a second copy of one appears. It
            # costs two queries and returns immediately on an org with no file store connected.
            from genios_engine.context.document_register import refresh_document_situations
            derived_rows += refresh_document_situations(store, org_id)
        except Exception:      # noqa: BLE001 — derived view, recomputed next drain
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception("derived fact refresh failed for org=%s", org_id)
    # Attention refresh — L2 is the SOLE writer of context_attention. Full-org refresh
    # when anything changed (recency decays even for untouched nodes, and it is a few
    # bulk queries, not per-node round-trips).
    attention_rows = 0
    if done or affected:
        try:
            from genios_engine.context.attention import refresh_attention
            attention_rows = refresh_attention(store, org_id)
        except Exception:      # noqa: BLE001 — attention is an ordering hint, never fatal
            pass

    # Situations are rebuilt AFTER attention, from correlations the drain just extended.
    # Every value is derived, so a failure here costs a refresh cycle, not data — the
    # next drain recomputes it. Never fatal: a situation view being briefly stale must
    # not stop events from landing.
    situation_rows = 0
    if done or affected:
        try:
            from genios_engine.context.situations import refresh_situations
            situation_rows = refresh_situations(store, org_id)
        except Exception:      # noqa: BLE001 — derived view, rebuilt next drain
            from genios_engine.platform.logging import get_logger
            get_logger("genios.l2").exception(
                "situation refresh failed for org=%s", org_id)
    # Credits: charge only the LLM-metered Gmail extraction — structured Calendar events use no LLM,
    # so they never bill. 1 credit per 10 emails keeps a sync from draining the balance. Never blocks
    # ingestion (background must keep flowing even at zero balance; the user-facing query/draft gates
    # do the hard block). Idempotent per drain so a re-run doesn't double-charge.
    llm_events = done - out.get("committed_structured", 0) - out.get("skipped_no_llm", 0)
    # 1 credit per 10 LLM-extracted items, but ALWAYS at least 1 whenever the LLM actually ran —
    # so a small upload or a light sync still visibly bills. No LLM work → no charge.
    charge = max(1, llm_events // 10) if llm_events > 0 else 0
    if charge > 0:
        try:
            from datetime import datetime, timezone
            from genios_engine.platform import billing as _B
            idem = f"sync:{org_id}:{datetime.now(timezone.utc):%Y%m%d%H%M}:{done}"
            with store.engine.begin() as c:
                _B.deduct(c, org_id, charge, reason="gmail_extraction", idem=idem, bucket="sync")
        except Exception:      # noqa: BLE001 — billing must never break ingestion
            pass
    return {"processed": done, "outcomes": dict(out), "read_models_built": len(affected),
            "attention_rows": attention_rows, "situation_rows": situation_rows,
            "derived_rows": derived_rows}
