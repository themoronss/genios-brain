"""Step 2 · the delivery-status recogniser — *a message we sent did not arrive.*

WHY THIS EXISTS. On 11 August the tenant pitched Afore and Surge. Three of those messages never
reached anyone — `madison@afore.vc` and `joseph@afore.vc` did not exist, and
`apply@surgeahead.com` failed permanently after 47 hours of retries. The bounce notices have been
in the mailbox since, Layer 1 captured all five of them, and **not one signal came out**. A
founder who believes they pitched two funds did not pitch them, and nothing in the product could
say so.

WHERE IT WAS LOST, from the production trace on 2026-09-23:

    S2                      pass           N-05                   availability=auto_reply
    s2_semantic_extraction  short_circuit  envelope_bulk_headers
    s4_esqe                 short_circuit  bulk_headers           signals=0

`esqe/relevance.refused_without_extraction` runs BEFORE S2 so an envelope-only refusal can save a
model call, and on the pilot org that rule saved 522,143 input tokens. It is right for a
newsletter. A delivery failure is the one kind of automated mail that is a **fact about something
the tenant did**, and the same rule swallowed it — 30 events org-wide.

So this module answers one question — *is this a delivery-status notification, and did delivery
fail?* — and `relevance.py` consults it above the bulk-header rung.

PROSE FIRST, NOT RFC 3464. The step that produced this module was written expecting to walk a
`multipart/report; report-type=delivery-status` MIME structure. Reading the real bodies made that
unnecessary for the first cut: Gmail states the address in the sentence —

    Your message wasn't delivered to madison@afore.vc because the address couldn't be found

— and `prepared_content` already holds that text, PII-masked and offset-mapped, for every one of
the five. A structured `Status: 5.1.1` / `Final-Recipient:` reader is a hardening pass for other
providers, not a prerequisite. It belongs here when a non-Gmail bounce is actually observed.

TWO CONDITIONS, BOTH REQUIRED, AND THAT IS THE WHOLE SAFETY ARGUMENT. A sender that is a delivery
daemon AND a body that reads like a delivery report. Either alone is a false positive waiting to
happen: `postmaster@` also sends ordinary administrative mail, and a person forwarding a bounce to
a colleague — *"Fwd: Delivery Status Notification (Failure) — can you resend?"* — carries the
words without being the thing. **A fabricated delivery failure is worse than a missed one**,
because it tells a founder to re-send a message that did arrive.

FAILED IS NOT THE SAME AS DELAYED, AND THAT DISTINCTION IS THE POINT. Surge produced two delay
notices (23 and 47 more hours) before the permanent failure. During those hours the honest answer
is that we do not know whether the message arrived. Reporting a bounce then would be exactly the
manufactured certainty this architecture exists to prevent — the same failure class as claiming a
condition was met on evidence that was not in the source.

No clock, no I/O, no model. Pure functions over strings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["DeliveryStatus", "FAILED", "DELAYED", "UNKNOWN", "read_delivery_status",
           "is_delivery_status", "names_a_delivery_report"]

#: Delivery failed and will not be retried. The finding.
FAILED = "failed"
#: Still being retried. NOT a finding — see the module docstring.
DELAYED = "delayed"
#: A delivery report we recognise but cannot classify. Recognised so it is not treated as
#: ordinary bulk mail; not reported as a failure, because we do not know that it is one.
UNKNOWN = "unknown"

#: Who sends delivery reports. Deliberately the same shape as `gate/rules._DEAD_SENDER` — a
#: second opinion about what a mail daemon looks like would eventually disagree with the first,
#: and the gate's table is the one that has been in production.
_DAEMON = re.compile(r"(mailer-daemon|postmaster@|bounces?@|mail[-_.]?delivery)", re.I)

#: What a delivery report says about itself. `subject` and `snippet` are both consulted because
#: the pipeline hands S4 the envelope before the body in some paths, and a DSN names itself in
#: both.
_REPORT = re.compile(
    r"delivery status notification"
    r"|delivery (?:has )?failed"
    r"|undelivered mail returned"
    r"|message not delivered"
    r"|delivery incomplete"
    r"|address not found",
    re.I)

#: Permanent failure. Gmail's own wording, plus the SMTP 5.x.x class for providers that quote it.
_FAILED_MARKERS = re.compile(
    r"\(failure\)"
    r"|message not delivered"
    r"|address not found"
    r"|wasn't delivered"
    r"|was not delivered"
    r"|couldn't be delivered"
    r"|could not be delivered"
    r"|permanent(?:ly)? fail"
    r"|\b5\.\d\.\d\b",
    re.I)

#: Still trying. Checked BEFORE the failure markers, because a delay notice contains
#: "delivery incomplete" and would otherwise read as a failure on a looser pattern.
_DELAY_MARKERS = re.compile(
    r"\(delay\)"
    r"|delivery incomplete"
    r"|will retry"
    r"|temporary problem"
    r"|\b4\.\d\.\d\b",
    re.I)

#: The address delivery was attempted to, as Gmail states it in prose. The verb varies
#: ("wasn't delivered to", "couldn't be delivered to", "while delivering your message to") so the
#: pattern anchors on the preposition and takes the address that follows it.
_RECIPIENT = re.compile(
    r"(?:deliver(?:ed|ing|y)?)\b[^.\n]{0,40}?\bto\s+<?([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})>?",
    re.I)

#: RFC 3464's structured field, when a provider includes it. Preferred over the prose when both
#: are present: it is the standard, and it is unambiguous.
_FINAL_RECIPIENT = re.compile(
    r"^\s*final-recipient\s*:\s*(?:rfc822;)?\s*<?([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})>?",
    re.I | re.M)


@dataclass(frozen=True, slots=True)
class DeliveryStatus:
    """What a delivery report says. `recipient` is `None` when it could not be read.

    A bounce whose address we cannot parse is **still a bounce** — it is recognised, so it is not
    refused as bulk mail, and the address is left absent rather than guessed. `unknown` is a real
    answer here for the same reason it is everywhere else in this layer: a wrong address in a
    "your message never arrived" card costs more than an incomplete one.
    """

    #: `FAILED` | `DELAYED` | `UNKNOWN`.
    kind: str
    #: The address delivery was attempted to, or `None` when the report did not state it in a
    #: form we can read without guessing.
    recipient: str | None
    #: The report's own words about why, trimmed. Carried for the evidence span, not parsed.
    reason: str | None = None

    @property
    def failed(self) -> bool:
        """Permanently undeliverable. `DELAYED` and `UNKNOWN` are both False — a message still
        being retried has not failed, and one we could not classify is not something to assert."""
        return self.kind == FAILED


def names_a_delivery_report(text: str) -> bool:
    """Does this string call itself a delivery report? **Sender not consulted.**

    Split out for `gate/rules.availability_marker`, whose stated contract is *"from the SUBJECT
    and the responder HEADERS only"* — it never sees a sender and must never read body prose. A
    delivery report names itself in its subject, so a subject-only question is enough there, and
    respecting that contract matters more than the extra certainty a sender check would add: the
    gate function is also recomputed by Layer 2 from the stored payload, and a rule that read
    something L2 does not have would drift between the two.

    Everywhere else, use `is_delivery_status`, which also requires the daemon sender.
    """
    return bool(_REPORT.search(text or ""))


def is_delivery_status(*, sender: str, subject: str = "", text: str = "") -> bool:
    """Both conditions: a delivery daemon sent it, and it reads like a delivery report."""
    if not _DAEMON.search(sender or ""):
        return False
    return bool(_REPORT.search(subject or "") or _REPORT.search(text or ""))


def read_delivery_status(*, sender: str, subject: str = "",
                         text: str = "") -> DeliveryStatus | None:
    """A delivery report, or `None` when this is not one.

    `None` means *not a delivery status notification* — the caller then treats the event exactly
    as it did before this module existed. It never means "a delivery report we are unsure about";
    that is `UNKNOWN`, which is a recognised report with an unstated outcome.
    """
    if not is_delivery_status(sender=sender, subject=subject, text=text):
        return None

    body = f"{subject or ''}\n{text or ''}"
    # Delay is asked first on purpose: a delay notice contains "delivery incomplete", which a
    # looser failure pattern would read as permanent. Getting this order wrong tells a founder
    # their pitch bounced while Gmail is still delivering it.
    if _DELAY_MARKERS.search(body):
        kind = DELAYED
    elif _FAILED_MARKERS.search(body):
        kind = FAILED
    else:
        kind = UNKNOWN

    match = _FINAL_RECIPIENT.search(text or "") or _RECIPIENT.search(body)
    recipient = match.group(1) if match else None
    return DeliveryStatus(kind=kind, recipient=recipient, reason=_reason(body))


def _reason(body: str) -> str | None:
    """The report's own headline, for the evidence span. Gmail wraps it in `** … **`."""
    match = re.search(r"\*\*\s*(.+?)\s*\*\*", body)
    return match.group(1).strip() if match else None
