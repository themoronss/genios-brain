from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import RawObject, SourceBatch
from .composio_base import ComposioExec

# HubSpot (CRM) via Composio. Deals are STRUCTURED — they carry the hubspot.deal.v1 mapping, so the
# gate short-circuits them (no LLM). Field paths are defensive and finalized against the real Composio
# response on the first live run (as with Gmail/Calendar). We pull each deal's contact associations
# too, so a deal is not a graph ISLAND: the mapping turns contact_email/contacts into person edges
# (single_threaded_deal / cooling_deal etc. were structurally unable to fire without them).


def _parse_ts(v: Any) -> datetime:
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if isinstance(v, (int, float)):                 # HubSpot often uses epoch millis
        try:
            return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    return datetime.now(timezone.utc)


class ComposioHubspotConnector:
    source = "hubspot"

    def __init__(self, *, api_key: str, user_id: str) -> None:
        self._x = ComposioExec(api_key=api_key, user_id=user_id)

    def _list(self, *, limit: int, page_token: str | None) -> dict:
        args: dict[str, Any] = {"limit": limit,
                                "properties": ["dealname", "dealstage", "amount", "closedate"]}
        if page_token:
            args["after"] = page_token
        return self._x.execute("HUBSPOT_LIST_DEALS", args)

    def _to_batch(self, data: dict) -> SourceBatch:
        results = data.get("results") or data.get("deals") or data.get("data") or []
        objs = [self._to_raw(d) for d in results if isinstance(d, dict)]
        cursor = None
        paging = data.get("paging")
        if isinstance(paging, dict) and isinstance(paging.get("next"), dict):
            cursor = paging["next"].get("after")
        return SourceBatch(objects=[o for o in objs if o], next_cursor=cursor)

    def _to_raw(self, d: dict) -> RawObject | None:
        did = d.get("id") or d.get("dealId")
        if did is None:
            return None
        props = d.get("properties") if isinstance(d.get("properties"), dict) else {}
        # Flatten deal properties to top-level raw so hubspot.deal.v1's source_fields (dealname,
        # dealstage, amount, closedate) resolve, and carry contact associations for the person edges.
        raw: dict[str, Any] = {**props}
        contacts = d.get("contacts") or d.get("contact_emails")
        if contacts:
            raw["contacts"] = contacts
        ce = d.get("contact_email") or props.get("contact_email")
        if ce:
            raw["contact_email"] = ce
        updated = d.get("updatedAt") or d.get("updated_at") or props.get("hs_lastmodifieddate")
        return RawObject(
            source="hubspot", object_type="deal", source_object_id=str(did),
            occurred_at=_parse_ts(updated),
            actor_type="system",
            # updatedAt bumps whenever the deal changes (stage move, amount) → new content_version →
            # the deal re-lands and deal.stage/amount update, instead of freezing at first-seen.
            content_version=str(updated) if updated else None,
            raw=raw,
        )

    def validate_connection(self) -> bool:
        self._list(limit=1, page_token=None)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        # HubSpot list is re-scanned; unchanged deals dedup (stable content_version), changed ones
        # re-land. A since-filter (hs_lastmodifieddate > since) is a first-live-run refinement.
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._x.execute("HUBSPOT_GET_DEAL", {"deal_id": object_ref})
