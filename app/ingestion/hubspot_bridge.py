"""
HubSpot Bridge — transforms HubSpot contacts + deals into our schema.

Contacts → contacts table via upsert_contact (same dedup + category detection as Gmail)
           + lightweight `interactions` record with source='hubspot' for graph scoring
Deals    → commitments table (linked to matching contact)

Lifecycle stage → relationship_stage mapping:
  lead / subscriber / marketingqualifiedlead  → "prospect"
  salesqualifiedlead / opportunity            → "active"
  customer / evangelist                       → "active"
  other                                       → "active"
  (no match)                                  → "active"

Source weight in relationship_calculator: hubspot = 0.15
"""

import uuid
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion.graph_builder import upsert_contact

logger = logging.getLogger(__name__)

# HubSpot lifecycle stage → our relationship_stage
_STAGE_MAP = {
    "lead": "prospect",
    "subscriber": "prospect",
    "marketingqualifiedlead": "prospect",
    "salesqualifiedlead": "active",
    "opportunity": "active",
    "customer": "active",
    "evangelist": "active",
    "other": "active",
}

# HubSpot deal stage keywords → commitment status
_DEAL_CLOSED_WON = {"closedwon", "closed won", "closed_won"}
_DEAL_CLOSED_LOST = {"closedlost", "closed lost", "closed_lost"}


def _upsert_hubspot_contact(db: Session, org_id: str, hs_contact: dict) -> str | None:
    """
    Upsert a HubSpot contact via graph_builder.upsert_contact (full dedup + category detection),
    then enrich with CRM-specific fields and create a lightweight interaction record.
    Returns contact_id or None if no usable identity.
    """
    props = hs_contact.get("properties", {})

    first = (props.get("firstname") or "").strip()
    last = (props.get("lastname") or "").strip()
    name = f"{first} {last}".strip()
    email = (props.get("email") or "").strip().lower() or None

    if not name and email:
        name = email.split("@")[0].replace(".", " ").title()
    if not name:
        return None

    company = (props.get("company") or "").strip() or None
    job_title = (props.get("jobtitle") or "").strip() or None
    lifecycle = (props.get("lifecyclestage") or "").lower().replace(" ", "")
    relationship_stage = _STAGE_MAP.get(lifecycle, "active")

    # Use graph_builder upsert — handles fuzzy dedup + category detection
    contact_id = upsert_contact(
        db, org_id,
        email=email or f"hubspot_{hs_contact.get('id', uuid.uuid4())}@noemail.local",
        name=name,
        entity_type=None,  # let category_detector classify
    )
    if not contact_id:
        return None

    # Enrich with CRM fields not set by upsert_contact
    db.execute(
        text("""
            UPDATE contacts SET
                company      = COALESCE(company, :company),
                job_title    = COALESCE(job_title, :job_title),
                relationship_stage = :stage,
                data_source  = COALESCE(data_source, 'hubspot')
            WHERE id = :cid
        """),
        {
            "company": company,
            "job_title": job_title,
            "stage": relationship_stage,
            "cid": contact_id,
        },
    )

    # Create / skip interaction record (idempotent — check by source + contact + type)
    last_modified = props.get("lastmodifieddate") or props.get("createdate")
    subject = f"HubSpot CRM: {name}" + (f" @ {company}" if company else "")
    summary = (
        f"HubSpot contact — {job_title or 'contact'}"
        + (f" at {company}" if company else "")
        + f" | Stage: {relationship_stage} | Lifecycle: {lifecycle or 'unknown'}"
    )

    existing_interaction = db.execute(
        text("""
            SELECT id FROM interactions
            WHERE org_id = :org_id AND contact_id = :cid
              AND source = 'hubspot' AND interaction_type = 'crm_contact'
            LIMIT 1
        """),
        {"org_id": org_id, "cid": contact_id},
    ).fetchone()

    if existing_interaction:
        db.execute(
            text("""
                UPDATE interactions
                SET summary = :summary,
                    interaction_at = COALESCE(:interaction_at::timestamptz, interaction_at)
                WHERE id = :id
            """),
            {"summary": summary, "interaction_at": last_modified, "id": str(existing_interaction[0])},
        )
    else:
        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id,
                    direction, subject, summary, sentiment,
                    interaction_at, source, interaction_type,
                    weight_score, signal_score
                )
                VALUES (
                    :id, :org_id, :cid,
                    'bidirectional', :subject, :summary, 0.1,
                    COALESCE(:interaction_at::timestamptz, NOW()), 'hubspot', 'crm_contact',
                    0.15, 0.2
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "cid": contact_id,
                "subject": subject,
                "summary": summary,
                "interaction_at": last_modified,
            },
        )

    return contact_id


