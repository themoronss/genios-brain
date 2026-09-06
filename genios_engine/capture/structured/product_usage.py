"""L1.3.9-U3 · product-usage event intake — the missing half of every churn signal.

"Did they log in? did they use the thing they pay for? did that stop?" is the question every
retention conversation turns on, and it is answered by data that is structured by nature: an
event name, an account, a timestamp, sometimes a quantity. Doc 03 makes the point exactly:
usage data is L1.1 priority P2, and "the mapping registry supports tenant-supplied mappings
already (`mapping_from_dict`) — this is a **configuration surface, not a new subsystem**".

So this module adds no connector, no vendor SDK and no second lane. It builds a
`StructuredMapping` — the same data type the four built-ins are — for a usage event stream whose
columns the tenant names. `capture/source_registry.py` already makes `postgres` buildable with
capability `product_usage`, and `capture/connectors/database.py` already reads changed rows off
a watermark column, so the event arrives, `gate.py` S1.5 short-circuits it, and
`mapper.map_to_extraction` carries it with zero model calls. Every piece existed; what was
missing was the mapping.

The one real rule here is the CAPABILITY GUARD. A mapping is registered by
`(source, object_type)`, so nothing structurally prevents somebody from declaring a "product
usage" mapping over a Gmail message. `product_usage_mapping` refuses any source the registry
does not describe as `product_usage`, because a churn cohort assembled from mail metadata that
was labelled as usage is worse than an empty one: it is a wrong answer wearing a
confidence of 10000.

Pure: dataclass construction over the two registries. No clock, no I/O, no float.
"""

from __future__ import annotations

from genios_engine.capture.source_registry import capability_of, descriptor_of

from .registry import FieldMap, RelationMap, StructuredMapping, register

#: The capability a source must declare before a usage mapping may be built over it. It is the
#: registry's own word (`SourceDescriptor.capability`), so adding a usage source is a descriptor
#: edit rather than a second allow-list here that would drift from it.
PRODUCT_USAGE_CAPABILITY = "product_usage"

#: The node the usage stream writes to. One node type for every tenant's usage stream, whatever
#: they call their table, so a churn rule reads one name instead of one per customer.
PRODUCT_USAGE_NODE_TYPE = "product_usage_event"

#: The namespace every target below carries, and what `StructuredMapping.target_namespace` is
#: set to. One constant, so the four target names and the declaration cannot drift apart —
#: `capture/structured/targets.py` refuses a target whose namespace is not the mapping's own.
TARGET_NAMESPACE = "product_usage"

#: The target field names a usage mapping writes. Fixed, because they are the vocabulary the
#: churn rules are written against: a tenant chooses which of THEIR columns feeds each one, and
#: never what the target is called. Letting the target be configurable would mean every tenant's
#: usage data landed under a different field name, and no rule could be written once.
EVENT_TARGET = f"{TARGET_NAMESPACE}.event"
ACCOUNT_TARGET = f"{TARGET_NAMESPACE}.account"
OCCURRED_TARGET = f"{TARGET_NAMESPACE}.occurred_at"
VALUE_TARGET = f"{TARGET_NAMESPACE}.value"

#: The registry `intent` for a usage event. Free text at this layer (Layer 2 keys emission on
#: it); `mapper.STRUCTURED_INTENT` has no row for it, so the contract's intent falls to the
#: default `inform` — which is right: a usage row states that something happened.
PRODUCT_USAGE_INTENT = "usage_event"

#: The default table a `postgres` usage stream is read from, and the object_type of the built-in
#: registered below. A tenant whose table is called something else registers their own with
#: `product_usage_mapping` (or a JSON entry) — this is the shape, not a requirement.
DEFAULT_USAGE_TABLE = "public.product_usage_events"


