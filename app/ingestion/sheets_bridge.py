"""
Sheets Bridge — Phase 2

Bridges Google Sheets data into the relationship graph:
1. CRM/pipeline rows with email columns → contacts enrichment

Per PDF spec: Sheets is the quantitative reality layer.
CRM rows enrich existing contacts with deal stage, deal size, etc.
No interaction edges — enrichment only.
"""

import logging
from sqlalchemy import text

from app.ingestion.graph_builder import upsert_contact
from app.ingestion.bridge_utils import get_org_domain, is_internal_email

logger = logging.getLogger(__name__)


def resolve_sheets_crm_to_contacts(db, org_id: str):
    """
    For CRM/pipeline tab rows that contain email-like fields,
    upsert into contacts and link person_id on sheets_rows.
    """
    org_domain = get_org_domain(db, org_id)

    # Find CRM/investor_pipeline rows that might have email data
    crm_rows = db.execute(
        text("""
            SELECT sr.id, sr.extracted_data, sr.person_id
            FROM sheets_rows sr
            JOIN sheets_tab_config stc ON stc.org_id = sr.org_id
                AND stc.spreadsheet_id = sr.spreadsheet_id
                AND stc.tab_name = sr.tab_name
            WHERE sr.org_id = :oid
              AND sr.person_id IS NULL
              AND sr.is_active = TRUE
              AND stc.tab_type IN ('crm', 'investor_pipeline')
            LIMIT 500
        """),
        {"oid": org_id},
    ).fetchall()

    resolved = 0
    for row in crm_rows:
        data = row.extracted_data or {}

        # Try to find email in common CRM column patterns
        email = (
            data.get("email")
            or data.get("contact_email")
            or data.get("email_address")
            or data.get("person_email")
        )
        if not email or "@" not in str(email):
            continue

        email = str(email).lower().strip()
        if is_internal_email(email, org_domain):
            continue

        name = (
            data.get("name")
            or data.get("contact_name")
            or data.get("person_name")
            or data.get("company")
            or email.split("@")[0].replace(".", " ").title()
        )

        contact_id = upsert_contact(db, org_id, email, str(name))
        if contact_id:
            db.execute(
                text("UPDATE sheets_rows SET person_id = :cid WHERE id = :rid"),
                {"cid": contact_id, "rid": row.id},
            )
            resolved += 1

    logger.info(f"Sheets bridge: resolved {resolved}/{len(crm_rows)} CRM rows for org={org_id}")
    return resolved
