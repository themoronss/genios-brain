"""L1.3.9-U2 · mapping coverage — which structured sources are connected but unmapped.

An unmapped structured source is not a neutral gap. It is a source that pays for a language
model call it did not need, on data that was already typed, and then records the model's
opinion at model confidence where the column deserved 10000. Doc 03 states both halves: the
metric is `unmapped_structured`, and the reason it exists is that the failure is otherwise
invisible — nothing breaks, a number is just quietly less certain than it should be, and the
bill is quietly larger.

This module answers the question at the CONNECTION level rather than the event level. Doc
03-U1's `route_structured` counts one object at a time, which tells you what the last sync did;
this tells you what the tenant's configuration will keep doing until somebody writes a mapping.

Three states, not two, and separating them is the point:

* **mapped** — a registered mapping carries this object type. The bypass works.
* **unmapped** — the source enumerates this object type and no mapping exists. This is the
  actionable row: a mapping is a data entry in `registry.py` or a JSON file
  (`load_mappings_from_config`), and writing one is minutes of work that pays every sync.
* **unenumerated** — the source's object types are tenant-defined and none was named. The
  client's own database is the case: `postgres` declares `object_types=()` because its tables
  are the customer's, and this module cannot know whether `public.orders` exists. Reporting
  that as "unmapped" would invent a gap; reporting it as "mapped" would hide one. It is a
  third answer, and the caller that knows the tenant's tables passes them and gets a real one.

Pure: a table read over the two registries, no clock, no I/O, no float. Coverage is reported in
integer basis points for the same reason every other ratio in Layer 1 is.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from genios_engine.capture.source_registry import descriptor_of
from genios_engine.capture.validate.authority import Authority, Provenance, weigh_authority

from .registry import get_mapping

#: Full coverage, in basis points — the same 0..10000 scale as every confidence in Layer 1, so a
#: reader never has to ask which unit a number is in.
BP_FULL = 10_000


@dataclass(frozen=True, slots=True)
class ConnectedObject:
    """One thing the tenant has connected, as the caller knows it.

    `object_type` is optional because a connection is usually recorded as a source alone
    ("they connected HubSpot"). Left None, the report expands it to every object type the source
    registry declares — which is the honest expansion, since those are exactly the object types
    a connector for that source can emit. A source that declares none expands to a single
    unenumerated row instead of silently disappearing from the report.
    """

    source: str
    object_type: str | None = None


@dataclass(frozen=True, slots=True)
class CoverageRow:
    """One (source, object_type) pair and whether the structured lane can carry it."""

    source: str
    #: None only on an unenumerated row — the source's object types are the tenant's to name.
    object_type: str | None
    mapping_id: str | None
    #: False when this pair would not take the structured lane at all (an email, a chat
    #: message). Such a pair is reported rather than dropped, because "we assessed it and it is
    #: not a structured source" and "we never looked" are different answers.
    structured: bool

    @property
    def mapped(self) -> bool:
        return self.mapping_id is not None

    @property
    def unenumerated(self) -> bool:
        """The source's object types are tenant-defined and none was supplied."""
        return self.object_type is None

    @property
    def actionable(self) -> bool:
        """A structured pair, named, and unmapped — the rows somebody should go and fix."""
        return self.structured and not self.mapped and not self.unenumerated


