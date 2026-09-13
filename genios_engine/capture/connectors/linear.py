from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .base import RawObject, SourceBatch
from .composio_base import ComposioExec

# Linear (issue tracker) via Composio. Issues are STRUCTURED — `linear.issue.v1`
# (capture/structured/registry.py) maps them to `task` nodes with no LLM: task.status /
# task.state_type / task.project / task.labels / task.assignee / task.due_at, which is what the P4
# readiness report (reason/team/readiness.py) counts. Mirrors hubspot.py: one `_to_raw` serves the
# poll and the webhook door.
#
# UNVERIFIED — READ BEFORE THE FIRST LIVE RUN. No live Linear account has been connected through
# Composio for this build. The tool slugs and their argument names below are best-effort from
# Composio's naming convention, and the response envelope from Linear's GraphQL shape
# (`issues { nodes { … } pageInfo { hasNextPage endCursor } }`). They live in LINEAR_TOOL_SLUGS and
# `_list` ONLY, and the envelope is read defensively; correct them there against the first real
# response, exactly as the HubSpot field paths were. Tests drive a fake Composio executor.

#: THE one place the Composio slugs live. UNVERIFIED against a live account (see above).
LINEAR_TOOL_SLUGS: dict[str, str] = {
    "list_issues": "LINEAR_LIST_LINEAR_ISSUES",
    "get_issue": "LINEAR_GET_LINEAR_ISSUE",
}


def _parse_ts(v: Any) -> datetime:
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _pick(v: Any, *keys: str) -> str | None:
    """A nested `{name: …}` object or a bare string → the string."""
    if isinstance(v, Mapping):
        for k in keys:
            if isinstance(v.get(k), str) and v[k].strip():
                return v[k].strip()
        return None
    return v.strip() if isinstance(v, str) and v.strip() else None


def _labels(v: Any) -> list[str]:
    if isinstance(v, Mapping):
        v = v.get("nodes") or v.get("items") or []
    out = []
    for item in v if isinstance(v, list) else []:
        name = _pick(item, "name")
        if name:
            out.append(name)
    return sorted(set(out))


def _issues_of(data: Any) -> list[dict]:
    if not isinstance(data, Mapping):
        return []
    for key in ("issues", "nodes", "items", "data", "results"):
        v = data.get(key)
        if isinstance(v, Mapping):
            inner = _issues_of(v)
            if inner:
                return inner
        if isinstance(v, list):
            return [d for d in v if isinstance(d, dict)]
    return []


def _cursor_of(data: Any) -> str | None:
    if not isinstance(data, Mapping):
        return None
    for holder in (data.get("issues"), data):
        if isinstance(holder, Mapping) and isinstance(holder.get("pageInfo"), Mapping):
            page = holder["pageInfo"]
            return page.get("endCursor") if page.get("hasNextPage") else None
    return None


#: Fields that mean "this payload carries the issue itself" rather than only a pointer to it.
_ISSUE_FIELDS = ("title", "state", "stateName")


class ComposioLinearConnector:
    source = "linear"

    def __init__(self, *, api_key: str, user_id: str, executor: Any = None) -> None:
        # `executor` is the test seam (a fake Composio with the same `.execute(slug, args)`).
        self._x = executor if executor is not None else ComposioExec(api_key=api_key,
                                                                     user_id=user_id)

    def _list(self, *, limit: int, page_token: str | None) -> dict:
        args: dict[str, Any] = {"first": int(limit)}
        if page_token:
            args["after"] = page_token
        return self._x.execute(LINEAR_TOOL_SLUGS["list_issues"], args)

    def _to_batch(self, data: dict) -> SourceBatch:
        objs = [self._to_raw(d) for d in _issues_of(data)]
        return SourceBatch(objects=[o for o in objs if o], next_cursor=_cursor_of(data))

    def _to_raw(self, d: Mapping[str, Any]) -> RawObject | None:
        iid = d.get("id") or d.get("issueId")
        if not iid:
            return None
        state = d.get("state")
        raw: dict[str, Any] = {
            "id": str(iid),
            "identifier": d.get("identifier"),
            "title": d.get("title"),
            "state_name": _pick(state, "name") or _pick(d.get("stateName")),
            "state_type": _pick(state, "type"),
            "assignee_email": (_pick(d.get("assignee"), "email") or "").lower() or None,
            "project": _pick(d.get("project"), "name"),
            "team": _pick(d.get("team"), "key", "name"),
            "due_date": d.get("dueDate") or d.get("due_date"),
            "completed_at": d.get("completedAt") or d.get("completed_at"),
            "url": d.get("url"),
        }
        labels = _labels(d.get("labels"))
        if labels:
            raw["labels"] = ", ".join(labels)
        raw = {k: v for k, v in raw.items() if v not in (None, "")}
        updated = d.get("updatedAt") or d.get("updated_at")
        return RawObject(
            source="linear", object_type="issue", source_object_id=str(iid),
            occurred_at=_parse_ts(updated), actor_type="system",
            # updatedAt moves on every state change → a new content_version → the issue re-lands
            # and task.status updates instead of freezing at first-seen.
            content_version=str(updated) if updated else None,
            raw=raw)

    def webhook_objects(self, payload: Mapping[str, Any]) -> tuple[RawObject, ...]:
        """One pushed Linear trigger → the row a poll of that issue produces. Linear's own webhook
        is `{action, type: "Issue", data: {…}}`; a non-Issue type (Comment, Project…) is not an
        issue and maps to nothing. An id-only push fetches the issue, or reports nothing."""
        if not isinstance(payload, Mapping):
            return ()
        kind = payload.get("type")
        if isinstance(kind, str) and kind.lower() != "issue":
            return ()
        record = next((dict(payload[k]) for k in ("data", "issue", "object", "record")
                       if isinstance(payload.get(k), Mapping)), dict(payload))
        if not any(record.get(f) for f in _ISSUE_FIELDS):
            record = self._fetch_issue(record)
            if record is None:
                return ()
        obj = self._to_raw(record)
        return (obj,) if obj is not None else ()

    def _fetch_issue(self, record: Mapping[str, Any]) -> dict | None:
        iid = record.get("id") or record.get("issueId")
        if not iid:
            return None
        try:
            fetched = self.fetch_content(str(iid))
        except Exception:      # noqa: BLE001 — a webhook must never 500 on a provider hiccup
            return None
        if not isinstance(fetched, Mapping):
            return None
        issue = fetched.get("issue") if isinstance(fetched.get("issue"), Mapping) else fetched
        return dict(issue) if any(issue.get(f) for f in _ISSUE_FIELDS) else None

    def validate_connection(self) -> bool:
        self._list(limit=1, page_token=None)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        # Re-scanned like HubSpot: unchanged issues dedup on a stable content_version, changed
        # ones re-land. An `updatedAt > since` filter is a first-live-run refinement.
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._x.execute(LINEAR_TOOL_SLUGS["get_issue"], {"issue_id": object_ref})
