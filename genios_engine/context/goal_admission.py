"""L3 admits — or holds, or rejects — a goal L2 proposed for a piece of work (GeniOS-012 S29.U3).

`speedrun008/GeniOS-008/00-ARCHITECTURE.md` "Goals", `GoalProposal`: L2 proposes, L3 admits by CODE, a human approves.

  HOLD   a duplicate — the same work already has a goal line, pending or accepted, or one the founder rejected
         lately, whoever proposed it (the drafter's lines carry the work's `file_id`, an L2 proposal its `file:` ref);
         and the same goal in other words from ANOTHER piece of work — which then SERVES that goal (G012 H-19,
         `company_brief_store.add_work`): a goal is many files' work, and the card of each carries it once it is live;
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

#: The work a line was BORN from: an L2 proposal's `file:` ref, or a drafter pattern's `file_id` — never a piece of work
#: that only serves it (`company_brief_store.SERVES`, G012 H-19), which may still have a goal of its own.
_SAME_WORK = text(
    "select count(*) from company_brief_lines where org_id = :o and section = 'goals' "
    "   and jsonb_typeof(evidence) = 'array' "
    "   and (evidence @> jsonb_build_array(cast(:file_ref as text)) "
    "        or exists (select 1 from jsonb_array_elements(evidence) e where e->>'file_id' = :file_id)) "
    "   and (status in ('proposed', 'accepted') or (status = 'rejected' and decided_at > :quiet))")
_GOAL_LINES = text(
    "select line_id, text, status from company_brief_lines where org_id = :o and section = 'goals' "
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
#: G012 H-17 · the senders of the mail in the work's own file — the file's correlations' members.
_FILE_SENDERS = text(
    "select distinct se.actor->>'email' as sender from context_correlations k "
    "  join context_correlation_members m on m.org_id = k.org_id and m.correlation_id = k.correlation_id "
    "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
    " where k.org_id = :o and k.anchor_node_id = :file")
_OUR_SIGNALS = text(
    "select count(*) from qualified_signals where org_id = :o and signal_id = any(:ids) and direction = 'outbound'")


@dataclass(frozen=True, slots=True)
class GoalAdmission:
    decision: str
    reason: str
    line_id: str | None = None


def _own_act(conn, org_id: str, evidence: tuple[str, ...], us: Any, file_id: str | None = None) -> bool:
    """Did the company act in this work — a mail we sent or a signal read from one, cited; or, G012 H-17, a mail we
    sent in the work's own file? The model cites what shows the GOAL (an investor's reply to our pitch), and the
    act that makes it ours is often the mail beside it: on the design partner's org (24 Oct) "Raise the seed round",
    proposed from an investor's file our founder had pitched, was held for citing the investor's reply."""
    events = [e for e in evidence if ":" not in e]
    signals = [e.split(":", 1)[1] for e in evidence if e.startswith("sig:")]
    if events and any(us.is_us(r.sender) for r in conn.execute(_OUR_MAIL, {"o": org_id, "ids": events})):
        return True
    if signals and conn.execute(_OUR_SIGNALS, {"o": org_id, "ids": signals}).scalar():
        return True
    return bool(file_id) and any(us.is_us(r.sender) for r in conn.execute(_FILE_SENDERS, {"o": org_id, "file": file_id}))


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
    if conn.execute(_SAME_WORK, {"o": org_id, "file_ref": subject_ref, "file_id": file_id,
                                 "quiet": at - timedelta(days=REJECTED_QUIET_DAYS)}).scalar():
        return GoalAdmission(HOLD, "duplicate: this work already has a goal line")
    quiet = at - timedelta(days=REJECTED_QUIET_DAYS)
    same = next((r for r in conn.execute(_GOAL_LINES, {"o": org_id, "quiet": quiet})
                 if same_goal(proposal.statement, r.text)), None)
    if same is not None:
        # G012 H-19 · the same goal from another piece of work: that work SERVES it (never for a goal the founder
        # rejected — the company is not pursuing it).
        if same.status != "rejected" and subject_ref.startswith("file:"):
            store.add_work(conn, org_id=org_id, line_id=same.line_id, work_ref=subject_ref, at=at,
                           why=proposal.why)
            return GoalAdmission(HOLD, "duplicate: the same goal in other words is already a goal line — this work "
                                       "now serves it", same.line_id)
        return GoalAdmission(HOLD, "duplicate: the same goal in other words is already a goal line")
    if conn.execute(_THIS_WEEK, {"o": org_id, "by": PROPOSED_BY, "since": at - timedelta(days=7)}).scalar() \
            >= WEEKLY_CAP:
        return GoalAdmission(HOLD, f"over the weekly cap of {WEEKLY_CAP}")
    if not _own_act(conn, org_id, proposal.evidence, us, file_id if subject_ref.startswith("file:") else None):
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
