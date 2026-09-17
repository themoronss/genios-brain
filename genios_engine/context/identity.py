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

from genios_engine.platform.identity import (LINKEDIN_PREFIX, company_slug, domain_root,
                                             norm_email, norm_linkedin_url, person_name_key)
from genios_engine.platform.ids import new_id

# Alias kinds, strongest first. The order matters for lookup: an email identifies one
# human, a company name identifies a company only as well as the name is unique.
ALIAS_EMAIL = "email"
# A LinkedIn profile url identifies one human exactly as an email does (SCREEN_INTEL_P2 §3.2).
# The key is the NORMALISED url (`norm_linkedin_url`), without the `li:` prefix the node's
# canonical key carries — the alias type already names the namespace. `graph_aliases.alias_type`
# has no CHECK (migrations/0036:18), so this needs no migration.
ALIAS_LINKEDIN = "linkedin_url"
ALIAS_DOMAIN = "domain"
ALIAS_COMPANY_NAME = "company_name"
ALIAS_PERSON_NAME = "person_name"
# Company knowledge, keyed by its title. Its OWN namespace on purpose: a project called
# "Acme" must not collide with the customer called "Acme". Different alias types cannot
# contend for the same key, so no false merge proposal is ever raised between them, and a
# company mention still resolves to the company.
ALIAS_CANON = "canon"

#: A KEY TWO LIVE NODES BOTH ANSWER TO, recorded rather than silently awarded to the first.
#:
#: `resolve_alias` already says ambiguity is not a match and returns None when two rows answer
#: to a key. For observed person names that guard could never fire: the table's primary key is
#: (org_id, alias_type, alias_key), so a second "John" never gets a row at all — the insert is
#: `on conflict do nothing`, the first claimant keeps the name for ever, and every fact written
#: from a later mention of that name lands on a person nobody chose. The storage shape made the
#: law unrepresentable.
#:
#: So contention is written onto the row instead of into a second row, and `resolve_alias`
#: refuses a contended key for every alias type. Nothing is deleted: the row still records that
#: the name was seen and who saw it first, and the only thing that changes is that the name
#: stops identifying anybody — which is the correct answer, and a recoverable one.
ALIAS_ORIGIN_CONTENDED = "contended"

# Aliases that PROVE identity on their own. A collision on these is a real duplicate and
# still only ever produces a proposal — but a high-signal one worth a human's attention.
_STRONG = frozenset({ALIAS_EMAIL, ALIAS_DOMAIN, ALIAS_LINKEDIN})


