"""What the check found in one expert review — a verdict per line, and what the founder may be shown (STEP-13).

`speedrun008/YC-II W27/` STEP-13 §3.1-§3.4 and §8.4, tree `yc2_w27_s13` M35.C1.L-contract.V0.U02. STEP-12's
contract (`contracts/expert_review.validate`) says whether a review says more than its dossier holds, and the
review run refused the WHOLE review on any of it: one uncited fact, and the file went back to the path the
expert replaced. STEP-13 checks a review line by line (`reason/expert/verify`) and keeps the judgment that
stands (`06` D59). This is what that check writes down:

  * a VERDICT for each line it looked at — kept, corrected (from what, to what, by which calculator), or
    dropped for one closed reason — and the wording notes it keeps without dropping anything;
  * the move's FATE: shown (the review decides as it said), held (the move lost its ground, or its own
    words or its recipient failed: the file goes to Investigation and asks ONE question), suppressed (the
    ask it answers is already answered), or refused (no fact stands: the file is not decided by it);
  * the QUESTION a file in Investigation asks — the find-out move's own, or the check's;
  * the card's WORDS after the check — the headline, the situation, what done looks like, the draft and
    its recipient: only these reach a card;
  * the ids the STANDING facts cite — what a decision's confidence may count, and nothing a dropped fact
    cited.

Closed vocabularies, so every verdict can be counted by kind. Pure and frozen: no I/O, no clock, no model.
`as_mapping` is what is stored beside the review (migration 0200); `from_mapping` reads it back.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: The check's own version — a review checked under an older one is checked again on read.
CHECK_VERSION = "check.v1"

# ── what happened to a line ────────────────────────────────────────────────────────────────────
# One name to a line: `tests/test_no_missing_module_deps` reads what a module defines by its assignments,
# and a tuple of names is no name it can see — every caller that imports one would read as broken.
KEPT = "kept"
CORRECTED = "corrected"
DROPPED = "dropped"
NOTED = "noted"
VERDICTS: tuple[str, ...] = (KEPT, CORRECTED, DROPPED, NOTED)

# ── why — closed ───────────────────────────────────────────────────────────────────────────────
UNCITED = "uncited"                          # a fact citing nothing
UNKNOWN_EVIDENCE = "unknown_evidence"        # citing an id the dossier never showed
UNQUOTED = "unquoted"                        # a fact a move rests on, citing a mail, with no quote
MISQUOTED = "misquoted"                      # a quote the cited mail's words do not hold — or no word shown
UNSUPPORTED = "unsupported"                  # a name its lines do not hold
WRONG_NUMBER = "wrong_number"                # a number its lines do not hold, and no calculator to fix it
UNGROUNDED = "ungrounded"                    # an inference or pattern whose grounds all fell
NO_RECIPIENT = "no_recipient"                # a draft with nobody to go to
RECIPIENT_NOT_ON_FILE = "recipient_not_on_file"
RECIPIENT_IS_US = "recipient_is_us"
RECIPIENT_IS_CONNECTOR = "recipient_is_connector"
NOT_OURS_TO_ANSWER = "not_ours_to_answer"    # answering an ask that waits on THEM
ANSWERED = "answered"                        # the ask it answers is answered already
NOTHING_STANDS = "nothing_stands"            # no fact of the review stands
ON_YOUR_ANSWER = "on_your_answer"            # a move resting only on what you told us: confirmed with you first
DECLINED_BY_YOU = "declined_by_you"          # …and you did not confirm it
REASONS: tuple[str, ...] = (UNCITED, UNKNOWN_EVIDENCE, UNQUOTED, MISQUOTED, UNSUPPORTED, WRONG_NUMBER,
                            UNGROUNDED, NO_RECIPIENT, RECIPIENT_NOT_ON_FILE, RECIPIENT_IS_US,
                            RECIPIENT_IS_CONNECTOR, NOT_OURS_TO_ANSWER, ANSWERED, NOTHING_STANDS,
                            ON_YOUR_ANSWER, DECLINED_BY_YOU)
#: How a line is corrected — closed, as a reason is.
BY_CALCULATOR = "by_calculator"              # a number replaced by the one its calculator line holds
BY_ALTERNATIVE = "by_alternative"            # a move to a connector replaced by the review's alternative
CORRECTIONS: tuple[str, ...] = (BY_CALCULATOR, BY_ALTERNATIVE)
#: Kept, and written down — for the live pass to count (`06` D50), never a reason to drop.
SPEAKS_OF_YOU = "speaks_of_you"              # a card text calling the founder "the founder", or naming us
UNHELD_NUMBER = "unheld_number"              # a number in prose no founder is shown, not in the dossier
CONFIRMED_BY_YOU = "confirmed_by_you"        # a move resting only on what you told us, that you confirmed
NOTES: tuple[str, ...] = (SPEAKS_OF_YOU, UNHELD_NUMBER, CONFIRMED_BY_YOU)

# ── what happens to the move ───────────────────────────────────────────────────────────────────
SHOWN = "shown"
HELD = "held"
SUPPRESSED = "suppressed"
REFUSED = "refused"
FATES: tuple[str, ...] = (SHOWN, HELD, SUPPRESSED, REFUSED)

#: The lines a verdict may name: a review's own, by kind and number — a fact's QUOTE among them, by its
#: fact's number (`quote:<n>`: a quote the cited words do not hold drops there, the fact needing none,
#: M35.C2.L-logic.V1.U09); what reaches the founder — the card's words, whom its draft goes to, the ask
#: the move answers, the kind it proposes; its prose; and the facts the move names as its ground
#: (`rests_on`: a ref that names no fact of the review drops there, M35.C1.L-contract.V0.U04).
LINE_KINDS: tuple[str, ...] = ("fact", "inference", "pattern", "quote")
CARD_LINES: tuple[str, ...] = ("move", "situation", "done_when", "draft", "to", "answers", "kind", "prose",
                               "rests_on", "do_nothing", "question")
#: What a file asks when nothing checked can be asked — ours, closed (`reason/expert/asks`, and a held question
#: that would name you, M36.C2.L-logic.V2.U19).
NOTHING_TO_ASK = "Can you tell us where this file stands?"

#: Why a move is HELD, as the founder reads it on the question card — closed, one phrase per cause
#: (M35.C3.L-integration.V2.U05, crosscheck X10): the check's own detail ("misquoted: <the model's
#: quote> (fact 1)") stays in its verdicts, never on a card. Keyed by the reason a fact the move rests on
#: was dropped for, or by what else held it: its own words (`move`), its recipient, its answered ask.
HELD_MOVE = "move"
HELD_BECAUSE: dict[str, str] = {
    UNCITED: "a fact your move rests on cites nothing on the file",
    UNKNOWN_EVIDENCE: "a fact your move rests on cites something the file does not show",
    UNQUOTED: "a fact your move rests on quotes nothing from the mail it cites",
    # ⛔ TRUE OF WHAT FAILED (M36.C2.L-logic.V2.U10, second crosscheck G2): the QUOTE is not in the mail — the
    # claim may well be (a paraphrase); "is not in the words it cites" was said of words the mail holds.
    MISQUOTED: "the words a fact your move rests on quotes are not in the mail it cites",
    UNSUPPORTED: "a fact your move rests on names someone its lines do not",
    WRONG_NUMBER: "a fact your move rests on has a number its lines do not hold",
    HELD_MOVE: "the move says something the facts it rests on do not hold",
    RECIPIENT_IS_US: "the move is addressed to you",
    RECIPIENT_IS_CONNECTOR: "the move goes to whoever made the introduction",
    ANSWERED: "the ask the move answers is already answered",
    ON_YOUR_ANSWER: "the move rests only on what you told us",
}


def _closed(value: Any, allowed: tuple[str, ...], name: str) -> str:
    word = str(value or "")
    if word not in allowed:
        raise ValueError(f"{name} is one of {allowed}, not {value!r}")
    return word


def _line(value: Any) -> str:
    line = str(value or "")
    kind, _, n = line.partition(":")
    if line in CARD_LINES or (kind in LINE_KINDS and n.isdigit() and int(n) >= 1):
        return line
    raise ValueError(f"a verdict names a line of the review or of the card, not {value!r}")


@dataclass(frozen=True, slots=True)
class LineVerdict:
    """One line, what the check did to it, and why."""
    line: str                                  # `fact:<n>`, `inference:<n>`, `pattern:<n>`, or a CARD_LINE
    verdict: str                               # one of VERDICTS
    reason: str | None = None                  # a REASON (dropped), a CORRECTION (corrected), a NOTE (noted)
    detail: str = ""                           # what was found: "number:52 -> 48 (num:reply_gap)", "name:Boardy"

    def __post_init__(self) -> None:
        object.__setattr__(self, "line", _line(self.line))
        object.__setattr__(self, "verdict", _closed(self.verdict, VERDICTS, "a verdict"))
        allowed = {KEPT: (None,), DROPPED: REASONS, CORRECTED: CORRECTIONS, NOTED: NOTES}[self.verdict]
        if self.reason not in allowed:
            raise ValueError(f"a {self.verdict} line's reason is one of {allowed}, not {self.reason!r}")
        object.__setattr__(self, "detail", " ".join(str(self.detail or "").split()))

    def as_mapping(self) -> dict[str, Any]:
        return {"line": self.line, "verdict": self.verdict, "reason": self.reason, "detail": self.detail}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LineVerdict":
        return cls(line=raw.get("line"), verdict=raw.get("verdict"), reason=raw.get("reason"),
                   detail=raw.get("detail") or "")


@dataclass(frozen=True, slots=True)
class CardWords:
    """The card's words once checked — only these may reach the founder. None: withheld. `evidence` and
    `quotes` are where the headline came from: the ids the facts it rests on cite, and those facts'
    quotes — what the card shows beside it (STEP-13 §5: every sentence carries its source). `do_nothing`
    is what doing nothing costs, as checked — the card's "cost of ignoring" — and `kind` the proposed kind's
    reason, as checked: what the brief's pending line is written from (M35.C3.L-integration.V2.U05)."""
    headline: str | None
    situation: str | None
    done_when: str | None
    draft: str | None
    to: str | None
    evidence: tuple[str, ...] = ()
    quotes: tuple[str, ...] = ()
    do_nothing: str | None = None
    kind: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(dict.fromkeys(str(e) for e in self.evidence)))
        object.__setattr__(self, "quotes", tuple(dict.fromkeys(str(q) for q in self.quotes if q)))

    def as_mapping(self) -> dict[str, Any]:
        return {"headline": self.headline, "situation": self.situation, "done_when": self.done_when,
                "draft": self.draft, "to": self.to, "evidence": list(self.evidence),
                "quotes": list(self.quotes), "do_nothing": self.do_nothing, "kind": self.kind}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CardWords":
        return cls(**{k: (str(raw[k]) if raw.get(k) else None)
                      for k in ("headline", "situation", "done_when", "draft", "to", "do_nothing", "kind")},
                   evidence=tuple(raw.get("evidence") or ()), quotes=tuple(raw.get("quotes") or ()))