@dataclass(frozen=True, slots=True)
class MappingCoverage:
    """L1.3.9-U2's answer: every assessed pair, and the counts a dashboard reads off it.

    A typed record rather than a dict for the reason every boundary type here is one: a caller
    that reads `report["unmapped"]` gets a KeyError when the shape changes, and a caller that
    reads `report.unmapped` gets an import-time failure at the seam that changed it.
    """

    rows: tuple[CoverageRow, ...] = ()

    @property
    def mapped(self) -> tuple[CoverageRow, ...]:
        return tuple(row for row in self.rows if row.structured and row.mapped)

    @property
    def unmapped(self) -> tuple[CoverageRow, ...]:
        """The actionable rows: connected, structured, named, and carried by no mapping."""
        return tuple(row for row in self.rows if row.actionable)

    @property
    def unenumerated(self) -> tuple[CoverageRow, ...]:
        return tuple(row for row in self.rows if row.structured and row.unenumerated)

    @property
    def unmapped_structured(self) -> int:
        """Doc 03's metric, at the connection level: how many structured object types the
        tenant has connected that no mapping carries.

        Unenumerated rows are NOT counted. A number that grows every time a customer connects a
        database is a number nobody trusts, and the gap it would be counting is one this module
        has no evidence for.
        """
        return len(self.unmapped)

    @property
    def coverage_bp(self) -> int:
        """Mapped share of the ASSESSABLE structured pairs, in integer basis points.

        Unenumerated rows are excluded from both halves — they are neither a success nor a
        failure, and putting them in the denominator would make connecting a database look like
        a coverage regression. `BP_FULL` when there is nothing to assess: no structured source
        is connected, so nothing is uncovered, and reporting 0 there would light a dashboard red
        for a tenant who has done nothing wrong.
        """
        assessable = len(self.mapped) + len(self.unmapped)
        if assessable == 0:
            return BP_FULL
        return len(self.mapped) * BP_FULL // assessable


def _is_structured(source: str, object_type: str | None) -> bool:
    """Does this pair enter the structured lane? — asked of ALG-14's tables, not a second list.

    `authority.py` already declares which sources and object types are systems of record: it has
    to, because that is what ranks them at 4. Re-deriving the same judgment here from a private
    set would produce two answers that agree until the day somebody adds a source to one of
    them, and then a source would be ranked as structured while being reported as unstructured.
    """
    weight = weigh_authority(Provenance(source=source, object_type=object_type))
    return weight.authority is Authority.STRUCTURED_SOURCE


def mapping_coverage(connected: Iterable[ConnectedObject]) -> MappingCoverage:
    """L1.3.9-U2 · which of the tenant's connected structured sources have no mapping.

    Each `ConnectedObject` expands to one row per object type: the one it names, or every object
    type the source registry declares for it, or a single unenumerated row when the source's
    object types belong to the tenant. Duplicates collapse — a caller assembling this from a
    connections table will hand the same source twice — so a count is a count of object types
    and not of connection rows.

    Order is the caller's, then the registry's declaration order within a source, so the report
    reads in the order the tenant connected things rather than in a hash order that changes
    between runs.
    """
    rows: list[CoverageRow] = []
    seen: set[tuple[str, str | None]] = set()
    for item in connected:
        source = (item.source or "").strip().lower()
        if not source:
            continue
        for object_type in _object_types_of(source, item.object_type):
            key = (source, object_type)
            if key in seen:
                continue
            seen.add(key)
            mapping = get_mapping(source, object_type) if object_type is not None else None
            rows.append(CoverageRow(
                source=source, object_type=object_type,
                mapping_id=mapping.mapping_id if mapping is not None else None,
                structured=_is_structured(source, object_type)))
    return MappingCoverage(rows=tuple(rows))


def _object_types_of(source: str, stated: str | None) -> tuple[str | None, ...]:
    """The object types to assess for one connected source.

    A stated type answers for itself — the caller knows the tenant's table name and this module
    does not. Otherwise the registry's declared types are the honest expansion, and an empty
    declaration yields `(None,)`: one unenumerated row, so the source still appears in the
    report rather than vanishing from it because nobody could name its objects.
    """
    if stated:
        return (stated,)
    descriptor = descriptor_of(source)
    if descriptor is None or not descriptor.object_types:
        return (None,)
    return tuple(descriptor.object_types)


__all__ = ["BP_FULL", "ConnectedObject", "CoverageRow", "MappingCoverage", "mapping_coverage"]
