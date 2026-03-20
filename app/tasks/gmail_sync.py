from sqlalchemy import text
import time
from email.utils import parseaddr

from app.database import SessionLocal
from app.ingestion.gmail_connector import (
    build_gmail_service,
    fetch_emails,
    fetch_message_headers,
    fetch_full_message,
    get_user_email,
)

from app.ingestion.email_parser import parse_headers, extract_email_body
from app.ingestion.graph_builder import (
    upsert_contact,
    create_interaction,
    store_state_event,
    upsert_state_entity,
    update_relationship_stats_only,
)
from app.ingestion.entity_extractor import (
    extract_email_intelligence,
    compute_signal_score,
)
from app.ingestion.email_classifier import classify_email, parse_system_email
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
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "protonmail.com",
        "aol.com",
        "mail.com",
    }
    if user_domain in personal_domains:
        return False

    return contact_domain == user_domain


def update_sync_progress(db, org_id: str, account_email: str = None, **kwargs):
    """
    Update sync progress in oauth_tokens table.
    If account_email is provided, scopes the update to that specific account.
    Otherwise updates the first/only token for the org (legacy behaviour).
    """
    set_clauses = []
    params = {"org_id": org_id}
    for key, value in kwargs.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value

    if set_clauses:
        if account_email:
            params["account_email"] = account_email
            query = (
                f"UPDATE oauth_tokens SET {', '.join(set_clauses)} "
                f"WHERE org_id = :org_id AND account_email = :account_email"
            )
        else:
            query = f"UPDATE oauth_tokens SET {', '.join(set_clauses)} WHERE org_id = :org_id"
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


# ── Update 1: Collect exactly N valid emails ──────────────────────────────────


def collect_valid_email_ids(service, user_email: str, target: int = 100) -> list:
    """
    Incrementally fetch email IDs using Gmail-side q-filter and lightweight header
    checks until exactly `target` valid human-to-human emails are collected.

    Strategy:
    1. Fetch a page of up to 50 IDs using the q-param (Gmail-side filter removes
       promotions, social, and obvious no-reply senders before any data is downloaded).
    2. For each ID, call fetch_message_headers() — cheap (no body download) — to get
       From/To headers.
    3. Run is_automated_email() and is_internal_email() on the headers.
    4. If the email passes both checks, it is added to the valid list.
    5. Repeat with the next page token until the list reaches `target` or Gmail runs dry.

    Returns:
        list of dicts, each with at minimum: id, threadId, internalDate
    """
    valid_messages = []
    page_token = None
    page_count = 0
    max_pages = 40  # safety valve — stops after 2000 candidates at 50/page

    print(f"🔍 Collecting {target} valid emails via incremental header-check loop...")

    while len(valid_messages) < target and page_count < max_pages:
        # Fetch a page of up to 50 IDs
        batch_ids, page_token = fetch_emails(
            service,
            max_results=50,
            query=("(in:inbox OR in:sent) " "-label:promotions -label:social"),
            page_token=page_token,
        )
        page_count += 1

        if not batch_ids:
            print(f"  Gmail returned no more messages after page {page_count}.")
            break

        # Lightweight header check for each ID in the batch
        for msg_stub in batch_ids:
            if len(valid_messages) >= target:
                break

            try:
                headers = fetch_message_headers(service, msg_stub["id"])
            except Exception as e:
                print(f"  ⚠️ Could not fetch headers for {msg_stub['id']}: {e}")
                continue

            from_raw = headers.get("from_raw", "")
            to_raw = headers.get("to_raw", "")

            # Determine which side is the contact
            from_name, from_email = parseaddr(from_raw)
            _, to_email = parseaddr(to_raw)

            if from_email and from_email.lower() == user_email.lower():
                contact_email = to_email
                contact_name = ""
            else:
                contact_email = from_email
                contact_name = from_name

            contact_email = (contact_email or "").strip().lower()

            if not contact_email:
                continue

            valid_messages.append(
                {
                    "id": headers["id"],
                    "threadId": headers["threadId"],
                    "internalDate": headers["internalDate"],
                }
            )

        print(
            f"  Page {page_count}: batch={len(batch_ids)}, "
            f"valid so far={len(valid_messages)}/{target}"
        )

        if not page_token:
            print("  No more pages available in Gmail.")
            break

    print(
        f"✅ Collected {len(valid_messages)} valid email IDs "
        f"(scanned {page_count} pages)"
    )
    return valid_messages


