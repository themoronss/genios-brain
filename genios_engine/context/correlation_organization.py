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

**A SITUATION ANCHOR IS ALMOST NEVER A PERSON.** Run read-only against the pilot before any test
existed, narrowing this module by the 82 waiting anchor ids returned ZERO groups against a tenant
that has four. The anchors are not people:

    awaiting_response       | outreach | 41        first_response_overdue | thread | 41

`works_at` runs person → company, so an anchor id can never match one. The bridges the graph does
hold, counted on the same run: `person --corresponded_with--> thread` resolves 41/41 thread
anchors to 22 people, and `outreach --concerns--> {thread 21, person 18, service 2}` is the
outreach anchor's only way out.

**AND THEN THE RESOLVER THAT WALKED THEM WAS DELETED, which is the more useful half of the
story.** A `resolve_people` was written here, tested eight ways, and called by nothing: the only
caller is `_gather`, which asks for every organisation and lets `read_organization_silence`
intersect them with the waiting rows it already holds. That is the correct order — see
`find_organizations` on why the denominator must count everyone — so the resolver was speculative
generality, shipped with the branch's own signature defect inside a module written to complain
about it. `correlation_domain._SITUATIONS_BY_PERSON` does the same walk in ONE statement, for a
consumer that exists. One walk, one caller.

**THIS MODULE HAS NO OPINION ABOUT WHOSE TURN IT IS, and a reader of the numbers above needs to
know that.** Narrowed to the 82 waiting anchors it finds FOUR firms, and only two of them have
gone quiet: Afore and Peak XV sit at `ball_in_court = them` with 29 days each, while Reticle and
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
from pathlib import Path

from sqlalchemy import text

#: How many people at one organisation make it an ORGANISATION-level reading rather than a
#: person-level one. Two: the whole point is that a second person at the same firm changes what
#: the reader should do — chase one contact, or accept that the firm has gone quiet — and one
#: person is already fully served by the per-counterparty situation.
MIN_MEMBERS = 2

#: Where an authored grouping lives. One file per grouping; see the README beside them.
GROUPINGS_DIR = Path(__file__).resolve().parent / "groupings"


class GroupingError(ValueError):
    """A grouping file that cannot be used. Names the file, like `ExclusionError` next door."""


@dataclass(frozen=True, slots=True)
class Grouping:
    """"For my business, these people are one party" — the edge that says so.

    `works_at` / `person` / `company` was hardcoded, and it is one business's version of a true
    statement. A hospital groups clinicians by DEPARTMENT, a school groups guardians by
    HOUSEHOLD, a broker groups traders by DESK, a consultancy groups people by the ENGAGEMENT
    they are staffed on rather than by who employs them. Every one of those is the same reading
    — more than one person on the other side has gone quiet — over a different edge.
    """

    grouping_id: str
    edge_type: str
    member_node_type: str
    group_node_type: str
    min_members: int = MIN_MEMBERS
    why: str = ""


