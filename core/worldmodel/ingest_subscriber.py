"""emit() bus subscriber: MemoryItem → extract → resolve → persist (g-i-3 §1).

Registered once at app startup (core/main.py / app/main.py lifespan) via
`register_ingest_subscriber()`. After registration, every MemoryItem emitted by
core/memory/sync_runner.py flows through here:

  emit(MemoryItem) ─→ extract_entities_and_relations (Haiku LLM, per MD §8.2 ₹0.29)
                  ├─→ resolve_entity (block + similarity)
                  ├─→ upsert NodeRow (org-isolated, grounded by source_item_ids)
                  ├─→ upsert EdgeRow (asserted_by_type=SOURCE — RULE/HUMAN only for INFLUENCE)
                  └─→ insert FactRow (S-P-O grounded by source_item_id)

Failure isolation: extraction failure for one item NEVER blocks others.
Cost guard: extraction skipped if EXTRACT_DISABLED env var set (demo / offline mode).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.db import get_session
from core.foundations.telemetry import get_logger
from core.graph.schema import AssertionSource, EdgeStatus, EdgeType
from core.graph.store import EdgeRow, FactRow, NodeRow
from core.memory.emit import subscribe
from core.memory.types import MemoryItem
from core.worldmodel.extract import (
    ExtractedEntity,
    ExtractedRelation,
    Extraction,
    ExtractionError,
    extract,
)
from core.worldmodel.resolve import similarity

log = get_logger(__name__)

EXTRACT_DISABLED = os.getenv("GENIOS_EXTRACT_DISABLED", "0") == "1"
SIMILARITY_THRESHOLD = float(os.getenv("GENIOS_EXTRACT_RESOLVE_THRESHOLD", "0.85"))


def register_ingest_subscriber() -> None:
    """Subscribe `_handle_memory_item` to the bus. Idempotent — safe to call again."""
    subscribe("g-i-3 worldmodel-ingest", _handle_memory_item)
    log.info("ingest_subscriber_registered", extract_disabled=EXTRACT_DISABLED)


def _handle_memory_item(item: MemoryItem) -> None:
    """Bus handler — never raises (bus expects failure isolation per emit.py).

    Bus signature is `Callable[[MemoryItem], None]` — `org_id` was deliberately
    left out of the per-call signature so the bus stays source-agnostic. We
    pull `org_id` from a small derived map: `source_id` ↔ `org_id` via the
    `connections` table. For demo we look it up per-item; a per-connection
    cache can land later if cost matters.
    """
    if EXTRACT_DISABLED:
        log.debug("ingest_extract_skipped_disabled", item_id=item.item_id)
        return
    try:
        with get_session() as session:
            org_id = _org_for_source(session, item.source_id)
            if org_id is None:
                log.warning(
                    "ingest_skipped_unknown_source",
                    item_id=item.item_id,
                    source_id=item.source_id,
                )
                return
            _ingest_one(session, item, org_id)
    except Exception as e:
        log.exception(
            "ingest_subscriber_failed",
            item_id=item.item_id,
            error=str(e),
        )


def _org_for_source(session: Session, source_id: str) -> str | None:
    """Resolve org_id from a connection.source_id (e.g. Gmail mailbox address)."""
    from core.memory.store import Connection

    row = (
        session.execute(
            select(Connection)
            .where(Connection.source_id == source_id)
            .order_by(Connection.created_at.desc())
            .limit(1)
        )
        .scalars()
        .one_or_none()
    )
    return row.org_id if row else None


def _ingest_one(session: Session, item: MemoryItem, org_id: str) -> None:
    """Run the extract → resolve → persist pipeline for one MemoryItem.

    org_id is threaded into extract() so the LLM call writes a row in
    llm_costs attributed to this tenant — needed for cost visibility +
    the per-day budget breaker.
    """
    try:
        extraction = extract(item, org_id=org_id)
    except ExtractionError as e:
        log.warning(
            "extract_failed", item_id=item.item_id, org_id=org_id, error=str(e)
        )
        # Failed extract → caller's sync deduction was for nothing of
        # value. Refund so the customer isn't charged for our error.
        _refund_zero_signal(
            org_id=org_id, source_type=item.source_type,
            native_id=item.item_id, reason="extract_failed",
        )
        return

    if not extraction.entities and not extraction.relations:
        # The LLM had nothing to extract (truly noisy content the noise
        # gate didn't catch). Refund the sync deduction so we don't bill
        # for junk — we still ate the ~$0.003 Haiku call, but that's our
        # cost of having a safety net.
        _refund_zero_signal(
            org_id=org_id, source_type=item.source_type,
            native_id=item.item_id, reason="zero_signal_extract",
        )
        return  # nothing extracted — common for trivial messages

    # Prefix the stored item_id with source_type so disconnect+wipe can find
    # everything tied to a specific source via a LIKE 'gmail:%' scan.
    tagged_item_id = f"{item.source_type}:{item.item_id}"

    # Upsert nodes — resolve to existing if similar enough
    node_id_by_name: dict[str, str] = {}
    for ent in extraction.entities:
        node = _upsert_node(session, org_id=org_id, entity=ent, item_id=tagged_item_id)
        node_id_by_name[ent.name.lower()] = node.id

    # Upsert edges (only TEMPORAL/DEPENDENCY — INFLUENCE never from source per spec)
    for rel in extraction.relations:
        _upsert_edge(
            session,
            org_id=org_id,
            relation=rel,
            node_id_by_name=node_id_by_name,
            item_id=tagged_item_id,
        )

    # Always write FactRows as the auditable grounding trail (S-P-O triples)
    for rel in extraction.relations:
        session.add(
            FactRow(
                org_id=org_id,
                subject=rel.subject,
                predicate=rel.predicate,
                object=rel.object,
                source_item_id=tagged_item_id,
                asserted_by_type=AssertionSource.SOURCE.value,
                asserted_by_id=item.source_id,
                confidence=1.0,
            )
        )

    # Predicate registry: count distinct verbs the LLM emits, per org. Plan
    # keeps predicates open-vocabulary, so this is the feedback loop ops +
    # module authors use to standardize rules against the real distribution
    # (e.g. "we have 4 variants of works_at — pick a canonical one").
    if extraction.relations:
        _bump_predicate_registry(
            session, org_id=org_id,
            predicates=[r.predicate for r in extraction.relations],
        )

    session.flush()
    log.info(
        "ingest_persisted",
        item_id=tagged_item_id,
        org_id=org_id,
        n_entities=len(extraction.entities),
        n_relations=len(extraction.relations),
    )


def _upsert_node(
    session: Session,
    *,
    org_id: str,
    entity: ExtractedEntity,
    item_id: str,
) -> NodeRow:
    """Find an existing node by similarity OR insert a new one.

    Block by lowercase first-token of canonical_name to bound candidates.
    """
    block_key = entity.name.lower().split()[0] if entity.name else ""
    candidates = (
        session.execute(
            select(NodeRow)
            .where(NodeRow.org_id == org_id)
            .where(NodeRow.type == entity.type.value)
            .limit(64)
        )
        .scalars()
        .all()
    )

    best: NodeRow | None = None
    best_score = 0.0
    new_node_for_sim = NodeRow(
        org_id=org_id,
        org_unit=org_id,
        type=entity.type.value,
        canonical_name=entity.name,
        aliases=list(entity.aliases),
        attributes=dict(entity.attributes or {}),
        source_item_ids=[item_id],
    )
    for cand in candidates:
        if not cand.canonical_name.lower().startswith(block_key[:3]):
            continue
        score = similarity(cand, new_node_for_sim)
        if score > best_score:
            best_score = score
            best = cand

    if best is not None and best_score >= SIMILARITY_THRESHOLD:
        # Merge: extend source_item_ids + aliases + attributes, bump last_seen.
        # Attributes merge is non-destructive: existing keys stay; new keys
        # the latest extraction surfaced get added. A correction can override.
        if item_id not in (best.source_item_ids or []):
            best.source_item_ids = [*(best.source_item_ids or []), item_id]
        existing_aliases = set(best.aliases or [])
        for a in entity.aliases:
            if a and a not in existing_aliases:
                existing_aliases.add(a)
        if entity.name and entity.name != best.canonical_name and entity.name not in existing_aliases:
            existing_aliases.add(entity.name)
        best.aliases = sorted(existing_aliases)
        if entity.attributes:
            merged = dict(best.attributes or {})
            for k, v in entity.attributes.items():
                if k not in merged and v not in (None, ""):
                    merged[k] = v
            best.attributes = merged
        best.last_seen = datetime.now(UTC)
        return best

    session.add(new_node_for_sim)
    session.flush()
    return new_node_for_sim


def _upsert_edge(
    session: Session,
    *,
    org_id: str,
    relation: ExtractedRelation,
    node_id_by_name: dict[str, str],
    item_id: str,
) -> None:
    """Insert an EdgeRow for a stated relation. Skip if either node missing."""
    from_id = node_id_by_name.get(relation.subject.lower())
    to_id = node_id_by_name.get(relation.object.lower())
    if not from_id or not to_id:
        return

    # SPEC HARD GATE: INFLUENCE edges cannot have asserted_by_type=SOURCE.
    # Extraction never emits INFLUENCE (see extract.py prompt) but guard anyway.
    if relation.edge_type == EdgeType.INFLUENCE:
        log.warning(
            "extract_emitted_influence_blocked",
            item_id=item_id,
            subject=relation.subject,
            object=relation.object,
        )
        return

    session.add(
        EdgeRow(
            org_id=org_id,
            from_node=from_id,
            to_node=to_id,
            type=relation.edge_type.value,
            asserted_by_type=AssertionSource.SOURCE.value,
            asserted_by_id=item_id,
            weight=1.0,
            weight_source="default",
            alpha=1,
            beta=1,
            trust=0.0,
            decay_lambda=0.0,
            status=EdgeStatus.ASSERTED.value,
        )
    )


def _bump_predicate_registry(
    session: Session, *, org_id: str, predicates: list[str]
) -> None:
    """UPSERT into predicate_registry, counting occurrences.

    Single batched INSERT ... ON CONFLICT keeps this cheap; we don't care
    about per-relation timing inside one item. Fail-soft: the registry is
    advisory, not on the critical path — extraction must not die if it's
    missing (e.g. migration not yet applied in some env).
    """
    if not predicates:
        return
    from collections import Counter as _Counter
    from sqlalchemy import text as _text
    counts = _Counter(p.strip() for p in predicates if p and p.strip())
    try:
        for pred, n in counts.items():
            session.execute(
                _text(
                    """
                    INSERT INTO predicate_registry
                        (org_id, predicate, occurrences, first_seen, last_seen)
                    VALUES (:org, :pred, :n, NOW(), NOW())
                    ON CONFLICT (org_id, predicate) DO UPDATE
                        SET occurrences = predicate_registry.occurrences + EXCLUDED.occurrences,
                            last_seen   = NOW()
                    """
                ),
                {"org": org_id, "pred": pred, "n": n},
            )
    except Exception as e:
        log.warning("predicate_registry_bump_failed", error=str(e))


def _refund_zero_signal(
    *,
    org_id: str,
    source_type: str,
    native_id: str,
    reason: str,
) -> None:
    """Refund the sync deduction when extraction returned no usable signal.

    Looks up the original deduct row by the deterministic idempotency_key
    sync_runner used (`sync:<source_type>:<native_id>`) and calls the
    ledger's refund() helper, which writes a paired ledger row reversing
    the deduct + adds the credits back to the org pool.

    Scope:
      - Only refunds sync deductions (skipped for resources:manual_entry
        and resources:upload_chunk where the user explicitly authored
        the input).
      - Fail-soft: a refund hiccup must never bubble up into ingest;
        worst case we have a one-credit anomaly the ops team can find
        via the ledger metadata.
    """
    if source_type in ("manual", "upload"):
        return
    try:
        from sqlalchemy import text as _text

        from app.credits.ledger import refund as _ledger_refund
        from app.database import SessionLocal

        # The idempotency_key now includes connection_id
        # (sync:{source}:{conn_id}:{native_id}) so a disconnect+reconnect
        # bills again. The refund still keys on the latest deduct that
        # carries the same (source, native_id) suffix — that's the
        # row we just charged. LIKE is fine because the prefix is
        # deterministic and there's at most one connection per
        # (org, source_type) active at a time.
        like_key = f"sync:{source_type}:%:{native_id}"
        db = SessionLocal()
        try:
            row = db.execute(
                _text(
                    """
                    SELECT id FROM credit_ledger
                    WHERE org_id = :org
                      AND idempotency_key LIKE :key
                      AND kind = 'deduct'
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """
                ),
                {"org": org_id, "key": like_key},
            ).fetchone()
            if row is None:
                return  # no matching deduct (e.g. trial-bypass, manual, retry)
            out = _ledger_refund(
                db, org_id=org_id, ledger_id=int(row.id),
                reason=f"sync:{source_type}_record:{reason}",
            )
            db.commit()
            if out is not None:
                log.info(
                    "sync_record_refunded",
                    org_id=org_id, source_type=source_type,
                    native_id=native_id, reason=reason,
                    refund_ledger_id=out.ledger_id,
                )
        finally:
            db.close()
    except Exception as e:
        log.warning(
            "refund_zero_signal_failed",
            org_id=org_id, source_type=source_type,
            native_id=native_id, error=str(e),
        )


# Re-exports for callers
__all__ = ["_handle_memory_item", "register_ingest_subscriber"]


def _silence_unused() -> tuple[Any, ...]:
    return (Extraction,)
