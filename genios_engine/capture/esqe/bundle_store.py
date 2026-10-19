"""GeniOS-008 L1 E1 · the BUNDLE STORE — `signal_bundles` (0186) gets its writer and its reader.

`publish_sweep` has built a `QualifiedEnterpriseSignalBundle` for every page of published signals
since L1.6.11, and `finalize_l1` passed it no store, so every bundle was thrown away with the report.
Migration 0186 has stood empty since it was applied. In the new architecture the bundle IS the L1 → L2
contract (`speedrun008/GeniOS-008/00-ARCHITECTURE.md`, L1 Blueprint §contracts): Layer 2 starts every
run from one. So this module is the two halves of that seam:

  put     the bundles a sweep built, `on conflict do nothing` — `bundle_id` is derived from the member
          signal ids, so a replayed page is the same row, never a second one;
  since   the bundles stored after a watermark, oldest first — Layer 2's "what arrived since I last
          read", the only question it asks of this table.

The same shape as `signal_store.py`: a Protocol, an in-memory store for a dev run with no database, a
Postgres store that logs and returns 0 rather than raising into a sweep. Losing a bundle costs one
reasoning run; raising costs the tenant their mail.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.bundle_store")

BUNDLE_TABLE = "signal_bundles"


@dataclass(frozen=True, slots=True)
class StoredBundle:
    """One stored bundle, as the table holds it. Plain JSON structures, never re-validated on read:
    a row written under an older contract must stay readable (the `QualifiedSignalRow` rule)."""

    bundle_id: str
    org_id: str
    trace_id: str
    signal_ids: tuple[str, ...]
    subject_key: str | None = None
    entity_keys: tuple[str, ...] = ()
    candidate_relationships: tuple[str, ...] = ()
    coverage: Mapping[str, Any] = field(default_factory=dict)
    unresolved: tuple[str, ...] = ()
    created_at: datetime | None = None


def _row_of(bundle: Any) -> StoredBundle:
    return StoredBundle(bundle_id=str(bundle.bundle_id), org_id=str(bundle.org_id),
                        trace_id=str(bundle.trace_id), signal_ids=tuple(bundle.signal_ids),
                        subject_key=bundle.subject_key, entity_keys=tuple(bundle.entity_keys),
                        candidate_relationships=tuple(bundle.candidate_relationships),
                        coverage=dict(bundle.coverage or {}), unresolved=tuple(bundle.unresolved))


def _loads(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return fallback
    return value


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class BundleStore(Protocol):
    def put(self, bundles: Sequence[Any]) -> int: ...

    def since(self, org_id: str, *, after: datetime | None, limit: int = 200) -> list[StoredBundle]: ...


class InMemoryBundleStore:
    """The dev store. Insertion order stands in for `created_at`."""

    def __init__(self) -> None:
        self._rows: dict[str, StoredBundle] = {}
        self._order: list[str] = []

    def put(self, bundles: Sequence[Any]) -> int:
        new = 0
        for bundle in bundles or ():
            row = _row_of(bundle)
            if row.bundle_id in self._rows:
                continue
            self._rows[row.bundle_id] = row
            self._order.append(row.bundle_id)
            new += 1
        return new

    def since(self, org_id: str, *, after: datetime | None, limit: int = 200) -> list[StoredBundle]:
        rows = [self._rows[b] for b in self._order if self._rows[b].org_id == org_id]
        if after is not None:
            rows = [r for r in rows if r.created_at is not None and r.created_at > after]
        return rows[:max(1, int(limit))]

    def erase(self, org_id: str) -> int:
        gone = [b for b, r in self._rows.items() if r.org_id == org_id]
        for b in gone:
            del self._rows[b]
            self._order.remove(b)
        return len(gone)


_INSERT = (
    f"insert into {BUNDLE_TABLE} (bundle_id, org_id, trace_id, subject_key, signal_ids, entity_keys, "
    " candidate_relationships, coverage, unresolved) values (:b, :o, :t, :s, cast(:sig as jsonb), "
    " cast(:ent as jsonb), cast(:rel as jsonb), cast(:cov as jsonb), cast(:unr as jsonb)) "
    # ⛔ NOTHING, never `do update`: the id IS the members, so the same id is the same group.
    "on conflict (bundle_id) do nothing")

_SINCE = (
    "select bundle_id, org_id, trace_id, subject_key, signal_ids, entity_keys, candidate_relationships, "
    "       coverage, unresolved, created_at "
    f"  from {BUNDLE_TABLE} where org_id = :o and (cast(:after as timestamptz) is null "
    "   or created_at > cast(:after as timestamptz)) "
    " order by created_at, bundle_id limit :n")


def _stored(row: Any) -> StoredBundle:
    m = row._mapping if hasattr(row, "_mapping") else row
    return StoredBundle(
        bundle_id=str(m["bundle_id"]), org_id=str(m["org_id"]), trace_id=str(m["trace_id"]),
        signal_ids=tuple(_loads(m["signal_ids"], [])), subject_key=m["subject_key"],
        entity_keys=tuple(_loads(m["entity_keys"], [])),
        candidate_relationships=tuple(_loads(m["candidate_relationships"], [])),
        coverage=_loads(m["coverage"], {}) or {}, unresolved=tuple(_loads(m["unresolved"], [])),
        created_at=m["created_at"])


class PostgresBundleStore:
    """The real store. Never raises into a sweep."""

    def __init__(self, database_url: str | None = None, *, engine: Any = None) -> None:
        if engine is None:
            from genios_engine.platform.db import get_engine
            engine = get_engine(database_url)
        self._engine = engine

    def put(self, bundles: Sequence[Any]) -> int:
        from sqlalchemy import text
        rows = [_row_of(b) for b in bundles or ()]
        if not rows:
            return 0
        new = 0
        try:
            with self._engine.begin() as conn:
                for r in rows:
                    result = conn.execute(text(_INSERT), {
                        "b": r.bundle_id, "o": r.org_id, "t": r.trace_id, "s": r.subject_key,
                        "sig": _dumps(list(r.signal_ids)), "ent": _dumps(list(r.entity_keys)),
                        "rel": _dumps(list(r.candidate_relationships)), "cov": _dumps(dict(r.coverage)),
                        "unr": _dumps(list(r.unresolved))})
                    new += int(result.rowcount or 0)
        except Exception as exc:      # noqa: BLE001 — a bundle store never kills a sweep
            _log.warning("could not store %d bundle(s) for org=%s: %s", len(rows), rows[0].org_id, exc)
            return 0
        return new

    def since(self, org_id: str, *, after: datetime | None, limit: int = 200) -> list[StoredBundle]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text(_SINCE), {"o": org_id, "after": after,
                                               "n": max(1, int(limit))}).all()
        return [_stored(r) for r in rows]


_BY_ID = (
    "select bundle_id, org_id, trace_id, subject_key, signal_ids, entity_keys, candidate_relationships, "
    "       coverage, unresolved, created_at "
    f"  from {BUNDLE_TABLE} where org_id = :o and bundle_id = any(:ids) order by created_at, bundle_id")


def read_bundles_by_id(conn, org_id: str, bundle_ids: Sequence[str]) -> list[StoredBundle]:
    """Named bundles again — what a run that re-enters on new evidence reasoned over the first time."""
    from sqlalchemy import text
    ids = sorted(set(bundle_ids))
    if not ids:
        return []
    return [_stored(r) for r in conn.execute(text(_BY_ID), {"o": org_id, "ids": ids}).all()]


def read_bundles_since(conn, org_id: str, *, after: datetime | None, limit: int = 200) -> list[StoredBundle]:
    """The reader on a connection the caller already holds — Layer 2's door into this table."""
    from sqlalchemy import text
    rows = conn.execute(text(_SINCE), {"o": org_id, "after": after, "n": max(1, int(limit))}).all()
    return [_stored(r) for r in rows]


__all__ = ["BUNDLE_TABLE", "BundleStore", "InMemoryBundleStore", "PostgresBundleStore", "StoredBundle",
           "read_bundles_by_id", "read_bundles_since"]
