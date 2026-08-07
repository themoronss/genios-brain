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

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"{self.source}: unknown family {self.family!r}")


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
    SourceDescriptor("gcal", "communication", capability="calendar", buildable=True,
                     aliases=("calendar", "google_calendar"),
                     object_types=("calendar_event",)),
    SourceDescriptor("mscal", "communication", capability="calendar"),

    # ── knowledge ────────────────────────────────────────────────────────────────
    SourceDescriptor("notion", "knowledge", capability="document_store", buildable=True,
                     object_types=("page",)),
    SourceDescriptor("gdrive", "knowledge", capability="document_store", buildable=True,
                     aliases=("drive", "google_drive"), object_types=("file",)),
    SourceDescriptor("confluence", "knowledge"),
    SourceDescriptor("upload", "knowledge", deliberate=True,
                     object_types=("document_chunk",)),

    # ── enterprise systems ───────────────────────────────────────────────────────
    SourceDescriptor("hubspot", "enterprise_system", capability="crm", buildable=True,
                     object_types=("deal",)),
    SourceDescriptor("salesforce", "enterprise_system", capability="crm"),
    SourceDescriptor("pipedrive", "enterprise_system"),
    SourceDescriptor("stripe", "enterprise_system", capability="finance",
                     object_types=("subscription",)),
    SourceDescriptor("razorpay", "enterprise_system", capability="finance"),
    SourceDescriptor("zendesk", "enterprise_system", capability="support_desk"),
    SourceDescriptor("intercom", "enterprise_system", capability="support_desk"),
    SourceDescriptor("mixpanel", "enterprise_system", capability="product_usage"),
    # The client's own database. Object types are the tenant's tables — unenumerable here.
    SourceDescriptor("postgres", "enterprise_system", capability="product_usage",
                     buildable=True),
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
