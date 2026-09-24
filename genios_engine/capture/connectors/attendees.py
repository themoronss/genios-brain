"""L1.2.x-U2/U3/U5 · CALENDAR PEOPLE AS PEOPLE — the keys P4's join needs, preserved not resolved.

Benchmark P4 asks *"for every external meeting, was there a follow-up email within 7 days?"*, and
that join needs `Manik` on a calendar invite and `Manik` in an email to be **joinable**.

⛔ **THE BOUNDARY, and §9 forbids crossing it:**

> Layer 2 owns **identity resolution** — deciding two mentions are one person.
> Layer 1 owns **preserving the keys that make resolution possible**, and never destroying them.

This module is entirely about the second sentence. It normalises an ADDRESS (lowercase, trim)
because that is a property of the string; it never decides that two different addresses are one
person. `keshav@rocketsdr.com` and `keshav@gmail.com` share a display name and are **two
identities** — the benchmark names that exact trap, and merging them here would put the graph back
inside the capture layer with less information than the layer that owns the question.

**WHAT WAS BEING THROWN AWAY.** `calendar.py` reads

    attendees = [a.get("email") for a in (ev.get("attendees") or []) if a.get("email")]

so an attendee is flattened to an address, and one **without** an address is dropped entirely. Two
things go with it:

* **the person** — a room, or an external guest invited by name, simply vanishes from the
  participant set. Dropping them decides for Layer 2, invisibly;
* **`responseStatus`** — the difference between *"we invited them"* and *"they came"*, and P4 asks
  about meetings that **happened**.

**MEETING KIND IS CHEAP AND THE PILOT PROVES IT.** Of 7 calendar events, **5 were cohort sessions**
where no follow-up is expected, so *"0 of 7 followed up"* is a true number and a misleading finding.
`calendar.py` already records what that costs, in its own words: *"a meeting cannot be told apart
from a broadcast, and 'send a recap' shipped on twenty-person cohort workshops the founder attended
as one participant."*

PURE: no clock, no I/O, no model. Deterministic first — §5 puts a model only on the remainder, and
the remainder is `UNKNOWN`, which is a real answer rather than a gap to fill.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

#: Above this many attendees a meeting is a session rather than a conversation. Twelve is the size
#: past which nobody expects a personal follow-up — it is a room, a cohort or an all-hands.
#:
#: A THRESHOLD FOR CLASSIFICATION, NOT A RULE ABOUT PEOPLE. It only ever produces `COHORT`, which
#: SUPPRESSES a follow-up expectation; it can never manufacture one. The direction matters: being
#: wrong here costs a missed nudge, and being wrong the other way costs a founder a recap email to
#: twenty strangers.
COHORT_ATTENDEE_COUNT = 12

#: Full scale for the joinability ratio. Integer basis points (V-7).
BP_FULL = 10_000


class MeetingKind(str, Enum):
    """What kind of meeting this was, for the one question P4 asks of it."""

    #: Somebody outside the tenant organised it, or it is small and mixed. A follow-up is expected.
    EXTERNAL = "external"
    #: Our own people. A follow-up email is not the evidence of anything.
    INTERNAL = "internal"
    #: A programme session, workshop or all-hands. **No follow-up is expected**, and counting it as
    #: a missed one is the misleading-finding case above.
    COHORT = "cohort"
    #: Cannot be told. Never guessed — see `read_meeting_kind`.
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Attendee:
    """One person on a calendar event, in the same key shape an email participant has.

    THE SHAPE IS THE POINT. If a calendar person and an email person do not share a key, Layer 2
    cannot join them and P4 stays blocked whatever else is built.
    """

    #: Normalised address — lowercased and trimmed, because `Manik@Acme.com` and `manik@acme.com`
    #: are the same STRING written twice, and that is a fact about text rather than about identity.
    email: str | None
    #: What the source called them. Kept even when there is an address: it is the only key a
    #: partial identity has, and L2 may want both.
    display_name: str | None
    #: `accepted` / `declined` / `tentative` / `needsAction`, verbatim from the provider. Not
    #: normalised into a vocabulary of ours — this is the provider's word and L2 can map it.
    response: str | None

    @property
    def is_partial(self) -> bool:
        """No address. **Kept rather than dropped**: a room booking or a guest invited by name is
        a real participant, and removing them makes the attendee list silently wrong."""
        return self.email is None


def _clean(value: object) -> str | None:
    """A string with something in it, or None. Never a blank masquerading as a value."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    return text or None


