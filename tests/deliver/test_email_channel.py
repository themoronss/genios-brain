"""GeniOS-011 S37.U2 — the email channel adapter, against a fake transport.

Audit items `l5-delivery-only-in-app` and `l5-b3-email-delivery-channel-missing`: the channel
registry knew `slack` and `agent_push` and nothing else, so `deliverable_channels` could never
contain `email` and the kept morning brief could reach nobody who had no Slack.

What these tests pin, in the order DONE WHEN states it:

  * `get_channel('email')` returns an adapter, so `deliverable_channels` can contain `email`;
  * the digest and a high-band card are sent to the ONE address the org's email row names (the
    owner seat's), and to nobody else — the message type has no cc/bcc field to fill;
  * the words are the formatter's words and nothing more — a payload carrying anything a
    formatter does not produce (a mail body, a snippet) is refused before the transport is asked;
  * it is OFF until a provider is wired (S37.U1 is Rohit's choice): no transport → a failed
    result, never a network call;
  * it is gated by quiet hours exactly as Slack is, because it is classed as a chat channel.

No network, no provider: every send goes to `FakeTransport`.
"""
from __future__ import annotations

import dataclasses

import pytest

from genios_engine.deliver.channels import email as E
from genios_engine.deliver.channels.base import ChannelResult
from genios_engine.deliver.channels.base import get_channel
from genios_engine.deliver.channels.slack import format_card_message
from genios_engine.deliver.channels.slack import format_digest_message

OWNER = "founder@acme.io"
CONFIG = {"provider": "fake", "to": OWNER}


class FakeTransport:
    """Records what it was handed; returns what it is told to."""

    def __init__(self, result: ChannelResult | None = None, raises: Exception | None = None):
        self.sent: list[E.EmailMessage] = []
        self._result = result or ChannelResult(ok=True)
        self._raises = raises

    def send(self, message):
        self.sent.append(message)
        if self._raises is not None:
            raise self._raises
        return self._result


def _card(**over) -> dict:
    card = {"card_id": "k_1", "headline": "Acme renewal stalls past Friday",
            "situation": "Dana has not replied since the pricing call on Monday.",
            "urgency_band": "high", "score": 78, "level": "act"}
    card.update(over)
    return card


# ── registered, and deliverable ─────────────────────────────────────────────────────────────────

def test_get_channel_knows_email():
    ch = get_channel("email")
    assert ch is not None and ch.name == "email"
    assert isinstance(ch, E.EmailChannel)


def test_the_implemented_set_now_contains_email():
    from genios_engine.deliver.units import _implemented_channels
    assert "email" in _implemented_channels()


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _Conn:
    """Answers `deliverable_channels`'s one select with the org's registered channels."""

    def __init__(self, registered):
        self.registered = registered

    def execute(self, *_a, **_k):
        return _Rows([(ch,) for ch in self.registered])


def test_deliverable_channels_can_contain_email():
    from genios_engine.deliver.outbox import deliverable_channels
    assert deliverable_channels(_Conn(["email", "in_app"]), "org_x") == ["email"]


# ── the card and the digest reach the owner address ───────────────────────────────────────────

def test_a_high_band_card_is_sent_to_the_owner_address_in_its_own_words():
    fake = FakeTransport()
    payload = format_card_message(_card(), base_url="https://app.genios.test")
    res = E.EmailChannel(transport=fake).send(payload, CONFIG)
    assert res.ok, res.detail
    assert len(fake.sent) == 1
    msg = fake.sent[0]
    assert msg.to == OWNER
    assert "Acme renewal stalls past Friday" in msg.subject
    assert "Acme renewal stalls past Friday" in msg.text
    assert "Dana has not replied since the pricing call on Monday." in msg.text
    assert "https://app.genios.test/cards/k_1" in msg.text
    # Slack markup is taken off, not carried into a plain-text mail.
    assert "*" not in msg.text and "<http" not in msg.text and "|Open" not in msg.text


def test_the_digest_is_sent_as_the_kept_brief_and_unescaped():
    fake = FakeTransport()
    payload = format_digest_message({"one_line": "Two things need you today.",
                                     "top_items": [{"line": "Reply to Dana & Lee <pricing>"},
                                                   {"line": "Sign the Acme order form"}]})
    res = E.EmailChannel(transport=fake).send(payload, CONFIG)
    assert res.ok, res.detail
    msg = fake.sent[0]
    assert msg.to == OWNER
    assert "Morning brief" in msg.subject and "Two things need you today." in msg.subject
    assert "• Reply to Dana & Lee <pricing>" in msg.text
    assert "• Sign the Acme order form" in msg.text
    assert "&amp;" not in msg.text and "&lt;" not in msg.text


def test_a_reminder_from_the_executive_bridge_is_rendered_with_the_reminder_wording():
    """`executive_bridge._render` hands a non-Slack channel the channel-neutral reminder dict. The
    email adapter says it with the SAME wording rules the Slack adapter uses, never its own."""
    from genios_engine.deliver.executive_bridge import format_reminder
    neutral = format_reminder({"urgency": "firm", "card_id": "k_9",
                               "reason_code": "escalation_remind",
                               "facts": {"goal": "Send the Acme order form", "days_open": 4,
                                         "next_action": "Email the signed PDF",
                                         "consequence": "The deal slips past quarter end"}})
    fake = FakeTransport()
    res = E.EmailChannel(transport=fake).send(
        neutral, {**CONFIG, "base_url": "https://app.genios.test"})
    assert res.ok, res.detail
    msg = fake.sent[0]
    assert msg.subject.endswith("Still open — Send the Acme order form")
    assert "The deal slips past quarter end" in msg.text
    assert "Next: Email the signed PDF" in msg.text
    assert "https://app.genios.test/cards/k_9" in msg.text


