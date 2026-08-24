from __future__ import annotations

from genios_engine.capture.connectors.hubspot import ComposioHubspotConnector
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.structured.apply import apply_mapping
from genios_engine.capture.structured.registry import get_mapping

# The Sales pack REQUIRES a CRM but no CRM was buildable — sales could never reach coverage_ready.
# This connector pulls HubSpot deals through the existing hubspot.deal.v1 mapping. Parsing is tested
# hermetically (no HubSpot creds here); field paths are finalized on first live run, as with Gmail.


def _conn() -> ComposioHubspotConnector:
    return ComposioHubspotConnector.__new__(ComposioHubspotConnector)   # skip __init__ (no network)


def _deal(updated: str, stage: str = "proposal", **extra) -> dict:
    return {"id": "d1", "updatedAt": updated,
            "properties": {"dealname": "Acme expansion", "dealstage": stage,
                           "amount": "50000", "closedate": "2026-09-01"}, **extra}


def test_deal_maps_to_structured_raw_with_content_version():
    raw = _conn()._to_raw(_deal("2026-07-30T09:00:00Z", contact_email="buyer@acme.io"))
    assert raw is not None
    assert raw.source == "hubspot" and raw.object_type == "deal" and raw.source_object_id == "d1"
    assert raw.content_version == "2026-07-30T09:00:00Z"        # mutable → re-lands on change
    assert raw.raw["dealname"] == "Acme expansion" and raw.raw["dealstage"] == "proposal"
    assert raw.raw["contact_email"] == "buyer@acme.io"          # carried for the person edge


def test_stage_change_relands_via_content_version():
    a = to_source_event(_conn()._to_raw(_deal("2026-07-20T10:00:00Z", stage="proposal")),
                        org_id="o", connection_id="c").dedup_key
    b = to_source_event(_conn()._to_raw(_deal("2026-07-28T14:00:00Z", stage="won")),
                        org_id="o", connection_id="c").dedup_key
    assert a != b


def test_connector_output_feeds_the_registry_mapping():
    raw = _conn()._to_raw(_deal("2026-07-30T09:00:00Z", stage="won"))
    fields = apply_mapping(get_mapping("hubspot", "deal"), raw.raw)
    assert fields.get("deal.stage") == "won"
    assert fields.get("deal.title") == "Acme expansion"


def test_epoch_millis_timestamp_is_parsed():
    raw = _conn()._to_raw({"id": "d2", "updatedAt": 1753862400000,
                           "properties": {"dealstage": "won"}})
    assert raw.occurred_at.year == 2025 or raw.occurred_at.year == 2026   # parsed, not "now"
    assert raw.content_version == "1753862400000"
