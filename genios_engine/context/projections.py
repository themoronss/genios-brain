"""L2 · Projections — one graph, many lenses.

The spec asks for a Sales graph, a Support graph, an HR graph — and is emphatic that
these must not be separate graphs, only different views of one. That is right, and the
reason is worth stating: separate graphs mean the same customer exists twice, and the
moment they disagree there is no way to say which is correct.

WHAT A PROJECTION IS HERE

    A projection is a DERIVED QUERY, not a stored membership.

There is no `node_projections` table and there will not be one. Membership is computable
from data that already exists — a node belongs to a domain's lens when it takes part in a
situation of that domain — and storing it would create a second source of truth that goes
stale the instant a situation changes domain, is folded by a merge, or opens a new
generation. A stale lens is worse than no lens: it shows a customer in Sales who moved to
Support three weeks ago, and nothing in the system disagrees with it.

DOMAINS ARE DISCOVERED, NEVER DECLARED HERE

`available_projections` reads the domains PRESENT IN THE DATA. Nothing in this module
names a domain, imports a domain list, or branches on one. Add "engineering" upstream and
its lens exists immediately, with no change here — which is the whole requirement: Layer 2
must keep working for domains it has never heard of.

THE CONSTITUTIONAL RULE: A LENS NARROWS RETRIEVAL, NEVER EVALUATION

This is the third time this rule appears in Layer 2 (attention scores, lifecycle states,
now projections), and it is the most dangerous of the three because a projection looks so
reasonable: "the Sales view shouldn't show promotional email".

    Showing less is fine. Evaluating less is not.

If reasoning only ever evaluated the Sales lens, then anything mis-assigned — or in no
lens at all — becomes permanently invisible, and nothing reports it missing. The customer
whose domain was never classified is exactly the one nobody is watching.

Two guarantees make that safe rather than merely intended:

  * `unprojected_nodes` exists and is a first-class query. Whatever falls through every
    lens is findable, on purpose. A projection system without this is a way to lose data.
  * `tests/test_projections.py` fails if anything under reason/ imports this module.

A NOTE ON THE WORD "PROJECTION"
It already means three other things here: an authoritative read-model of an L4 decision
(reason/authority.py), a delivery card's rendered form (deliver/push.py), and a derived
rewritable table generally. This module keeps the name because it is the product's word
and the user-facing route; the prose says "lens" where ambiguity would bite.

BOUNDARY EDGES ARE REPORTED, NOT DROPPED

An entity in the Sales lens is often connected to one that is not. Dropping that edge
makes the lens claim the customer has no other relationships — a lie by omission, and the
worst kind, because the view looks complete. Crossing edges are returned separately and
labelled, so a caller can see the boundary rather than mistake it for the edge of the
world.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from genios_engine.context.domain_spec import is_registered, spec_for

# THE definition of membership. One fragment, used by every question this module answers.
#
# A node reaches a lens two ways: the situation is ABOUT it, or its facts were written by
# an event in that situation's evidence. Both matter — a deal anchors an opportunity, but
# the people on it belong to that lens too.
#
# This is a single constant because the first draft had THREE definitions in 197 lines:
# members counted anchors and participants, while "which lenses is this node in?" and
# "what falls through every lens?" counted anchors only. A participant in the Sales lens
# was therefore also reported as belonging to no lens at all — three answers to one
# question, in the module written to prevent exactly that.
_REACHED = """
select distinct domain, status, node_id from (
    select s.domain, s.status, s.anchor_node_id as node_id
      from context_situations s
     where s.org_id = :o
    union all
    select s.domain, s.status, f.subject_node_id as node_id
      from context_situations s
      join context_correlation_members m
        on m.org_id = s.org_id and m.correlation_id = s.correlation_id
      join graph_facts f
        on f.org_id = m.org_id and f.created_by_event_id = m.event_id
       and f.valid_to is null and f.status = 'active'
     where s.org_id = :o
) reached
where node_id is not null
"""

# Default cap on a lens's membership. A tenant's Sales lens can hold tens of thousands of
# entities, and the route serialises the ids into JSON and feeds them to the boundary-edge
# query as an array — unbounded, that is a slow request that gets slower as the customer
# succeeds.
MEMBER_LIMIT = 500


@dataclass(frozen=True, slots=True)
class Projection:
    """One lens. Deliberately thin — it reports membership, it does not rank or filter."""

    domain: str
    display_name: str
    registered: bool          # is this domain described yet, or only present in data?
    node_ids: tuple[str, ...]
    situation_count: int
    # How many entities the lens actually holds, independent of how many were returned.
    # Without this, "500 members" is indistinguishable from "exactly 500 members" when
    # the truth is 40,000 — a truncation the caller cannot see and would not suspect.
    total_members: int = 0
    truncated: bool = False


def available_projections(conn, *, org_id: str) -> list[dict]:
    """The lenses this tenant actually has, discovered from its data.

    Domains are NOT read from a registry here on purpose. A registry lists what someone
    has described; this lists what exists. A domain arriving in the data before anyone
    describes it must still get a working lens — otherwise Layer 2 blocks Layer 3 from
    ever adding one.
    """
    rows = conn.execute(text(
        "select domain, count(*) as situations, "
        "       count(*) filter (where status = 'active') as active_situations, "
        "       max(last_seen_at) as last_seen_at "
        "from context_situations where org_id = :o "
        "group by domain order by active_situations desc, situations desc"),
        {"o": org_id}).mappings().all()
    return [{"domain": r["domain"],
             "display_name": spec_for(r["domain"]).display_name or r["domain"],
             # False means "present in the data, not described yet" — a normal state
             # while a new domain is being introduced, not an error.
             "registered": is_registered(r["domain"]),
             "situations": int(r["situations"]),
             "active_situations": int(r["active_situations"] or 0),
             "last_seen_at": r["last_seen_at"]}
            for r in rows]


def projection_members(conn, *, org_id: str, domain: str, active_only: bool = True,
                       limit: int = MEMBER_LIMIT) -> Projection:
    """Which entities are visible through one lens.

    `active_only` defaults to True because a lens is a working view. Pass False to
    include dormant and resolved situations — which is what a historical question needs,
    and the reason this is a parameter rather than a hard-coded filter.

    The result is capped and says so. A silently truncated lens is worse than a small
    one: the caller believes it has the whole view.
    """
    status = "and r.status = 'active'" if active_only else ""
    params = {"o": org_id, "d": domain}
    total = conn.execute(text(
        f"select count(*) from ({_REACHED}) r where r.domain = :d {status}"),
        params).scalar() or 0
    node_ids = tuple(row.node_id for row in conn.execute(text(
        f"select distinct r.node_id from ({_REACHED}) r where r.domain = :d {status} "
        "order by r.node_id limit :lim"), {**params, "lim": limit}).fetchall())
    situations = conn.execute(text(
        "select count(*) from context_situations where org_id = :o and domain = :d "
        + ("and status = 'active'" if active_only else "")), params).scalar() or 0
    spec = spec_for(domain)
    return Projection(domain=domain, display_name=spec.display_name or domain,
                      registered=is_registered(domain), node_ids=node_ids,
                      situation_count=int(situations), total_members=int(total),
                      truncated=int(total) > len(node_ids))


def boundary_edges(conn, *, org_id: str, node_ids: tuple[str, ...]) -> list[dict]:
    """Relationships that leave the lens.

    Returned SEPARATELY from internal edges rather than dropped. A lens that silently
    omits these claims the customer has no other relationships — a lie the view has no
    way of admitting to, because it looks complete.
    """
    if not node_ids:
        return []
    rows = conn.execute(text(
        "select e.edge_id, e.edge_type, e.from_node_id, e.to_node_id, "
        "       case when e.from_node_id = any(:ids) then e.to_node_id "
        "            else e.from_node_id end as outside_node_id, "
        "       n.display_name as outside_name, n.node_type as outside_type "
        "from graph_edges e "
        "left join graph_nodes n on n.org_id = e.org_id and n.valid_to is null "
        "  and n.node_id = case when e.from_node_id = any(:ids) then e.to_node_id "
        "                       else e.from_node_id end "
        "where e.org_id = :o and e.valid_to is null "
        "  and (e.from_node_id = any(:ids)) <> (e.to_node_id = any(:ids))"),
        {"o": org_id, "ids": list(node_ids)}).mappings().all()
    return [dict(r) for r in rows]


def unprojected_nodes(conn, *, org_id: str, limit: int = 200) -> dict:
    """Entities that fall through EVERY lens.

    A first-class query, not a diagnostic afterthought. Without it a projection system is
    a way to lose things quietly: an entity nobody classified is invisible in every view
    and absent from every count, and nothing anywhere says so.

    A non-empty result is normal, not a fault. It is also the most useful place to look
    when a domain has just been introduced and classification has not caught up.

    Uses `_REACHED` — the same definition of membership as every other query here — via
    `not in` rather than a correlated `not exists`, so the reachable set is computed once
    instead of once per candidate entity.
    """
    total = conn.execute(text(
        f"select count(*) from graph_nodes n where n.org_id = :o and n.valid_to is null "
        f"and n.node_id not in (select node_id from ({_REACHED}) r)"),
        {"o": org_id}).scalar() or 0
    rows = conn.execute(text(
        f"select n.node_id, n.node_type, n.display_name, n.canonical_key "
        f"from graph_nodes n where n.org_id = :o and n.valid_to is null "
        f"and n.node_id not in (select node_id from ({_REACHED}) r) "
        f"order by n.valid_from desc limit :lim"),
        {"o": org_id, "lim": limit}).mappings().all()
    return {"nodes": [dict(r) for r in rows], "total": int(total),
            "truncated": int(total) > len(rows)}


def node_projections(conn, *, org_id: str, node_id: str) -> list[str]:
    """Every lens one entity appears in.

    A list, never a single value. A customer with a live deal AND an open support ticket
    genuinely belongs to both, and picking one would make the other view lose them —
    silently, since neither view can tell it is incomplete.
    """
    rows = conn.execute(text(
        f"select distinct r.domain from ({_REACHED}) r where r.node_id = :n "
        f"order by r.domain"), {"o": org_id, "n": node_id}).fetchall()
    return [r.domain for r in rows]
