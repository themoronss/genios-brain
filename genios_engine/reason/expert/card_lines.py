"""The lines code writes for a file's card — why now, what remains, who and what the file is, its window (STEP-14).

`speedrun008/YC-II W27/` STEP-14 §8.4 item 5, tree `yc2_w27_s14` M43.C2.L-logic.V0.U02 (s14-F6, s14-F9; `03` F64,
F179). The gold card's middle was empty on all 39 golden cards: why now 0/39, what remains 0/39, the role 0/39; a
bare domain as the subject on 21; the window the 7-day default on 20 (every move with no date). These lines are
CODE's — no model writes them — so a file's card has the same shape whichever model reviewed it. Pure over the
dossier's parts (`reason/expert/dossier.DossierParts`), the review and its triggers (`reason/expert/triggers`):

  WHY NOW       the first trigger that says something to you, as a sentence — a new touch by who wrote and the
                day, a meeting closing in by its title and its days away, a quiet past the file's own pattern in
                days, your asking. Never "first look" and never an id: a file never judged (or reviewed again only
                because a version moved) is looked at now because of the newest thing on it;
  WHAT REMAINS  each of the file's open asks, ours and theirs, by who asked, what, and since when;
  SUBJECT/ROLE  the file's counterparty PERSON — the last of its people to write to us, else a person its numbers
                name — and its company, the file's counterparty as the file holds it; the brief's kind of work and
                its role. Never a bare domain where a person is named (`03` F64);
  WINDOW        the move's own date, else the playbook stage's prior for the stage the review names, else the
                file's measured reply time, else seven days — each labelled by where it came from (`03` F179).

Written at review time from the dossier the review was written against and kept beside its check
(`expert_reviews.card_lines`, 0221), so a decision and a replay read them without the dossier.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# ── where a window came from — closed. One name to a line (`tests/test_no_missing_module_deps`). ─────────────
MOVE_DATE = "move_date"
STAGE_PRIOR = "stage_prior"
REPLY_TIME = "reply_time"
DEFAULT = "default"
WINDOW_FROM: tuple[str, ...] = (MOVE_DATE, STAGE_PRIOR, REPLY_TIME, DEFAULT)
#: How each source is said beside the window.
WINDOW_SAID: Mapping[str, str] = {
    MOVE_DATE: "the move's own date",
    STAGE_PRIOR: "the playbook's prior for this stage — not measured here",
    REPLY_TIME: "how long this file's people take to reply, measured here",
    DEFAULT: "a default — nothing on the file sets it",
}
#: A move with no date, no stage, and a file with no pattern: a week, said to be a default.
DEFAULT_WINDOW_DAYS = 7

#: The open asks' kinds as a sentence names them (`context/waiting._ASK_KINDS`), closed; any other kind is said by
#: its own words.
ASK_SAID: Mapping[str, str] = {
    "question": "a question", "meeting_request": "a meeting", "proposal_sent": "a proposal",
    "demo_requested": "a demo", "contract_requested": "a contract", "next_step_agreed": "the agreed next step",
    "approval_requested": "an approval", "information_requested": "information",
    "intro_requested": "an introduction", "investor_update_sent": "an investor update",
}


def day(at: datetime | None) -> str:
    """A day as a card says it — "11 Aug"."""
    if at is None:
        return ""
    at = at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return f"{at.day} {at.strftime('%b')}"


def _n(value: float) -> str:
    return f"{value:g}"


@dataclass(frozen=True, slots=True)
class CardLines:
    """What code writes for a file's card. None or empty: the file holds nothing for that line."""
    why_now: str | None
    what_remains: tuple[str, ...]
    subject: str
    company: str | None
    kind_of_work: str | None
    role: str | None
    window_days: int
    window_from: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "what_remains", tuple(self.what_remains))
        if self.window_from not in WINDOW_FROM:
            raise ValueError(f"a window comes from one of {WINDOW_FROM}, not {self.window_from!r}")
        if isinstance(self.window_days, bool) or not isinstance(self.window_days, int) or self.window_days < 1:
            raise ValueError("a window is at least a day")
        if not str(self.subject or "").strip():
            raise ValueError("a card names its subject")

    @property
    def window_said(self) -> str:
        return WINDOW_SAID[self.window_from]

    def as_mapping(self) -> dict[str, Any]:
        return {"why_now": self.why_now, "what_remains": list(self.what_remains), "subject": self.subject,
                "company": self.company, "kind_of_work": self.kind_of_work, "role": self.role,
                "window": {"days": self.window_days, "from": self.window_from}}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CardLines":
        if not isinstance(raw, Mapping):
            raise ValueError("card lines are an object")
        window = raw.get("window") or {}
        return cls(why_now=raw.get("why_now") or None, what_remains=tuple(raw.get("what_remains") or ()),
                   subject=str(raw.get("subject") or ""), company=raw.get("company") or None,
                   kind_of_work=raw.get("kind_of_work") or None, role=raw.get("role") or None,
                   window_days=window.get("days"), window_from=str(window.get("from") or ""))


