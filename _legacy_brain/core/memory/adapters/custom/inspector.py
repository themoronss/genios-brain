"""Schema introspection for custom sources.

Per g-i-1 custom integration path, step 2 INSPECT:
- REST: parse OpenAPI spec if available, else sample N records
- SQL: INFORMATION_SCHEMA query
- GraphQL: introspection query
- Vector DB: metadata keys
- Generic JSON API: sample N records + type inference

Output: list of (field_name, inferred_type, sample_value) tuples
that proposer.py feeds to the LLM for mapping suggestions.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

FieldType = Literal[
    "string",
    "integer",
    "float",
    "boolean",
    "datetime_iso",
    "datetime_epoch",
    "list",
    "object",
    "null",
    "unknown",
]


class IntrospectedField(BaseModel):
    """One observed field from a sample of source records."""

    model_config = ConfigDict(frozen=True)

    name: str
    inferred_type: FieldType
    sample_value: str  # truncated representation (NOT stored content — for LLM only)
    nullable: bool
    observed_in: int  # how many records had this field


class Introspection(BaseModel):
    """Output of an introspection run. Feeds proposer.py."""

    model_config = ConfigDict(frozen=True)

    source_type: str
    sample_size: int
    fields: list[IntrospectedField]


def introspect_samples(
    source_type: str,
    samples: list[dict[str, Any]],
    *,
    sample_value_limit: int = 80,
) -> Introspection:
    """Generic sampler: infer fields + types from N example records.

    Use this when the source has no schema endpoint (most REST APIs in the wild).
    For SQL sources, use `introspect_sql_schema` instead.
    """
    if not samples:
        return Introspection(source_type=source_type, sample_size=0, fields=[])

    field_types: dict[str, Counter[FieldType]] = {}
    field_samples: dict[str, Any] = {}
    field_counts: Counter[str] = Counter()
    null_counts: Counter[str] = Counter()

    for record in samples:
        for name, value in record.items():
            field_counts[name] += 1
            if value is None:
                null_counts[name] += 1
                continue
            t = _infer_type(value)
            field_types.setdefault(name, Counter())[t] += 1
            if name not in field_samples:
                field_samples[name] = value

    fields = []
    for name in sorted(field_counts):
        type_counter = field_types.get(name, Counter())
        most_common = type_counter.most_common(1)
        inferred = most_common[0][0] if most_common else "null"
        fields.append(
            IntrospectedField(
                name=name,
                inferred_type=inferred,
                sample_value=_truncate(field_samples.get(name), sample_value_limit),
                nullable=null_counts[name] > 0,
                observed_in=field_counts[name],
            )
        )

    return Introspection(source_type=source_type, sample_size=len(samples), fields=fields)


def introspect_sql_schema(
    source_type: str,
    schema_rows: list[dict[str, Any]],
) -> Introspection:
    """For SQL sources — schema_rows = SELECT from INFORMATION_SCHEMA.COLUMNS."""
    fields = [
        IntrospectedField(
            name=str(r["column_name"]),
            inferred_type=_sql_type_to_inferred(str(r.get("data_type", ""))),
            sample_value="",  # no value sample without actually querying
            nullable=str(r.get("is_nullable", "YES")).upper() != "NO",
            observed_in=1,
        )
        for r in schema_rows
    ]
    return Introspection(
        source_type=source_type,
        sample_size=0,  # we used schema, not data samples
        fields=fields,
    )


# ── helpers ────────────────────────────────────────────────────────────────


def _infer_type(v: Any) -> FieldType:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        if 1_000_000_000 < v < 9_999_999_999_999:
            return "datetime_epoch"
        return "integer"
    if isinstance(v, float):
        return "float"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, str):
        if _looks_like_iso_datetime(v):
            return "datetime_iso"
        return "string"
    return "unknown"


def _looks_like_iso_datetime(s: str) -> bool:
    if len(s) < 10 or len(s) > 35:
        return False
    if not (s[0:4].isdigit() and s[4] == "-"):
        return False
    return True


def _truncate(v: Any, limit: int) -> str:
    if v is None:
        return ""
    s = str(v)
    return s[:limit] + ("..." if len(s) > limit else "")


def _sql_type_to_inferred(sql_type: str) -> FieldType:
    t = sql_type.lower()
    if "int" in t:
        return "integer"
    if "float" in t or "double" in t or "numeric" in t or "decimal" in t:
        return "float"
    if "bool" in t:
        return "boolean"
    if "timestamp" in t or "datetime" in t or "date" in t:
        return "datetime_iso"
    if "json" in t:
        return "object"
    if "array" in t:
        return "list"
    return "string"
