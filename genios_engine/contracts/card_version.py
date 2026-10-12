"""What a version of a file's card is — the words it showed, the signal it carried, and what changed (STEP-14).

`speedrun008/YC-II W27/` STEP-14 §8.4 items 1-2, tree `yc2_w27_s14` M42.C1.L-contract.V0.U02, s14-D1. A file's
card lives (`migrations/0220`): each new decision or question on the file is a VERSION of the same card — the
card re-pointed at the file's new signal, its words rewritten, one `card.versioned` event keeping the words before
(`platform/card_lifecycle.version_card`) — never a second card. This is what that event says:

  * the WORDS the version showed: the headline, the situation, the move whole, the draft, the lane — and the
    three things a move is made of that are not words: whom it asks for (`ask`: the ask it answers, or the
    question asked), whom its draft goes to (`recipient`) and by when (`by_when`), with the card's `mode`;
  * the SIGNAL it carried — a learning verdict given on this version is read against it (STEP-14 §8.7);
  * the CHANGE, closed: created, updated, reworded, renewed, asked, answered, reopened;
  * whether it is MATERIAL, by ONE closed rule (s14-D1): another ask, recipient, date, lane or mode. A rewording
    or a renewal is a quiet version — kept in the card's history, pushed to nobody — and only a material one
    may interrupt the founder again; the pipeline pushes it under the day's band and budget, as any card.

Pure and frozen: no I/O, no clock, no model. `as_mapping` is what the version event stores; `from_mapping` reads
it back and holds it to the rule — a stored version that says it is quiet while its ask moved is refused.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any

# ── the change — closed. One name to a line (`tests/test_no_missing_module_deps` reads assignments). ──────────
CREATED = "created"            # the file's card, its first version
UPDATED = "updated"            # a material change (another ask, recipient, date, lane or mode)
REWORDED = "reworded"          # its words moved and nothing material did
RENEWED = "renewed"            # the same advice on the file's new signal — its window moved, nothing else
ASKED = "asked"                # the file asks you a question, or another question
ANSWERED = "answered"          # your answer is in; the file is read again
REOPENED = "reopened"          # a card the clock, a replacement or a clearing closed, brought back (s14-D2)
CHANGES: tuple[str, ...] = (CREATED, UPDATED, REWORDED, RENEWED, ASKED, ANSWERED, REOPENED)

# ── what is material — closed (s14-D1) ─────────────────────────────────────────────────────────────────
ASK = "ask"
RECIPIENT = "recipient"
DATE = "by_when"
LANE = "lane"
MODE = "mode"
MATERIAL: tuple[str, ...] = (ASK, RECIPIENT, DATE, LANE, MODE)
#: The words a version shows; a change in these alone is a rewording.
WORDS: tuple[str, ...] = ("headline", "situation", "move", "draft")

#: The mode of a version that asks you a question, and of the one your answer makes.
QUESTION_MODE = "question"
ANSWERED_MODE = "answered"


def _said(value: Any) -> str | None:
    """A shown word as the founder reads it: its whitespace folded; empty is None."""
    said = " ".join(str(value).split()) if value is not None else ""
    return said or None


@dataclass(frozen=True, slots=True)
class VersionWords:
    """What one version of a card showed — and the three things its move is made of that are not words."""
    headline: str
    situation: str
    move: str | None = None            # the move whole (who, what, for whom, by when, to)
    draft: str | None = None
    lane: str | None = None            # the output lane (`reason/output_lane`)
    mode: str | None = None            # the expert's mode, QUESTION_MODE or ANSWERED_MODE
    ask: str | None = None             # the ask the move answers, or the question asked
    recipient: str | None = None       # whom the draft goes to
    by_when: str | None = None         # the move's date, ISO

    def __post_init__(self) -> None:
        for f in fields(self):
            object.__setattr__(self, f.name, _said(getattr(self, f.name)))
        if not self.headline or not self.situation:
            raise ValueError("a version shows a headline and a situation")

    def as_mapping(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "VersionWords":
        if not isinstance(raw, Mapping):
            raise ValueError("a version's words are an object")
        return cls(**{f.name: raw.get(f.name) for f in fields(cls)})


def changed_fields(before: VersionWords, after: VersionWords) -> tuple[str, ...]:
    """Every field that moved, in the order a version names them."""
    return tuple(f.name for f in fields(VersionWords) if getattr(before, f.name) != getattr(after, f.name))


def is_material(changed: tuple[str, ...]) -> bool:
    """THE RULE (s14-D1): another ask, recipient, date, lane or mode."""
    return any(name in MATERIAL for name in changed)


def _change(before: VersionWords | None, after: VersionWords, changed: tuple[str, ...], *, reopened: bool,
            answered: bool) -> str:
    if before is None:
        return CREATED
    if answered:
        return ANSWERED
    if after.mode == QUESTION_MODE and (before.mode != QUESTION_MODE or before.ask != after.ask):
        return ASKED
    if reopened:
        return REOPENED
    if is_material(changed):
        return UPDATED
    return REWORDED if changed else RENEWED


@dataclass(frozen=True, slots=True)
class CardVersion:
    """One version of a file's card: its number, the signal it carried, what it showed, what changed."""
    version: int
    signal_id: str
    change: str
    words: VersionWords
    before: VersionWords | None
    changed: tuple[str, ...]
    material: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "changed", tuple(self.changed))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("a version is numbered from 1")
        if not str(self.signal_id or "").strip():
            raise ValueError("a version names the signal it carried")
        if self.change not in CHANGES:
            raise ValueError(f"a change is one of {CHANGES}, not {self.change!r}")
        if (self.change == CREATED) != (self.before is None):
            raise ValueError("only a created card has no words before it")
        if self.change == CREATED and self.version != 1:
            raise ValueError("a card is created as its version 1")
        expected = () if self.before is None else changed_fields(self.before, self.words)
        if self.changed != expected:
            raise ValueError(f"a version says what changed: {expected}, not {self.changed}")
        material = self.before is None or is_material(self.changed)
        if self.material != material:
            raise ValueError("a version is material by the rule (s14-D1) and by nothing else")

    def as_mapping(self) -> dict[str, Any]:
        return {"version": self.version, "signal_id": self.signal_id, "change": self.change,
                "material": self.material, "changed": list(self.changed), "words": self.words.as_mapping(),
                "before": self.before.as_mapping() if self.before is not None else None}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CardVersion":
        if not isinstance(raw, Mapping):
            raise ValueError("a card version is an object")
        before = raw.get("before")
        return cls(version=raw.get("version"), signal_id=str(raw.get("signal_id") or ""),
                   change=str(raw.get("change") or ""), words=VersionWords.from_mapping(raw.get("words") or {}),
                   before=VersionWords.from_mapping(before) if before is not None else None,
                   changed=tuple(str(c) for c in raw.get("changed") or ()), material=raw.get("material"))


def version_of(before: VersionWords | None, after: VersionWords, *, version: int, signal_id: str,
               reopened: bool = False, answered: bool = False) -> CardVersion:
    """The version `after` makes of a card that showed `before` (None: the card is new) — its change and
    whether it is material, by the one closed rule. `reopened`: the card was closed by the clock, a replacement
    or a clearing (s14-D2); `answered`: the version your answer makes (s14-D3)."""
    if before is None and answered:
        raise ValueError("an answer versions a card that asked")
    changed = () if before is None else changed_fields(before, after)
    return CardVersion(version=version, signal_id=signal_id,
                       change=_change(before, after, changed, reopened=reopened, answered=answered),
                       words=after, before=before, changed=changed,
                       material=before is None or is_material(changed))


__all__ = ["ANSWERED", "ANSWERED_MODE", "ASK", "ASKED", "CHANGES", "CREATED", "CardVersion", "DATE", "LANE",
           "MATERIAL", "MODE", "QUESTION_MODE", "RECIPIENT", "REOPENED", "RENEWED", "REWORDED", "UPDATED",
           "VersionWords", "WORDS", "changed_fields", "is_material", "version_of"]