def strong_proposal_reasons() -> frozenset[str]:
    """The `merge_proposals.reason` values raised by an alias that proves identity alone.

    DERIVED FROM `_STRONG`, NOT RESTATED BESIDE IT. `situations.identity_score` prices a strong
    collision differently from a weak one, so it has to know which is which — and a second
    hand-written copy of this set is a copy that silently stops matching the day a strong alias
    kind is added here. `register_node_identity` writes the reason as `shared_<alias_type>` and
    is the only caller of `propose_merge`, so this mapping is total.
    """
    return frozenset(f"shared_{alias_type}" for alias_type in _STRONG)


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
        if str(canonical_key).strip().lower().startswith(LINKEDIN_PREFIX):
            # A person seen only on screen, keyed on their profile: `li:https://…/in/<slug>`.
            profile = norm_linkedin_url(canonical_key)
            if profile:
                keys.append((ALIAS_LINKEDIN, profile, "anchor"))
            return keys
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
    node's id when the key is already taken by a LIVE node — the caller has found a duplicate,
    and the insert did nothing. A live first claimant keeps the key, so resolution stays stable
    while a proposal waits for a human.

    A KEY HELD BY A NODE THAT NO LONGER EXISTS IS UNOWNED, and this is the correction.
    `node_id` is minted per node (`new_id("node")`), the erasure list clears `graph_nodes` and
    leaves `graph_aliases` standing, and this insert was `do nothing` — so a tenant whose graph
    was ever rebuilt kept an alias table pointing at the FIRST graph that ever existed, for
    ever. Measured on the pilot 2026-09-11: **309 of 364 aliases resolved to a node with no row
    at any version** — 107 of 116 emails, 87 of 89 person names, 78 of 107 company names.
    `resolve_company_mention("Antler")` returned a dead id, the caller's type check found no live
    node, and the claim was dropped. That is why `party.role` holds one fact and
    `company.industry` none: not an extractor that cannot read them, a subject that cannot
    resolve.

    Taking over a DEAD key is not overwriting a claimant — there is no claimant. The ambiguity
    guard is untouched and is the whole point of the distinction: two LIVE nodes claiming one
    name is a real collision and still refuses, because picking one silently moves every fact
    written from that mention onto the wrong person.
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
    if holder == node_id or holder is None:
        return None
    # Is the incumbent still a node at all? One indexed lookup, and only on the contended path.
    alive = conn.execute(text(
        "select 1 from graph_nodes where org_id=:o and node_id=:n and valid_to is null limit 1"),
        {"o": org_id, "n": holder}).first()
    if alive is not None:
        return holder                     # a real duplicate: refuse, exactly as before
    conn.execute(text(
        "update graph_aliases set node_id=:n, origin=:orig, created_by_event_id=:ev "
        "where org_id=:o and alias_type=:t and alias_key=:k and node_id=:dead"),
        {"n": node_id, "orig": origin, "ev": event_id, "o": org_id, "t": alias_type,
         "k": alias_key, "dead": holder})
    return None


def prune_dead_aliases(conn, *, org_id: str | None = None, limit: int = 5000) -> int:
    """Delete every alias whose node no longer exists, and report how many.

    WHY A SWEEP AND NOT ONLY THE TAKEOVER. `record_alias` now claims a key whose holder is
    gone, which repairs a name the moment something mentions it again. That is lazy by nature:
    a person or company never written about again keeps a dead key for ever, and until then
    `resolve_alias` answers with an id whose node does not exist — so every caller performs the
    live-node check and drops the claim. Measured on the pilot 2026-09-11, 309 of 364 aliases
    were in that state.

    DELETING IS THE CONSERVATIVE REPAIR, not repointing. A dead key resolves to nothing useful
    already, so removing it loses no answer that was being given; and guessing WHICH live node
    should inherit it would be exactly the silent re-attribution `resolve_person_name` refuses
    ("a name shared by several anchored people resolves to NOBODY, not to the first claimant").
    Removal leaves the key free, and the next real observation claims it with evidence.

    Bounded per pass so a tenant with a large table cannot make one heartbeat tick long, and
    idempotent: a second pass over a repaired org deletes nothing.
    """
    scope = "" if org_id is None else " and a.org_id = :org"
    result = conn.execute(text(
        "delete from graph_aliases where (org_id, alias_type, alias_key) in ("
        "  select a.org_id, a.alias_type, a.alias_key from graph_aliases a"
        "   where not exists (select 1 from graph_nodes n where n.org_id = a.org_id"
        "                       and n.node_id = a.node_id and n.valid_to is null)"
        f"  {scope} limit :limit)"),
        {"org": org_id, "limit": int(limit)} if org_id is not None else {"limit": int(limit)})
    return int(result.rowcount or 0)


