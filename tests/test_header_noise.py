from __future__ import annotations

import base64

from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event

# The gate's N-01 (Auto-Submitted), N-02 (List-Unsubscribe) and N-04 (Precedence) noise rules read
# raw["headers"] — but the Gmail connector never built that dict, so on real Gmail those three rules
# were DEAD: bulk/automated mail slipped L1, hit L2's LLM, and only THEN got classified as noise (a
# wasted LLM call reaching no situation). The connector now surfaces the noise headers so the rules
# actually fire at L1, before any LLM spend.


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _email(headers: dict, *, sender: str = "person@realco.com",
           body: str = "Here is the weekly digest of product updates and news."):
    hlist = [{"name": k, "value": v} for k, v in headers.items()] + [{"name": "From", "value": sender}]
    m = {"id": "h1", "from": sender, "subject": "Digest",
         "payload": {"headers": hlist,
                     "parts": [{"mimeType": "text/plain", "filename": "",
                                "body": {"data": _b64(body)}}]}}
    conn = ComposioGmailConnector.__new__(ComposioGmailConnector)
    conn._ocr = None
    return conn._to_raw(m)


def _outcome(raw) -> str:
    return capture_event(raw, org_id="o", connection_id="c",
                         repo=InMemorySourceEventRepository()).outcome


def test_connector_now_surfaces_noise_headers():
    raw = _email({"List-Unsubscribe": "<mailto:u@x.com>"})
    assert raw.raw.get("headers", {}).get("List-Unsubscribe")   # was absent before → the rule was dead


def test_list_unsubscribe_now_drops_at_l1():
    assert _outcome(_email({"List-Unsubscribe": "<mailto:u@x.com>"})) == "dropped"


def test_auto_submitted_drops_at_l1():
    assert _outcome(_email({"Auto-Submitted": "auto-replied"})) == "dropped"


def test_precedence_bulk_drops_at_l1():
    assert _outcome(_email({"Precedence": "bulk"})) == "dropped"


def test_list_id_mailing_list_drops_at_l1():
    assert _outcome(_email({"List-Id": "<news.acme.com>"})) == "dropped"


def test_clean_business_mail_is_untouched():
    # real sender, no noise headers, a genuine request → must still reach L2
    raw = _email({}, sender="priya@acme.io", body="Can we meet Friday to discuss the proposal?")
    assert _outcome(raw) != "dropped"


def test_bulk_with_attachment_still_survives():
    # a noreply/bulk mail that carries a real file (invoice) is NOT dropped — relevance/L2 decides
    raw = _email({"List-Unsubscribe": "<mailto:u@x.com>"})
    raw.raw["has_attachment"] = True
    assert _outcome(raw) != "dropped"
