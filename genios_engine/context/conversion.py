"""L2.3 · what each correlator was GIVEN and what it produced — the census nobody kept.

THE NUMBER THAT WAS NOT ANYWHERE. Layer 1 extracted 165 dependencies and 305 commitments on the
pilot; `correlation_dependency` published 0 derived facts and `correlation_timeline` published 2.
The correlators ran on every sweep, received real input, and emitted almost nothing — and no
surface in the engine said so. `facts_written` was reported, `claims_read` was reported, and the
two were never put beside each other where a reader could subtract them.

THE REASONS WERE ALREADY COMPUTED AND THROWN AWAY. `correlation_dependency` carries a
`DropReason` for every claim it refuses — `UNRESOLVED_BLOCKER`, `NO_EVIDENCE`, `SELF_LOOP`,
`RESOLVED`, `UNRESOLVED_BLOCKED` — assembles them into `DependencySweep.dropped`, hands that to
`runner.process_pending`, and the runner reads `facts_written` and `budget_exhausted` from the
same object and discards the rest. The most useful diagnostic in the layer travelled one function
call and died there.

ONE SHAPE FOR EVERY CORRELATOR, WHICH IS THE POINT. This records `read`, `emitted` and `dropped`
and computes nothing else. It holds no opinion about what a healthy rate is, names no correlator,
and carries no threshold — a tenant whose dependencies genuinely are all resolved SHOULD convert
at zero, and a rule that called that a failure would be wrong for them and right for nobody.
What the census gives is the subtraction: 165 in, 0 out, 161 of them `unresolved_blocker`. That
sentence names its own fix on any customer's data; a conversion rate alone names none.

ON THE TENANT NODE, because the subject is the org's own processing rather than any counterparty,
and `periodic.py` already anchors tenant-wide readings there. One fact per correlator, replaced in
place: the interesting question is what the LAST sweep converted, and `metric_history` is where a
trend would belong if anybody wanted one.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

FACT_PREFIX = "derived.conversion"

#: `publish_derived_fact` needs a version prefix per writer so `close_derived_facts` can retire
#: exactly this module's rows and nobody else's.
VERSION_PREFIX = "fv_conv"
VALUE_TYPE = "conversion_census"

#: PARTICIPANTS, not `org`. The counts summarise mail the tenant's own people sent and received,
#: so the census is exactly as narrow as the evidence behind it — the ceiling
#: `correlation_timeline` records for its own rows.
VISIBILITY_SCOPE = "participants"


def field_for(correlator: str) -> str:
    """`derived.conversion.<correlator>`. One field per writer, so two correlators cannot
    overwrite each other's census and a reader can ask about one of them."""
    return f"{FACT_PREFIX}.{str(correlator).strip().lower()}"


def census(*, read: int, emitted: int, dropped: Mapping[str, int] | None = None) -> dict[str, Any]:
    """The record itself. Pure, so a caller can build one without a database and a test can check
    the arithmetic without a sweep.

    `rate_bp` IS A REPORTED NUMBER AND NOT A VERDICT. It is `emitted / read` in basis points
    because every score in this layer is, and because "0" and "10000" are both legitimate answers
    — an org with no open dependencies converts at zero and is perfectly healthy. Nothing here
    compares it to anything.
    """
    read, emitted = max(0, int(read)), max(0, int(emitted))
    kept = {str(k): int(v) for k, v in (dropped or {}).items() if int(v) > 0}
    return {"read": read,
            "emitted": emitted,
            "dropped": dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))),
            # `read - emitted` is NOT the same as the sum of `dropped`: one claim can be refused
            # by a step that records no reason, and several claims can collapse into one edge.
            # Both numbers are carried so a gap between them is visible rather than reconciled
            # away — an unexplained difference is itself a thing worth seeing.
            "unaccounted": max(0, read - emitted - sum(kept.values())),
            "rate_bp": 0 if read == 0 else int(round(10_000 * emitted / read))}


def record_conversion(conn, org_id: str, *, correlator: str, read: int, emitted: int,
                      eval_time: datetime, dropped: Mapping[str, int] | None = None) -> bool:
    """Publish one correlator's census. Returns whether a row was written.

    NO TENANT NODE, NO CENSUS, and that is not an error. `periodic.tenant_node_id` returns None
    before the first sweep has minted one, and minting one here would make a diagnostic the reason
    a node exists. A graph without one simply has no census this sweep.

    NEVER FATAL AND NEVER GUARDED HERE. A measurement that can take a correlator down is worse
    than no measurement, and the guard belongs to the caller that owns the transaction — see
    `outreach_situations._optional` for why a `try/except` around a database call without a
    savepoint is not a guard at all.
    """
    from genios_engine.context.analytic.publish import publish_derived_fact
    from genios_engine.context.periodic import tenant_node_id

    node_id = tenant_node_id(conn, org_id)
    if not node_id:
        return False
    field = field_for(correlator)
    publish_derived_fact(
        conn, org_id=org_id, subject_node_id=node_id, field=field,
        value=census(read=read, emitted=emitted, dropped=dropped),
        eval_time=eval_time, value_type=VALUE_TYPE, visibility_scope=VISIBILITY_SCOPE,
        version_prefix=f"{VERSION_PREFIX}:", fact_id=f"f_conv:{field}:{node_id}")
    return True


_READ = ("select f.field as field, f.value as value from graph_facts f "
         "where f.org_id = :o and f.field like :prefix and f.status = 'active' "
         "and f.valid_to is null")


def read_conversion(conn, org_id: str) -> dict[str, dict[str, Any]]:
    """`{correlator: census}` for one org. Defensive about the driver's `jsonb`, like every
    reader here: a malformed row costs one correlator's number, never the whole report."""
    out: dict[str, dict[str, Any]] = {}
    for row in conn.execute(text(_READ), {"o": org_id, "prefix": f"{FACT_PREFIX}.%"}).mappings():
        value = row["value"]
        if isinstance(value, (str, bytes)):
            try:
                value = json.loads(value)
            except ValueError:
                continue
        if isinstance(value, Mapping):
            out[str(row["field"]).rsplit(".", 1)[-1]] = dict(value)
    return out


__all__ = ["FACT_PREFIX", "VALUE_TYPE", "VERSION_PREFIX", "VISIBILITY_SCOPE",
           "census", "field_for", "read_conversion", "record_conversion"]
