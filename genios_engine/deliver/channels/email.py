"""Email — the second human push channel, built against an injected transport (GeniOS-011 S37.U2).

Audit items `l5-delivery-only-in-app` and `l5-b3-email-delivery-channel-missing`: delivery was
pull-only. `get_channel` knew `slack` and `agent_push`, so `deliverable_channels` could never
contain `email`, and the kept morning brief (the digest payload) and every high-band card could
reach only a founder who had wired Slack. GeniOS-008 03-QUESTIONS B3 asks for email first.

WHAT THIS ADAPTER IS, AND IS NOT

  * It is a FORMAT and a SEND, like every channel (`base.py`): it never decides who, whether or
    when. Quiet hours and burst caps are the gate's, and they hold an email row because `email`
    is classed a chat channel (`executive/communication.CHAT_CHANNELS`), exactly as Slack is.
  * It has NO PROVIDER. Which provider (and which sending domain) is S37.U1, Rohit's decision, so
    the transport is an interface (`EmailTransport`) and `TRANSPORTS` — the provider registry — is
    EMPTY in production. An org whose `org_channels` row names a provider nobody has wired gets a
    failed result, never a network call. The channel is OFF until both exist: the org's row (the
    per-org setting) and a transport for the provider it names.

ONE RECIPIENT, AND IT IS THE ORG'S OWN

The address is the one `to` on the org's email row — the owner seat's address, which is what the
row is registered with (S37.U3). `EmailMessage` has no cc, no bcc and no second `to`, so there is
no field another person's address could be put in; a `to` that is anything but one plain address
(a list, a comma, a header smuggled after a CR/LF, a display name) is refused, not trimmed.

NEVER OTHER PEOPLE'S MAIL BODIES

The outbox stores, for every human channel, the chat formatter's payload (`outbox.enqueue_pending`
calls `slack.format_card_message`; the digest is `slack.format_digest_message` of the KEPT brief;
an executive reminder arrives as `executive_bridge.format_reminder`'s neutral dict). Those are the
card's own checked words — headline, situation, the abstention cause, the next move — and a link
back to the card. This adapter reads exactly those shapes, takes the Slack markup off, and adds no
word. A payload carrying ANY key a formatter does not write (a `body`, a `snippet`, an `html`, a
`to`) is refused before the transport is asked, so a mail body cannot ride out on this channel by
being put in a payload: there is no field here that would carry it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from typing import Protocol

from genios_engine.deliver.channels.base import ChannelResult


@dataclass(frozen=True)
class EmailMessage:
    """One plain-text mail to one person. Deliberately no cc, bcc or html: see the module header."""
    to: str
    subject: str
    text: str


class EmailTransport(Protocol):
    """What a provider (S37.U1) implements. A failure is a `ChannelResult`, or an exception the
    adapter turns into one — the outbox owns retry, never the transport."""

    def send(self, message: EmailMessage) -> ChannelResult: ...


#: The provider registry: `org_channels.config["provider"]` → a factory that builds the transport
#: from that org's config (so a sealed per-org credential is read by the provider, never here).
#: ⛔ EMPTY ON PURPOSE. No provider is chosen (S37.U1), and a registry entry is the only way an
#: email can leave; `tests/deliver/test_email_channel.py::test_production_ships_no_transport`
#: pins it, so wiring one is a deliberate edit.
TRANSPORTS: dict[str, Callable[[dict], EmailTransport]] = {}

#: One plain address and nothing else: no display name, no list, no whitespace.
_ADDRESS = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

#: The two keys `slack.format_card_message` / `format_digest_message` / `format_reminder_message`
#: write, and the one block shape they write.
_FORMATTED_KEYS = frozenset({"text", "blocks"})
_SECTION_KEYS = frozenset({"type", "text"})
_REMINDER_KINDS = frozenset({"execution_reminder", "execution_escalation"})

_SUBJECT_MAX = 150
_TEXT_MAX = 4000

_LINK = re.compile(r"<(https?://[^|>\s]+)\|([^>\n]*)>")
_BOLD = re.compile(r"\*([^*\n]+)\*")
_ITALIC_LINE = re.compile(r"^_(.+)_$")


class PayloadRefused(ValueError):
    """The payload is not one a formatter wrote, so it is not sent."""


def recipient(config: dict | None) -> str | None:
    """The one address this org's email row names, or None when it is not exactly one plain
    address. Never repaired: a `to` that needs trimming is a registration bug to surface."""
    to = (config or {}).get("to")
    if not isinstance(to, str) or not _ADDRESS.fullmatch(to):
        return None
    return to


def _reminder_keys() -> frozenset[str]:
    # Derived from the one writer rather than copied, so a field the bridge adds is not refused
    # here by a stale list — and a field it never writes still is.
    from genios_engine.deliver.executive_bridge import format_reminder
    return frozenset(format_reminder({}))


def _formatted(payload: dict, *, base_url: str) -> dict:
    """The payload as a chat formatter wrote it — or PayloadRefused."""
    if not isinstance(payload, dict):
        raise PayloadRefused("email sends only a formatter's payload")
    if payload.get("kind") in _REMINDER_KINDS and set(payload) <= _reminder_keys():
        # `executive_bridge._render` hands a non-Slack channel the neutral reminder. It is said
        # with the reminder wording rules that already exist, never a second copy of them.
        from genios_engine.deliver.channels.slack import format_reminder_message
        payload = format_reminder_message(payload, base_url=base_url)
    if not set(payload) <= _FORMATTED_KEYS or not isinstance(payload.get("text"), str):
        raise PayloadRefused("email sends only a formatter's payload")
    for block in payload.get("blocks") or ():
        inner = block.get("text") if isinstance(block, dict) else None
        if (not isinstance(block, dict) or set(block) != _SECTION_KEYS
                or block.get("type") != "section" or not isinstance(inner, dict)
                or inner.get("type") != "mrkdwn" or not isinstance(inner.get("text"), str)):
            raise PayloadRefused("email sends only a formatter's section blocks")
    return payload


def _plain(mrkdwn: str) -> str:
    """Slack mrkdwn → plain text: the same words, the markup taken off. A link keeps its label and
    shows its URL, because a plain-text mail cannot hide one behind a label."""
    lines = []
    for line in mrkdwn.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _LINK.sub(lambda m: f"{m.group(2).strip()} {m.group(1)}".strip(), line)
        line = _BOLD.sub(r"\1", line)
        italic = _ITALIC_LINE.match(line)
        if italic:
            line = italic.group(1)
        # `slack._escaped` escapes the digest's words for Slack; a mail says them as they were.
        lines.append(line.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").rstrip())
    return "\n".join(lines).strip()


def compose(payload: dict, *, to: str, base_url: str = "") -> EmailMessage:
    """Pure: a formatter's payload → one mail to `to`. Raises PayloadRefused for anything else."""
    formatted = _formatted(payload, base_url=base_url)
    # The subject is one line: every CR/LF (and any other run of whitespace) becomes one space, so
    # no word in a headline can start a second header.
    subject = " ".join(_plain(formatted["text"]).split())[:_SUBJECT_MAX]
    blocks = formatted.get("blocks") or ()
    body = "\n\n".join(_plain(b["text"]["text"]) for b in blocks) if blocks \
        else _plain(formatted["text"])
    return EmailMessage(to=to, subject=subject, text=body[:_TEXT_MAX])


