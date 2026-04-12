"""
Email Classification Module for GeniOS

Categorizes emails into TIER_0, TIER_1, TIER_2, or SYSTEM
per the Graph Enrichment spec's 3-tier classifier.

Tier 0 — HARD DISCARD: zero graph impact, zero LLM cost
Tier 1 — EDGE STATS ONLY: updates counters (interaction_count, last_interaction_at), no LLM
Tier 2 — FULL EXTRACTION: runs LLM, writes to graph
SYSTEM — structured state data (tax, invoices, payments) → State Graph only

Author: GeniOS Team
Version: 2.0
Last Updated: 2026-04-11
"""

import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ── Tier 0: Hard Discard constants ───────────────────────────────────────────

TIER_0_SENDER_PATTERNS = [
    "noreply@", "no-reply@", "donotreply@", "do-not-reply@",
    "notifications@", "alerts@", "mailer-daemon@",
]

PROMO_DOMAINS = [
    "mailchimp.com", "sendgrid.net", "klaviyo.com", "substack.com",
    "beehiiv.com", "convertkit.com", "mailgun.org", "constantcontact.com",
    "hubspot.com", "mailjet.com", "sendinblue.com", "brevo.com",
    "campaign-archive.com", "list-manage.com",
]

TIER_0_DISCARD_KEYWORDS = [
    "unsubscribe", "newsletter", "automated", "digest", "marketing",
]

OOO_SUBJECT_PATTERN = re.compile(
    r"^(out of office|ooo|auto[\s-]?reply|automatic reply)", re.IGNORECASE
)

TIER_0_SUBJECT_PREFIXES = re.compile(
    r"^(invoice|receipt|order conf|payment conf)", re.IGNORECASE
)

# ── SYSTEM constants ─────────────────────────────────────────────────────────

SYSTEM_KEYWORDS = [
    "gst", "tax", "invoice", "receipt", "payment", "transaction",
    "itr", "bill", "refund", "order confirmation", "shipping", "delivery",
]

SYSTEM_DOMAINS = [
    "gov.in", ".bank", "razorpay", "stripe", "paypal", "paytm",
    "banking", "noreply@amazon", "noreply@flipkart",
]

# ── Tier 1 constants ─────────────────────────────────────────────────────────

TIER_1_WORD_THRESHOLD = 15  # Spec: < 15 words with no commitment language

COMMITMENT_PATTERNS = re.compile(
    r"(i'll send|i will share|let's connect|can you send|i'll follow|"
    r"we've decided|moving forward|passing on|as head of|i am the|"
    r"as .{2,20} of|my role)",
    re.IGNORECASE,
)

MASS_SEND_THRESHOLD = 50  # Spec: 50+ recipients


