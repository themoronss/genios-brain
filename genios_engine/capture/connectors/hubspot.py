from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

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


#: Fields that mean "this payload carries the deal itself" rather than only a pointer to it.
_DEAL_FIELDS = ("properties", "dealname", "dealstage", "amount", "closedate")


def _webhook_record(payload: Any) -> dict | None:
    """The deal record inside a pushed envelope, whatever wrapper it arrived in."""
    if not isinstance(payload, Mapping):
        return None
    for key in ("deal", "object", "record"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            return dict(nested)
    return dict(payload)


def _has_deal_fields(record: Mapping[str, Any]) -> bool:
    return any(record.get(f) for f in _DEAL_FIELDS)


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

    def webhook_objects(self, payload: Mapping[str, Any]) -> tuple[RawObject, ...]:
        """L1.2.5-U1 — one pushed HubSpot trigger → the row a poll of that deal produces.

        THIS IS THE SOURCE THAT WAS DROPPING ITS ENTIRE REAL-TIME LANE. `dispatch.py` had no
        HubSpot branch, so every CRM push answered "unmapped payload" while the poll path read
        the same deals fine.

        Two envelope shapes arrive, and only one of them carries a record. Composio nests the
        object (`deal` / `object` / `record`) or sends it bare; HubSpot's own webhook sends a
        PROPERTY CHANGE — an `objectId` and the one field that moved, nothing else. Parsing that
        envelope on its own would land a deal with no name, stage or amount and freeze the real
        one out by dedup, so an id-only push FETCHES the deal: same record, same `_to_raw`, same
        row as the sweep. If the fetch cannot be made (no credentials) or comes back empty, this
        reports nothing rather than fabricating a hollow deal.
        """
        record = _webhook_record(payload)
        if record is None:
            return ()
        if not _has_deal_fields(record):
            record = self._fetch_deal(record)
            if record is None:
                return ()
        obj = self._to_raw(record)
        return (obj,) if obj is not None else ()

    def _fetch_deal(self, record: dict) -> dict | None:
        """Resolve an id-only push into the full deal, or None when we cannot."""
        did = record.get("id") or record.get("dealId") or record.get("objectId")
        if did is None:
            return None
        try:
            fetched = self.fetch_content(str(did))
        except Exception:      # noqa: BLE001 — a webhook must never 500 on a provider hiccup
            return None
        if not isinstance(fetched, Mapping):
            return None
        inner = fetched.get("data") if isinstance(fetched.get("data"), Mapping) else fetched
        deal = _webhook_record(inner)
        return deal if deal is not None and _has_deal_fields(deal) else None

    def _to_raw(self, d: dict) -> RawObject | None:
        # `objectId` is HubSpot's own name for the id in a webhook envelope; the list API says
        # `id`. Both read here so ONE parser serves both doors (L1.2.5-U1 parity).
        did = d.get("id") or d.get("dealId") or d.get("objectId")
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
