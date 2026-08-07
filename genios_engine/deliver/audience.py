"""Atlas audience resolution: execution ownership is a seed, not a final recipient."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Seat:
    seat_id: str
    role: str = "member"
    manager_seat_id: str | None = None
    active: bool = True
    email: str | None = None


@dataclass(frozen=True, slots=True)
class AudienceResolution:
    audience: str
    recipient: str | None
    reason_code: str


def resolve_audience(*, execution_owner: str | None, requested_audience: str = "owner",
                     seats: Sequence[Seat] = (), event_detail: Mapping | None = None,
                     agent_recipient: str | None = None) -> AudienceResolution:
    """Resolve the current recipient with deterministic, fail-safe fallbacks.

    Escalation targets are delivery intent, not blind authority: the target must still be active.
    Manager routing follows the current directory so a frozen plan cannot page an ex-manager.
    """
    active = {seat.seat_id: seat for seat in seats if seat.active}
    details = dict(event_detail or {})
    audience = str(details.get("target_audience") or requested_audience or "owner")
    if audience == "agent":
        return AudienceResolution(
            "agent", agent_recipient,
            "registered_agent" if agent_recipient else "agent_unavailable")

    owner = active.get(execution_owner or "")
    # Role audiences are resolved against the current directory. A frozen escalation target may
    # still be an active seat after a re-org, but that does not make an ex-manager the manager now.
    if audience == "manager" and owner and owner.manager_seat_id in active:
        return AudienceResolution("manager", owner.manager_seat_id,
                                  "current_owner_manager")
    if audience in {"owner", "team"} and owner:
        return AudienceResolution(audience, owner.seat_id, "active_execution_owner")

    requested = details.get("target_seat")
    # A frozen escalation target is never proof of a *current* reporting relationship. If the
    # manager edge disappeared, route through the live admin/owner fallbacks below even when the
    # former manager still has an active seat.
    if audience != "manager" and isinstance(requested, str) and requested in active:
        return AudienceResolution(audience, requested, "event_target_active")

    admins = sorted(seat.seat_id for seat in active.values() if seat.role == "admin")
    if admins:
        return AudienceResolution("admin_queue", admins[0], "active_admin_fallback")
    if owner:
        return AudienceResolution("owner", owner.seat_id, "active_owner_fallback")
    return AudienceResolution("admin_queue", None, "unresolved_admin_surface")


__all__ = ["AudienceResolution", "Seat", "resolve_audience"]
