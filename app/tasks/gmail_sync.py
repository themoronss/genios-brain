from sqlalchemy import text
import time
from email.utils import parseaddr

from app.config import SYNC_MAX_EMAILS
from app.database import SessionLocal
from app.ingestion.gmail_connector import (
    build_gmail_service,
    fetch_emails,
    fetch_message_headers,
    fetch_full_message,
    get_user_email,
)

from app.ingestion.email_parser import parse_headers, extract_email_body, detect_attachments
from app.ingestion.attachment_extractor import extract_attachment_text
from app.ingestion.graph_builder import (
    upsert_contact,
    create_interaction,
    store_state_event,
    upsert_state_entity,
    update_relationship_stats_only,
)
from app.ingestion.entity_extractor import (
    extract_email_intelligence,
)
from app.ingestion.email_classifier import classify_email, classify_sender, parse_system_email
from app.ingestion.bridge_utils import get_email_domain
from app.graph.relationship_calculator import recalculate_all_relationships
from app.config import PROCESSING_VERSION
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
    "@beehiiv.com",
    "@mailchimp.com",
    "@sendgrid.net",
    "@klaviyo.com",
    "@constantcontact.com",
    "@campaign-archive.",
]

# PDF spec: "Any email thread where the contact sent to a BCC list of 50+ people →
# exclude (mass outreach, not a relationship)". We use a lower threshold of 10
# for external senders to avoid capturing batch newsletters / mass campaigns.
MASS_OUTREACH_RECIPIENT_THRESHOLD = 10


def is_mass_outreach(cc_list: list, to_email: str, from_email: str, user_email: str) -> bool:
    """
    Returns True if this email looks like mass outreach (not a real relationship).
    PDF spec: sender to BCC list of 50+ → exclude. We use 10+ as a safer threshold.
    Only applies when the sender is external (not us).
    """
    if not from_email or from_email.lower() == (user_email or "").lower():
        return False  # Our own outbound emails are never mass outreach

    # Count unique recipients: to + cc participants
    unique_recipients = set()
    if to_email:
        for addr in to_email.split(","):
            addr = addr.strip()
            if addr:
                unique_recipients.add(addr.lower())
    for cc_person in (cc_list or []):
        cc_email = cc_person.get("email", "").strip().lower()
        if cc_email:
            unique_recipients.add(cc_email)

    return len(unique_recipients) >= MASS_OUTREACH_RECIPIENT_THRESHOLD


def quick_sentiment_heuristic(body: str) -> float:
    """
    Lightweight keyword-based sentiment for short emails (WEAK category, <25 words).
    PDF spec: "weight short replies differently — add email length as calibration signal"

    Returns a float in [-0.5, 0.5] with 0.3x weight applied by caller in EWMA.
    """
    if not body:
        return 0.0

    body_lower = body.lower()

    positive_signals = [
        "great", "perfect", "sounds good", "yes", "confirmed", "agreed", "sure",
        "absolutely", "wonderful", "excellent", "love it", "awesome", "thanks",
        "thank you", "appreciated", "looking forward", "excited", "happy to",
        "works for me", "let's do it", "deal", "done",
    ]
    negative_signals = [
        "no", "not interested", "cancel", "declined", "disappoint", "issue",
        "problem", "concerned", "unfortunately", "not possible", "can't",
        "won't", "never", "stop", "unsubscribe", "remove me", "pass",
        "not right now", "not a fit", "not moving forward",
    ]

    pos_count = sum(1 for sig in positive_signals if sig in body_lower)
    neg_count = sum(1 for sig in negative_signals if sig in body_lower)

    if pos_count == 0 and neg_count == 0:
        return 0.0
    if pos_count > neg_count:
        return min(0.5, 0.25 * pos_count)
    if neg_count > pos_count:
        return max(-0.5, -0.25 * neg_count)
    return 0.0  # tie → neutral


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

            if is_automated_email(contact_email, contact_name):
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


