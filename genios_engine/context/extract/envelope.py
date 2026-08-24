"""The message envelope — who sent this, to whom, and which side we are on.

The extraction prompt used to receive a bare body. With no From, no To and no direction, an
outbound sentence and an inbound one are indistinguishable, so "as requested, here is the demo"
— written BY the account owner — was extracted as `demo_requested` and filed on the sender,
producing a card that told a founder to book a demo with his own product's invite address.

Direction is not something to infer from tone. It is a fact the mail provider already gave us,
and every layer above depends on it: an observation without an actor cannot say who asked for
what, and a rule keyed on "whose turn is it" cannot be right more often than the direction is.
"""
from __future__ import annotations

from dataclasses import dataclass

INBOUND = "inbound"
OUTBOUND = "outbound"
UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Envelope:
    """Trusted routing metadata, kept separate from the untrusted body.

    Trusted here means "came from the provider's headers, not from text a stranger wrote". The
    prompt states that distinction explicitly, because a body that claims to be from someone
    must never be able to reassign a message's direction.
    """

    sender: str = ""
    recipients: tuple[str, ...] = ()
    self_identities: frozenset[str] = frozenset()

    @property
    def direction(self) -> str:
        """inbound (they wrote to us) · outbound (we wrote to them) · unknown.

        `unknown` is a real answer and must stay one: when the tenant's own identities are not
        known, claiming a direction would be a guess dressed as metadata. Every self-filter in
        L2 was a no-op for exactly this reason — `org_seats` was empty, so the "us" set was
        empty, so everything looked inbound from a stranger.
        """
        if not self.self_identities:
            return UNKNOWN
        if self.sender and _norm(self.sender) in self.self_identities:
            return OUTBOUND
        if self.sender:
            return INBOUND
        return UNKNOWN

    @property
    def counterparties(self) -> tuple[str, ...]:
        """Everyone on the message who is not us, in envelope order.

        On an outbound message these are the recipients; on an inbound one, the sender plus any
        other recipients. Either way it answers "who is this exchange actually with", which is
        the question the business subject is resolved from.
        """
        seen: list[str] = []
        for addr in (self.sender, *self.recipients):
            n = _norm(addr)
            if n and n not in self.self_identities and n not in seen:
                seen.append(n)
        return tuple(seen)

    def as_prompt_fields(self) -> dict[str, str]:
        """The four envelope lines the prompt renders."""
        return {
            "direction": self.direction,
            "sender": self.sender or "(unknown)",
            "recipients": ", ".join(self.recipients) or "(unknown)",
            "self_identity": ", ".join(sorted(self.self_identities)) or "(unknown — do not "
                                                                       "assume a direction)",
        }


def _norm(addr: str | None) -> str:
    return (addr or "").strip().lower()


def envelope_from_raw(raw: dict | None, self_identities: frozenset[str] | set[str] | None,
                      *, sender: str | None = None) -> Envelope:
    """Build an envelope from a connector's raw object.

    Recipient extraction is best-effort by design: connectors differ, and a missing To list must
    degrade the envelope rather than fail the extraction. What must NOT degrade silently is the
    self-identity set — an empty one yields `direction=unknown`, which the prompt is told to
    treat as "do not assume".
    """
    raw = raw or {}
    to = raw.get("to") or raw.get("recipients") or []
    cc = raw.get("cc") or []
    if isinstance(to, str):
        to = [to]
    if isinstance(cc, str):
        cc = [cc]
    recipients = tuple(_norm(a) for a in [*to, *cc] if _norm(a))
    return Envelope(
        sender=_norm(sender if sender is not None else raw.get("from") or raw.get("sender")),
        recipients=recipients,
        self_identities=frozenset(_norm(a) for a in (self_identities or ()) if _norm(a)),
    )
