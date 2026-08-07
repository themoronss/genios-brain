"""L2 · Node merge — executing a human's decision that two nodes are one entity.

Nothing here runs automatically. `context.identity` PROPOSES; a person decides; this
module carries out the decision and records enough to undo it.

WHY IT IS REVERSIBLE
A merge is the most destructive edit in the graph: it rewrites who every fact, edge and
observation is about. If the decision was wrong, "just merge them back" is not a repair —
the original ownership is gone. So every merge snapshots what it moved, and
`reverse_merge` puts it back.

THE TWO INVARIANTS MERGING CAN BREAK
Repointing rows at a survivor can violate rules the graph is built on, and Postgres will
not catch either one:

  1. ONE ACTIVE FACT PER (subject, field). Merge two companies that each hold
     `deal.stage` and the survivor now holds two active values for one field. Every
     reader takes `limit 1` — so which value is "true" becomes whichever row the planner
     returns first. Resolved here by the same rule the graph uses everywhere: higher
     authority wins, then more recent. The loser is kept as `superseded`, not deleted.

  2. NO SELF-EDGES. If the two nodes were linked to each other — and duplicates usually
     are — repointing turns that edge into A→A ("Acme corresponded_with Acme"). Closed,
     not carried over.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id

# Every table that names a node. Missing one leaves rows pointing at a closed node —
# invisible in the UI, still returned by any query that joins on node_id.
_NODE_REFERENCES: tuple[tuple[str, str], ...] = (
    ("graph_facts", "subject_node_id"),
    ("graph_observations", "subject_node_id"),
    ("graph_aliases", "node_id"),
    ("source_identity_map", "node_id"),
    ("context_attention", "node_id"),
    ("merge_proposals", "left_node_id"),
    ("merge_proposals", "right_node_id"),
    # Safe in the generic loop: uniqueness here is on (org, correlation_id), not on the
    # anchor, so two situations pointing at the survivor cannot collide. By the time this
    # runs, _merge_correlations has already removed the situations whose correlation was
    # folded — only genuinely repointed ones are left.
    ("context_situations", "anchor_node_id"),
)
# context_correlations.anchor_node_id is DELIBERATELY absent: a blind update there trips
# `unique (org, anchor, domain, generation)`. _merge_correlations handles it by folding
# the two groups together instead. Adding it here would abort the whole merge.
_CORRELATION_HANDLED_SEPARATELY = ("context_correlations", "anchor_node_id")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot(conn, org_id: str, node_id: str) -> dict:
    """Everything needed to put this node back exactly as it was."""
    node = conn.execute(text(
        "select node_id, node_type, canonical_key, display_name, identity_strength "
        "from graph_nodes where org_id=:o and node_id=:n and valid_to is null limit 1"),
        {"o": org_id, "n": node_id}).mappings().first()
    # The exact rows this node owned, by primary key, so an unmerge can move back
    # precisely what was moved — not "everything that now points at the survivor",
    # which would also drag across rows the survivor had all along.
    owned: dict[str, list] = {}
    for table, id_column, owner_column in (
            ("graph_facts", "fact_version_id", "subject_node_id"),
            ("graph_observations", "observation_id", "subject_node_id"),
            ("graph_aliases", "alias_type || ':' || alias_key", "node_id")):
        owned[table] = [r[0] for r in conn.execute(text(
            f"select {id_column} from {table} where org_id=:o and {owner_column}=:n"),
            {"o": org_id, "n": node_id}).fetchall()]
    edges = [dict(r) for r in conn.execute(text(
        "select edge_version_id, edge_type, from_node_id, to_node_id from graph_edges "
        "where org_id=:o and (from_node_id=:n or to_node_id=:n) and valid_to is null"),
        {"o": org_id, "n": node_id}).mappings().all()]
    return {"node": dict(node) if node else None, "owned": owned, "edges": edges}


def _merge_correlations(conn, org_id: str, survivor_id: str, merged_id: str) -> dict:
    """Fold the merged node's situations into the survivor's. Must run BEFORE the generic
    repoint loop, and correlations must stay out of it.

    A plain `update anchor_node_id` would violate `unique (org, anchor, domain,
    generation)` the moment both nodes have a situation in the same domain and generation
    — which is precisely the case when the two nodes were the same customer all along.
    Postgres would abort the whole merge with a constraint error.

    So: where the survivor already has the counterpart situation, the members move across
    and the emptied group is closed. Where it does not, the group simply changes owner.
    """
    moved_members = 0
    folded = 0
    repointed = 0
    for corr in conn.execute(text(
            "select correlation_id, domain, generation, first_event_at, last_event_at "
            "from context_correlations where org_id=:o and anchor_node_id=:m"),
            {"o": org_id, "m": merged_id}).all():
        twin = conn.execute(text(
            "select correlation_id from context_correlations where org_id=:o "
            "and anchor_node_id=:s and domain=:d and generation=:g"),
            {"o": org_id, "s": survivor_id, "d": corr.domain, "g": corr.generation}).scalar()
        if twin is None:
            conn.execute(text(
                "update context_correlations set anchor_node_id=:s, updated_at=now() "
                "where org_id=:o and correlation_id=:c"),
                {"s": survivor_id, "o": org_id, "c": corr.correlation_id})
            repointed += 1
            continue
        moved_members += conn.execute(text(
            "update context_correlation_members set correlation_id=:twin "
            "where org_id=:o and correlation_id=:c and event_id not in ("
            "  select event_id from context_correlation_members "
            "  where org_id=:o and correlation_id=:twin)"),
            {"twin": twin, "o": org_id, "c": corr.correlation_id}).rowcount
        # Whatever is left was already evidence for the twin — the same event reached both
        # nodes before we knew they were one. Drop the duplicate membership rows.
        conn.execute(text(
            "delete from context_correlation_members where org_id=:o and correlation_id=:c"),
            {"o": org_id, "c": corr.correlation_id})
        # Recount from actual membership rather than adding the two totals: overlapping
        # evidence was just de-duplicated, so a sum would overstate what we know.
        # The surviving group now covers both spans. `least`/`greatest` ignore nulls, so
        # a group that never had a dated event does not blank out the other's span.
        conn.execute(text(
            "update context_correlations c set "
            "  event_count = (select count(*) from context_correlation_members m "
            "                 where m.org_id = c.org_id "
            "                   and m.correlation_id = c.correlation_id), "
            "  first_event_at = least(c.first_event_at, :cf), "
            "  last_event_at  = greatest(c.last_event_at, :cl), "
            "  updated_at = now() "
            "where c.org_id = :o and c.correlation_id = :twin"),
            {"o": org_id, "twin": twin,
             "cf": corr.first_event_at, "cl": corr.last_event_at})
        # The folded group's SITUATION goes with it — situations are 1:1 with
        # correlations, and leaving an orphan would put a situation about nothing in the
        # active list. Everything about a situation is derived and rebuilt on the next
        # refresh EXCEPT one thing: a human marking it resolved. That decision carries
        # over when the surviving situation has not been decided, so confirming two
        # customers are one does not quietly reopen work somebody already closed.
        conn.execute(text(
            "update context_situations t set status = s.status, "
            "  resolved_by = s.resolved_by, resolved_at = s.resolved_at, "
            "  resolution_note = s.resolution_note "
            "from context_situations s "
            "where t.org_id = :o and t.correlation_id = :twin "
            "  and s.org_id = :o and s.correlation_id = :src "
            "  and s.resolved_by = 'human' and t.resolved_by is distinct from 'human'"),
            {"o": org_id, "twin": twin, "src": corr.correlation_id})
        conn.execute(text(
            "delete from context_situations where org_id=:o and correlation_id=:c"),
            {"o": org_id, "c": corr.correlation_id})
        conn.execute(text(
            "delete from context_correlations where org_id=:o and correlation_id=:c"),
            {"o": org_id, "c": corr.correlation_id})
        folded += 1
    return {"correlations_repointed": repointed, "correlations_folded": folded,
            "correlation_members_moved": moved_members}


def _resolve_duplicate_facts(conn, org_id: str, survivor_id: str) -> int:
    """Invariant 1. After repointing, one (subject, field) can hold several active facts.

    Keep the winner by the graph's own precedence — authority_rank, then occurred_at,
    then insertion order — and mark the rest `superseded`. Superseded rows keep their
    provenance and stay queryable; nothing is deleted, so an unmerge can restore them.
    """
    rows = conn.execute(text(
        "select fact_version_id from ("
        "  select fact_version_id, row_number() over ("
        "    partition by field"
        "    order by authority_rank desc, occurred_at desc nulls last, created_at desc"
        "  ) as rank_in_field"
        "  from graph_facts"
        "  where org_id=:o and subject_node_id=:s and valid_to is null and status='active'"
        ") ranked where rank_in_field > 1"), {"o": org_id, "s": survivor_id}).fetchall()
    if not rows:
        return []
    losers = [r.fact_version_id for r in rows]
    conn.execute(text(
        "update graph_facts set status='superseded', valid_to=now() "
        "where org_id=:o and fact_version_id = any(:ids)"), {"o": org_id, "ids": losers})
    # The IDS, not a count. A count records that something was changed; only the ids let
    # it be changed back, and "reversible" is a promise the snapshot has to keep.
    return losers


def _close_self_edges(conn, org_id: str, survivor_id: str) -> list[str]:
    """Invariant 2. Duplicates are usually linked to each other, and repointing turns
    that link into 'Acme corresponded_with Acme'. Returns the edges closed, so an unmerge
    can reopen exactly those and not the ones that were already closed."""
    rows = conn.execute(text(
        "update graph_edges set valid_to=now() where org_id=:o and valid_to is null "
        "and from_node_id=:s and to_node_id=:s returning edge_version_id"),
        {"o": org_id, "s": survivor_id}).fetchall()
    return [r.edge_version_id for r in rows]


def _dedupe_edges(conn, org_id: str, survivor_id: str) -> int:
    """Both nodes knew the same person → two identical edges after repointing. Keep the
    one seen most recently and fold the interaction count into it, so merging does not
    quietly halve how well we appear to know someone."""
    rows = conn.execute(text(
        "select edge_type, from_node_id, to_node_id, "
        "       array_agg(edge_version_id order by last_seen_at desc nulls last) as versions, "
        "       sum(interaction_count) as total "
        "from graph_edges where org_id=:o and valid_to is null "
        "  and (from_node_id=:s or to_node_id=:s) "
        "group by edge_type, from_node_id, to_node_id having count(*) > 1"),
        {"o": org_id, "s": survivor_id}).fetchall()
    closed: list[str] = []
    for row in rows:
        keep, *drop = row.versions
        conn.execute(text(
            "update graph_edges set interaction_count=:c where org_id=:o "
            "and edge_version_id=:v"), {"c": int(row.total), "o": org_id, "v": keep})
        conn.execute(text(
            "update graph_edges set valid_to=now() where org_id=:o "
            "and edge_version_id = any(:ids)"), {"o": org_id, "ids": drop})
        closed.extend(drop)
    return closed


def apply_merge(conn, *, org_id: str, survivor_node_id: str, merged_node_id: str,
                reason: str, proposal_id: str | None = None) -> dict:
    """Fold `merged` into `survivor`. Caller supplies the transaction.

    The survivor is the node that keeps its id, its canonical_key and its history. Pick
    the one with the stronger anchor — everything downstream (read models, delivery
    cards, reasoning traces) already refers to it by id.
    """
    if survivor_node_id == merged_node_id:
        raise ValueError("cannot merge a node into itself")
    snapshots = {"survivor": _snapshot(conn, org_id, survivor_node_id),
                 "merged": _snapshot(conn, org_id, merged_node_id)}
    if snapshots["merged"]["node"] is None:
        raise ValueError(f"node {merged_node_id} is not an open node in this org")
    if snapshots["survivor"]["node"] is None:
        raise ValueError(f"node {survivor_node_id} is not an open node in this org")

    # Situations FIRST and separately: a blind repoint of anchor_node_id trips the
    # unique index the moment both nodes hold a situation in the same domain, which is
    # exactly what happens when the two nodes really were one customer.
    correlation_result = _merge_correlations(conn, org_id, survivor_node_id, merged_node_id)

    moved: dict[str, int] = {}
    for table, column in _NODE_REFERENCES:
        moved[f"{table}.{column}"] = conn.execute(text(
            f"update {table} set {column}=:surv where org_id=:o and {column}=:merged"),
            {"surv": survivor_node_id, "o": org_id, "merged": merged_node_id}).rowcount
    for column in ("from_node_id", "to_node_id"):
        moved[f"graph_edges.{column}"] = conn.execute(text(
            f"update graph_edges set {column}=:surv where org_id=:o and {column}=:merged"),
            {"surv": survivor_node_id, "o": org_id, "merged": merged_node_id}).rowcount

    # Repairs record WHICH rows they touched. A count proves something happened; only
    # the ids let it be undone, and reverse_merge has to reopen exactly these edges — not
    # every closed edge, which would resurrect ones closed for unrelated reasons.
    repairs = {
        "self_edges_closed": _close_self_edges(conn, org_id, survivor_node_id),
        "duplicate_edges_closed": _dedupe_edges(conn, org_id, survivor_node_id),
        "facts_superseded": _resolve_duplicate_facts(conn, org_id, survivor_node_id),
        **correlation_result,
    }

    # The merged node is CLOSED, never deleted: its id may already appear in a delivery
    # card, a reasoning trace or an audit row, and those must still resolve.
    conn.execute(text(
        "update graph_nodes set valid_to=now() where org_id=:o and node_id=:n "
        "and valid_to is null"), {"o": org_id, "n": merged_node_id})

    history_id = new_id("mh")
    conn.execute(text(
        "insert into merge_history (id, org_id, survivor_node_id, merged_node_id, "
        "snapshots, reason) values (:id, :o, :s, :m, cast(:snap as jsonb), :why)"),
        {"id": history_id, "o": org_id, "s": survivor_node_id, "m": merged_node_id,
         "snap": json.dumps({"snapshots": snapshots, "moved": moved, "repairs": repairs},
                            default=str),
         "why": reason})
    if proposal_id:
        conn.execute(text(
            "update merge_proposals set status='merged' where org_id=:o and id=:id"),
            {"o": org_id, "id": proposal_id})
    # Any other OPEN proposal naming the merged node now names the survivor on both
    # sides (it was repointed above) — a proposal to merge a node with itself. Close it.
    conn.execute(text(
        "update merge_proposals set status='merged' where org_id=:o and status='open' "
        "and left_node_id = right_node_id"), {"o": org_id})

    return {"merge_id": history_id, "survivor": survivor_node_id,
            "merged": merged_node_id, "moved": moved, "repairs": repairs}


def reverse_merge(conn, *, org_id: str, merge_id: str) -> dict:
    """Undo a merge, using the snapshot taken when it was applied.

    WHAT IS RESTORED: the graph itself. The merged node reopens, and every fact,
    observation, alias and edge that belonged to it goes back — identified by the exact
    row ids recorded at merge time, so rows that merely LOOK similar are left alone.
    Facts superseded by the merge become active again; edges it closed reopen.

    WHAT IS REBUILT INSTEAD: correlations and situations. Those are derived views, and
    the merge folded some of their rows away entirely. Restoring deleted derivations from
    a snapshot would be guessing at state that is cheaper and more correct to recompute —
    so this marks the merge reversed and the next refresh rebuilds them from the graph it
    just restored. A human resolution carried across during the fold stays where it went;
    that was somebody's decision about a real situation, not an artefact of the merge.
    """
    record = conn.execute(text(
        "select survivor_node_id, merged_node_id, snapshots, reversed "
        "from merge_history where org_id=:o and id=:id"),
        {"o": org_id, "id": merge_id}).first()
    if record is None:
        raise ValueError(f"no merge {merge_id!r} in this org")
    if record.reversed:
        raise ValueError(f"merge {merge_id!r} was already reversed")

    payload = record.snapshots if isinstance(record.snapshots, dict) else json.loads(
        record.snapshots or "{}")
    snapshots = payload.get("snapshots", {})
    repairs = payload.get("repairs", {})
    owned = (snapshots.get("merged") or {}).get("owned") or {}
    merged_id, survivor_id = record.merged_node_id, record.survivor_node_id

    restored: dict[str, int] = {}

    conn.execute(text(
        "update graph_nodes set valid_to=null where org_id=:o and node_id=:n"),
        {"o": org_id, "n": merged_id})

    for ids, table, column, key_column in (
            (owned.get("graph_facts"), "graph_facts", "subject_node_id", "fact_version_id"),
            (owned.get("graph_observations"), "graph_observations", "subject_node_id",
             "observation_id")):
        if ids:
            restored[table] = conn.execute(text(
                f"update {table} set {column}=:m where org_id=:o and {key_column} = any(:ids)"),
                {"m": merged_id, "o": org_id, "ids": list(ids)}).rowcount

    # Aliases were snapshotted as "type:key" pairs — the table has no single-column id.
    alias_keys = owned.get("graph_aliases") or []
    if alias_keys:
        pairs = [k.split(":", 1) for k in alias_keys if ":" in k]
        restored["graph_aliases"] = sum(
            conn.execute(text(
                "update graph_aliases set node_id=:m where org_id=:o "
                "and alias_type=:t and alias_key=:k"),
                {"m": merged_id, "o": org_id, "t": t, "k": k}).rowcount
            for t, k in pairs)

    for edge in (snapshots.get("merged") or {}).get("edges") or []:
        conn.execute(text(
            "update graph_edges set from_node_id=:f, to_node_id=:t where org_id=:o "
            "and edge_version_id=:v"),
            {"f": edge["from_node_id"], "t": edge["to_node_id"], "o": org_id,
             "v": edge["edge_version_id"]})

    reopen = list(repairs.get("self_edges_closed") or []) + list(
        repairs.get("duplicate_edges_closed") or [])
    if reopen:
        restored["graph_edges_reopened"] = conn.execute(text(
            "update graph_edges set valid_to=null where org_id=:o "
            "and edge_version_id = any(:ids)"), {"o": org_id, "ids": reopen}).rowcount

    superseded = list(repairs.get("facts_superseded") or [])
    if superseded:
        restored["graph_facts_reactivated"] = conn.execute(text(
            "update graph_facts set status='active', valid_to=null where org_id=:o "
            "and fact_version_id = any(:ids)"), {"o": org_id, "ids": superseded}).rowcount

    # Derived views are dropped, not restored — the next refresh rebuilds them correctly
    # from the graph as it now stands.
    conn.execute(text(
        "delete from context_situations where org_id=:o and anchor_node_id in (:s, :m)"),
        {"o": org_id, "s": survivor_id, "m": merged_id})
    conn.execute(text(
        "delete from context_correlation_members where org_id=:o and correlation_id in ("
        "  select correlation_id from context_correlations "
        "  where org_id=:o and anchor_node_id in (:s, :m))"),
        {"o": org_id, "s": survivor_id, "m": merged_id})
    conn.execute(text(
        "delete from context_correlations where org_id=:o and anchor_node_id in (:s, :m)"),
        {"o": org_id, "s": survivor_id, "m": merged_id})

    conn.execute(text(
        "update merge_history set reversed=true where org_id=:o and id=:id"),
        {"o": org_id, "id": merge_id})
    # The pair becomes an open question again rather than a settled one: reversing says
    # the merge was wrong, not that the two nodes were never worth comparing.
    left, right = sorted((survivor_id, merged_id))
    conn.execute(text(
        "update merge_proposals set status='rejected' where org_id=:o "
        "and left_node_id=:l and right_node_id=:r and status='merged'"),
        {"o": org_id, "l": left, "r": right})

    return {"merge_id": merge_id, "restored": restored, "survivor": survivor_id,
            "reopened_node": merged_id,
            "note": "correlations and situations are rebuilt on the next L2 refresh"}


def reject_merge(conn, *, org_id: str, proposal_id: str) -> bool:
    """A human says these are two different things. Recorded so the same pair is never
    proposed again — without this, the next email about either one re-raises it."""
    return conn.execute(text(
        "update merge_proposals set status='rejected' where org_id=:o and id=:id "
        "and status='open'"), {"o": org_id, "id": proposal_id}).rowcount > 0


def open_proposals(conn, *, org_id: str, limit: int = 50) -> list[dict]:
    """The review queue, with enough context to decide without opening the graph."""
    rows = conn.execute(text(
        "select p.id, p.left_node_id, p.right_node_id, p.node_type, p.reason, "
        "       p.evidence, p.created_at, "
        "       l.display_name as left_name, l.canonical_key as left_key, "
        "       r.display_name as right_name, r.canonical_key as right_key "
        "from merge_proposals p "
        "left join graph_nodes l on l.org_id=p.org_id and l.node_id=p.left_node_id "
        "     and l.valid_to is null "
        "left join graph_nodes r on r.org_id=p.org_id and r.node_id=p.right_node_id "
        "     and r.valid_to is null "
        "where p.org_id=:o and p.status='open' "
        "order by p.created_at desc limit :lim"), {"o": org_id, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]
