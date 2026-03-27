"""
Drive Bridge — Phase 2

Bridges Google Drive data into the relationship graph:
1. Resolve Shared Drive member emails → contacts
2. Resolve file owner emails → contacts
3. Create FILE_SHARED interactions for externally shared files

Per PDF spec: Drive feeds Authority Graph (40%) — Shared Drive roles
are explicit org structure with 0.95 confidence.
"""

import logging
from uuid import uuid4
from sqlalchemy import text

from app.ingestion.graph_builder import upsert_contact
from app.ingestion.bridge_utils import get_org_domain, is_internal_email

logger = logging.getLogger(__name__)


def resolve_drive_people_to_contacts(db, org_id: str):
    """
    Resolve external people found in Drive to the contacts table:
    1. Shared Drive members (highest value — explicit org structure)
    2. File owners for externally shared files
    """
    org_domain = get_org_domain(db, org_id)
    resolved = 0

    # 1. Shared Drive members — resolve external members
    members = db.execute(
        text("""
            SELECT id, email, is_external
            FROM gdrive_shared_drive_members
            WHERE org_id = :oid AND person_id IS NULL
              AND email IS NOT NULL AND email != ''
        """),
        {"oid": org_id},
    ).fetchall()

    for m in members:
        email = m.email.lower().strip()
        if not email or "@" not in email:
            continue
        if is_internal_email(email, org_domain):
            continue

        name = email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)
        if contact_id:
            db.execute(
                text("UPDATE gdrive_shared_drive_members SET person_id = :cid WHERE id = :mid"),
                {"cid": contact_id, "mid": m.id},
            )
            resolved += 1

    # 2. File owners for externally shared files
    owners = db.execute(
        text("""
            SELECT DISTINCT owner_email
            FROM gdrive_files
            WHERE org_id = :oid AND is_shared_externally = TRUE
              AND owner_email IS NOT NULL
              AND owner_person_id IS NULL
        """),
        {"oid": org_id},
    ).fetchall()

    for o in owners:
        email = o.owner_email.lower().strip()
        if not email or "@" not in email:
            continue
        if is_internal_email(email, org_domain):
            # Internal owner — still resolve for graph but don't count as external
            continue

        name = email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)
        if contact_id:
            db.execute(
                text("UPDATE gdrive_files SET owner_person_id = :cid WHERE org_id = :oid AND owner_email = :email"),
                {"cid": contact_id, "oid": org_id, "email": o.owner_email},
            )
            resolved += 1

    logger.info(f"Drive bridge: resolved {resolved} people for org={org_id}")
    return resolved


def create_drive_interactions(db, org_id: str):
    """
    Create FILE_SHARED interaction for externally shared files.
    Weight: 1.5x per PDF spec.
    """
    org_domain = get_org_domain(db, org_id)

    # Get user's primary email so graph edges connect to the user node
    user_row = db.execute(text("SELECT email FROM orgs WHERE id = :oid"), {"oid": org_id}).fetchone()
    account_email = user_row.email if user_row else None

    # Find externally shared files with resolved owners
    shared_files = db.execute(
        text("""
            SELECT f.id, f.file_id, f.file_name, f.owner_person_id,
                   f.modified_time, f.content_type
            FROM gdrive_files f
            WHERE f.org_id = :oid
              AND f.is_shared_externally = TRUE
              AND f.owner_person_id IS NOT NULL
              AND f.trashed = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM interactions i
                  WHERE i.gdrive_file_id = f.file_id
                    AND i.contact_id = f.owner_person_id
              )
            LIMIT 300
        """),
        {"oid": org_id},
    ).fetchall()

    created = 0
    for f in shared_files:
        synthetic_msg_id = f"drive:{f.file_id}:{f.owner_person_id}"

        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id, gmail_message_id,
                    account_email,
                    direction, subject, summary, sentiment,
                    interaction_at, source, interaction_type,
                    weight_score, signal_score, edge_weight_multiplier,
                    gdrive_file_id
                )
                VALUES (
                    :id, :org_id, :contact_id, :gmail_message_id,
                    :account_email,
                    'bidirectional', :subject, :summary, 0.2,
                    COALESCE(:interaction_at, NOW()), 'drive', 'file_shared',
                    0.6, 0.5, 1.5,
                    :file_id
                )
                ON CONFLICT (gdrive_file_id, contact_id)
                    WHERE gdrive_file_id IS NOT NULL
                DO NOTHING
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "contact_id": str(f.owner_person_id),
                "gmail_message_id": synthetic_msg_id,
                "account_email": account_email,
                "subject": f"Shared: {f.file_name or 'file'}",
                "summary": f"File shared externally: {f.file_name} ({f.content_type})",
                "interaction_at": f.modified_time,
                "file_id": f.file_id,
            },
        )
        created += 1

    logger.info(f"Drive bridge: created {created} file-shared interactions for org={org_id}")
    return created