def product_usage_mapping(*, source: str, object_type: str, identity_field: str,
                          event_field: str, account_field: str, occurred_field: str,
                          value_field: str | None = None,
                          value_currency: str | None = None,
                          user_email_field: str | None = None,
                          mapping_id: str | None = None) -> StructuredMapping:
    """Build the structured mapping for one tenant's product-usage event stream.

    The five required columns are the five a usage event cannot be read without: what happened
    (`event_field`), to whose account (`account_field`), when (`occurred_field`), which row this
    is (`identity_field`), and where it came from (`source`/`object_type`). None of them has a
    default, because a usage stream missing any one of them produces rows that cannot be
    attributed, deduplicated or placed in time — and discovering that per row, silently, at
    capture time is exactly the failure a required argument prevents.

    `value_field` is optional and is the quantity — seats used, API calls, minutes. Pass
    `value_currency` alongside it when the quantity is MONEY (usage-based billing: an ISO 4217
    code, or the name of a column holding one is not accepted here because a usage value column
    is single-dimensioned by construction). Without a currency the value is a plain number and
    is carried as written; with one it goes through ALG-10 like every other amount in the system.

    `user_email_field` is the bridge. A usage event that names the person who caused it merges
    with the person the CRM and the mailbox already know, through `norm_email` — which is what
    turns "this account went quiet" into "the champion who ran every report stopped logging in".

    Raises `ValueError` when the source is unknown to the registry or does not declare the
    `product_usage` capability. See the module docstring for why that guard is not paranoia.
    """
    if descriptor_of(source) is None:
        raise ValueError(
            f"{source!r} is not in the source registry — a mapping for an undescribed source "
            "lands its events as `unclassified`, which is how stripe.subscription.v1 sat "
            "unnoticed. Add a SourceDescriptor first")
    declared = capability_of(source)
    if declared != PRODUCT_USAGE_CAPABILITY:
        raise ValueError(
            f"{source!r} declares capability {declared!r}, not {PRODUCT_USAGE_CAPABILITY!r} — "
            "a usage mapping over a source that is not a usage source produces churn cohorts "
            "from data that never described usage, at confidence 10000")

    fields = [
        FieldMap(event_field, EVENT_TARGET, "enum"),
        FieldMap(account_field, ACCOUNT_TARGET, "string"),
        FieldMap(occurred_field, OCCURRED_TARGET, "timestamp"),
    ]
    if value_field is not None:
        fields.append(
            FieldMap(value_field, VALUE_TARGET, "money", currency=value_currency)
            if value_currency is not None
            # `direct_observation`, not `source_of_record`: the tenant's own instrumentation
            # counted this, which is the strongest kind of claim about their own product and a
            # different kind of claim from a CRM stage somebody typed.
            else FieldMap(value_field, VALUE_TARGET, "number", authority="direct_observation"))

    relations = ([RelationMap(user_email_field, "person", "used", "in", "email")]
                 if user_email_field else [])

    return StructuredMapping(
        mapping_id=mapping_id or f"{source}.{object_type}.v1",
        source=source, object_type=object_type, identity_field=identity_field,
        node_type=PRODUCT_USAGE_NODE_TYPE, fields=fields,
        # The one mapping whose targets are NOT namespaced by its node type: the node is one
        # usage EVENT (`product_usage_event`) and the facts on it describe the usage
        # (`product_usage.*`). Declared rather than left to be inferred, because
        # `capture/structured/targets.py` refuses a target from another mapping's namespace and
        # would otherwise refuse every field this unit has ever written.
        target_namespace=TARGET_NAMESPACE,
        intent=PRODUCT_USAGE_INTENT, relations=relations,
        tags=["product_usage"],
        # A usage row is an append-only fact; there is no "changed" state to emit on. The event
        # itself is the change, so naming a column here would emit a second time for nothing.
        emit_on_change=[])


def register_product_usage_mapping(**kwargs: object) -> StructuredMapping:
    """Build one and put it in the registry. The configuration surface, in one call.

    Separate from `product_usage_mapping` so that building a mapping and MUTATING the process's
    global registry are two different acts: a caller validating a tenant's proposed configuration
    wants the first without the second, and a test that could only get a mapping by registering
    it would leak into every test that ran after it.
    """
    mapping = product_usage_mapping(**kwargs)          # type: ignore[arg-type]
    register(mapping)
    return mapping


#: The built-in. `postgres` is buildable and declares `product_usage`
#: (`source_registry.py`), its object types are the tenant's tables so any name is legal, and
#: `connectors/database.py` reads it off the `updated_at` watermark. A tenant whose usage table
#: matches this shape is carried with no configuration at all; a tenant whose table differs
#: registers their own and this one never fires.
PRODUCT_USAGE_DEFAULT = register_product_usage_mapping(
    source="postgres", object_type=DEFAULT_USAGE_TABLE, identity_field="id",
    event_field="event_name", account_field="account_id", occurred_field="occurred_at",
    value_field="quantity", user_email_field="user_email",
    mapping_id="postgres.product_usage_events.v1")


__all__ = [
    "ACCOUNT_TARGET",
    "DEFAULT_USAGE_TABLE",
    "EVENT_TARGET",
    "OCCURRED_TARGET",
    "PRODUCT_USAGE_CAPABILITY",
    "PRODUCT_USAGE_DEFAULT",
    "PRODUCT_USAGE_INTENT",
    "PRODUCT_USAGE_NODE_TYPE",
    "TARGET_NAMESPACE",
    "VALUE_TARGET",
    "product_usage_mapping",
    "register_product_usage_mapping",
]