# ── who the file is ─────────────────────────────────────────────────────────────────────────────────────────
def _names(parts) -> dict[str, str]:
    """The file's people by node, as its numbers name them."""
    people = parts.numbers.people if parts.numbers is not None else ()
    return {p.node_id: p.name for p in people if p.name}


def _the_connector(parts, who: str | None) -> bool:
    """Whether `who` is the connector that introduced this file — never its person (STEP-14, found re-recording F03:
    the connector's nudges sit on the introduced person's file). A connector's own file is the connector's."""
    f = parts.file
    key = str(getattr(f, "introduced_by", None) or "").casefold()
    if not key or getattr(f, "kind", None) == "connector" or not who:
        return False
    who = str(who).casefold()
    return who == key or ("@" not in key and who.rsplit("@", 1)[-1] == key)


def _person(parts) -> str | None:
    """The file's counterparty PERSON: the last of its people to write to us — never the connector that introduced
    them — else one its numbers name."""
    for t in reversed(parts.timeline.touches):
        if t.direction == "in" and t.who_name and not _the_connector(parts, t.who):
            return t.who_name
    names = _names(parts)
    return names[sorted(names)[0]] if names else None


def _trigger(t: Any) -> tuple[str, str]:
    if isinstance(t, Mapping):
        return str(t.get("kind") or ""), str(t.get("says") or "")
    if isinstance(t, (tuple, list)):
        return str(t[0]), str(t[1])
    return str(getattr(t, "kind", "")), str(getattr(t, "says", ""))


def _touch_said(parts, touch) -> str:
    company = parts.file.counterparty
    if touch.direction == "out":
        return f"You wrote to {company} on {day(touch.at)}"
    if touch.direction == "meeting":
        title = parts.meeting_titles.get(touch.event_id)
        return (f"Your meeting “{title}” was held on {day(touch.at)}" if title
                else f"You met {touch.who_name or company} on {day(touch.at)}")
    return f"{touch.who_name or company} wrote on {day(touch.at)}"


def _newest(parts) -> str | None:
    touches = parts.timeline.touches
    return _touch_said(parts, touches[-1]) if touches else None


def _new_touch(parts, says: str) -> str | None:
    ids = {w.strip(" ,.:") for w in says.split()}
    if any(i.startswith("answer:") for i in ids):
        return "You answered its question"
    seen = [t for t in parts.timeline.touches if t.event_id in ids]
    return _touch_said(parts, seen[-1]) if seen else None


def _closing_in(parts, says: str) -> str | None:
    from .fingerprint import nearest_due

    if says.startswith("the next meeting") and parts.timeline.upcoming:
        meeting = parts.timeline.upcoming[0]
        away = max(0, math.floor((meeting.at - parts.as_of).total_seconds() / 86400))
        title = parts.meeting_titles.get(meeting.event_id)
        what = f"Your meeting “{title}”" if title else f"Your meeting with {meeting.who_name or parts.file.counterparty}"
        return f"{what} is in {away} day{'s' if away != 1 else ''}, on {day(meeting.at)}"
    due = nearest_due(parts)
    if says.startswith("the nearest promised date") and due is not None:
        away = math.floor((due - parts.as_of).total_seconds() / 86400)
        return (f"A promised date, {day(due)}, is {away} day{'s' if away != 1 else ''} away" if away >= 0
                else f"A promised date, {day(due)}, has passed")
    return None