def _scrubbed(detail: str, to: str) -> str:
    # `ChannelResult.detail` never includes the config, and a provider's error often quotes the
    # recipient back ("550 founder@… rejected").
    return detail.replace(to, "<recipient>")


def _wired_transport(config: dict) -> EmailTransport | None:
    provider = config.get("provider")
    factory = TRANSPORTS.get(provider) if isinstance(provider, str) else None
    return factory(config) if factory is not None else None


class EmailChannel:
    name = "email"

    def __init__(self, transport: EmailTransport | None = None) -> None:
        # Injected in tests; in production None, and the transport is found by the org's provider.
        self._transport = transport

    def send(self, payload: dict, config: dict) -> ChannelResult:
        cfg = config or {}
        to = recipient(cfg)
        if to is None:
            return ChannelResult(ok=False, detail="email needs exactly one plain recipient "
                                                  "address on the org's email row")
        try:
            message = compose(payload, to=to, base_url=str(cfg.get("base_url") or ""))
        except PayloadRefused as e:
            return ChannelResult(ok=False, detail=str(e))
        try:
            transport = self._transport or _wired_transport(cfg)
            if transport is None:
                return ChannelResult(ok=False, detail="email is off: no email transport is wired "
                                                      "for this org's provider (GeniOS-011 S37.U1)")
            res = transport.send(message)
        except Exception as e:      # noqa: BLE001 — failure is a result; the outbox owns retry
            return ChannelResult(ok=False,
                                 detail=_scrubbed(f"{type(e).__name__}: {str(e)[:160]}", to))
        if not isinstance(res, ChannelResult):
            return ChannelResult(ok=False, detail="email transport returned no result")
        return res if res.ok else ChannelResult(ok=False, detail=_scrubbed(res.detail, to))
