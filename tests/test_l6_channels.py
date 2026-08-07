"""Layer 5.2 Delivery channels — formatting is pure and invents nothing; send failures are results."""
from __future__ import annotations

from genios_engine.deliver.channels.base import ChannelResult, get_channel
from genios_engine.deliver.channels.slack import (format_card_message,
                                                  format_digest_message,
                                                  valid_webhook_url)

CARD = {"card_id": "crd_1", "headline": "Chat360 quiet 9 days",
        "situation": "Proposal sent, no inbound since Jul 28.",
        "urgency_band": "high", "score": 73}


def test_card_message_says_only_what_the_card_says():
    msg = format_card_message(CARD, base_url="https://app.genios.ai")
    text = str(msg)
    assert "Chat360 quiet 9 days" in text and "no inbound since Jul 28" in text
    assert "crd_1" in text                          # deep link back to the card
    assert msg["text"]                              # notification fallback present
    # nothing added beyond card fields + the link — no invented advice/names
    for word in ("recommend", "urgent!", "immediately"):
        assert word not in text.lower()


def test_message_is_deterministic():
    a = format_card_message(CARD, base_url="https://x")
    b = format_card_message(CARD, base_url="https://x")
    assert a == b


def test_digest_message_counts_never_estimates():
    msg = format_digest_message({"one_line": "2 open item(s), 1 high-band.",
                                 "top_items": [{"entity": "Chat360",
                                                "reason": "stalled_deal", "score": 73}]})
    text = str(msg)
    assert "2 open item(s)" in text and "Chat360" in text and "stalled deal" in text
    empty = format_digest_message({"one_line": "Nothing needs you right now."})
    assert "Nothing needs you" in str(empty)


def test_webhook_url_validation():
    assert valid_webhook_url("https://hooks.slack.com/services/T/B/x")
    assert not valid_webhook_url("https://evil.example.com/hook")   # SSRF guard
    assert not valid_webhook_url("")
    assert not valid_webhook_url(None)


def test_send_failure_is_a_result_not_an_exception():
    ch = get_channel("slack")
    res = ch.send({"text": "x"}, {"webhook_url": "https://evil.example.com/hook"})
    assert isinstance(res, ChannelResult) and not res.ok
    assert "webhook_url" in res.detail


def test_unknown_channel_returns_none():
    assert get_channel("carrier_pigeon") is None
