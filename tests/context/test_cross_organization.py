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
    `restrict_to=<the 82 waiting anchors>` returned ZERO groups against a tenant that has four;
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
    resolve_people,
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
# DEFECT ONE — a situation anchor is almost never a person.
# =============================================================================================
def test_a_thread_anchor_resolves_to_the_person_on_it(db):
    """THE DEFECT THE LIVE RUN CAUGHT. On the pilot all 41 `first_response_overdue` anchors are
    THREAD nodes and all 41 `awaiting_response` anchors are OUTREACH nodes — not one is a person.
    `works_at` runs person → company, so raw anchor ids matched nothing and the module returned
    zero groups against a tenant that has four."""
    peak_xv(db)
    node(db, "t_h", "Thread with harshita", "thread")
    node(db, "t_v", "Thread with vidushi", "thread")
    edge(db, "corresponded_with", "p_harshita", "t_h")
    edge(db, "corresponded_with", "p_vidushi", "t_v")

    assert resolve_people(db, ORG, ["t_h", "t_v"]) == ("p_harshita", "p_vidushi")
    assert find_organizations(db, ORG, anchors=["t_h", "t_v"])[0].size == 2


def test_an_outreach_anchor_reaches_a_person_it_concerns(db):
    """18 of the pilot's outreach anchors `concerns` a person directly."""
    peak_xv(db)
    node(db, "o_h", "Outreach to harshita", "outreach")
    edge(db, "concerns", "o_h", "p_harshita")

    assert resolve_people(db, ORG, ["o_h"]) == ("p_harshita",)


def test_an_outreach_anchor_reaches_a_person_through_a_thread(db):
    """And 21 concern a THREAD, whose party is the person — the second hop, and the reason this
    resolver is two-pass rather than one."""
    peak_xv(db)
    node(db, "t_h", "Thread with harshita", "thread")
    node(db, "o_h", "Outreach", "outreach")
    edge(db, "concerns", "o_h", "t_h")
    edge(db, "corresponded_with", "p_harshita", "t_h")

    assert resolve_people(db, ORG, ["o_h"]) == ("p_harshita",)


def test_an_anchor_that_already_is_a_person_needs_no_hop(db):
    peak_xv(db)

    assert resolve_people(db, ORG, ["p_harshita"]) == ("p_harshita",)


def test_an_outreach_about_a_service_resolves_to_nobody(db):
    """Two of the pilot's anchors concern a `service`. A service is not somebody we can be
    waiting on, and inventing a person for it would be a counterparty nobody can chase."""
    peak_xv(db)
    node(db, "s_stripe", "stripe", "service")
    node(db, "o_s", "Outreach", "outreach")
    edge(db, "concerns", "o_s", "s_stripe")

    assert resolve_people(db, ORG, ["o_s"]) == ()


def test_the_walk_stops_at_two_hops(db):
    """CC-40's safety property, stated as a bound rather than a hope. `concerns` and
    `corresponded_with` are dense edges; a transitive walk drifts from one situation's
    counterparty to another's, and on a consultant node from one client to another. A person
    three hops out is NOT this anchor's counterparty."""
    peak_xv(db)
    node(db, "o_a", "Outreach", "outreach")
    node(db, "t_a", "Thread A", "thread")
    node(db, "t_far", "Thread B", "thread")
    edge(db, "concerns", "o_a", "t_a")
    edge(db, "concerns", "t_a", "t_far")          # hop three
    edge(db, "corresponded_with", "p_vidushi", "t_far")

    assert "p_vidushi" not in resolve_people(db, ORG, ["o_a"])


def test_no_anchors_is_not_a_query(db):
    """`in ()` is a syntax error, not a zero-row read, and a quiet tenant arrives here empty."""
    peak_xv(db)

    assert resolve_people(db, ORG, []) == ()
    assert find_organizations(db, ORG, anchors=[]) == ()


def test_an_empty_restriction_means_nobody_not_everybody(db):
    """`[]` and `None` are different questions. Collapsing them turns "none of my situations
    reached a person" into "show me every firm I have ever emailed"."""
    peak_xv(db)

    assert find_organizations(db, ORG, restrict_to=[]) == ()
    assert len(find_organizations(db, ORG, restrict_to=None)) == 1


def test_one_silent_contact_of_two_is_not_a_silent_firm(db):
    """The reason `restrict_to` narrows BEFORE grouping instead of filtering after. A firm where
    one of two people has replied is not a firm that has gone quiet, and a card saying so would
    be wrong about the one fact it exists to report."""
    peak_xv(db)

    assert find_organizations(db, ORG, restrict_to=["p_harshita"]) == ()


def test_anchors_and_an_explicit_list_are_combined(db):
    peak_xv(db)
    node(db, "t_v", "Thread with vidushi", "thread")
    edge(db, "corresponded_with", "p_vidushi", "t_v")

    groups = find_organizations(db, ORG, restrict_to=["p_harshita"], anchors=["t_v"])

    assert groups[0].size == 2


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
    """CC-40, at the resolver. A consultant working for two clients exists in both graphs; one
    client's anchor must never resolve into the other's person, and one client's roles must never
    describe the other's relationship."""
    peak_xv(db)
    node(db, "t_h", "Thread", "thread", org=OTHER)
    edge(db, "corresponded_with", "p_harshita", "t_h", org=OTHER)

    assert resolve_people(db, ORG, ["t_h"]) == ()


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
