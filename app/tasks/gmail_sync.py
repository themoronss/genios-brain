from sqlalchemy import text
import time

from app.database import SessionLocal
from app.ingestion.gmail_connector import (
    build_gmail_service,
    fetch_emails,
    fetch_full_message,
    get_user_email,
)

from app.ingestion.email_parser import parse_headers, extract_email_body
from app.ingestion.graph_builder import upsert_contact, create_interaction
from app.ingestion.entity_extractor import extract_email_intelligence
from app.graph.relationship_calculator import recalculate_all_relationships
from datetime import datetime, timezone


# Automated email patterns to filter out
AUTOMATED_EMAIL_PATTERNS = [
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "newsletter",
    "digest",
    "alert",
    "notification",
    "automated",
    "bounce",
    "mailer-daemon",
    "postmaster",
    "jobnotification",
    "jobalert",
]

AUTOMATED_DOMAINS = [
    "@linkedin.com",
    "@substack.com",
    "@medium.com",
    "@facebookmail.com",
    "@notifications.",
    "@alert.",
]


def is_automated_email(email, name):
    """
    Check if an email address is from an automated sender.

    Args:
        email: Email address
        name: Sender name

    Returns:
        bool: True if automated, False if real person
    """
    if not email:
        return True

    email_lower = email.lower()
    name_lower = (name or "").lower()

    # Check for automated patterns in email
    for pattern in AUTOMATED_EMAIL_PATTERNS:
        if pattern in email_lower or pattern in name_lower:
            return True

    # Check for automated domains
    for domain in AUTOMATED_DOMAINS:
        if domain in email_lower:
            return True

    return False


def update_sync_progress(db, org_id: str, **kwargs):
    """Update sync progress in oauth_tokens table."""
    set_clauses = []
    params = {"org_id": org_id}
    for key, value in kwargs.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value

    if set_clauses:
        query = (
            f"UPDATE oauth_tokens SET {', '.join(set_clauses)} WHERE org_id = :org_id"
        )
        db.execute(text(query), params)
        db.commit()


def run_gmail_sync(org_id, max_emails=100):
    """
    Sync Gmail emails for an organization.

    Args:
        org_id: Organization ID
        max_emails: Maximum number of emails to sync (default: 100)
    """
    db = SessionLocal()

    # Mark sync as running
    update_sync_progress(
        db,
        org_id,
        sync_status="running",
        sync_processed=0,
        sync_total=0,
        sync_error=None,
        sync_started_at=datetime.now(timezone.utc),
    )

    try:
        token = db.execute(
            text(
                """
            SELECT access_token, refresh_token
            FROM oauth_tokens
            WHERE org_id = :org_id
            """
            ),
            {"org_id": org_id},
        ).fetchone()

        if not token:
            print("No Gmail token found")
            update_sync_progress(
                db, org_id, sync_status="error", sync_error="No Gmail token found"
            )
            db.close()
            return

        access_token = token[0]
        refresh_token = token[1]

        service = build_gmail_service(access_token, refresh_token)

        # Get the user's own email address
        user_email = get_user_email(service)
        print(f"Syncing emails for: {user_email}")

        messages = fetch_emails(service, max_results=max_emails)

        print(f"Fetched {len(messages)} emails from Gmail")

        # Pre-filter: find which emails are actually new
        new_messages = []
        for m in messages:
            existing = db.execute(
                text(
                    """
                    SELECT id FROM interactions 
                    WHERE gmail_message_id = :gmail_id
                """
                ),
                {"gmail_id": m["id"]},
            ).fetchone()

            if not existing:
                new_messages.append(m)

        skipped_existing = len(messages) - len(new_messages)
        print(
            f"Skipping {skipped_existing} already synced emails. Processing {len(new_messages)} new emails."
        )

        # Update total count with only new emails
        update_sync_progress(db, org_id, sync_total=len(new_messages))

        processed = 0
        skipped_automated = 0

        for i, m in enumerate(new_messages, 1):

            # Progress indicator
            if i % 10 == 0:
                print(f"Processing email {i}/{len(new_messages)}...")

            msg = fetch_full_message(service, m["id"])

            payload = msg["payload"]

            parsed = parse_headers(payload)

            from_email = parsed["from_email"]
            to_email = parsed["to_email"]
            name = parsed["from_name"]
            subject = parsed["subject"]
            date = parsed["date"]

            # Extract email body
            body_text = extract_email_body(payload)

            # Determine direction based on user's email address
            # Inbound: someone sent TO me (from_email is the contact)
            # Outbound: I sent TO someone (to_email is the contact)
            if from_email and from_email.lower() == user_email.lower():
                direction = "outbound"
                contact_email = to_email
                contact_name = parsed["to_name"] or to_email  # Use to_name if available
            else:
                direction = "inbound"
                contact_email = from_email
                contact_name = name

            # Skip if we can't identify the contact
            if not contact_email:
                skipped_automated += 1
                update_sync_progress(db, org_id, sync_processed=i)
                continue

            # Skip automated emails
            if is_automated_email(contact_email, contact_name):
                skipped_automated += 1
                # Still update progress so the bar moves
                update_sync_progress(db, org_id, sync_processed=i)
                continue

            contact_id = upsert_contact(db, org_id, contact_email, contact_name)

            # Extract intelligence using LLM
            intelligence = extract_email_intelligence(subject, body_text, contact_name)

            # Rate limiting: Groq allows 30 requests/minute
            # 60 seconds / 30 requests = 2 seconds per request
            time.sleep(2)

            # Create interaction with enhanced data
            create_interaction(
                db,
                org_id,
                contact_id,
                m["id"],
                subject,
                intelligence["summary"],  # Use LLM-generated summary
                date,
                direction,
                sentiment=intelligence["sentiment"],
                intent=intelligence["intent"],
                commitments=intelligence["commitments"],
                topics=intelligence["topics"],
            )

            processed += 1

            # Update progress after each email
            update_sync_progress(db, org_id, sync_processed=i)

        db.commit()

        print(
            f"Sync completed: {processed} new emails processed, "
            f"{skipped_existing} already synced (skipped), "
            f"{skipped_automated} automated emails filtered"
        )

        # Recalculate relationship stages after sync
        print("Recalculating relationship stages...")
        try:
            updated_count = recalculate_all_relationships(db, org_id)
            print(f"✓ Updated {updated_count} contact relationship stages")
        except Exception as e:
            print(f"✗ Error recalculating relationships: {e}")

        # Mark sync as completed
        update_sync_progress(
            db,
            org_id,
            sync_status="completed",
            last_synced_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        print(f"❌ Sync failed with error: {e}")
        update_sync_progress(
            db,
            org_id,
            sync_status="error",
            sync_error=str(e)[:500],
        )

    finally:
        db.close()
