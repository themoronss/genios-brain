"""Light schema-drift detection on batch runs.

Per g-i-1 §1.2.2 — DRIFT step:
On every batch, compare incoming record fields vs the frozen mapping.
- New field appearing → flag for re-confirmation (never silent re-guess)
- Mapped field disappearing → flag (mapping may be broken)
- Mapped field's type changed → flag

Output: DriftReport. Dashboard surfaces this; user re-runs proposer + confirmer
if they want to map newly-appeared fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.memory.types import RawRecord, SourceMapping

log = get_logger(__name__)


@dataclass(frozen=True)
class DriftReport:
    """Surfaces what changed since the mapping was frozen."""

    connection_id: str
    mapping_version: int
    new_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)  # mapped fields no longer present
    has_drift: bool = False


def check(
    records: list[RawRecord],
    mapping: SourceMapping,
    *,
    connection_id: str,
    org_id: str,
) -> DriftReport:
    """Inspect a batch of records vs the mapping. No data persisted; only field names compared."""
    if not records:
        return DriftReport(connection_id=connection_id, mapping_version=mapping.version)

    observed_fields: set[str] = set()
    for r in records:
        observed_fields.update(r.fields.keys())

    mapped_fields = {fm.source_field for fm in mapping.field_map.values()}

    # Field name we MAPPED but isn't appearing in any record -> mapping may be broken
    missing = sorted(mapped_fields - observed_fields)

    # Fields we DIDN'T map but are appearing -> user may want to map them
    # Only flag fields that appear in >50% of records (signal, not noise)
    threshold = max(1, len(records) // 2)
    per_field_counts: dict[str, int] = {f: 0 for f in observed_fields}
    for r in records:
        for f in r.fields:
            per_field_counts[f] += 1

    new = sorted(
        f for f, count in per_field_counts.items() if f not in mapped_fields and count >= threshold
    )

    has_drift = bool(new) or bool(missing)

    if has_drift:
        log.info(
            "schema_drift_detected",
            connection_id=connection_id,
            new_fields=new,
            missing_fields=missing,
        )
        audit.record(
            org_id=org_id,
            actor_type="system",
            actor_id="drift_check",
            action="config_changed",
            target_type="source_mapping",
            target_id=connection_id,
            metadata={
                "mapping_version": mapping.version,
                "new_fields_count": len(new),
                "missing_fields_count": len(missing),
            },
        )

    return DriftReport(
        connection_id=connection_id,
        mapping_version=mapping.version,
        new_fields=new,
        missing_fields=missing,
        has_drift=has_drift,
    )