# ── Main sync function ────────────────────────────────────────────────────────


def run_gmail_sync(org_id, max_emails=100, account_email: str = None):
    """
    Sync Gmail emails for an organization.
    Thread-aware: groups messages by threadId and builds conversation context
    so the LLM can extract commitments buried in earlier messages.

    Update 1: Now collects exactly max_emails valid (non-automated, non-internal)
              emails using an incremental Gmail-side filter loop before any full
              message downloads happen.
    Update 2: Passes contact_role extracted by LLM into upsert_contact() so
              the contacts table gets populated with Investor/Customer/etc. tags.
    Update 3: After processing the primary contact, also creates interaction rows
              for CC participants, making the graph truly many-to-many.
    Update 4: Accepts optional account_email to sync one specific connected Gmail
              account. If omitted, syncs all connected accounts for the org.

    Args:
        org_id: Organization ID
        max_emails: Target number of valid emails to sync (default: 100)
        account_email: Specific Gmail account to sync. If None, syncs all accounts.
    """
    db = SessionLocal()

    try:
        # ── Update 4: Resolve which token(s) to sync ──────────────────────────
        if account_email:
            tokens = db.execute(
                text(
                    """
                    SELECT access_token, refresh_token, account_email
                    FROM oauth_tokens
                    WHERE org_id = :org_id AND account_email = :account_email
                    """
                ),
                {"org_id": org_id, "account_email": account_email},
            ).fetchall()
        else:
            # Try new multi-account schema first
            tokens = db.execute(
                text(
                    """
                    SELECT access_token, refresh_token,
                           COALESCE(account_email, 'default') AS account_email
                    FROM oauth_tokens
                    WHERE org_id = :org_id
                    """
                ),
                {"org_id": org_id},
            ).fetchall()

        if not tokens:
            print("No Gmail token found")
            update_sync_progress(
                db, org_id, sync_status="error", sync_error="No Gmail token found"
            )
            db.close()
            return

        # ── Sync each connected account ───────────────────────────────────────
        for token_row in tokens:
            _sync_single_account(
                db=db,
                org_id=org_id,
                access_token=token_row[0],
                refresh_token=token_row[1],
                account_identifier=token_row[2],
                max_emails=max_emails,
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


def _sync_single_account(
    db, org_id, access_token, refresh_token, account_identifier, max_emails
):
    """
    Internal: run the full sync pipeline for one Gmail account token.
    """
    # Mark sync as running
    update_sync_progress(
        db,
        org_id,
        account_email=account_identifier,
        sync_status="running",
        sync_processed=0,
        sync_total=0,
        sync_error=None,
        sync_started_at=datetime.now(timezone.utc),
    )

    try:
        service = build_gmail_service(access_token, refresh_token)

        # Get the user's own email address
        user_email = get_user_email(service)
        print(f"📧 Syncing emails for: {user_email} (account: {account_identifier})")

        # ── Update 1: Collect exactly max_emails valid email IDs ──────────────
        valid_ids = collect_valid_email_ids(service, user_email, target=max_emails)

        # Pre-filter: skip emails already in the DB
        new_ids = []
        for m in valid_ids:
            existing = db.execute(
                text(
                    """
                    SELECT id FROM interactions
                    WHERE gmail_message_id = :gmail_id
                    LIMIT 1
                """
                ),
                {"gmail_id": m["id"]},
            ).fetchone()

            if not existing:
                new_ids.append(m)

        skipped_existing = len(valid_ids) - len(new_ids)
        print(
            f"Skipping {skipped_existing} already synced emails. "
            f"Processing {len(new_ids)} new emails."
        )

        update_sync_progress(
            db, org_id, account_email=account_identifier, sync_total=len(new_ids)
        )

        # ── Step 1: Fetch full message data + group by thread ─────────────────
        print("🔍 Fetching full message details and grouping by thread...")
        thread_groups: dict = defaultdict(list)

        processed_count = 0
        skipped_automated = 0
        skipped_internal = 0

        all_parsed = []  # list of parsed message dicts

        for i, m in enumerate(new_ids, 1):
            if i % 20 == 0:
                print(f"Fetching message {i}/{len(new_ids)}...")
            try:
                msg = fetch_full_message(service, m["id"])
            except Exception as e:
                print(f"⚠️ Could not fetch message {m['id']}: {e}")
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
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
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
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
                # Update 3: carry CC list for many-to-many linking
                "cc_list": parsed.get("cc_list", []),
            }

            thread_groups[thread_id].append(parsed_msg)
            all_parsed.append(parsed_msg)

        print(
            f"📊 Grouped into {len(thread_groups)} threads from {len(all_parsed)} valid messages"
            f" ({skipped_automated} automated filtered, {skipped_internal} internal filtered)"
        )

        # ── Step 2: Sort each thread by date ascending ────────────────────────
        for tid in thread_groups:
            thread_groups[tid].sort(
                key=lambda x: (
                    x["date"]
                    if x["date"]
                    else datetime.min.replace(tzinfo=timezone.utc)
                )
            )

        # ── Step 3: Email classification & processing ────────────────────────
        print("🔍 Classifying and processing emails...")

        thread_processed: dict = defaultdict(list)
        llm_processed = 0
        system_emails = 0
        discarded_emails = 0
        weak_emails = 0

        for i, parsed_msg in enumerate(all_parsed, 1):
            if i % 10 == 0:
                print(f"Processing message {i}/{len(all_parsed)}...")

            thread_id = parsed_msg["thread_id"]
            contact_email = parsed_msg["contact_email"]
            contact_name = parsed_msg["contact_name"]
            subject = parsed_msg["subject"]
            body_text = parsed_msg["body"]
            direction = parsed_msg["direction"]
            cc_list = parsed_msg.get("cc_list", [])

            # ── Update 1.1: Classify email ────────────────────────────────────
            from_email = parsed_msg["from_email"]

            # Get headers for unsubscribe detection
            headers = (
                {}
            )  # Would need to pass this from fetch, but for now use empty dict

            category = classify_email(
                subject=subject or "",
                sender_email=from_email or "",
                body=body_text or "",
                headers=headers,
            )

            # ── Branch processing by category ─────────────────────────────────
            if category == "SYSTEM":
                # Parse structured state data (GST, payments, invoices) → State Graph (v2.2)
                parsed_state = parse_system_email(
                    subject=subject or "",
                    body=body_text or "",
                    sender_email=from_email or "",
                )
                # Use UPSERT logic: updates existing entity if found, inserts if new
                parsed_state["source_email_id"] = msg_id  # Track source email
                upsert_state_entity(db, org_id, parsed_state)
                system_emails += 1
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
                continue

            elif category == "DISCARD":
                # Skip marketing/newsletter emails
                discarded_emails += 1
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
                continue

            elif category == "WEAK":
                # Update stats only (no LLM extraction)
                contact_id = upsert_contact(
                    db, org_id, contact_email, contact_name, entity_type=None
                )
                update_relationship_stats_only(
                    db, org_id, contact_id, parsed_msg["date"]
                )
                weak_emails += 1
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
                continue

            # ── STRONG category: Full LLM extraction ──────────────────────────

            # Build thread context from messages already processed in this thread
            thread_context = build_thread_context(thread_processed[thread_id])

            # Detect if this is a reply
            is_reply = bool(
                subject and ("re:" in subject.lower() or "fwd:" in subject.lower())
            )
            is_reply = is_reply or len(thread_processed[thread_id]) > 0

            # Extract intelligence using LLM with thread context
            intelligence = extract_email_intelligence(
                subject,
                body_text,
                sender_name=contact_name,
                is_reply=is_reply,
                thread_context=thread_context,
            )

            # Compute signal score
            signal = compute_signal_score(intelligence, body_text or "")
            llm_processed += 1

            # Rate limiting: Groq allows 30 requests/minute
            time.sleep(2)

            # ── Update 2: Pass contact_role into upsert_contact ──
            contact_role = intelligence.get("contact_role")
            contact_id = upsert_contact(
                db, org_id, contact_email, contact_name, entity_type=contact_role
            )

            # Create the primary interaction row with signal_score
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
                account_email=user_email,
                signal_score=signal,
            )

            # ── Update 3: Create interaction rows for CC participants ──────────
            for cc_person in cc_list:
                cc_email = cc_person.get("email", "").strip().lower()
                cc_name = cc_person.get("name", cc_email)

                if not cc_email:
                    continue
                # Skip user's own address in CC
                if cc_email == user_email.lower():
                    continue
                if is_automated_email(cc_email, cc_name):
                    continue
                if is_internal_email(cc_email, user_email):
                    continue

                # Upsert CC contact (no LLM role for CC — use None to preserve existing tag)
                cc_contact_id = upsert_contact(
                    db, org_id, cc_email, cc_name, entity_type=None
                )

                # Link the same email to this CC participant without re-running LLM
                # direction is always "inbound" from the CC participants' perspective
                try:
                    create_interaction(
                        db,
                        org_id,
                        cc_contact_id,
                        parsed_msg["gmail_id"],  # same gmail_message_id
                        subject,
                        intelligence["summary"],  # reuse primary summary
                        parsed_msg["date"],
                        "cc",  # distinct direction for CC participants
                        sentiment=intelligence["sentiment"],
                        intent=intelligence["intent"],
                        commitments=[],  # commitments tracked against primary contact only
                        topics=intelligence.get("topics", []),
                        interaction_type=intelligence.get(
                            "interaction_type", "email_one_way"
                        ),
                        engagement_level=intelligence.get("engagement_level", "medium"),
                        reply_time_hours=None,
                        account_email=user_email,
                    )
                    print(
                        f"  🔗 CC edge: {cc_email} ↔ gmail:{parsed_msg['gmail_id'][:8]}..."
                    )
                except Exception as e:
                    print(f"  ⚠️ Could not create CC interaction for {cc_email}: {e}")
                    continue

            # Add to thread context for subsequent messages
            thread_processed[thread_id].append(
                {
                    "direction": direction,
                    "date": parsed_msg["date"],
                    "body": body_text,
                    "subject": subject,
                }
            )

            processed_count += 1
            update_sync_progress(
                db, org_id, account_email=account_identifier, sync_processed=i
            )

        db.commit()

        print(
            f"✅ Sync completed: {processed_count} new emails processed, "
            f"{skipped_existing} already synced (skipped), "
            f"{skipped_automated} automated emails filtered, "
            f"{skipped_internal} internal emails filtered\n"
            f"📊 Classification: {llm_processed} STRONG (LLM), {weak_emails} WEAK (stats only), "
            f"{system_emails} SYSTEM (state), {discarded_emails} DISCARD (skipped)"
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
            account_email=account_identifier,
            sync_status="completed",
            last_synced_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        print(f"❌ Sync failed for account {account_identifier}: {e}")
        update_sync_progress(
            db,
            org_id,
            account_email=account_identifier,
            sync_status="error",
            sync_error=str(e)[:500],
        )