def index_person_names(conn, *, org_id: str | None = None, limit: int = 2000) -> int:
    """Index the display name of every person node that is not yet findable by it.

    WHY A SWEEP AND NOT ONLY THE CHOKE POINT. `register_node_identity` now observes a person's
    name on every sighting, which repairs a node the moment anything mentions it again. That is
    lazy by nature, and the people who most need the lookup are exactly the ones nobody has
    written to since: a promise made in May that says "once Keshav confirms" is read months
    later, and the node it needs may not have been touched in between. Measured on the pilot
    2026-09-15: 76 person nodes, 41 carrying a human name, 4 reachable by it — and 49 conditional
    promises dropped for want of a subject the graph already held.

    ONE NAME AT A TIME, THROUGH `observe_person_name`, rather than one bulk insert. The contention
    rule is the reason: a name two living people answer to must end up resolving to NEITHER, and
    a set-based insert with `on conflict do nothing` is precisely the shape that awards it to
    whoever sorted first. This pass is slower and cannot produce that outcome.

    Bounded per pass so one heartbeat tick stays short, and idempotent: a second pass over an
    indexed org writes nothing and REPORTS nothing. Counting rows examined instead would report
    a permanent 1 on any graph holding one contended name, because the loser of a contention
    never gets a row of their own and is re-examined on every tick.
    """
    scope = "" if org_id is None else " and n.org_id = :org"
    rows = conn.execute(text(
        "select n.org_id, n.node_id, n.display_name from graph_nodes n "
        " where n.node_type = 'person' and n.valid_to is null "
        "   and n.display_name is not null and n.display_name <> '' "
        "   and n.display_name <> coalesce(n.canonical_key, '') "
        "   and not exists (select 1 from graph_aliases a "
        "                    where a.org_id = n.org_id and a.node_id = n.node_id "
        "                      and a.alias_type = :t) "
        f"  {scope} order by n.node_id limit :limit"),
        {"t": ALIAS_PERSON_NAME, "limit": int(limit), **({} if org_id is None else {"org": org_id})}
    ).fetchall()
    changed = 0
    for row in rows:
        # THE ADDRESS TEST IS PYTHON, NOT SQL, and that is a rule rather than a preference. This
        # module's standing law is that a key is COMPARED by string equality — `test_no_sql_on_
        # the_identity_path_matches_approximately` fails the build on any `like` in a `text()`
        # literal here, because a wildcard predicate is a similarity threshold that never appears
        # in the Python and so cannot be reviewed. The shape test is the same one the choke point
        # applies, spelled the same way.
        shown = str(row.display_name or "").strip()
        if "@" in shown:
            continue
        if observe_person_name(conn, org_id=row.org_id, node_id=row.node_id,
                               name=shown) != "unchanged":
            changed += 1
    return changed


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
    # `origin` IS PART OF THE QUESTION, not just provenance. A key marked contended is one two
    # live nodes both answered to, which is the same fact as two rows and must get the same
    # answer — see ALIAS_ORIGIN_CONTENDED for why it cannot be stored as two rows.
    rows = conn.execute(text(
        "select node_id from graph_aliases where org_id=:o and alias_type=:t "
        "and alias_key=:k and coalesce(origin,'') <> :contended limit 2"),
        {"o": org_id, "t": alias_type, "k": alias_key,
         "contended": ALIAS_ORIGIN_CONTENDED}).fetchall()
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

    # A PERSON'S OWN DISPLAY NAME IS A NAME THEY CAN BE FOUND BY, and until now nothing wrote it
    # down. `alias_keys_for_node` leaves person names out on purpose — an ANCHOR key would make
    # every future "John" collide with this one and raise a merge proposal for two people who
    # merely share a name. But the OBSERVED alias exists for precisely this, never creates a node
    # and never proposes a merge, and the only path that wrote one was the extractor's entity
    # list, which needs the same message to carry a name AND an email AND a person type.
    #
    # Measured on the pilot before this line existed: 76 person nodes, 41 of them carrying a
    # human display name, and 4 reachable by it. So 37 people the graph knew by name answered to
    # nobody when a promise said "once Keshav confirms", and the timeline correlator dropped 49
    # conditional promises at `unresolved_subject` for want of a lookup the graph could already
    # have answered.
    #
    # Guarded by the name not being the anchor restated: a person created from an address alone
    # is displayed as that address, and indexing "keshav@rocketsdr.ai" as a NAME would put the
    # same string in two namespaces for no gain.
    if node_type == "person" and display_name:
        shown = str(display_name).strip()
        anchor = str(canonical_key or "").strip()
        if shown and shown.casefold() != anchor.casefold() and "@" not in shown:
            observe_person_name(conn, org_id=org_id, node_id=node_id, name=shown,
                                event_id=event_id)
    return proposals


