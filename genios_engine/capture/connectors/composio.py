from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .base import RawObject, SourceBatch

# Composio sits BEHIND this interface — auth + Gmail data delivery only. Our contract,
# gate, graph, and acquisition orchestration stay ours; swappable for native.
#
# NOTE: the Gmail response field paths below are defensive and may need a small tweak
# against the real payload on the first live run (the "spike"). Only this mapping
# changes — nothing downstream.

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _extract_email(s: str | None) -> str | None:
    if not s:
        return None
    m = _EMAIL.search(s)
    return m.group(0).lower() if m else None


def _header(m: dict, name: str) -> str | None:
    for h in (m.get("payload") or {}).get("headers") or []:
        if str(h.get("name", "")).lower() == name.lower():
            return h.get("value")
    return None


def _parse_ts(m: dict) -> datetime:
    for k in ("internalDate", "messageTimestamp", "timestamp", "date"):
        v = m.get(k)
        if v is None:
            continue
        # epoch (ms or s), as int or digit-string
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            ms = int(v)
            return datetime.fromtimestamp(ms / 1000 if ms > 1e12 else ms, tz=timezone.utc)
        # ISO 8601, e.g. "2026-07-30T09:27:19Z"
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    # fallback: RFC-2822 Date header ("Thu, 30 Jul 2026 09:27:19 GMT")
    hdr = _header(m, "Date")
    if hdr:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(hdr)
            if dt:
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


class ComposioGmailConnector:
    source = "gmail"

    def __init__(self, *, api_key: str, user_id: str,
                 connected_account_id: str | None = None) -> None:
        self._api_key = api_key
        self._user_id = user_id
        self._account = connected_account_id or None
        self._client: Any = None

    def _client_(self) -> Any:
        if self._client is None:
            from composio import Composio          # lazy: only needed on real runs
            self._client = Composio(api_key=self._api_key)
        return self._client

    def _execute(self, slug: str, arguments: dict[str, Any]) -> Any:
        # Composio 0.18 requires an explicit toolkit version for manual execution.
        # Trial: skip (uses latest). TODO(prod): pin toolkit_versions={"gmail": "<ver>"}.
        return self._client_().tools.execute(
            slug, user_id=self._user_id, arguments=arguments,
            dangerously_skip_version_check=True,
        )

    def _fetch(self, *, max_results: int, query: str | None = None,
               page_token: str | None = None) -> Any:
        args: dict[str, Any] = {"max_results": max_results}
        if query:
            args["query"] = query
        if page_token:
            args["page_token"] = page_token
        if self._account:
            args["connected_account_id"] = self._account
        return self._execute("GMAIL_FETCH_EMAILS", args)

    def validate_connection(self) -> bool:
        self._fetch(max_results=1)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._fetch(max_results=limit, query="newer_than:90d",
                                          page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        # Resume from the stored watermark (date-granular → a natural overlap that the
        # dedup ledger de-dups) so nothing at the boundary is missed. No watermark yet
        # (first-ever connect+sync) → backfill the last 90 days so the graph starts rich,
        # not just the last 2 days. Subsequent syncs use the watermark and pull only new mail.
        query = f"after:{since.strftime('%Y/%m/%d')}" if since else "newer_than:90d"
        return self._to_batch(self._fetch(max_results=limit, query=query, page_token=cursor))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._execute("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": object_ref})

    # -- response mapping (adjust field paths on first live run) --------------------
    def _to_batch(self, result: Any) -> SourceBatch:
        data = result.get("data", result) if isinstance(result, dict) else {}
        messages = (data.get("messages") or data.get("emails")
                    or data.get("response_data") or [])
        objs = [self._to_raw(m) for m in messages if isinstance(m, dict)]
        cursor = data.get("nextPageToken") or data.get("next_page_token")
        return SourceBatch(objects=[o for o in objs if o is not None], next_cursor=cursor)

    def _to_raw(self, m: dict) -> RawObject | None:
        mid = m.get("messageId") or m.get("id") or m.get("message_id")
        if not mid:
            return None
        sender = m.get("sender") or m.get("from") or _header(m, "From")
        body = m.get("messageText") or m.get("body") or ""
        preview = m.get("preview") or m.get("snippet") or ""
        body = body if isinstance(body, str) else ""
        preview = preview if isinstance(preview, str) else ""
        snippet = preview if len(preview.strip()) >= 20 else body[:280]
        return RawObject(
            source="gmail",
            object_type="email_message",
            source_object_id=str(mid),
            occurred_at=_parse_ts(m),
            actor_email=_extract_email(sender),
            actor_type="external_contact",
            parent_object_id=m.get("threadId") or m.get("thread_id"),
            raw={
                "subject": m.get("subject") or _header(m, "Subject"),
                "body": body,        # full text → preprocess
                "snippet": snippet,  # preview, or body prefix if preview is empty
                "labelIds": m.get("labelIds") or m.get("labels") or [],
            },
        )
