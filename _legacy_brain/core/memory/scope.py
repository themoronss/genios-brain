"""Scope enforcement — DEFENSE IN DEPTH (per g-i-1 §1.2.1).

Two layers, both required:
1. PULL-TIME: scope pushed into source query where possible (skip fetching out-of-scope).
2. POST-FETCH GATE: re-check every record before it reaches the normalizer.

4 granularity levels:
- SOURCE          entire source instance
- CONTAINER       folder / label / database / collection
- ITEM_ATTRIBUTE  tag-based include/exclude
- TIME            only items >= since

If a server cannot honor a scope, the post-fetch gate MUST still drop it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.foundations.telemetry import get_logger
from core.memory.types import RawRecord, ReadScope, ScopeLevel

log = get_logger(__name__)


class ScopeEnforcer:
    """Holds a set of grants for one connection. Records pass only if ALL grants pass."""

    def __init__(self, scopes: list[ReadScope], connection_id: str, org_id: str) -> None:
        self._scopes = scopes
        self._connection_id = connection_id
        self._org_id = org_id
        self._drops = 0

    @property
    def drop_count(self) -> int:
        """How many records have been dropped so far (for observability)."""
        return self._drops

    def is_allowed(self, record: RawRecord) -> bool:
        """Post-fetch gate. Returns False if any scope rejects the record.

        Drop count incremented (not the record content) for observability.
        """
        for scope in self._scopes:
            if not self._check_one(scope, record):
                self._drops += 1
                # Log only refs + level, NEVER content
                log.info(
                    "scope_drop",
                    connection_id=self._connection_id,
                    org_id=self._org_id,
                    native_id=record.native_id,
                    scope_level=scope.level.value,
                )
                return False
        return True

    def filter(self, records: list[RawRecord]) -> list[RawRecord]:
        """Convenience: drop out-of-scope records from a batch."""
        return [r for r in records if self.is_allowed(r)]

    def server_side_hints(self) -> dict[str, list[str]]:
        """Hints adapters can push into source queries to avoid fetching out-of-scope.

        Adapters use these when the provider's API supports container/tag/time filters.
        The post-fetch gate is still mandatory — hints are best-effort only.
        """
        hints: dict[str, list[str]] = {"containers": [], "include_tags": [], "exclude_tags": []}
        since: datetime | None = None
        for scope in self._scopes:
            if scope.level == ScopeLevel.CONTAINER:
                hints["containers"].extend(scope.include)
            elif scope.level == ScopeLevel.ITEM_ATTRIBUTE:
                hints["include_tags"].extend(scope.include)
                hints["exclude_tags"].extend(scope.exclude)
            elif scope.level == ScopeLevel.TIME and scope.since is not None:
                if since is None or scope.since > since:
                    since = scope.since
        if since is not None:
            hints["since"] = [since.isoformat()]
        return hints

    # ── per-scope checks ───────────────────────────────────────────────────

    def _check_one(self, scope: ReadScope, record: RawRecord) -> bool:
        match scope.level:
            case ScopeLevel.SOURCE:
                return True
            case ScopeLevel.CONTAINER:
                return self._check_container(scope, record)
            case ScopeLevel.ITEM_ATTRIBUTE:
                return self._check_attribute(scope, record)
            case ScopeLevel.TIME:
                return self._check_time(scope, record)

    @staticmethod
    def _check_container(scope: ReadScope, record: RawRecord) -> bool:
        container = record.fields.get("container")
        if container is None:
            # No container info -> conservative: drop if any include is set
            return not scope.include
        if container in scope.exclude:
            return False
        if scope.include and container not in scope.include:
            return False
        return True

    @staticmethod
    def _check_attribute(scope: ReadScope, record: RawRecord) -> bool:
        tags = _as_str_list(record.fields.get("tags"))
        # Exclude wins over include
        if any(t in scope.exclude for t in tags):
            return False
        if scope.include and not any(t in scope.include for t in tags):
            return False
        return True

    @staticmethod
    def _check_time(scope: ReadScope, record: RawRecord) -> bool:
        if scope.since is None:
            return True
        ts = record.fields.get("timestamp")
        record_dt = _coerce_dt(ts)
        if record_dt is None:
            return False  # missing timestamp on a TIME-scoped read -> drop
        return record_dt >= scope.since


# ─── helpers ────────────────────────────────────────────────────────────────


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def _coerce_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, tz=UTC)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None
