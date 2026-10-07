"""STEP-10 · a delivery report's attached original is not a document — the connector leaves it out.

    GENIOS_TEST_DATABASE_URL=… pytest tests/capture/test_a_bounces_original_is_not_a_document.py -q

`capture/connectors/composio.ComposioGmailConnector._to_objects` (tree `yc2_w27_s10 ·
M29.C3.L-data.V0.U05`, `06` D38). A delivery report carries the mail that bounced. Production's
shape is RFC 6522's `multipart/report`: the daemon's words, often a `message/delivery-status`
part, and the original as `message/rfc822` — or its headers alone, `text/rfc822-headers`. The
connector minted each named part as an `email_attachment` event of its own, which the gate parked
as a DOC-02 "unsupported" stub for review — our own pitch, filed as a document — and walked into
the original, so a deck on the pitch would become a document a mail daemon sent. Now, when the
message is a report by the gate's own question (`gate/rules.is_a_delivery_report` — its sender,
its subject, its body else its snippet), those three parts mint no attachment event and the
original is not walked into; the report's own words are still its body, for the parser. The parts
are recognised by MIME type, never by filename. Any other message — a person forwarding a bounce
with the `.eml` attached, a daemon's mail that is not a report — keeps every attachment exactly as
before.
"""
from __future__ import annotations

import base64

import pytest

from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.delivery_status import read_delivery_status
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.gate.rules import is_a_delivery_report

DAEMON = "Mail Delivery Subsystem <mailer-daemon@googlemail.com>"
REPORT_SUBJECT = "Delivery Status Notification (Failure)"
#: Production's words (`tests/capture/test_delivery_failure.py`).
REPORT_TEXT = ("** Address not found **\n\nYour message wasn't delivered to madison@afore.vc "
               "because the address couldn't be found or is unable to receive email.\n\n"
               "Learn more here: https://support.google.com/mail/?p=NoSuchUser")
#: The same words without Gmail's headline: only the SUBJECT names the report.
UNNAMED_TEXT = ("Your message wasn't delivered to madison@afore.vc because the address couldn't be "
                "found or is unable to receive email.")
STATUS = ("Reporting-MTA: dns; googlemail.com\n\nFinal-Recipient: rfc822; madison@afore.vc\n"
          "Action: failed\nStatus: 5.1.1\n")
PITCH = "Hi Madison,\n\nNimbus Labs is raising a seed round. Could we find 20 minutes?\n\nArjun"
DECK = "Nimbus-Labs-deck.pdf"
EML = "Nimbus Labs - raising our seed round.eml"


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _text(words: str) -> dict:
    return {"mimeType": "text/plain", "filename": "", "body": {"data": _b64(words)}}


def _original(*, named: bool, mime: str = "message/rfc822") -> dict:
    """The mail that bounced, as Gmail nests it in the report: the pitch, and its deck."""
    if mime == "text/rfc822-headers":
        return {"mimeType": mime, "filename": "headers.txt" if named else "",
                "body": {"attachmentId": "hdr1", "size": 900}}
    return {"mimeType": mime, "filename": EML if named else "",
            "body": {"attachmentId": "orig1", "size": 48000},
            "parts": [
                {"mimeType": "multipart/alternative", "filename": "", "body": {"size": 0},
                 "parts": [_text(PITCH),
                           {"mimeType": "text/html", "filename": "",
                            "body": {"data": _b64(f"<p>{PITCH}</p>")}}]},
                {"mimeType": "application/pdf", "filename": DECK,
                 "body": {"attachmentId": "deck1", "size": 45000}}]}


def _status(*, named: bool) -> dict:
    return {"mimeType": "message/delivery-status", "filename": "details.txt" if named else "",
            "body": {"data": _b64(STATUS), "size": len(STATUS)}}


def _message(sender: str, subject: str, parts: list, *, mid: str = "m-bounce",
             kind: str = "multipart/report", **fields) -> dict:
    """A Gmail API message: the envelope as headers, the MIME tree under `payload`. A report
    carries Gmail's `Auto-Submitted: auto-replied`; a person's mail does not."""
    headers = [{"name": "From", "value": sender}, {"name": "To", "value": "arjun@nimbuslabs.test"},
               {"name": "Subject", "value": subject}]
    if kind == "multipart/report":
        headers.append({"name": "Auto-Submitted", "value": "auto-replied"})
    return {"id": mid, "threadId": "t-bounce", "labelIds": ["INBOX"],
            "messageTimestamp": "2026-08-11T06:00:20+00:00",
            "payload": {"mimeType": kind, "parts": parts, "headers": headers}, **fields}


