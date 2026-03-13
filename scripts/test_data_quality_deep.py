#!/usr/bin/env python3
"""
Deep Data Quality Analysis - Check for real human contacts vs automated emails
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal

TEST_ORG_ID = "87b0235e-e29d-468a-b841-522c13546515"


def analyze_contact_quality():
    """Analyze the quality of contacts in the database"""

    print("\n" + "=" * 80)
    print("  DATA QUALITY ANALYSIS - Contact Types")
    print("=" * 80 + "\n")

    db = SessionLocal()

    # Get all contacts with interaction counts
    result = db.execute(
        text(
            f"""
        SELECT 
            c.name,
            c.email,
            c.company,
            COUNT(i.id) as interaction_count,
            MAX(i.interaction_at) as last_interaction
        FROM contacts c
        LEFT JOIN interactions i ON i.contact_id = c.id
        WHERE c.org_id = '{TEST_ORG_ID}'
        GROUP BY c.id, c.name, c.email, c.company
        ORDER BY COUNT(i.id) DESC
    """
        )
    )

    contacts = result.fetchall()

    # Classify contacts
    automated_keywords = [
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
        "newsletter",
        "digest",
        "alert",
        "notification",
        "bulletin",
        "automated",
        "system",
        "mailer",
    ]

    real_contacts = []
    automated_contacts = []

    for contact in contacts:
        name, email, company, count, last = contact
        email_lower = email.lower() if email else ""
        name_lower = name.lower() if name else ""

        is_automated = any(
            keyword in email_lower or keyword in name_lower
            for keyword in automated_keywords
        )

        if is_automated:
            automated_contacts.append(contact)
        else:
            real_contacts.append(contact)

    # Print summary
    total = len(contacts)
    real_count = len(real_contacts)
    auto_count = len(automated_contacts)

    print(f"📊 SUMMARY")
    print(f"   Total Contacts: {total}")
    print(f"   Real People: {real_count} ({real_count/total*100:.1f}%)")
    print(f"   Automated/Newsletters: {auto_count} ({auto_count/total*100:.1f}%)")

    # Automated contacts
    if automated_contacts:
        print(f"\n❌ AUTOMATED EMAILS ({len(automated_contacts)}):")
        print("   " + "-" * 76)
        for contact in automated_contacts[:10]:
            print(f"   • {contact[0][:40]:40} | {contact[1][:35]:35}")
        if len(automated_contacts) > 10:
            print(f"   ... and {len(automated_contacts) - 10} more")

    # Real contacts
    if real_contacts:
        print(f"\n✅ REAL CONTACTS ({len(real_contacts)}):")
        print("   " + "-" * 76)
        for contact in real_contacts[:15]:
            interactions = contact[3]
            print(
                f"   • {contact[0][:35]:35} | {contact[1][:30]:30} | {interactions} emails"
            )
        if len(real_contacts) > 15:
            print(f"   ... and {len(real_contacts) - 15} more")
    else:
        print(f"\n❌ NO REAL CONTACTS FOUND!")
        print("   This is a problem for the MVP demo.")

    # Check for investors, customers, partners
    print(f"\n🔍 LOOKING FOR HIGH-VALUE CONTACTS:")

    high_value_keywords = [
        "capital",
        "ventures",
        "invest",
        "fund",
        "partner",
        "ceo",
        "founder",
    ]
    high_value_contacts = []

    for contact in real_contacts:
        name_lower = (contact[0] or "").lower()
        email_lower = (contact[1] or "").lower()
        company_lower = (contact[2] or "").lower()

        if any(
            keyword in name_lower or keyword in email_lower or keyword in company_lower
            for keyword in high_value_keywords
        ):
            high_value_contacts.append(contact)

    if high_value_contacts:
        print(
            f"   Found {len(high_value_contacts)} potential investors/partners/customers:"
        )
        for contact in high_value_contacts:
            print(f"   ⭐ {contact[0]} ({contact[1]}) - {contact[3]} interactions")
    else:
        print("   ⚠️  No obvious investors/partners found in email data")

    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")

    if real_count < 5:
        print("   ❌ CRITICAL: Less than 5 real human contacts!")
        print("      → Need to sync more emails or connect a different Gmail account")
        print("      → For MVP demo, you need 20+ investor/customer contacts")
    elif real_count < 20:
        print("   ⚠️  WARNING: Less than 20 real contacts")
        print("      → MVP requires 20+ investor contacts for a good demo")
        print("      → Sync more email history")
    else:
        print("   ✅ Good: You have enough contacts for MVP testing")

    if auto_count > real_count * 2:
        print("   ⚠️  Too many automated emails (newsletters, alerts)")
        print("      → Consider filtering these during ingestion")
        print("      → They dilute the quality of vector search results")

    # Check interaction depth
    result = db.execute(
        text(
            f"""
        SELECT 
            c.name,
            c.email,
            COUNT(i.id) as interaction_count
        FROM contacts c
        LEFT JOIN interactions i ON i.contact_id = c.id
        WHERE c.org_id = '{TEST_ORG_ID}'
        GROUP BY c.id, c.name, c.email
        HAVING COUNT(i.id) >= 3
        ORDER BY COUNT(i.id) DESC
    """
        )
    )

    deep_contacts = result.fetchall()

    print(f"\n📧 INTERACTION DEPTH:")
    print(f"   Contacts with 3+ interactions: {len(deep_contacts)}")

    if len(deep_contacts) >= 5:
        print("   ✅ Good depth for building context")
        print(f"   Top contacts by interaction:")
        for contact in deep_contacts[:5]:
            print(f"      • {contact[0]} - {contact[2]} interactions")
    else:
        print("   ⚠️  Limited interaction history")
        print("      → Sync more emails to get deeper relationship context")

    db.close()

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    analyze_contact_quality()
