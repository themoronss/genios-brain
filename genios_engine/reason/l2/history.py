"""GeniOS-008 L2 R3 · the History Assembler — comparable past work, and how it went (spec §7, *proposed*).

The STEP-12 dossier already tells a file's OWN past (what was judged before, how its cards ended, its
numbers with their n). What it never told was the company's past with OTHER work of the same kind: the
last investors who went quiet after the deck, the last program applications. A 30-year chief of staff
reasons from exactly that. So this reads, for the kind of work the subject is, the most recently touched
other files of that kind — what the file holds, whose move it was, the latest situation anchored on it
and how it ended, and the last thing the expert advised on it — each printed with a `case:` id the model
may cite in `history_used`, and nothing inferred.

Bounded (`MAX_CASES`), newest first, two reads for all the cases together. An org-level reader, as every file reader.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.reasoning_result import HistoricalCase, HistoricalContext

MAX_CASES = 5

#: L2 rebuild A4 · the latest situation and the latest valid review of EVERY comparable file in one read each
#: (was two reads per case — up to ten a subject).
_LAST_SITUATIONS = text(
    "select distinct on (anchor_node_id) anchor_node_id, situation_type, status, resolved_by, resolved_at "
    "  from context_situations where org_id = :o and anchor_node_id = any(:fs) "
    " order by anchor_node_id, last_seen_at desc nulls last, situation_id")

_LAST_REVIEWS = text(
    "select distinct on (file_id) file_id, review ->> 'mode' as mode, review -> 'next_move' ->> 'what' as move, "
    "       reviewed_at "
    "  from expert_reviews where org_id = :o and file_id = any(:fs) and status = 'valid' "
    " order by file_id, reviewed_at desc")


def _when(at: datetime | None) -> str:
    return at.strftime("%Y-%m-%d") if at is not None else "unknown"


def comparable(files: Sequence[Any], *, work_kind: str | None, exclude: str | None) -> list[Any]:
    """The other files of the same kind of work, most recently touched first. Pure."""
    if not work_kind:
        return []
    same = [f for f in files if getattr(f, "work_kind", None) == work_kind and str(f.file_id) != str(exclude)]
    same.sort(key=lambda f: (f.last_touch is None, -(f.last_touch.timestamp() if f.last_touch else 0),
                             str(f.file_id)))
    return same[:MAX_CASES]


def history_for(conn, org_id: str, *, files: Sequence[Any], work_kind: str | None,
                exclude: str | None) -> HistoricalContext:
    cases = []
    picked = comparable(files, work_kind=work_kind, exclude=exclude)
    if not picked:
        return HistoricalContext(cases=())
    ids = [str(f.file_id) for f in picked]
    sits = {str(r.anchor_node_id): r for r in conn.execute(_LAST_SITUATIONS, {"o": org_id, "fs": ids})}
    revs = {str(r.file_id): r for r in conn.execute(_LAST_REVIEWS, {"o": org_id, "fs": ids})}
    for f in picked:
        sit, rev = sits.get(str(f.file_id)), revs.get(str(f.file_id))
        outcome = None
        if sit is not None and sit.status and sit.status not in ("active", "partial"):
            outcome = f"{sit.situation_type} {sit.status}" + (f" by {sit.resolved_by}" if sit.resolved_by else "")
        bits = [f"{len(f.events)} touches, {_when(f.first_touch)} → {_when(f.last_touch)}"]
        if f.whose_move:
            bits.append(f"the move was {f.whose_move}")
        if f.open_asks:
            bits.append(f"{len(f.open_asks)} open asks")
        if rev is not None and rev.mode:
            bits.append(f"last advised ({_when(rev.reviewed_at)}): {rev.mode}" + (f" — {rev.move}" if rev.move else ""))
        cases.append(HistoricalCase(case_id=f"case:{f.file_id}", subject=str(f.counterparty),
                                    work_kind=f.work_kind, outcome=outcome, last_touch=f.last_touch,
                                    summary="; ".join(bits)))
    return HistoricalContext(cases=tuple(cases))


__all__ = ["MAX_CASES", "comparable", "history_for"]
