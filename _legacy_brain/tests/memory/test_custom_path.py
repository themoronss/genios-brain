"""Tests for the custom-integration path: inspector, templates, confirmer, freezer.

Covers g-i-1 §1.2.2 acceptance:
- Custom source: inspect → template/LLM propose → human confirm → freeze → reads work
- Unknown/changed field appearing later triggers re-confirmation flag (drift_check)
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.memory.adapters.custom.confirmer import (
    ConfirmationError,
    HumanEdit,
    apply_human_edits,
    to_confirmation_view,
)
from core.memory.adapters.custom.drift_check import check as drift_check
from core.memory.adapters.custom.freezer import freeze, load_active
from core.memory.adapters.custom.inspector import introspect_samples
from core.memory.adapters.custom.proposer import MappingProposal
from core.memory.adapters.custom.templates import guess_from_introspection
from core.memory.store import Connection
from core.memory.types import RawRecord


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture
def connection_row(session: Session) -> Connection:
    conn = Connection(
        org_id="org_x",
        source_type="custom:acme-crm",
        source_id="acme-crm-prod",
        created_by="alice",
    )
    session.add(conn)
    session.commit()
    return conn


# ── inspector ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_inspector_infers_field_types_from_samples() -> None:
    samples = [
        {"id": 1, "body": "hello", "created_at": "2026-01-01T00:00:00Z", "tags": ["x"]},
        {"id": 2, "body": "world", "created_at": "2026-01-02T00:00:00Z", "tags": []},
    ]
    intro = introspect_samples("custom:test", samples)

    assert intro.sample_size == 2
    by_name = {f.name: f for f in intro.fields}
    assert by_name["id"].inferred_type == "integer"
    assert by_name["body"].inferred_type == "string"
    assert by_name["created_at"].inferred_type == "datetime_iso"
    assert by_name["tags"].inferred_type == "list"


# ── templates (no LLM call needed for conventional names) ──────────────────


@pytest.mark.unit
def test_template_guesses_conventional_names() -> None:
    samples = [
        {"body": "hi", "created_at": "2026-01-01T00:00:00Z", "author": "bob", "labels": ["a"]},
    ]
    intro = introspect_samples("custom:test", samples)
    guess = guess_from_introspection(intro)

    assert guess is not None
    assert guess.field_map["content"].source_field == "body"
    assert guess.field_map["timestamp"].source_field == "created_at"
    assert guess.field_map["owner"].source_field == "author"
    assert guess.field_map["tags"].source_field == "labels"
    assert guess.confidence >= 0.8


@pytest.mark.unit
def test_template_returns_none_on_weird_schema() -> None:
    """Random field names → no template match → caller falls back to LLM."""
    samples = [{"xyz_blob": "data", "ts_001": 12345}]
    intro = introspect_samples("custom:test", samples)
    assert guess_from_introspection(intro) is None


# ── confirmer ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_confirmer_view_lists_all_canonical_fields() -> None:
    intro = introspect_samples("custom:test", [{"body": "x", "created_at": "2026-01-01T00:00:00Z"}])
    proposal = MappingProposal(
        field_map={
            "content": guess_from_introspection(intro).field_map["content"],  # type: ignore[union-attr]
            "timestamp": guess_from_introspection(intro).field_map["timestamp"],  # type: ignore[union-attr]
        },
        overall_confidence=0.95,
        reason="template",
        source="template",
    )
    rows = to_confirmation_view(proposal, intro)
    canonical = [r.canonical_field for r in rows]
    assert canonical == ["content", "timestamp", "owner", "tags"]


@pytest.mark.unit
def test_confirmer_rejects_missing_required_field() -> None:
    intro = introspect_samples("custom:test", [{"body": "x", "created_at": "2026-01-01T00:00:00Z"}])
    with pytest.raises(ConfirmationError):
        apply_human_edits(
            [
                HumanEdit(canonical_field="content", source_field=None, transform=None),
                HumanEdit(canonical_field="timestamp", source_field="created_at", transform=None),
            ],
            intro,
        )


@pytest.mark.unit
def test_confirmer_applies_edits_and_boosts_confidence() -> None:
    intro = introspect_samples("custom:test", [{"body": "x", "created_at": "2026-01-01T00:00:00Z"}])
    final = apply_human_edits(
        [
            HumanEdit(canonical_field="content", source_field="body", transform=None),
            HumanEdit(canonical_field="timestamp", source_field="created_at", transform=None),
        ],
        intro,
    )
    assert final["content"].confidence == 1.0  # human confirm boosts to 1.0


# ── freezer + load_active ──────────────────────────────────────────────────


@pytest.mark.unit
def test_freeze_persists_and_load_active_returns_latest(
    session: Session, connection_row: Connection
) -> None:
    intro = introspect_samples("custom:test", [{"body": "x", "created_at": "2026-01-01T00:00:00Z"}])
    final = apply_human_edits(
        [
            HumanEdit(canonical_field="content", source_field="body", transform=None),
            HumanEdit(canonical_field="timestamp", source_field="created_at", transform=None),
        ],
        intro,
    )
    mapping = freeze(
        session,
        connection_id=connection_row.id,
        org_id="org_x",
        source_type="custom:acme-crm",
        field_map=final,
        confirmed_by="alice",
    )
    session.commit()

    assert mapping.version == 1
    loaded = load_active(session, connection_row.id, "custom:acme-crm")
    assert loaded is not None
    assert loaded.version == 1
    assert loaded.field_map["content"].source_field == "body"

    # Re-freeze (after drift re-confirm) bumps version
    mapping2 = freeze(
        session,
        connection_id=connection_row.id,
        org_id="org_x",
        source_type="custom:acme-crm",
        field_map=final,
        confirmed_by="alice",
    )
    session.commit()
    assert mapping2.version == 2

    loaded2 = load_active(session, connection_row.id, "custom:acme-crm")
    assert loaded2 is not None
    assert loaded2.version == 2


# ── drift_check ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_drift_detects_new_field(session: Session, connection_row: Connection) -> None:
    """A new field appearing in >50% records flags for re-confirmation."""
    intro = introspect_samples("custom:test", [{"body": "x", "created_at": "2026-01-01T00:00:00Z"}])
    final = apply_human_edits(
        [
            HumanEdit(canonical_field="content", source_field="body", transform=None),
            HumanEdit(canonical_field="timestamp", source_field="created_at", transform=None),
        ],
        intro,
    )
    mapping = freeze(
        session,
        connection_id=connection_row.id,
        org_id="org_x",
        source_type="custom:acme-crm",
        field_map=final,
        confirmed_by="alice",
    )
    session.commit()

    # New batch suddenly has 'priority' field on every record
    new_batch = [
        RawRecord(
            native_id=str(i), fields={"body": "x", "created_at": "2026-01-01", "priority": "high"}
        )
        for i in range(10)
    ]
    report = drift_check(new_batch, mapping, connection_id=connection_row.id, org_id="org_x")
    assert report.has_drift is True
    assert "priority" in report.new_fields


@pytest.mark.unit
def test_no_drift_when_schema_unchanged(session: Session, connection_row: Connection) -> None:
    intro = introspect_samples("custom:test", [{"body": "x", "created_at": "2026-01-01T00:00:00Z"}])
    final = apply_human_edits(
        [
            HumanEdit(canonical_field="content", source_field="body", transform=None),
            HumanEdit(canonical_field="timestamp", source_field="created_at", transform=None),
        ],
        intro,
    )
    mapping = freeze(
        session,
        connection_id=connection_row.id,
        org_id="org_x",
        source_type="custom:acme-crm",
        field_map=final,
        confirmed_by="alice",
    )
    session.commit()

    same = [RawRecord(native_id="1", fields={"body": "x", "created_at": "2026-01-01"})]
    report = drift_check(same, mapping, connection_id=connection_row.id, org_id="org_x")
    assert report.has_drift is False
