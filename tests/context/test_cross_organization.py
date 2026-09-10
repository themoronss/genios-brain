"""CC-37…CC-42 · Cross Organization — one counterparty firm, several people, several roles.

    pytest tests/context/test_cross_organization.py -q

THE SIXTH OF EIGHT CORRELATORS. Cross Conversation shipped on this branch; this is the next.
Cross Domain remains.

WHAT THE PILOT HOLDS, measured before a line of this file was written: 43 company nodes, 47
`works_at` edges, and six firms with two people each — Peak XV (harshita, vidushi), Afore (joseph,
madison), NSRCEL, Reticle, Fuse, Vectorly. Nothing read it. Two people at one fund, both silent
for the same 28 days, were two situations and would have been two cards saying the same thing
about the same firm.

RUN AGAINST LIVE DATA BEFORE THESE TESTS EXISTED, and it caught two defects that the module's
first cut shipped with. Both are pinned by name below:

  * a situation anchor is almost never a person — 41 `outreach`, 41 `thread`, 0 people — so
    narrowing by the 82 waiting anchor ids returned ZERO groups against a tenant that has four;
  * every role fact on the tenant is absent, and a two-valued `is_multi_role` answered False for
    a group it knew nothing about, which a caller reads as "safe to treat as one relationship".

After the fix, the same live read: 82 anchors → 41 people → 4 organisations where two people are
both silent, Peak XV and Afore among them.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.correlation_organization import (
    MIN_MEMBERS,
    find_organizations,
    group_by_organization,
)

pytestmark = pytest.mark.unit

ORG = "org_pilot"
OTHER = "org_other"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in (
            "create table graph_nodes (node_id text, org_id text, node_type text, "
            "canonical_key text, display_name text, valid_to timestamp)",
            "create table graph_edges (org_id text, edge_type text, from_node_id text, "
            "to_node_id text, valid_to timestamp)",
            "create table graph_facts (fact_version_id text, org_id text, subject_node_id text, "
            "field text, value text, status text, valid_to timestamp)",
        ):
            c.execute(text(ddl))
    with engine.begin() as c:
        yield c


def node(c, node_id: str, name: str, node_type: str = "person", *, org: str = ORG,
         valid_to=None) -> None:
    c.execute(text("insert into graph_nodes values (:n, :o, :t, :k, :k, :v)"),
              {"n": node_id, "o": org, "t": node_type, "k": name, "v": valid_to})


def edge(c, kind: str, src: str, dst: str, *, org: str = ORG, valid_to=None) -> None:
    c.execute(text("insert into graph_edges values (:o, :e, :f, :t, :v)"),
              {"o": org, "e": kind, "f": src, "t": dst, "v": valid_to})


def works_at(c, person: str, company: str, *, org: str = ORG, valid_to=None) -> None:
    edge(c, "works_at", person, company, org=org, valid_to=valid_to)


def role(c, person: str, value: str, field: str = "relationship.nature", *,
         org: str = ORG, status: str = "active") -> None:
    c.execute(text("insert into graph_facts values (:f, :o, :n, :fd, :v, :s, null)"),
              {"f": f"fv_{person}_{field}", "o": org, "n": person, "fd": field,
               "v": value, "s": status})


def peak_xv(c, *, org: str = ORG) -> None:
    """The firm the founder named: two partners, both silent, one company node."""
    node(c, "c_peak", "peakxv.com", "company", org=org)
    node(c, "p_harshita", "harshita@peakxv.com", org=org)
    node(c, "p_vidushi", "vidushi@peakxv.com", org=org)
    works_at(c, "p_harshita", "c_peak", org=org)
    works_at(c, "p_vidushi", "c_peak", org=org)


# =============================================================================================
# The group the system could not see.
# =============================================================================================
def test_two_people_at_one_firm_are_one_organisation(db):
    peak_xv(db)

    [group] = find_organizations(db, ORG)

    assert group.company == "peakxv.com"
    assert group.size == 2


def test_every_member_is_named(db):
    """A count alone cannot be acted on — the reader has to know which two people."""
    peak_xv(db)

    [group] = find_organizations(db, ORG)

    assert {m.name for m in group.members} == {"harshita@peakxv.com", "vidushi@peakxv.com"}


def test_one_person_is_a_counterparty_not_an_organisation(db):
    """Below the floor the per-person situation already says everything there is to say, and a
    one-member "group" would double every card on the feed."""
    node(db, "c_solo", "solo.vc", "company")
    node(db, "p_solo", "one@solo.vc")
    works_at(db, "p_solo", "c_solo")

    assert find_organizations(db, ORG) == ()
    assert MIN_MEMBERS == 2


def test_the_biggest_firm_comes_first(db):
    peak_xv(db)
    node(db, "c_afore", "afore.vc", "company")
    for who in ("joseph", "madison", "chris"):
        node(db, f"p_{who}", f"{who}@afore.vc")
        works_at(db, f"p_{who}", "c_afore")

    sizes = [g.size for g in find_organizations(db, ORG)]

    assert sizes == [3, 2]


def test_two_works_at_edges_for_one_person_is_still_one_member(db):
    """A re-written edge, or an alias resolved after the fact, would otherwise report a
    two-person firm as four — and the number is what the card would say."""
    peak_xv(db)
    works_at(db, "p_harshita", "c_peak")

    [group] = find_organizations(db, ORG)

    assert group.size == 2


def test_a_retired_edge_does_not_keep_someone_at_a_firm(db):
    """Somebody who left. `valid_to` is how the graph says so, and a group that ignores it
    reports a departed contact as silent."""
    peak_xv(db)
    node(db, "p_gone", "gone@peakxv.com")
    works_at(db, "p_gone", "c_peak", valid_to="2026-01-01")

    [group] = find_organizations(db, ORG)

    assert group.size == 2


# =============================================================================================
# DEFECT ONE — a situation anchor is almost never a person. RETIRED, and the record stays.
#
# Eight tests stood here for `resolve_people` and the `anchors=` / `restrict_to=` parameters. They
# were correct about the graph — measured on the pilot, all 41 `awaiting_response` anchors are
# `outreach` nodes and all 41 `first_response_overdue` anchors are `thread` nodes, and the two
# bridges (`person --corresponded_with--> thread`, `outreach --concerns--> {thread|person}`)
# resolved 82 anchors to 41 people.
#
# THEY WERE TESTING CODE NOTHING CALLED. `_gather` asks `find_organizations(c, org_id)` for every
# organisation and lets `read_organization_silence` intersect them with the waiting rows it
# already holds — which is the CORRECT order, because the denominator has to count everyone at a
# firm for "two of the two partners are silent" to mean anything. So the resolver was speculative
# generality, shipped with this branch's own signature defect inside a module written to complain
# about it, and eight green tests hid that from every gate.
#
# The walk itself survives where it has a consumer: `correlation_domain._SITUATIONS_BY_PERSON`
# does it in one statement, and `tests/context/test_cross_domain.py::
# test_two_anchors_that_are_not_people_still_resolve_to_one_subject` is where it is pinned now.
# Deleted rather than kept "in case" — that is what put it here.
# =============================================================================================
def test_a_firm_is_counted_over_everyone_who_works_there(db):
    """The property the deleted narrowing would have broken. `find_organizations` takes no filter
    at all, so `size` is the firm's real headcount as the graph knows it and a reading can say
    "two of the two" rather than "two of however many happened to be waiting"."""
    peak_xv(db)
    node(db, "p_third", "third@peakxv.com")
    works_at(db, "p_third", "c_peak")

    [group] = find_organizations(db, ORG)

    assert group.size == 3


# =============================================================================================
# DEFECT TWO / CC-37 — one organisation, several business roles.
# =============================================================================================
def test_a_firm_we_know_nothing_about_is_not_a_firm_we_know_is_one_thing(db):
    """THE SECOND DEFECT THE LIVE RUN CAUGHT. The pilot holds ONE `relationship.nature` and ONE
    `party.role` across every node, so `roles` is empty for every group. A two-valued
    `is_multi_role` answers False there — and a caller reading False as "safe to treat as one
    relationship" has made exactly the mistake CC-37 names, on the strength of no evidence."""
    peak_xv(db)

    [group] = find_organizations(db, ORG)

    assert group.roles == ()
    assert group.is_multi_role is False
    assert group.relationship_is_uniform is None