def load_groupings(directory: "Path | None" = None) -> tuple[Grouping, ...]:
    """Every `*.yaml` in the directory, in filename order.

    Sorted, so two machines load the same set and a diff of two reports is a diff of behaviour
    rather than of `readdir` — the reason `load_exclusions` and `patterns.load_directory` sort.

    STRICT, unlike the corpus reads elsewhere on this branch, and deliberately: an unreadable
    `Domain Expertise/` is a deployment problem where the shipped default is still correct, but
    a grouping file that will not parse is a statement somebody wrote about who counts as one
    party, and silently ignoring it would group people the author said not to group.
    """
    import yaml

    root = directory or GROUPINGS_DIR
    if not root.is_dir():
        return ()
    out: list[Grouping] = []
    for path in sorted(root.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise GroupingError(f"{path.name} could not be read as YAML: {exc}") from exc
        if not isinstance(data, Mapping):
            raise GroupingError(f"{path.name} is not a grouping mapping")
        missing = [k for k in ("grouping_id", "edge_type", "member_node_type",
                               "group_node_type") if not str(data.get(k) or "").strip()]
        if missing:
            raise GroupingError(f"{path.name} is missing {', '.join(missing)}")
        floor = int(data.get("min_members") or MIN_MEMBERS)
        if floor < MIN_MEMBERS:
            # A "group" of one is a duplicate of the per-member card with a firm's name on it.
            raise GroupingError(
                f"{path.name} sets min_members={floor}; the reading refuses below {MIN_MEMBERS}")
        out.append(Grouping(
            grouping_id=str(data["grouping_id"]).strip(),
            edge_type=str(data["edge_type"]).strip(),
            member_node_type=str(data["member_node_type"]).strip(),
            group_node_type=str(data["group_node_type"]).strip(),
            min_members=floor, why=str(data.get("why") or "").strip()))
    return tuple(out)


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
#: BOUND PARAMETERS FOR THE THREE TYPES, not interpolation. They arrive from a YAML file a
#: tenant can edit, and a node type spliced into SQL is a node type that can end a statement.
_ORG_MEMBERS = (
    "select e.to_node_id as company_node, c.display_name as company, "
    "       e.from_node_id as person_node, "
    "       coalesce(p.display_name, p.canonical_key) as person "
    "from graph_edges e "
    "join graph_nodes c on c.org_id = e.org_id and c.node_id = e.to_node_id "
    "     and c.node_type = :group_type and c.valid_to is null "
    "join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
    "     and p.node_type = :member_type and p.valid_to is null "
    "where e.org_id = :o and e.edge_type = :edge_type and e.valid_to is null "
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


def group_by_organization(member_rows: Sequence[Mapping],
                          role_rows: Sequence[Mapping] = (),
                          *, min_members: int = MIN_MEMBERS) -> tuple[OrgGroup, ...]:
    """Group people into their counterparty organisations. Pure, so the rule reads in one place."""
    roles_by_person: dict[str, dict[str, object]] = {}
    for row in role_rows:
        roles_by_person.setdefault(str(row["person_node"]), {})[str(row["field"])] = row["value"]

    buckets: dict[tuple[str, str], list[OrgMember]] = {}
    for row in member_rows:
        person = str(row["person_node"])
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
           for (node, name), members in buckets.items() if len(members) >= min_members]
    return tuple(sorted(out, key=lambda g: (-g.size, g.company, g.company_node_id)))


def find_organizations(conn, org_id: str,
                       groupings: "Sequence[Grouping] | None" = None) -> tuple[OrgGroup, ...]:
    """Every counterparty organisation with at least `MIN_MEMBERS` people, largest first.

    DELIBERATELY UNNARROWED, and an earlier cut of this function was wrong about that. It took
    `anchors=` and `restrict_to=` so a caller could ask only about the people it was waiting on.
    Nobody wants that: the DENOMINATOR is the point. "Two of the two partners we know at Peak XV
    are silent" is a firm going dark; "two of nine" is a Tuesday, and a group narrowed before it
    is counted cannot tell them apart. `read_organization_silence` intersects these groups with
    the waiting rows it already holds, which is the correct order.

    Two statements for the whole tenant rather than one per group — the same bulk discipline every
    other pass in this layer keeps.
    """
    # ONE ROLE READ FOR EVERY GROUPING. What a person IS to us does not depend on which edge
    # grouped them, so reading it once per grouping would be the same statement N times.
    roles = conn.execute(text(_MEMBER_ROLES), {"o": org_id}).mappings().all()

    out: list[OrgGroup] = []
    for grouping in (groupings if groupings is not None else load_groupings()):
        members = conn.execute(text(_ORG_MEMBERS), {
            "o": org_id, "edge_type": grouping.edge_type,
            "member_type": grouping.member_node_type,
            "group_type": grouping.group_node_type}).mappings().all()
        out.extend(group_by_organization(members, roles, min_members=grouping.min_members))
    # LARGEST FIRST ACROSS ALL GROUPINGS, then by name, so a tenant with two groupings gets one
    # ordered list rather than two concatenated ones — the caller reads a ranking, not a
    # traversal order.
    return tuple(sorted(out, key=lambda g: (-len(g.members), g.company, g.company_node_id)))


__all__ = [
    "GROUPINGS_DIR",
    "MIN_MEMBERS",
    "Grouping",
    "GroupingError",
    "OrgGroup",
    "OrgMember",
    "find_organizations",
    "group_by_organization",
    "load_groupings",
]
