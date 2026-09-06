"""L1.7.5 · the coverage STORE — `source_coverage`, which had no reader and no writer.

The table has existed since migration `0002`. Until now the only code that referenced it was
`0033_org_data_cascade.sql`, which made sure it would be deleted when a tenant was — a table
that nothing wrote, carefully cleaned up. Doc 07 lists it in the storage map with the retention
line *"recomputed each sweep"*, which is a promise about a write that never happened.

**Why persist a declaration that is recomputed anyway.** Because two different readers need it
at two different times. The capture path computes it and uses it immediately; the dashboard, the
admin console and Layer 2 need to know what we believed we could see WITHOUT running a sweep to
find out — and Layer 2 in particular needs "unknowable from connected sources" as a state it can
read off a row rather than re-derive from a connection table it has no business querying.

The row is the declaration flattened to exactly what a reader asks of it: which capabilities the
domain required, which of them the org has, how fresh each one is, and the single bit that
licenses a negative inference. `computed_at` is what makes the retention line checkable — a
coverage row nobody can date is indistinguishable from one that stopped being recomputed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol

from genios_engine.capture.coverage.declaration import CoverageDeclaration
from genios_engine.capture.coverage.model import PACK_REQUIREMENTS
from genios_engine.platform.db import get_engine
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.coverage")

COVERAGE_TABLE = "source_coverage"


@dataclass(frozen=True)
class CoverageRow:
    """One (org, domain) coverage row, as stored.

    `required` and `connected` are tuples rather than lists because a row read back is a record
    of what was true at `computed_at`, and a caller that could append to it would be editing
    history in place.
    """

    org_id: str
    domain: str
    required: tuple[str, ...]
    connected: tuple[str, ...]
    freshness: Mapping[str, str]
    coverage_ready: bool
    computed_at: datetime | None = None


def rows_for(declaration: CoverageDeclaration) -> list[CoverageRow]:
    """The declaration, flattened to one row per registered domain.

    A separate callable rather than a method on the store so that the SHAPE of a coverage row is
    decided in one place and both store implementations agree on it by construction — an
    in-memory store that stored something subtly different from the Postgres one would let a
    hermetic test pass against a schema production does not have.
    """
    connected = tuple(sorted(declaration.connected))
    out: list[CoverageRow] = []
    for domain, verdict in declaration.domains.items():
        # Read from the requirement table, never re-derived from the verdict. `capabilities`
        # minus `missing_recommended` looks like the required set and is only equal to it while
        # every recommended capability happens to be missing — the moment a tenant connects a
        # calendar, a derivation like that would file `calendar` as REQUIRED for sales.
        required = tuple(PACK_REQUIREMENTS.get(domain, {}).get("required", ()))
        out.append(CoverageRow(
            org_id=declaration.org_id, domain=domain,
            required=required, connected=connected,
            freshness=dict(declaration.connected),
            coverage_ready=bool(verdict.get("coverage_ready")),
            computed_at=declaration.computed_at))
    return out


class CoverageStore(Protocol):
    """Two operations. A sweep writes the whole declaration; a reader asks for one domain."""

    def save(self, declaration: CoverageDeclaration) -> int:
        """Rows written. Upsert, because a sweep RECOMPUTES coverage rather than appending to it."""
        ...

    def get(self, org_id: str, domain: str) -> CoverageRow | None: ...

    def list(self, org_id: str) -> list[CoverageRow]: ...


class InMemoryCoverageStore:
    """A dict, for dev and for hermetic tests. Same upsert semantics as the real one."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], CoverageRow] = {}

    def save(self, declaration: CoverageDeclaration) -> int:
        rows = rows_for(declaration)
        for row in rows:
            self._rows[(row.org_id, row.domain)] = row
        return len(rows)

    def get(self, org_id: str, domain: str) -> CoverageRow | None:
        return self._rows.get((org_id, domain))

    def list(self, org_id: str) -> list[CoverageRow]:
        return [r for (o, _), r in sorted(self._rows.items()) if o == org_id]


class PostgresCoverageStore:
    """The real store. One statement per domain, `on conflict (org_id, domain) do update`.

    A sweep must never fail because coverage could not be filed: `save` logs and returns 0 on a
    database error rather than raising into the ingestion path. Losing a coverage row costs a
    stale dashboard; losing a sweep costs the tenant their mail.
    """

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def save(self, declaration: CoverageDeclaration) -> int:
        from sqlalchemy import text
        rows = rows_for(declaration)
        try:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(text(
                        f"insert into {COVERAGE_TABLE} "
                        "(org_id, domain, required, connected, freshness, coverage_ready, "
                        " computed_at) "
                        "values (:o, :d, :req, :con, cast(:fr as jsonb), :ready, :at) "
                        "on conflict (org_id, domain) do update set "
                        "required=excluded.required, connected=excluded.connected, "
                        "freshness=excluded.freshness, "
                        "coverage_ready=excluded.coverage_ready, "
                        "computed_at=excluded.computed_at"),
                        {"o": row.org_id, "d": row.domain, "req": list(row.required),
                         "con": list(row.connected), "fr": json.dumps(dict(row.freshness)),
                         "ready": row.coverage_ready, "at": row.computed_at})
        except Exception as exc:      # noqa: BLE001 — coverage is a hint, never a sweep-killer
            _log.warning("could not persist coverage for org=%s: %s", declaration.org_id, exc)
            return 0
        return len(rows)

    def get(self, org_id: str, domain: str) -> CoverageRow | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select org_id, domain, required, connected, freshness, coverage_ready, "
                f"computed_at from {COVERAGE_TABLE} where org_id=:o and domain=:d"),
                {"o": org_id, "d": domain}).first()
        return _to_row(row) if row is not None else None

    def list(self, org_id: str) -> list[CoverageRow]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select org_id, domain, required, connected, freshness, coverage_ready, "
                f"computed_at from {COVERAGE_TABLE} where org_id=:o order by domain"),
                {"o": org_id}).all()
        return [_to_row(r) for r in rows]


def _to_row(row: Any) -> CoverageRow:
    freshness = row.freshness if isinstance(row.freshness, dict) else json.loads(
        row.freshness or "{}")
    return CoverageRow(org_id=row.org_id, domain=row.domain,
                       required=tuple(row.required or ()), connected=tuple(row.connected or ()),
                       freshness=freshness, coverage_ready=bool(row.coverage_ready),
                       computed_at=row.computed_at)


__all__ = ["COVERAGE_TABLE", "CoverageRow", "CoverageStore", "InMemoryCoverageStore",
           "PostgresCoverageStore", "rows_for"]
