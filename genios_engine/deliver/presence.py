"""Live delivery context reported by GeniOS surfaces.

Calendar data is not enough to know what a person is doing: a meeting may have ended early and
an IDE focus session may not exist on a calendar at all. Browser, desktop, mobile and agent
surfaces therefore publish a short-lived presence row. Expiry is mandatory, so a crashed client
can make delivery briefly conservative but can never leave a recipient "busy" forever.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from genios_engine.contracts.validators import require_aware, require_bool, require_identifier


PRESENCE_VERSION = "presence.v1"


class ActivityKind(str, Enum):
    IDLE = "idle"
    EMAIL = "email"
    CRM = "crm"
    CODING = "coding"
    MEETING = "meeting"
    PRESENTING = "presenting"
    FOCUS = "focus"
    MOBILE = "mobile"
    UNKNOWN = "unknown"


BUSY_ACTIVITIES = frozenset({
    ActivityKind.CODING,
    ActivityKind.MEETING,
    ActivityKind.PRESENTING,
    ActivityKind.FOCUS,
})


@dataclass(frozen=True, slots=True)
class Presence:
    org_id: str
    seat_id: str
    activity: ActivityKind
    surface: str
    focus_mode: bool
    observed_at: datetime
    expires_at: datetime
    busy_until: datetime | None = None

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "seat_id", require_identifier(self.seat_id, "seat id"))
        try:
            activity = (self.activity if isinstance(self.activity, ActivityKind)
                        else ActivityKind(self.activity))
        except ValueError as exc:
            raise ValueError(f"unknown activity {self.activity!r}") from exc
        setattr_(self, "activity", activity)
        setattr_(self, "surface", require_identifier(self.surface, "surface"))
        setattr_(self, "focus_mode", require_bool(self.focus_mode, "focus mode"))
        observed = require_aware(self.observed_at, "observed_at")
        expires = require_aware(self.expires_at, "expires_at")
        if expires <= observed:
            raise ValueError("presence expires_at must be after observed_at")
        setattr_(self, "observed_at", observed)
        setattr_(self, "expires_at", expires)
        if self.busy_until is not None:
            setattr_(self, "busy_until", require_aware(self.busy_until, "busy_until"))

    def active_at(self, now: datetime) -> bool:
        moment = require_aware(now, "now")
        return self.observed_at <= moment < self.expires_at

    def effective_busy_until(self, now: datetime) -> datetime | None:
        """The conservative hold window, bounded by the presence TTL."""
        moment = require_aware(now, "now")
        if not self.active_at(moment):
            return None
        explicit = self.busy_until if self.busy_until and self.busy_until > moment else None
        if explicit is not None:
            return min(explicit, self.expires_at)
        return self.expires_at if (self.focus_mode or self.activity in BUSY_ACTIVITIES) else None

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"schema_version": PRESENCE_VERSION, "org_id": self.org_id,
                "seat_id": self.seat_id, "activity": self.activity.value,
                "surface": self.surface, "focus_mode": self.focus_mode,
                "observed_at": self.observed_at, "expires_at": self.expires_at,
                "busy_until": self.busy_until}


def presence_from_row(row: Mapping[str, Any]) -> Presence:
    return Presence(
        org_id=str(row["org_id"]), seat_id=str(row["seat_id"]),
        activity=ActivityKind(str(row.get("activity") or ActivityKind.UNKNOWN.value)),
        surface=str(row.get("surface") or "unknown"),
        focus_mode=bool(row.get("focus_mode")), observed_at=row["observed_at"],
        expires_at=row["expires_at"], busy_until=row.get("busy_until"))


__all__ = ["ActivityKind", "BUSY_ACTIVITIES", "PRESENCE_VERSION", "Presence",
           "presence_from_row"]
