"""Layer 1 source-registry invariants.

A source used to be described in four independent lists that nothing compared, so they
drifted silently. These tests are the comparison. Each one names the drift it prevents.
"""
from __future__ import annotations

from genios_engine.capture.coverage.model import PACK_REQUIREMENTS, capability_of
from genios_engine.capture.source_families import family_of
from genios_engine.capture.source_registry import (
    BUILDABLE_SOURCES,
    DELIBERATE_SOURCES,
    FAMILIES,
    PROVIDER_CAPABILITY,
    SOURCES,
    descriptor_of,
    known_ids,
)
from genios_engine.capture.structured.registry import all_mappings
from genios_engine.platform.wiring import (
    COMPOSIO_SOURCE_TYPES,
    DIRECT_SOURCE_TYPES,
    IMPLEMENTED_SOURCE_TYPES,
)

# Capabilities a pack REQUIRES that no buildable source can satisfy today. Every entry
# is a domain that can never become coverage_ready — `sales` needs a CRM, and with
# Composio as the broker that means a HubSpot/Salesforce payload mapper.
#
# This is a ratchet, not a waiver: adding a new unsatisfiable requirement fails, and so
# does closing one of these without deleting its line.
KNOWN_UNSATISFIABLE_CAPABILITIES = frozenset({"crm", "support_desk", "finance"})

# The exact source→family mapping that existed before the registry. Nothing may be lost
# in the move; new entries are fine, silent removals are not.
_LEGACY_SOURCE_FAMILY = {
    "gmail": "communication", "outlook": "communication", "imap": "communication",
    "inkbox": "communication", "slack": "communication", "teams": "communication",
    "whatsapp": "communication", "sms": "communication",
    "gcal": "communication", "calendar": "communication",
    "google_calendar": "communication",
    "notion": "knowledge", "gdrive": "knowledge", "drive": "knowledge",
    "google_drive": "knowledge", "confluence": "knowledge", "upload": "knowledge",
    "hubspot": "enterprise_system", "salesforce": "enterprise_system",
    "pipedrive": "enterprise_system", "database": "enterprise_system",
    "postgres": "enterprise_system", "mysql": "enterprise_system",
    "human": "human_input", "agent": "ai_generated",
    "github": "operational", "gitlab": "operational", "jira": "operational",
    "linear": "operational", "genios": "intelligence",
}


def test_every_family_is_declared() -> None:
    for descriptor in SOURCES:
        assert descriptor.family in FAMILIES, descriptor.source


def test_source_ids_and_aliases_are_unique() -> None:
    """Importing the registry raises on a collision; this pins the count so a silently
    shadowed alias (two sources claiming 'calendar') cannot slip through."""
    seen = [key for d in SOURCES for key in (d.source, *d.aliases)]
    assert len(seen) == len(set(seen))
    assert set(seen) == set(known_ids())


def test_aliases_resolve_to_their_canonical_descriptor() -> None:
    for descriptor in SOURCES:
        for alias in descriptor.aliases:
            assert descriptor_of(alias) is descriptor


def test_no_family_was_lost_in_the_move_to_the_registry() -> None:
    for source, family in _LEGACY_SOURCE_FAMILY.items():
        assert family_of(source) == family, source


def test_unknown_source_is_unclassified_not_an_error() -> None:
    assert family_of("weird_new_thing") == "unclassified"
    assert descriptor_of("weird_new_thing") is None


def test_buildable_matches_the_connector_dispatch() -> None:
    """`buildable=True` and the branches in make_connector_for must agree.

    Flipping buildable without wiring a branch advertises a Connect button that ends in
    'no connector wired'; wiring a branch without flipping buildable hides a working
    integration from the UI. In dev the function falls back to a fake connector for every
    source_type, so this compares the dispatch table instead of calling it.
    """
    assert DIRECT_SOURCE_TYPES | COMPOSIO_SOURCE_TYPES == BUILDABLE_SOURCES
    assert IMPLEMENTED_SOURCE_TYPES == BUILDABLE_SOURCES


def test_structured_mappings_reference_known_sources() -> None:
    """A mapping for a source the taxonomy does not know lands its events as
    `unclassified` — which is how stripe.subscription.v1 sat unnoticed."""
    for mapping in all_mappings():
        assert descriptor_of(mapping.source) is not None, mapping.mapping_id
        assert family_of(mapping.source) != "unclassified", mapping.mapping_id


def test_structured_mapping_object_types_are_declared() -> None:
    """If a source enumerates its object types, a mapping must use one of them. An empty
    tuple means 'tenant-defined' (client DB tables) and is not checked."""
    for mapping in all_mappings():
        declared = descriptor_of(mapping.source).object_types
        if declared:
            assert mapping.object_type in declared, mapping.mapping_id


def test_capability_implies_a_real_family() -> None:
    for descriptor in SOURCES:
        if descriptor.capability is not None:
            assert descriptor.family != "unclassified", descriptor.source


def test_capability_lookup_resolves_aliases() -> None:
    """A connection stored as 'google_calendar' must count toward `calendar` coverage;
    the old hand-listed dict held only the canonical id and under-reported it."""
    assert capability_of("google_calendar") == "calendar"
    assert capability_of("gcal") == "calendar"
    assert capability_of("drive") == "document_store"
    assert capability_of("nothing_like_this") is None


def test_deliberate_sources_are_known() -> None:
    assert DELIBERATE_SOURCES <= known_ids()
    assert {"human", "agent", "upload"} <= DELIBERATE_SOURCES


def test_required_pack_capabilities_are_satisfiable() -> None:
    """A pack requiring a capability no buildable source provides can never become
    coverage_ready. The allowlist is the current, deliberate debt."""
    satisfiable = {capability_of(source) for source in BUILDABLE_SOURCES} - {None}
    required = {cap for reqs in PACK_REQUIREMENTS.values() for cap in reqs["required"]}
    unsatisfiable = required - satisfiable
    assert unsatisfiable == KNOWN_UNSATISFIABLE_CAPABILITIES, (
        "pack capability coverage changed — add the new gap to "
        "KNOWN_UNSATISFIABLE_CAPABILITIES, or delete the line you just closed")