def test_two_roles_at_one_firm_forbid_a_single_reading(db):
    """CC-37 proper. A supplier in one process and a customer in another share an identity and
    share nothing else — obligation direction, money direction and confidentiality all differ."""
    peak_xv(db)
    role(db, "p_harshita", "supplier")
    role(db, "p_vidushi", "customer")

    [group] = find_organizations(db, ORG)

    assert group.roles == ("customer", "supplier")
    assert group.is_multi_role is True
    assert group.relationship_is_uniform is False


def test_one_agreed_role_is_the_only_case_that_may_be_read_as_one(db):
    peak_xv(db)
    role(db, "p_harshita", "investor")
    role(db, "p_vidushi", "investor")

    [group] = find_organizations(db, ORG)

    assert group.relationship_is_uniform is True
    assert group.is_multi_role is False


def test_one_role_and_one_blank_is_still_unknown(db):
    """Half an answer is not an answer. The blank member could be anything, including the thing
    that makes this organisation two relationships."""
    peak_xv(db)
    role(db, "p_harshita", "investor")

    [group] = find_organizations(db, ORG)

    assert group.roles_known is False
    assert group.relationship_is_uniform is None


def test_the_richer_role_field_wins_over_the_structural_one(db):
    """`relationship.nature` is what the counterparty IS to this business; `party.role` is often
    the structural default. Neither is invented, and the order is fixed rather than incidental."""
    peak_xv(db)
    role(db, "p_harshita", "investor", "relationship.nature")
    role(db, "p_harshita", "recipient", "party.role")

    [group] = find_organizations(db, ORG)

    assert next(m for m in group.members if m.node_id == "p_harshita").role == "investor"