def read_attendees(raw: Iterable[object]) -> tuple[Attendee, ...]:
    """Provider attendee records into participants, **losing nobody**.

    An entry with neither an address nor a name is skipped — it names no one and there is nothing
    for Layer 2 to resolve. Everything else survives, including the address-less ones the current
    list comprehension in `calendar.py` drops on the floor.

    Order is preserved and duplicates are NOT collapsed: two entries for one address is something
    the provider said, and de-duplicating it here would hide a malformed invite behind a tidy list.
    """
    people: list[Attendee] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        email = _clean(entry.get("email"))
        name = _clean(entry.get("displayName")) or _clean(entry.get("display_name"))
        if email is None and name is None:
            continue
        people.append(Attendee(
            email=email.lower() if email else None,
            display_name=name,
            response=_clean(entry.get("responseStatus")) or _clean(entry.get("response_status"))))
    return tuple(people)


def read_meeting_kind(*, attendee_count: int, organiser_domain: str | None,
                      owner_domain: str | None, is_recurring: bool) -> MeetingKind:
    """Classify a meeting deterministically, or say `UNKNOWN`.

    THE ORDER IS THE DESIGN, and it was CORRECTED once — the cohort rung used to sit below the
    domain check, so a twenty-person recurring session with no identifiable owner came back
    `UNKNOWN` and would have been chased for a recap. Caught by
    `test_meeting_kind_reaches_the_raw_payload`.

    1. **Large, or large-and-recurring** → `COHORT`. **It needs no domains at all**: twenty people
       on a recurring invite is a session whoever organised it. It goes first for that reason, and
       because it is the only rung that can only ever SUPPRESS an expectation — being wrong here
       costs a missed nudge, and being wrong the other way costs a founder a recap email to twenty
       strangers.
    2. **Cannot tell whose meeting it is** → `UNKNOWN`. Without both domains there is nothing to
       compare, and guessing EXTERNAL would put a follow-up on a meeting that may not warrant one
       while guessing INTERNAL would hide a real one. Neither is recoverable by a reader.
    3. **Organised from our own domain** → `INTERNAL`.
    4. **Otherwise** → `EXTERNAL`, which is the case P4 is actually about.

    §5 puts a model on "the remainder". The remainder is rung 2, and it answers `UNKNOWN` — a real
    answer rather than a gap a model should be paid to fill. If a measurement later shows `UNKNOWN`
    dominating, that is the evidence for adding one; there is no such measurement yet.
    """
    if attendee_count >= COHORT_ATTENDEE_COUNT:
        return MeetingKind.COHORT
    organiser = (organiser_domain or "").strip().lower()
    owner = (owner_domain or "").strip().lower()
    if not organiser or not owner:
        return MeetingKind.UNKNOWN
    if organiser == owner:
        return MeetingKind.INTERNAL
    return MeetingKind.EXTERNAL


def joinability_bp(*, attendee_emails: Iterable[str],
                   email_side_emails: Iterable[str]) -> int:
    """13-U5 · what share of calendar attendees have an email-side counterpart key.

    **Without this, P4's answer is unfalsifiable.** *"No follow-up found"* could mean no follow-up
    happened, or that the two sides were never joinable at all — and those have opposite fixes.
    It is Gemini's 18-of-18 with a different denominator.

    Zero attendees reports 0, not a perfect join: an empty calendar is nothing to join, and
    reporting 10000 would make it look like flawless coverage. Read it beside the attendee count.
    """
    attendees = {e.strip().lower() for e in attendee_emails if e and e.strip()}
    if not attendees:
        return 0
    known = {e.strip().lower() for e in email_side_emails if e and e.strip()}
    return len(attendees & known) * BP_FULL // len(attendees)


def attendee_emails(people: Sequence[Attendee]) -> tuple[str, ...]:
    """Just the addresses, for a caller that wants the old flat shape — `calendar.py`'s
    `recipients` keeps meaning exactly what it meant, and the richer list travels beside it."""
    return tuple(p.email for p in people if p.email)


__all__ = ["BP_FULL", "COHORT_ATTENDEE_COUNT", "Attendee", "MeetingKind", "attendee_emails",
           "joinability_bp", "read_attendees", "read_meeting_kind"]
