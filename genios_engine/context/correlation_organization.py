"""L2.3 · Cross Organization — one counterparty organisation, several people, several roles.

**THE SIXTH OF EIGHT.** Cross Tool and Cross User live in `correlation.py`; Resource, Timeline,
Dependency and (since this branch) Conversation have their own modules. This is Cross
Organization. Cross Domain remains unwritten.

**WHAT IT IS FOR, measured.** The pilot's graph holds 43 company nodes and 47 `works_at` edges,
and six firms have two people each — `peakxv.com` (harshita, vidushi), `afore.vc` (joseph,
madison), `nsrcel.iimb.ac.in`, `reticle.sh`, `tryfuse.ai`, `vectorly.app`. Nothing reads that. Two
people at one fund, both silent for the same 28 days, are two situations and would be two cards
saying the same thing about the same firm.

**IT DOES NOT MERGE THE SITUATIONS.** Two people are two conversations, two obligations and two
receipts — the same argument that retired the boilerplate unit and shaped Cross Conversation.
This adds a GROUP over them so a reader can see "Peak XV, two people, both silent" instead of
discovering it by reading two cards and doing the arithmetic.

**A SITUATION ANCHOR IS ALMOST NEVER A PERSON, and the first cut of this module did not know it.**
Run read-only against the pilot before any test existed, `restrict_to=<the 82 waiting anchors>`
returned ZERO groups. The anchors are not people:

    awaiting_response       | outreach | 41        first_response_overdue | thread | 41

`works_at` runs person → company, so raw anchor ids can never match one. The bridges, counted on
the same run: `person --corresponded_with--> thread` resolves 41/41 thread anchors to 22 people,
and `outreach --concerns--> {thread 21, person 18, service 2}` is the outreach anchor's only way
out. `resolve_people` walks exactly those, at most two hops — the same bounded shape
`situation_bso.absence_receipt_event_ids` uses, and bounded for the same reason: an unbounded walk
is how one client's evidence reaches another's.

**THIS MODULE HAS NO OPINION ABOUT WHOSE TURN IT IS, and a reader of the numbers above needs to
know that.** Handed all 82 waiting anchors it returns FOUR firms, and only two of them have gone
quiet: Afore and Peak XV sit at `ball_in_court = them` with 29 days each, while Reticle and
Vectorly sit at `ball_in_court = us` — we are the silent party there, and a card saying Reticle
went dark would be wrong in the one direction that matters. Grouping is a primitive; direction is
the READING's job, and `outreach_situations.read_organization_silence` applies it by firing on
`thread.days_waiting`, which `waiting.py` writes only while the last message was ours. Live, that
reading returns the two.

**WHAT IT REFUSES TO DO, and these are the catalogue's own cases.**

  * CC-37 — one organisation, several business roles. A supplier in one process and a customer in
    another share an IDENTITY and share nothing else. Roles are carried PER MEMBER and never
    folded into a group-level relationship. On this tenant the role fields are all but empty — one
    `relationship.nature` (*partner*) and one `party.role` (*introducer*) across every node — so
    `relationship_is_uniform` answers **None**, not True. "We do not know what they are to us" is
    not "they are one thing to us", and a boolean that cannot say so is the CC-37 failure itself.
  * CC-39 — parent and subsidiary. Identity is not applicability. This module makes no claim that
    a group certificate satisfies a subsidiary's requirement; it groups what the graph says works
    at one company node and stops.
  * CC-40 — a consultant across several clients. Every statement is org-scoped on every join, and
    the resolver's hops are org-scoped too.
  * CC-42 — a shared external identity is not a shared audience. This returns groups; visibility
    of what a member contributed is enforced where it already is, and nothing here widens it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import bindparam, text

#: How many people at one organisation make it an ORGANISATION-level reading rather than a
#: person-level one. Two: the whole point is that a second person at the same firm changes what
#: the reader should do — chase one contact, or accept that the firm has gone quiet — and one
#: person is already fully served by the per-counterparty situation.
MIN_MEMBERS = 2


@dataclass(frozen=True, slots=True)
class OrgMember:
    """One person at a counterparty organisation, with what we know of their relationship."""

    node_id: str
    name: str
    #: What this person is to us, where the graph holds it. `None` is the common case on a real
    #: tenant and is the honest state — a group with no roles at all is still a group.
    role: str | None = None


@dataclass(frozen=True, slots=True)
class OrgGroup:
    """One counterparty organisation and the people we deal with there."""

    company_node_id: str
    company: str
    members: tuple[OrgMember, ...]

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def roles(self) -> tuple[str, ...]:
        """The distinct roles present, sorted. Empty when the graph holds none."""
        return tuple(sorted({m.role for m in self.members if m.role}))

    @property
    def roles_known(self) -> bool:
        """Every member carries a role. False whenever even one is missing — a partial answer to
        "what is this organisation to us" is not an answer."""
        return bool(self.members) and all(m.role for m in self.members)

    @property
    def is_multi_role(self) -> bool:
        """CC-37, stated as a POSITIVE only. True means the graph has actually recorded two
        different relationships at one organisation, so its obligations must not be read as one."""
        return len(self.roles) > 1

    @property
    def relationship_is_uniform(self) -> bool | None:
        """May this organisation be treated as ONE relationship? Three answers, not two.

        `True` — every member has a role and they agree.
        `False` — the graph records more than one; CC-37 applies and flattening is a defect.
        `None` — we do not know, because at least one member has no role at all.

        The third state is the whole point. `is_multi_role` alone returns False for a group with
        no roles whatsoever, and a caller reading that as "safe to treat as one relationship" has
        made exactly the mistake CC-37 names — on the strength of no evidence. On the pilot every
        group answers `None`.
        """
        if not self.roles_known:
            return None
        return len(self.roles) == 1


#: Person → the company node they work at.
#:
#: `works_at` is written by `context/pipeline.py` and already read by `outreach_situations`'s
#: `_EMPLOYERS`; this reads the same edge and keeps the NODE ID as well as the display name,
#: because a group has to be addressable and two firms can share a display name.
_ORG_MEMBERS = (
    "select e.to_node_id as company_node, c.display_name as company, "
    "       e.from_node_id as person_node, "
    "       coalesce(p.display_name, p.canonical_key) as person "
    "from graph_edges e "
    "join graph_nodes c on c.org_id = e.org_id and c.node_id = e.to_node_id "
    "     and c.node_type = 'company' and c.valid_to is null "
    "join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
    "     and p.node_type = 'person' and p.valid_to is null "
    "where e.org_id = :o and e.edge_type = 'works_at' and e.valid_to is null "
    "order by c.display_name, person"
)

#: What each person IS to us. Two fields because two writers fill them and neither is guaranteed:
#: `relationship.nature` is the richer one where the extractor placed it, `party.role` the
#: structural one. Both are nearly always absent, and absent stays absent.
_MEMBER_ROLES = (
    "select f.subject_node_id as person_node, f.field as field, f.value as value "
    "from graph_facts f "
    "where f.org_id = :o and f.status = 'active' and f.valid_to is null "
    "  and f.field in ('relationship.nature', 'party.role') "
    "order by f.subject_node_id, f.field"
)

#: HOP ONE — the anchor itself, when it already is a person.
_ANCHOR_IS_PERSON = (
    "select n.node_id as person_node from graph_nodes n "
    "where n.org_id = :o and n.node_type = 'person' and n.valid_to is null "
    "  and n.node_id in :anchors"
)

#: HOP TWO — a thread anchor. `person --corresponded_with--> thread`, the same bridge
#: `correlation_conversation` and `_THREAD_COVERED_BY_PARTY` use. 41/41 on the pilot.
_PARTY_ON_ANCHOR = (
    "select e.from_node_id as person_node from graph_edges e "
    "join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
    "     and p.node_type = 'person' and p.valid_to is null "
    "where e.org_id = :o and e.edge_type = 'corresponded_with' and e.valid_to is null "
    "  and e.to_node_id in :anchors"
)

#: HOP TWO — an outreach anchor. `outreach --concerns--> person`, and the same edge again for the
#: 21 that concern a THREAD, whose party is then found by `_PARTY_ON_ANCHOR` on the second pass.
#: Two passes is the whole walk; there is no third.
_CONCERNS_TARGETS = (
    "select e.to_node_id as target from graph_edges e "
    "where e.org_id = :o and e.edge_type = 'concerns' and e.valid_to is null "
    "  and e.from_node_id in :anchors"
)


def _role_of(entries: Mapping[str, object]) -> str | None:
    """`relationship.nature` wins over `party.role`: it is what the counterparty IS to this
    business, where `party.role` is often the structural default. Neither is invented."""
    for field in ("relationship.nature", "party.role"):
        value = _plain(entries.get(field))
        if value:
            return value
    return None


def _plain(raw) -> str | None:
    """`jsonb` arrives decoded from Postgres and as text elsewhere; a bare string is also legal."""
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip().strip('"')
        return stripped or None
    return str(raw) or None


def _ids(conn, statement: str, org_id: str, anchors: Sequence[str], column: str) -> set[str]:
    """One read over a list of ids.

    `in :anchors` with an EXPANDING bindparam, not `= any(:anchors)` — the array cast is
    Postgres-only and would make these paths untestable on SQLite, the rule `waiting.py:84` and
    `situation_bso._L1_BY_EVENT_SELECT` both already record.

    Empty in, empty out: `in ()` is a syntax error rather than a zero-row query, and a quiet
    tenant reaches here with nothing.
    """
    if not anchors:
        return set()
    stmt = text(statement).bindparams(bindparam("anchors", expanding=True))
    rows = conn.execute(stmt, {"o": org_id, "anchors": sorted(set(anchors))})
    return {str(row[column]) for row in rows.mappings().all() if row[column]}


def resolve_people(conn, org_id: str, anchors: Sequence[str]) -> tuple[str, ...]:
    """Situation anchors → the counterparty people behind them. Sorted, deduplicated.

    THREE SHAPES, because the pilot has three and a caller should not have to know which. An
    anchor that already is a person; a THREAD anchor, reached by the party who corresponded on it;
    an OUTREACH anchor, which `concerns` a person directly (18) or a thread (21) whose party is
    then the person. `service` targets (2) resolve to nobody, correctly — a service is not a
    counterparty we can be waiting on a human at.

    AT MOST TWO HOPS, and the bound is the safety property. `concerns` and `corresponded_with` are
    dense edges; a transitive walk would drift from one situation's counterparty to another's, and
    on a consultant node (CC-40) from one client to another. Two hops is what the graph needs and
    is where this stops.
    """
    anchors = [str(a) for a in anchors if a]
    if not anchors:
        return ()
    people = _ids(conn, _ANCHOR_IS_PERSON, org_id, anchors, "person_node")
    people |= _ids(conn, _PARTY_ON_ANCHOR, org_id, anchors, "person_node")
    targets = _ids(conn, _CONCERNS_TARGETS, org_id, anchors, "target")
    if targets:
        people |= _ids(conn, _ANCHOR_IS_PERSON, org_id, sorted(targets), "person_node")
        people |= _ids(conn, _PARTY_ON_ANCHOR, org_id, sorted(targets), "person_node")
    return tuple(sorted(people))


def group_by_organization(member_rows: Sequence[Mapping],
                          role_rows: Sequence[Mapping] = (),
                          *, restrict_to: Sequence[str] | None = None) -> tuple[OrgGroup, ...]:
    """Group people into their counterparty organisations. Pure, so the rule reads in one place.

    `restrict_to` narrows to a set of PERSON node ids — the callers that matter want "the people
    we are WAITING on at this firm", not "everyone we have ever emailed there", and computing the
    second and filtering afterwards would report a firm as fully silent when only one of four
    contacts is. An empty sequence means "nobody", which is not the same as `None`.
    """
    roles_by_person: dict[str, dict[str, object]] = {}
    for row in role_rows:
        roles_by_person.setdefault(str(row["person_node"]), {})[str(row["field"])] = row["value"]

    wanted = None if restrict_to is None else {str(n) for n in restrict_to}
    buckets: dict[tuple[str, str], list[OrgMember]] = {}
    for row in member_rows:
        person = str(row["person_node"])
        if wanted is not None and person not in wanted:
            continue
        key = (str(row["company_node"]), str(row["company"] or ""))
        bucket = buckets.setdefault(key, [])
        # ONE ROW PER PERSON. A person with two `works_at` edges to the same company — a re-write
        # of the same edge, or an alias resolved after the fact — is one member, and counting them
        # twice would report a two-person firm as four.
        if any(existing.node_id == person for existing in bucket):
            continue
        bucket.append(OrgMember(node_id=person, name=str(row["person"] or person),
                                role=_role_of(roles_by_person.get(person, {}))))

    out = [OrgGroup(company_node_id=node, company=name,
                    members=tuple(sorted(members, key=lambda m: (m.name, m.node_id))))
           for (node, name), members in buckets.items() if len(members) >= MIN_MEMBERS]
    return tuple(sorted(out, key=lambda g: (-g.size, g.company, g.company_node_id)))


def find_organizations(conn, org_id: str, *,
                       restrict_to: Sequence[str] | None = None,
                       anchors: Sequence[str] | None = None) -> tuple[OrgGroup, ...]:
    """Counterparty organisations with at least `MIN_MEMBERS` people, largest first.

    `anchors` is the form a caller in this layer actually has — situation anchor ids — and is
    resolved through `resolve_people`. `restrict_to` is the resolved form, for a caller that
    already holds person ids. Passing both narrows to the union, which is what a caller combining
    a situation sweep with a known list means.

    Two statements for the whole tenant rather than one per group — the same bulk discipline every
    other pass in this layer keeps.
    """
    narrowed: set[str] | None = None
    if restrict_to is not None:
        narrowed = {str(n) for n in restrict_to}
    if anchors is not None:
        narrowed = (narrowed or set()) | set(resolve_people(conn, org_id, anchors))

    members = conn.execute(text(_ORG_MEMBERS), {"o": org_id}).mappings().all()
    roles = conn.execute(text(_MEMBER_ROLES), {"o": org_id}).mappings().all()
    return group_by_organization(members, roles,
                                 restrict_to=None if narrowed is None else sorted(narrowed))


__all__ = [
    "MIN_MEMBERS",
    "OrgGroup",
    "OrgMember",
    "find_organizations",
    "group_by_organization",
    "resolve_people",
]
