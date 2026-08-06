"""L2 · Entity Resolution — the same real thing, arriving under many names.

WHAT THIS IS FOR
An enterprise names one company five ways in a week: acme.io in an email address,
"Acme" in Slack, "Acme, Inc." in a contract, "ACME" in a CRM export, "Acme Technologies
Pvt Ltd" on an invoice. Until this module, only the first became a node and the other
four became text on somebody's sender record. Every rule that asked "what is happening
with Acme?" saw a fraction of the truth.

THE LAW IT OBEYS (platform.identity, D8)
    Exact key equality is the ONLY auto-merge.
    Name similarity is a candidate finder, never a merge authority.

So this module resolves by LOOKUP, not by scoring. An alias is a key an entity can be
found by — recorded once, then matched exactly. Fuzziness lives in how aliases are
DERIVED (stripping "Inc.", lowercasing, taking a domain's label), never in how they are
compared. Comparison is string equality, forever.

Two colleagues genuinely share a name. Two companies genuinely share a slug. So when a
second node claims an alias that already belongs to another node, this module writes a
merge PROPOSAL and changes nothing. A human decides. That is the difference between a
graph that quietly fuses your two biggest customers and one that asks.

WHAT IT DELIBERATELY DOES NOT DO
  * No edit distance, no embeddings, no "0.87 similar". Every one of those turns a
    coin-flip into a permanent, invisible join.
  * No auto-merge, ever — not even at "certainty". The reversal path (merge_history)
    exists, but an unnoticed wrong merge is not reversed by anyone.
  * No new nodes from a bare name. The P1 anchor rule stands: a mention resolves to an
    ALREADY-ANCHORED node or it stays an observation. This module widens what counts as
    anchored; it does not lower the bar.
"""
from __future__ import annotations

from sqlalchemy import text

from genios_engine.platform.identity import (company_slug, domain_root, norm_email,
                                             person_name_key)
from genios_engine.platform.ids import new_id

# Alias kinds, strongest first. The order matters for lookup: an email identifies one
# human, a company name identifies a company only as well as the name is unique.
ALIAS_EMAIL = "email"
ALIAS_DOMAIN = "domain"
ALIAS_COMPANY_NAME = "company_name"
ALIAS_PERSON_NAME = "person_name"
# Company knowledge, keyed by its title. Its OWN namespace on purpose: a project called
# "Acme" must not collide with the customer called "Acme". Different alias types cannot
# contend for the same key, so no false merge proposal is ever raised between them, and a
# company mention still resolves to the company.
ALIAS_CANON = "canon"

# Aliases that PROVE identity on their own. A collision on these is a real duplicate and
# still only ever produces a proposal — but a high-signal one worth a human's attention.
_STRONG = frozenset({ALIAS_EMAIL, ALIAS_DOMAIN})


def alias_keys_for_node(*, node_type: str, canonical_key: str | None,
                        display_name: str | None) -> list[tuple[str, str, str]]:
    """The keys a node can legitimately be found by, derived from what anchors it.

    Returns (alias_type, alias_key, origin) triples. `origin='anchor'` means the key is
    a restatement of the node's own identity (acme.io → the label "acme"), not a guess.

    A person's NAME is deliberately absent: "Rohit S." anchors nothing on its own, and
    minting it as a lookup key would make every future Rohit collide with this one.
    Person names are recorded only as observed aliases, next to a real anchor.
    """
    keys: list[tuple[str, str, str]] = []
    if not canonical_key:
        return keys

    if node_type == "person":
        email = norm_email(canonical_key)
        if email:
            keys.append((ALIAS_EMAIL, email, "anchor"))
    elif node_type == "company":
        domain = str(canonical_key).strip().lower()
        keys.append((ALIAS_DOMAIN, domain, "anchor"))
        root = domain_root(domain)
        if root:
            # acme.io → findable as "acme". This is the link that lets a bare mention of
            # "Acme" in an email body reach the company built from its email domain.
            keys.append((ALIAS_COMPANY_NAME, root, "anchor"))
        named = company_slug(display_name)
        if named and named != root:
            keys.append((ALIAS_COMPANY_NAME, named, "anchor"))
    return keys


def record_alias(conn, *, org_id: str, node_id: str, alias_type: str, alias_key: str,
                 origin: str = "anchor", event_id: str | None = None) -> str | None:
    """Claim one lookup key for one node.

    Returns None when the key is now (or already was) this node's. Returns the OTHER
    node's id when the key is already taken — the caller has found a duplicate, and the
    insert did nothing. Nothing is ever overwritten: the first claimant keeps the key,
    so resolution stays stable while a proposal waits for a human.
    """
    if not alias_key:
        return None
    conn.execute(text(
        "insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin, "
        "created_by_event_id) values (:o, :t, :k, :n, :orig, :ev) "
        "on conflict (org_id, alias_type, alias_key) do nothing"),
        {"o": org_id, "t": alias_type, "k": alias_key, "n": node_id, "orig": origin,
         "ev": event_id})
    holder = conn.execute(text(
        "select node_id from graph_aliases where org_id=:o and alias_type=:t "
        "and alias_key=:k"), {"o": org_id, "t": alias_type, "k": alias_key}).scalar()
    return None if holder == node_id else holder


