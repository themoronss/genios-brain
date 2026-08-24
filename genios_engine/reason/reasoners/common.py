"""Shared pure helpers for built-in reasoners."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from genios_engine.contracts.reasoning import ReasonerSpec, ReasoningRequest


def active_spec(request: ReasoningRequest, reasoner_id: str) -> ReasonerSpec:
    for spec in request.capability.reasoners:
        if spec.reasoner_id == reasoner_id:
            return spec
    raise ValueError(f"capability does not declare reasoner {reasoner_id}")


def fact_record(request: ReasoningRequest, field: str, *, neighbor: bool = False) -> Any:
    source = request.context.neighbor_facts if neighbor else request.context.facts
    return source.get(field)


def fact_value(request: ReasoningRequest, field: str, *, neighbor: bool = False) -> Any:
    record = fact_record(request, field, neighbor=neighbor)
    return record.get("value") if isinstance(record, Mapping) and "value" in record else record


def integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} must be an integer") from exc
        if parsed == parsed.to_integral_value():
            return int(parsed)
    raise ValueError(f"{label} must be an integer")


def basis_points(value: Any, label: str) -> int:
    result = integer(value, label)
    if not 0 <= result <= 10_000:
        raise ValueError(f"{label} must be between 0 and 10000")
    return result


def decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    return result


def ratio_bp(value: Any, label: str) -> int:
    """Accept a ratio (0..1) or explicit basis points (0..10000), return basis points."""
    amount = decimal(value, label)
    if Decimal("0") <= amount <= Decimal("1"):
        amount *= Decimal(10_000)
    result = int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return clamp_bp(result)


def clamp_bp(value: int) -> int:
    return min(10_000, max(0, int(value)))


def divide_half_up(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator >= 0:
        return (numerator + denominator // 2) // denominator
    return -((-numerator + denominator // 2) // denominator)


def parse_time(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{label} must be an ISO-8601 datetime") from exc
    else:
        raise ValueError(f"{label} must be an ISO-8601 datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def elapsed_hours(request: ReasoningRequest, field: str) -> int:
    occurred = parse_time(fact_value(request, field), field)
    seconds = int((request.evaluation_time - occurred).total_seconds())
    if seconds < 0:
        raise ValueError(f"{field} is in the future")
    return seconds // 3600


def evidence_ids(request: ReasoningRequest, *fields: str) -> tuple[str, ...]:
    wanted = set(fields)
    return tuple(sorted(item.evidence_id for item in request.context.evidence
                        if item.field in wanted))


def missing_fields(request: ReasoningRequest, fields: tuple[str, ...]) -> tuple[str, ...]:
    missing = []
    for field in fields:
        if field.startswith("neighbor:"):
            if field.split(":", 1)[1] not in request.context.neighbor_facts:
                missing.append(field)
        elif field not in request.context.facts:
            missing.append(field)
    return tuple(sorted(missing))
