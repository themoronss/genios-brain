"""Layer 1 source registry — ONE description per source, the single source of truth.

A source used to be described in four independent places that nothing checked against
each other:

  * its family              — source_families.SOURCE_FAMILY
  * whether it can be built — platform.wiring.IMPLEMENTED_SOURCE_TYPES
  * which coverage capability it satisfies — coverage.model.PROVIDER_CAPABILITY
  * its object mappings     — structured.registry

Four hand-maintained lists drift, and they had:

  * `stripe`, `razorpay`, `zendesk`, `intercom`, `mscal`, `mixpanel` carried a coverage
    capability but NO family — so every event from them landed as `unclassified`, and a
    `stripe.subscription.v1` structured mapping existed for a source the taxonomy did
    not know. (No live impact yet: none of them is buildable.)
  * `hubspot` advertises the `crm` capability that the `sales` pack REQUIRES, while no
    connector can be built for it — so `sales` can never be coverage_ready, and nothing
    in the codebase could say so.

Adding a source is now one descriptor here. The four old names are derived views over
this module, so no call site changed. tests/test_source_registry.py enforces the
invariants that let the drift happen.

`buildable` means "make_connector_for can construct this" — with Composio as the broker
that is "a Composio payload mapper is wired", not "we hand-wrote a connector".
"""
from __future__ import annotations

from dataclasses import dataclass

from genios_engine.capture.internal_knowledge import INTERNAL_KINDS

# The ten families of the vision's Layer 1, plus the honest fallback. This IS the
# taxonomy — it is declared, never derived.
FAMILIES: frozenset[str] = frozenset({
    "internal",           # the company's own records: policies, SOPs, pricing, KPIs
    "external",           # the public world: websites, news, filings
    "human_input",        # a person typed / uploaded / decided it
    "ai_generated",       # an AI agent produced it
    "enterprise_system",  # CRM / ERP / billing / client databases (systems of record)
    "communication",      # mail, chat, meetings, calendar
    "knowledge",          # docs, pages, files
    "operational",        # GitHub / Jira / CI
    "live_event",         # webhook-pushed happenings
    "intelligence",       # judgments arriving from OUTSIDE the engine
    "unclassified",       # a source we have not described yet
})

# Families a human or an agent DELIBERATELY handed us. The noise gate's N-codes exist
# for inbox firehoses; deliberately-provided material bypasses them (it still lands, is
# traced, and is deduped like everything else).
DELIBERATE_FAMILIES: frozenset[str] = frozenset({"human_input", "ai_generated"})


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    """Everything Layer 1 knows about one source, in one place."""

    source: str
    family: str
    capability: str | None = None
    buildable: bool = False
    deliberate: bool = False
    aliases: tuple[str, ...] = ()
    # () means NOT ENUMERATED (tenant-defined, e.g. client DB tables) — never "none".
    object_types: tuple[str, ...] = ()

    #: Does an object from this source ever CHANGE after we first see it?
    #:
    #: An email does not: once sent it is fixed, so its id alone is a safe dedup key. A CRM deal,
    #: a calendar event and a database row all do, and for those the id alone is a trap — the
    #: dedup ledger says "already seen" and the object freezes at whatever state it happened to
    #: be in the first time. Deal stage, account status, meeting time: all stuck, silently, with
    #: every generic test still green because gmail (immutable) is what the tests exercise.
    #:
    #: Immutable by default because most sources are, and because the cost of the two mistakes
    #: is not symmetric: a wrongly-mutable source re-lands harmlessly, a wrongly-immutable one
    #: loses every update forever.
    immutable: bool = True
    #: The field carrying "when this version was made" — `updatedAt`, `etag`, a watermark.
    #: Required for a mutable source: without it there is nothing to fold into the dedup key.
    version_field: str | None = None

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"{self.source}: unknown family {self.family!r}")
        # A mutable source with no version field cannot be deduped correctly, and discovering
        # that at capture time — per object, silently — is exactly the failure this catches at
        # import time instead.
        if not self.immutable and not self.version_field:
            raise ValueError(
                f"{self.source}: declared mutable but names no version_field — its objects "
                "would freeze at first-seen state")