def test_a_superseded_role_is_not_a_role(db):
    peak_xv(db)
    role(db, "p_harshita", "supplier", status="superseded")
    role(db, "p_vidushi", "customer")

    [group] = find_organizations(db, ORG)

    assert group.roles == ("customer",)
    assert group.relationship_is_uniform is None


# =============================================================================================
# CC-40 / CC-42 — tenancy, and what a shared identity does not grant.
# =============================================================================================
def test_another_orgs_firm_never_appears_in_this_ones(db):
    peak_xv(db, org=OTHER)

    assert find_organizations(db, ORG) == ()
    assert len(find_organizations(db, OTHER)) == 1


def test_a_shared_person_never_bridges_two_tenants(db):
    """CC-40. A consultant working for two clients exists in both graphs. One client's `works_at`
    edge must never place that person inside the other client's firm, and one client's roles must
    never describe the other's relationship."""
    peak_xv(db)
    node(db, "c_peak", "peakxv.com", "company", org=OTHER)
    node(db, "p_harshita", "harshita@peakxv.com", org=OTHER)
    node(db, "p_other", "someone@peakxv.com", org=OTHER)
    works_at(db, "p_harshita", "c_peak", org=OTHER)
    works_at(db, "p_other", "c_peak", org=OTHER)

    [ours] = find_organizations(db, ORG)
    [theirs] = find_organizations(db, OTHER)

    assert {m.node_id for m in ours.members} == {"p_harshita", "p_vidushi"}
    assert {m.node_id for m in theirs.members} == {"p_harshita", "p_other"}


def test_a_role_recorded_by_another_tenant_is_not_read_here(db):
    peak_xv(db)
    role(db, "p_harshita", "supplier", org=OTHER)
    role(db, "p_vidushi", "supplier", org=OTHER)

    [group] = find_organizations(db, ORG)

    assert group.roles == ()


# =============================================================================================
# The grouping rule, without a database.
# =============================================================================================
def test_grouping_is_pure_and_reads_in_one_place():
    rows = [{"company_node": "c", "company": "Peak XV", "person_node": "a", "person": "A"},
            {"company_node": "c", "company": "Peak XV", "person_node": "b", "person": "B"}]

    [group] = group_by_organization(rows)

    assert group.size == 2
    assert group.company == "Peak XV"


def test_members_are_ordered_so_a_card_reads_the_same_every_run():
    rows = [{"company_node": "c", "company": "X", "person_node": "b", "person": "Zoe"},
            {"company_node": "c", "company": "X", "person_node": "a", "person": "Adam"}]

    [group] = group_by_organization(rows)

    assert [m.name for m in group.members] == ["Adam", "Zoe"]


def test_a_person_with_no_display_name_falls_back_to_their_id():
    rows = [{"company_node": "c", "company": "X", "person_node": "a", "person": None},
            {"company_node": "c", "company": "X", "person_node": "b", "person": "B"}]

    [group] = group_by_organization(rows)

    assert "a" in {m.name for m in group.members}


def test_nothing_in_yields_nothing_out():
    assert group_by_organization([]) == ()