def _upsert_hubspot_deal(
    db: Session,
    org_id: str,
    hs_deal: dict,
    contact_id: str | None,
) -> str | None:
    """
    Insert a HubSpot deal as a commitment linked to a contact.
    Also creates an interaction for the deal so it's visible in the graph.
    Returns commitment_id or None if deal has no name.
    """
    props = hs_deal.get("properties", {})
    deal_name = (props.get("dealname") or "").strip()
    if not deal_name:
        return None

    deal_stage = (props.get("dealstage") or "").lower().replace(" ", "")
    amount = props.get("amount") or None
    close_date = props.get("closedate") or None

    if deal_stage in _DEAL_CLOSED_WON:
        status = "FULFILLED"
    elif deal_stage in _DEAL_CLOSED_LOST:
        status = "MISSED"
    else:
        status = "OPEN"

    commit_text = deal_name
    if amount:
        try:
            commit_text += f" (₹{float(amount):,.0f})"
        except (ValueError, TypeError):
            pass

    # Upsert commitment
    existing = db.execute(
        text("""
            SELECT id FROM commitments
            WHERE org_id = :oid
              AND LOWER(commit_text) = LOWER(:text)
              AND (contact_id = :cid OR :cid IS NULL)
            LIMIT 1
        """),
        {"oid": org_id, "text": commit_text, "cid": contact_id},
    ).fetchone()

    if existing:
        db.execute(
            text("UPDATE commitments SET status = :status WHERE id = :id"),
            {"status": status, "id": str(existing[0])},
        )
        commitment_id = str(existing[0])
    else:
        commitment_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO commitments
                  (id, org_id, contact_id, commit_text, owner, status, due_date)
                VALUES
                  (:id, :oid, :cid, :text, 'hubspot', :status, :due_date::timestamptz)
            """),
            {
                "id": commitment_id,
                "oid": org_id,
                "cid": contact_id,
                "text": commit_text,
                "status": status,
                "due_date": close_date,
            },
        )

    # Create interaction for the deal (makes deal visible in relationship graph)
    if contact_id:
        deal_subject = f"HubSpot Deal: {deal_name}"
        deal_summary = f"Deal '{deal_name}' — {deal_stage} | Status: {status}" + (f" | Close: {close_date}" if close_date else "")

        existing_deal_interaction = db.execute(
            text("""
                SELECT id FROM interactions
                WHERE org_id = :org_id AND contact_id = :cid
                  AND source = 'hubspot' AND interaction_type = 'crm_deal'
                  AND subject = :subject
                LIMIT 1
            """),
            {"org_id": org_id, "cid": contact_id, "subject": deal_subject},
        ).fetchone()

        if existing_deal_interaction:
            db.execute(
                text("UPDATE interactions SET summary = :summary WHERE id = :id"),
                {"summary": deal_summary, "id": str(existing_deal_interaction[0])},
            )
        else:
            db.execute(
                text("""
                    INSERT INTO interactions (
                        id, org_id, contact_id,
                        direction, subject, summary, sentiment,
                        interaction_at, source, interaction_type,
                        weight_score, signal_score
                    )
                    VALUES (
                        :id, :org_id, :cid,
                        'bidirectional', :subject, :summary, 0.1,
                        COALESCE(:close_date::timestamptz, NOW()), 'hubspot', 'crm_deal',
                        0.20, 0.25
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "org_id": org_id,
                    "cid": contact_id,
                    "subject": deal_subject,
                    "summary": deal_summary,
                    "close_date": close_date,
                },
            )

    return commitment_id


def run_hubspot_bridge(db: Session, org_id: str, contacts: list, deals: list) -> dict:
    """
    Upsert all HubSpot contacts and deals into our schema.
    Returns a summary dict with counts.
    """
    contacts_upserted = 0
    deals_upserted = 0

    # hs_contact_id → our contact_id for deal association
    hs_id_to_contact: dict[str, str] = {}

    for hs_contact in contacts:
        try:
            cid = _upsert_hubspot_contact(db, org_id, hs_contact)
            if cid:
                hs_id_to_contact[str(hs_contact.get("id", ""))] = cid
                contacts_upserted += 1
        except Exception as e:
            logger.warning(f"HubSpot contact upsert failed ({hs_contact.get('id')}): {e}")

    db.commit()

    for hs_deal in deals:
        try:
            assoc = hs_deal.get("associations", {}).get("contacts", {}).get("results", [])
            contact_id = None
            if assoc:
                hs_cid = str(assoc[0].get("id", ""))
                contact_id = hs_id_to_contact.get(hs_cid)

            did = _upsert_hubspot_deal(db, org_id, hs_deal, contact_id)
            if did:
                deals_upserted += 1
        except Exception as e:
            logger.warning(f"HubSpot deal upsert failed ({hs_deal.get('id')}): {e}")

    db.commit()
    return {"contacts_upserted": contacts_upserted, "deals_upserted": deals_upserted}
