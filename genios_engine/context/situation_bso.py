"""Produce the typed Layer 2 -> Layer 3 boundary objects from live L2 situation output.

Layer 2 stores situations in ``context_situations`` and their evidence across
``context_correlation_members`` + ``graph_source_refs``; the graph slice comes from the same
``NodeContext`` the reasoning engine already loads. This module packs those into the two frozen
contracts the Domain Expertise compiler consumes — ``BusinessSituationObject`` and
``SituationContextSlice`` — WITHOUT reaching past Layer 2 (Layer 3 never reads the graph itself).

Deliberately honest about the seam's gaps (see the design doc's Layer 3 gaps):
  * L2 carries NO importance -> a neutral default until Layer 6 supplies one;
  * signal ids / evidence are reconstructed from the correlation, not stored on the situation;
  * missing_fields uses field-path keys, never the plain-language ``missing`` labels (those have
    spaces and are not identifiers).
These are marked in metadata so a shadow package is never mistaken for a fully-sourced one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.visibility import Visibility

# The selector identity for this producer. Bump when the field mapping below changes so a
# replayed slice is never silently attributed to a different extraction.
SELECTOR_VERSION = "l2-situation-selector.v1"

# L2 situations refuse to carry importance/priority by design. Until Layer 6 publishes one, a
# shadow BSO uses a neutral midpoint so it neither inflates nor suppresses a package.
DEFAULT_IMPORTANCE_BP = 5000


def _bp(percent: Any) -> int:
    """L2 confidence/coverage are int 0-100; the contracts want 0-10000 basis points."""
    try:
        value = int(percent or 0) * 100
    except (TypeError, ValueError):
        value = 0
    return max(0, min(10000, value))


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else None)


def _no_floats(value: Any) -> Any:
    """The frozen contracts forbid floats (they are not replay-stable). L2 graph facts carry
    numeric confidence as float, so convert any float to Decimal (which canonicalisation allows)
    before it enters a semantic artifact. Recurses through mappings and sequences."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {k: _no_floats(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_no_floats(v) for v in value]
    return value


def gather_evidence_and_signals(
    conn, org_id: str, correlation_id: str | None, situation_id: str,
) -> tuple[list[str], list[Mapping[str, Any]]]:
    """Reconstruct the situation's qualified signal ids + evidence receipts from L2 tables.

    Both BSO fields are required and non-empty; when the correlation has no members yet we fall
    back to a single synthetic receipt derived from the situation id so the contract still holds
    and the reconstruction is visibly labelled rather than faked as source evidence.
    """
    signal_ids: list[str] = []
    evidence: list[Mapping[str, Any]] = []
    if correlation_id:
        events = conn.execute(text(
            "select event_id from context_correlation_members "
            "where org_id=:o and correlation_id=:c order by event_id"),
            {"o": org_id, "c": correlation_id}).scalars().all()
        signal_ids = [str(e) for e in events]
        if signal_ids:
            refs = conn.execute(text(
                "select event_id, source, source_object_id, evidence from graph_source_refs "
                "where org_id=:o and event_id = any(cast(:ev as text[])) order by event_id"),
                {"o": org_id, "ev": signal_ids}).mappings().all()
            evidence = [{
                "event_id": str(r["event_id"]),
                "source": r["source"],
                "source_object_id": r["source_object_id"],
                "evidence": r["evidence"],
            } for r in refs]
    if not signal_ids:
        signal_ids = [f"sig:{situation_id}"]
    if not evidence:
        evidence = [{"event_id": signal_ids[0], "source": "situation",
                     "reconstructed": True}]
    return signal_ids, evidence


def build_business_situation(
    *, org_id: str, situation: Mapping[str, Any],
    signal_ids: list[str], evidence: list[Mapping[str, Any]], trace_id: str,
) -> BusinessSituationObject:
    anchor = situation.get("anchor_node_id")
    entities: tuple[Mapping[str, Any], ...] = ()
    if anchor:
        entities = ({
            "id": str(anchor),
            "type": str(situation.get("anchor_type") or "unknown"),
            "name": str(situation.get("anchor_name") or anchor),
        },)
    timeline: tuple[Mapping[str, Any], ...] = ()
    first_seen, last_seen = situation.get("first_seen_at"), situation.get("last_seen_at")
    if first_seen or last_seen:
        timeline = ({"first_seen_at": _iso(first_seen), "last_seen_at": _iso(last_seen)},)
    domain = situation.get("domain")
    return BusinessSituationObject(
        org_id=org_id,
        trace_id=trace_id,
        visibility=Visibility(scope="org", derived_from="l2:situation"),
        id=str(situation["situation_id"]),
        signal_ids=tuple(signal_ids),
        type=str(situation["situation_type"]),
        confidence_bp=_bp(situation.get("confidence_overall")),
        importance_bp=DEFAULT_IMPORTANCE_BP,
        evidence=tuple(_no_floats(dict(e)) for e in evidence),
        entities=entities,
        timeline=timeline,
        state=str(situation.get("status") or "active"),
        metadata={
            "domain_ids": [str(domain)] if domain else [],
            "coverage_bp": _bp(situation.get("coverage")),
            "importance_source": "default",
            "shadow": True,
        },
    )


def build_context_slice(
    *, org_id: str, situation: Mapping[str, Any], facts: Mapping[str, Any],
    observations: list[Mapping[str, Any]], neighbor: tuple[int, set, Mapping[str, Any]],
    graph_version: int, eval_time: datetime, trace_id: str,
) -> SituationContextSlice:
    edge_count, neighbor_obs, neighbor_facts = neighbor
    anchor = str(situation["anchor_node_id"])
    return SituationContextSlice(
        org_id=org_id,
        trace_id=trace_id,
        visibility=Visibility(scope="org", derived_from="l2:situation"),
        id=f"slice:{situation['situation_id']}",
        graph_version=int(graph_version),
        selector_version=SELECTOR_VERSION,
        evaluation_time=eval_time,
        root_entity_ids=(anchor,),
        facts=_no_floats(dict(facts)),
        observations=tuple(_no_floats(dict(o)) for o in observations),
        neighbor_facts=_no_floats(dict(neighbor_facts)),
        neighbor_observations=tuple(sorted({str(k) for k in neighbor_obs})),
        edge_count=int(edge_count),
        missing_fields=(),
        metadata={"shadow": True},
    )


__all__ = [
    "SELECTOR_VERSION",
    "DEFAULT_IMPORTANCE_BP",
    "gather_evidence_and_signals",
    "build_business_situation",
    "build_context_slice",
]