# ── never other people's mail bodies ─────────────────────────────────────────────────────────

def test_a_field_on_the_card_row_that_is_not_a_checked_word_never_reaches_the_mail():
    secret = "Hi Dana, our internal floor is 40k, do not share"
    fake = FakeTransport()
    payload = format_card_message(_card(body=secret, snippet=secret, evidence=[secret]))
    E.EmailChannel(transport=fake).send(payload, CONFIG)
    assert secret not in fake.sent[0].text and secret not in fake.sent[0].subject


@pytest.mark.parametrize("extra", [{"body": "a mail body"}, {"snippet": "x"},
                                   {"html": "<p>x</p>"}, {"to": "someone@else.io"}])
def test_a_payload_carrying_more_than_a_formatter_produces_is_refused(extra):
    fake = FakeTransport()
    payload = {**format_card_message(_card()), **extra}
    res = E.EmailChannel(transport=fake).send(payload, CONFIG)
    assert res.ok is False
    assert fake.sent == []


def test_a_block_that_is_not_a_formatter_section_is_refused():
    fake = FakeTransport()
    payload = {"text": "x", "blocks": [{"type": "image", "image_url": "https://x"}]}
    res = E.EmailChannel(transport=fake).send(payload, CONFIG)
    assert res.ok is False and fake.sent == []


def test_the_message_has_one_recipient_and_no_copy_fields():
    assert {f.name for f in dataclasses.fields(E.EmailMessage)} == {"to", "subject", "text"}


@pytest.mark.parametrize("to", [None, "", "not-an-address", "a@x.io, b@y.io", "a@x.io;b@y.io",
                                ["a@x.io"], "a@x.io\r\nBcc: b@y.io", "Name <a@x.io>"])
def test_anything_but_one_plain_address_is_refused(to):
    fake = FakeTransport()
    res = E.EmailChannel(transport=fake).send(format_card_message(_card()),
                                              {**CONFIG, "to": to})
    assert res.ok is False and fake.sent == []


def test_cc_and_bcc_in_the_config_reach_no_one():
    fake = FakeTransport()
    E.EmailChannel(transport=fake).send(format_card_message(_card()),
                                        {**CONFIG, "cc": "x@y.io", "bcc": "z@y.io"})
    assert [m.to for m in fake.sent] == [OWNER]


def test_a_subject_cannot_carry_a_header():
    fake = FakeTransport()
    E.EmailChannel(transport=fake).send(
        format_card_message(_card(headline="Hello\r\nBcc: spy@evil.io")), CONFIG)
    assert "\r" not in fake.sent[0].subject and "\n" not in fake.sent[0].subject


# ── off until a provider is wired; failures are results ──────────────────────────────────────

def test_with_no_transport_wired_the_channel_is_off_and_sends_nothing(monkeypatch):
    monkeypatch.setattr(E, "TRANSPORTS", {})
    res = get_channel("email").send(format_card_message(_card()), CONFIG)
    assert res.ok is False and "transport" in res.detail


def test_with_no_provider_named_the_channel_is_off(monkeypatch):
    fake = FakeTransport()
    monkeypatch.setattr(E, "TRANSPORTS", {"fake": lambda cfg: fake})
    res = get_channel("email").send(format_card_message(_card()), {"to": OWNER})
    assert res.ok is False and fake.sent == []


def test_a_registered_transport_is_found_by_the_orgs_provider(monkeypatch):
    fake = FakeTransport()
    seen = []
    monkeypatch.setattr(E, "TRANSPORTS", {"fake": lambda cfg: seen.append(cfg) or fake})
    res = get_channel("email").send(format_card_message(_card()), CONFIG)
    assert res.ok, res.detail
    assert [m.to for m in fake.sent] == [OWNER]
    assert seen == [CONFIG]


def test_production_ships_no_transport():
    """S37.U1 (provider) is Rohit's decision; until it lands nothing can leave by email."""
    assert E.TRANSPORTS == {}


def test_a_transport_that_raises_is_a_failed_result_that_does_not_echo_the_config():
    fake = FakeTransport(raises=RuntimeError("smtp 421 try later"))
    res = E.EmailChannel(transport=fake).send(format_card_message(_card()), CONFIG)
    assert res.ok is False
    assert "RuntimeError" in res.detail and OWNER not in res.detail


def test_a_transport_failure_result_is_passed_through():
    fake = FakeTransport(result=ChannelResult(ok=False, detail="provider 503"))
    res = E.EmailChannel(transport=fake).send(format_card_message(_card()), CONFIG)
    assert res == ChannelResult(ok=False, detail="provider 503")


# ── quiet hours: gated as Slack is ───────────────────────────────────────────────────────────

def test_email_is_a_chat_channel_so_quiet_hours_hold_it():
    from genios_engine.contracts.delivery import INTRUSIVE_CHANNEL_CLASSES
    from genios_engine.contracts.execution import ChannelClass
    from genios_engine.deliver.gate import channel_class_for
    assert channel_class_for("email") is ChannelClass.CHAT
    assert channel_class_for("email") in INTRUSIVE_CHANNEL_CLASSES
