"""Layer 5.2 · Phase 2 — the Audience Resolver (responsibility 2).

Resolves the *current* recipient (owner / manager / admin / a specific registered agent) and then
permits only a seat that is (a) currently active — a frozen former manager cannot receive — and
(b) whose verified identity may view the evidence's inherited source ACL. An unrelated admin
cannot bypass that ACL just by being an admin. No authorised seat means fail-closed, not an
arbitrary fallback (routing law 7).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from genios_engine.contracts.execution import AudienceClass
from genios_engine.executive.assignment import SeatDirectory


@dataclass(frozen=True, slots=True)
class ResolvedRecipient:
    """The seat (or agent) this delivery may actually reach, with the reason it was chosen."""

    recipient: str | None            # seat id / agent id; None = fail-closed, no lawful recipient
    audience: AudienceClass
    reason_code: str

    @property
    def authorized(self) -> bool:
        return self.recipient is not None


def resolve_recipient(*, recipient: str | None, audience: AudienceClass,
                      directory: SeatDirectory,
                      can_view: Callable[[str], bool]) -> ResolvedRecipient:
    """Resolve + ACL-gate one recipient.

    ``can_view(seat_id)`` is the visibility predicate the orchestrator builds from the evidence's
    source ACL and the seat's verified email — kept as an injected callable so this resolver stays
    pure and unit-testable. Agents are resolved by identity here; their transport auth
    (scoped key / signed push) is enforced at the send boundary, not by visibility email.
    """
    if audience is AudienceClass.AGENT:
        # A specific registered agent. Identity only; ACL email-view does not apply to a machine.
        if not recipient:
            return ResolvedRecipient(None, audience, "agent_unresolved")
        return ResolvedRecipient(recipient, audience, "agent_recipient")

    if audience is AudienceClass.ADMIN_QUEUE:
        # Nobody could be resolved upstream; this is the visible unrouted queue, not a person.
        return ResolvedRecipient(None, audience, "admin_queue")

    seat = directory.active_seat(recipient)
    if seat is None:
        # Frozen / departed / never-active seat — no current person to receive.
        return ResolvedRecipient(None, audience, "recipient_inactive")

    if not can_view(seat):
        # The seat is real and active but not permitted to see this evidence. Fail closed rather
        # than escalate to an admin who is equally unauthorised.
        return ResolvedRecipient(None, audience, "acl_denied")

    return ResolvedRecipient(seat, audience, "resolved")


__all__ = ["ResolvedRecipient", "resolve_recipient"]
