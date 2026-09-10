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


def header(hdrs, name: str, default: str = "") -> str:
    """Case-insensitive header read — the ONE way this file looks at a header.

    RFC 5322 makes header names case-insensitive and every provider payload is case-PRESERVING,
    so the spelling that arrives is whatever the sending mailer chose. N-01, N-02 and N-04 read
    `hdrs.get("Auto-Submitted")`, `hdrs.get("Precedence")` and `hdrs.get("List-Unsubscribe")`
    exactly, while `esqe/relevance._header_value` two modules over reads the same headers
    case-INSENSITIVELY. A connector that lower-cases header names therefore turned three of this
    gate's four bulk rules off with nothing going red — the exact failure the comment at
    `connectors/composio.py:71` says the `_NOISE_HEADERS` tuple was written to prevent.
    """
    if not hdrs:
        return default
    for key, value in hdrs.items():
        if str(key).strip().lower() == name.strip().lower():
            return str(value if value is not None else default)
    return default


def is_automated_sender(email: str | None) -> bool:
    """True for a machine local-part / mail-blaster subdomain — the ONE machine-sender table.

    Public because L1.6.4 (`capture/esqe/source_analyzer.py`) ranks actor authority off the
    same question and a second regex would drift into a second answer about `notify@stripe.com`
    — the gate dropping it as a robot while the scorer weighs it as a counterparty. Kept
    conservative for exactly the reason the table's own comment gives: `support@`/`hello@` are
    a real small business, and over-matching here costs a genuine sender 80% of its authority.
    """
    return bool(email) and bool(_AUTOMATED_SENDER.search(email))


#: The pre-existing private name, kept so the gate's own call sites read unchanged.
_automated_sender = is_automated_sender


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
    # "we chose not to read this" vs "we could not read this" must be distinguishable, or the
    # fix (wire an OCR engine) is invisible from the data.
    "DOC-06": "doc_ocr_unavailable",
    # An engine WAS wired and the read still produced nothing — a missing binary, a corrupt
    # scan, a page that rasterized to noise. Distinct from DOC-06 because the fix is different:
    # DOC-06 is a config line, DOC-07 is an engine or a source document to go and look at.
    "DOC-07": "doc_ocr_failed",
    # Audio arrived and no speech-to-text engine exists (L1.3.4-U3: source P5 is unbuilt).
    "DOC-08": "doc_transcription_unavailable",
    "DOC-09": "doc_transcription_failed",
    # A changing object arrived with no version to change WITH — undedupable, so it would
    # freeze at first-seen state rather than update.
    "MUT-01": "versionless_mutable",
    # No derivation rule could name who was allowed to see the original — parked, never
    # published under a guessed audience (capture/visibility_rules.py).
    "visibility_unknown": "visibility_unknown",
    # The LLM said junk but was not confident enough to authorise deletion → recoverable park.
    "llm_junk_unconfident": "llm_junk_low_confidence",
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


def content_integrity_rule(ctx: GateContext) -> tuple[str, str] | None:
    """Rules about whether we can READ this object at all. Never bypassable by a whitelist.

    A whitelist is a statement about the SENDER ("this person matters"), so letting it skip
    these produced the exact inversion of what anyone wanted: a contract or deck PDF from a
    known investor — the highest-value attachment class there is — sailed past the document
    park and was emitted with an empty body, while the same unreadable file from a stranger was
    correctly parked for review. A whitelist may prevent a DROP. It may never prevent a PARK.
    """
    doc = ctx.raw.get("document") or {}
    if doc.get("status") == "unsupported":
        return ("DOC-02", "park")
    if doc.get("status") == "ocr_unavailable":
        return ("DOC-06", "park")                # readable in principle, no engine wired
    if doc.get("status") == "ocr_review_required":
        return ("DOC-04", "park")
    # Every status below is an EMPTY document that knows why it is empty (L1.3.4-U2/U3). Each
    # needs its own park code or it falls off the end of this function and is emitted with an
    # empty body — which is the silent loss G2 counts, arriving through the gate instead of
    # through the router.
    if doc.get("status") == "ocr_failed":
        return ("DOC-07", "park")                # engine ran, read nothing → reviewable
    if doc.get("status") == "transcription_unavailable":
        return ("DOC-08", "park")                # no speech engine wired anywhere yet
    if doc.get("status") == "transcription_failed":
        return ("DOC-09", "park")
    if doc.get("status") == "fetch_failed":
        return ("DOC-05", "park")                # attachment download failed → retryable, never silent

    # A MUTABLE object with no version is undedupable, and the failure is silent and total: the
    # ledger says "already seen" on every later sync, so the object freezes at whatever state it
    # was in the first time. A HubSpot deal stuck at its first-seen stage reports a pipeline that
    # stopped moving the day it was connected. Park rather than emit — the object is real, we
    # simply cannot tell versions of it apart yet.
    from genios_engine.capture.source_registry import is_mutable, version_field_for
    if is_mutable(ctx.event.source) and not ctx.content_version:
        # Fall back to the raw field the descriptor names, so a connector that carries the stamp
        # in its payload but forgets to set `content_version` still passes rather than parking
        # its whole feed. Both empty is the real failure.
        if not ctx.raw.get(version_field_for(ctx.event.source) or ""):
            return ("MUT-01", "park")

    body = ctx.prepared.clean_text if ctx.prepared else (ctx.raw.get("snippet") or "")
    if not body.strip() and not bool(ctx.raw.get("has_attachment")):
        return ("N-10", "drop")                  # empty, no attachment — nothing to read
    return None


def noise_rule(ctx: GateContext) -> tuple[str, str] | None:
    """Sender/traffic-shape rules. These a whitelist MAY bypass — that is what it is for."""
    email = ctx.event.actor.email or ""
    subject = ctx.raw.get("subject") or ""
    hdrs: dict = ctx.raw.get("headers") or {}
    labels = set(ctx.raw.get("labelIds") or [])   # source-provided category signals

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

    if header(hdrs, "Auto-Submitted", "no") not in ("no", ""):
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
    if not att and header(hdrs, "Precedence").lower() in ("bulk", "list", "junk"):
        return ("N-04", "drop")                  # bulk campaign (Precedence header)
    if not att and any(header(hdrs, name) for name in
                       ("List-Unsubscribe", "List-Id", "List-Post", "Feedback-ID")):
        return ("N-02", "drop")                  # bulk campaign (unsubscribe / mailing-list / ESP headers)
    # N-11 (notification linked to tracked entity → park) needs entity linkage → S3/L2.
    # N-12/N-20 (bulk-from-known → park · grey-zone relevance) need relevance/linkage → L2.
    return None


def hard_rule(ctx: GateContext) -> tuple[str, str] | None:
    """Both classes in their historical order. Kept so callers and tests outside the gate keep
    working; ``run_gate`` evaluates the two halves separately so the whitelist can only skip
    the noise half."""
    return content_integrity_rule(ctx) or noise_rule(ctx)
