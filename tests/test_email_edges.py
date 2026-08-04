from __future__ import annotations

import base64

from genios_engine.capture.connectors.composio import ComposioGmailConnector, _extract_emails

# These lock the DETERMINISTIC inputs to the email relationship graph + content completeness:
#   1. To/Cc capture (person↔person / person→company edges in L2)
#   2. FULL body from MIME parts (not a ~280-char snippet)
#   3. attachments/PDF → their own document event so their text reaches the graph
# See genios_engine/context/pipeline.py (edges + store-don't-delete) and this connector.


def _b64url(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _msg_with_parts():
    """A Gmail message shaped like the full-MIME payload: headers + a text body part + an
    attachment part with inline data (so the test needs no network / no composio client)."""
    return {
        "messageId": "m1",
        "threadId": "t1",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "Piyush Sharma <piyush@3one4capital.com>"},
                {"name": "To", "value": "Rohit <rohit@genios.ai>"},
                {"name": "Cc", "value": "partner@3one4capital.com, rohit@genios.ai"},
                {"name": "Subject", "value": "Our deck"},
            ],
            "parts": [
                {"mimeType": "text/plain",
                 "body": {"data": _b64url(
                     "Hi Rohit, sharing our deck. We think it's slightly early, "
                     "we'll wait this round out and re-engage once you have traction.")}},
                {"filename": "deck.txt", "mimeType": "text/plain",
                 "body": {"attachmentId": "att1",
                          "data": _b64url("Valuation ask: 20cr. Stage: Series A. Sector: SaaS.")}},
            ],
        },
    }


def test_extract_emails_handles_names_lists_and_dedups():
    got = _extract_emails("Rohit <rohit@genios.ai>, piyush@3one4capital.com",
                          None, ["a@b.com", "a@b.com"])
    assert got == ["rohit@genios.ai", "piyush@3one4capital.com", "a@b.com"]


def test_connector_captures_full_body_recipients_and_attachment():
    c = ComposioGmailConnector(api_key="x", user_id="u")
    objs = c._to_objects(_msg_with_parts())

    # 1) email + its one attachment
    assert len(objs) == 2
    email, att = objs[0], objs[1]

    # 2) email: FULL body (not a snippet), recipients, has_attachment flag
    assert email.object_type == "email_message"
    assert email.actor_email == "piyush@3one4capital.com"
    assert "wait this round out" in email.raw["body"]        # full body, not 280-char stub
    assert email.raw["to"] == ["rohit@genios.ai"]
    assert email.raw["cc"] == ["partner@3one4capital.com", "rohit@genios.ai"]
    assert email.raw["has_attachment"] is True

    # 3) attachment: its own document event carrying extracted text, linked to the email
    assert att.object_type == "email_attachment"
    assert att.parent_object_id == "m1"
    assert att.actor_email == "piyush@3one4capital.com"       # facts attach to the sender
    assert "20cr" in att.raw["body"] and "Series A" in att.raw["body"]


def test_company_domain_skips_personal_and_malformed():
    # imported here (not at top) so the connector tests above still run where sqlalchemy is absent
    from genios_engine.context.pipeline import _company_domain
    assert _company_domain("piyush@3one4capital.com") == "3one4capital.com"
    assert _company_domain("someone@gmail.com") is None      # personal provider → no company
    assert _company_domain("not-an-email") is None
    assert _company_domain(None) is None
