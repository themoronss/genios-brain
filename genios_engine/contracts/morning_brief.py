"""The morning brief — what a chief of staff tells you at 8, as a contract (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4-§8.5, tree `yc2_w27_s15` M44.C1.L-contract.V0.U01. Four morning surfaces
existed and none read a file (`03` s15-F14); the summary ladder counted signals and said *"Nothing needs you
right now."* while the expert held a wait rule or an open question (s15-F2). The brief reads the day — every
file's checked judgment, the questions your files ask, your desk, your meetings, your promises, what changed —
and this module is what it is made of:

  * an ITEM is one thing of the day: its KIND (closed — `KINDS`), the file, meeting or promise it is ABOUT, who
    it is about as a name (never an address), the MATERIAL its words may use — the checked words by role, each
    number with the calculator that made it and its n, the dates, the names — and its SOURCES (closed kinds: a
    review, a question, a card, a mail, a meeting, a promise, a calculator, a mailbox's receipt, a line of the
    company brief). An item names at least one source: every line says where it came from (§5, restated);
  * a SECTION is where a line stands, closed and in the brief's order (`SECTIONS`), each CAPPED (`CAPS`).
    `desk` is the section §8.1's table and the case restatement (M44.C5.L-data.V1.U02: *"F55 your desk"*) put
    your last mail and who waits on you in; §8.5's list of sections left it out — it is here, between today's
    five and what changed;
  * a LINE is an item's words in a section — its id is its place in the day (org, seat, local date, section,
    item), so a mark on it means one thing — whose words they are (the template's or the writer's) and the
    check's verdict on a written line: KEPT, or GIVEN BACK its template words with the reason;
  * the BRIEF is one seat's morning: its org, seat, local date and timezone, the instant it was read as of, the
    one line, the lines in the sections' order, the items they came from, how it was written (the template,
    written, or escalated — and why), the model, tier and cost, what each section cut, the digest of the day's
    material — and its word budget: 600 words, three minutes at 200 a minute.

AN EMPTY MORNING is a brief with no line outside `changed`: nothing open, asked, due or watched. Only then does
it say so (s15-F2).

Frozen and pure: no I/O, no clock, no model. `as_mapping` is what is kept (`0230_morning_briefs`) and
`from_mapping` reads it back, equal to what was kept.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from genios_engine.platform.canonical import semantic_hash

BRIEF_VERSION = "morning_brief.v1"
#: Reading speed, and the budget it makes: three minutes.
WORDS_PER_MINUTE = 200
WORD_BUDGET = 600

# ── what an item is — closed. One name to a line: `tests/test_no_missing_module_deps` reads assignments. ──
DECISION = "decision"            # a file's checked move, decided on the live lane
QUESTION = "question"            # a question a file asks you
WATCHED = "watched"              # a file waiting on someone else, with the expert's wait rule
PROMISE = "promise"              # a promise of yours, due or overdue
MEETING = "meeting"              # a meeting of today or tomorrow, with its prep
NO_FOLLOW_UP = "no_follow_up"    # an external meeting with no mail of yours to anyone you met
DESK = "desk"                    # your desk: your last mail, and who waits on you
CHANGE = "change"                # what changed since your last brief
KINDS: tuple[str, ...] = (DECISION, QUESTION, WATCHED, PROMISE, MEETING, NO_FOLLOW_UP, DESK, CHANGE)

# ── where a line stands — closed, in the brief's order ────────────────────────────────────────────
TODAY = "today"
YOUR_DESK = "desk"
CHANGED = "changed"
STUCK = "stuck"
ASKED = "asked"
PROMISES = "promises"
MEETINGS = "meetings"
WATCHING = "watching"
SECTIONS: tuple[str, ...] = (TODAY, YOUR_DESK, CHANGED, STUCK, ASKED, PROMISES, MEETINGS, WATCHING)
#: How many lines a section may hold. Today's five is the brief's promise; the rest keep it inside three minutes.
CAPS: Mapping[str, int] = {TODAY: 5, YOUR_DESK: 1, CHANGED: 5, STUCK: 3, ASKED: 3, PROMISES: 5, MEETINGS: 6,
                           WATCHING: 3}
TITLES: Mapping[str, str] = {TODAY: "Today", YOUR_DESK: "Your desk", CHANGED: "Changed since your last brief",
                             STUCK: "Stuck", ASKED: "Your files ask you", PROMISES: "Your promises due",
                             MEETINGS: "Meetings", WATCHING: "Watching"}

# ── whose words a line is, and what the check said of a written one ──────────────────────────────
TEMPLATE = "template"
WRITER = "writer"
BY: tuple[str, ...] = (TEMPLATE, WRITER)
KEPT = "kept"
GIVEN_BACK = "given_back"
LINE_VERDICTS: tuple[str, ...] = (KEPT, GIVEN_BACK)

# ── how a brief was written ───────────────────────────────────────────────────────────────────────
TEMPLATE_BRIEF = "template"      # code's words: no model armed, or every model failed
WRITTEN = "written"              # the T1 writer, checked line by line
ESCALATED = "escalated"          # the T1 writer failed; T2 asked once, checked line by line
WRITTEN_BY: tuple[str, ...] = (TEMPLATE_BRIEF, WRITTEN, ESCALATED)

# ── where an item came from — closed ──────────────────────────────────────────────────────────────
SOURCE_REVIEW = "review"         # `<file>@<fingerprint>` — a checked review of `expert_reviews`
SOURCE_QUESTION = "question"     # a `founder_questions` id
SOURCE_CARD = "card"             # a card id
SOURCE_MAIL = "mail"             # a source event id
SOURCE_MEETING = "meeting"       # a meeting node id
SOURCE_PROMISE = "promise"       # a commitment node id
SOURCE_CALCULATOR = "calculator"  # the calculator that made a number
SOURCE_RECEIPT = "receipt"       # a mailbox's coverage receipt (its connection id)
SOURCE_BRIEF = "brief"           # a line of the company brief
SOURCE_KINDS: tuple[str, ...] = (SOURCE_REVIEW, SOURCE_QUESTION, SOURCE_CARD, SOURCE_MAIL, SOURCE_MEETING,
                                 SOURCE_PROMISE, SOURCE_CALCULATOR, SOURCE_RECEIPT, SOURCE_BRIEF)

#: An appraisal's levels (`contracts/expert_review.LEVELS`) and the lanes a decision is taken on.
LEVELS: tuple[str, ...] = ("low", "medium", "high")
LANES: tuple[str, ...] = ("live", "shadow")

_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _closed(value: Any, allowed: tuple[str, ...], name: str) -> str:
    if value not in allowed:
        raise ValueError(f"{name} is one of {allowed}, not {value!r}")
    return value


def _words(value: Any, name: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"a {name} says something: its words are empty")
    return text


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


def _instant(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def count_words(text: str | None) -> int:
    """Words as a reader counts them: runs of non-space."""
    return len(str(text or "").split())


@dataclass(frozen=True, slots=True)
class Source:
    """Where an item came from: a kind (closed) and its reference."""
    kind: str
    ref: str

    def __post_init__(self) -> None:
        _closed(self.kind, SOURCE_KINDS, "a source")
        if not str(self.ref or "").strip():
            raise ValueError("a source names its ref")

    def as_mapping(self) -> dict[str, str]:
        return {"kind": self.kind, "ref": self.ref}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Source":
        return cls(kind=raw.get("kind"), ref=str(raw.get("ref") or ""))


@dataclass(frozen=True, slots=True)
class Number:
    """A number a line may state — the words a reader may show (`contracts/measured.Measured.says`), its value
    and n, and the calculator that made it. A line never states a number its item does not hold."""
    name: str
    says: str
    value: float | None
    n: int
    calculator: str
    unit: str = ""

    def __post_init__(self) -> None:
        if not str(self.calculator or "").strip():
            raise ValueError("a number names the calculator that made it")
        if not str(self.says or "").strip():
            raise ValueError("a number says itself in words")
        if not isinstance(self.n, int) or self.n < 0:
            raise ValueError("a number's n is a count of what it rests on, never negative")

    def as_mapping(self) -> dict[str, Any]:
        return {"name": self.name, "says": self.says, "value": self.value, "n": self.n,
                "calculator": self.calculator, "unit": self.unit}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Number":
        return cls(name=str(raw.get("name") or ""), says=str(raw.get("says") or ""), value=raw.get("value"),
                   n=int(raw.get("n") or 0), calculator=str(raw.get("calculator") or ""),
                   unit=str(raw.get("unit") or ""))


@dataclass(frozen=True, slots=True)
class Material:
    """What a line's words may use, and nothing else: the checked words by role, the numbers, the dates (ISO)
    by role, the names."""
    words: tuple[tuple[str, str], ...] = ()
    numbers: tuple[Number, ...] = ()
    dates: tuple[tuple[str, str], ...] = ()
    names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "words", tuple((str(r), " ".join(str(w).split())) for r, w in self.words
                                                if str(w or "").strip()))
        object.__setattr__(self, "numbers", tuple(self.numbers))
        object.__setattr__(self, "dates", tuple((str(r), _iso(d)) for r, d in self.dates if d is not None))
        object.__setattr__(self, "names", tuple(dict.fromkeys(str(n).strip() for n in self.names
                                                              if str(n or "").strip())))

    def word(self, role: str) -> str | None:
        return next((w for r, w in self.words if r == role), None)

    def date(self, role: str) -> str | None:
        return next((d for r, d in self.dates if r == role), None)

    def number(self, name: str) -> Number | None:
        return next((n for n in self.numbers if n.name == name), None)

    def texts(self) -> tuple[str, ...]:
        """Every text the material holds — what a written line is checked against."""
        return (*(w for _r, w in self.words), *(n.says for n in self.numbers), *(d for _r, d in self.dates),
                *self.names)

    def as_mapping(self) -> dict[str, Any]:
        return {"words": [list(p) for p in self.words], "numbers": [n.as_mapping() for n in self.numbers],
                "dates": [list(p) for p in self.dates], "names": list(self.names)}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Material":
        return cls(words=tuple((r, w) for r, w in raw.get("words") or ()),
                   numbers=tuple(Number.from_mapping(n) for n in raw.get("numbers") or ()),
                   dates=tuple((r, d) for r, d in raw.get("dates") or ()),
                   names=tuple(raw.get("names") or ()))


def item_id_for(kind: str, about: str | None, key: str | None = None) -> str:
    """An item's id, from what it is — the same thing tomorrow is the same item, so a brief can say what is
    new today and what is gone."""
    return "bi_" + semantic_hash({"kind": kind, "about": about, "key": key})[:24]


@dataclass(frozen=True, slots=True)
class Item:
    """One thing of the day, with what its words may use and where it came from — and what orders it."""
    item_id: str
    kind: str
    about: str | None
    subject: str | None
    material: Material
    sources: tuple[Source, ...]
    mode: str | None = None              # the expert's mode, for a file's item
    stakes: str | None = None            # the appraisal's levels — the expert's judgment, mapped by code
    urgency: str | None = None
    at: datetime | None = None           # the instant it is about: due, start, asked, last mail
    quiet_days: float | None = None      # how long the file has been quiet
    our_move: bool = False               # the move is yours
    book_score_bp: int | None = None     # the book re-rank's score, for a carded decision
    card_id: str | None = None           # the card that shows it, when one is open
    lane: str | None = None              # live or shadow — the lane its decision was taken on

    def __post_init__(self) -> None:
        _closed(self.kind, KINDS, "an item's kind")
        object.__setattr__(self, "sources", tuple(self.sources))
        if not self.sources:
            raise ValueError("an item names at least one source: every line says where it came from")
        if self.subject is not None and _ADDRESS.search(self.subject):
            raise ValueError(f"an item is about a person or a company by name, never an address: {self.subject!r}")
        for name in ("stakes", "urgency"):
            if getattr(self, name) is not None:
                _closed(getattr(self, name), LEVELS, f"an item's {name}")
        if self.lane is not None:
            _closed(self.lane, LANES, "an item's lane")
        object.__setattr__(self, "at", _instant(self.at))

    def as_mapping(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "kind": self.kind, "about": self.about, "subject": self.subject,
                "material": self.material.as_mapping(), "sources": [s.as_mapping() for s in self.sources],
                "mode": self.mode, "stakes": self.stakes, "urgency": self.urgency, "at": _iso(self.at),
                "quiet_days": self.quiet_days, "our_move": self.our_move, "book_score_bp": self.book_score_bp,
                "card_id": self.card_id, "lane": self.lane}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Item":
        return cls(item_id=str(raw["item_id"]), kind=raw.get("kind"), about=raw.get("about"),
                   subject=raw.get("subject"), material=Material.from_mapping(raw.get("material") or {}),
                   sources=tuple(Source.from_mapping(s) for s in raw.get("sources") or ()),
                   mode=raw.get("mode"), stakes=raw.get("stakes"), urgency=raw.get("urgency"), at=raw.get("at"),
                   quiet_days=raw.get("quiet_days"), our_move=bool(raw.get("our_move")),
                   book_score_bp=raw.get("book_score_bp"), card_id=raw.get("card_id"), lane=raw.get("lane"))


def line_id_for(org_id: str, seat_id: str, local_date: date, section: str, item_id: str) -> str:
    """A line's id: its place in one seat's day — the org, the seat, the local date, the section, the item."""
    return "bl_" + semantic_hash({"org": org_id, "seat": seat_id, "date": _iso(local_date),
                                  "section": section, "item": item_id})[:24]


@dataclass(frozen=True, slots=True)
class Line:
    """An item's words in a section — whose they are, and the check's verdict on a written one."""
    line_id: str
    item_id: str
    section: str
    words: str
    kind: str
    subject: str | None
    sources: tuple[Source, ...]
    by: str = TEMPLATE
    verdict: str | None = None           # None: code's words, nothing to check
    reason: str | None = None            # why a written line was given back its template words

    def __post_init__(self) -> None:
        _closed(self.section, SECTIONS, "a line's section")
        object.__setattr__(self, "words", _words(self.words, "line"))
        _closed(self.by, BY, "a line's by")
        _closed(self.kind, KINDS, "a line's kind")
        object.__setattr__(self, "sources", tuple(self.sources))
        if self.verdict is not None:
            _closed(self.verdict, LINE_VERDICTS, "a line's verdict")
        if self.by == WRITER and self.verdict != KEPT:
            raise ValueError("a written line was checked and kept — a line the check refused has its "
                             "template words back")
        if self.verdict == KEPT and self.by != WRITER:
            raise ValueError("only a written line is kept by the check")
        if self.verdict == GIVEN_BACK and not str(self.reason or "").strip():
            raise ValueError("a line given back says why")
        if self.reason is not None and self.verdict != GIVEN_BACK:
            raise ValueError("a reason belongs to a line given back")

    def as_mapping(self) -> dict[str, Any]:
        return {"line_id": self.line_id, "item_id": self.item_id, "section": self.section, "words": self.words,
                "kind": self.kind, "subject": self.subject, "sources": [s.as_mapping() for s in self.sources],
                "by": self.by, "verdict": self.verdict, "reason": self.reason}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Line":
        return cls(line_id=str(raw["line_id"]), item_id=str(raw["item_id"]), section=raw.get("section"),
                   words=raw.get("words"), kind=raw.get("kind"), subject=raw.get("subject"),
                   sources=tuple(Source.from_mapping(s) for s in raw.get("sources") or ()),
                   by=raw.get("by") or TEMPLATE, verdict=raw.get("verdict"), reason=raw.get("reason"))


def digest_of(items: Iterable[Item]) -> str:
    """The day's material, as one content address: two days with the same material have the same digest.
    JSON with sorted keys rather than `semantic_hash`, which refuses floats — and a reply time is one."""
    payload = json.dumps([i.as_mapping() for i in items], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Brief:
    """One seat's morning — read back as it was kept."""
    org_id: str
    seat_id: str
    local_date: date
    timezone: str
    as_of: datetime
    one_line: str
    lines: tuple[Line, ...]
    items: tuple[Item, ...]
    written_by: str
    why: str
    model: str | None
    tier: str | None
    cost_micro_usd: int
    cut: tuple[tuple[str, int], ...]
    material_digest: str
    version: str = BRIEF_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "cut", tuple((s, int(n)) for s, n in self.cut))
        object.__setattr__(self, "as_of", _instant(self.as_of))
        if isinstance(self.local_date, str):
            object.__setattr__(self, "local_date", date.fromisoformat(self.local_date))
        object.__setattr__(self, "one_line", _words(self.one_line, "brief's one line"))
        _closed(self.written_by, WRITTEN_BY, "how a brief was written")
        if not str(self.why or "").strip():
            raise ValueError("a brief says why it was written the way it was")
        if not isinstance(self.cost_micro_usd, int) or self.cost_micro_usd < 0:
            raise ValueError("a brief's cost is a non-negative number of micro-dollars")
        if self.written_by == TEMPLATE_BRIEF and (self.cost_micro_usd or self.model or self.tier):
            raise ValueError("the template brief spends nothing and names no model")
        if self.written_by == TEMPLATE_BRIEF and any(l.by == WRITER for l in self.lines):
            raise ValueError("the template brief holds no writer's line")
        for section, n in self.cut:
            _closed(section, SECTIONS, "a cut's section")
            if n < 1:
                raise ValueError("a cut counts what it cut: at least one")
        if self.material_digest != digest_of(self.items):
            raise ValueError("the material digest is the digest of the brief's items")
        order = [SECTIONS.index(l.section) for l in self.lines]
        if order != sorted(order):
            raise ValueError("a brief's lines keep the sections' order")
        for section in SECTIONS:
            n = sum(1 for l in self.lines if l.section == section)
            if n > CAPS[section]:
                raise ValueError(f"{section} holds {n} lines, past its cap of {CAPS[section]}")
        ids = [l.line_id for l in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("a line stands once in a brief")
        items = {i.item_id for i in self.items}
        shown = [l.item_id for l in self.lines]
        if not set(shown) <= items:
            raise ValueError("a line names an item of its own brief")
        if len(shown) != len(set(shown)):
            raise ValueError("an item stands once in a brief")
        if self.words > WORD_BUDGET:
            raise ValueError(f"a brief is read in three minutes: {self.words} words, past {WORD_BUDGET}")

    @property
    def words(self) -> int:
        return count_words(self.one_line) + sum(count_words(l.words) for l in self.lines)

    @property
    def empty(self) -> bool:
        """Nothing open, asked, due or watched: no line outside what changed."""
        return not any(l.section != CHANGED for l in self.lines)

    def section(self, name: str) -> tuple[Line, ...]:
        return tuple(l for l in self.lines if l.section == name)

    def item(self, item_id: str) -> Item | None:
        return next((i for i in self.items if i.item_id == item_id), None)

    def as_mapping(self) -> dict[str, Any]:
        return {"version": self.version, "org_id": self.org_id, "seat_id": self.seat_id,
                "local_date": self.local_date.isoformat(), "timezone": self.timezone,
                "as_of": self.as_of.isoformat(), "one_line": self.one_line,
                "lines": [l.as_mapping() for l in self.lines], "items": [i.as_mapping() for i in self.items],
                "written_by": self.written_by, "why": self.why, "model": self.model, "tier": self.tier,
                "cost_micro_usd": self.cost_micro_usd, "cut": [list(c) for c in self.cut],
                "material_digest": self.material_digest}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Brief":
        return cls(org_id=str(raw["org_id"]), seat_id=str(raw["seat_id"]),
                   local_date=date.fromisoformat(str(raw["local_date"])), timezone=str(raw["timezone"]),
                   as_of=raw["as_of"], one_line=raw.get("one_line"),
                   lines=tuple(Line.from_mapping(l) for l in raw.get("lines") or ()),
                   items=tuple(Item.from_mapping(i) for i in raw.get("items") or ()),
                   written_by=raw.get("written_by"), why=raw.get("why"), model=raw.get("model"),
                   tier=raw.get("tier"), cost_micro_usd=int(raw.get("cost_micro_usd") or 0),
                   cut=tuple((s, int(n)) for s, n in raw.get("cut") or ()),
                   material_digest=str(raw.get("material_digest") or ""),
                   version=str(raw.get("version") or BRIEF_VERSION))


__all__ = ["ASKED", "BRIEF_VERSION", "BY", "Brief", "CAPS", "CHANGE", "CHANGED", "DECISION", "DESK", "ESCALATED",
           "GIVEN_BACK", "Item", "KEPT", "KINDS", "LANES", "LEVELS", "LINE_VERDICTS", "Line", "MEETING",
           "MEETINGS", "Material", "NO_FOLLOW_UP", "Number", "PROMISE", "PROMISES", "QUESTION", "SECTIONS",
           "SOURCE_BRIEF", "SOURCE_CALCULATOR", "SOURCE_CARD", "SOURCE_KINDS", "SOURCE_MAIL", "SOURCE_MEETING",
           "SOURCE_PROMISE", "SOURCE_QUESTION", "SOURCE_RECEIPT", "SOURCE_REVIEW", "STUCK", "Source", "TEMPLATE",
           "TEMPLATE_BRIEF", "TITLES", "TODAY", "WATCHED", "WATCHING", "WORDS_PER_MINUTE", "WORD_BUDGET",
           "WRITER", "WRITTEN", "WRITTEN_BY", "YOUR_DESK", "count_words", "digest_of", "item_id_for",
           "line_id_for"]
