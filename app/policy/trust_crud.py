"""
Per-agent trust list helpers.

Each row marks a sender/caller as trusted by a specific agent. On every
ingest event we check this list — if matched, the interaction is flagged
`trusted_sender=true` so downstream agent code can act on instructions
only from approved sources.

Three match modes (one per row): contact_id, match_email, match_phone.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_for_agent(db: Session, org_id: str, agent_uuid: str):
    return db.execute(
        text("""
            SELECT t.id::text, t.contact_id::text, t.match_email, t.match_phone,
                   t.note, t.created_at, c.name AS contact_name, c.email AS contact_email
            FROM agent_trust t
            LEFT JOIN contacts c ON c.id = t.contact_id
            WHERE t.org_id = :o AND t.agent_uuid = :a
            ORDER BY t.created_at DESC
        """),
        {"o": org_id, "a": agent_uuid},
    ).fetchall()


def add(
    db: Session,
    org_id: str,
    agent_uuid: str,
    contact_id: Optional[str] = None,
    match_email: Optional[str] = None,
    match_phone: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    return db.execute(
        text("""
            INSERT INTO agent_trust
                (org_id, agent_uuid, contact_id, match_email, match_phone, note)
            VALUES (:o, :a, :c, :e, :p, :n)
            RETURNING id::text
        """),
        {
            "o": org_id, "a": agent_uuid,
            "c": contact_id,
            "e": (match_email or "").strip().lower() or None,
            "p": (match_phone or "").strip() or None,
            "n": note,
        },
    ).scalar()


def remove(db: Session, org_id: str, agent_uuid: str, trust_id: str) -> bool:
    res = db.execute(
        text("""
            DELETE FROM agent_trust
            WHERE id = :id AND org_id = :o AND agent_uuid = :a
            RETURNING 1
        """),
        {"id": trust_id, "o": org_id, "a": agent_uuid},
    ).fetchone()
    return res is not None


def is_trusted(
    db: Session,
    agent_uuid: str,
    sender_email: Optional[str] = None,
    sender_phone: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> bool:
    """Quick lookup — does the agent trust this sender/caller?"""
    clauses = []
    binds = {"a": agent_uuid}
    if contact_id:
        clauses.append("contact_id = :c")
        binds["c"] = contact_id
    if sender_email:
        clauses.append("LOWER(match_email) = :e")
        binds["e"] = sender_email.strip().lower()
    if sender_phone:
        clauses.append("match_phone = :p")
        binds["p"] = sender_phone.strip()
    if not clauses:
        return False
    sql = (
        "SELECT 1 FROM agent_trust WHERE agent_uuid = :a AND ("
        + " OR ".join(clauses) + ") LIMIT 1"
    )
    return db.execute(text(sql), binds).fetchone() is not None
