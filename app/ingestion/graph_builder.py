from sqlalchemy import text
from uuid import uuid4


def extract_company_from_email(email):
    """
    Extract company name from email domain.

    Args:
        email: Email address

    Returns:
        str: Company name or None
    """
    if not email or "@" not in email:
        return None

    domain = email.split("@")[1].lower()

    # Common personal email domains
    personal_domains = [
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "protonmail.com",
        "aol.com",
        "mail.com",
    ]

    if domain in personal_domains:
        return None

    # Extract company name from domain
    # Example: john@sequoiacap.com -> Sequoia Cap
    company = domain.split(".")[0]

    # Capitalize and clean up
    company = company.replace("-", " ").replace("_", " ")
    company = " ".join(word.capitalize() for word in company.split())

    return company


def upsert_contact(db, org_id, email, name):

    contact_id = str(uuid4())

    # Extract company from email domain
    company = extract_company_from_email(email)

    db.execute(
        text(
            """
        INSERT INTO contacts (
            id,
            org_id,
            email,
            name,
            company
        )
        VALUES (
            :id,
            :org_id,
            :email,
            :name,
            :company
        )
        ON CONFLICT (org_id, email)
        DO UPDATE SET
            name = EXCLUDED.name,
            company = COALESCE(EXCLUDED.company, contacts.company)
        """
        ),
        {
            "id": contact_id,
            "org_id": org_id,
            "email": email,
            "name": name,
            "company": company,
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
):
    """
    Create an interaction record with enhanced LLM extraction data.
    """
    if commitments is None:
        commitments = []
    if topics is None:
        topics = []

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
            commitments,
            topics
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
            :commitments,
            :topics
        )
        ON CONFLICT (gmail_message_id)
        DO UPDATE SET
            sentiment = EXCLUDED.sentiment,
            intent = EXCLUDED.intent,
            commitments = EXCLUDED.commitments,
            topics = EXCLUDED.topics
        """
        ),
        {
            "id": str(uuid4()),
            "org_id": org_id,
            "contact_id": contact_id,
            "gmail_id": gmail_id,
            "direction": direction,
            "subject": subject,
            "summary": summary,
            "date": date,
            "sentiment": sentiment,
            "intent": intent,
            "commitments": commitments,
            "topics": topics,
        },
    )
