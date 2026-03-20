"""
Email Classification Module for GeniOS

Categorizes emails into STRONG, WEAK, SYSTEM, or DISCARD
to optimize LLM processing and separate relationship data from state data.

Author: GeniOS Team
Version: 1.1
Last Updated: 2026-03-18
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Classification Constants
SYSTEM_KEYWORDS = [
    "gst",
    "tax",
    "invoice",
    "receipt",
    "payment",
    "transaction",
    "itr",
    "bill",
    "refund",
    "order confirmation",
    "shipping",
    "delivery",
]

SYSTEM_DOMAINS = [
    "gov.in",
    ".bank",
    "razorpay",
    "stripe",
    "paypal",
    "paytm",
    "banking",
    "noreply@amazon",
    "noreply@flipkart",
]

DISCARD_KEYWORDS = [
    "unsubscribe",
    "newsletter",
    "no-reply",
    "noreply",
    "donotreply",
    "automated",
    "notification",
    "digest",
    "marketing",
]

WEAK_WORD_THRESHOLD = 25  # Emails with fewer words are considered WEAK


def classify_email(
    subject: str, sender_email: str, body: str, headers: Optional[Dict[str, str]] = None
) -> str:
    """
    Classify email into categories for processing optimization.

    Args:
        subject: Email subject line
        sender_email: Sender's email address
        body: Email body content
        headers: Optional email headers dict

    Returns:
        str: One of "STRONG", "WEAK", "SYSTEM", "DISCARD"

    Classification Rules:
        SYSTEM: Contains GST/tax/invoice/payment keywords or from gov/bank domains
        DISCARD: Has unsubscribe header or from marketing/newsletter senders
        WEAK: Body has < 25 words (not enough signal)
        STRONG: Default category (full LLM extraction)
    """

    # Normalize inputs
    subject_lower = (subject or "").lower()
    sender_lower = (sender_email or "").lower()
    body_lower = (body or "").lower()
    headers = headers or {}

    # SYSTEM check - structured state data (GST, payments, invoices)
    if any(keyword in subject_lower for keyword in SYSTEM_KEYWORDS):
        logger.debug(f"Classified as SYSTEM (keyword in subject): {subject[:50]}")
        return "SYSTEM"

    if any(domain in sender_lower for domain in SYSTEM_DOMAINS):
        logger.debug(f"Classified as SYSTEM (domain match): {sender_email}")
        return "SYSTEM"

    # DISCARD check - marketing/automated emails
    unsubscribe_header = headers.get("List-Unsubscribe") or headers.get(
        "list-unsubscribe"
    )
    if unsubscribe_header:
        logger.debug(f"Classified as DISCARD (unsubscribe header): {subject[:50]}")
        return "DISCARD"

    if any(keyword in sender_lower for keyword in DISCARD_KEYWORDS):
        logger.debug(f"Classified as DISCARD (keyword in sender): {sender_email}")
        return "DISCARD"

    # WEAK check - insufficient content for meaningful extraction
    word_count = len(body_lower.split())
    if word_count < WEAK_WORD_THRESHOLD:
        logger.debug(f"Classified as WEAK ({word_count} words): {subject[:50]}")
        return "WEAK"

    # STRONG - default category for full LLM extraction
    logger.debug(f"Classified as STRONG: {subject[:50]}")
    return "STRONG"


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
    import re
    from datetime import datetime, timedelta

    subject_lower = subject.lower()
    body_lower = body.lower()

    # ──────────────────────────────────────────────────────────────────────
    # GST/Tax parsing with entity_id generation
    # ──────────────────────────────────────────────────────────────────────
    if "gst" in subject_lower or "itr" in subject_lower:
        status = "PENDING"  # Default
        if "filed" in body_lower or "submitted" in body_lower:
            status = "FILED"
        elif "pending" in body_lower:
            status = "PENDING"

        # Extract period (Q1, Q2, Q3, Q4, FY2023-24, etc.)
        period = None
        period_match = re.search(
            r"(Q[1-4]|FY\s?\d{4}-?\d{2})", subject + " " + body, re.IGNORECASE
        )
        if period_match:
            period = period_match.group(1)

        # Extract ARN (Application Reference Number)
        arn = None
        arn_match = re.search(r"ARN[\s:]*([A-Za-z0-9]{10,})", body, re.IGNORECASE)
        if arn_match:
            arn = arn_match.group(1)

        # Generate entity_id: GST_Q2_2025
        year = datetime.now().year
        entity_id = (
            f"GST_{period}_{year}"
            if period
            else f"GST_{datetime.now().strftime('%Y-%m-%d')}"
        )

        # Estimate due date (typically end of next month after period)
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
        status = "PENDING"  # Default
        if "success" in body_lower or "confirmed" in body_lower:
            status = "CONFIRMED"

        # Extract amount
        amount = None
        amount_match = re.search(
            r"(?:₹|Rs\.?|\$|INR)[\s]*([0-9,]+\.?\d*)", subject + " " + body
        )
        if amount_match:
            amount = float(amount_match.group(1).replace(",", ""))

        # Extract vendor/payee
        vendor = None
        vendor_match = re.search(
            r"(?:to|from|vendor|payee)[:\s]+([A-Za-z&\s]+?)(?=\s+(?:has|have|been|confirmed|for|on|by|amount|transaction)|$)",
            body,
            re.IGNORECASE,
        )
        if vendor_match:
            vendor = vendor_match.group(1).strip()[:50]

        # Extract UTR or reference
        utr = None
        utr_match = re.search(
            r"(?:UTR|utr|reference)[:\s]*([A-Za-z0-9]{10,})", body, re.IGNORECASE
        )
        if utr_match:
            utr = utr_match.group(1)

        # Generate entity_id: PAYMENT_UTR_123 or PAYMENT_TIMESTAMP
        entity_id = (
            f"PAYMENT_{utr}"
            if utr
            else f"PAYMENT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Estimate due date (typically 30 days from now for payments)
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
        # Extract invoice number
        invoice_number = None
        inv_match = re.search(
            r"(?:invoice|bill|#)[:\s#-]*([A-Za-z0-9-]{5,})",
            subject + " " + body,
            re.IGNORECASE,
        )
        if inv_match:
            invoice_number = inv_match.group(1)

        # Extract amount
        amount = None
        amount_match = re.search(
            r"(?:₹|Rs\.?|\$|INR|total)[:\s]*([0-9,]+\.?\d*)", body, re.IGNORECASE
        )
        if amount_match:
            amount = float(amount_match.group(1).replace(",", ""))

        # Extract vendor
        vendor = None
        vendor_match = re.search(
            r"(?:from|vendor|bill\s+from)[:\s]+([A-Za-z\s&]+?)(?=\s+(?:for|date|amount)|$)",
            body,
            re.IGNORECASE,
        )
        if vendor_match:
            vendor = vendor_match.group(1).strip()[:50]

        # Generate entity_id: INVOICE_INV-001
        entity_id = (
            f"INVOICE_{invoice_number}"
            if invoice_number
            else f"INVOICE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Estimate due date (typically 30 days for invoices)
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

    # Order confirmation parsing with order_id and amount
    if "order" in subject_lower and "confirm" in subject_lower:
        # Extract order ID
        import re

        order_id = None
        order_match = re.search(
            r"(?:order|#)[:\s#-]?([A-Za-z0-9-]{5,})",
            subject + " " + body,
            re.IGNORECASE,
        )
        if order_match:
            order_id = order_match.group(1)

        # Extract amount
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

    # Shipping/Delivery parsing with tracking_id
    if any(
        word in subject_lower
        for word in ["shipping", "delivery", "dispatched", "shipped"]
    ):
        # Extract tracking ID
        import re

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
