"""Deterministic Layer 5.2 destination routing over registered adapters."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


DESTINATION_VERSION = "destination.v1"


@dataclass(frozen=True, slots=True)
class RegisteredDestination:
    channel: str
    config: Mapping[str, Any]

    @property
    def priority(self) -> int:
        value = self.config.get("priority")
        if isinstance(value, bool) or not isinstance(value, int):
            return {"slack": 100, "teams": 90, "webhook": 80}.get(self.channel, 10)
        return max(0, min(value, 1_000))

    def enabled_for(self, purpose: str) -> bool:
        key = f"{purpose}_enabled"
        value = self.config.get(key)
        if isinstance(value, bool):
            return value
        if purpose == "digest":
            return self.channel in {"slack", "teams"}
        # Every registered surface can be the primary destination. Pull surfaces have a lower
        # default priority than active transports, so they become the fallback when no external
        # channel is configured rather than duplicating a Slack push.
        return True


def destination_from_row(row: Mapping[str, Any]) -> RegisteredDestination:
    raw = row.get("config")
    if isinstance(raw, Mapping):
        config = dict(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {}
        config = parsed if isinstance(parsed, dict) else {}
    else:
        config = {}
    return RegisteredDestination(channel=str(row["channel"]), config=config)


def route_destinations(destinations: list[RegisteredDestination], *, purpose: str) \
        -> tuple[RegisteredDestination, ...]:
    """Primary then fallbacks. Stable ties resolve by channel name, never row order."""
    if purpose not in {"push", "digest"}:
        raise ValueError("purpose must be push or digest")
    eligible = [item for item in destinations if item.enabled_for(purpose)]
    return tuple(sorted(eligible, key=lambda item: (-item.priority, item.channel)))


__all__ = ["DESTINATION_VERSION", "RegisteredDestination", "destination_from_row",
           "route_destinations"]