def observe_person_name(conn, *, org_id: str, node_id: str, name: str | None,
                        event_id: str | None = None) -> str:
    """Record what a person is CALLED, next to the email that actually identifies them.

    Written as an observed alias so a later "Rohit S." in prose can reach an anchored
    node. It is never used to create a person and never on its own to propose a merge:
    two people sharing a name is ordinary, not a duplicate.

    Returns what it DID — "indexed", "contended", "taken_over", or "unchanged" — rather than
    nothing. A caller sweeping a whole graph has to be able to report real work, and a pass that
    returns the number of rows it LOOKED at reads as non-idempotent for ever once one name is
    contended: that person never gets a row of their own, so they are examined on every tick.
    """
    key = person_name_key(name)
    if not key:
        return "unchanged"
    inserted = conn.execute(text(
        "insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin, "
        "created_by_event_id) values (:o, :t, :k, :n, 'observed', :ev) "
        "on conflict (org_id, alias_type, alias_key) do nothing"),
        {"o": org_id, "t": ALIAS_PERSON_NAME, "k": key, "n": node_id, "ev": event_id})
    if (inserted.rowcount or 0) > 0:
        # THE KEY WAS FREE and is now ours. Asked of the insert rather than by re-reading the
        # row, because a re-read cannot tell "we just created this" from "we already owned it" —
        # both come back owned by us, and a sweep that cannot tell them apart reports no work on
        # the pass that did all of it.
        return "indexed"
    # WHO ACTUALLY HOLDS IT NOW. The insert above is silent about whether it did anything, and
    # the difference matters: `do nothing` because this node already owned the key is ordinary,
    # while `do nothing` because a DIFFERENT living person is called the same thing means the
    # name identifies nobody. Before this, the two were indistinguishable and the second one
    # quietly handed every later mention of the name to whoever was inserted first.
    row = conn.execute(text(
        "select a.node_id, a.origin, (n.node_id is not null) as alive "
        "from graph_aliases a left join graph_nodes n "
        "  on n.org_id = a.org_id and n.node_id = a.node_id and n.valid_to is null "
        "where a.org_id=:o and a.alias_type=:t and a.alias_key=:k"),
        {"o": org_id, "t": ALIAS_PERSON_NAME, "k": key}).first()
    if row is None:
        return "unchanged"                       # nothing inserted and nothing there: no key
    if row.node_id == node_id:
        return "unchanged"                       # already ours; the ordinary re-sighting
    if str(row.origin or "") == ALIAS_ORIGIN_CONTENDED:
        return "unchanged"                       # answers to nobody already; leave it that way
    if not row.alive:
        # A KEY HELD BY A NODE THAT NO LONGER EXISTS IS UNOWNED — `record_alias` makes exactly
        # this correction for anchor keys and this path never did, so a rebuilt graph left every
        # observed name pointing at the first graph that ever existed. Measured on the pilot:
        # 87 of 89 person names resolved to a node with no row at any version. Taking the key
        # over is not a merge; there is nothing on the other side to merge with.
        conn.execute(text(
            "update graph_aliases set node_id=:n, origin='observed', created_by_event_id=:ev "
            "where org_id=:o and alias_type=:t and alias_key=:k"),
            {"o": org_id, "t": ALIAS_PERSON_NAME, "k": key, "n": node_id, "ev": event_id})
        return "taken_over"
    # A SECOND LIVE PERSON BY THE SAME NAME. No merge is proposed and nothing is deleted —
    # sharing a name is ordinary, not a duplicate, and this module has said so since it was
    # written. The key simply stops resolving, for both of them.
    conn.execute(text(
        "update graph_aliases set origin=:contended where org_id=:o and alias_type=:t "
        "and alias_key=:k"),
        {"o": org_id, "t": ALIAS_PERSON_NAME, "k": key,
         "contended": ALIAS_ORIGIN_CONTENDED})
    return "contended"


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
