"""STEP-07 · the connector's fast path never settles a known or brief-named sender from its list snippet.

    pytest tests/capture/test_the_fast_path_keeps_named_senders_whole.py -q

Tree `yc2_w27_s07 · M25.C4.L-logic.V2.U04`. On the onboarding backfill and `_sync_source` the Gmail
connector gates on the cheap LIST fields first: Promotions, Social and Spam labels and automated
senders are settled there and never fetched in full (`capture/connectors/composio.py`, `03` F58). The
gate then keeps a watchlisted portal's Promotions mail (W-07) or a known counterparty's (W-01) — and
reads its snippet. So a sender the resolver knows, or the brief names, is fetched whole. A stranger's
Promotions mail is still settled from the list, as before.
"""
from __future__ import annotations

from genios_engine.capture.connectors.composio import ComposioGmailConnector


def _message(mid: str, sender: str, labels):
    return {"messageId": mid, "sender": sender, "subject": f"subject {mid}",
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
            self.fetched.append(arguments["message_id"])
            return {"data": {**self._messages[arguments["message_id"]],
                             "messageText": f"the whole body of {arguments['message_id']}"}}
        raise AssertionError(slug)


class _Filter:
    """A primed classifier that calls everything confident junk; `keeps_whole` is the resolver's."""

    def __init__(self, known: set[str]):
        self.known = known

    def prime(self, objects):
        self.primed = [o.source_object_id for o in objects]

    def verdict_for(self, oid):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated")

    def keeps_whole(self, obj):
        return obj.actor_email in self.known


PROMO = ["INBOX", "CATEGORY_PROMOTIONS"]


def test_a_watchlisted_portal_on_promotions_is_fetched_whole():
    box = _Mailbox([_message("m_portal", "StartupSetu <updates@startupsetu.gov.test>", PROMO),
                    _message("m_shop", "Shop <deals@shop.test>", PROMO)],
                   _Filter({"updates@startupsetu.gov.test"}))
    batch = box.initial_snapshot()
    assert box.fetched == ["m_portal"], "the named sender is fetched in full; the shop is not"
    assert {o.source_object_id for o in batch.objects} == {"m_portal", "m_shop"}


def test_a_known_sender_the_filter_calls_junk_is_still_fetched_whole():
    box = _Mailbox([_message("m_vc", "Kiran <kiran@banyanseed.test>", ["INBOX"])],
                   _Filter({"kiran@banyanseed.test"}))
    box.initial_snapshot()
    assert box.fetched == ["m_vc"]


def test_without_a_resolver_the_fast_path_is_what_it_was():
    class _Plain(_Filter):
        keeps_whole = None

    box = _Mailbox([_message("m_portal", "StartupSetu <updates@startupsetu.gov.test>", PROMO)],
                   _Plain(set()))
    box.initial_snapshot()
    assert box.fetched == []