def _quiet(parts, kind: str, says: str) -> str | None:
    from .triggers import our_usual, their_usual

    quiet = parts.timeline.days_quiet
    if quiet is None:
        return None
    days = math.floor(quiet)
    if kind == "reply_overdue":
        usual = their_usual(parts)
        return (f"{_person(parts) or parts.file.counterparty} has not replied in {days} days"
                + (f" — past the {_n(usual)} days they usually take" if usual is not None else ""))
    if says.startswith("our move"):
        ours = our_usual(parts)
        return f"Your reply is {days} days due" + (f" — past the {_n(ours)} days you usually take"
                                                   if ours is not None else "")
    longest = parts.timeline.longest_gap_days
    return f"Nothing in {days} days" + (f" — longer than this file has gone quiet before ({_n(longest)} days)"
                                        if longest is not None else "")


def _why_now(parts, triggers: Iterable[Any]) -> str | None:
    for t in triggers:
        kind, says = _trigger(t)
        said = None
        if kind == "new_evidence":
            said = _new_touch(parts, says)
        elif kind == "date_closing_in":
            said = _closing_in(parts, says)
        elif kind in ("reply_overdue", "past_normal"):
            said = _quiet(parts, kind, says)
        elif kind == "founder_asked":
            said = "You asked about it"
        if said:
            return said
    # A first look, a version that moved, nothing that said anything: the newest thing on the file.
    return _newest(parts)


def _what_remains(parts) -> tuple[str, ...]:
    names = _names(parts)
    out = []
    for a in parts.file.open_asks:
        who = names.get(a.asked_by) or parts.file.counterparty
        thing = ASK_SAID.get(a.kind, a.kind.replace("_", " "))
        since = f" since {day(a.opened_at)}" if a.opened_at is not None else ""
        if a.owed_by == "us":
            asked = f"asked {thing}" if thing.startswith(("a question", "the ")) else f"asked for {thing}"
            out.append(f"{who} {asked} — waiting on you{since}")
        else:
            out.append(f"{thing[:1].upper()}{thing[1:]} — waiting on {who}{since}")
    return tuple(out)


def _window(parts, review) -> tuple[int, str]:
    from .triggers import their_usual

    move = getattr(review, "next_move", None) if review is not None else None
    if move is not None and move.by_when is not None:
        return max(1, min(365, (move.by_when - parts.as_of.date()).days)), MOVE_DATE
    stage = getattr(getattr(review, "expected_vs_actual", None), "stage", None) if review is not None else None
    pb = getattr(parts.playbook, "playbook", None)
    prior = next((s.typical.value for s in (pb.stages if pb is not None else ()) if s.name == stage), None) \
        if stage else None
    if prior:
        return max(1, math.ceil(prior)), STAGE_PRIOR
    usual = their_usual(parts)
    if usual is not None and usual > 0:
        return max(1, math.ceil(usual)), REPLY_TIME
    return DEFAULT_WINDOW_DAYS, DEFAULT


def card_lines(parts, review, triggers: Iterable[Any] = ()) -> CardLines:
    """The lines a file's card shows beside the review's own words (see the module docstring)."""
    f = parts.file
    days, source = _window(parts, review)
    return CardLines(why_now=_why_now(parts, tuple(triggers)), what_remains=_what_remains(parts),
                     subject=_person(parts) or f.counterparty, company=f.counterparty or None,
                     kind_of_work=f.work_kind, role=f.kind, window_days=days, window_from=source)


__all__ = ["ASK_SAID", "CardLines", "DEFAULT", "DEFAULT_WINDOW_DAYS", "MOVE_DATE", "REPLY_TIME", "STAGE_PRIOR",
           "WINDOW_FROM", "WINDOW_SAID", "card_lines", "day"]
