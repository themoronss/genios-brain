"""The week, measured — one tenant's ISO week: was it useful, what was held back, what was read, what ended, what you changed.

`speedrun008/YC-II W27/` STEP-16 §8.4 item 9, tree `yc2_w27_s16` M47.C3.L-logic.V5.U01 (`09` G6, `06` D18). Five parts,
each read from what is already written, composed here — no model, no table of its own:

  USEFULNESS     the week's cards (created in it) by lane, and what came of each so far (`context/file_outcomes`):
                 taken, called wrong — by reason, and the layer each reason debits (`feedback/attribution.route`,
                 which nothing read until now) — only replied, verified, lapsed, replaced, cleared, still open;
  HELD BACK      the reviews the check decided in the week: each move's fate (shown, held, suppressed, refused)
                 and why, the reasons lines were dropped for, the notes it kept — and the questions the files asked,
                 answered and called wrong ("held — its question called wrong", `06` S16-D10);
  COVERAGE       STEP-10's receipt: each connected mailbox, the window it sweeps, its last sync and whether it
                 completed (`context/coverage_receipt`);
  OUTCOMES       of the week's decisions that ended, how many ended verified — by the kind of work their file is,
                 and for all: the verified-outcome rate, with its n (never a habit below five, `06` D37);
  CORRECTIONS    each correction you made in the week, and what it changed on each file it reached
                 (`reason/expert/correction_delta`): reviewed since, changed, cited.

A WEEK WITH NOTHING SAYS SO: `nothing` is true and `says` reads it. A part with nothing in it is empty, never left
out — an empty count and a part that was not read must not look alike.

The week is the ISO week in UTC — Monday 00:00 to the next — named `YYYY-Www`. Org-level: nothing a seat holds
privately is read. Observe-only: nothing here writes, mutes, nudges or moves an authority (`06` S16-D5).
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.feedback.attribution import route

#: An ISO week, as the route takes it: `2026-W42`.
_WEEK = re.compile(r"^(\d{4})-W(\d{2})$")

#: Each review the check decided in the week — its stored check.
_CHECKED = (
    "select file_id, fingerprint, checked from expert_reviews where org_id = :o and status = 'valid' "
    "and checked is not null and checked_at >= :since and checked_at < :until order by checked_at, fingerprint")
#: The questions the files asked, answered and called wrong in the week (`context/founder_questions.CALLED_WRONG`:
#: each a move held with no card — "held, its question called wrong", `06` S16-D10).
_QUESTIONS = (
    "select count(*) filter (where asked_at >= :since and asked_at < :until) as asked, "
    "count(*) filter (where answered_at >= :since and answered_at < :until) as answered, "
    "count(*) filter (where state = 'retired' and retired_why = :wrong and retired_at >= :since "
    "and retired_at < :until) as called_wrong from founder_questions where org_id = :o")


@dataclass(frozen=True, slots=True)
class Week:
    """One ISO week, in UTC."""
    year: int
    number: int

    def __post_init__(self) -> None:
        datetime.fromisocalendar(self.year, self.number, 1)      # raises on a week the year has not

    @property
    def label(self) -> str:
        return f"{self.year}-W{self.number:02d}"

    @property
    def since(self) -> datetime:
        return datetime.fromisocalendar(self.year, self.number, 1).replace(tzinfo=timezone.utc)

    @property
    def until(self) -> datetime:
        return self.since + timedelta(days=7)

    @classmethod
    def of(cls, label: str) -> "Week":
        """`2026-W42` — anything else is refused."""
        m = _WEEK.match(str(label or "").strip())
        if m is None:
            raise ValueError(f"a week is YYYY-Www, not {label!r}")
        return cls(int(m.group(1)), int(m.group(2)))

    @classmethod
    def containing(cls, at: datetime) -> "Week":
        year, number, _day = at.astimezone(timezone.utc).isocalendar()
        return cls(year, number)


@dataclass(frozen=True, slots=True)
class Scorecard:
    """One tenant's week."""
    org_id: str
    week: Week
    usefulness: Mapping[str, Mapping[str, int]] = field(default_factory=dict)   # lane → end → cards
    wrong_reasons: Mapping[str, int] = field(default_factory=dict)              # reason → cards called wrong
    debits: tuple[Mapping[str, Any], ...] = ()                                  # the layers your reasons debit
    unattributed: int = 0
    held_back: Mapping[str, Any] = field(default_factory=dict)
    questions: Mapping[str, int] = field(default_factory=dict)
    coverage: tuple[Mapping[str, Any], ...] = ()
    outcomes: Mapping[str, Any] = field(default_factory=dict)
    corrections: tuple[Mapping[str, Any], ...] = ()

    @property
    def cards(self) -> int:
        return sum(sum(ends.values()) for ends in self.usefulness.values())

    @property
    def nothing(self) -> bool:
        """Nothing happened in the week: no card, no review checked, no question, no correction."""
        return not (self.cards or self.held_back.get("reviews") or any(self.questions.values())
                    or self.corrections)

    @property
    def says(self) -> str:
        if self.nothing:
            return f"Nothing happened in {self.week.label}: no card, no review, no question, no correction."
        verified = self.outcomes.get("all", {}).get("verified", {})
        return (f"{self.week.label}: {self.cards} card(s); {self.held_back.get('reviews', 0)} review(s) checked; "
                f"{len(self.corrections)} correction(s); verified outcomes: {verified.get('says', 'not measured')}")

    def as_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "week": self.week.label, "since": self.week.since.isoformat(),
                "until": self.week.until.isoformat(), "nothing": self.nothing, "says": self.says,
                "usefulness": {lane: dict(ends) for lane, ends in self.usefulness.items()},
                "wrong_reasons": dict(self.wrong_reasons), "debits": [dict(d) for d in self.debits],
                "unattributed": self.unattributed, "held_back": dict(self.held_back),
                "questions": dict(self.questions), "coverage": [dict(c) for c in self.coverage],
                "outcomes": dict(self.outcomes), "corrections": [dict(c) for c in self.corrections]}


