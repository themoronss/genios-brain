"""L1.5.5 · the conflict STORE — `signal_conflicts`, the table nothing created and nothing wrote.

Doc 07's storage map lists `signal_conflicts` as NEW, permanent, cascade-on-tenant-deletion, and
doc 05 gives its DDL. Neither existed. ALG-12 meanwhile runs on every sweep in production —
`acquire/sync_runner._detect_conflicts` compares every claim a page extracted — and its answer
was returned on a `SyncSummary` to callers that read the counts and dropped the conflicts. So a
disagreement between a signed PDF and the email that quotes it was computed, priced into an
escalation, and then garbage-collected. `contracts/conflict.py` describes claims as things
*"written to `signal_conflicts.claims`"*, which was not true of any row anywhere.

**This module is L1.7.4's sibling and follows its shape.** One row per detected conflict; the
claims are stored WHOLE rather than as pointers, because unlike an extraction (which lives once
in `l1_extraction_results` and is referenced) a conflict's two claims are a *judgement made at a
moment* — the value, the authority class, and the rank that class had AT DETECTION TIME. Doc 05
is explicit that a re-tuned authority table must not silently re-decide a stored conflict, and a
row that pointed at today's ranks would do exactly that.

**Content-addressed ids.** `conflict_id` is a digest over the org, the subject, the field, the
resolution and both claims — everything except `detected_at`. A replayed sweep re-detects the
same disagreement and must UPSERT its own row; an id from a counter or a uuid would append a
second copy of one fact on every re-run, and "how many conflicts does this tenant have" would
count replays.

**It never fails a sweep.** Persisting is downstream of capture, exactly like the grouping and
the detection above it: a database error costs the sweep its conflict record, never its mail.

PURITY. No clock — `detected_at` comes from the detection, which took it from the sweep's frozen
`eval_time`. No float: `Money.minor_units` is an int and `authority_rank` is an int, and both go
into jsonb through pydantic's own JSON mode rather than through `float()`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Protocol, Sequence

from genios_engine.platform.db import get_engine
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.conflict_store")

CONFLICT_TABLE = "signal_conflicts"


@dataclass(frozen=True)
class ConflictRow:
    """One stored disagreement, in the shape the table holds it.

    `claims` and `resolved_value` are plain JSON structures rather than `ConflictClaim` objects
    on purpose: this type is what crosses the database boundary in BOTH directions, and a row
    read back from jsonb cannot rehydrate into a frozen pydantic model without asserting that
    today's contract still validates a row written under an older one — which is the one thing a
    permanent evidence record must not do. Re-validation is a reader's decision, not the store's.
    """

    org_id: str
    conflict_id: str
    #: What the conflict is ABOUT. Today the event carrying the strongest claim; when L1.7.4's
    #: qualified-signal store lands this becomes that signal's id and old rows stay readable.
    signal_id: str
    field: str
    subject_key: str
    claims: tuple[dict, ...]
    resolution: str
    resolved_value: Any
    event_ids: tuple[str, ...]
    detected_at: datetime


def _jsonable(value: Any) -> Any:
    """A pydantic model, or anything already JSON-shaped, as JSON. `mode="json"` so a `Money`
    becomes `{"minor_units": 7400000, ...}` with its integer intact and a datetime becomes an
    ISO string — never `float()` on the way past."""
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def conflict_id(org_id: str, signal_id: str, subject_key: str, conflict: Any) -> str:
    """The content address of one conflict. See the module docstring on why `detected_at` is
    excluded: it is the only field a replay changes, and a digest that included it would turn
    one disagreement into one row per re-run."""
    payload = json.dumps({
        "org": org_id, "signal": signal_id, "subject": subject_key,
        "field": conflict.field, "resolution": getattr(conflict.resolution, "value",
                                                       conflict.resolution),
        "claims": _jsonable(list(conflict.claims)),
        "resolved_value": _jsonable(conflict.resolved_value),
    }, sort_keys=True, separators=(",", ":"), default=str)
    return "cfl_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def rows_for(detection: Any, *, org_id: str) -> list[ConflictRow]:
    """A `ConflictDetection` (or anything with `.conflicts`) flattened to rows.

    A free function rather than a method, for the reason `coverage/store.rows_for` is one: the
    SHAPE of a stored conflict is decided once, so the in-memory store and the Postgres store
    agree by construction instead of by two implementations that happen to match today.
    """
    rows: list[ConflictRow] = []
    for detected in getattr(detection, "conflicts", ()) or ():
        conflict = detected.conflict
        event_ids = tuple(detected.event_ids or ())
        # The strongest claim's event. `DetectedConflict.event_ids` is ordered strongest-first by
        # the detector, so this is a read of its ordering, never a re-ranking here.
        signal_id = event_ids[0] if event_ids else detected.subject_key
        rows.append(ConflictRow(
            org_id=org_id,
            conflict_id=conflict_id(org_id, signal_id, detected.subject_key, conflict),
            signal_id=signal_id, field=conflict.field, subject_key=detected.subject_key,
            claims=tuple(_jsonable(claim) for claim in conflict.claims),
            resolution=getattr(conflict.resolution, "value", str(conflict.resolution)),
            resolved_value=_jsonable(conflict.resolved_value),
            event_ids=event_ids, detected_at=conflict.detected_at))
    return rows


class ConflictStore(Protocol):
    """Two operations, on L1.7.4's terms: a sweep writes what it detected, a reader asks for one."""

    def put(self, rows: Sequence[ConflictRow]) -> int:
        """Rows written. UPSERT by `conflict_id` — a replay re-files one fact, it does not add one."""
        ...

    def get(self, org_id: str, conflict_id: str) -> ConflictRow | None: ...

    def list(self, org_id: str, signal_id: str | None = None) -> list[ConflictRow]: ...


