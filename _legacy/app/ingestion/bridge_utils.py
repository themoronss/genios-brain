"""
Shared utilities for all tool bridges.
"""

from sqlalchemy import text


def get_email_domain(email: str) -> str:
    """Extract domain from email address."""
    if not email or "@" not in email:
        return ""
    return email.split("@")[1].lower()


_PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "protonmail.com", "aol.com", "mail.com",
    "live.com", "ymail.com", "googlemail.com",
}


def get_org_domain(db, org_id: str) -> str | None:
    """Get org email domain from the orgs table. Returns None for public email providers."""
    row = db.execute(
        text("SELECT email FROM orgs WHERE id = :oid"),
        {"oid": org_id},
    ).fetchone()
    if row and row.email and "@" in row.email:
        domain = row.email.split("@")[1].lower()
        if domain in _PUBLIC_EMAIL_DOMAINS:
            return None
        return domain
    return None


def is_internal_email(email: str, org_domain: str | None) -> bool:
    """Check if email belongs to the org's domain."""
    if not org_domain or not email:
        return False
    return email.lower().strip().endswith(f"@{org_domain}")