def _report(*, named: bool = True, original: str = "message/rfc822",
            with_status: bool = True) -> dict:
    """Production's report: the daemon's words + (often) the status + the original."""
    return _message(DAEMON, REPORT_SUBJECT,
                    [_text(REPORT_TEXT)] + ([_status(named=named)] if with_status else [])
                    + [_original(named=named, mime=original)])


class _Gmail(ComposioGmailConnector):
    """The production connector with its network a dict. Every attachment download is recorded:
    a deck fetched out of the original is a document about to be minted."""

    def __init__(self, full: dict | None = None, *, relevance=None) -> None:
        self._ocr = None
        self._relevance = relevance
        self._account = None
        self._full = full or {}
        self.downloads: list[str] = []

    def _full_message(self, mid):
        return self._full

    def _attachment_bytes(self, mid, attachment_id, file_name=None):
        self.downloads.append(file_name or attachment_id or "")
        return b"%PDF-1.7 the deck"


def _attachments(objs) -> list[str]:
    return [o.raw["subject"] for o in objs if o.object_type == "email_attachment"]


# ── a report: its email, and no attachment ─────────────────────────────────────────────────────

@pytest.mark.parametrize("with_status", [True, False], ids=["and-a-status-part", "no-status-part"])
@pytest.mark.parametrize("original", ["message/rfc822", "text/rfc822-headers"])
@pytest.mark.parametrize("named", [True, False], ids=["parts-named", "parts-unnamed"])
def test_a_report_yields_its_email_and_no_attachment(named, original, with_status):
    conn = _Gmail()
    objs = conn._to_objects(_report(named=named, original=original, with_status=with_status))
    assert [o.object_type for o in objs] == ["email_message"]
    assert conn.downloads == [], "a part of the original was fetched"
    assert objs[0].raw["has_attachment"] is False


def test_the_reports_own_words_still_reach_the_parser():
    email = _Gmail()._to_objects(_report())[0]
    assert email.raw["body"] == REPORT_TEXT
    status = read_delivery_status(sender=email.actor_email, subject=email.raw["subject"],
                                  text=email.raw["body"])
    assert status is not None and status.failed and status.recipient == "madison@afore.vc"
    # …and the gate reads as a report exactly the mail the connector left the original out of.
    assert is_a_delivery_report(email.raw, sender_email=email.actor_email)


def test_the_original_is_never_walked_into_for_its_words():
    """A report whose own words are HTML alone: walked into, the pitch's text/plain — the first
    plain part in the tree — became the report's body, and the parser read our pitch."""
    report = _message(DAEMON, REPORT_SUBJECT, [
        {"mimeType": "text/html", "filename": "",
         "body": {"data": _b64(f"<p>{REPORT_TEXT}</p>")}},
        _original(named=False)])
    email = _Gmail()._to_objects(report)[0]
    assert "Nimbus Labs is raising" not in email.raw["body"]
    assert "wasn't delivered to madison@afore.vc" in email.raw["body"]


@pytest.mark.parametrize("subject, parts, fields", [
    # Gmail's words without their headline: only the subject names the report.
    (REPORT_SUBJECT, [_text(UNNAMED_TEXT)], {}),
    # A subject and a provider snippet that name nothing: only the daemon's own words do — read
    # BEFORE the snippet, as the gate reads them.
    ("Returned mail", [_text(REPORT_TEXT)],
     {"snippet": "This is the mail system at host relay.acme.test."}),
    # A list entry whose parts carry no text: only the snippet does — the gate's fallback.
    ("Returned mail", [{"mimeType": "text/plain", "filename": "", "body": {"size": 0}}],
     {"snippet": "Message not delivered: madison@afore.vc does not exist."}),
], ids=["named-in-its-subject", "named-in-its-body", "named-in-its-snippet"])
def test_a_report_is_recognised_on_each_of_the_gates_three_inputs(subject, parts, fields):
    report = _message(DAEMON, subject, parts + [_status(named=True), _original(named=True)],
                      **fields)
    conn = _Gmail()
    objs = conn._to_objects(report)
    assert _attachments(objs) == [] and conn.downloads == []
    assert is_a_delivery_report(objs[0].raw, sender_email=objs[0].actor_email)


