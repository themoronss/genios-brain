"""What every team pass reads once per run, and the template helpers they share."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from genios_engine.context.availability import AvailabilityWindow
from genios_engine.context.correlation_people import (CommitmentLink, PeopleDirectory, Person,
                                                      commitment_links, load_directory,
                                                      org_visible_windows)

#: Commitments due within this many days are checked against their owner's absence (P-10).
DEADLINE_HORIZON_DAYS = 30


def digest(*parts) -> str:
    return hashlib.sha256(json.dumps(list(parts), default=str, separators=(",", ":"))
                          .encode()).hexdigest()[:32]


def day(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def span(w: AvailabilityWindow) -> str:
    """`15–22 Sep`, `28 Sep–3 Oct`, `from 15 Sep` (open-ended)."""
    if w.end is None:
        return f"from {day(w.start)}"
    if (w.start.year, w.start.month) == (w.end.year, w.end.month):
        return f"{w.start.day}–{day(w.end)}"
    return f"{day(w.start)}–{day(w.end)}"


def window_evidence(person: Person, w: AvailabilityWindow) -> dict:
    """An absence as evidence: WHO and WHEN only — never the kind's reason (sick/leave) or text."""
    return {"kind": "availability", "person": person.label, "seat_id": person.seat_id,
            "from": w.start.isoformat(), "to": w.effective_end.isoformat(), "status": "away"}


@dataclass(frozen=True)
class Situation:
    """One team situation for `emit_situation`."""
    key: str
    seat_id: str
    capability_id: str
    subject_node_ids: tuple[str, ...]
    headline: str
    body: str
    actions: tuple[dict, ...]
    evidence: tuple[dict, ...]
    digest: str
    expires_at: datetime
    ttl_seconds: int = 4 * 3600
    priority: str = "high"


@dataclass
class TeamContext:
    org_id: str
    now: datetime
    directory: PeopleDirectory
    links: list[CommitmentLink]
    windows: list[AvailabilityWindow] = field(default_factory=list)

    @property
    def today(self) -> date:
        return self.now.date()

    @classmethod
    def load(cls, conn, org_id: str, *, now: datetime,
             horizon_days: int = DEADLINE_HORIZON_DAYS) -> "TeamContext":
        directory = load_directory(conn, org_id)
        today = now.date()
        return cls(org_id=org_id, now=now, directory=directory,
                   links=commitment_links(conn, org_id, directory),
                   windows=org_visible_windows(conn, org_id, today,
                                               today + timedelta(days=horizon_days)))

    def windows_of(self, person: Person | None) -> list[AvailabilityWindow]:
        return sorted(self.directory.windows_of(person, self.windows), key=lambda w: w.start)

    def seat_away(self, seat_id: str, start: date, end: date) -> list[AvailabilityWindow]:
        return [w for w in self.windows_of(self.directory.for_seat(seat_id))
                if w.overlaps(start, end)]


__all__ = ["DEADLINE_HORIZON_DAYS", "Situation", "TeamContext", "day", "digest", "span",
           "window_evidence"]
