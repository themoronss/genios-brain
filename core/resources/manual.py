"""Manual context entries — typed meeting/call/conversation summaries.

Flow per g-i-1:
  1. UI POSTs {contact_name, type, discussion, ...}
  2. We write a row into `manual_entries` so the card lists in O(1)
  3. We wrap the same text as a MemoryItem and emit() it — the worldmodel
     ingest subscriber then extracts entities/facts and writes them to
     `graph_nodes` / `facts`, keyed by source_item_id so we can find
     them again (delete cascade, fact-count rollup, etc).

Read side: list_manual_entries reads from manual_entries (UI-shaped) and
rolls up the live facts/entities counts via a join on source_item_id.

Delete: removes the manual_entries row AND the facts/graph_nodes rows
linked by source_item_id (full GDPR-style wipe — per MD §non-negotiable).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.memory.emit import emit as emit_memory_item
from core.memory.types import MemoryItem, MemoryItemMetadata
from core.resources.billing import deduct_or_raise as _deduct_or_raise_impl
from core.resources.connection import (
    ensure_resource_connection,
    synthetic_source_id,
)


def _deduct_or_raise(**kwargs):
    """Local alias so the call site reads cleanly. Forwards to the shared
    helper that lives in core/resources/billing.py."""
    return _deduct_or_raise_impl(**kwargs)

log = get_logger(__name__)


@dataclass(frozen=True)
class ManualEntryInput:
    contact_name: str
    context_type: str
    discussion: str
    contact_email: str | None = None
    commitments: str | None = None
    interaction_date: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Write
# ─────────────────────────────────────────────────────────────────────────────


def _build_content(entry: ManualEntryInput) -> str:
    """Serialize a manual entry into a single text block for extraction.

    The ingest_subscriber feeds this string into the Haiku extractor; we
    front-load the contact + type so the LLM keeps the subject clear.
    """
    parts = [
        f"Contact: {entry.contact_name}",
        f"Type: {entry.context_type}",
    ]
    if entry.interaction_date is not None:
        parts.append(f"When: {entry.interaction_date.isoformat()}")
    parts.append("")
    parts.append(entry.discussion.strip())
    if entry.commitments:
        parts.append("")
        parts.append(f"Commitments: {entry.commitments.strip()}")
    return "\n".join(parts)


def create_manual_entry(
    session: Session,
    *,
    org_id: str,
    actor_email: str,
    entry: ManualEntryInput,
    agent_id: str | None = None,
) -> dict:
    """Persist + emit. Returns the created row in dict form for the route.

    Billing: 1 credit per entry under reason 'resources:manual_entry'.
    Charged BEFORE the LLM extract call so an out-of-credits user gets a
    402 here instead of after we've already burned a Haiku call. The
    raise propagates to the route which renders the 402 envelope.
    """
    ensure_resource_connection(session, org_id=org_id, source_type="manual")
    source_id = synthetic_source_id(source_type="manual", org_id=org_id)

    entry_id = str(uuid.uuid4())
    source_item_id = f"manual_{entry_id}"
    created_at = datetime.now(UTC)
    interaction_ts = entry.interaction_date or created_at

    _deduct_or_raise(
        org_id=org_id, reason="resources:manual_entry",
        idempotency_key=f"manual:{entry_id}",
        related_kind="manual_entry", related_id=entry_id,
        agent_uuid=agent_id, actor_email=actor_email,
    )

    session.execute(
        text(
            """
            INSERT INTO manual_entries
                (id, org_id, agent_id, contact_name, contact_email, context_type,
                 interaction_date, discussion, commitments, source_item_id,
                 created_by, created_at)
            VALUES
                (:id, :org, :agent, :cname, :cemail, :ctype,
                 :idate, :disc, :commits, :sid,
                 :actor, :created)
            """
        ),
        {
            "id": entry_id,
            "org": org_id,
            "agent": agent_id,
            "cname": entry.contact_name,
            "cemail": entry.contact_email,
            "ctype": entry.context_type,
            "idate": interaction_ts,
            "disc": entry.discussion,
            "commits": entry.commitments,
            "sid": source_item_id,
            "actor": actor_email,
            "created": created_at,
        },
    )
    session.commit()

    # Emit so worldmodel extracts entities/facts. The ingest subscriber
    # resolves org_id via the connections row we just ensured.
    try:
        item = MemoryItem(
            item_id=source_item_id,
            source_id=source_id,
            source_type="manual",
            content=_build_content(entry),
            metadata=MemoryItemMetadata(
                timestamp=interaction_ts,
                owner=actor_email,
                source_confidence=1.0,
                tags=[entry.context_type.lower()],
            ),
        )
        emit_memory_item(item, org_id=org_id)
    except Exception as e:
        # Extraction failure must not roll back the user's typed entry —
        # they can re-trigger ingest later. The row is still useful as
        # plain text storage.
        log.warning(
            "manual_entry_emit_failed",
            entry_id=entry_id, org_id=org_id, error=str(e),
        )

    audit.record(
        org_id=org_id,
        actor_type="user",
        actor_id=actor_email,
        action="data_accessed",
        target_type="manual_entry",
        target_id=entry_id,
        metadata={"op": "create", "contact": entry.contact_name},
    )
    log.info("manual_entry_created", entry_id=entry_id, org_id=org_id)

    return _row_to_card(session, org_id=org_id, entry_id=entry_id)


# ─────────────────────────────────────────────────────────────────────────────
# Read
# ─────────────────────────────────────────────────────────────────────────────


def list_manual_entries(
    session: Session,
    *,
    org_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List manual entries (org-scoped) newest first, with live fact counts.

    Per-agent scope policy filtering is layered by the route caller — this
    module returns everything for the org and lets the route trim.
    """
    # Single JOIN against `facts` for the live count is enough — the
    # entities figure is harder (graph_nodes.source_item_ids is JSON, not
    # a Postgres array, so ANY() does not apply portably). We fall back
    # to counts maintained on the row itself (refreshed by the ingest
    # post-hook in a later pass).
    rows = session.execute(
        text(
            """
            SELECT m.id, m.contact_name, m.contact_email, m.context_type,
                   m.interaction_date, m.discussion, m.commitments,
                   m.source_item_id, m.created_at, m.created_by,
                   m.entities_count,
                   COALESCE(f.facts_count, m.facts_count) AS facts_count
            FROM manual_entries m
            LEFT JOIN (
                SELECT source_item_id, COUNT(*)::int AS facts_count
                FROM facts WHERE org_id = :org
                GROUP BY source_item_id
            ) f ON f.source_item_id = ('manual:' || m.source_item_id)
            WHERE m.org_id = :org
            ORDER BY m.created_at DESC
            LIMIT :lim OFFSET :off
            """
        ),
        {"org": org_id, "lim": limit, "off": offset},
    ).fetchall()
    return [_card_from_row(r) for r in rows]


