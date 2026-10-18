"""GeniOS-008 L2 R2 · the Context Adapter — a BOUNDED, frozen snapshot of what the company knows.

`context/bounded_read.read_bounded` was built for exactly this and had no caller; the old lanes read the
whole tenant (`reason/runner._bulk_load_facts`). This is its first caller. The run's seeds — the file's
anchor, or the nodes the subject's own events wrote — are walked two hops, at most `MAX_NODES` nodes, and
the view comes back with the graph REVISION it saw and whether a cap stopped it. Nothing in the run reads
the graph after this: the prompt is built from the snapshot.

⛔ `truncated` IS PRINTED. A view a cap stopped is "we stopped looking", never "there is nothing more", and
the dossier says so in its coverage block, so the model cannot claim the absence.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import text

from genios_engine.context.bounded_read import ReadRequest, read_bounded

#: Smaller than `bounded_read.DEFAULT_MAX_NODES`: this view is printed whole into a prompt beside the
#: file's own dossier, and every node is a line the model reads.
MAX_NODES = 40
MAX_SEEDS = 5

_SEEDS_OF_EVENTS = text(
    "select distinct subject_node_id from graph_facts "
    " where org_id = :o and created_by_event_id = any(:events) and valid_to is null "
    "   and visibility_scope <> 'private' "
    " order by subject_node_id limit :n")

_NODES = text(
    "select distinct on (node_id) node_id, node_type, display_name "
    "  from graph_nodes where org_id = :o and node_id = any(:ids) and valid_to is null "
    " order by node_id, version desc")


@dataclass(frozen=True, slots=True)
class SnapshotNode:
    node_id: str
    node_type: str
    name: str | None


@dataclass(frozen=True, slots=True)
class Snapshot:
    seeds: tuple[str, ...]
    nodes: tuple[SnapshotNode, ...]
    edges: tuple[tuple[str, str, str], ...]          # (edge_type, from, to)
    revision: int | None
    truncated: bool
    truncated_by: str | None = None

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


def read_snapshot(conn, org_id: str, seeds: Sequence[str], *, max_nodes: int = MAX_NODES) -> Snapshot:
    """The bounded view around `seeds`, with names, its revision and whether it finished."""
    seeds = tuple(dict.fromkeys(str(s) for s in seeds if s))
    if not seeds:
        return EMPTY
    view = read_bounded(conn, org_id, ReadRequest(seeds=seeds, max_nodes=max(max_nodes, len(seeds))))
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
    return Snapshot(seeds=seeds, nodes=nodes, edges=tuple(sorted(set(edges))), revision=view.revision,
                    truncated=view.truncated, truncated_by=view.truncated_by)


__all__ = ["EMPTY", "MAX_NODES", "MAX_SEEDS", "Snapshot", "SnapshotNode", "read_snapshot", "seeds_for"]
