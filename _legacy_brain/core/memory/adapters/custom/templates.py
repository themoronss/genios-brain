"""Common-pattern templates — auto-suggest a mapping before invoking the LLM.

Per g-i-1 custom integration path, supports `templates.py`:
- REST + JSON with conventional names → instant mapping (no LLM call needed)
- SQL with common column names → instant mapping
- GraphQL types → instant mapping
- Vector DB metadata → instant mapping

If a template matches with high confidence, the proposer skips the LLM entirely
(cheaper + faster + more reliable). Falls back to LLM only on weird schemas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from core.memory.adapters.custom.inspector import IntrospectedField, Introspection
from core.memory.types import FieldMapping, SourceMapping


@dataclass(frozen=True)
class TemplateGuess:
    """A candidate mapping derived from common naming patterns."""

    field_map: dict[str, FieldMapping]
    confidence: float
    template_name: str


# Per canonical field, list of (source_name, transform, confidence) candidates ordered by preference.
_CONTENT_HINTS = [
    ("content", None, 0.95),
    ("body", None, 0.95),
    ("body_text", None, 0.95),
    ("text", None, 0.9),
    ("message", None, 0.9),
    ("description", None, 0.85),
    ("summary", None, 0.85),
    ("snippet", None, 0.8),
    ("note", None, 0.75),
]

_TIMESTAMP_HINTS = [
    ("created_at", None, 0.95),
    ("updated_at", None, 0.95),
    ("timestamp", None, 0.9),
    ("ts", None, 0.85),
    ("date", None, 0.85),
    ("internal_date_ms", "epoch_ms_to_iso8601", 0.95),
    ("created_at_ms", "epoch_ms_to_iso8601", 0.9),
    ("created_ts", "epoch_s_to_iso8601", 0.85),
]

_OWNER_HINTS = [
    ("owner", None, 0.95),
    ("from", None, 0.95),
    ("author", None, 0.9),
    ("user", None, 0.85),
    ("user_id", None, 0.8),
    ("created_by", None, 0.85),
    ("sender", None, 0.85),
    ("from_address", None, 0.9),
]

_TAGS_HINTS = [
    ("tags", None, 0.95),
    ("labels", None, 0.95),
    ("categories", None, 0.9),
    ("topics", None, 0.85),
]


def guess_from_introspection(introspection: Introspection) -> TemplateGuess | None:
    """Try to match the source's fields against common patterns.

    Returns None if no high-confidence match (caller falls back to LLM proposer).
    Returns TemplateGuess if at least content + timestamp are mapped with confidence > 0.8.
    """
    observed = {f.name.lower(): f for f in introspection.fields}

    content = _best_match(observed, _CONTENT_HINTS)
    timestamp = _best_match(observed, _TIMESTAMP_HINTS)

    if content is None or timestamp is None:
        return None

    field_map: dict[str, FieldMapping] = {
        "content": content,
        "timestamp": timestamp,
    }

    owner = _best_match(observed, _OWNER_HINTS)
    if owner:
        field_map["owner"] = owner

    tags = _best_match(observed, _TAGS_HINTS)
    if tags:
        field_map["tags"] = tags

    overall = min(fm.confidence for fm in field_map.values())
    if overall < 0.8:
        return None

    return TemplateGuess(
        field_map=field_map,
        confidence=overall,
        template_name="conventional_names_v1",
    )


def to_source_mapping(
    guess: TemplateGuess,
    *,
    source_type: str,
    confirmed_by: str,
) -> SourceMapping:
    """Convert a TemplateGuess into a SourceMapping after human confirms it."""
    return SourceMapping(
        source_type=source_type,
        field_map=guess.field_map,  # type: ignore[arg-type]
        confirmed_by=confirmed_by,
        confirmed_at=datetime.now(UTC),
        version=1,
    )


# ── helpers ────────────────────────────────────────────────────────────────


def _best_match(
    observed: Mapping[str, IntrospectedField],
    hints: Sequence[tuple[str, str | None, float]],
) -> FieldMapping | None:
    for source_name, transform, confidence in hints:
        if source_name in observed:
            return FieldMapping(
                source_field=source_name,
                transform=transform,
                confidence=confidence,
            )
    return None
