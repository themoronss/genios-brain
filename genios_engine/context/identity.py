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
    """Look up a key. Exact match only — this is the whole matching algorithm.

    AMBIGUITY IS NOT A MATCH. When more than one node answers to a key, this returns None rather
    than the first row. Two people called "John" at different companies is ordinary, and handing
    a mention to whichever John was inserted first silently moves every fact, commitment and
    thread state written from that mention onto the wrong person — a merge nobody proposed,
    nobody reviewed, and nothing records.
    """
    if not alias_key:
        return None
    rows = conn.execute(text(
        "select node_id from graph_aliases where org_id=:o and alias_type=:t "
        "and alias_key=:k limit 2"), {"o": org_id, "t": alias_type, "k": alias_key}).fetchall()
    if len(rows) != 1:
        # 0 → nothing is called that, which is the ordinary answer and already handled by callers.
        # 2+ → the key does not identify anyone, and saying so is the only safe reply.
        return None
    return rows[0][0]


def resolve_alias_candidates(conn, *, org_id: str, alias_type: str,
                             alias_key: str) -> tuple[str, ...]:
    """Every node answering to a key — so a caller can SEE an ambiguity rather than infer it.

    `resolve_alias` returning None conflates "nobody" with "several", and a surface asking the
    user to disambiguate needs to tell those apart.
    """
    if not alias_key:
        return ()
    return tuple(r[0] for r in conn.execute(text(
        "select node_id from graph_aliases where org_id=:o and alias_type=:t "
        "and alias_key=:k order by node_id"),
        {"o": org_id, "t": alias_type, "k": alias_key}).fetchall())


def company_name_keys(name: str | None) -> list[str]:
    """The keys a prose company name may be looked up by. Derivation, never comparison.

    `company_slug` joins words with a space ("DevDash Labs" → "devdash labs") while
    `domain_root` cannot contain one ("devdashlabs.com" → "devdashlabs"). The two therefore
    never met, and a company whose name is written as two words was unreachable from the node
    built out of its own email domain. Measured on the design partner's org: 22 company nodes
    carrying live cards, and exactly ONE of them ("Actual AI" → actual.ai, which survives only
    because the dot in the domain becomes the same space) resolved from any of the 77 company
    names the extractor had already pulled out of that org's mail. With the space-insensitive
    key it is six.

    This stays inside the module's law. Fuzziness is allowed in how a key is DERIVED — stripping
    "Inc.", lowercasing, taking a domain's label — and forbidden in how keys are COMPARED.
    Removing the separator is a derivation of exactly that kind; both keys are then matched by
    string equality, and an ambiguous key still resolves to nobody.
    """
    slug = company_slug(name)
    if not slug:
        return []
    squashed = slug.replace(" ", "")
    return [slug] if squashed == slug else [slug, squashed]


def resolve_company_mention(conn, *, org_id: str, name: str | None) -> str | None:
    """A company named in prose → an existing company node, or None.

    None is a real answer and the common one: it means nothing anchored is called that,
    so the mention stays an observation rather than becoming an orphan node. This is the
    P1 anchor rule holding, not a failure.
    """
    for key in company_name_keys(name):
        hit = resolve_alias(conn, org_id=org_id, alias_type=ALIAS_COMPANY_NAME, alias_key=key)
        if hit:
            return hit
    return None


def resolve_person_name(conn, *, org_id: str, name: str | None) -> str | None:
    """A person named in prose (no email) → an existing person node, or None.

    Reads the observed name-alias that `observe_person_name` writes — the read side that was
    missing, leaving those aliases write-only. So a bare-name mention ("Rohit said yes") no longer
    piles onto the message's sender. Exact key match only.

    A name shared by several anchored people resolves to NOBODY, not to the first claimant. Two
    "John"s at different companies is ordinary; picking one moves every fact and commitment
    written from that mention onto the wrong person, and nothing anywhere records that a choice
    was made. An unresolved mention stays an observation, which is recoverable.

    Never creates a node and never merges.
    """
    return resolve_alias(conn, org_id=org_id, alias_type=ALIAS_PERSON_NAME,
                         alias_key=person_name_key(name) or "")


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


def observe_company_name(conn, *, org_id: str, node_id: str, name: str | None,
                         event_id: str | None = None) -> None:
    """Record what a company is CALLED, next to the domain that actually identifies it.

    The company twin of `observe_person_name`, and it exists for the same reason: the anchor and
    the name arrive separately. A company node is anchored on an email domain, so it is born
    called "devdashlabs.com" — which is why 19 of the design partner's 47 live card headlines
    opened on a hostname ("errorcore.dev: no problem documented yet") while the words "DevDash
    Labs" and "Crescere Labs" sat in the same graph as extracted company mentions.

    Written only after the mention ALREADY resolved to this node by exact key equality against
    the node's own anchor, so the association is not a guess. Like its person twin this writes an
    alias and nothing else; the display-name promotion is a node write and lives with the other
    node writes, in the store.
    """
    key = company_slug(name)
    if not key:
        return
    conn.execute(text(
        "insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin, "
        "created_by_event_id) values (:o, :t, :k, :n, 'observed', :ev) "
        "on conflict (org_id, alias_type, alias_key) do nothing"),
        {"o": org_id, "t": ALIAS_COMPANY_NAME, "k": key, "n": node_id, "ev": event_id})


def _json(value: dict) -> str:
    import json
    return json.dumps(value, default=str)
