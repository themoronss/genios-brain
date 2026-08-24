"""Layer 5.2 · Phase 2 — the Delivery Context Resolver (responsibility 1).

Reads an **expiring seat lease**: is the recipient active, on which surface, in focus/meeting mode,
inside a busy window? The single most important property is that stale context *expires* rather
than becoming permanent truth — a "do not disturb" set at 14:00 and never cleared must not silence
someone at 20:00. So every read is judged against ``now`` and an ``expires_at``; past the lease,
the context is simply absent and the delivery falls back to its durable pull surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.contracts.validators import require_aware, require_identifier


@dataclass(frozen=True, slots=True)
class PresenceContext:
    """One seat's live delivery context, valid only until ``expires_at``."""

    seat_id: str
    expires_at: datetime
    active: bool = False
    current_surface: str | None = None     # e.g. 'slack', 'in_app' — where they are right now
    focus: bool = False                    # focus / do-not-disturb
    busy_until: datetime | None = None     # in a meeting until this instant

    def __post_init__(self) -> None:
        s = object.__setattr__
        s(self, "seat_id", require_identifier(self.seat_id, "seat id"))
        s(self, "expires_at", require_aware(self.expires_at, "expires_at"))
        if self.current_surface is not None:
            s(self, "current_surface", require_identifier(self.current_surface, "current surface"))
        if self.busy_until is not None:
            s(self, "busy_until", require_aware(self.busy_until, "busy_until"))

    def is_live(self, now: datetime) -> bool:
        """Is this lease still valid at ``now``? Past it, the context is absent, not sticky."""
        return require_aware(now, "now") < self.expires_at

    def interruptible(self, now: datetime) -> bool:
        """May an intrusive push break through right now?

        False under focus mode, inside a busy window, or once the lease has expired (we do not
        know they are free, so we do not assume it). Note: this removes the *interruption*, not
        the delivery — law 4/3 still land the work on a durable surface.
        """
        if not self.is_live(now):
            return False
        if self.focus:
            return False
        if self.busy_until is not None and require_aware(now, "now") < self.busy_until:
            return False
        return True

    def surface(self, now: datetime) -> str | None:
        """The surface the recipient is actually on, or None if the lease has lapsed."""
        if not self.is_live(now) or not self.active:
            return None
        return self.current_surface


#: An absent lease — the safe default when no context row exists for a seat. Not interruptible on
#: an active surface (we know nothing), so high/critical work still reaches the pull surface.
def absent(seat_id: str, now: datetime) -> PresenceContext:
    """A minimal already-expired context so callers can treat 'no lease' uniformly."""
    return PresenceContext(seat_id=seat_id, expires_at=now, active=False)


__all__ = ["PresenceContext", "absent"]
