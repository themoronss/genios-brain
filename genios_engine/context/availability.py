"""`person.availability` — the graph's record of who is away, and the reads over it.

One fact per WINDOW on the person node: field `person.availability`, value
`{kind, from, to, cover}`. The window's start is its identity, so a person can hold several
windows at once (leave next week AND a conference next month) while a later message restating the
same window supersedes it instead of stacking a duplicate. That is the one place this field departs
from the (subject, field) → one active row rule every other fact follows, which is why the health
check and the merge repair partition this field by window start (see WINDOWED_FIELDS).

Writes come from two lanes: L2's extraction (an OOO auto-reply, "on leave 15–22", rank 2) and the
calendar structured lane (an outOfOffice event or an all-day "Leave" block, rank 3 — the calendar is
the system of record for its owner's time). Reads serve the reasoners (derived `owner.*` facts) and,
later, the device slice.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from genios_engine.context.graph_store import fact_write_action
from genios_engine.contracts.availability import ABSENT_KINDS, AVAILABILITY_KINDS
from genios_engine.platform.identity import norm_email
from genios_engine.platform.ids import new_id

AVAILABILITY_FIELD = "person.availability"

#: Fields whose active rows are keyed by (subject, field, value->>'from') rather than
#: (subject, field). Imported by the health check and the merge repair so neither mistakes two
#: windows for a duplicate.
WINDOWED_FIELDS: frozenset[str] = frozenset({AVAILABILITY_FIELD})

#: How long an OPEN-ENDED window counts as current. An auto-reply that never says when it ends is
#: evidence of absence as of that message, not forever: without a horizon, one vacation responder
#: would mark its owner unavailable for the rest of time. Shorter for the kinds that are short.
OPEN_ENDED_DAYS: dict[str, int] = {"leave": 14, "ooo": 14, "travel": 7, "sick": 3,
                                   "busy": 1, "partial": 1}

#: Kind → the status word the reasoners already understand (dependency_unit.OWNER_UNAVAILABLE,
#: resource_unit._UNAVAILABLE_STATUSES / _REDUCED_STATUSES). Kept to words BOTH units read.
STATUS_BY_KIND: dict[str, str] = {"leave": "on_leave", "sick": "on_leave",
                                  "ooo": "out_of_office", "travel": "out_of_office",
                                  "busy": "busy", "partial": "partial"}

#: Facts naming who owns a piece of work. Mirrors executive.assignment.OWNER_FIELDS (a higher
#: layer this module may not import).
OWNER_FIELDS: tuple[str, ...] = ("deal.owner", "relationship.owner", "commitment.owner")

#: How far ahead an upcoming absence is surfaced to a reasoner as `owner.next_unavailable`.
UPCOMING_HORIZON_DAYS = 30


def _family(kind: str) -> str:
    return "absent" if kind in ABSENT_KINDS else "reduced"


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _as_dict(value: Any) -> dict | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, dict) else None


def _canon(value: Any) -> str:
    """Order-independent JSON, so a jsonb round-trip (which reorders keys) compares equal."""
    return json.dumps(_as_dict(value) if not isinstance(value, dict) else value,
                      sort_keys=True, default=str)


@dataclass(frozen=True, slots=True)
class AvailabilityWindow:
    person_node_id: str
    person_key: str | None
    display_name: str | None
    kind: str
    start: date
    end: date | None
    cover: str | None
    authority_rank: int
    confidence: float
    occurred_at: datetime | None
    fact_version_id: str

    @property
    def effective_end(self) -> date:
        if self.end is not None:
            return self.end
        return self.start + timedelta(days=OPEN_ENDED_DAYS.get(self.kind, 14) - 1)

    @property
    def absent(self) -> bool:
        return self.kind in ABSENT_KINDS

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.effective_end

    def overlaps(self, start: date, end: date) -> bool:
        return self.start <= end and self.effective_end >= start

    def value(self) -> dict:
        return {"kind": self.kind, "from": self.start.isoformat(),
                "to": self.end.isoformat() if self.end else None, "cover": self.cover}

    def as_dict(self) -> dict:
        return {**self.value(), "person_node_id": self.person_node_id,
                "person": self.person_key, "name": self.display_name,
                "status": STATUS_BY_KIND[self.kind],
                "effective_to": self.effective_end.isoformat(),
                "authority_rank": self.authority_rank, "fact_version_id": self.fact_version_id}


def _window_from_row(r) -> AvailabilityWindow | None:
    """A stored row → a window. A row that does not parse is skipped, never guessed at."""
    v = _as_dict(r.value)
    if not v or v.get("kind") not in AVAILABILITY_KINDS:
        return None
    start = _as_date(v.get("from"))
    if start is None:
        return None
    end = _as_date(v.get("to")) if v.get("to") else None
    if end is not None and end < start:
        return None
    return AvailabilityWindow(
        person_node_id=r.subject_node_id, person_key=getattr(r, "canonical_key", None),
        display_name=getattr(r, "display_name", None), kind=v["kind"], start=start, end=end,
        cover=v.get("cover") or None, authority_rank=int(r.authority_rank or 1),
        confidence=float(r.confidence) if r.confidence is not None else 0.5,
        occurred_at=r.occurred_at, fact_version_id=r.fact_version_id)


# ── write ────────────────────────────────────────────────────────────────────────────────────

def _active_windows(conn, *, org_id: str, person_node_id: str) -> list:
    return conn.execute(text(
        "select fact_version_id, fact_id, subject_node_id, value, authority_rank, confidence, "
        "occurred_at from graph_facts where org_id=:o and subject_node_id=:s and field=:f "
        "and valid_to is null and status='active'"),
        {"o": org_id, "s": person_node_id, "f": AVAILABILITY_FIELD}).fetchall()


def write_availability_window(store, conn, *, org_id: str, person_node_id: str, value: dict,
                              occurred_at: datetime | None, event_id: str, source: str | None,
                              authority_rank: int, confidence: float, evidence: dict,
                              relevance: float | None = None,
                              from_stated: bool = True) -> str | None:
    """Write one window. Returns the new fact_version_id, or None (noop / corroboration /
    discrepancy). Same decision table as GraphStore.write_fact — authority-aware, out-of-order
    aware — keyed on the window start instead of the bare field.

    Beyond the per-window rule, a STATED window supersedes the earlier-asserted, overlapping,
    same-family windows it restates ("leave now 16–24" replaces "leave 15–22"): that is what
    "a later message changes the same window" means when the change moved the start date. A
    window whose start merely defaulted to the message date never displaces anything — it is
    corroboration of whatever stated window already covers that day.
    """
    start = str(value.get("from") or "")
    start_date = _as_date(start)
    if value.get("kind") not in AVAILABILITY_KINDS or start_date is None:
        return None
    rows = _active_windows(conn, org_id=org_id, person_node_id=person_node_id)
    windows = {r.fact_version_id: _window_from_row(r) for r in rows}
    held = next((r for r in rows if (_as_dict(r.value) or {}).get("from") == start), None)

    if held is None and not from_stated:
        # "I am out of office" on the 17th, while a stated 15–22 leave is on record: the same
        # absence seen again, not a new window starting on the 17th.
        covering = next((r for r in rows
                         if (w := windows.get(r.fact_version_id)) is not None
                         and _family(w.kind) == _family(value["kind"])
                         and w.covers(start_date)), None)
        if covering is not None:
            _corroborate(store, conn, org_id=org_id, fact_version_id=covering.fact_version_id,
                         event_id=event_id, source=source, evidence=evidence)
            return None

    action = fact_write_action(
        held_value_json=_canon(held.value) if held is not None else None,
        held_rank=held.authority_rank if held is not None else None,
        held_occurred_at=held.occurred_at if held is not None else None,
        new_value_json=_canon(value), new_rank=authority_rank, new_occurred_at=occurred_at)
    if action == "noop":
        _corroborate(store, conn, org_id=org_id, fact_version_id=held.fact_version_id,
                     event_id=event_id, source=source, evidence=evidence)
        return None
    if action == "discrepancy":
        store.write_discrepancy(conn, org_id=org_id, subject_node_id=person_node_id,
                                field=AVAILABILITY_FIELD,
                                held={"value": _as_dict(held.value), "rank": held.authority_rank},
                                challenger={"value": value, "rank": authority_rank,
                                            "source": source, "event_id": event_id})
        return None
    superseded: list[str] = []
    if action == "supersede":
        superseded.append(held.fact_version_id)
    if action in ("insert", "supersede") and from_stated:
        new_end = _as_date(value.get("to"))
        probe = AvailabilityWindow(person_node_id, None, None, value["kind"], start_date, new_end,
                                   None, authority_rank, confidence, occurred_at, "")
        for r in rows:
            w = windows.get(r.fact_version_id)
            if (w is None or r is held or _family(w.kind) != _family(probe.kind)
                    or not w.overlaps(probe.start, probe.effective_end)
                    or w.authority_rank > authority_rank):
                continue
            if occurred_at is not None and w.occurred_at is not None and w.occurred_at > occurred_at:
                continue                          # a newer statement is never displaced by an older
            superseded.append(r.fact_version_id)
    if superseded:
        conn.execute(text("update graph_facts set valid_to=now(), status='superseded' "
                          "where org_id=:o and fact_version_id = any(:ids)"),
                     {"o": org_id, "ids": superseded})
        store.resolve_discrepancies(conn, org_id=org_id, subject_node_id=person_node_id,
                                    field=AVAILABILITY_FIELD)

    status = "historical" if action == "historical" else "active"
    fv = new_id("factv")
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "value, value_type, status, authority_rank, confidence, relevance, occurred_at, "
        "created_by_event_id" + (", valid_to" if status == "historical" else "") + ") "
        "values (:fv, :fid, :o, :s, :f, cast(:val as jsonb), 'json', :st, :ar, :c, :rel, :oc, :ev"
        + (", now()" if status == "historical" else "") + ")"),
        {"fv": fv, "fid": held.fact_id if held is not None else f"avail:{person_node_id}:{start}",
         "o": org_id, "s": person_node_id, "f": AVAILABILITY_FIELD,
         "val": json.dumps(value, default=str), "st": status, "ar": authority_rank,
         "c": confidence, "rel": relevance, "oc": occurred_at, "ev": event_id})
    store._write_ref(conn, org_id=org_id, fact_version_id=fv, event_id=event_id, source=source,
                     evidence=evidence)
    return fv


def _corroborate(store, conn, *, org_id, fact_version_id, event_id, source, evidence) -> None:
    already = conn.execute(text(
        "select 1 from graph_source_refs where fact_version_id=:fv and event_id=:e limit 1"),
        {"fv": fact_version_id, "e": event_id}).first()
    if already is None:
        store._write_ref(conn, org_id=org_id, fact_version_id=fact_version_id, event_id=event_id,
                         source=source, evidence={**(evidence or {}), "corroborates": True})


def retire_source_windows(conn, *, org_id: str, source: str, source_object_id: str,
                          keep_from: str | None = None) -> list[str]:
    """Supersede the active windows one source object asserted — a calendar block that was moved
    (every window it asserted except the one starting `keep_from`) or cancelled (all of them).
    Returns the fact_version_ids retired (ids, not a count: reversible).

    Keyed on the evidence's `source_object`, which the calendar lane writes, so an email-derived
    window of the same person is never touched by a calendar edit.
    """
    rows = conn.execute(text(
        "select distinct f.fact_version_id, f.value->>'from' as start from graph_facts f "
        "join graph_source_refs sr on sr.fact_version_id = f.fact_version_id "
        "and sr.org_id = f.org_id "
        "where f.org_id=:o and f.field=:f and f.valid_to is null and f.status='active' "
        "and sr.source=:src and sr.evidence->>'source_object' = :soid"),
        {"o": org_id, "f": AVAILABILITY_FIELD, "src": source, "soid": source_object_id}).fetchall()
    ids = [r.fact_version_id for r in rows if keep_from is None or r.start != keep_from]
    if ids:
        conn.execute(text("update graph_facts set valid_to=now(), status='superseded' "
                          "where org_id=:o and fact_version_id = any(:ids)"),
                     {"o": org_id, "ids": ids})
    return ids


# ── read ─────────────────────────────────────────────────────────────────────────────────────

_READ_SQL = (
    "select f.fact_version_id, f.subject_node_id, f.value, f.authority_rank, f.confidence, "
    "f.occurred_at, n.canonical_key, n.display_name "
    "from graph_facts f join graph_nodes n on n.org_id = f.org_id "
    "and n.node_id = f.subject_node_id and n.valid_to is null "
    "where f.org_id=:o and f.field='" + AVAILABILITY_FIELD + "' "
    "and f.valid_to is null and f.status='active'")


def _read(conn, org_id: str, extra: str = "", params: dict | None = None) -> list[AvailabilityWindow]:
    rows = conn.execute(text(_READ_SQL + extra), {"o": org_id, **(params or {})}).fetchall()
    return [w for w in (_window_from_row(r) for r in rows) if w is not None]


def availability_for_person(conn, *, org_id: str, on: date, person_node_id: str | None = None,
                            email: str | None = None,
                            horizon_days: int = UPCOMING_HORIZON_DAYS) -> list[AvailabilityWindow]:
    """Current and upcoming windows for one person (by node id or email), soonest first."""
    if person_node_id:
        windows = _read(conn, org_id, " and f.subject_node_id=:s", {"s": person_node_id})
    elif email and (key := norm_email(email)):
        windows = _read(conn, org_id, " and n.canonical_key=:k", {"k": key})
    else:
        return []
    horizon = on + timedelta(days=horizon_days)
    return sorted((w for w in windows if w.effective_end >= on and w.start <= horizon),
                  key=lambda w: (w.start, w.kind))


def org_availability(conn, *, org_id: str, start: date, end: date) -> list[AvailabilityWindow]:
    """Every window in the org overlapping [start, end] — the team view."""
    return sorted((w for w in _read(conn, org_id) if w.overlaps(start, end)),
                  key=lambda w: (w.start, w.person_key or "", w.kind))


def load_org_windows(conn, *, org_id: str) -> dict[str, list[AvailabilityWindow]]:
    """All active windows, indexed by the keys an owner fact can carry: the person's canonical key
    (email) and, for name-valued owner fields, the person's display name. One query per sweep."""
    out: dict[str, list[AvailabilityWindow]] = {}
    for w in _read(conn, org_id):
        for key in {(w.person_key or "").strip().lower(), (w.display_name or "").strip().casefold()}:
            if key:
                out.setdefault(key, []).append(w)
    return out