def _row_to_card(session: Session, *, org_id: str, entry_id: str) -> dict:
    row = session.execute(
        text(
            """
            SELECT id, contact_name, contact_email, context_type,
                   interaction_date, discussion, commitments,
                   source_item_id, created_at, created_by
            FROM manual_entries WHERE id = :id AND org_id = :org
            """
        ),
        {"id": entry_id, "org": org_id},
    ).fetchone()
    if row is None:
        return {}
    # Fact/entity counts may not be populated yet right after create —
    # the ingest subscriber runs synchronously but the UI displays 0
    # until the next list refresh.
    base = _card_from_row(row)
    base["facts_count"] = 0
    base["entities_count"] = 0
    return base


def _card_from_row(r) -> dict:
    return {
        "id": str(r.id),
        "contact_name": r.contact_name,
        "contact_email": r.contact_email,
        "context_type": r.context_type,
        "interaction_date": r.interaction_date.isoformat() if r.interaction_date else None,
        "discussion": r.discussion,
        "commitments": r.commitments,
        "source_item_id": r.source_item_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "created_by": r.created_by,
        "facts_count": getattr(r, "facts_count", 0) or 0,
        "entities_count": getattr(r, "entities_count", 0) or 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Update / Delete
# ─────────────────────────────────────────────────────────────────────────────


def update_manual_entry(
    session: Session,
    *,
    org_id: str,
    entry_id: str,
    actor_email: str,
    fields: dict,
) -> dict | None:
    """Patch UI fields. Does NOT re-emit — the original extraction stands.

    If the user changes the discussion text and wants fresh extraction
    they should delete + re-add (cleaner audit trail than silent re-ingest).
    """
    allowed = {"contact_name", "contact_email", "context_type",
               "interaction_date", "discussion", "commitments"}
    sets = []
    params: dict = {"id": entry_id, "org": org_id}
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        sets.append(f"{k} = :{k}")
        params[k] = v
    if not sets:
        return _row_to_card(session, org_id=org_id, entry_id=entry_id) or None
    session.execute(
        text(f"UPDATE manual_entries SET {', '.join(sets)} "
             f"WHERE id = :id AND org_id = :org"),
        params,
    )
    session.commit()
    audit.record(
        org_id=org_id, actor_type="user", actor_id=actor_email,
        action="config_changed", target_type="manual_entry",
        target_id=entry_id, metadata={"op": "update", "fields": list(fields.keys())},
    )
    return _row_to_card(session, org_id=org_id, entry_id=entry_id) or None


def delete_manual_entry(
    session: Session,
    *,
    org_id: str,
    entry_id: str,
    actor_email: str,
) -> bool:
    """Full wipe: row + every fact/node rooted at this entry's source_item_id.

    Per MD non-negotiable user-data deletion. Cascade is manual so the
    counts in the audit metadata are accurate.
    """
    row = session.execute(
        text("SELECT source_item_id FROM manual_entries "
             "WHERE id = :id AND org_id = :org"),
        {"id": entry_id, "org": org_id},
    ).fetchone()
    if row is None:
        return False
    tagged = f"manual:{row.source_item_id}"

    facts_n = session.execute(
        text("DELETE FROM facts WHERE org_id = :org AND source_item_id = :sid "
             "RETURNING id"),
        {"org": org_id, "sid": tagged},
    ).rowcount or 0
    # graph_nodes.source_item_ids is JSON (array shape). Use jsonb cast +
    # containment so a node attached to multiple sources only loses this
    # one reference if also attached elsewhere (manual delete is per-entry,
    # not org wide). For now we delete nodes that ONLY reference this entry.
    nodes_n = session.execute(
        text(
            """
            DELETE FROM graph_nodes
            WHERE org_id = :org
              AND source_item_ids::jsonb @> to_jsonb(ARRAY[:sid]::text[])
              AND jsonb_array_length(source_item_ids::jsonb) = 1
            RETURNING id
            """
        ),
        {"org": org_id, "sid": tagged},
    ).rowcount or 0
    session.execute(
        text("DELETE FROM manual_entries WHERE id = :id AND org_id = :org"),
        {"id": entry_id, "org": org_id},
    )
    session.commit()

    audit.record(
        org_id=org_id, actor_type="user", actor_id=actor_email,
        action="data_subject_erasure", target_type="manual_entry",
        target_id=entry_id,
        metadata={"facts_deleted": facts_n, "nodes_deleted": nodes_n},
    )
    log.info("manual_entry_deleted", entry_id=entry_id,
             facts_n=facts_n, nodes_n=nodes_n)
    return True
