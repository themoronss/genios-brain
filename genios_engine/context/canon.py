"""L2 · Canon — making company knowledge a participant instead of a passenger.

THE BUG THIS CLOSES

Layer 1 built the door for company knowledge: you write a refund policy or upload a
project brief, and it lands at authority rank 4, above any connected system. Then Layer 2
did almost nothing with it. Trace one policy through `process_event` as it stood:

    the author is an internal seat
      → sender_node becomes the AUTHOR's person node
      → every extracted fact attaches to the author
      → internal nodes are excluded from correlation anchors
      → the policy reaches no situation at all

So your refund policy became facts about *you*. The most authoritative material in the
system was also the least connected — filed under whoever happened to type it.

WHAT CHANGES

A canon document becomes a NODE of its own: `internal:<kind>:<key>`, named by its title.
Facts extracted from its body attach to that node, so "refunds within 30 days" is a fact
about the Refund Policy, not about a colleague.

TWO CLASSES, AND WHY THE LINE IS THERE

  ANCHORING (project)   — work in flight. Other signals legitimately group under it: a
                          Slack thread, a commit and a meeting about Project Phoenix are
                          one situation.
  REFERENCE (the rest)  — standing knowledge. A refund policy is true continuously; it is
                          not something happening. Nothing "groups under" it.

Letting every policy and price list open its own situation would bury the handful that
need attention under a filing cabinet. The line is not about importance — pricing may
matter more than any single project — it is about whether other events cluster around it.

HOW A MENTION FINDS IT, AND WHY IT IS BY NAME

The extraction prompt (`context/extract/prompt.py`) never asks for a "project" entity
type, and `_NODE_TYPES` in the pipeline does not include one. So a project mentioned in
prose arrives with no usable type — resolving canon by entity TYPE cannot work, and any
design that assumed it would have failed silently.

Resolution is therefore by NAME, through the same exact-match alias table Step 1 built.
Canon titles use their own alias type, which is what keeps a project called "Acme" from
colliding with the customer called "Acme": different namespaces, no false merge, and a
company mention still resolves to the company first.
"""
from __future__ import annotations

from sqlalchemy import text

from genios_engine.capture.internal_knowledge import is_anchoring, normalize_kind
from genios_engine.context.identity import ALIAS_CANON, record_alias, resolve_alias
from genios_engine.platform.identity import company_slug

# Canon node types that may anchor a situation, as node_type strings. Derived from the
# Layer 1 vocabulary rather than restated, so the two can never disagree about what a
# project is.
def anchoring_node_types() -> frozenset[str]:
    from genios_engine.capture.internal_knowledge import ANCHORING_KINDS
    return frozenset(ANCHORING_KINDS)


def canon_key(kind: str, knowledge_key: str) -> str:
    """The canonical key for a canon node.

    Shaped like the structured lane's `<source>:<object id>` so it reads the same as a
    CRM deal or a calendar event — canon is a system of record, and the company is the
    system.
    """
    return f"internal:{kind}:{knowledge_key}"


def canon_title_key(title: str | None) -> str | None:
    """A canon title reduced to a comparison key.

    Reuses `company_slug` deliberately: it already strips punctuation, case and
    decoration, and one normalisation rule for names is easier to reason about than two
    that drift. A canon title is not a company name, but it is normalised the same way.
    """
    return company_slug(title)


def register_canon_node(conn, store, *, org_id: str, kind: str, title: str,
                        knowledge_key: str, event_id: str | None) -> str:
    """Find or create the node for one canon document, and make it findable by name.

    The title is claimed as an alias so a later mention in an email or Slack message
    resolves here. A collision — two projects with the same title — raises a merge
    proposal exactly as any other duplicate does, because two projects genuinely called
    "Migration" is the same problem as two customers genuinely called "Acme": a human
    knows, and the system must not guess.
    """
    canonical = normalize_kind(kind) or "wiki"
    node_id = store.find_or_create_node(
        conn, org_id=org_id, node_type=canonical,
        canonical_key=canon_key(canonical, knowledge_key),
        display_name=title or knowledge_key, event_id=event_id)
    title_key = canon_title_key(title)
    if title_key:
        record_alias(conn, org_id=org_id, node_id=node_id, alias_type=ALIAS_CANON,
                     alias_key=title_key, origin="anchor", event_id=event_id)
    return node_id


def resolve_canon_mention(conn, *, org_id: str,
                          name: str | None) -> tuple[str, str] | None:
    """A name in prose → (node id, node type) for an existing canon node, or None.

    The TYPE comes back with the id deliberately. Correlation anchors on node type, so a
    caller that had only the id would have to invent one — and an invented type matches
    nothing in ANCHOR_PRIORITY, which means the mention resolves correctly and then
    anchors nothing. The feature would look built and do nothing, which is the failure
    mode this whole module exists to end.

    None is the ordinary answer and stays the ordinary answer: nothing is created here.
    A name nobody has declared as company knowledge is just a name, and inventing a
    project because someone wrote a capitalised word would fill the graph with work that
    does not exist.
    """
    key = canon_title_key(name)
    if not key:
        return None
    node_id = resolve_alias(conn, org_id=org_id, alias_type=ALIAS_CANON, alias_key=key)
    if not node_id:
        return None
    node_type = conn.execute(text(
        "select node_type from graph_nodes where org_id = :o and node_id = :n "
        "and valid_to is null limit 1"), {"o": org_id, "n": node_id}).scalar()
    return (node_id, node_type) if node_type else None


def anchors_situations(kind: str | None) -> bool:
    """Whether a canon document of this kind should anchor situations."""
    return is_anchoring(kind)
