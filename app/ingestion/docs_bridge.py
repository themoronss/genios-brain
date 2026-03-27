"""
Docs Bridge — Phase 2

Bridges Google Docs data into the relationship graph:
1. Resolve comment author emails → contacts
2. Create DOC_SHARED interactions for documents with external collaborators

Per PDF spec: Docs comments are the richest authority signal outside Slack.
Google Docs SOP = authority 0.92 (beats Notion's 0.88).
"""

import logging
from uuid import uuid4
from sqlalchemy import text

from app.ingestion.graph_builder import upsert_contact
from app.ingestion.bridge_utils import get_org_domain, is_internal_email

logger = logging.getLogger(__name__)


def resolve_docs_people_to_contacts(db, org_id: str):
    """
    Resolve external people found in Google Docs:
    1. Comment authors (authority signal)
    2. Document owners (for externally shared docs)
    """
    org_domain = get_org_domain(db, org_id)
    resolved = 0

    # 1. Comment authors
    authors = db.execute(
        text("""
            SELECT DISTINCT author_email
            FROM gdocs_comments
            WHERE org_id = :oid
              AND author_email IS NOT NULL
              AND author_person_id IS NULL
        """),
        {"oid": org_id},
    ).fetchall()

    for a in authors:
        email = a.author_email.lower().strip()
        if not email or "@" not in email:
            continue
        if is_internal_email(email, org_domain):
            continue

        name = email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)
        if contact_id:
            db.execute(
                text("""
                    UPDATE gdocs_comments SET author_person_id = :cid
                    WHERE org_id = :oid AND author_email = :email AND author_person_id IS NULL
                """),
                {"cid": contact_id, "oid": org_id, "email": a.author_email},
            )
            resolved += 1

    # 2. External doc owners (docs shared WITH us from outside)
    owners = db.execute(
        text("""
            SELECT DISTINCT owner_email
            FROM gdocs_documents
            WHERE org_id = :oid
              AND owned_by_us = FALSE
              AND owner_email IS NOT NULL
        """),
        {"oid": org_id},
    ).fetchall()

    for o in owners:
        email = o.owner_email.lower().strip()
        if not email or "@" not in email or is_internal_email(email, org_domain):
            continue

        name = email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)
        if contact_id:
            resolved += 1

    logger.info(f"Docs bridge: resolved {resolved} people for org={org_id}")
    return resolved


def create_docs_interactions(db, org_id: str):
    """
    Create DOC_SHARED interaction for documents with external comment authors.
    Each external commenter on a doc = one interaction edge.
    """
    # Get user's primary email so graph edges connect to the user node
    user_row = db.execute(text("SELECT email FROM orgs WHERE id = :oid"), {"oid": org_id}).fetchone()
    account_email = user_row.email if user_row else None

    # Find comments from resolved external authors without existing interactions
    comments = db.execute(
        text("""
            SELECT DISTINCT gc.document_id, gc.author_person_id,
                   gd.title, gd.last_modified_time, gd.doc_type
            FROM gdocs_comments gc
            JOIN gdocs_documents gd ON gd.org_id = gc.org_id
                AND gd.document_id = gc.document_id
            WHERE gc.org_id = :oid
              AND gc.author_person_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM interactions i
                  WHERE i.gdocs_document_id = gc.document_id
                    AND i.contact_id = gc.author_person_id
              )
            LIMIT 300
        """),
        {"oid": org_id},
    ).fetchall()

    created = 0
    for c in comments:
        synthetic_msg_id = f"docs:{c.document_id}:{c.author_person_id}"

        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id, gmail_message_id,
                    account_email,
                    direction, subject, summary, sentiment,
                    interaction_at, source, interaction_type,
                    weight_score, signal_score, edge_weight_multiplier,
                    gdocs_document_id
                )
                VALUES (
                    :id, :org_id, :contact_id, :gmail_message_id,
                    :account_email,
                    'inbound', :subject, :summary, 0.2,
                    COALESCE(:interaction_at, NOW()), 'gdocs', 'doc_shared',
                    0.7, 0.6, 1.5,
                    :document_id
                )
                ON CONFLICT (gdocs_document_id, contact_id)
                    WHERE gdocs_document_id IS NOT NULL
                DO NOTHING
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "contact_id": str(c.author_person_id),
                "gmail_message_id": synthetic_msg_id,
                "account_email": account_email,
                "subject": f"Doc comment: {c.title or 'document'}",
                "summary": f"External comment on {c.doc_type or 'document'}: {c.title}",
                "interaction_at": c.last_modified_time,
                "document_id": c.document_id,
            },
        )
        created += 1

    logger.info(f"Docs bridge: created {created} doc interactions for org={org_id}")
    return created
