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
    spaces and are not identifiers) — so it is derived here from the domain spec's expected
    fields rather than copied off the situation row.
These are marked in metadata so a shadow package is never mistaken for a fully-sourced one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from genios_engine.context.domain_spec import spec_for
from genios_engine.context.situations import SCORE_MAX
from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.contracts.visibility import Visibility, narrowest

# The selector identity for this producer. Bump when the field mapping below changes so a
# replayed slice is never silently attributed to a different extraction.
SELECTOR_VERSION = "l2-situation-selector.v1"

# L2 situations refuse to carry importance/priority by design. Until Layer 6 publishes one, a
# shadow BSO uses a neutral midpoint so it neither inflates nor suppresses a package.
DEFAULT_IMPORTANCE_BP = 5000


def _bp(percent: Any) -> int:
    """L2 confidence/coverage are int 0..SCORE_MAX percent; the contracts want basis points.

    The clamp is a floor/ceiling on a legal percent, NOT a scale converter. Feed it a number
    already in basis points and it saturates silently: 2500 (a knowledge_gap coverage honestly
    capped at a quarter) and 3000 (escalation) both came out of here as 10000 — the same value a
    fully-covered recorded situation produces — which is exactly the "reports coverage it does not
    have" failure the caps exist to prevent, and it left
    `expertise_builder`'s `min(situation.confidence_bp, expert.coverage_bp)` with nothing to cap.
    `situations.SCORE_MAX` now names the storage unit so a writer cannot pick the other one by
    accident, and `tests/test_situation_bso.py` pins that an inferred situation can never reach a
    recorded one's coverage across this seam.
    """
    try:
        value = int(percent or 0) * 100
    except (TypeError, ValueError):
        value = 0
    return max(0, min(SCORE_MAX * 100, value))


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


#: Above this many distinct external counterparties, one anchor is not describing one
#: relationship — it is doing multi-relationship duty. Two is the honest floor: a genuine
#: 1:1 relationship has exactly one, and a warm intro (one sender, one new contact) has two
#: without being a chimera. Three or more distinct external parties correlated onto a single
#: anchor is the Boardy shape — a connector's own address absorbing everyone it introduced.
SPLIT_REQUIRED_THRESHOLD = 2


def gather_visibility(conn, org_id: str, correlation_id: str | None) -> Visibility:
    """The situation's audience = the NARROWEST merge of its evidence's audiences.

    Both builders stamped `Visibility(scope="org")` as a literal. Harmless while every event was
    org-scoped — and L1-04 ended that: communication events now land `participants`-scoped with
    real principals, so a situation built from a two-person thread claiming org visibility is
    exactly the widening `contracts/visibility.narrowest` exists to prevent. The merge can only
    narrow; a situation with no member evidence stays org (there is nothing narrower to honour).
    """
    if not correlation_id:
        return Visibility(scope="org", derived_from="l2:situation:no_members")
    rows = conn.execute(text(
        "select distinct se.visibility_scope, se.visibility_principals "
        "from context_correlation_members m "
        "join source_events se on se.event_id = m.event_id and se.org_id = m.org_id "
        "where m.org_id = :o and m.correlation_id = :c and se.visibility_scope is not null"),
        {"o": org_id, "c": correlation_id}).fetchall()
    if not rows:
        return Visibility(scope="org", derived_from="l2:situation:pre_visibility_capture")
    merged = narrowest(*(
        Visibility(scope=r.visibility_scope, principals=list(r.visibility_principals or ()),
                   derived_from="source_event")
        for r in rows))
    return Visibility(scope=merged.scope, principals=merged.principals,
                      derived_from="l2:narrowest_of_members",
                      excluded_subjects=merged.excluded_subjects)


def gather_members(conn, org_id: str, correlation_id: str | None) -> tuple[Mapping[str, Any], ...]:
    """The DISTINCT real counterparties actually correlated onto this situation.

    `build_business_situation` used to build `entities` as a one-element tuple from
    `anchor_node_id` alone — so a situation anchored on `boardy.ai` with 68 correlated events
    reported as being about ONE entity, the connector bot, rather than the dozens of real people
    it introduced. Every later layer inherited that: L3 reasoned about "the Boardy relationship"
    as a unit, and a rejected pitch to one introduced founder read as evidence about all of them.

    This is "real member evidence" in the sense the gap asks for: derived from the actor on each
    correlated event, not synthesised or defaulted. Grouped by email so the same person across
    several events is one entity, not one per message.
    """
    if not correlation_id:
        return ()
    rows = conn.execute(text(
        "select se.actor->>'email' as email, se.actor->>'type' as actor_type, "
        "min(se.occurred_at) as first_seen, count(*) as n "
        "from context_correlation_members m "
        "join source_events se on se.event_id = m.event_id and se.org_id = m.org_id "
        "where m.org_id = :o and m.correlation_id = :c and se.actor->>'email' is not null "
        "group by 1, 2 order by n desc, email"),
        {"o": org_id, "c": correlation_id}).mappings().all()
    return tuple({
        "id": str(r["email"]),
        "type": str(r["actor_type"] or "unknown"),
        "name": str(r["email"]),
        "event_count": int(r["n"]),
    } for r in rows)


