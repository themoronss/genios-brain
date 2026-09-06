from __future__ import annotations

from dataclasses import dataclass, field


#: The declared shape of a typed field. Two of these five are DIMENSIONED — a money field
#: carries an amount that is meaningless without its currency, a timestamp carries an instant
#: that is meaningless without a calendar — and L1.3.9's mapper routes exactly those two through
#: ALG-10 (`capture/validate/money.py`) and ALG-09 (`capture/validate/dates.py`). The other three
#: are carried as written. Kept as data so `mapping_from_dict` accepts the same words a built-in
#: mapping uses and a tenant cannot invent a sixth by typo.
VALUE_TYPES: frozenset[str] = frozenset({"string", "enum", "number", "timestamp", "money"})


@dataclass(frozen=True)
class FieldMap:
    source_field: str
    target: str
    value_type: str = "string"                 # one of VALUE_TYPES
    authority: str = "source_of_record"        # per-field (not every source is SoR for every field)
    #: The RAW field holding this amount's ISO 4217 code — HubSpot's `deal_currency_code`,
    #: a `currency` column beside an `amount` column. Preferred over `currency` because a
    #: multi-currency pipeline states the code per row and a fixed code would silently convert
    #: every euro deal into a dollar one.
    currency_field: str | None = None
    #: The fixed ISO 4217 code, for a source that is single-currency by construction (a Stripe
    #: account on one settlement currency, a billing table with no currency column).
    currency: str | None = None

    def __post_init__(self) -> None:
        """A money field must SAY what currency it is in. There is no default and there will
        not be one.

        Doc 03's own failure table names this: "Money in a typed field with no currency column
        -> wrong currency -> the mapping must declare the currency field or a fixed currency;
        no default". A default would make an unlabelled `amount` column silently dollars, which
        is a 100%-confidence wrong number on the single field the whole lane exists to protect
        — and it would carry `field_confidence=10000` while it was wrong.

        Declaring BOTH is refused too. Two sources of truth for one currency is a mapping that
        cannot be read: whichever one the code happens to consult first is the answer, and the
        other is a comment that looks like configuration.
        """
        if self.value_type not in VALUE_TYPES:
            raise ValueError(
                f"{self.source_field} -> {self.target}: unknown value_type {self.value_type!r}; "
                f"one of {sorted(VALUE_TYPES)}")
        declared = (self.currency_field is not None) + (self.currency is not None)
        if self.value_type == "money":
            if declared != 1:
                raise ValueError(
                    f"{self.source_field} -> {self.target}: a money field must declare exactly "
                    "one of currency_field or currency — an amount with no stated currency is "
                    "a number nobody can compare, and guessing one is how a euro deal becomes "
                    "a dollar deal at full confidence")
        elif declared:
            raise ValueError(
                f"{self.source_field} -> {self.target}: value_type {self.value_type!r} declares "
                "a currency; only a money field carries one, and a currency on a non-money "
                "field is configuration nothing reads")


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
    #: The first segment every one of this mapping's targets carries — `deal` for `deal.amount`,
    #: `product_usage` for `product_usage.event`. Declared only when it differs from `node_type`,
    #: which is the case for exactly one shipping mapping: L1.3.9-U3 files its facts under
    #: `product_usage.*` on a node typed `product_usage_event`, because the node is one EVENT and
    #: the facts describe the usage it records.
    #:
    #: It exists so `capture/structured/targets.py` can ask "is this target one of MINE?" — a
    #: mapping for a deal that writes `subscription.status` has been pasted together out of two
    #: mappings, and the fact it produces is filed against a node it does not describe. Read
    #: through `namespace`, never directly, so the default is stated in one place.
    target_namespace: str | None = None

    @property
    def namespace(self) -> str:
        """The namespace every target of this mapping must carry. `node_type` unless declared."""
        return self.target_namespace or self.node_type


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
            # MONEY, not "number": an amount is dimensioned, and doc 03 L1.3.9 step 3 sends it
            # through the SAME ALG-10 normalizer the prose path uses. HubSpot states the code
            # per deal in `deal_currency_code`, so the mapping names that column rather than
            # pinning one currency for every tenant.
            FieldMap("amount", "deal.amount", "money", currency_field="deal_currency_code"),
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
        emit_on_change=list(d.get("emit_on_change", [])),
        # Optional, and absent from every config written before it existed: a mapping whose
        # targets are namespaced by its own node type says nothing here and gets the right
        # answer from `namespace`.
        target_namespace=d.get("target_namespace"))


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
