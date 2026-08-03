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


# UNIVERSAL noise — these are junk for EVERY business, regardless of vertical.
# Bank / HR / shipping / SaaS-welcome patterns intentionally REMOVED — they
# are signal for finance / recruiting / logistics / SaaS-customer-success
# verticals respectively. Per-vertical relevance is the LLM gate's job
# (sees org.business_context), not this regex layer.
#
# What stays here: identity/auth/security/spam — categories no startup
# wants in their context graph regardless of what they do.
_GMAIL_NOISE_SENDERS = [
    re.compile(p, re.I) for p in (
        # System / bounces / postmaster — never business signal anywhere
        r"@(mailer-daemon|postmaster|bounces?)\.",
        r"^mailer-daemon@",
        # Account security from major providers
        r"@accounts\.google\.com$",
        r"\b(security|account)-?(noreply|notif|alert)@",
        r"\baccounts?-?noreply@",
        # Generic noreply / do-not-reply — IF the LLM gate later decides
        # one of these IS relevant for a given vertical (e.g. tracking
        # for a logistics startup), the gate will override.
        r"\bno-?reply@",
        r"\bdo-?not-?reply@",
        r"\bnoreply[._-]",
        # Bulk-marketing senders — newsletters / campaign blasts. A founder's
        # manager-brain should never surface these as "priorities".
        r"\b(newsletter|marketing|promo(tions)?|campaigns?|events?|webinars?)@",
        r"@e?mail\.(mailchimp|mailgun|sendgrid|hubspotemail|substack|beehiiv|convertkit)\.",
        r"@(mailchimpapp|sendgrid|mailgun|customeriomail)\.",
    )
]

# UNIVERSAL noise subjects — OTPs, password resets, sign-in alerts.
# Statement / invoice / "thanks for applying" / "order shipped" etc REMOVED
# for the same vertical-context reason as the senders above.
_GMAIL_NOISE_SUBJECTS = [
    re.compile(p, re.I) for p in (
        # Identity / auth / security — junk for everyone
        r"\b(otp|one[- ]time password|verification code|security code)\b",
        r"\bverify (your|the) (email|phone|account|identity)\b",
        r"\bpassword (reset|changed|change request|expir(ed|ing))\b",
        r"\baccount (verification|verify|locked|suspended|recovery)\b",
        r"\bsign[- ]?in (alert|attempt|from)\b",
        r"\bnew (device|sign-?in|login)\b",
        r"\btwo[- ]factor\b",
        r"\b(2fa|mfa) code\b",
        # Unsubscribe / explicit marketing markers — rare in real biz threads
        r"\bunsubscribe\b",
        # Promo / event-blast subjects — "register now", "you're invited",
        # webinar pushes, %-off sales. These were leaking through as
        # "suggestions"; a 1:1 event invite from a real contact has none of
        # these phrasings, so false-positive risk is low. LLM gate can still
        # override for verticals where events ARE the business.
        r"\bwebinar\b",
        r"\byou'?re invited\b",
        r"\bregister (now|today|here|free)\b",
        r"\b(last chance|don'?t miss|limited (time|seats|spots))\b",
        r"\b\d{1,2}% off\b",
        r"\b(flash|mega|festive) sale\b",
        r"\bnewsletter\b",
        r"\bjoin us (for|at|live)\b",
    )
]


_RULES: dict[str, dict[str, Any]] = {
    "gmail": {
        "sender_patterns":   _GMAIL_NOISE_SENDERS,
        "subject_patterns":  _GMAIL_NOISE_SUBJECTS,
        # Gmail's snippet field is a ~150-char preview, not the full
        # body — a 2-line ack like "Sure, let's chat 3pm tomorrow" is
        # legit signal even though it's well under 80 chars. The LLM
        # gate downstream handles "is this actually content?".
        "min_content_chars": 30,
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


def should_keep(
    source_type: str,
    record: RawRecord,
    *,
    org_id: str | None = None,
) -> GateDecision:
    """Universal noise gate. Returns (keep, reason).

    Unknown source_type → keep (better to over-bill once than block a new
    adapter from working). The rule sheet below makes adding a source a
    one-line registry change.

    org_id (optional): when provided, lets the per-source handler call
    the org-context-aware LLM gate. Without it the LLM gate falls back
    to its generic-business default.
    """
    rules = _RULES.get(source_type)
    if rules is None:
        return GateDecision(True, "no_rules_for_source")
    if rules.get("_always_keep"):
        return GateDecision(True, "always_keep")

    if source_type == "gmail":
        return _gmail_decision(record, rules, org_id=org_id)
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


def _gmail_decision(record: RawRecord, rules: dict, *, org_id: str | None = None) -> GateDecision:
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
    # ~$0.0003 per call (50-300 in + ≤4 out tokens). With org_id we send
    # the org's business_context so the model judges relevance from THE
    # CUSTOMER'S viewpoint (bank statements = signal for a fintech,
    # noise for a sales SaaS). Without org_id it falls back to the
    # generic-business prompt. Fail-open on any LLM error so a
    # transient API blip doesn't drop legitimate mail.
    try:
        from core.memory.llm_gate import is_business_relevant
        verdict = is_business_relevant(
            sender=sender, subject=subject, body=content, org_id=org_id,
        )
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