@dataclass(frozen=True, slots=True)
class CheckedReview:
    """A review once checked: its verdicts, the move's fate, the one question, the card's words, and the
    ids its standing facts cite."""
    verdicts: tuple[LineVerdict, ...]
    fate: str
    words: CardWords
    cited: tuple[str, ...]
    question: str | None = None
    because: str | None = None                 # held, suppressed or refused: the verdict that decided it
    version: str = CHECK_VERSION
    _dropped: frozenset[str] = field(default=frozenset(), init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdicts", tuple(self.verdicts))
        object.__setattr__(self, "fate", _closed(self.fate, FATES, "a move's fate"))
        object.__setattr__(self, "cited", tuple(sorted(set(self.cited))))
        # One verdict per line — and beside it, any notes, each once.
        lines = [v.line for v in self.verdicts if v.verdict != NOTED]
        notes = [(v.line, v.reason) for v in self.verdicts if v.verdict == NOTED]
        if len(lines) != len(set(lines)) or len(notes) != len(set(notes)):
            raise ValueError("a line has one verdict")
        if self.fate in (HELD, SUPPRESSED, REFUSED) and not self.because:
            raise ValueError(f"a {self.fate} move says why")
        if self.fate == HELD and not self.question:
            raise ValueError("a held move asks its question")
        if self.fate == REFUSED and self.cited:
            raise ValueError("a refused review has no standing fact to cite")
        object.__setattr__(self, "_dropped", frozenset(
            v.line for v in self.verdicts if v.verdict == DROPPED))

    def stands(self, line: str) -> bool:
        """Did this line survive the check?"""
        return line not in self._dropped

    @property
    def dropped(self) -> tuple[LineVerdict, ...]:
        return tuple(v for v in self.verdicts if v.verdict == DROPPED)

    @property
    def reasons(self) -> tuple[str, ...]:
        """Every reason a line was dropped, once each — what is counted."""
        return tuple(sorted({v.reason for v in self.dropped if v.reason}))

    @property
    def notes(self) -> tuple[str, ...]:
        """Every note the check kept, once each."""
        return tuple(sorted({v.reason for v in self.verdicts if v.verdict == NOTED and v.reason}))

    def as_mapping(self) -> dict[str, Any]:
        return {"version": self.version, "fate": self.fate, "question": self.question,
                "because": self.because, "cited": list(self.cited), "words": self.words.as_mapping(),
                "verdicts": [v.as_mapping() for v in self.verdicts]}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CheckedReview":
        if not isinstance(raw, Mapping):
            raise ValueError("a checked review is an object")
        return cls(verdicts=tuple(LineVerdict.from_mapping(v) for v in raw.get("verdicts") or ()),
                   fate=raw.get("fate"), words=CardWords.from_mapping(raw.get("words") or {}),
                   cited=tuple(str(c) for c in raw.get("cited") or ()),
                   question=raw.get("question") or None, because=raw.get("because") or None,
                   version=str(raw.get("version") or CHECK_VERSION))


__all__ = ["ANSWERED", "BY_ALTERNATIVE", "BY_CALCULATOR", "CARD_LINES", "CHECK_VERSION", "CORRECTED",
           "HELD_BECAUSE", "HELD_MOVE",
           "CORRECTIONS", "CardWords", "CheckedReview", "DROPPED", "FATES", "HELD", "KEPT", "LINE_KINDS",
           "LineVerdict", "MISQUOTED", "NOTED", "NOTES", "NOTHING_STANDS", "NOT_OURS_TO_ANSWER",
           "NO_RECIPIENT", "REASONS", "RECIPIENT_IS_CONNECTOR", "RECIPIENT_IS_US",
           "RECIPIENT_NOT_ON_FILE", "REFUSED", "SHOWN", "SPEAKS_OF_YOU", "SUPPRESSED", "UNCITED",
           "UNGROUNDED", "UNHELD_NUMBER", "UNKNOWN_EVIDENCE", "UNQUOTED", "UNSUPPORTED", "VERDICTS",
           "WRONG_NUMBER"]
