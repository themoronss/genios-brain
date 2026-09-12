"""Availability — who is away, when, and who covers.

A leave email used to be the one message the capture gate threw away on its subject line alone,
and it is exactly the message team intelligence needs: "Anisha is on leave 15–22, her audit docs
are due on the 19th" is a risk nobody can see if the leave never reached the graph.

This is the boundary vocabulary only. Resolution (turning "kal se 3 din" into two dates) lives in
Layer 2, writing and reading the windows lives in `context/availability.py`, and the reasoners read
the derived `owner.*` facts. Nothing here imports above platform.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

#: The closed kind vocabulary. Closed on purpose: an open set lets a model invent a kind no reader
#: can map to a status, and the window is then stored and never consulted.
AVAILABILITY_KINDS: frozenset[str] = frozenset({"leave", "ooo", "sick", "travel", "busy", "partial"})

#: Kinds under which the person cannot act at all. `busy` / `partial` reduce capacity instead.
ABSENT_KINDS: frozenset[str] = frozenset({"leave", "ooo", "sick", "travel"})
REDUCED_KINDS: frozenset[str] = frozenset({"busy", "partial"})

#: Synonyms a model (or a calendar title) actually produces → the canonical kind.
KIND_SYNONYMS: dict[str, str] = {
    "leave": "leave", "on_leave": "leave", "vacation": "leave", "holiday": "leave",
    "holidays": "leave", "pto": "leave", "time_off": "leave", "annual_leave": "leave",
    "chutti": "leave", "off": "leave", "day_off": "leave",
    "ooo": "ooo", "out_of_office": "ooo", "away": "ooo", "auto_reply": "ooo",
    "sick": "sick", "sick_leave": "sick", "ill": "sick", "unwell": "sick", "medical": "sick",
    "travel": "travel", "travelling": "travel", "traveling": "travel", "trip": "travel",
    "business_trip": "travel", "offsite": "travel",
    "busy": "busy", "unavailable_partly": "partial",
    "partial": "partial", "limited": "partial", "reduced": "partial", "half_day": "partial",
}


def normalize_kind(value: object) -> str | None:
    """A kind token → the canonical kind, or None when it is not one we can reason over."""
    if not isinstance(value, str):
        return None
    token = value.strip().lower().replace("-", "_").replace(" ", "_")
    return KIND_SYNONYMS.get(token)


@dataclass(frozen=True, slots=True)
class AvailabilityClaim:
    """One validated availability window, ready to be written.

    `person` is None when the claim is about the message's own author ("I am out of office") — the
    writer resolves that to the sender rather than the model guessing a name. `from_date` is always
    set; `to_date` None means open-ended (an auto-reply that never says when it ends).

    `from_stated` records whether the start was STATED or defaulted to the message date. A
    defaulted start is honest ("as of this message they are away") but it is not a claim about when
    the absence began, and the writer must not let it move a window someone did state.
    """

    person: str | None
    kind: str
    from_date: date
    to_date: date | None
    coverage_person: str | None
    evidence: str
    from_stated: bool = True
    to_stated: bool = False

    def value(self) -> dict:
        """The stored fact value. Evidence is NOT part of it: two messages stating the same window
        in different words must compare equal (corroboration), not flip the fact."""
        return {"kind": self.kind, "from": self.from_date.isoformat(),
                "to": self.to_date.isoformat() if self.to_date else None,
                "cover": self.coverage_person}