def classify_email(
    subject: str, sender_email: str, body: str,
    headers: Optional[Dict[str, str]] = None,
    recipient_count: int = 1,
    org_domain: Optional[str] = None,
) -> str:
    """
    Classify email per Graph Enrichment spec 3-tier classifier.

    Args:
        subject: Email subject line
        sender_email: Sender's email address
        body: Email body content
        headers: Optional email headers dict
        recipient_count: Total number of recipients (To + CC + BCC)
        org_domain: Your org's email domain (for mass-send exception)

    Returns:
        str: One of "TIER_0", "TIER_1", "TIER_2", "SYSTEM"
    """
    subject_lower = (subject or "").lower()
    sender_lower = (sender_email or "").lower()
    body_lower = (body or "").lower()
    headers = headers or {}
    sender_domain = sender_lower.split("@")[-1] if "@" in sender_lower else ""

    # ── SYSTEM check first (structured state data) ────────────────────────
    if any(keyword in subject_lower for keyword in SYSTEM_KEYWORDS):
        logger.debug(f"SYSTEM (keyword in subject): {subject[:50]}")
        return "SYSTEM"

    if any(domain in sender_lower for domain in SYSTEM_DOMAINS):
        logger.debug(f"SYSTEM (domain match): {sender_email}")
        return "SYSTEM"

    # ── TIER 0: Hard Discard ──────────────────────────────────────────────
    # Header-based (fastest — check before reading body)

    # noreply/donotreply/notifications/alerts sender
    if any(pattern in sender_lower for pattern in TIER_0_SENDER_PATTERNS):
        logger.debug(f"TIER_0 (sender pattern): {sender_email}")
        return "TIER_0"

    # List-Unsubscribe header
    if headers.get("List-Unsubscribe") or headers.get("list-unsubscribe"):
        logger.debug(f"TIER_0 (List-Unsubscribe header): {subject[:50]}")
        return "TIER_0"

    # Precedence: bulk | list | junk
    precedence = (
        headers.get("Precedence") or headers.get("precedence") or ""
    ).lower()
    if precedence in ("bulk", "list", "junk"):
        logger.debug(f"TIER_0 (Precedence: {precedence}): {subject[:50]}")
        return "TIER_0"

    # Auto-Submitted header (not null, not "no")
    auto_submitted = (
        headers.get("Auto-Submitted") or headers.get("auto-submitted")
    )
    if auto_submitted and auto_submitted.lower() != "no":
        logger.debug(f"TIER_0 (Auto-Submitted: {auto_submitted}): {subject[:50]}")
        return "TIER_0"

    # Subject-based OOO / auto-reply
    if OOO_SUBJECT_PATTERN.match(subject_lower):
        logger.debug(f"TIER_0 (OOO subject): {subject[:50]}")
        return "TIER_0"

    # Subject-based invoice/receipt/order/payment confirmations
    if TIER_0_SUBJECT_PREFIXES.match(subject_lower):
        logger.debug(f"TIER_0 (transactional subject): {subject[:50]}")
        return "TIER_0"

    # Promo domain blocklist
    if sender_domain in PROMO_DOMAINS:
        logger.debug(f"TIER_0 (promo domain): {sender_email}")
        return "TIER_0"

    # Discard keywords in sender
    if any(keyword in sender_lower for keyword in TIER_0_DISCARD_KEYWORDS):
        logger.debug(f"TIER_0 (keyword in sender): {sender_email}")
        return "TIER_0"

    # Mass sends: 50+ recipients and sender is not your domain
    if recipient_count >= MASS_SEND_THRESHOLD:
        if not org_domain or sender_domain != org_domain:
            logger.debug(f"TIER_0 (mass send: {recipient_count} recipients): {subject[:50]}")
            return "TIER_0"

    # ── TIER 1: Edge Stats Only ───────────────────────────────────────────
    # < 15 words, no commitment/role/decision language
    word_count = len(body_lower.split())
    if word_count < TIER_1_WORD_THRESHOLD:
        # Check for commitment/role language that upgrades to TIER_2
        if COMMITMENT_PATTERNS.search(body_lower):
            logger.debug(f"TIER_2 (short but has commitment language): {subject[:50]}")
            return "TIER_2"
        logger.debug(f"TIER_1 ({word_count} words, no commitment): {subject[:50]}")
        return "TIER_1"

    # ── TIER 2: Full Extraction ───────────────────────────────────────────
    logger.debug(f"TIER_2: {subject[:50]}")
    return "TIER_2"