def current_window(windows: list[AvailabilityWindow], on: date) -> AvailabilityWindow | None:
    """The window in force on `on`. Absence outranks reduced capacity, then authority, then the
    most recent statement."""
    live = [w for w in windows if w.covers(on)]
    if not live:
        return None
    return max(live, key=lambda w: (w.absent, w.authority_rank,
                                    w.occurred_at.timestamp() if w.occurred_at else 0.0))


def _owner_key(facts: dict) -> str | None:
    for field in OWNER_FIELDS:
        record = facts.get(field)
        value = record.get("value") if isinstance(record, dict) and "value" in record else record
        if isinstance(value, str) and value.strip():
            return norm_email(value) or value.strip().casefold()
    return None


def _record(value: Any, w: AvailabilityWindow) -> dict:
    return {"value": value, "confidence": w.confidence, "authority_rank": w.authority_rank,
            "occurred_at": w.occurred_at, "fact_version_id": w.fact_version_id,
            "independence_group": "graph:person.availability", "src_count": 1}


def owner_availability_facts(facts: dict, windows_by_key: dict[str, list[AvailabilityWindow]],
                             *, on: date) -> dict[str, dict]:
    """Derived `owner.*` facts for a node whose owner is on record.

    `owner.availability` / `owner.status` carry the status word the dependency and resource units
    already read; `owner.availability_bp` is 0 only for a full absence — for busy/partial the
    resource unit's own tunable status mapping stays in charge, because a basis-point figure would
    claim a measurement nobody made. `owner.next_unavailable` names the next absence inside the
    horizon, which is what lets "her docs are due on the 19th, she is away from the 15th" be seen.
    Nothing is emitted when no window applies: the absence of a leave record is not evidence of
    availability.
    """
    key = _owner_key(facts)
    windows = windows_by_key.get(key or "") if key else None
    if not windows:
        return {}
    out: dict[str, dict] = {}
    now = current_window(windows, on)
    if now is not None:
        status = STATUS_BY_KIND[now.kind]
        out["owner.availability"] = _record(status, now)
        out["owner.status"] = _record(status, now)
        out["owner.availability_window"] = _record(now.value(), now)
        if now.absent:
            out["owner.availability_bp"] = _record(0, now)
    horizon = on + timedelta(days=UPCOMING_HORIZON_DAYS)
    upcoming = sorted((w for w in windows if w.absent and on < w.start <= horizon),
                      key=lambda w: w.start)
    if upcoming:
        out["owner.next_unavailable"] = _record(upcoming[0].value(), upcoming[0])
    return out
