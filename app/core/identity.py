"""Source-agnostic person identity.

A person's stable identity is `contacts.id` (a UUID) — never their email.
Every source-specific handle (email, phone, Slack id, Jira account, or just
a name) lives in `entity_aliases` as an (alias_kind, alias_text) pair.

`resolve_or_create_person` looks a person up by ANY known alias and creates
them — with no email required — when nothing matches. This is what lets the
context brain ingest people from Slack, calls, documents, etc. without
forcing a fake email.

Identity resolution / de-dup of the same person across sources is handled
separately by the existing merge pipeline (merge_queue + app/api/routes/merge.py).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Canonical alias kinds. `alias_kind` is free text in the DB, but callers
# should use these constants so lookups across sources agree.
EMAIL = "email"
PHONE = "phone"
NAME = "display_name"
EXTERNAL = "external_id"   # namespace the value, e.g. "slack:U0123", "jira:abc"


def resolve_or_create_person(
    db: Session,
    org_id: str,
    *,
    identifiers: list[tuple[str, str]],
    entity_type: str = "other",
) -> Optional[str]:
    """Return the contact id for a person, creating them if new.

    `identifiers` is a list of (kind, value) pairs — pass everything the
    source knows:
        [(EMAIL, "a@b.com"), (NAME, "Ankit Rao")]      # email source
        [(EXTERNAL, "slack:U07"), (NAME, "Ankit")]     # Slack
        [(NAME, "Ankit Rao")]                          # document mention

    Lookup tries every identifier against `entity_aliases` (and, as a
    legacy fallback, the `contacts.email` column). On a miss a new contact
    is created with `email` left NULL when none was supplied. Every
    identifier is then recorded as an alias so future lookups hit it.

    Returns the contact id (uuid str), or None if there is nothing usable.
    The caller owns the transaction.
    """
    ids: list[tuple[str, str]] = []
    for kind, value in identifiers:
        v = (value or "").strip()
        if kind and v:
            ids.append((kind, v))
    if not ids:
        return None

    # 1. Match any handle we have already seen.
    for kind, value in ids:
        hit = db.execute(
            text("""
                SELECT contact_id::text FROM entity_aliases
                WHERE org_id = :o AND alias_kind = :k
                  AND lower(alias_text) = lower(:v)
                LIMIT 1
            """),
            {"o": org_id, "k": kind, "v": value},
        ).scalar()
        if hit:
            _record_aliases(db, org_id, hit, ids)   # learn any new handles
            return hit

    # 2. Legacy fallback — match the contacts.email column directly
    #    (contacts created before alias backfill).
    for kind, value in ids:
        if kind == EMAIL:
            hit = db.execute(
                text("SELECT id::text FROM contacts "
                     "WHERE org_id = :o AND lower(email) = lower(:v) LIMIT 1"),
                {"o": org_id, "v": value},
            ).scalar()
            if hit:
                _record_aliases(db, org_id, hit, ids)
                return hit

    # 3. Brand-new person — email stays NULL if the source had none.
    email = next((v for k, v in ids if k == EMAIL), None)
    name = next((v for k, v in ids if k == NAME), None)
    contact_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO contacts (id, org_id, name, email, entity_type, authority_score)
            VALUES (:id, :o, :n, :e, :et, 1.0)
        """),
        {"id": contact_id, "o": org_id, "n": name, "e": email, "et": entity_type},
    )
    _record_aliases(db, org_id, contact_id, ids)
    logger.info(
        f"identity: created contact {contact_id} for org {org_id} "
        f"from [{', '.join(k for k, _ in ids)}]"
    )
    return contact_id


def _record_aliases(
    db: Session, org_id: str, contact_id: str, ids: list[tuple[str, str]]
) -> None:
    """Persist every identifier as an alias so future lookups resolve to
    this same contact. Idempotent."""
    for kind, value in ids:
        try:
            db.execute(
                text("""
                    INSERT INTO entity_aliases
                        (org_id, contact_id, alias_text, alias_kind, confidence)
                    VALUES (:o, :c, :t, :k, 1.00)
                    ON CONFLICT (org_id, contact_id, alias_text) DO NOTHING
                """),
                {"o": org_id, "c": contact_id, "t": value, "k": kind},
            )
        except Exception as e:
            logger.debug(f"alias insert skipped ({kind}={value}): {e}")
