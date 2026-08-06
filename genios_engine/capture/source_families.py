"""The ten source families of Layer 1 — now a view over the source registry.

Every SourceEvent carries a family so downstream layers can reason about the KIND of
reality an event came from without matching on source names. The pipeline never
branches on family (capture stays reasoning-free).

The taxonomy and the per-source descriptors moved to `capture.source_registry`, which
is the one place a source is described. This module keeps its public names so nothing
that imports it had to change; adding a source means adding a descriptor there, not a
line here.
"""
from __future__ import annotations

from genios_engine.capture.source_registry import (
    DELIBERATE_FAMILIES,
    DELIBERATE_SOURCES,
    FAMILIES,
    SOURCE_FAMILY,
    family_of,
)

__all__ = ["FAMILIES", "SOURCE_FAMILY", "DELIBERATE_FAMILIES", "DELIBERATE_SOURCES",
           "family_of"]
