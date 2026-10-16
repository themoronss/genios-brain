"""The day, ordered — by code, from the expert's own judgment of each file (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 2, tree `yc2_w27_s15` M44.C3.L-logic.V0.U01. The 5 Oct plan asked a model
to order the day. Under `06` D1 (answered 10 Oct) a file's importance and urgency ARE its appraisal, mapped by code —
so the day is ordered from the expert's own judgment, never by a second model asked what matters (s15-D1).

TODAY'S FIVE. Always in, whatever else the day holds: a meeting today (in the org's timezone), and a dated deadline
or promise within 48 hours, overdue included. When those alone pass five, the five FLEXES and says by how many. The
rest of the five are the open decisions — in the book re-rank's order (`reason/brief_ranking.book_rank`, already on
for the tenant: under D1 a decision's utility is the expert's appraisal, and a card left unread steps down), so the
brief and `GET /v1/intelligence/brief` agree on #1; a decision with no open card after every carded one, by its
appraisal — then the questions, the oldest asked first.

THE OTHER SECTIONS. Your desk. What changed, newest first. STUCK: a decision not among today's five whose move is
yours, quiet past the second rung (14 days). ASKED: the questions not among today's five. Your PROMISES due, soonest
first. MEETINGS: the rest of the day's meetings and the meetings nobody followed up, soonest first. WATCHING: a
waiting file once it is quiet past the first rung, 7 days — s15-D4: F08 and F14 in; F39, F40 and F43, quiet two
days at most, out (`03` s15-F9) — the quietest first. Each section is capped (`contracts/morning_brief.CAPS`); what
it cut is counted, never dropped silently — a decision that is neither in today's five nor stuck is counted under
today.

THE WORD BUDGET. `fit` keeps a rendered brief inside its words by cutting from the last section back — watching
first — and never an always-in item of today's; the cut is counted.

Pure: items in, sections out. No I/O, no clock, no model.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from genios_engine.contracts import morning_brief as B

#: The first rung: a waiting file is watched once it is quieter than this (s15-D4).
WATCH_AFTER_DAYS = 7
#: The second rung: a file whose move is yours is stuck once it is quieter than this.
STUCK_AFTER_DAYS = 14
#: A dated deadline or promise this close is always in today's five.
ALWAYS_IN = timedelta(hours=48)
#: An appraisal's level, as it orders: high before medium before low, an unappraised one last.
_LEVEL = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Ordered:
    """The day's items by section, in the brief's order; what each section cut; how far today flexed."""
    sections: tuple[tuple[str, tuple[B.Item, ...]], ...]
    cut: tuple[tuple[str, int], ...]
    flexed: int
    always: frozenset[str] = frozenset()          # the always-in items' ids

    def items(self, section: str) -> tuple[B.Item, ...]:
        return next((items for name, items in self.sections if name == section), ())


def always_in(item: B.Item, *, now: datetime, tz: str) -> bool:
    """A meeting today, or a dated deadline or promise within 48 hours (overdue included). A decision's instant is
    its move's date, a promise's its due date, a meeting's its start; a question's is when it was asked — no
    deadline, so never always in."""
    if item.at is None:
        return False
    if item.kind == B.MEETING:
        zone = ZoneInfo(tz)
        return item.at.astimezone(zone).date() == now.astimezone(zone).date()
    return item.kind in (B.DECISION, B.PROMISE) and item.at <= now + ALWAYS_IN


def _decision(item: B.Item):
    return (item.book_score_bp is None, -(item.book_score_bp or 0), _LEVEL.get(item.stakes, 3),
            _LEVEL.get(item.urgency, 3), -(item.quiet_days or 0.0), item.item_id)


def _at(item: B.Item):
    return (item.at is None, item.at.timestamp() if item.at else 0.0, item.item_id)


def order(items: Iterable[B.Item], *, now: datetime, tz: str) -> Ordered:
    """The day's items in their sections, each capped, the cut counted."""
    items = list(items)
    of = {kind: [i for i in items if i.kind == kind] for kind in B.KINDS}
    always = sorted((i for i in items if always_in(i, now=now, tz=tz)), key=_at)
    ids = {i.item_id for i in always}
    decisions = sorted((i for i in of[B.DECISION] if i.item_id not in ids), key=_decision)
    questions = sorted((i for i in of[B.QUESTION] if i.item_id not in ids), key=_at)
    room = max(0, B.CAPS[B.TODAY] - len(always))
    chosen = (decisions + questions)[:room]
    today = always + chosen
    seated = {i.item_id for i in today}
    stuck = [i for i in decisions if i.item_id not in seated and i.our_move
             and (i.quiet_days or 0) > STUCK_AFTER_DAYS]
    unseated = [i for i in decisions if i.item_id not in seated and i not in stuck]
    sections = {
        B.TODAY: today,
        B.YOUR_DESK: of[B.DESK],
        B.CHANGED: sorted(of[B.CHANGE], key=lambda i: (-(i.at.timestamp() if i.at else 0.0), i.item_id)),
        B.STUCK: stuck,
        B.ASKED: [i for i in questions if i.item_id not in seated],
        B.PROMISES: sorted((i for i in of[B.PROMISE] if i.item_id not in seated), key=_at),
        B.MEETINGS: sorted((i for i in of[B.MEETING] + of[B.NO_FOLLOW_UP] if i.item_id not in seated), key=_at),
        B.WATCHING: sorted((i for i in of[B.WATCHED] if (i.quiet_days or 0) > WATCH_AFTER_DAYS),
                           key=lambda i: (-(i.quiet_days or 0.0), i.item_id)),
    }
    out, cut = [], []
    for name in B.SECTIONS:
        held = sections[name]
        cap = max(B.CAPS[name], len(always)) if name == B.TODAY else B.CAPS[name]
        dropped = len(unseated) if name == B.TODAY else max(0, len(held) - cap)
        if dropped:
            cut.append((name, dropped))
        out.append((name, tuple(held[:cap])))
    return Ordered(sections=tuple(out), cut=tuple(cut), flexed=max(0, len(always) - B.CAPS[B.TODAY]),
                   always=frozenset(ids))


def fit(ordered: Ordered, words_of: Callable[[str, B.Item], int], *, budget: int) -> Ordered:
    """Keep the brief inside `budget` words: cut from the last section back, never an always-in item."""
    names = [name for name, _items in ordered.sections]
    held = [list(items) for _name, items in ordered.sections]
    total = sum(words_of(n, i) for n, items in zip(names, held) for i in items)
    cut = dict(ordered.cut)
    for index in range(len(names) - 1, -1, -1):
        for item in reversed(list(held[index])):
            if total <= budget:
                break
            if item.item_id in ordered.always:
                continue
            held[index].remove(item)
            total -= words_of(names[index], item)
            cut[names[index]] = cut.get(names[index], 0) + 1
    return Ordered(sections=tuple((n, tuple(h)) for n, h in zip(names, held)),
                   cut=tuple((n, cut[n]) for n in names if cut.get(n)), flexed=ordered.flexed,
                   always=ordered.always)


__all__ = ["ALWAYS_IN", "Ordered", "STUCK_AFTER_DAYS", "WATCH_AFTER_DAYS", "always_in", "fit", "order"]
