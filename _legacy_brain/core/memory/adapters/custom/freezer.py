"""Freeze a confirmed mapping into a versioned, audit-logged artifact.

Per g-i-1 §1.2.2 — FREEZE step:
- The mapping becomes immutable for this version
- Bumped on re-confirmation after drift (drift_check.py triggers re-confirm flow)
- Audit-logged with the human who confirmed
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.foundations import audit
from core.memory.store import SourceMappingRow
from core.memory.types import FieldMapping, SourceMapping


def freeze(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    source_type: str,
    field_map: dict[str, FieldMapping],
    confirmed_by: str,
) -> SourceMapping:
    """Persist a confirmed mapping. Bumps version if prior mapping exists.

    Returns the SourceMapping pydantic object that adapters can consume directly.
    """
    if "content" not in field_map or "timestamp" not in field_map:
        raise ValueError("field_map missing required keys: content, timestamp")

    prev = (
        session.query(SourceMappingRow)
        .filter_by(connection_id=connection_id)
        .order_by(SourceMappingRow.version.desc())
        .first()
    )
    next_version = (prev.version + 1) if prev else 1

    overall_confidence = min(fm.confidence for fm in field_map.values())
    mapping_json = {k: v.model_dump() for k, v in field_map.items()}

    row = SourceMappingRow(
        connection_id=connection_id,
        org_id=org_id,
        mapping_json=mapping_json,
        version=next_version,
        confirmed_by=confirmed_by,
        confirmed_at=datetime.now(UTC),
        source_confidence=overall_confidence,
    )
    session.add(row)
    session.flush()

    audit.record(
        org_id=org_id,
        actor_type="user",
        actor_id=confirmed_by,
        action="config_changed",
        target_type="source_mapping",
        target_id=row.id,
        metadata={
            "connection_id": connection_id,
            "source_type": source_type,
            "version": next_version,
            "confidence": overall_confidence,
            "fields_mapped": sorted(field_map.keys()),
        },
    )

    return SourceMapping(
        source_type=source_type,
        field_map=field_map,  # type: ignore[arg-type]
        confirmed_by=confirmed_by,
        confirmed_at=row.confirmed_at,
        version=next_version,
    )


def load_active(session: Session, connection_id: str, source_type: str) -> SourceMapping | None:
    """Load the active (highest-version) frozen mapping for a connection."""
    row = (
        session.query(SourceMappingRow)
        .filter_by(connection_id=connection_id)
        .order_by(SourceMappingRow.version.desc())
        .first()
    )
    if row is None:
        return None
    field_map = {k: FieldMapping(**v) for k, v in row.mapping_json.items() if isinstance(v, dict)}
    return SourceMapping(
        source_type=source_type,
        field_map=field_map,  # type: ignore[arg-type]
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
        version=row.version,
    )