def parse_system_email(subject: str, body: str, sender_email: str) -> Dict[str, Any]:
    """
    Extract structured data from SYSTEM category emails for State Graph.

    Args:
        subject: Email subject
        body: Email body
        sender_email: Sender email address

    Returns:
        Dict with keys:
        - entity_type: Type (GST, PAYMENT, INVOICE, ORDER, SHIPPING)
        - entity_id: Unique identifier for this entity (GST_Q2_2025, PAYMENT_UTR_123, etc)
        - status: PENDING, FILED, CONFIRMED, RECEIVED, IN_TRANSIT
        - reference_id: ARN, UTR, invoice_number, order_id, tracking_id
        - amount: Numeric amount if applicable
        - vendor: Name of vendor
        - due_date: When is it due (if applicable)
        - metadata: Additional context

    Types Supported:
        - GST: Tax filing notifications
        - PAYMENT: Payment confirmations
        - INVOICE: Invoice receipts
        - ORDER: Order confirmations
        - SHIPPING: Delivery notifications
    """
    from datetime import datetime, timedelta

    subject_lower = subject.lower()
    body_lower = body.lower()

    # ──────────────────────────────────────────────────────────────────────
    # GST/Tax parsing with entity_id generation
    # ──────────────────────────────────────────────────────────────────────
    if "gst" in subject_lower or "itr" in subject_lower:
        status = "PENDING"
        if "filed" in body_lower or "submitted" in body_lower:
            status = "FILED"
        elif "pending" in body_lower:
            status = "PENDING"

        period = None
        period_match = re.search(
            r"(Q[1-4]|FY\s?\d{4}-?\d{2})", subject + " " + body, re.IGNORECASE
        )
        if period_match:
            period = period_match.group(1)

        arn = None
        arn_match = re.search(r"ARN[\s:]*([A-Za-z0-9]{10,})", body, re.IGNORECASE)
        if arn_match:
            arn = arn_match.group(1)

        year = datetime.now().year
        entity_id = (
            f"GST_{period}_{year}"
            if period
            else f"GST_{datetime.now().strftime('%Y-%m-%d')}"
        )

        due_date = None
        if period and "Q" in period:
            quarter_map = {"Q1": 4, "Q2": 7, "Q3": 10, "Q4": 1}
            month = quarter_map.get(period.upper(), 1)
            next_year = year + 1 if month == 1 else year
            due_date = datetime(next_year - (1 if month == 1 else 0), month, 1)

        return {
            "entity_type": "GST",
            "entity_id": entity_id,
            "status": status,
            "reference_id": arn,
            "amount": None,
            "vendor": None,
            "due_date": due_date,
            "metadata": {
                "subject": subject,
                "sender": sender_email,
                "period": period,
            },
        }

    # ──────────────────────────────────────────────────────────────────────
    # Payment parsing with entity_id generation
    # ──────────────────────────────────────────────────────────────────────
    if any(word in subject_lower for word in ["payment", "transaction", "paid"]):
        status = "PENDING"
        if "success" in body_lower or "confirmed" in body_lower:
            status = "CONFIRMED"

        amount = None
        amount_match = re.search(
            r"(?:₹|Rs\.?|\$|INR)[\s]*([0-9,]+\.?\d*)", subject + " " + body
        )
        if amount_match:
            amount = float(amount_match.group(1).replace(",", ""))

        vendor = None
        vendor_match = re.search(
            r"(?:to|from|vendor|payee)[:\s]+([A-Za-z&\s]+?)(?=\s+(?:has|have|been|confirmed|for|on|by|amount|transaction)|$)",
            body,
            re.IGNORECASE,
        )
        if vendor_match:
            vendor = vendor_match.group(1).strip()[:50]

        utr = None
        utr_match = re.search(
            r"(?:UTR|utr|reference)[:\s]*([A-Za-z0-9]{10,})", body, re.IGNORECASE
        )
        if utr_match:
            utr = utr_match.group(1)

        entity_id = (
            f"PAYMENT_{utr}"
            if utr
            else f"PAYMENT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        due_date = datetime.now() + timedelta(days=30) if status == "PENDING" else None

        return {
            "entity_type": "PAYMENT",
            "entity_id": entity_id,
            "status": status,
            "reference_id": utr,
            "amount": amount,
            "vendor": vendor,
            "due_date": due_date,
            "metadata": {
                "subject": subject,
                "sender": sender_email,
            },
        }

    # ──────────────────────────────────────────────────────────────────────
    # Invoice parsing with entity_id generation
    # ──────────────────────────────────────────────────────────────────────
    if "invoice" in subject_lower or "bill" in subject_lower:
        invoice_number = None
        inv_match = re.search(
            r"(?:invoice|bill|#)[:\s#-]*([A-Za-z0-9-]{5,})",
            subject + " " + body,
            re.IGNORECASE,
        )
        if inv_match:
            invoice_number = inv_match.group(1)

        amount = None
        amount_match = re.search(
            r"(?:₹|Rs\.?|\$|INR|total)[:\s]*([0-9,]+\.?\d*)", body, re.IGNORECASE
        )
        if amount_match:
            amount = float(amount_match.group(1).replace(",", ""))

        vendor = None
        vendor_match = re.search(
            r"(?:from|vendor|bill\s+from)[:\s]+([A-Za-z\s&]+?)(?=\s+(?:for|date|amount)|$)",
            body,
            re.IGNORECASE,
        )
        if vendor_match:
            vendor = vendor_match.group(1).strip()[:50]

        entity_id = (
            f"INVOICE_{invoice_number}"
            if invoice_number
            else f"INVOICE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        due_date = datetime.now() + timedelta(days=30)

        return {
            "entity_type": "INVOICE",
            "entity_id": entity_id,
            "status": "RECEIVED",
            "reference_id": invoice_number,
            "amount": amount,
            "vendor": vendor,
            "due_date": due_date,
            "metadata": {
                "subject": subject,
                "sender": sender_email,
            },
        }

    # Order confirmation parsing
    if "order" in subject_lower and "confirm" in subject_lower:
        order_id = None
        order_match = re.search(
            r"(?:order|#)[:\s#-]?([A-Za-z0-9-]{5,})",
            subject + " " + body,
            re.IGNORECASE,
        )
        if order_match:
            order_id = order_match.group(1)

        amount = None
        amount_match = re.search(
            r"(?:₹|Rs\.?|\$|total)[:\s]?([0-9,]+\.?\d*)", body, re.IGNORECASE
        )
        if amount_match:
            amount = amount_match.group(1).replace(",", "")

        return {
            "type": "ORDER",
            "status": "CONFIRMED",
            "metadata": {
                "subject": subject,
                "sender": sender_email,
                "order_id": order_id,
                "amount": amount,
            },
        }

    # Shipping/Delivery parsing
    if any(
        word in subject_lower
        for word in ["shipping", "delivery", "dispatched", "shipped"]
    ):
        tracking_id = None
        tracking_match = re.search(
            r"(?:tracking|awb)[:\s#-]?([A-Z0-9]{8,})",
            subject + " " + body,
            re.IGNORECASE,
        )
        if tracking_match:
            tracking_id = tracking_match.group(1)

        return {
            "type": "SHIPPING",
            "status": "IN_TRANSIT",
            "metadata": {
                "subject": subject,
                "sender": sender_email,
                "tracking_id": tracking_id,
            },
        }

    # Fallback for unrecognized system emails
    return {
        "type": "OTHER",
        "status": "UNKNOWN",
        "metadata": {"subject": subject, "sender": sender_email},
    }
