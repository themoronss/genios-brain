"""The brief, kept — once per seat per local day, and your mark on its lines (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 items 4-5, tree `yc2_w27_s15` M44.C4.L-data.V0.U01, over
`migrations/0230_morning_briefs.sql`. A brief is composed for a seat's local day on whichever tick comes first after
the hour, or on read — so two composers can meet. The row is the claim:

  `keep`         writes the brief once; a second composer of the same seat's day writes nothing and is handed the
                 first one's brief, as it was kept;
  `read`         one seat's brief of one local day, read back equal to what was kept (`contracts/morning_brief`);
  `last_before`  the seat's last brief before a day — what "changed since your last brief" is read against;
  `mark_line`    your mark on a line — useful, or not useful with your words — one per line per person, a later
                 mark replacing an earlier one and never the other way round; the line names its brief;
  `marks_for`    the marks on one brief, by line.

Recorded only: STEP-16 turns marks into proposals you accept. Pure SQL over one connection; the caller owns the
transaction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import text

from genios_engine.contracts.morning_brief import Brief

#: Your mark on a line — closed, as 0230's check is.
USEFUL = "useful"
NOT_USEFUL = "not_useful"
MARKS: tuple[str, ...] = (USEFUL, NOT_USEFUL)

_KEEP = text(
    "insert into morning_briefs (org_id, seat_id, local_date, timezone, as_of, one_line, lines, brief, "
    "       material_digest, written_by, why, model, tier, cost_micro_usd) "
    "values (:o, :s, :d, :tz, :as_of, :one, cast(:lines as jsonb), cast(:brief as jsonb), :digest, :by, :why, "
    "        :model, :tier, :cost) "
    "on conflict (org_id, seat_id, local_date) do nothing returning seat_id")

_READ = text(
    "select brief from morning_briefs where org_id = :o and seat_id = :s and local_date = :d")

_LAST_BEFORE = text(
    "select brief from morning_briefs where org_id = :o and seat_id = :s and local_date < :d "
    " order by local_date desc limit 1")

#: The brief a line stands in — its lines hold it (jsonb containment over the array of lines).
_LINE_BRIEF = text(
    "select seat_id, local_date from morning_briefs "
    " where org_id = :o and lines @> cast(:probe as jsonb) order by local_date desc limit 1")

_MARK = text(
    "insert into morning_brief_marks (org_id, line_id, marked_by, seat_id, local_date, mark, words, marked_at) "
    "values (:o, :l, :by, :s, :d, :m, :w, :at) "
    "on conflict (org_id, line_id, marked_by) do update set mark = excluded.mark, words = excluded.words, "
    "       marked_at = excluded.marked_at "
    " where morning_brief_marks.marked_at <= excluded.marked_at "
    "returning mark, words, marked_at")

_MARKS = text(
    "select line_id, marked_by, seat_id, local_date, mark, words, marked_at from morning_brief_marks "
    " where org_id = :o and seat_id = :s and local_date = :d order by line_id, marked_by")


@dataclass(frozen=True, slots=True)
class Mark:
    line_id: str
    marked_by: str
    seat_id: str
    local_date: date
    mark: str
    words: str | None
    marked_at: datetime


def keep(conn, brief: Brief) -> tuple[Brief, bool]:
    """Keep `brief` once for its seat's local day. Returns the brief that stands — this one when it was written
    (True), the first composer's when one already was (False)."""
    row = conn.execute(_KEEP, {
        "o": brief.org_id, "s": brief.seat_id, "d": brief.local_date, "tz": brief.timezone, "as_of": brief.as_of,
        "one": brief.one_line, "lines": json.dumps([l.as_mapping() for l in brief.lines]),
        "brief": json.dumps(brief.as_mapping()), "digest": brief.material_digest, "by": brief.written_by,
        "why": brief.why, "model": brief.model, "tier": brief.tier, "cost": brief.cost_micro_usd}).first()
    if row is not None:
        return brief, True
    return read(conn, brief.org_id, brief.seat_id, brief.local_date), False


def _brief(row) -> Brief | None:
    if row is None:
        return None
    raw = row.brief if isinstance(row.brief, dict) else json.loads(row.brief)
    return Brief.from_mapping(raw)


def read(conn, org_id: str, seat_id: str, local_date: date) -> Brief | None:
    """The seat's brief of that local day, as kept — or None."""
    return _brief(conn.execute(_READ, {"o": org_id, "s": seat_id, "d": local_date}).first())


def last_before(conn, org_id: str, seat_id: str, local_date: date) -> Brief | None:
    """The seat's last brief before `local_date` — or None."""
    return _brief(conn.execute(_LAST_BEFORE, {"o": org_id, "s": seat_id, "d": local_date}).first())


def mark_line(conn, *, org_id: str, line_id: str, marked_by: str, mark: str, words: str | None,
         at: datetime) -> Mark:
    """Keep `marked_by`'s mark on a line. ValueError for a mark that is not one, or not useful without words;
    LookupError for a line no kept brief holds. A mark older than the one kept changes nothing: the kept one is
    returned."""
    if mark not in MARKS:
        raise ValueError(f"a mark is one of {MARKS}, not {mark!r}")
    said = " ".join(str(words or "").split()) or None
    if mark == NOT_USEFUL and said is None:
        raise ValueError("not useful, because — the words say why")
    if mark == USEFUL and said is not None:
        raise ValueError("a useful mark needs no words")
    where = conn.execute(_LINE_BRIEF, {"o": org_id, "probe": json.dumps([{"line_id": line_id}])}).first()
    if where is None:
        raise LookupError(f"no kept brief holds line {line_id}")
    row = conn.execute(_MARK, {"o": org_id, "l": line_id, "by": marked_by, "s": where.seat_id,
                               "d": where.local_date, "m": mark, "w": said, "at": at}).first()
    if row is None:
        held = next(m for m in marks_for(conn, org_id, where.seat_id, where.local_date).get(line_id, ())
                    if m.marked_by == marked_by)
        return held
    return Mark(line_id=line_id, marked_by=marked_by, seat_id=where.seat_id, local_date=where.local_date,
                mark=row.mark, words=row.words, marked_at=row.marked_at)


def marks_for(conn, org_id: str, seat_id: str, local_date: date) -> dict[str, tuple[Mark, ...]]:
    """Every mark on one brief, by line — each person's latest."""
    out: dict[str, list[Mark]] = {}
    for r in conn.execute(_MARKS, {"o": org_id, "s": seat_id, "d": local_date}):
        out.setdefault(r.line_id, []).append(Mark(line_id=r.line_id, marked_by=r.marked_by, seat_id=r.seat_id,
                                                  local_date=r.local_date, mark=r.mark, words=r.words,
                                                  marked_at=r.marked_at))
    return {line: tuple(marks) for line, marks in out.items()}


__all__ = ["MARKS", "Mark", "NOT_USEFUL", "USEFUL", "keep", "last_before", "mark_line", "marks_for", "read"]
