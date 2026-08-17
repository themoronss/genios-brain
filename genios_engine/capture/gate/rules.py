from __future__ import annotations

import re

from genios_engine.capture.source_families import DELIBERATE_FAMILIES, DELIBERATE_SOURCES

from .context import GateContext

# Deterministic S1. Whitelist runs BEFORE destructive drops so known
# customers/prospects/vendors/important-attachments are never blanket-dropped.

# Only DEAD mail is hard-dropped on the sender alone: a bounce/mailer-daemon carries no
# business signal ever. Ambiguous no-reply/notification/newsletter senders are NOT dropped
# here anymore (a receipt, an invoice, an "action required" notice all come from noreply@);
# they fall through to the S2 LLM gate, which keeps the relevant ones and drops true junk.
_DEAD_SENDER = re.compile(r"(mailer-daemon|bounces?@|postmaster@)", re.I)
_OOO = re.compile(r"\b(out of office|ooo|on leave|automatic reply|chutti)\b", re.I)

# Machine/bulk senders that never expect a human reply. Deliberately CONSERVATIVE for a hard drop:
# only clearly-automated local-parts (no-reply / notify / newsletter / digest / mailer / bounce /
# marketing / alerts) and mail-blaster subdomains. NOT support@/info@/hello@/team@ — those can be a
# real small business, so they still go to the S2 LLM gate. Every drop below is guarded by
# has_attachment so a vendor invoice/receipt from noreply@ is never lost.
_AUTOMATED_SENDER = re.compile(
    r"(^|[._+-])(no[._-]?reply|do[._-]?not[._-]?reply|notify|notification[s]?|"
    r"newsletter|digest|mailer|mailings?|marketing|campaign[s]?|no[._-]?response|"
    r"jobalerts?|alerts?)([._+-]|@)|@(notify|email|mail|mailer|news|updates?|alerts?|e|em|mktg)\.",
    re.I)

# Gmail's own high-confidence categories + provider spam. These drop regardless of attachment.
_JUNK_LABELS = frozenset({"SPAM", "TRASH", "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"})


def _automated_sender(email: str) -> bool:
    return bool(email) and bool(_AUTOMATED_SENDER.search(email))


def light_junk(labels, sender_email: str, has_attachment: bool) -> str | None:
    """High-confidence deterministic junk from LIST-time fields ONLY (Gmail labels + sender local-
    part) — lets the connector drop obvious junk BEFORE the S2 LLM prime ever runs, so it costs no
    model call. Header-based bulk signals (List-Unsubscribe/Precedence) need the full fetch and stay
    on the LLM path. Mirrors hard_rule exactly so the pipeline gate reaches the SAME verdict."""
    labs = set(labels or [])
    if labs & {"SPAM", "TRASH"}:
        return "N-09"
    if "CATEGORY_PROMOTIONS" in labs:
        return "N-06"
    if "CATEGORY_SOCIAL" in labs:
        return "N-07"
    if not has_attachment and _automated_sender(sender_email or ""):
        return "N-03"
    return None

# Human-readable label per reason code — shown in traces/logs so a drop is legible.
REASON_LABELS = {
    "W-01": "known_sender", "W-02": "starred_important", "W-03": "agent_event",
    "W-04": "important_attachment", "W-05": "deliberate_source",
    "N-01": "machine_ack", "N-02": "bulk_campaign_unsub", "N-03": "no_reply_sender",
    "N-04": "bulk_precedence", "N-05": "out_of_office", "N-06": "gmail_promotions",
    "N-07": "gmail_social", "N-08": "tenant_blocklisted", "N-09": "provider_spam",
    "N-10": "empty_no_attachment", "duplicate": "already_seen",
    "out_of_scope": "out_of_scope", "mapping_missing": "structured_unmapped",
    "structured_mapped": "structured_ok", "low_relevance": "low_relevance",
    "llm_junk": "llm_junk_gate",
    "poison_quarantine": "poison_quarantine",
    "DOC-02": "doc_unsupported", "DOC-04": "doc_ocr_review", "DOC-05": "doc_fetch_failed",
}


