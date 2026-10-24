"""L3 admits — or holds, or rejects — a goal L2 proposed for a piece of work (GeniOS-012 S29.U3).

`speedrun008/GeniOS-008/00-ARCHITECTURE.md` "Goals", `GoalProposal`: L2 proposes, L3 admits by CODE, a human approves.

  HOLD   a duplicate — the same work already has a goal line, pending or accepted, or one the founder rejected
         lately, whoever proposed it (the drafter's lines carry the work's `file_id`, an L2 proposal its `file:` ref);
  HOLD   over the weekly cap (D12: 3 a week per tenant) — the founder is asked, never flooded;
  HOLD   no evidence of the company's OWN act (we applied, wrote, met): a goal is something the company pursues;
  REJECT a statement the brief cannot hold as one line;
  ADMIT  writes a PENDING brief `goals` line (`platform/company_brief_store.propose`) — never an approved goal. The
         sweep's goal sync (`context/goals`) then shows it as `proposed`, and the founder's one click makes it real.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.goals import GoalProposal

ADMIT, HOLD, REJECT = "admit", "hold", "reject"
#: D12 · the goals L2 may propose to one tenant in a week.
WEEKLY_CAP = 3
#: Who a line says proposed it.
PROPOSED_BY = "l2"
#: How long a goal the founder rejected keeps the same work from being proposed again (the brief's own quiet).
REJECTED_QUIET_DAYS = 90

_SAME_WORK = text(
    "select count(*) from company_brief_lines where org_id = :o and section = 'goals' "
    "   and (evidence::text like :file_ref or evidence::text like :file_id) "
    "   and (status in ('proposed', 'accepted') or (status = 'rejected' and decided_at > :quiet))")
_GOAL_LINES = text(
    "select text from company_brief_lines where org_id = :o and section = 'goals' "
    "   and (status in ('proposed', 'accepted') or (status = 'rejected' and decided_at > :quiet))")
#: G012 H-16 · how much of a goal's words another goal line may share before it is the same goal in other words —
#: "Raise the pre-seed round" proposed from five investors' files is one goal, admitted once.
SAME_GOAL_SHARE = 0.6
_PLAIN = frozenset("a an the and or of to for with from into on in by our your its this that we us it is be "
                   "get keep make".split())
_THIS_WEEK = text(
    "select count(*) from company_brief_lines where org_id = :o and section = 'goals' and proposed_by = :by "
    "   and proposed_at > :since")
_OUR_MAIL = text(
    "select actor->>'email' as sender from source_events where org_id = :o and event_id = any(:ids)")
_OUR_SIGNALS = text(
    "select count(*) from qualified_signals where org_id = :o and signal_id = any(:ids) and direction = 'outbound'")


@dataclass(frozen=True, slots=True)
class GoalAdmission:
    decision: str
    reason: str
    line_id: str | None = None


def _own_act(conn, org_id: str, evidence: tuple[str, ...], us: Any) -> bool:
    """Does the proposal cite an act of the company's own — a mail we sent, a signal read from one?"""
    events = [e for e in evidence if ":" not in e]
    signals = [e.split(":", 1)[1] for e in evidence if e.startswith("sig:")]
    if events and any(us.is_us(r.sender) for r in conn.execute(_OUR_MAIL, {"o": org_id, "ids": events})):
        return True
    return bool(signals) and bool(conn.execute(_OUR_SIGNALS, {"o": org_id, "ids": signals}).scalar())


def _content(words: str) -> frozenset[str]:
    import re
    return frozenset(w for w in re.findall(r"[a-z0-9₹$]+", str(words or "").casefold()) if w not in _PLAIN and len(w) > 1)


def same_goal(a: str, b: str) -> bool:
    """Two goal statements that share most of their content words are one goal in other words."""
    x, y = _content(a), _content(b)
    return bool(x and y) and len(x & y) >= SAME_GOAL_SHARE * min(len(x), len(y))


def admit_proposal(conn, *, org_id: str, proposal: GoalProposal, subject_ref: str, us: Any,
                   at: datetime) -> GoalAdmission:
    """L3's ruling on one proposal for the work `subject_ref` (`file:<id>`), on the caller's transaction."""
    from genios_engine.platform import company_brief_store as store

    file_id = subject_ref.split(":", 1)[1] if subject_ref.startswith("file:") else subject_ref
    if conn.execute(_SAME_WORK, {"o": org_id, "file_ref": f"%{subject_ref}%", "file_id": f'%"{file_id}"%',
                                 "quiet": at - timedelta(days=REJECTED_QUIET_DAYS)}).scalar():
        return GoalAdmission(HOLD, "duplicate: this work already has a goal line")
    quiet = at - timedelta(days=REJECTED_QUIET_DAYS)
    if any(same_goal(proposal.statement, r.text) for r in conn.execute(_GOAL_LINES, {"o": org_id, "quiet": quiet})):
        return GoalAdmission(HOLD, "duplicate: the same goal in other words is already a goal line")
    if conn.execute(_THIS_WEEK, {"o": org_id, "by": PROPOSED_BY, "since": at - timedelta(days=7)}).scalar() \
            >= WEEKLY_CAP:
        return GoalAdmission(HOLD, f"over the weekly cap of {WEEKLY_CAP}")
    if not _own_act(conn, org_id, proposal.evidence, us):
        return GoalAdmission(HOLD, "no evidence of the company's own act")
    try:
        line_id = store.propose(conn, org_id=org_id, section="goals", words=proposal.statement,
                                proposed_by=PROPOSED_BY, at=at, evidence=[subject_ref, *proposal.evidence])
    except ValueError as exc:
        return GoalAdmission(REJECT, f"not a brief line: {exc}")
    if line_id is None:
        return GoalAdmission(HOLD, "duplicate: the brief already says it, or the founder rejected it lately")
    return GoalAdmission(ADMIT, "a pending goals line", line_id)


__all__ = ["ADMIT", "GoalAdmission", "HOLD", "PROPOSED_BY", "REJECT", "WEEKLY_CAP", "admit_proposal"]