def resolve_alias(conn, *, org_id: str, alias_type: str, alias_key: str) -> str | None:
    """Look up a key. Exact match only — this is the whole matching algorithm."""
    if not alias_key:
        return None
    return conn.execute(text(
        "select node_id from graph_aliases where org_id=:o and alias_type=:t "
        "and alias_key=:k"), {"o": org_id, "t": alias_type, "k": alias_key}).scalar()


def resolve_company_mention(conn, *, org_id: str, name: str | None) -> str | None:
    """A company named in prose → an existing company node, or None.

    None is a real answer and the common one: it means nothing anchored is called that,
    so the mention stays an observation rather than becoming an orphan node. This is the
    P1 anchor rule holding, not a failure.
    """
    return resolve_alias(conn, org_id=org_id, alias_type=ALIAS_COMPANY_NAME,
                         alias_key=company_slug(name) or "")


def propose_merge(conn, *, org_id: str, left_node_id: str, right_node_id: str,
                  node_type: str | None, reason: str, evidence: dict) -> str | None:
    """Two nodes look like one thing. Record it; change nothing.

    The pair is ordered before insert so (A,B) and (B,A) are one proposal, and a partial
    unique index keeps one OPEN proposal per pair — otherwise every future email about
    Acme re-proposes the same merge and the queue becomes unreadable.

    Returns the proposal id, or None when this pair is already queued or already decided.
    """
    if not left_node_id or not right_node_id or left_node_id == right_node_id:
        return None
    left, right = sorted((left_node_id, right_node_id))
    settled = conn.execute(text(
        "select 1 from merge_proposals where org_id=:o and left_node_id=:l "
        "and right_node_id=:r and status in ('merged','rejected') limit 1"),
        {"o": org_id, "l": left, "r": right}).first()
    if settled is not None:
        return None          # a human already ruled on this pair; do not ask again
    proposal_id = new_id("mrg")
    row = conn.execute(text(
        "insert into merge_proposals (id, org_id, left_node_id, right_node_id, "
        "node_type, reason, evidence, status) "
        "values (:id, :o, :l, :r, :nt, :why, cast(:ev as jsonb), 'open') "
        "on conflict do nothing returning id"),
        {"id": proposal_id, "o": org_id, "l": left, "r": right, "nt": node_type,
         "why": reason, "ev": _json(evidence)}).first()
    return row.id if row else None


def register_node_identity(conn, *, org_id: str, node_id: str, node_type: str,
                           canonical_key: str | None, display_name: str | None,
                           event_id: str | None = None) -> list[str]:
    """Claim every key a node is entitled to; propose a merge for each one already taken.

    Called on node creation AND on every later sighting, because a node's display name
    often arrives after its anchor did (an email gives you acme.io on Monday and the
    words "Acme Technologies" on Thursday).

    Returns the proposal ids raised. An empty list is the normal case.
    """
    proposals: list[str] = []
    for alias_type, alias_key, origin in alias_keys_for_node(
            node_type=node_type, canonical_key=canonical_key, display_name=display_name):
        holder = record_alias(conn, org_id=org_id, node_id=node_id,
                              alias_type=alias_type, alias_key=alias_key,
                              origin=origin, event_id=event_id)
        if holder is None:
            continue
        strength = "strong" if alias_type in _STRONG else "weak"
        pid = propose_merge(
            conn, org_id=org_id, left_node_id=node_id, right_node_id=holder,
            node_type=node_type, reason=f"shared_{alias_type}",
            evidence={"alias_type": alias_type, "alias_key": alias_key,
                      "strength": strength, "display_name": display_name,
                      "canonical_key": canonical_key, "event_id": event_id})
        if pid:
            proposals.append(pid)
    return proposals


def observe_person_name(conn, *, org_id: str, node_id: str, name: str | None,
                        event_id: str | None = None) -> None:
    """Record what a person is CALLED, next to the email that actually identifies them.

    Written as an observed alias so a later "Rohit S." in prose can reach an anchored
    node. It is never used to create a person and never on its own to propose a merge:
    two people sharing a name is ordinary, not a duplicate.
    """
    key = person_name_key(name)
    if not key:
        return
    conn.execute(text(
        "insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin, "
        "created_by_event_id) values (:o, :t, :k, :n, 'observed', :ev) "
        "on conflict (org_id, alias_type, alias_key) do nothing"),
        {"o": org_id, "t": ALIAS_PERSON_NAME, "k": key, "n": node_id, "ev": event_id})


def _json(value: dict) -> str:
    import json
    return json.dumps(value, default=str)