def _held_back(checks: Iterable[Any]) -> dict[str, Any]:
    fates: Counter = Counter()
    because: Counter = Counter()
    dropped: Counter = Counter()
    notes: Counter = Counter()
    reviews = 0
    for checked in checks:
        reviews += 1
        fates[checked.fate] += 1
        if checked.because:
            because[f"{checked.fate}: {checked.because}"] += 1
        dropped.update(checked.reasons)
        notes.update(checked.notes)
    from genios_engine.contracts.claim_check import FATES
    return {"reviews": reviews, "fates": {f: fates.get(f, 0) for f in FATES}, "because": dict(sorted(because.items())),
            "dropped": dict(sorted(dropped.items())), "notes": dict(sorted(notes.items()))}


def _correction(delta: Any, correction: Any) -> dict[str, Any]:
    return {"correction_id": correction.correction_id, "scope": correction.scope, "file_id": correction.file_id,
            "kind": correction.kind, "reason": correction.reason, "words": correction.words,
            "corrected_at": correction.corrected_at.isoformat(), "state": correction.state,
            "reviewed": delta.reviewed, "changed": delta.changed, "cited": delta.cited,
            "files": [{"file_id": f.file_id, "changed": f.changed,
                       "before": None if f.before is None else {"mode": f.before.mode, "move": f.before.move},
                       "after": None if f.after is None else {"mode": f.after.mode, "move": f.after.move,
                                                              "cited": f.after.cited, "fate": f.after.fate}}
                      for f in delta.files]}


def compose(*, org_id: str, week: Week, endings: Sequence[Any], kinds: Mapping[str, str | None],
            checks: Sequence[Any], questions: Mapping[str, int], coverage: Sequence[Any],
            corrections: Sequence[Any], deltas: Sequence[Any]) -> Scorecard:
    """The scorecard from what was read — pure: the same reads, the same week, the same scorecard."""
    from genios_engine.context.file_outcomes import CALLED_WRONG, rates
    by = rates(endings, kinds=kinds)
    usefulness = {lane: dict(r.counts) for lane, r in by["lane"].items()}
    wrong = Counter(str(e.reason or "none") for e in endings if e.ended == CALLED_WRONG)
    # Every card's end is a judgment row: a card called wrong debits the layer its reason names, any other end is
    # counted as no complaint (`attribution.route`).
    report = route({"cause": "wrong" if e.ended == CALLED_WRONG else e.ended, "reason": e.reason} for e in endings)
    return Scorecard(
        org_id=org_id, week=week, usefulness=usefulness, wrong_reasons=dict(sorted(wrong.items())),
        debits=tuple({"layer": d.layer, "layer_number": d.layer_number, "debits": d.debits,
                      "accuracy_debits": d.accuracy_debits, "fixes": list(d.fixes)} for d in report.by_layer),
        unattributed=report.unattributed, held_back=_held_back(checks),
        questions={"asked": int(questions.get("asked") or 0), "answered": int(questions.get("answered") or 0),
                   "called_wrong": int(questions.get("called_wrong") or 0)},
        coverage=tuple({"connection_id": r.connection_id, "address": r.address, "window_days": r.window_days,
                        "window_start": r.window_start.isoformat() if r.window_start else None,
                        "last_finished_at": r.last_finished_at.isoformat() if r.last_finished_at else None,
                        "last_completed": r.last_completed} for r in coverage),
        outcomes={"by_kind": {k: r.as_dict() for k, r in by["kind"].items()}, "all": by["all"]["all"].as_dict()},
        corrections=tuple(_correction(d, c) for d, c in zip(deltas, corrections)))


def scorecard_for(conn, org_id: str, week: Week, *, now: datetime) -> Scorecard:
    """One tenant's week, read as of `now` (a week not over yet is read so far)."""
    from genios_engine.context.coverage_receipt import receipt_for
    from genios_engine.context.file_outcomes import ended_between
    from genios_engine.context.founder_corrections import made_between
    from genios_engine.context.founder_questions import CALLED_WRONG as QUESTION_CALLED_WRONG
    from genios_engine.context.workstreams import files_for
    from genios_engine.contracts.claim_check import CheckedReview
    from genios_engine.reason.expert.correction_delta import deltas_for
    until = min(week.until, now)
    window = {"o": org_id, "since": week.since, "until": until}
    endings = ended_between(conn, org_id, since=week.since, until=until)
    kinds = {f.file_id: f.work_kind for f in files_for(conn, org_id, now=until).files} if endings else {}
    checks = [CheckedReview.from_mapping(r.checked) for r in conn.execute(text(_CHECKED), window)]
    asked = conn.execute(text(_QUESTIONS), {**window, "wrong": QUESTION_CALLED_WRONG}).one()._mapping
    corrections = made_between(conn, org_id, since=week.since, until=until)
    return compose(org_id=org_id, week=week, endings=endings, kinds=kinds, checks=checks, questions=dict(asked),
                   coverage=receipt_for(conn, org_id, now=until), corrections=corrections,
                   deltas=deltas_for(conn, org_id, corrections))


__all__ = ["Scorecard", "Week", "compose", "scorecard_for"]