def whitelist(ctx: GateContext) -> str | None:
    """Return a W-code if the event bypasses destructive drops, else None."""
    labels = set(ctx.raw.get("labelIds") or [])
    if ctx.sender_known:
        return "W-01"                            # known customer/prospect/vendor
    if "STARRED" in labels or ctx.raw.get("approved_sender"):
        return "W-02"                            # human-starred / manually approved
    if ctx.event.actor.type == "agent":
        return "W-03"                            # agent event
    if ctx.raw.get("important_attachment"):
        return "W-04"                            # contract/invoice/legal marker
    if (ctx.event.source in DELIBERATE_SOURCES
            or ctx.event.source_family in DELIBERATE_FAMILIES):
        return "W-05"                            # a human/agent deliberately handed us this —
                                                 # N-codes exist for inbox firehoses, not for it
    return None


def hard_rule(ctx: GateContext) -> tuple[str, str] | None:
    """Return (reason_code, action) to drop/park, else None. Only very-high-certainty
    drops — ambiguous automation is parked, never blanket-dropped."""
    email = ctx.event.actor.email or ""
    subject = ctx.raw.get("subject") or ""
    body = ctx.prepared.clean_text if ctx.prepared else (ctx.raw.get("snippet") or "")
    hdrs: dict = ctx.raw.get("headers") or {}
    labels = set(ctx.raw.get("labelIds") or [])   # source-provided category signals

    # Documents: unparseable / low-confidence OCR → park (reviewable, never silent drop).
    doc = ctx.raw.get("document") or {}
    if doc.get("status") == "unsupported":
        return ("DOC-02", "park")
    if doc.get("status") == "ocr_review_required":
        return ("DOC-04", "park")
    if doc.get("status") == "fetch_failed":
        return ("DOC-05", "park")                # attachment download failed → retryable, never silent

    # Provider-classified spam/trash + tenant blocklist — highest-confidence noise.
    if "SPAM" in labels or "TRASH" in labels:
        return ("N-09", "drop")                  # provider spam/trash label
    if ctx.raw.get("sender_blocked"):
        return ("N-08", "drop")                  # tenant blocklist (fed by tenant config)

    # Gmail's own high-confidence categories → deterministic noise (no guessing).
    # (CATEGORY_UPDATES is left alone — receipts/alerts can matter; L2 decides.)
    if "CATEGORY_PROMOTIONS" in labels:
        return ("N-06", "drop")                  # marketing / promotions
    if "CATEGORY_SOCIAL" in labels:
        return ("N-07", "drop")                  # social-network notifications

    if str(hdrs.get("Auto-Submitted", "no")) not in ("no", ""):
        return ("N-01", "drop")                  # machine acknowledgement
    if _OOO.search(subject):
        return ("N-05", "drop")                  # out-of-office — SUBJECT only. Body no longer drops:
                                                 # a normal email that merely mentions "out of office"
                                                 # in prose is real mail, not an auto-reply.
    # N-02/03/04 are bulk / no-reply SIGNALS, not certainties: a vendor invoice or receipt routinely
    # comes from noreply@ or carries a List-Unsubscribe header. If the message carries a real
    # attachment (an invoice/contract PDF), do NOT hard-drop it on these signals — let relevance/L2
    # decide. High-confidence noise (SPAM/TRASH, Gmail PROMOTIONS/SOCIAL) above still drops regardless.
    att = bool(ctx.raw.get("has_attachment"))
    if not att and (_DEAD_SENDER.search(email) or _automated_sender(email)):
        return ("N-03", "drop")                  # dead mail (bounce/mailer-daemon) OR a clearly
                                                 # automated/bulk sender (no-reply/notify/newsletter/
                                                 # digest/mailer) with no attachment — no human reply
                                                 # expected. Attachment-bearing mail is exempted
                                                 # above so a vendor invoice from noreply@ survives.
    if not att and str(hdrs.get("Precedence", "")).lower() in ("bulk", "list", "junk"):
        return ("N-04", "drop")                  # bulk campaign (Precedence header)
    if not att and (hdrs.get("List-Unsubscribe") or hdrs.get("List-Id")
                    or hdrs.get("List-Post") or hdrs.get("Feedback-ID")):
        return ("N-02", "drop")                  # bulk campaign (unsubscribe / mailing-list / ESP headers)
    if not body.strip() and not att:
        return ("N-10", "drop")                  # empty, no attachment
    # N-11 (notification linked to tracked entity → park) needs entity linkage → S3/L2.
    # N-12/N-20 (bulk-from-known → park · grey-zone relevance) need relevance/linkage → L2.
    return None
