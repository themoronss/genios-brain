"""Event receipts for deterministic graph derivations, without a second source of truth.

The 10 September pilot had 509 company, 175 outreach and 12 campaign facts with zero
source refs. A derivation label is not evidence: retain the actual contributing event and
its source/independence group, rather than minting an engine event as a new witness.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, bindparam, text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.derived_provenance")
VERSION = "derived-provenance.v1"


@dataclass(frozen=True, slots=True)
class EventReceipt:
    event_id: str
    source: str | None
    independence_group: str
    occurred_at: datetime | None
    source_object_id: str | None
    evidence: dict[str, Any]


def _timestamp(value) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _evidence(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def load_event_receipts(conn, *, org_id: str, event_ids) -> tuple[EventReceipt, ...] | None:
    """None is an unavailable refinement; () is a successful read with no real evidence.

    A savepoint matters on Postgres: catching a missing-table error without rolling back its
    subtransaction leaves every subsequent statement aborted, which is not fail-open.
    """
    ids = sorted({event for event in event_ids if isinstance(event, str) and event})
    if not ids:
        return ()
    statement = text(
        "select e.event_id, e.source, e.source_object_id, e.occurred_at, "
        "r.source_ref_id, r.independence_group, r.evidence "
        "from source_events e left join graph_source_refs r "
        "on r.org_id=e.org_id and r.event_id=e.event_id "
        "where e.org_id=:org and e.event_id in :events "
        "order by e.event_id, r.source_ref_id"
    ).bindparams(bindparam("events", expanding=True))
    try:
        with conn.begin_nested():
            rows = conn.execute(statement, {"org": org_id, "events": ids}).mappings().all()
    except Exception:  # noqa: BLE001 — a refinement cannot break an existing fact write
        _log.warning("Derived event receipts unavailable (org=%s); retaining original path", org_id)
        return None
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["event_id"], []).append(row)
    receipts = []
    for event_id, refs in grouped.items():
        row = refs[0]
        groups = sorted({r["independence_group"] for r in refs if r["independence_group"]})
        # One event cannot become several witnesses because several graph rows cite it.
        # Preserve an established origin; conflicting origins are unattributed, never additive.
        group = (groups[0] if len(groups) == 1 else
                 "unattributed" if groups else row["source"] or "unattributed")
        evidence = next((_evidence(r["evidence"]) for r in refs if r["evidence"]), {})
        receipts.append(EventReceipt(
            event_id=event_id, source=row["source"], independence_group=group,
            occurred_at=_timestamp(row["occurred_at"]), source_object_id=row["source_object_id"],
            evidence=evidence))
    return tuple(receipts)


def write_fact_source_refs(conn, *, org_id: str, fact_version_id: str,
                           receipts: tuple[EventReceipt, ...]) -> None:
    """Replace this writer's receipts in the fact transaction; repeat sweeps keep stable IDs.

    A membership change must remove obsolete receipts, not accumulate evidence from an older
    value of the same deterministic fact version. Other writers' refs are never deleted here.
    """
    conn.execute(text(
        "delete from graph_source_refs where org_id=:org and fact_version_id=:fact "
        "and extractor_version=:version"),
        {"org": org_id, "fact": fact_version_id, "version": VERSION})
    statement = text(
        "insert into graph_source_refs (source_ref_id, org_id, fact_version_id, event_id, "
        "source, source_object_id, independence_group, evidence, extractor_version) "
        "values (:id,:org,:fact,:event,:source,:object,:group,:evidence,:version) "
        "on conflict (source_ref_id) do update set source=excluded.source, "
        "source_object_id=excluded.source_object_id, independence_group=excluded.independence_group, "
        "evidence=excluded.evidence"
    ).bindparams(bindparam("evidence", type_=JSON))
    # ONE ROUND TRIP FOR THE WHOLE FACT, not one per receipt.
    #
    # MEASURED, NOT GUESSED. A full sweep on the pilot took ~3 hours on 2026-09-16, and eleven
    # stack dumps taken 300s apart through it land on this function and the two `_write_fact`
    # callers above it more than on anything else. The tenant holds 8,532 `graph_source_refs`
    # rows and a sweep rewrites most of them; at one `execute` per receipt against a remote
    # pooler, the cost is thousands of separate round trips of tens of milliseconds each. The SQL
    # was never wrong — it was being asked for one row at a time.
    #
    # NOTHING ELSE CHANGES. Same deterministic `source_ref_id`, same `on conflict do update`,
    # same delete before it, same de-duplication by event id — the driver is simply handed every
    # row at once. The determinism is what makes that safe: `ref_derived_<sha256(org|fact|event)>`
    # means a replayed sweep addresses exactly the rows it addressed before, so a batch cannot
    # duplicate anything single-stepping would not have.
    params = [
        {"id": f"ref_derived_"
               f"{hashlib.sha256(f'{org_id}|{fact_version_id}|{receipt.event_id}'.encode()).hexdigest()[:32]}",
         "org": org_id, "fact": fact_version_id,
         "event": receipt.event_id, "source": receipt.source,
         "object": receipt.source_object_id, "group": receipt.independence_group,
         "evidence": receipt.evidence, "version": VERSION}
        # De-duplicated by event id BEFORE the batch, not after: two receipts for one event are
        # one row, and sending both would hand the driver two rows with the same primary key.
        for receipt in {r.event_id: r for r in receipts}.values()
    ]
    if params:
        conn.execute(statement, params)
