from sqlalchemy import text
import time

from app.database import SessionLocal
from app.ingestion.gmail_connector import (
    build_gmail_service,
    fetch_emails,
    fetch_message_metadata,
    fetch_full_message,
    get_user_email,
)

from app.ingestion.email_parser import parse_headers, extract_email_body
from app.ingestion.graph_builder import upsert_contact, create_interaction
from app.ingestion.entity_extractor import extract_email_intelligence
from app.graph.relationship_calculator import recalculate_all_relationships
from datetime import datetime, timezone
from collections import defaultdict


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
    """
    if not email:
        return True

    email_lower = email.lower()
    name_lower = (name or "").lower()

    for pattern in AUTOMATED_EMAIL_PATTERNS:
        if pattern in email_lower or pattern in name_lower:
            return True

    for domain in AUTOMATED_DOMAINS:
        if domain in email_lower:
            return True

    return False


def get_email_domain(email: str) -> str:
    """Extract domain from email address."""
    if not email or "@" not in email:
        return ""
    return email.split("@")[1].lower()


def is_internal_email(contact_email: str, user_email: str) -> bool:
    """
    Check if contact is internal (same domain as the org owner).
    Filters out team member / co-founder emails that would pollute the graph.
    """
    contact_domain = get_email_domain(contact_email)
    user_domain = get_email_domain(user_email)

    if not contact_domain or not user_domain:
        return False

    # Skip personal email domains — everyone uses gmail, can't deduce "internal"
    personal_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "icloud.com", "protonmail.com", "aol.com", "mail.com",
    }
    if user_domain in personal_domains:
        return False

    return contact_domain == user_domain


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


def build_thread_context(thread_messages: list) -> str:
    """
    Build a context string from the last 3 messages in a thread.
    Used to give the LLM awareness of the full conversation.

    Args:
        thread_messages: List of already-parsed messages (dicts with subject, body, direction, date)

    Returns:
        str: Formatted thread context string (max ~6000 chars total)
    """
    if not thread_messages:
        return ""

    # Take last 3 messages, most recent last
    context_messages = thread_messages[-3:]

    context_parts = []
    for i, msg in enumerate(context_messages):
        direction_label = "THEM" if msg["direction"] == "inbound" else "YOU"
        date_str = msg.get("date", "")
        if hasattr(date_str, "strftime"):
            date_str = date_str.strftime("%b %d")

        body_snippet = (msg.get("body", "") or "")[:800].strip()
        if body_snippet:
            context_parts.append(
                f"[Message {i+1} - {direction_label} on {date_str}]:\n{body_snippet}"
            )

    return "\n\n".join(context_parts)


def run_gmail_sync(org_id, max_emails=100):
    """
    Sync Gmail emails for an organization.
    Thread-aware: groups messages by threadId and builds conversation context
    so the LLM can extract commitments buried in earlier messages.

    Args:
        org_id: Organization ID
        max_emails: Total emails to fetch
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

        # ── Fetch from both labels — Gmail returns newest first, so fetching
        # max_emails from each gives enough to find the top max_emails by date.
        # e.g. max_emails=100 → fetch 100 INBOX + 100 SENT = 200 candidates
        #      then sort all 200 by date → keep top 100 for LLM.
        pool_size = max_emails  # 100 from each label

        print(f"📧 Fetching INBOX message IDs (newest {pool_size})...")
        inbox_ids = fetch_emails(service, max_results=pool_size, label_id="INBOX")

        print(f"📤 Fetching SENT message IDs (newest {pool_size})...")
        sent_ids = fetch_emails(service, max_results=pool_size, label_id="SENT")

        # Deduplicate by message ID (a message can appear in both INBOX and SENT)
        seen_ids = set()
        all_candidates = []
        for m in inbox_ids + sent_ids:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                all_candidates.append(m)

        print(
            f"📬 {len(inbox_ids)} inbox + {len(sent_ids)} sent → "
            f"{len(all_candidates)} unique. Fetching dates to pick top {max_emails}..."
        )

        # Get internalDate for each candidate via lightweight metadata call
        dated_candidates = []
        for i, m in enumerate(all_candidates, 1):
            if i % 50 == 0:
                print(f"  Fetching metadata {i}/{len(all_candidates)}...")
            try:
                meta = fetch_message_metadata(service, m["id"])
                dated_candidates.append(meta)
            except Exception as e:
                print(f"⚠️ Could not fetch metadata for {m['id']}: {e}")
                continue

        # Sort by date descending (newest first) and cap at max_emails
        dated_candidates.sort(key=lambda x: x["internalDate"], reverse=True)
        messages = dated_candidates[:max_emails]

        print(
            f"📅 Selected {len(messages)} most recent emails by date "
            f"(from a pool of {len(dated_candidates)})"
        )

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

        update_sync_progress(db, org_id, sync_total=len(new_messages))

        # ── Step 1: Fetch full message data for all new messages ──────────────
        # Group by threadId so we can pass thread context to LLM
        print("🔍 Fetching full message details and grouping by thread...")
        thread_groups: dict = defaultdict(list)  # threadId → list of parsed msgs

        processed_count = 0
        skipped_automated = 0
        skipped_internal = 0

        all_parsed = []  # [(m_id, thread_id, parsed_msg)]

        for i, m in enumerate(new_messages, 1):
            if i % 20 == 0:
                print(f"Fetching message {i}/{len(new_messages)}...")
            try:
                msg = fetch_full_message(service, m["id"])
            except Exception as e:
                print(f"⚠️ Could not fetch message {m['id']}: {e}")
                update_sync_progress(db, org_id, sync_processed=i)
                continue

            payload = msg["payload"]
            thread_id = msg.get("threadId", m["id"])
            parsed = parse_headers(payload)
            body_text = extract_email_body(payload)

            from_email = parsed["from_email"]
            to_email = parsed["to_email"]
            name = parsed["from_name"]

            if from_email and from_email.lower() == user_email.lower():
                direction = "outbound"
                contact_email = to_email
                contact_name = parsed["to_name"] or to_email
            else:
                direction = "inbound"
                contact_email = from_email
                contact_name = name

            if not contact_email:
                skipped_automated += 1
                update_sync_progress(db, org_id, sync_processed=i)
                continue

            if is_automated_email(contact_email, contact_name):
                skipped_automated += 1
                update_sync_progress(db, org_id, sync_processed=i)
                continue

            # ── FIX 6: Skip internal team emails (same domain as user) ────────
            if is_internal_email(contact_email, user_email):
                skipped_internal += 1
                update_sync_progress(db, org_id, sync_processed=i)
                continue

            parsed_msg = {
                "gmail_id": m["id"],
                "thread_id": thread_id,
                "from_email": from_email,
                "to_email": to_email,
                "contact_email": contact_email,
                "contact_name": contact_name,
                "subject": parsed["subject"],
                "date": parsed["date"],
                "body": body_text,
                "direction": direction,
            }

            thread_groups[thread_id].append(parsed_msg)
            all_parsed.append(parsed_msg)

        print(
            f"📊 Grouped into {len(thread_groups)} threads from {len(all_parsed)} valid messages"
            f" ({skipped_automated} automated filtered, {skipped_internal} internal filtered)"
        )

        # ── Step 2: Sort each thread by date ascending (oldest first) ─────────
        for tid in thread_groups:
            thread_groups[tid].sort(
                key=lambda x: x["date"] if x["date"] else datetime.min.replace(tzinfo=timezone.utc)
            )

        # ── Step 3: Process messages — pass thread context to LLM ─────────────
        print("🧠 Running LLM extraction with thread context...")

        # Build a lookup of thread_id → messages processed so far (for context)
        thread_processed: dict = defaultdict(list)

        for i, parsed_msg in enumerate(all_parsed, 1):
            if i % 10 == 0:
                print(f"Processing message {i}/{len(all_parsed)}...")

            thread_id = parsed_msg["thread_id"]
            contact_email = parsed_msg["contact_email"]
            contact_name = parsed_msg["contact_name"]
            subject = parsed_msg["subject"]
            body_text = parsed_msg["body"]
            direction = parsed_msg["direction"]

            # Build thread context from messages already processed in this thread
            thread_context = build_thread_context(thread_processed[thread_id])

            # Detect if this is a reply
            is_reply = bool(subject and ("re:" in subject.lower() or "fwd:" in subject.lower()))
            # Also treat as reply if thread already has messages
            is_reply = is_reply or len(thread_processed[thread_id]) > 0

            # Upsert contact
            contact_id = upsert_contact(db, org_id, contact_email, contact_name)

            # Extract intelligence using LLM with thread context
            intelligence = extract_email_intelligence(
                subject,
                body_text,
                sender_name=contact_name,
                is_reply=is_reply,
                thread_context=thread_context,
            )

            # Rate limiting: Groq allows 30 requests/minute
            time.sleep(2)

            # Create interaction with enhanced data
            create_interaction(
                db,
                org_id,
                contact_id,
                parsed_msg["gmail_id"],
                subject,
                intelligence["summary"],
                parsed_msg["date"],
                direction,
                sentiment=intelligence["sentiment"],
                intent=intelligence["intent"],
                commitments=intelligence.get("commitments", []),
                topics=intelligence.get("topics", []),
                interaction_type=intelligence.get("interaction_type", "email_one_way"),
                engagement_level=intelligence.get("engagement_level", "medium"),
                reply_time_hours=None,
            )

            # Add to thread context for subsequent messages
            thread_processed[thread_id].append({
                "direction": direction,
                "date": parsed_msg["date"],
                "body": body_text,
                "subject": subject,
            })

            processed_count += 1
            update_sync_progress(db, org_id, sync_processed=i)

        db.commit()

        print(
            f"Sync completed: {processed_count} new emails processed, "
            f"{skipped_existing} already synced (skipped), "
            f"{skipped_automated} automated emails filtered, "
            f"{skipped_internal} internal emails filtered"
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
