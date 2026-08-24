from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldMap:
    source_field: str
    target: str
    value_type: str = "string"                 # string | enum | number | timestamp
    authority: str = "source_of_record"        # per-field (not every source is SoR for every field)


@dataclass(frozen=True)
class RelationMap:
    """A relationship the source object carries to OTHER entities → a graph edge.
    e.g. a calendar event's `attendees` → person nodes, each person→attended→meeting."""
    source_field: str                          # raw field holding the related entity/entities
    related_node_type: str                     # node_type of the related entity, e.g. "person"
    edge_type: str                             # e.g. "attended", "works_at", "about"
    direction: str = "in"                      # "in": related→this node; "out": this→related
    identity: str = "email"                    # how to build the related node's canonical_key


@dataclass
class StructuredMapping:
    mapping_id: str                            # versioned, e.g. hubspot.deal.v1
    source: str
    object_type: str
    identity_field: str
    node_type: str
    fields: list[FieldMap]
    intent: str
    name_field: str | None = None              # mapped target used as the node's display_name
    relations: list[RelationMap] = field(default_factory=list)   # source object → graph edges
    tags: list[str] = field(default_factory=list)
    emit_on_change: list[str] = field(default_factory=list)


_REGISTRY: dict[tuple[str, str], StructuredMapping] = {}


def register(m: StructuredMapping) -> None:
    _REGISTRY[(m.source, m.object_type)] = m


def get_mapping(source: str, object_type: str) -> StructuredMapping | None:
    return _REGISTRY.get((source, object_type))


def has_mapping(source: str, object_type: str) -> bool:
    return (source, object_type) in _REGISTRY


def all_mappings() -> list[StructuredMapping]:
    return list(_REGISTRY.values())


# ── Built-in mappings (DATA — new source = new entry here, or load YAML/DB later) ──
# The same lane serves CRM, billing, calendar, and the client's own database.
register(StructuredMapping(
    mapping_id="hubspot.deal.v1", source="hubspot", object_type="deal",
    identity_field="id", node_type="deal",
    fields=[FieldMap("dealname", "deal.title", "string"),
            FieldMap("dealstage", "deal.stage", "enum"),
            FieldMap("amount", "deal.amount", "number"),
            FieldMap("closedate", "deal.close_date", "timestamp")],
    intent="pipeline_update", name_field="deal.title", tags=["stage_change"],
    # THE CROSS-TOOL BRIDGE. Without these, a CRM deal was an ISLAND — zero edges to
    # any person — so every neighbor rule (cooling_deal, competitor_in_live_deal,
    # deal_sentiment_negative) was structurally unable to fire across tools, and
    # single_threaded_deal fired on EVERY deal (edge_count 0). Contact emails, when
    # present in the payload (either field shape), become person edges whose
    # canonical keys MERGE with email/calendar-derived persons. Absent field = no-op.
    relations=[RelationMap("contact_email", "person", "involves", "in", "email"),
               RelationMap("contacts", "person", "involves", "in", "email")],
    emit_on_change=["dealstage", "amount"]))

register(StructuredMapping(
    mapping_id="stripe.subscription.v1", source="stripe", object_type="subscription",
    identity_field="id", node_type="subscription",
    fields=[FieldMap("status", "subscription.status", "enum"),
            FieldMap("current_period_end", "subscription.current_period_end", "timestamp")],
    intent="invoice_event", tags=["subscription_change"], emit_on_change=["status"]))

register(StructuredMapping(
    mapping_id="gcal.event.v1", source="gcal", object_type="calendar_event",
    identity_field="id", node_type="meeting",
    fields=[FieldMap("summary", "meeting.title", "string"),
            FieldMap("start", "meeting.start_at", "timestamp"),
            FieldMap("end", "meeting.end_at", "timestamp"),
            FieldMap("status", "meeting.status", "enum"),
            FieldMap("description", "meeting.description", "string"),
            FieldMap("location", "meeting.location", "string")],
    intent="scheduling_move", name_field="meeting.title",
    relations=[RelationMap("attendees", "person", "attended", "in", "email")],
    emit_on_change=["start", "status"]))

# Client's own database — same mechanism, customer-defined table. (Example row shape.)
register(StructuredMapping(
    mapping_id="postgres.customer_accounts.v1", source="postgres",
    object_type="public.customer_accounts", identity_field="account_id",
    node_type="product_account",
    fields=[FieldMap("plan", "product_account.plan", "enum"),
            FieldMap("status", "product_account.status", "enum"),
            FieldMap("seats_used", "product_account.seats_used", "number",
                     authority="direct_observation")],
    intent="pipeline_update", emit_on_change=["plan", "status"]))


# ── Config-driven mappings (DATA, not code) ──────────────────────────────────────
# A client can map their OWN DB tables / CRM objects by dropping a JSON file instead of
# editing Python — the mapping is data. Set GENIOS_STRUCTURED_MAPPINGS=/path/to/file.json.
# Without it, only the built-ins above are active (behaviour unchanged). This is how an
# unmapped client table stops PARKing (see LAYER1_CAPTURE_FIXES #1) — you map it in config.
def mapping_from_dict(d: dict) -> StructuredMapping:
    """Build a StructuredMapping from a plain dict (parsed JSON). Field/relation dicts map
    1:1 to FieldMap/RelationMap kwargs, so the config shape is the dataclass shape."""
    return StructuredMapping(
        mapping_id=d["mapping_id"], source=d["source"], object_type=d["object_type"],
        identity_field=d["identity_field"], node_type=d["node_type"],
        fields=[FieldMap(**f) for f in d.get("fields", [])],
        intent=d.get("intent", ""),
        name_field=d.get("name_field"),
        relations=[RelationMap(**r) for r in d.get("relations", [])],
        tags=list(d.get("tags", [])),
        emit_on_change=list(d.get("emit_on_change", [])))


def load_mappings_from_config(path: str) -> int:
    """Register every mapping in a JSON file (a list of mapping dicts). Returns how many were
    loaded; 0 if the file is absent (never raises on a missing path — config is optional)."""
    import json
    import os
    if not path or not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    count = 0
    for d in data or []:
        register(mapping_from_dict(d))
        count += 1
    return count


import os as _os

_CONFIG_PATH = _os.environ.get("GENIOS_STRUCTURED_MAPPINGS")
if _CONFIG_PATH:                                    # opt-in: absent → only built-ins, unchanged
    load_mappings_from_config(_CONFIG_PATH)
