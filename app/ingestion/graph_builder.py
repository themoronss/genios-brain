from sqlalchemy import text
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from typing import Optional
import re


def extract_company_from_email(email):
    """
    Extract company name from email domain.
    """
    if not email or "@" not in email:
        return None

    domain = email.split("@")[1].lower()

    personal_domains = [
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "icloud.com", "protonmail.com", "aol.com", "mail.com",
    ]

    if domain in personal_domains:
        return None

    # Extract company name from domain (e.g. priya@sequoiacap.com → Sequoiacap)
    company = domain.split(".")[0]
    company = company.replace("-", " ").replace("_", " ")
    company = " ".join(word.capitalize() for word in company.split())

    return company


def get_email_domain(email: str) -> str:
    """Extract domain from email address."""
    if not email or "@" not in email:
        return ""
    return email.split("@")[1].lower()


# ── Due date parsing ──────────────────────────────────────────────────────────

def parse_due_signal(due_signal: str, reference_date: datetime = None) -> Optional[datetime]:
    """
    Convert a natural language due signal into an actual datetime.
    Handles common patterns like "by Friday", "next week", "end of month",
    "in 3 days", "tomorrow", "by March 20", etc.

    Args:
        due_signal: Natural language time reference from LLM
        reference_date: Base date for relative parsing (defaults to now)

    Returns:
        datetime or None if unparseable
    """
    if not due_signal or not due_signal.strip():
        return None

    ref = reference_date or datetime.now(timezone.utc)
    signal = due_signal.lower().strip()

    # --- Absolute patterns first ---
    # "by March 20", "March 20", "20 March"
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    for month_name, month_num in month_names.items():
        # "March 20", "March 20th"
        m = re.search(rf"{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?", signal)
        if m:
            day = int(m.group(1))
            year = ref.year
            try:
                dt = datetime(year, month_num, day, 23, 59, tzinfo=timezone.utc)
                # If date is in the past, move to next year
                if dt < ref:
                    dt = dt.replace(year=year + 1)
                return dt
            except ValueError:
                pass

        # "20 March", "20th March", "20th of March"
        m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+{month_name}", signal)
        if m:
            day = int(m.group(1))
            year = ref.year
            try:
                dt = datetime(year, month_num, day, 23, 59, tzinfo=timezone.utc)
                if dt < ref:
                    dt = dt.replace(year=year + 1)
                return dt
            except ValueError:
                pass

    # --- Relative day patterns ---
    day_names = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    }

    for day_name, day_num in day_names.items():
        if day_name in signal:
            current_weekday = ref.weekday()
            days_ahead = (day_num - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7  # "this Friday" always means next occurrence
            if "next" in signal:
                days_ahead += 7  # "next Friday" = one more week
            return (ref + timedelta(days=days_ahead)).replace(
                hour=23, minute=59, second=0, microsecond=0
            )

    # --- Common relative phrases ---
    if re.search(r"\btoday\b", signal):
        return ref.replace(hour=23, minute=59, second=0, microsecond=0)
    
    if re.search(r"\btomorrow\b", signal):
        return (ref + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        
    if re.search(r"\beod\b|\bend of day\b", signal):
        return ref.replace(hour=23, minute=59, second=0, microsecond=0)
        
    if re.search(r"\beow\b|\bend of week\b|\bthis week\b", signal):
        days_ahead = (4 - ref.weekday()) % 7 or 5
        return (ref + timedelta(days=days_ahead)).replace(hour=23, minute=59, second=0, microsecond=0)
        
    if re.search(r"\bnext week\b", signal):
        days_ahead = 7 + (4 - ref.weekday()) % 7
        return (ref + timedelta(days=days_ahead)).replace(hour=23, minute=59, second=0, microsecond=0)
    # "end of month"
    if re.search(r"\bend of month\b|\beom\b|\bthis month\b", signal):
        # Last day of current month
        next_month = ref.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        return last_day.replace(hour=23, minute=59, second=0, microsecond=0, tzinfo=timezone.utc)

    # "next month"
    if "next month" in signal:
        m = ref.month + 1
        y = ref.year
        if m > 12:
            m = 1
            y += 1
        next_month = ref.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        return datetime(y, m, last_day.day, 23, 59, tzinfo=timezone.utc)

    # "in N days" or just "N days"
    m = re.search(r"(?:in\s+)?(\d+)\s*days?", signal)
    if m:
        return ref + timedelta(days=int(m.group(1)))

    # "in N hours" or "next N hours"
    m = re.search(r"(?:in|next)\s+(\d+)\s*hours?", signal)
    if m:
        return ref + timedelta(hours=int(m.group(1)))

    # "on the 18th", "18th" (when month is omitted)
    if not any(month in signal for month in month_names.keys()):
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", signal)
        if m:
            day = int(m.group(1))
            try:
                dt = datetime(ref.year, ref.month, day, 23, 59, tzinfo=timezone.utc)
                if dt < ref:
                    # if day has already passed this month, they mean next month
                    m_next = ref.month + 1
                    y_next = ref.year
                    if m_next > 12:
                        m_next = 1
                        y_next += 1
                    dt = datetime(y_next, m_next, day, 23, 59, tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass

    # "in N weeks"
    m = re.search(r"in (\d+)\s*weeks?", signal)
    if m:
        return ref + timedelta(weeks=int(m.group(1)))

    # "within N days"
    m = re.search(r"within (\d+)\s*days?", signal)
    if m:
        return ref + timedelta(days=int(m.group(1)))

    # Could not parse
    return None


# ── Contact upsert with same-person fuzzy dedup ───────────────────────────────

def find_existing_contact_by_domain_and_name(db, org_id: str, email: str, name: str):
    """
    Before creating a new contact, check if someone with very similar name
    exists at the same company domain. Prevents the split-history problem where
    priya@sequoia.com and priya.sharma@sequoia.com become two nodes.

    Returns contact_id if a high-confidence match is found, else None.
    """
    if not email or "@" not in email:
        return None

    domain = get_email_domain(email)
    if not domain or not name:
        return None

    # Skip personal domains — can't infer same-company from gmail.com etc.
    personal_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "icloud.com", "protonmail.com", "aol.com",
    }
    if domain in personal_domains:
        return None

    # Find all contacts at the same company domain
    candidates = db.execute(
        text(
            """
            SELECT id, name, email
            FROM contacts
            WHERE org_id = :org_id
              AND company_domain = :domain
              AND id IS NOT NULL
            LIMIT 50
            """
        ),
        {"org_id": org_id, "domain": domain},
    ).fetchall()

    if not candidates:
        return None

    # Simple name similarity: check if first name matches
    first_name = name.strip().split()[0].lower() if name.strip() else ""
    if len(first_name) < 2:
        return None

    for row in candidates:
        existing_name = (row[1] or "").strip()
        existing_first = existing_name.split()[0].lower() if existing_name else ""

        # Same first name at same domain = high confidence merge
        if existing_first and existing_first == first_name:
            print(
                f"🔗 Dedup merge: '{name}' ({email}) → existing '{existing_name}' ({row[2]})"
                f" [same domain: {domain}]"
            )
            return str(row[0])

    return None


def upsert_contact(db, org_id, email, name, entity_type: str = None):
    """
    Create or update a contact record.
    Includes same-person fuzzy dedup: checks if a contact with the same
    first name exists at the same company domain before creating a new node.

    Args:
        db: Database session
        org_id: Organization ID
        email: Contact email address
        name: Contact display name
        entity_type: Optional role tag from LLM (investor, customer, vendor, etc.).
                     Uses COALESCE — first non-null value wins; subsequent syncs
                     won't overwrite it with null.
    """
    # ── FIX 9: Same-person dedup check ──
    existing_id = find_existing_contact_by_domain_and_name(db, org_id, email, name)
    if existing_id:
        # If we now have a role, update it (COALESCE ensures we don't blank out
        # an existing tag if this call has entity_type=None)
        if entity_type:
            db.execute(
                text(
                    """
                    UPDATE contacts
                    SET entity_type = COALESCE(:entity_type, entity_type)
                    WHERE id = :contact_id
                    """
                ),
                {"entity_type": entity_type, "contact_id": existing_id},
            )
        return existing_id

    contact_id = str(uuid4())
    company = extract_company_from_email(email)
    domain = get_email_domain(email)

    db.execute(
        text(
            """
        INSERT INTO contacts (
            id,
            org_id,
            email,
            name,
            company,
            company_domain,
            entity_type
        )
        VALUES (
            :id,
            :org_id,
            :email,
            :name,
            :company,
            :domain,
            :entity_type
        )
        ON CONFLICT (org_id, email)
        DO UPDATE SET
            name = EXCLUDED.name,
            company = COALESCE(EXCLUDED.company, contacts.company),
            company_domain = COALESCE(EXCLUDED.company_domain, contacts.company_domain),
            entity_type = COALESCE(EXCLUDED.entity_type, contacts.entity_type)
        """
        ),
        {
            "id": contact_id,
            "org_id": org_id,
            "email": email,
            "name": name,
            "company": company,
            "domain": domain,
            "entity_type": entity_type,
        },
    )

    result = db.execute(
        text(
            """
        SELECT id FROM contacts
        WHERE org_id = :org_id AND email = :email
        """
        ),
        {"org_id": org_id, "email": email},
    )

    return result.fetchone()[0]


def create_interaction(
    db,
    org_id,
    contact_id,
    gmail_id,
    subject,
    summary,
    date,
    direction,
    sentiment=0.0,
    intent="other",
    commitments=None,
    topics=None,
    interaction_type="email_one_way",
    engagement_level="medium",
    reply_time_hours=None,
    account_email=None,
):
    """
    Create an interaction record with enhanced LLM extraction data.
    Stores engagement signals, interaction type, and commitments with lifecycle.
    """
    if commitments is None:
        commitments = []
    if topics is None:
        topics = []

    weight_score = _calculate_interaction_weight(
        interaction_type, engagement_level, sentiment, direction
    )

    interaction_id = str(uuid4())

    db.execute(
        text(
            """
        INSERT INTO interactions (
            id,
            org_id,
            contact_id,
            gmail_message_id,
            direction,
            subject,
            summary,
            interaction_at,
            sentiment,
            intent,
            interaction_type,
            reply_time_hours,
            weight_score,
            topics,
            account_email
        )
        VALUES (
            :id,
            :org_id,
            :contact_id,
            :gmail_id,
            :direction,
            :subject,
            :summary,
            :date,
            :sentiment,
            :intent,
            :interaction_type,
            :reply_time_hours,
            :weight_score,
            :topics,
            :account_email
        )
        ON CONFLICT (gmail_message_id, contact_id)
        DO UPDATE SET
            sentiment = EXCLUDED.sentiment,
            intent = EXCLUDED.intent,
            interaction_type = EXCLUDED.interaction_type,
            weight_score = EXCLUDED.weight_score,
            topics = EXCLUDED.topics,
            account_email = EXCLUDED.account_email
        """
        ),
        {
            "id": interaction_id,
            "org_id": org_id,
            "contact_id": contact_id,
            "gmail_id": gmail_id,
            "direction": direction,
            "subject": subject,
            "summary": summary,
            "date": date,
            "sentiment": sentiment,
            "intent": intent,
            "interaction_type": interaction_type,
            "reply_time_hours": reply_time_hours,
            "weight_score": weight_score,
            "topics": topics,
            "account_email": account_email,
        },
    )

    # Store commitments in separate table for lifecycle tracking
    _store_commitments(db, org_id, contact_id, interaction_id, commitments, direction)

    return interaction_id


def _calculate_interaction_weight(
    interaction_type: str, engagement_level: str, sentiment: float, direction: str
) -> float:
    """
    Calculate weight score for an interaction based on type, engagement, and sentiment.
    """
    type_weights = {
        "email_reply": 0.7,
        "email_one_way": 0.1,
        "commitment": 0.95,
        "meeting": 0.9,
        "other": 0.3,
    }

    base_weight = type_weights.get(interaction_type, 0.3)

    engagement_mult = {
        "high": 1.2,
        "medium": 1.0,
        "low": 0.6,
    }.get(engagement_level, 1.0)

    direction_mult = 1.1 if direction == "INBOUND" else 0.9

    sentiment_mult = 1.0
    if interaction_type == "commitment" and sentiment < -0.3:
        sentiment_mult = 0.4

    weight = base_weight * engagement_mult * direction_mult * sentiment_mult
    return round(max(0.0, min(1.0, weight)), 3)


def _store_commitments(
    db,
    org_id: str,
    contact_id: str,
    interaction_id: str,
    commitments: list,
    direction: str,
):
    """
    Store commitments in the commitments table with lifecycle tracking.
    Now includes:
    - Actual due date parsing (not a stub anymore)
    - Soft commitments tagged with status 'SOFT' for separate downstream handling
    """
    if not commitments:
        return

    for commitment in commitments:
        try:
            owner = commitment.get("owner", "them")
            if owner not in ("them", "us"):
                owner = "them" if direction == "INBOUND" else "us"

            # ── FIX 4: Parse due_signal into actual due_date ──
            due_date = None
            due_signal = commitment.get("due_signal")
            if due_signal:
                due_date = parse_due_signal(due_signal)
                if due_date:
                    print(f"  📅 Parsed due date: '{due_signal}' → {due_date.strftime('%Y-%m-%d')}")
                else:
                    print(f"  ⚠️ Could not parse due signal: '{due_signal}'")

            # ── FIX 5: Soft commitments get status 'SOFT' not 'OPEN' ──
            is_soft = commitment.get("is_soft", False)
            status = "SOFT" if is_soft else "OPEN"

            db.execute(
                text(
                    """
                    INSERT INTO commitments (
                        id, org_id, contact_id, commit_text, owner, due_date,
                        status, source_interaction_id, created_at
                    )
                    VALUES (
                        :id, :org_id, :contact_id, :commit_text, :owner, :due_date,
                        :status, :source_interaction_id, NOW()
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": str(uuid4()),
                    "org_id": org_id,
                    "contact_id": contact_id,
                    "commit_text": commitment.get("text", "")[:500],
                    "owner": owner,
                    "due_date": due_date,
                    "status": status,
                    "source_interaction_id": interaction_id,
                },
            )
        except Exception as e:
            print(f"⚠️ Error storing commitment: {e}")
            continue
