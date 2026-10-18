"""`03` F117 · on the connector's fast path a bounce is never judged on its list snippet.

    pytest tests/capture/connectors/test_a_bounce_is_read_whole_on_the_fast_path.py -q

`yc2_w27_s18` M49.C1.L-logic.V0.U02 (L1 Signals, `capture/connectors`), STEP-18 §8.3 s18-F5.

⛔ WHAT WAS WRONG. Since STEP-10 (`06` D38) the gate keeps a delivery report and reads it — the
failed address, the code and the original are in its BODY. On the connector's fast path a report was
still handed to the junk filter's batch like any mail (a call bought for a verdict the gate never asks),
its automated sender could settle it from the LIST fields alone, and a confident `drop` left it a
snippet — so the bounce parser read a body nobody fetched. A report is now asked for the way Layer 1
asks it (`capture/gate/rules.is_a_delivery_report`) and is never primed, never settled from the list,
never left a snippet.
"""
from __future__ import annotations

import base64

from genios_engine.capture.connectors.composio import ComposioGmailConnector

REPORT_BODY = ("Address not found. Your message wasn't delivered to ira@larkspurvc.test because the "
               "address couldn't be found. The response was: 550 5.1.1 The email account that you "
               "tried to reach does not exist.")


def _message(mid: str, sender: str, subject: str, labels):
    return {"messageId": mid, "sender": sender, "subject": subject,
            "messageText": f"snippet {mid}", "labelIds": labels,
            "messageTimestamp": "2026-09-24T05:20:00Z"}


class _Mailbox(ComposioGmailConnector):
    def __init__(self, messages, relevance):
        super().__init__(api_key="k", user_id="u", ocr=None, relevance=relevance)
        self._messages = {m["messageId"]: m for m in messages}
        self.fetched: list[str] = []

    def _execute(self, slug, arguments):
        if slug == "GMAIL_FETCH_EMAILS":
            return {"data": {"messages": list(self._messages.values())}}
        if slug == "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID":
            mid = arguments["message_id"]
            self.fetched.append(mid)
            body = REPORT_BODY if mid.startswith("m_bounce") else f"the whole body of {mid}"
            # The full message carries its text as a MIME part, as Gmail's does; the list entry
            # carries only the snippet.
            part = {"mimeType": "text/plain",
                    "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}}
            return {"data": {**self._messages[mid], "payload": part}}
        raise AssertionError(slug)


class _Filter:
    """A primed classifier that calls everything confident junk."""

    def __init__(self):
        self.primed: list[str] = []

    def prime(self, objects):
        self.primed = [o.source_object_id for o in objects]

    def verdict_for(self, oid):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated")

    keeps_whole = None


#: Gmail's own daemon: its automated sender settles it from the LIST fields (N-03) before any filter.
BOUNCE = _message("m_bounce", "Mail Delivery Subsystem <mailer-daemon@googlemail.com>",
                  "Delivery Status Notification (Failure)", ["INBOX"])
#: A domain's postmaster: no list rule settles it, so it went to the junk filter's batch.
POSTMASTER = _message("m_bounce_pm", "Postmaster <postmaster@larkspurvc.test>",
                      "Undelivered Mail Returned to Sender", ["INBOX"])
STRANGER = _message("m_shop", "Shop <deals@shop.test>", "Ten percent off", ["INBOX"])


def _sync(messages):
    junk = _Filter()
    box = _Mailbox(messages, junk)
    batch = box.initial_snapshot()
    return box, junk, {o.source_object_id: o for o in batch.objects}


def test_a_bounce_is_never_primed_for_the_junk_filter():
    _box, junk, _objects = _sync([POSTMASTER, STRANGER])
    assert "m_bounce_pm" not in junk.primed, "a verdict bought for a report the gate never judges"
    assert "m_shop" in junk.primed, "the control: a stranger's mail is still primed"


def test_a_postmasters_bounce_the_filter_calls_junk_is_fetched_whole():
    box, _junk, objects = _sync([POSTMASTER])
    assert box.fetched == ["m_bounce_pm"]
    assert "550 5.1.1" in objects["m_bounce_pm"].raw["body"]


def test_a_daemons_bounce_is_not_settled_from_its_list_fields():
    box, _junk, objects = _sync([BOUNCE, STRANGER])
    assert "m_bounce" in box.fetched
    assert "550 5.1.1" in objects["m_bounce"].raw["body"], "the parser reads the report's body"
    assert "m_shop" not in box.fetched, "the control: confident junk is still settled from the list"


def test_a_bounce_on_promotions_is_not_settled_from_its_labels():
    promo_bounce = {**BOUNCE, "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"]}
    box, _junk, _objects = _sync([promo_bounce])
    assert box.fetched == ["m_bounce"]