@pytest.mark.parametrize("part", [
    {"mimeType": "message/rfc822", "filename": DECK, "body": {"attachmentId": "orig1"}},
    {"mimeType": "Message/RFC822", "filename": EML, "body": {"attachmentId": "orig1"}},
    {"mimeType": "Message/Delivery-Status", "filename": "details.txt",
     "body": {"data": _b64(STATUS)}},
    {"mimeType": "TEXT/RFC822-HEADERS", "filename": "headers.txt", "body": {"attachmentId": "h1"}},
], ids=["named-like-a-deck", "type-in-capitals", "status-in-capitals", "headers-in-capitals"])
def test_the_parts_are_recognised_by_their_type_not_their_name(part):
    """A part's name is the mailer's choice and its type is the standard's (RFC 2045: the type is
    compared without regard to case)."""
    report = _message(DAEMON, REPORT_SUBJECT, [_text(REPORT_TEXT), part])
    assert _attachments(_Gmail()._to_objects(report)) == []


def test_a_report_keeps_a_part_that_is_none_of_the_three():
    """It is the three types that are left out, not a report's attachments: a file of any other
    type on a report is minted as before."""
    report = _message(DAEMON, REPORT_SUBJECT, [
        _text(REPORT_TEXT), _status(named=True), _original(named=True),
        {"mimeType": "application/pdf", "filename": "policy.pdf", "body": {"attachmentId": "p1"}}])
    conn = _Gmail()
    assert _attachments(conn._to_objects(report)) == ["policy.pdf"]
    assert conn.downloads == ["policy.pdf"]


# ── every door the connector has ───────────────────────────────────────────────────────────────

class _Junk:
    """The S2 filter, primed, calling everything confident junk — the fast path's worst case."""

    def __init__(self) -> None:
        self.primed: list = []

    def prime(self, objects):
        self.primed.extend(objects)

    def verdict_for(self, source_object_id):
        return RelevanceVerdict(relevant=False, relevance=0.05, disposition="drop")


@pytest.mark.parametrize("door", ["sweep", "fast-path", "light-pass", "webhook"])
def test_every_door_leaves_the_original_out(door):
    report = _report()
    if door == "sweep":                                  # the legacy full fetch (the golden runner)
        conn = _Gmail()
        objs = conn._to_batch({"data": {"messages": [report]}}).objects
    elif door == "fast-path":                            # production: list → prime → fetch keepers
        conn = _Gmail(report, relevance=_Junk())
        objs = conn._to_batch({"data": {"messages": [report]}}).objects
    elif door == "light-pass":
        conn = _Gmail()
        objs = conn._to_objects(report, fetch_full=False)
    else:
        conn = _Gmail()
        objs = list(conn.webhook_objects({"message": report}))
    assert [o.object_type for o in objs] == ["email_message"]
    assert conn.downloads == []


# ── any other message keeps every attachment ───────────────────────────────────────────────────

@pytest.mark.parametrize("named, expected", [
    (True, ["details.txt", DECK, EML]),
    (False, [DECK]),
], ids=["parts-named", "parts-unnamed"])
def test_a_persons_forward_keeps_every_attachment(named, expected):
    """The same parts on a person's mail — a colleague forwarding the bounce with the `.eml`
    attached — are that person's attachments, minted exactly as they always were."""
    forward = _message("Priya Shah <priya@acme.test>", f"Fwd: {REPORT_SUBJECT}",
                       [_text("Can you resend this one?"), _status(named=named),
                        _original(named=named)], mid="m-forward", kind="multipart/mixed")
    conn = _Gmail()
    objs = conn._to_objects(forward)
    assert _attachments(objs) == expected
    assert conn.downloads == [DECK]
    assert objs[0].raw["body"] == "Can you resend this one?"
    assert objs[0].raw["has_attachment"] is True


def test_a_daemons_mail_that_is_not_a_report_keeps_its_attachments():
    """Both conditions, never one: a delivery daemon's own notice is not a delivery report."""
    notice = _message("postmaster@acme.test", "Your mailbox is 95% full",
                      [_text("Please delete old mail."), _original(named=True)],
                      mid="m-notice", kind="multipart/mixed")
    assert _attachments(_Gmail()._to_objects(notice)) == [DECK, EML]