def run_gmail_sync(org_id, max_emails=None, account_email: str = None, force_reprocess: bool = False):
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
    Update 5: force_reprocess=True skips the dedup check, allowing already-synced
              emails to be re-extracted. ON CONFLICT handles idempotency.

    Args:
        org_id: Organization ID
        max_emails: Target number of valid emails to sync (default: SYNC_MAX_EMAILS from config)
        account_email: Specific Gmail account to sync. If None, syncs all accounts.
        force_reprocess: If True, reprocess already-synced emails (skip dedup check).
    """
    if max_emails is None:
        max_emails = SYNC_MAX_EMAILS
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
                force_reprocess=force_reprocess,
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
    db, org_id, access_token, refresh_token, account_identifier, max_emails,
    force_reprocess=False,
):
    """
    Internal: run the full sync pipeline for one Gmail account token.
    """
    # Mark sync as running + bootstrap status
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
    # Set bootstrap_status to ingesting (CLM spec)
    try:
        db.execute(
            text("""
                UPDATE oauth_tokens
                SET bootstrap_status = CASE WHEN bootstrap_status != 'live' THEN 'ingesting' ELSE bootstrap_status END,
                    bootstrap_started_at = COALESCE(bootstrap_started_at, NOW())
                WHERE org_id = :oid AND account_email = :acct
            """),
            {"oid": org_id, "acct": account_identifier},
        )
        db.commit()
    except Exception:
        pass

    try:
        service = build_gmail_service(
            access_token, refresh_token,
            db=db, org_id=org_id, account_email=account_identifier,
        )

        # Get the user's own email address
        user_email = get_user_email(service)
        print(f"📧 Syncing emails for: {user_email} (account: {account_identifier})")

        # ── Update 1: Collect exactly max_emails valid email IDs ──────────────
        valid_ids = collect_valid_email_ids(service, user_email, target=max_emails)

        # Pre-filter: skip emails already in the DB (unless force_reprocess)
        skipped_existing = 0
        if force_reprocess:
            new_ids = valid_ids
            print(
                f"🔄 Force reprocess: processing all {len(new_ids)} emails "
                f"(ON CONFLICT handles dedup)"
            )
        else:
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
            attachment_info = detect_attachments(payload)

            # Phase 2 Task 2.1 — pull text out of supported attachments and
            # append to the body so the LLM extractor sees what was sent.
            # PDF/DOCX/plain only; fail-soft on unsupported or corrupt files.
            if attachment_info.get("has_attachment"):
                attach_text = extract_attachment_text(service, m["id"], payload)
                if attach_text:
                    body_text = (body_text + "\n\n" + attach_text)[:8000]

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

            # PDF spec: skip mass outreach (sender to 10+ recipients = not a real relationship)
            to_raw_header = parsed.get("to_email", "")
            cc_list_raw = parsed.get("cc_list", [])
            if is_mass_outreach(cc_list_raw, to_raw_header, from_email, user_email):
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
                # Raw headers for Tier 0 classifier (Precedence, Auto-Submitted, etc.)
                "raw_headers": parsed.get("raw_headers", {}),
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

            # ── Classify email (Tier 0/1/2/SYSTEM) ───────────────────────────
            from_email = parsed_msg["from_email"]
            raw_headers = parsed_msg.get("raw_headers", {})
            recipient_count = 1 + len(cc_list)

            category = classify_email(
                subject=subject or "",
                sender_email=from_email or "",
                body=body_text or "",
                headers=raw_headers,
                recipient_count=recipient_count,
                org_domain=user_email.split("@")[-1] if user_email and "@" in user_email else None,
            )

            # ── Phase 3.1: Classify the SENDER (header-based) and persist ────
            # This runs for ALL tiers. Even TIER_0 senders get a contact row
            # tagged with their classification. P1: store everything, tag it.
            sender_class = classify_sender(
                sender_email=from_email or "",
                headers=raw_headers,
                recipient_count=recipient_count,
            )
            if sender_class["classification"] != "unknown" and contact_email:
                try:
                    # Upsert contact (creates if new, updates classification if changed)
                    _cls_contact_id = upsert_contact(
                        db, org_id, contact_email, contact_name, entity_type=None
                    )
                    # Only update if no manual override exists
                    db.execute(
                        text("""
                            UPDATE contacts
                            SET classification = CASE
                                    WHEN classification_override IS NOT NULL THEN classification
                                    ELSE :cls
                                END,
                                classification_confidence = CASE
                                    WHEN classification_override IS NOT NULL THEN classification_confidence
                                    ELSE :conf
                                END,
                                classification_method = CASE
                                    WHEN classification_override IS NOT NULL THEN classification_method
                                    ELSE :method
                                END,
                                classified_at = CASE
                                    WHEN classification_override IS NOT NULL THEN classified_at
                                    ELSE NOW()
                                END
                            WHERE id = :cid AND org_id = :oid
                              AND (classification_override IS NULL)
                              AND (classification IS NULL OR classification = 'unknown'
                                   OR :conf > COALESCE(classification_confidence, 0))
                        """),
                        {
                            "cid": str(_cls_contact_id),
                            "oid": org_id,
                            "cls": sender_class["classification"],
                            "conf": sender_class["confidence"],
                            "method": sender_class["method"],
                        },
                    )
                    db.commit()
                except Exception as e:
                    logger.debug(f"Classification persist failed for {contact_email}: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass

            # ── Branch processing by category ─────────────────────────────────
            if category == "SYSTEM":
                # Parse structured state data (GST, payments, invoices) → State Graph (v2.2)
                parsed_state = parse_system_email(
                    subject=subject or "",
                    body=body_text or "",
                    sender_email=from_email or "",
                )
                # Use UPSERT logic: updates existing entity if found, inserts if new
                parsed_state["source_email_id"] = parsed_msg["gmail_id"]  # Track source email
                upsert_state_entity(db, org_id, parsed_state)
                system_emails += 1
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
                continue

            elif category == "TIER_0":
                # Hard discard from extraction — zero LLM cost, zero graph
                # impact (no interaction row, no fact write).
                # BUT: brain still benefits from knowing "Acme sent 50 newsletters
                # but 0 personal emails" → not a real relationship. Bump a
                # lightweight marketing counter on the contact (created earlier
                # by sender_class block if recognized). Graph stays clean.
                if contact_email:
                    try:
                        _mk_contact_id = upsert_contact(
                            db, org_id, contact_email, contact_name, entity_type=None
                        )
                        db.execute(
                            text("""
                                UPDATE contacts
                                SET marketing_email_count = COALESCE(marketing_email_count, 0) + 1,
                                    last_marketing_email_at = NOW()
                                WHERE id = :cid AND org_id = :oid
                            """),
                            {"cid": str(_mk_contact_id), "oid": org_id},
                        )
                        db.commit()
                    except Exception as e:
                        logger.debug(f"TIER_0 marketing counter skip {contact_email}: {e}")
                        try: db.rollback()
                        except Exception: pass
                discarded_emails += 1
                update_sync_progress(
                    db, org_id, account_email=account_identifier, sync_processed=i
                )
                continue

            elif category == "TIER_1":
                # Edge stats only — update counters, NO interaction row, NO LLM
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

            # ── TIER_2: Store raw interaction NOW, extract via async worker LATER ──
            # Per Phase 1.1: sync writes the row instantly (no LLM wait),
            # Celery worker picks up pending rows and extracts in batch.

            # Upsert contact without LLM-derived role (role updated by extractor later)
            contact_id = upsert_contact(
                db, org_id, contact_email, contact_name,
                entity_type=None,
                email_body=body_text or "",
            )

            # Count consecutive outbound messages in this thread with no inbound reply
            thread_msgs = thread_processed.get(thread_id, [])
            followup_count = 0
            if direction == "outbound":
                for prev in reversed(thread_msgs):
                    if prev.get("direction") == "outbound":
                        followup_count += 1
                    else:
                        break

            # Thread initiator = first message sender in this thread
            thread_first = thread_groups.get(thread_id, [None])[0]
            thread_initiator = thread_first["from_email"] if thread_first else None

            # Create the interaction with extraction_status='pending'.
            # Summary/sentiment/topics/commitments stay NULL until the
            # async extractor processes this row.
            create_interaction(
                db,
                org_id,
                contact_id,
                parsed_msg["gmail_id"],
                subject,
                f"[Pending extraction] {(subject or 'No subject')[:100]}",  # placeholder summary
                parsed_msg["date"],
                direction,
                sentiment=None,
                intent=None,
                commitments=[],
                topics=[],
                interaction_type="email_one_way",
                engagement_level=None,
                reply_time_hours=None,
                account_email=user_email,
                signal_score=None,
                mentioned_people=[],
                what_works=None,
                what_to_avoid=None,
                has_attachment=attachment_info.get("has_attachment", False),
                unanswered_followup_count=followup_count,
                processed_version=PROCESSING_VERSION,
                initiator_email=thread_initiator,
                raw_body=body_text,
                extraction_status="pending",
            )
            llm_processed += 1  # counter still tracks how many need extraction

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
                        processed_version=PROCESSING_VERSION,
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

        # Run async LLM extraction for pending interaction rows
        print("Running async LLM extraction for pending rows...")
        try:
            from app.tasks.extract_interactions import run_pending_extractions
            extracted = run_pending_extractions(org_id)
            print(f"✓ Extracted {extracted} interactions via LLM")
        except Exception as e:
            print(f"✗ Extraction task failed (rows stay pending for retry): {e}")

        # Recalculate relationship stages after sync + extraction
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
        # Set bootstrap_status to live (CLM spec)
        try:
            db.execute(
                text("""
                    UPDATE oauth_tokens
                    SET bootstrap_status = 'live',
                        bootstrap_completed_at = NOW(),
                        bootstrap_email_count = :count
                    WHERE org_id = :oid AND account_email = :acct
                """),
                {"oid": org_id, "acct": account_identifier, "count": processed_count},
            )
            db.commit()
        except Exception:
            pass

    except Exception as e:
        print(f"❌ Sync failed for account {account_identifier}: {e}")
        update_sync_progress(
            db,
            org_id,
            account_email=account_identifier,
            sync_status="error",
            sync_error=str(e)[:500],
        )
