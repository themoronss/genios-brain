"""Universal pre-emit noise filter.

One module every adapter calls BEFORE billing + emit. The goal is dual:
  - Save customer credits — junk records do not deduct.
  - Save our Anthropic spend — junk records do not reach the Haiku
    extractor downstream.

Per-source rule registries below. Each adapter's pull path calls
`noise_gate.should_keep(source_type, record)` and drops the record on a
False return. The dropped reason is logged so ops can tune the rules.

Design notes:
  - Rules are simple data (regex + structural flags). No LLM, no DB.
  - Adding a source = adding a key to `_RULES`. No code branches.
  - Rules are deliberately conservative: drop only obvious noise. The
    refund-on-zero-signal layer in ingest_subscriber catches what slips
    through here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.foundations.telemetry import get_logger
from core.memory.types import RawRecord

log = get_logger(__name__)


@dataclass(frozen=True)
class GateDecision:
    """Why a record was kept or dropped. `reason` is short + machine-grep-able."""

    keep: bool
    reason: str


# ─────────────────────────────────────────────────────────────────────────────
# Per-source rule registry — extend by adding a key, no code branches.
# ─────────────────────────────────────────────────────────────────────────────


# Sender regexes — match against the `from` header (full string incl. display name).
# Grouped by category so adding patterns stays grep-able. \b word-boundary at
# start of each token name lets "alerts@" match inside "ICICI Alerts <alerts@..>".
_GMAIL_NOISE_SENDERS = [
    re.compile(p, re.I) for p in (
        # ── Generic automated (no-reply / system / bot) ──────────────────
        r"\bno-?reply@",
        r"\bdo-?not-?reply@",
        r"\bnoreply[._-]",
        r"\bnotifications?@",
        r"\balerts?@",
        r"\bautomated?@",
        r"\bbot@",
        r"\bnews(letter)?@",
        r"\bdigest@",
        r"@(mailer-daemon|postmaster)\.",

        # ── Marketing / sales / SaaS welcome / drip ──────────────────────
        r"\bmarketing@",
        r"\bcampaigns?@",
        r"\bgrowth@",
        r"\bsales@",
        r"\bhello@",
        r"\bhi@",
        r"\bwelcome@",
        r"\bgetstarted@",
        r"\bonboarding@",
        r"\bnew(s|)letter@",
        r"\bteam@",  # often used for marketing blasts from saas startups
        r"\bsupport@",  # tickets land in inbox but rarely business signal
        r"\bsupport-?(noreply|alert|reply)@",

        # ── HR / recruiting (from BOTH job boards and direct company HR) ─
        r"@(naukri|indeed|monster|linkedin-jobs|glassdoor|hirist|cutshort|"
        r"foundit|shine|wellfound|angel|angelco|otta|hired|himalayas|workatastartup)\.",
        r"\b(careers?|talent|jobs?|hiring|recruit(ing)?|hr|peopleops)@",
        r"\bapply(ing)?@",
        r"\bcandidates?@",

        # ── Banks / financial / fintech / payments — India + global ──────
        r"@([a-z0-9-]*bank[a-z0-9-]*)\.",  # *bank* in domain
        r"@(icici|hdfc|sbi|axis|kotak|yesbank|paytm|paypal|stripe|square|"
        r"razorpay|phonepe|gpay|googlepay|cashfree|amex|americanexpress|"
        r"visa|mastercard|citi|hsbc|chase|barclays|standardchartered|"
        r"deutsche|ubs|jpmorgan|morganstanley|bofa|wellsfargo|capitalone|"
        r"discover|ingbank|ing|aubank|idbi|pnb|bankofbaroda|bob|bandhanbank|"
        r"federal|rblbank|rbl|csb|equitas|esaf|jana|smallfinancebank)\.",
        r"\b(estatement|statement|estatements|payments?|payroll|invoice|"
        r"invoices|billing|receipt|transactions?)@",
        r"\bcustomercare@",
        r"\bcardservices?@",

        # ── Travel / transport / food / e-commerce / OTAs ────────────────
        r"@(amazon|flipkart|ebay|paytm|swiggy|zomato|uber|ola|rapido|"
        r"makemytrip|goibibo|ixigo|cleartrip|yatra|booking|expedia|airbnb|"
        r"agoda|tripadvisor|redbus|abhibus|irctc|trainpnr|indianrailways|"
        r"indigo|airindia|vistara|spicejet|emirates|qatar|britishairways|"
        r"lufthansa|delta|united|americanairlines|dhl|fedex|bluedart|"
        r"shiprocket|delhivery)\.",
        r"@(orders?|shipping|tracking|fulfillment|delivery)\.",

        # ── Govt / regulatory (statements, notices) ─────────────────────
        r"@(uidai|epfindia|incometax|incometaxindia|gst|gstn|gstin|cbic|"
        r"sebi|rbi|trai|mca|govt?\.in|gov\.in|nic\.in|esic|pfo)\.",

        # ── Telco / utility (bill, recharge) ────────────────────────────
        r"@(airtel|vi|vodafoneidea|jio|reliancejio|bsnl|tatateleservices|"
        r"actcorp|hathway|tplink|tata|adani|reliance|torrentpower)\.",

        # ── Social / community / forum noise ────────────────────────────
        r"@e\.linkedin\.com$",
        r"@updates\.linkedin\.com$",
        r"@em\.linkedin\.com$",
        r"@quora\.com$",
        r"@medium\.com$",
        r"@substack\.com$",
        r"@meetup\.com$",
        r"@eventbrite\.com$",
        r"@stackoverflow\.com$",
        r"@discourse\.",
        r"@discord(app)?\.com$",
        r"@reddit\.com$",
        r"@notifications\.github\.com$",
        r"@notify\.",
        r"@notification\.",

        # ── Anti-spam / security alerts (Google, Microsoft, etc) ────────
        r"\b(security|account)-?(noreply|notif|alert)@",
        r"\baccounts?-?noreply@",
        r"@accounts\.google\.com$",
    )
]

# Subject regexes — case-insensitive substring matches on the subject line.
_GMAIL_NOISE_SUBJECTS = [
    re.compile(p, re.I) for p in (
        # ── Identity / auth / security ──────────────────────────────────
        r"\b(otp|one[- ]time password|verification code|security code)\b",
        r"\bverify (your|the) (email|phone|account|identity)\b",
        r"\bpassword (reset|changed|change request|expir(ed|ing))\b",
        r"\baccount (verification|verify|locked|suspended|recovery)\b",
        r"\bsign[- ]?in (alert|attempt|from)\b",
        r"\bnew (device|sign-?in|login)\b",
        r"\btwo[- ]factor\b",
        r"\b(2fa|mfa) code\b",

        # ── Marketing / digest / newsletter ─────────────────────────────
        r"\bunsubscribe\b",
        r"\b(weekly|daily|monthly)\s+(digest|recap|summary|news|update|roundup)\b",
        r"\bnewsletter\b",
        r"\b(free|limited time) (offer|trial|access)\b",
        r"\b\d+%?\s*off\b",
        r"\bsale ends?\b",
        r"\b(announcing|introducing) (the )?new\b",

        # ── Welcome / onboarding ────────────────────────────────────────
        r"\bwelcome to\b",
        r"\bthanks for (signing up|joining|registering)\b",
        r"\bget started with\b",
        r"\byour (free )?trial (has |is )(begun|started|active|ended)\b",
        r"\bcomplete your (account|profile|setup)\b",

        # ── Recruiting / job ────────────────────────────────────────────
        r"\bjob\s+(alert|match|recommendation|opportunit(y|ies))\b",
        r"\b(thanks?|thank you) for (applying|your application)\b",
        r"\b(your )?application (has been )?(received|submitted)\b",
        r"\bnext steps? in your application\b",
        r"\b(we|the team) (regret|are unable) to\b",  # rejection emails
        r"\bunfortunatel(y|y,) (we|our)\b",

        # ── Financial / billing / transactional ─────────────────────────
        r"\b(your )?(monthly|quarterly|annual)? ?(account |credit card |bank )?statement\b",
        r"\b(your )?invoice\b",
        r"\b(payment|invoice) (received|reminder|due|failed|successful)\b",
        r"\breceipt for\b",
        r"\bautopay\b",
        r"\btransaction (alert|notification|confirmation)\b",
        r"\bdebit(ed)? (from|on)\b",
        r"\bcredit(ed)? (to|on)\b",
        r"\bbalance (alert|enquiry)\b",
        r"\bemi (due|reminder|payment)\b",
        r"\b(card|policy) renewal\b",

        # ── Orders / shipping ───────────────────────────────────────────
        r"\b(your )?order (has been )?(placed|confirmed|shipped|delivered|cancelled)\b",
        r"\bout for delivery\b",
        r"\btracking (number|info|details)\b",
        r"\bdelivery (update|confirmation)\b",

        # ── Notifications / system ──────────────────────────────────────
        r"\baction required\b",
        r"\b(?:please )?reset your password\b",
        r"\bgovernment of india\b",
        r"\bregulatory (notice|update)\b",
    )
]


_RULES: dict[str, dict[str, Any]] = {
    "gmail": {
        "sender_patterns":   _GMAIL_NOISE_SENDERS,
        "subject_patterns":  _GMAIL_NOISE_SUBJECTS,
        "min_content_chars": 80,
        # Gmail category labels we still drop at the adapter query level
        # but enumerated here for completeness / future override path.
        "drop_labels": {
            "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES",
            "CATEGORY_FORUMS", "SPAM", "TRASH",
        },
    },
    "calendar": {
        "skip_blank_description":   True,
        "skip_solo_attendee":       True,   # blocked-time placeholders
        "skip_all_day":             True,
        "min_attendees":            2,
        "min_content_chars":        20,
    },
    "slack": {
        "skip_bot_messages":        True,
        "skip_system_messages":     True,   # joined / left channel / channel_renamed
        "min_message_chars":        30,
        "skip_emoji_only":          True,
    },
    "hubspot": {
        "skip_auto_logged":         True,   # bot-generated activities
        "skip_zero_value_deal":     False,  # zero-value deals may still matter
        "min_content_chars":        50,
    },
    "notion": {
        "min_content_chars":        80,
        "skip_template_pages":      True,
    },
    "manual": {
        # User typed it themselves — never drop. The customer already
        # chose to pay for it.
        "_always_keep": True,
    },
    "upload": {
        # User uploaded the file. Skipping a chunk silently would surprise.
        "_always_keep": True,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────────────────


def should_keep(source_type: str, record: RawRecord) -> GateDecision:
    """Universal noise gate. Returns (keep, reason).

    Unknown source_type → keep (better to over-bill once than block a new
    adapter from working). The rule sheet below makes adding a source a
    one-line registry change.
    """
    rules = _RULES.get(source_type)
    if rules is None:
        return GateDecision(True, "no_rules_for_source")
    if rules.get("_always_keep"):
        return GateDecision(True, "always_keep")

    if source_type == "gmail":
        return _gmail_decision(record, rules)
    if source_type == "calendar":
        return _calendar_decision(record, rules)
    if source_type == "slack":
        return _slack_decision(record, rules)
    if source_type == "hubspot":
        return _hubspot_decision(record, rules)
    if source_type == "notion":
        return _notion_decision(record, rules)

    return GateDecision(True, "no_handler")


# ─────────────────────────────────────────────────────────────────────────────
# Per-source decision helpers
# ─────────────────────────────────────────────────────────────────────────────


def _gmail_decision(record: RawRecord, rules: dict) -> GateDecision:
    f = record.fields
    labels = set(f.get("labels", []) or [])
    if rules["drop_labels"] & labels:
        return GateDecision(False, f"label:{(rules['drop_labels'] & labels).pop()}")

    sender = (f.get("from") or "").lower()
    for pat in rules["sender_patterns"]:
        if pat.search(sender):
            return GateDecision(False, f"noise_sender:{pat.pattern[:30]}")

    subject = f.get("subject") or ""
    for pat in rules["subject_patterns"]:
        if pat.search(subject):
            return GateDecision(False, f"noise_subject:{pat.pattern[:30]}")

    content = f.get("snippet") or ""
    if len(content.strip()) < rules["min_content_chars"]:
        return GateDecision(False, "too_short")

    # LLM gatekeeper — final pass on what the pattern rules let through.
    # ~$0.0001 per call (50 in + 1-3 out tokens). Pattern misses are the
    # long tail (varied bank senders, real-looking HR addresses, SaaS
    # team@ that's marketing, etc) — the gate's domain knowledge catches
    # them. Fail-open: any LLM error keeps the record (we don't block a
    # business email on a transient API failure).
    try:
        from core.memory.llm_gate import is_business_relevant
        verdict = is_business_relevant(sender=sender, subject=subject, body=content)
        if not verdict.keep:
            return GateDecision(False, f"llm_gate:{verdict.reason}")
    except Exception as e:
        log.warning("llm_gate_call_failed", error=str(e))

    return GateDecision(True, "kept")


def _calendar_decision(record: RawRecord, rules: dict) -> GateDecision:
    f = record.fields
    desc = (f.get("description") or "").strip()
    if rules["skip_blank_description"] and not desc:
        return GateDecision(False, "blank_description")
    if len(desc) < rules["min_content_chars"]:
        return GateDecision(False, "too_short")
    attendees = f.get("attendees") or []
    if rules["skip_solo_attendee"] and len(attendees) <= 1:
        return GateDecision(False, "solo_event")
    if rules["min_attendees"] and len(attendees) < rules["min_attendees"]:
        return GateDecision(False, "too_few_attendees")
    if rules["skip_all_day"] and f.get("all_day"):
        return GateDecision(False, "all_day_block")
    return GateDecision(True, "kept")


def _slack_decision(record: RawRecord, rules: dict) -> GateDecision:
    f = record.fields
    text = (f.get("text") or "").strip()
    if rules["skip_bot_messages"] and f.get("is_bot"):
        return GateDecision(False, "bot_message")
    if rules["skip_system_messages"] and f.get("subtype"):
        return GateDecision(False, f"system:{f.get('subtype')}")
    if len(text) < rules["min_message_chars"]:
        return GateDecision(False, "too_short")
    if rules["skip_emoji_only"] and re.fullmatch(r"(:[a-z0-9_+-]+:\s*)+", text):
        return GateDecision(False, "emoji_only")
    return GateDecision(True, "kept")


def _hubspot_decision(record: RawRecord, rules: dict) -> GateDecision:
    f = record.fields
    if rules["skip_auto_logged"] and f.get("auto_logged"):
        return GateDecision(False, "auto_logged")
    if rules["skip_zero_value_deal"] and f.get("type") == "deal" and not f.get("amount"):
        return GateDecision(False, "zero_value_deal")
    content = (f.get("notes") or f.get("body") or "").strip()
    if len(content) < rules["min_content_chars"]:
        return GateDecision(False, "too_short")
    return GateDecision(True, "kept")


def _notion_decision(record: RawRecord, rules: dict) -> GateDecision:
    f = record.fields
    content = (f.get("content") or f.get("body") or "").strip()
    if len(content) < rules["min_content_chars"]:
        return GateDecision(False, "too_short")
    if rules["skip_template_pages"] and f.get("template"):
        return GateDecision(False, "template_page")
    return GateDecision(True, "kept")
