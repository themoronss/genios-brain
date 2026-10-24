"""The goal object, `GoalImpact` and `GoalProposal` — what the loop works toward (GeniOS-012 S28.U1).

The authority is `speedrun008/GeniOS-008/00-ARCHITECTURE.md` "Goals" (amended 23 Oct 2026, S26.U3); this module is that
section as types. A goal is an object L3 owns (`context/goals`), every revision a row of `company_goals`. **A human makes
a goal real**: nothing a model or code writes is ever `approved` or `active` — the two statuses require who approved it
and when, here and in the table's check constraint.

  * One goal per piece of work (D10). The door is the company brief (D11): a goal is born when a brief `goals` line is
    accepted, a proposed goal is a pending brief line, and L3 syncs the goals from the brief every sweep.
  * `GoalImpact` — written by L2 on a move: which goal it bears on and how, a word never a score. L3 links it to a
    situation only when the situation is admitted and the goal is live.
  * `GoalProposal` — L2 proposes, L3 admits as a pending brief line, a human approves. Its subject is filled by code.
  * The model never approves, never picks an owner, never states a target or a deadline the dossier did not print.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

#: A goal's life. `proposed` waits on a human; `approved` and `active` were made real by one.
STATUSES: tuple[str, ...] = ("proposed", "approved", "active", "completed", "superseded", "cancelled")
PROPOSED, APPROVED, ACTIVE, COMPLETED, SUPERSEDED, CANCELLED = STATUSES
#: The statuses a human made real — printed to a model as the company's goal (block G).
LIVE: frozenset[str] = frozenset({APPROVED, ACTIVE})
#: The statuses that require `approved_by` and `approved_at` (the table's check constraint says the same).
NEEDS_APPROVER: frozenset[str] = LIVE

#: Who a goal came from: the founder directly, a drafter line the founder accepted, or a proposal still waiting.
SOURCES: tuple[str, ...] = ("founder", "brief", "inferred")
FOUNDER, BRIEF, INFERRED = SOURCES

#: How a move bears on a goal — a word, never a score.
RELATIONS: tuple[str, ...] = ("advances", "threatens", "depends_on", "unclear")
ADVANCES, THREATENS, DEPENDS_ON, UNCLEAR = RELATIONS

#: The longest statement — a goal in the founder's words.
MAX_STATEMENT_CHARS = 200
#: How a goal is named to a model and cited back: `goal:<goal_id>`.
GOAL_REF_PREFIX = "goal:"


def goal_ref(goal_id: str) -> str:
    return f"{GOAL_REF_PREFIX}{goal_id}"


def _statement(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError("a goal needs its statement")
    if len(text) > MAX_STATEMENT_CHARS:
        raise ValueError(f"a goal's statement is at most {MAX_STATEMENT_CHARS} characters")
    return text


@dataclass(frozen=True, slots=True)
class Goal:
    """One revision of a goal, as `company_goals` keeps it."""

    goal_id: str
    org_id: str
    statement: str
    status: str
    source: str
    revision: int = 1
    line_id: str | None = None               # the brief `goals` line it was born from (the one approval door)
    department: str | None = None
    category: str | None = None
    owner_seat: str | None = None
    metric: str | None = None
    target: str | None = None
    deadline: str | None = None
    parent_goal_id: str | None = None
    subject_ref: str | None = None            # an inferred goal's piece of work, `file:<id>`
    evidence_refs: tuple[str, ...] = ()
    approved_by: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not str(self.goal_id or "").strip():
            raise ValueError("a goal needs its id")
        object.__setattr__(self, "statement", _statement(self.statement))
        if self.status not in STATUSES:
            raise ValueError(f"a goal's status is one of {STATUSES}, not {self.status!r}")
        if self.source not in SOURCES:
            raise ValueError(f"a goal's source is one of {SOURCES}, not {self.source!r}")
        if self.status in NEEDS_APPROVER and not (self.approved_by and self.approved_at):
            raise ValueError(f"a goal is {self.status} only when a human approved it — who and when")
        if self.revision < 1:
            raise ValueError("a goal's revisions count from 1")

    @property
    def ref(self) -> str:
        return goal_ref(self.goal_id)

    @property
    def live(self) -> bool:
        return self.status in LIVE

    def same_as(self, other: "Goal") -> bool:
        """The same goal in every field a revision records — so an unchanged sync writes no new row."""
        keys = ("statement", "status", "source", "line_id", "department", "category", "owner_seat", "metric",
                "target", "deadline", "parent_goal_id", "subject_ref", "evidence_refs", "approved_by")
        return all(getattr(self, k) == getattr(other, k) for k in keys)


@dataclass(frozen=True, slots=True)
class GoalImpact:
    """What a move does to a goal (L2 writes it; L3 links it when the situation is admitted and the goal is live)."""

    goal_ref: str
    relation: str
    why: str
    evidence: tuple[str, ...] = ()
    size_basis: str = "not measurable"

    def __post_init__(self) -> None:
        if not str(self.goal_ref or "").startswith(GOAL_REF_PREFIX):
            raise ValueError(f"a goal impact names a printed goal, `{GOAL_REF_PREFIX}<id>`")
        if self.relation not in RELATIONS:
            raise ValueError(f"a goal impact's relation is one of {RELATIONS}, not {self.relation!r}")
        if not " ".join(str(self.why or "").split()):
            raise ValueError("a goal impact says why")
        if self.relation != UNCLEAR and not self.evidence:
            raise ValueError("a goal impact other than `unclear` stands on printed evidence")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "GoalImpact":
        return cls(goal_ref=str(raw.get("goal_ref") or ""), relation=str(raw.get("relation") or ""),
                   why=str(raw.get("why") or ""), evidence=tuple(str(e) for e in raw.get("evidence") or ()),
                   size_basis=str(raw.get("size_basis") or "not measurable"))

    def as_mapping(self) -> dict[str, Any]:
        return {"goal_ref": self.goal_ref, "relation": self.relation, "why": self.why,
                "evidence": list(self.evidence), "size_basis": self.size_basis}


@dataclass(frozen=True, slots=True)
class GoalProposal:
    """A goal L2 sees in motion. L3 admits it as a PENDING brief line; only a human approves it."""

    statement: str
    why: str
    evidence: tuple[str, ...]
    subject_ref: str | None = None            # filled by code from the judged subject, never named by the model
    parent_goal_ref: str | None = None
    deadline: str | None = None
    target: str | None = None
    metric: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "statement", _statement(self.statement))
        if not " ".join(str(self.why or "").split()):
            raise ValueError("a goal proposal says why it is a goal the company is pursuing")
        if not self.evidence:
            raise ValueError("a goal proposal stands on printed evidence — at least one the company's own act")
        if self.parent_goal_ref is not None and not str(self.parent_goal_ref).startswith(GOAL_REF_PREFIX):
            raise ValueError(f"a goal proposal's parent is a printed goal, `{GOAL_REF_PREFIX}<id>`")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "GoalProposal":
        def opt(key: str) -> str | None:
            value = " ".join(str(raw.get(key) or "").split())
            return value or None
        return cls(statement=str(raw.get("statement") or ""), why=str(raw.get("why") or ""),
                   evidence=tuple(str(e) for e in raw.get("evidence") or ()),
                   parent_goal_ref=opt("parent_goal_ref"), deadline=opt("deadline"), target=opt("target"),
                   metric=opt("metric"))

    def as_mapping(self) -> dict[str, Any]:
        return {"statement": self.statement, "why": self.why, "evidence": list(self.evidence),
                "subject_ref": self.subject_ref, "parent_goal_ref": self.parent_goal_ref,
                "deadline": self.deadline, "target": self.target, "metric": self.metric}


__all__ = ["ACTIVE", "ADVANCES", "APPROVED", "BRIEF", "CANCELLED", "COMPLETED", "DEPENDS_ON", "FOUNDER", "GOAL_REF_PREFIX",
           "Goal", "GoalImpact", "GoalProposal", "INFERRED", "LIVE", "MAX_STATEMENT_CHARS", "NEEDS_APPROVER", "PROPOSED",
           "RELATIONS", "SOURCES", "STATUSES", "SUPERSEDED", "THREATENS", "UNCLEAR", "goal_ref"]