SOURCES: tuple[SourceDescriptor, ...] = (
    # ── communication ────────────────────────────────────────────────────────────
    SourceDescriptor("gmail", "communication", capability="communication",
                     buildable=True, object_types=("message",)),
    SourceDescriptor("outlook", "communication", capability="communication"),
    SourceDescriptor("imap", "communication"),
    SourceDescriptor("inkbox", "communication"),
    SourceDescriptor("slack", "communication", capability="communication"),
    SourceDescriptor("teams", "communication"),
    SourceDescriptor("whatsapp", "communication"),
    SourceDescriptor("sms", "communication"),
    # A meeting is rescheduled, cancelled and re-titled; `updated` is what makes the new
    # version land instead of being deduped away as "already seen".
    SourceDescriptor("gcal", "communication", capability="calendar", buildable=True,
                     aliases=("calendar", "google_calendar"),
                     object_types=("calendar_event",),
                     immutable=False, version_field="updated"),
    SourceDescriptor("mscal", "communication", capability="calendar",
                     immutable=False, version_field="lastModifiedDateTime"),

    # ── knowledge ────────────────────────────────────────────────────────────────
    SourceDescriptor("notion", "knowledge", capability="document_store", buildable=True,
                     object_types=("page",),
                     immutable=False, version_field="last_edited_time"),
    SourceDescriptor("gdrive", "knowledge", capability="document_store", buildable=True,
                     aliases=("drive", "google_drive"), object_types=("file",),
                     immutable=False, version_field="modifiedTime"),
    SourceDescriptor("confluence", "knowledge"),
    SourceDescriptor("upload", "knowledge", deliberate=True,
                     object_types=("document_chunk",)),

    # ── enterprise systems ───────────────────────────────────────────────────────
    # THE case this flag exists for. A deal's whole value is its stage, and stage changes —
    # freezing it at first-seen means the CRM integration reports a pipeline that stopped moving
    # the day it was connected, with every generic test still green.
    SourceDescriptor("hubspot", "enterprise_system", capability="crm", buildable=True,
                     object_types=("deal",),
                     immutable=False, version_field="updatedAt"),
    SourceDescriptor("salesforce", "enterprise_system", capability="crm",
                     immutable=False, version_field="LastModifiedDate"),
    SourceDescriptor("pipedrive", "enterprise_system"),
    SourceDescriptor("stripe", "enterprise_system", capability="finance",
                     object_types=("subscription",),
                     immutable=False, version_field="updated"),
    SourceDescriptor("razorpay", "enterprise_system", capability="finance"),
    SourceDescriptor("zendesk", "enterprise_system", capability="support_desk"),
    SourceDescriptor("intercom", "enterprise_system", capability="support_desk"),
    SourceDescriptor("mixpanel", "enterprise_system", capability="product_usage"),
    # The client's own database. Object types are the tenant's tables — unenumerable here.
    # The client's own database. Object types are the tenant's tables — unenumerable here.
    # Rows change by definition; the watermark column is configured per connection.
    SourceDescriptor("postgres", "enterprise_system", capability="product_usage",
                     buildable=True, immutable=False, version_field="updated_at"),
    SourceDescriptor("database", "enterprise_system", buildable=True),
    SourceDescriptor("mysql", "enterprise_system", buildable=True),

    # ── deliberate intake (the one door) ─────────────────────────────────────────
    # The company stating something about ITSELF. No connector: the door is a person
    # writing, or an upload tagged with one of these kinds. Enters at authority rank 4
    # (see capture.internal_knowledge) — above system-of-record.
    SourceDescriptor("internal", "internal", deliberate=True,
                     object_types=tuple(sorted(INTERNAL_KINDS))),
    SourceDescriptor("human", "human_input", deliberate=True),
    SourceDescriptor("agent", "ai_generated", deliberate=True, object_types=("action",)),

    # ── operational ──────────────────────────────────────────────────────────────
    SourceDescriptor("github", "operational"),
    SourceDescriptor("gitlab", "operational"),
    SourceDescriptor("jira", "operational"),
    SourceDescriptor("linear", "operational"),

    # ── GeniOS's own outputs re-entering as evidence ─────────────────────────────
    SourceDescriptor("genios", "intelligence"),
)


def _index() -> dict[str, SourceDescriptor]:
    """source id and every alias → descriptor. Collisions are a definition error."""
    index: dict[str, SourceDescriptor] = {}
    for descriptor in SOURCES:
        for key in (descriptor.source, *descriptor.aliases):
            held = index.get(key)
            if held is not None:
                raise ValueError(
                    f"duplicate source id {key!r}: {held.source} and {descriptor.source}")
            index[key] = descriptor
    return index


_BY_ID: dict[str, SourceDescriptor] = _index()


def descriptor_of(source: str) -> SourceDescriptor | None:
    return _BY_ID.get((source or "").lower())


def family_of(source: str) -> str:
    descriptor = descriptor_of(source)
    return descriptor.family if descriptor is not None else "unclassified"


def capability_of(source: str) -> str | None:
    descriptor = descriptor_of(source)
    return descriptor.capability if descriptor is not None else None


def is_buildable(source: str) -> bool:
    descriptor = descriptor_of(source)
    return descriptor is not None and descriptor.buildable


def known_ids() -> frozenset[str]:
    """Every accepted source id, canonical and alias."""
    return frozenset(_BY_ID)


# ── Derived views — the four old names, so no call site had to change ────────────
SOURCE_FAMILY: dict[str, str] = {key: d.family for key, d in _BY_ID.items()}

DELIBERATE_SOURCES: frozenset[str] = frozenset(
    key for key, d in _BY_ID.items() if d.deliberate)

BUILDABLE_SOURCES: frozenset[str] = frozenset(
    key for key, d in _BY_ID.items() if d.buildable)

PROVIDER_CAPABILITY: dict[str, str] = {
    key: d.capability for key, d in _BY_ID.items() if d.capability is not None}


def is_mutable(source: str) -> bool:
    """Does this source's objects change after first sight?

    Unknown sources answer False — the same default a descriptor gets — because an unregistered
    source is not evidence of mutability, and treating it as mutable would park every object
    from it for lacking a version we never asked any connector to supply.
    """
    d = descriptor_of(source)
    return bool(d and not d.immutable)


def version_field_for(source: str) -> str | None:
    """The field a mutable source must carry a version in."""
    d = descriptor_of(source)
    return d.version_field if d else None