class InMemoryConflictStore:
    """A dict, for dev and hermetic tests. Same upsert and the same TENANT BOUNDARY: `get` is
    keyed on (org, id) rather than on the id alone, so a hermetic test cannot pass while the
    real store would hand one tenant's contract amounts to another."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ConflictRow] = {}

    def put(self, rows: Sequence[ConflictRow]) -> int:
        for row in rows:
            self._rows[(row.org_id, row.conflict_id)] = row
        return len(rows)

    def get(self, org_id: str, conflict_id: str) -> ConflictRow | None:
        return self._rows.get((org_id, conflict_id))

    def list(self, org_id: str, signal_id: str | None = None) -> list[ConflictRow]:
        return [r for (o, _), r in sorted(self._rows.items())
                if o == org_id and (signal_id is None or r.signal_id == signal_id)]


class PostgresConflictStore:
    """The real store. One statement per row, `on conflict (conflict_id) do update`.

    `put` logs and returns 0 on a database error rather than raising into the ingestion path —
    the same rule `_assemble_groups` and `_detect_conflicts` already follow one layer up. Losing
    a conflict row costs a card its receipt; losing a sweep costs the tenant their mail.
    """

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def put(self, rows: Sequence[ConflictRow]) -> int:
        from sqlalchemy import text
        if not rows:
            return 0
        try:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(text(
                        f"insert into {CONFLICT_TABLE} "
                        "(conflict_id, org_id, signal_id, field, subject_key, claims, "
                        " resolution, resolved_value, event_ids, detected_at) "
                        "values (:id, :o, :sig, :f, :sub, cast(:claims as jsonb), :res, "
                        "        cast(:val as jsonb), cast(:evts as jsonb), :at) "
                        "on conflict (conflict_id) do update set "
                        "claims=excluded.claims, resolution=excluded.resolution, "
                        "resolved_value=excluded.resolved_value, "
                        "event_ids=excluded.event_ids, detected_at=excluded.detected_at"),
                        {"id": row.conflict_id, "o": row.org_id, "sig": row.signal_id,
                         "f": row.field, "sub": row.subject_key,
                         "claims": json.dumps(list(row.claims), default=str),
                         "res": row.resolution,
                         "val": json.dumps(row.resolved_value, default=str),
                         "evts": json.dumps(list(row.event_ids)), "at": row.detected_at})
        except Exception as exc:      # noqa: BLE001 — a conflict record never kills a sweep
            _log.warning("could not persist %d conflict(s) for org=%s: %s",
                         len(rows), rows[0].org_id, exc)
            return 0
        return len(rows)

    def get(self, org_id: str, conflict_id: str) -> ConflictRow | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select {_COLUMNS} from {CONFLICT_TABLE} "
                "where org_id=:o and conflict_id=:id"), {"o": org_id, "id": conflict_id}).first()
        return _to_row(row) if row is not None else None

    def list(self, org_id: str, signal_id: str | None = None) -> list[ConflictRow]:
        from sqlalchemy import text
        clause = " and signal_id=:sig" if signal_id else ""
        params: dict[str, Any] = {"o": org_id}
        if signal_id:
            params["sig"] = signal_id
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_COLUMNS} from {CONFLICT_TABLE} where org_id=:o{clause} "
                "order by detected_at desc, conflict_id"), params).all()
        return [_to_row(r) for r in rows]


_COLUMNS = ("conflict_id, org_id, signal_id, field, subject_key, claims, resolution, "
            "resolved_value, event_ids, detected_at")


def _to_row(row: Any) -> ConflictRow:
    claims = row.claims if isinstance(row.claims, list) else json.loads(row.claims or "[]")
    events = row.event_ids if isinstance(row.event_ids, list) else json.loads(row.event_ids or "[]")
    return ConflictRow(
        org_id=row.org_id, conflict_id=row.conflict_id, signal_id=row.signal_id,
        field=row.field, subject_key=row.subject_key, claims=tuple(claims),
        resolution=row.resolution, resolved_value=row.resolved_value,
        event_ids=tuple(events), detected_at=row.detected_at)


def persist_sweep_conflicts(summary: Any, *, org_id: str, store: Any) -> int:
    """THE SEAM. One sweep's conflicts, filed — the call every `run_sync` caller now makes.

    `sync_runner` detects across the whole page (a conflict lives BETWEEN events, so it cannot
    be filed from inside `capture_event`) and hands the result back on the summary. This turns
    that returned object into rows. It is deliberately a function over the SUMMARY rather than
    over a `ConflictOutcome`, so a caller that has a sweep result has everything it needs and
    cannot file half of it.

    Returns rows written. Zero for a sweep that detected nothing, for a caller with no store,
    and for a database that refused — none of which is an error worth failing an ingest for.
    """
    outcome = getattr(summary, "conflicts", None)
    if outcome is None or store is None:
        return 0
    try:
        rows = rows_for(getattr(outcome, "detection", outcome), org_id=org_id)
        return store.put(rows) if rows else 0
    except Exception:      # noqa: BLE001 — downstream of capture, never above it
        _log.warning("conflict persistence failed for org=%s", org_id, exc_info=True)
        return 0


__all__ = ["CONFLICT_TABLE", "ConflictRow", "ConflictStore", "InMemoryConflictStore",
           "PostgresConflictStore", "conflict_id", "persist_sweep_conflicts", "rows_for"]
