"""Human-in-the-loop mapping confirmation.

Per g-i-1 §1.2.2 — the LLM/template PROPOSES, a human CONFIRMS.
This module exposes the data shapes the dashboard UI consumes; it does NOT
render UI (that's g-i-7's dashboard).

Two operations:
1. `to_confirmation_view` — turns a MappingProposal into a UI-friendly payload
2. `apply_human_edits`    — accepts the human's edits + returns the final mapping
                            ready to freeze
"""

from __future__ import annotations

from dataclasses import dataclass

from core.memory.adapters.custom.inspector import Introspection
from core.memory.adapters.custom.proposer import MappingProposal
from core.memory.types import FieldMapping


@dataclass(frozen=True)
class ConfirmationRow:
    """One row in the dashboard's mapping confirmation table."""

    canonical_field: str  # content | timestamp | owner | tags
    proposed_source_field: str | None
    proposed_transform: str | None
    proposed_confidence: float
    available_source_fields: list[str]  # for the dropdown
    is_required: bool


def to_confirmation_view(
    proposal: MappingProposal,
    introspection: Introspection,
) -> list[ConfirmationRow]:
    """Build the dashboard payload showing the proposed mapping + alternatives."""
    available = [f.name for f in introspection.fields]
    rows: list[ConfirmationRow] = []

    for canonical, required in [
        ("content", True),
        ("timestamp", True),
        ("owner", False),
        ("tags", False),
    ]:
        proposed = proposal.field_map.get(canonical)
        rows.append(
            ConfirmationRow(
                canonical_field=canonical,
                proposed_source_field=proposed.source_field if proposed else None,
                proposed_transform=proposed.transform if proposed else None,
                proposed_confidence=proposed.confidence if proposed else 0.0,
                available_source_fields=available,
                is_required=required,
            )
        )
    return rows


@dataclass(frozen=True)
class HumanEdit:
    """One row of the dashboard form, posted back."""

    canonical_field: str
    source_field: str | None  # None = skip (only valid for non-required)
    transform: str | None
    confidence_override: float | None = None  # human boosts confidence to 1.0 on confirm


class ConfirmationError(Exception):
    """Human submitted invalid edits (e.g. missing required field)."""


def apply_human_edits(
    edits: list[HumanEdit],
    introspection: Introspection,
) -> dict[str, FieldMapping]:
    """Validate + apply human edits. Returns the final field_map ready to freeze."""
    available = {f.name for f in introspection.fields}
    final: dict[str, FieldMapping] = {}

    for edit in edits:
        canonical = edit.canonical_field
        if canonical not in {"content", "timestamp", "owner", "tags"}:
            raise ConfirmationError(f"Unknown canonical field: {canonical}")
        if edit.source_field is None:
            if canonical in {"content", "timestamp"}:
                raise ConfirmationError(f"Required field '{canonical}' cannot be unmapped")
            continue
        if edit.source_field not in available:
            raise ConfirmationError(
                f"Source field '{edit.source_field}' not in observed fields: {sorted(available)}"
            )
        # Human confirm sets confidence high (default 1.0) unless they override
        confidence = edit.confidence_override if edit.confidence_override is not None else 1.0
        final[canonical] = FieldMapping(
            source_field=edit.source_field,
            transform=edit.transform,
            confidence=confidence,
        )

    if "content" not in final or "timestamp" not in final:
        raise ConfirmationError("Both 'content' and 'timestamp' MUST be mapped")

    return final
