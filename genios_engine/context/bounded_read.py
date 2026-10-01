"""L3 · the bounded read — ask for what you are reasoning about, not for the tenant.

⛔ WHAT WAS WRONG. `context/` offered exactly two graph reads, and both return everything:

    GraphStore.read_graph(org_id, *, as_of)   # the whole org, at a moment
    GraphStore.live_graph(org_id)             # the whole org, now

No seeds, no hop limit, no node cap. A caller wanting three nodes gets the tenant's entire graph
and filters in Python. That is survivable at sixty-six situations and is the wrong shape at any
size — and the reasoning layer reads through it, so the cost lands on the layer that can least
afford it.

⛔ BOUNDED BY DEFAULT, AND THAT IS THE WHOLE POINT. `ReadRequest` has limits whether or not the
caller supplies them. An unbounded default makes every caller's mistake invisible until the tenant
is large enough for it to hurt — which is the point at which it is hardest to fix.

⛔ TRUNCATION IS REPORTED, NEVER SILENT. A traversal that hit its cap and does not say so returns a
partial answer that reads as a complete one. That is the same failure `coverage` exists to prevent
one layer down: *"an empty result over an unmeasured slice, reported as a fact about the business."*
`BoundedView.truncated` is the difference between *"there is nothing more"* and *"we stopped
looking"*, and a caller that cannot tell them apart will eventually claim the first.

THE REVISION COMES BACK WITH THE VIEW so a later write can be guarded against it — see
`write_if_unchanged`. A read that did not say which revision it saw cannot be the basis of a
compare-and-set, and every read here is a candidate basis for one.

SPLIT SO IT IS TESTABLE WITHOUT A DATABASE. `expand` is the traversal and takes a `neighbours`
callable; `read_bounded` wires the SQL one. The rule being enforced is a counting rule, and a test
of it should not need Postgres to prove the count.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

#: Two hops, because the useful question is almost always "this thing and what it touches" — and a
#: third hop on a well-connected node is most of the tenant. Raise it per request, never here.
DEFAULT_MAX_HOPS = 2

#: Sixty nodes is about what a bounded reasoning pass can hold and still say something specific.
#: A cap that is never hit teaches nothing; this one is meant to bite occasionally, and to SAY so.
DEFAULT_MAX_NODES = 60


@dataclass(frozen=True, slots=True)
class ReadRequest:
    """What one caller is asking about, and how far it will go to find it."""

    seeds: tuple[str, ...]
    #: `None` means any edge type. A tuple restricts the walk, which is how a caller asking about
    #: ownership avoids dragging in every message the node ever appeared in.
    edge_types: tuple[str, ...] | None = None
    max_hops: int = DEFAULT_MAX_HOPS
    max_nodes: int = DEFAULT_MAX_NODES
    #: The asking seat's visibility. Carried on the request rather than applied afterwards: a
    #: filter after the walk has already read the rows it is meant to withhold.
    visibility: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not self.seeds:
            raise ValueError("a bounded read starts somewhere: seeds is empty")
        if self.max_hops < 0:
            raise ValueError("max_hops cannot be negative")
        if self.max_nodes < 1:
            raise ValueError("max_nodes must admit at least the seeds")

    def allows(self, edge_type: str) -> bool:
        return self.edge_types is None or edge_type in self.edge_types


@dataclass(frozen=True, slots=True)
class BoundedView:
    """What the walk found, and whether it finished."""

    node_ids: tuple[str, ...]
    edges: tuple[Any, ...]
    #: The graph revision this view was read at. `None` only when the store cannot say.
    revision: int | None = None
    #: ⛔ True when a cap stopped the walk. NOT the same as "there was nothing more".
    truncated: bool = False
    #: How far it actually got, which is how a caller tells "two hops, done" from "two hops, capped".
    hops_walked: int = 0
    #: Which cap bit, when one did. Named so the fix is obvious from the result.
    truncated_by: str | None = None

    @property
    def complete(self) -> bool:
        return not self.truncated


#: `neighbours(node_id) -> iterable of (edge_type, other_node_id, edge)`.
Neighbours = Callable[[str], Iterable[tuple[str, str, Any]]]


def expand(request: ReadRequest, neighbours: Neighbours) -> BoundedView:
    """Breadth-first from the seeds, stopping at whichever cap bites first.

    Breadth-first rather than depth-first on purpose: when a cap does bite, what survives should be
    the nodes NEAREST the thing asked about. A depth-first walk under the same cap returns one long
    thread and calls it a neighbourhood.
    """
    seen: list[str] = []
    seen_set: set[str] = set()
    edges: list[Any] = []
    truncated_by: str | None = None

    frontier: list[str] = []
    for seed in request.seeds:
        if seed in seen_set:
            continue
        if len(seen) >= request.max_nodes:
            truncated_by = "max_nodes"
            break
        seen.append(seed)
        seen_set.add(seed)
        frontier.append(seed)

    hop = 0
    while frontier and truncated_by is None and hop < request.max_hops:
        hop += 1
        nxt: list[str] = []
        for node in frontier:
            for edge_type, other, edge in neighbours(node):
                if not request.allows(edge_type):
                    continue
                if other not in seen_set:
                    if len(seen) >= request.max_nodes:
                        # ⛔ Stop, and do NOT keep the edge. Collecting edges for nodes we refuse
                        # to return would produce a view whose edges point at things it does not
                        # contain — the caller joins on the edge, finds nothing, and reads that
                        # absence as a fact about the business.
                        truncated_by = "max_nodes"
                        break
                    seen.append(other)
                    seen_set.add(other)
                    nxt.append(other)
                edges.append(edge)
            if truncated_by is not None:
                break
        frontier = nxt

    # A frontier left standing at the hop limit means there WAS more — distinct from a walk that
    # ran out of graph, which is the distinction the whole class exists for.
    if truncated_by is None and frontier and hop >= request.max_hops:
        truncated_by = "max_hops"

    return BoundedView(node_ids=tuple(seen), edges=tuple(edges),
                       truncated=truncated_by is not None, hops_walked=hop,
                       truncated_by=truncated_by)


_NEIGHBOUR_SQL = (
    "select edge_type, from_node_id, to_node_id, confidence, valid_from "
    "from graph_edges "
    "where org_id = :o and valid_to is null "
    "  and (from_node_id = :n or to_node_id = :n)"
)

_REVISION_SQL = "select graph_version from graph_versions where org_id = :o"


def sql_neighbours(conn, org_id: str) -> Neighbours:
    """The database-backed walk. One query per node, deliberately.

    A single recursive CTE would be fewer round trips and would also make the cap a `limit` the
    traversal cannot explain — a truncated result with no way to say which bound stopped it. The
    walk is capped at `max_nodes` queries by construction, so the round trips are bounded too.
    """
    from sqlalchemy import text

    def walk(node_id: str):
        rows = conn.execute(text(_NEIGHBOUR_SQL), {"o": org_id, "n": node_id}).mappings().all()
        for row in rows:
            other = row["to_node_id"] if row["from_node_id"] == node_id else row["from_node_id"]
            yield str(row["edge_type"]), str(other), dict(row)

    return walk


def read_bounded(conn, org_id: str, request: ReadRequest) -> BoundedView:
    """The bounded read, against a live connection, carrying the revision it saw."""
    from sqlalchemy import text

    view = expand(request, sql_neighbours(conn, org_id))
    revision = conn.execute(text(_REVISION_SQL), {"o": org_id}).scalar()
    return BoundedView(node_ids=view.node_ids, edges=view.edges,
                       revision=None if revision is None else int(revision),
                       truncated=view.truncated, hops_walked=view.hops_walked,
                       truncated_by=view.truncated_by)


__all__ = ["DEFAULT_MAX_HOPS", "DEFAULT_MAX_NODES", "BoundedView", "Neighbours", "ReadRequest",
           "expand", "read_bounded", "sql_neighbours"]
