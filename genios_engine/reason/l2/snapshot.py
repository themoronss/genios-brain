"""GeniOS-008 L2 R2 · the Context Adapter — a BOUNDED, frozen snapshot of what the company knows.

`context/bounded_read.read_bounded` was built for exactly this and had no caller; the old lanes read the
whole tenant (`reason/runner._bulk_load_facts`). This is its first caller. The run's seeds — the file's
anchor, or the nodes the subject's own events wrote — are walked two hops, at most `MAX_NODES` nodes, and
the view comes back with the graph REVISION it saw and whether a cap stopped it. Nothing in the run reads
the graph after this: the prompt is built from the snapshot.

⛔ `truncated` IS PRINTED. A view a cap stopped is "we stopped looking", never "there is nothing more", and
the dossier says so in its coverage block, so the model cannot claim the absence.

GeniOS-011 S16.U3 · AS OF AN INSTANT, WITH WHAT IS NOT KNOWN AND WHAT IS CONTESTED (audit item
`l3-bounded-snapshot-incomplete`; Atlas v2 `GeniOS-008/00-ARCHITECTURE.md:107`, `02-MIGRATION-PLAN.md` L3-3: "seeds,
hops, max nodes, unknowns and contradictions; bitemporal as-of"). Three things were missing:

  * THE INSTANT. 5985b6e1 gave the walk `ReadRequest.as_of` and no caller passed it, so the snapshot read the live
    graph whatever instant the pass judged at. `as_of` is now a REQUIRED keyword — a default is how it went unused
    — and the L2 pass hands it its own `now`. An edge we had not learned by then is not in the view.
  * THE UNKNOWNS. The typed absences L3 recorded on the view's nodes (`situation_absences`,
    `context/quality/missing`): UNKNOWABLE (no source could carry it), GENUINELY_ABSENT (a source could and none
    did — the only one that licenses "there is none"), STALE. A GENUINELY_ABSENT drawn under a coverage epoch that
    has since moved licenses nothing (`epoch.stale_coverage`, the rule `read_absences` marks by).
  * THE CONTRADICTIONS. L3's open `discrepancies` on the view's nodes (a held fact and a challenger, nobody has
    settled it; a snoozed one is unsettled too) and L1's unresolved `signal_conflicts` on the events that wrote the
    view's facts — both sides kept, no winner.

⛔ THESE LEDGERS ARE NOT VERSIONED. A contradiction is cut at the instant it was DETECTED (`created_at`,
`detected_at`), as an edge is at the instant we learned it, and its words are its current ones. The absences are
the CURRENT classification — the table holds no other (`refresh_typed_absences` replaces it) — so a past instant
reads today's unknowns, never a guess at older ones.

⛔ NO PRIVATE FACT DECIDES WHAT IT SHOWS — the seed read's rule (`visibility_scope <> 'private'`), kept by the two
fact-backed reads: a discrepancy whose HELD fact is private is not printed, and an L1 conflict counts only through a
fact the org may see. (`ReadRequest.visibility` was the walk's own spelling of this and nothing ever read it:
`graph_edges` has no visibility column. It is deleted, not left to read as a rule that holds.)
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.context.bounded_read import ReadRequest, read_bounded
from genios_engine.context.quality.epoch import current_epochs
from genios_engine.context.quality.epoch import stale_coverage

from .inputs import CONFLICT_QUOTE_CHARS
from .inputs import _claim_quote  # the quote L1's own conflict reader takes, never a second spelling

#: Smaller than `bounded_read.DEFAULT_MAX_NODES`: this view is printed whole into a prompt beside the
#: file's own dossier, and every node is a line the model reads.
MAX_NODES = 40
MAX_SEEDS = 5
#: GeniOS-011 S16.U3 · each is a printed line too. A list that reaches its cap names itself in `Snapshot.capped`, so
#: "the first twenty" never reads as "all of them".
MAX_UNKNOWNS = 20
MAX_CONTRADICTIONS = 10

_SEEDS_OF_EVENTS = text(
    "select distinct subject_node_id from graph_facts "
    " where org_id = :o and created_by_event_id = any(:events) and valid_to is null "
    "   and visibility_scope <> 'private' "
    " order by subject_node_id limit :n")

_NODES = text(
    "select distinct on (node_id) node_id, node_type, display_name "
    "  from graph_nodes where org_id = :o and node_id = any(:ids) and valid_to is null "
    " order by node_id, version desc")

#: GeniOS-011 S16.U3 · the typed absences on the view's nodes — one line per (node, fact, type), however many
#: situations expected it.
_ABSENCES = text(
    "select distinct subject_node_id, expected_fact, absence_type, coverage_domain, coverage_epoch "
    "  from situation_absences where org_id = :o and subject_node_id = any(:ids) "
    " order by subject_node_id, expected_fact, absence_type, coverage_domain, coverage_epoch limit :n")

#: GeniOS-011 S16.U3 · L3's unsettled disagreements on the view's nodes, as known at `:t`; never one whose held
#: fact is private.
_DISCREPANCIES = text(
    "select d.id, d.subject_node_id, d.field, d.held, d.challenger from discrepancies d "
    " where d.org_id = :o and d.subject_node_id = any(:ids) and d.status in ('open', 'snoozed') "
    "   and d.created_at <= :t "
    "   and not exists (select 1 from graph_facts f where f.org_id = d.org_id "
    "                    and f.fact_version_id = d.held ->> 'fact_version_id' and f.visibility_scope = 'private') "
    " order by d.subject_node_id, d.field, d.id limit :n")

#: GeniOS-011 S16.U3 · L1's unresolved conflicts (ALG-12 `unresolved_surface_both`) resting on an event that wrote a
#: fact the org may see on one of the view's nodes, as known at `:t`.
_SIGNAL_CONFLICTS = text(
    "select c.conflict_id, c.field, c.claims, c.event_ids from signal_conflicts c "
    " where c.org_id = :o and c.resolution = 'unresolved_surface_both' and c.detected_at <= :t "
    "   and exists (select 1 from graph_facts f where f.org_id = c.org_id and f.subject_node_id = any(:ids) "
    "                and f.visibility_scope <> 'private' and f.created_by_event_id is not null "
    "                and c.event_ids @> jsonb_build_array(f.created_by_event_id)) "
    " order by c.conflict_id limit :n")


@dataclass(frozen=True, slots=True)
class SnapshotNode:
    node_id: str
    node_type: str
    name: str | None


@dataclass(frozen=True, slots=True)
class SnapshotUnknown:
    """A fact L3 expected on a node of the view and does not hold — typed, so "not known" never reads as "none"."""
    node_id: str
    expected_fact: str
    absence_type: str                       # `contracts.quality.AbsenceType`: unknowable | genuinely_absent | stale
    #: GENUINELY_ABSENT under a coverage epoch still standing — the only unknown that licenses "there is none".
    licenses_negative_inference: bool
    #: Drawn under a coverage epoch since superseded: unverified until it is drawn again.
    stale_coverage: bool = False


@dataclass(frozen=True, slots=True)
class SnapshotContradiction:
    """Two sources that disagree about something in the view, both sides kept and neither chosen."""
    kind: str                               # "discrepancy" (L3) | "signal_conflict" (L1)
    ref: str                                # `discrepancies.id` | `signal_conflicts.conflict_id`
    field: str
    sides: tuple[str, ...]                  # the held side first for a discrepancy; one per claim for a conflict
    node_id: str | None = None              # a discrepancy's node; an L1 conflict names events, not a node
    event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Snapshot:
    seeds: tuple[str, ...]
    nodes: tuple[SnapshotNode, ...]
    edges: tuple[tuple[str, str, str], ...]          # (edge_type, from, to)
    revision: int | None
    truncated: bool
    truncated_by: str | None = None
    #: GeniOS-011 S16.U3 · the instant the view was read AT (the pass's `now`).
    as_of: datetime | None = None
    unknowns: tuple[SnapshotUnknown, ...] = ()
    contradictions: tuple[SnapshotContradiction, ...] = ()
    #: Which of the two lists reached its cap ("unknowns", "contradictions"): there may be more.
    capped: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return f"graph@{self.revision if self.revision is not None else 'unknown'}"


EMPTY = Snapshot(seeds=(), nodes=(), edges=(), revision=None, truncated=False)


def seeds_for(conn, org_id: str, *, file_id: str | None, events: Iterable[str]) -> tuple[str, ...]:
    if file_id:
        return (str(file_id),)
    events = sorted(set(events))
    if not events:
        return ()
    rows = conn.execute(_SEEDS_OF_EVENTS, {"o": org_id, "events": events, "n": MAX_SEEDS}).all()
    return tuple(str(r.subject_node_id) for r in rows)


def _loads(value: Any) -> Any:
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _side(value: Any) -> str:
    """One side of a discrepancy, as it was written: its `value`, compact, cut."""
    held = _loads(value)
    v = held.get("value") if isinstance(held, dict) else held
    said = v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
    return " ".join(str(said).split())[:CONFLICT_QUOTE_CHARS]


def _unknowns(conn, org_id: str, ids: list[str]) -> tuple[tuple[SnapshotUnknown, ...], bool]:
    rows = conn.execute(_ABSENCES, {"o": org_id, "ids": ids, "n": MAX_UNKNOWNS + 1}).all()
    if not rows:
        return (), False
    current = {d: e.epoch for d, e in current_epochs(conn, org_id).items()}
    out: dict[tuple[str, str, str], SnapshotUnknown] = {}
    for r in rows[:MAX_UNKNOWNS]:
        stale = stale_coverage(domain=str(r.coverage_domain),
                               drawn_under=None if r.coverage_epoch is None else int(r.coverage_epoch),
                               current=current)
        kind = str(r.absence_type)
        key = (str(r.subject_node_id), str(r.expected_fact), kind)
        held = out.get(key)
        # The same gap concluded in two domains: it licenses only if every conclusion of it still stands.
        stale = stale or (held is not None and held.stale_coverage)
        out[key] = SnapshotUnknown(node_id=key[0], expected_fact=key[1], absence_type=kind,
                                   licenses_negative_inference=kind == "genuinely_absent" and not stale,
                                   stale_coverage=stale)
    return tuple(out.values()), len(rows) > MAX_UNKNOWNS


def _contradictions(conn, org_id: str, ids: list[str],
                    as_of: datetime) -> tuple[tuple[SnapshotContradiction, ...], bool]:
    params = {"o": org_id, "ids": ids, "t": as_of, "n": MAX_CONTRADICTIONS + 1}
    out = [SnapshotContradiction(kind="discrepancy", ref=str(r.id), field=str(r.field),
                                 sides=(_side(r.held), _side(r.challenger)), node_id=str(r.subject_node_id))
           for r in conn.execute(_DISCREPANCIES, params).all()]
    for r in conn.execute(_SIGNAL_CONFLICTS, params).all():
        claims = _loads(r.claims) or []
        out.append(SnapshotContradiction(
            kind="signal_conflict", ref=str(r.conflict_id), field=str(r.field),
            sides=tuple(q for q in (_claim_quote(c) for c in claims) if q),
            event_ids=tuple(str(e) for e in (_loads(r.event_ids) or ()))))
    return tuple(out[:MAX_CONTRADICTIONS]), len(out) > MAX_CONTRADICTIONS


def read_snapshot(conn, org_id: str, seeds: Sequence[str], *, as_of: datetime,
                  max_nodes: int = MAX_NODES) -> Snapshot:
    """The bounded view around `seeds` AS OF `as_of`: names, revision, whether it finished, and the view's typed
    absences and open contradictions."""
    seeds = tuple(dict.fromkeys(str(s) for s in seeds if s))
    if not seeds:
        return replace(EMPTY, as_of=as_of)
    view = read_bounded(conn, org_id, ReadRequest(seeds=seeds, max_nodes=max(max_nodes, len(seeds)), as_of=as_of))
    rows = conn.execute(_NODES, {"o": org_id, "ids": list(view.node_ids)}).all()
    named = {str(r.node_id): SnapshotNode(str(r.node_id), str(r.node_type), r.display_name) for r in rows}
    nodes = tuple(named[n] for n in view.node_ids if n in named)
    kept = {n.node_id for n in nodes}
    edges = []
    for e in view.edges:
        m = e if isinstance(e, dict) else getattr(e, "_mapping", {})
        a, b = str(m.get("from_node_id")), str(m.get("to_node_id"))
        if a in kept and b in kept:
            edges.append((str(m.get("edge_type")), a, b))
    ids = [n.node_id for n in nodes]
    unknowns, more_unknowns = _unknowns(conn, org_id, ids) if ids else ((), False)
    contradictions, more_contradictions = _contradictions(conn, org_id, ids, as_of) if ids else ((), False)
    capped = tuple(name for name, hit in (("unknowns", more_unknowns), ("contradictions", more_contradictions))
                   if hit)
    return Snapshot(seeds=seeds, nodes=nodes, edges=tuple(sorted(set(edges))), revision=view.revision,
                    truncated=view.truncated, truncated_by=view.truncated_by, as_of=as_of, unknowns=unknowns,
                    contradictions=contradictions, capped=capped)


__all__ = ["EMPTY", "MAX_CONTRADICTIONS", "MAX_NODES", "MAX_SEEDS", "MAX_UNKNOWNS", "Snapshot", "SnapshotContradiction",
           "SnapshotNode", "SnapshotUnknown", "read_snapshot", "seeds_for"]
