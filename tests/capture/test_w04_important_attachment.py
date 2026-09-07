"""W-04 · a readable document attached is a reason not to blanket-drop the mail carrying it.

    pytest tests/capture/test_w04_important_attachment.py -q

`gate/rules.whitelist` has read `raw["important_attachment"]` since the gate was written, and
nothing in the engine ever set it. So the rung existed in the rule table, in the reason labels and
in the docs, and could not fire — a documented rule that is unreachable is the same as an absent
one and harder to notice.

It matters for one class of mail. `N-02/03/04` (unsubscribe headers, bulk precedence, automated
sender) already exempt a message that carries an attachment. `N-06/N-07` do not: they drop on
Gmail's own PROMOTIONS/SOCIAL classification regardless. In production that is 514 drops, and the
one that costs is a renewal notice from a vendor we have not met yet with the countersigned PDF
attached — the FILE survives (`attachment_overrides_junk` forces the full fetch and the attachment
lands as its own event with no labels on it), but the covering email, which is where the date and
the amount are stated, did not.

The rule stays narrow on purpose: only a part we could actually read counts, because a whitelist
skips every N-code and `invite.ics` would readmit the newsletter volume the prefilter exists to
refuse.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.rules import noise_rule, whitelist
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.contracts.source_event import Actor, SourceEvent

NOW = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _conn(ocr=None) -> ComposioGmailConnector:
    conn = ComposioGmailConnector.__new__(ComposioGmailConnector)   # skip __init__ (no network)
    conn._ocr = ocr
    return conn


def _message(parts: list[dict], *, labels: list[str] | None = None) -> dict:
    return {"id": "m_w04", "payload": {"parts": parts}, "from": "sales@newvendor.test",
            "subject": "Countersigned MSA + renewal terms",
            "labelIds": labels if labels is not None else ["CATEGORY_PROMOTIONS"]}


PDF_PART = {"mimeType": "application/pdf", "filename": "MSA-countersigned.pdf",
            "body": {"attachmentId": "a1"}}
ICS_PART = {"mimeType": "text/calendar", "filename": "invite.ics", "body": {"attachmentId": "a2"}}
BODY_PART = {"mimeType": "text/plain", "filename": "",
             "body": {"data": _b64("Attached is the countersigned MSA. Renewal is 28 March.")}}


def _email_object(conn, message):
    objs = conn._to_objects(message)
    return next(o for o in objs if o.object_type == "email_message")


# =============================================================================================
# The connector states it
# =============================================================================================
def test_a_readable_document_sets_the_flag(monkeypatch):
    conn = _conn()
    monkeypatch.setattr(conn, "_attachment_bytes", lambda *a, **k: b"%PDF-1.4 contract")
    email = _email_object(conn, _message([BODY_PART, PDF_PART]))
    assert email.raw["important_attachment"] is True


def test_a_calendar_invite_does_not(monkeypatch):
    """The narrow half of the rule. A whitelist skips EVERY N-code, so `invite.ics` — which every
    promotional webinar mail carries — would readmit exactly the volume the prefilter refuses."""
    conn = _conn()
    email = _email_object(conn, _message([BODY_PART, ICS_PART]))
    assert email.raw["important_attachment"] is False


def test_an_image_counts_only_when_ocr_is_wired(monkeypatch):
    """"Readable" is a fact about this deployment, not about the file: with no OCR engine a
    screenshot invoice is a review stub, and whitelisting the mail that carried it buys nothing."""
    part = {"mimeType": "image/png", "filename": "invoice-scan.png", "body": {"attachmentId": "a3"}}
    assert _email_object(_conn(), _message([BODY_PART, part])).raw["important_attachment"] is False

    class _Ocr:
        name = "fake"

        def ocr(self, path):                    # pragma: no cover - never called here
            raise AssertionError("the light pass must not OCR anything")

    conn = _conn(ocr=_Ocr())
    monkeypatch.setattr(conn, "_attachment_bytes", lambda *a, **k: b"")
    assert _email_object(conn, _message([BODY_PART, part])).raw["important_attachment"] is True


def test_a_message_with_no_attachment_states_false(monkeypatch):
    assert _email_object(_conn(), _message([BODY_PART])).raw["important_attachment"] is False


# =============================================================================================
# The gate honours it
# =============================================================================================
def _ctx(raw: dict) -> GateContext:
    """A gate context over one email, carrying only what the two rules under test read."""
    event = SourceEvent(
        event_id="evt_w04", org_id="org_w04", connection_id="con_w04", source="gmail",
        object_type="email_message", source_object_id="m_w04",
        dedup_key="gmail:email_message:m_w04",
        actor=Actor(type="external_contact", email="sales@newvendor.test"), occurred_at=NOW)
    return GateContext(event=event, raw=raw, prepared=None, sender_known=False)


def test_promotions_alone_still_drops():
    """The rule this exemption narrows must still work: Gmail's category with nothing attached is
    the 470-drop class, and it is the reason the prefilter is affordable."""
    raw = {"subject": "50% off", "body": "sale", "labelIds": ["CATEGORY_PROMOTIONS"],
           "has_attachment": False, "important_attachment": False}
    assert whitelist(_ctx(raw)) is None
    assert noise_rule(_ctx(raw)) == ("N-06", "drop")


def test_promotions_with_a_countersigned_contract_is_whitelisted():
    raw = {"subject": "Countersigned MSA", "body": "attached", "labelIds": ["CATEGORY_PROMOTIONS"],
           "has_attachment": True, "important_attachment": True}
    assert whitelist(_ctx(raw)) == "W-04"


def test_the_whole_path_keeps_the_covering_email(monkeypatch):
    """End to end through `capture_event`: the connector states the flag, the gate reads it, and
    the message that states the renewal date survives instead of being dropped on a label."""
    conn = _conn()
    monkeypatch.setattr(conn, "_attachment_bytes", lambda *a, **k: b"%PDF-1.4 contract")
    email = _email_object(conn, _message([BODY_PART, PDF_PART]))

    res = capture_event(email, org_id="org_w04", connection_id="con_w04",
                        repo=InMemorySourceEventRepository(), mailbox_owner="me@acme.io")
    assert res.outcome == "emitted", "a promotions-labelled contract mail was dropped anyway"
    assert [r.reason_code for r in res.trace.records if r.stage == "S1"] == [None]