def _distinct_external_domains(members: tuple[Mapping[str, Any], ...]) -> set[str]:
    domains = set()
    for m in members:
        if m.get("type") != "external_contact":
            continue
        email = str(m.get("id") or "")
        if "@" in email:
            domains.add(email.rsplit("@", 1)[1].lower())
    return domains


def build_business_situation(
    *, org_id: str, situation: Mapping[str, Any],
    signal_ids: list[str], evidence: list[Mapping[str, Any]], trace_id: str,
    members: tuple[Mapping[str, Any], ...] = (),
    visibility: Visibility | None = None,
) -> BusinessSituationObject:
    """``members`` — real correlated counterparties from ``gather_members`` — is a separate,
    explicit parameter rather than a key smuggled onto ``situation``. Callers pass a raw DB row
    for ``situation`` in every existing call site; making a new field's absence silently produce
    the OLD anchor-only behaviour is safer than requiring every caller to know a magic key."""
    anchor = situation.get("anchor_node_id")
    if members:
        # Real distinct counterparties, not the anchor alone. Capped like every other list this
        # module emits — a BSO is a summary a human or an LLM reads, not the correlation table.
        entities = tuple(dict(m) for m in sorted(
            members, key=lambda m: -int(m.get("event_count", 0)))[:20])
    elif anchor:
        # No correlation membership to draw from (a fresh or synthetic situation) — the anchor
        # is still the only entity we can honestly name, same as before this fix.
        entities = ({
            "id": str(anchor),
            "type": str(situation.get("anchor_type") or "unknown"),
            "name": str(situation.get("anchor_name") or anchor),
        },)
    else:
        entities = ()
    split_required = len(_distinct_external_domains(members)) > SPLIT_REQUIRED_THRESHOLD
    timeline: tuple[Mapping[str, Any], ...] = ()
    first_seen, last_seen = situation.get("first_seen_at"), situation.get("last_seen_at")
    if first_seen or last_seen:
        timeline = ({"first_seen_at": _iso(first_seen), "last_seen_at": _iso(last_seen)},)
    domain = situation.get("domain")
    return BusinessSituationObject(
        org_id=org_id,
        trace_id=trace_id,
        visibility=visibility or Visibility(scope="org", derived_from="l2:situation"),
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
            # One anchor correlating more than SPLIT_REQUIRED_THRESHOLD distinct external
            # counterparties is not describing one relationship. Surfaced rather than silently
            # reasoned over as a unit — a reviewer (or, later, an L2 re-correlation pass) decides
            # whether and how to split it; this module only refuses to hide that the question
            # exists.
            "split_required": split_required,
            "distinct_counterparty_count": len(entities),
        },
    )



def _missing_paths(situation: Mapping[str, Any], facts: Mapping[str, Any],
                   neighbor_facts: Mapping[str, Any]) -> tuple[str, ...]:
    """Which of this situation type's expected fields the graph does not hold, as FIELD PATHS.

    This used to be a hardcoded empty tuple, and an empty `missing_fields` is not a neutral
    default — it is a claim. `packs/compiler/context_adapter.evaluate` consults exactly this set
    to decide whether a predicate is UNKNOWN, so with it empty an `exists:` test on a field
    nothing ever wrote returned a confident FALSE. The situation was then silently not routed,
    indistinguishable from a situation correctly judged not to apply, and every downstream reader
    was told the context was complete.

    Derived from `domain_spec.expected_fields` — the same declaration `situations.coverage_score`
    already scores against — so the two can never disagree about what a situation type is supposed
    to know. The neighbourhood counts as held: `reason/adapters/native.py` borrows a missing root
    field from the 1-hop neighbours, so a field present there is one the reasoner can actually
    read, and calling it missing here would abstain over evidence we have.

    An unregistered domain declares no expected fields and therefore reports nothing missing —
    unchanged behaviour, and correct: we cannot name a gap in a domain nobody has described.
    """
    expected = spec_for(situation.get("domain")).fields_for(str(situation["situation_type"]))
    if not expected:
        return ()
    held = set(facts or ()) | set(neighbor_facts or ())
    return tuple(sorted(path for path in expected if path not in held))

def build_context_slice(
    *, org_id: str, situation: Mapping[str, Any], facts: Mapping[str, Any],
    observations: list[Mapping[str, Any]], neighbor: tuple[int, set, Mapping[str, Any]],
    graph_version: int, eval_time: datetime, trace_id: str,
    visibility: Visibility | None = None,
) -> SituationContextSlice:
    edge_count, neighbor_obs, neighbor_facts = neighbor
    anchor = str(situation["anchor_node_id"])
    return SituationContextSlice(
        org_id=org_id,
        trace_id=trace_id,
        visibility=visibility or Visibility(scope="org", derived_from="l2:situation"),
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
        missing_fields=_missing_paths(situation, facts, neighbor_facts),
        metadata={"shadow": True},
    )


__all__ = [
    "SELECTOR_VERSION",
    "gather_visibility",
    "DEFAULT_IMPORTANCE_BP",
    "gather_evidence_and_signals",
    "build_business_situation",
    "build_context_slice",
]
