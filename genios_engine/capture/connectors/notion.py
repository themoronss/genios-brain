from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import RawObject, SourceBatch
from .composio_base import ComposioExec

# Notion via Composio. Pages are UNSTRUCTURED text → they go through the normal gate and
# on to L2 for relevance + extraction. Field paths finalized on first live run.


def _parse_ts(s: str | None) -> datetime:
    if isinstance(s, str):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _title(page: dict) -> str | None:
    props = page.get("properties") or {}
    for p in props.values():
        if isinstance(p, dict) and p.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in (p.get("title") or []))
    return page.get("title")


class ComposioNotionConnector:
    source = "notion"

    def __init__(self, *, api_key: str, user_id: str) -> None:
        self._x = ComposioExec(api_key=api_key, user_id=user_id)

    def _search(self, *, limit: int, page_token: str | None) -> dict:
        args: dict[str, Any] = {"page_size": limit}
        if page_token:
            args["start_cursor"] = page_token
        return self._x.execute("NOTION_SEARCH_NOTION_PAGE", args)

    def _markdown(self, page_id: str) -> str:
        data = self._x.execute("NOTION_GET_PAGE_MARKDOWN", {"page_id": page_id})
        md = data.get("markdown") or data.get("content") or data.get("text") or ""
        return md if isinstance(md, str) else ""

    def _to_batch(self, data: dict, since: datetime | None = None) -> SourceBatch:
        results = data.get("results") or data.get("pages") or []
        if since is not None:
            # honour the watermark BEFORE fetching content: _to_raw pulls each page's
            # full markdown, so filtering here is what stops every 6-hourly sweep from
            # re-downloading the whole workspace (`since` was previously ignored).
            # Metadata-only compare; dedup_key/content_version are untouched.
            results = [p for p in results if isinstance(p, dict)
                       and _parse_ts(p.get("last_edited_time")) > since]
        objs = [self._to_raw(p) for p in results if isinstance(p, dict)]
        cursor = data.get("next_cursor") if data.get("has_more") else None
        return SourceBatch(objects=[o for o in objs if o], next_cursor=cursor)

    def _to_raw(self, page: dict) -> RawObject | None:
        pid = page.get("id")
        if not pid:
            return None
        body = self._markdown(str(pid))
        return RawObject(
            source="notion", object_type="page", source_object_id=str(pid),
            occurred_at=_parse_ts(page.get("last_edited_time")),
            actor_email=((page.get("last_edited_by") or {}).get("email")),
            actor_type="internal_user",
            # last_edited_time bumps on every edit → new content_version → an edited page re-lands
            # and its body updates, instead of being deduped to the first version seen.
            content_version=str(page.get("last_edited_time")) if page.get("last_edited_time") else None,
            raw={"subject": _title(page), "body": body, "url": page.get("url")},
        )

    def validate_connection(self) -> bool:
        self._search(limit=1, page_token=None)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._search(limit=limit, page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        return self._to_batch(self._search(limit=limit, page_token=cursor), since=since)

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return {"body": self._markdown(object_ref)}
