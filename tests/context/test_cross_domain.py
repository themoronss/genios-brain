"""CC-31…CC-36 · Cross Domain — two domains reasoning about one subject, and disagreeing.

    pytest tests/context/test_cross_domain.py -q

THE LAST OF EIGHT. With this the architecture's eight named correlators all exist: Cross Tool and
Cross User in `correlation.py`, then Resource, Timeline, Dependency, Conversation, Organization
and now Domain.

MEASURED READ-ONLY ON THE PILOT BEFORE A LINE OF THIS WAS WRITTEN. Every situation resolved to the
person behind it — anchor, or one hop through `corresponded_with`, or one through `concerns`:

    people reached by at least one situation            43
    people carrying more than one situation TYPE         4
      x3   admin:awaiting_response  +  support:first_response_overdue

That is not overlap. `awaiting_response` says THEY OWE US A REPLY; `first_response_overdue` says
WE NEVER ANSWERED THEM. Both cannot be true of one counterparty at one time. On all three —
Boardy, Crescere Labs, IIM-A — `thread.ball_in_court` reads `them`, so admin is right and support
is wrong, and nothing in the system noticed. Two cards would have gone out telling the founder
opposite things about the same person.

Seventeen nodes carry situations in more than one domain at the anchor level and almost all of it
is harmless: `nsrcel.iimb.ac.in` is an investor relationship, a general relationship and a sales
opportunity at once, which is three true readings of one accelerator. Overlap is normal. Only a
DECLARED impossibility is a finding, and the tests below pin that distinction hardest.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.correlation_domain import (
    EXCLUSIONS,
    Exclusion,
    arbiter_fields,
    find_contradictions,
    read_contradictions,
)

pytestmark = pytest.mark.unit

ORG = "org_pilot"
OTHER = "org_other"

AWAITING = "admin:awaiting_response"
OVERDUE = "support:first_response_overdue"
DIRECTION = EXCLUSIONS[0]


def situation(person: str, key: str, sid: str | None = None) -> dict:
    domain, stype = key.split(":", 1)
    return {"situation_id": sid or f"sit_{person}_{stype}", "domain": domain,
            "situation_type": stype, "person": person}


def contradictions(rows, ball: str | None = "them", **kw):
    arbiters = {} if ball is None else {"p_boardy": {"thread.ball_in_court": ball}}
    return find_contradictions(rows, arbiters, {"p_boardy": "boardy@boardy.ai"}, **kw)


BOTH = [situation("p_boardy", AWAITING), situation("p_boardy", OVERDUE)]


# =============================================================================================
# The contradiction nobody was checking for.
# =============================================================================================
def test_they_owe_us_and_we_owe_them_cannot_both_be_true():
    [found] = contradictions(BOTH)

    assert found.subject == "boardy@boardy.ai"
    assert found.exclusion.pair == frozenset((AWAITING, OVERDUE))


def test_the_arbiter_settles_it_and_names_a_loser():
    """`thread.ball_in_court` is the fact BOTH readings derive from — `waiting.py` computes it
    from the message timeline and the two situations are two readings of it that drifted. So it
    is not a tiebreak invented here; it is the shared source they disagreed about."""
    [found] = contradictions(BOTH, ball="them")

    assert found.resolved
    assert found.winner == AWAITING
    assert found.loser == OVERDUE


def test_the_arbiter_can_settle_it_the_other_way():
    """The rule may not be a way for one domain to always win."""
    [found] = contradictions(BOTH, ball="us")

    assert found.winner == OVERDUE
    assert found.loser == AWAITING


def test_an_absent_arbiter_leaves_it_unresolved_rather_than_guessed():
    """A coin toss between two domains is worse than telling a reviewer the system cannot tell —
    and the caller acts on it differently: an unresolved contradiction holds BOTH sides."""
    [found] = contradictions(BOTH, ball=None)

    assert not found.resolved
    assert found.winner is None and found.loser is None


def test_an_arbiter_value_nobody_declared_does_not_pick_a_side():
    """`thread.ball_in_court` could hold something neither branch names. Falling through to a
    default would be the guess this refuses everywhere else."""
    [found] = contradictions(BOTH, ball="nobody")

    assert not found.resolved


def test_both_sides_are_carried_so_a_caller_can_hold_either():
    [found] = contradictions(BOTH)

    assert dict(found.sides)[AWAITING] == "sit_p_boardy_awaiting_response"
    assert dict(found.sides)[OVERDUE] == "sit_p_boardy_first_response_overdue"


# =============================================================================================
# Overlap is not contradiction, and this is the distinction the module exists to hold.
# =============================================================================================
def test_three_true_readings_of_one_accelerator_are_not_a_finding():
    """`nsrcel.iimb.ac.in` on the live tenant: an investor relationship, a general relationship
    and a sales opportunity at once. All three are true. A similarity score would have flagged
    this and been undebuggable; a declared list does not."""
    rows = [situation("p_n", "fundraising:investor_relationship"),
            situation("p_n", "general:relationship"),
            situation("p_n", "sales:opportunity")]

    assert find_contradictions(rows) == ()


def test_one_situation_alone_contradicts_nothing():
    assert find_contradictions([situation("p_boardy", AWAITING)]) == ()


def test_the_two_halves_on_different_people_are_two_ordinary_situations():
    """The pair is only impossible about ONE subject. Two different counterparties, one of whom
    owes us and one of whom we owe, is a perfectly ordinary Tuesday."""
    rows = [situation("p_a", AWAITING), situation("p_b", OVERDUE)]

    assert find_contradictions(rows) == ()


def test_the_same_claim_twice_is_not_a_contradiction_with_itself():
    """Two `awaiting_response` rows on one person — the outreach anchor and the thread anchor
    resolving to the same party — must not read as a subject disagreeing with itself."""
    rows = [situation("p_a", AWAITING, "sit_1"), situation("p_a", AWAITING, "sit_2")]

    assert find_contradictions(rows) == ()


def test_nothing_declared_finds_nothing():
    """The mechanism is the declaration. With no pairs there is no detector left over."""
    assert find_contradictions(BOTH, exclusions=()) == ()


# =============================================================================================
# The declarations themselves.
# =============================================================================================
def test_every_declared_pair_says_why():
    """A pair a reviewer cannot argue with is a rule nobody can remove. `because` is not
    decoration — it is the whole justification for suppressing a domain's work."""
    for exclusion in EXCLUSIONS:
        assert exclusion.because.strip()
        assert exclusion.left != exclusion.right


def test_every_declared_pair_names_a_domain_on_both_sides():
    for exclusion in EXCLUSIONS:
        for key in (exclusion.left, exclusion.right):
            domain, _, stype = key.partition(":")
            assert domain and stype, key


def test_an_arbiter_that_favours_a_type_outside_its_own_pair_is_a_bug():
    """A `favours` map pointing at a third type would silently make every finding unresolved —
    `winner` would return a value `loser` cannot subtract from the pair."""
    for exclusion in EXCLUSIONS:
        for favoured in (exclusion.favours or {}).values():
            assert favoured in exclusion.pair, exclusion


def test_a_pair_with_no_arbiter_is_allowed_and_answers_unresolved():
    """Not every impossibility has a fact that settles it, and refusing to declare those would
    leave the contradiction undetected — which is strictly worse than detecting it unresolved."""
    silent = Exclusion(left="a:one", right="b:two", because="they cannot both hold")
    rows = [situation("p_x", "a:one"), situation("p_x", "b:two")]

    [found] = find_contradictions(rows, exclusions=(silent,))

    assert not found.resolved


def test_the_arbiter_fields_are_derived_from_the_declarations():
    """The bulk read asks for exactly the facts the declared pairs need. Hard-coding the list
    would make adding a pair a two-file edit, and the second file is the one people forget."""
    assert arbiter_fields() == ("thread.ball_in_court",)
    assert arbiter_fields((Exclusion("a:one", "b:two", "because"),)) == ()


# =============================================================================================
# Against a database — the resolution the live run exercised.
# =============================================================================================
@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in (
            "create table context_situations (situation_id text, org_id text, domain text, "
            "situation_type text, anchor_node_id text, status text)",
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


def sit(c, sid: str, key: str, anchor: str, *, org: str = ORG, status: str = "active") -> None:
    domain, stype = key.split(":", 1)
    c.execute(text("insert into context_situations values (:s,:o,:d,:t,:a,:st)"),
              {"s": sid, "o": org, "d": domain, "t": stype, "a": anchor, "st": status})


def node(c, node_id: str, name: str, node_type: str = "person", *, org: str = ORG) -> None:
    c.execute(text("insert into graph_nodes values (:n,:o,:t,:k,:k,null)"),
              {"n": node_id, "o": org, "t": node_type, "k": name})


def fact(c, node_id: str, field: str, value: str, *, org: str = ORG) -> None:
    c.execute(text("insert into graph_facts values (:f,:o,:n,:fd,:v,'active',null)"),
              {"f": f"fv_{node_id}_{field}", "o": org, "n": node_id, "fd": field, "v": value})


def boardy(c, *, ball: str | None = "them", org: str = ORG) -> None:
    """The live shape: an OUTREACH anchor concerning a thread, and a THREAD anchor, both resolving
    to one person. Neither anchor is the person — that is what made this invisible."""
    node(c, "p_b", "boardy@boardy.ai", org=org)
    node(c, "t_b", "Thread with Boardy", "thread", org=org)
    node(c, "o_b", "Outreach to Boardy", "outreach", org=org)
    c.execute(text("insert into graph_edges values (:o,'corresponded_with','p_b','t_b',null)"),
              {"o": org})
    c.execute(text("insert into graph_edges values (:o,'concerns','o_b','t_b',null)"), {"o": org})
    sit(c, "sit_await", AWAITING, "o_b", org=org)
    sit(c, "sit_overdue", OVERDUE, "t_b", org=org)
    if ball is not None:
        fact(c, "p_b", "thread.ball_in_court", ball, org=org)


def test_two_anchors_that_are_not_people_still_resolve_to_one_subject(db):
    """The reason this was invisible. 41 `awaiting_response` anchors are `outreach` nodes and 41
    `first_response_overdue` anchors are `thread` nodes on the pilot; not one is a person, so a
    naive group-by-anchor sees two unrelated rows."""
    boardy(db)

    [found] = read_contradictions(db, ORG)

    assert found.subject == "boardy@boardy.ai"
    assert found.winner == AWAITING


def test_a_dormant_claim_cannot_contradict_a_live_one(db):
    """A dormant situation has stopped making its claim, and two claims cannot contradict when
    only one is still being made."""
    boardy(db)
    db.execute(text("update context_situations set status='dormant' "
                    "where situation_id='sit_overdue'"))

    assert read_contradictions(db, ORG) == ()


def test_a_resolved_claim_is_not_a_contradiction(db):
    boardy(db)
    db.execute(text("update context_situations set status='resolved' "
                    "where situation_id='sit_await'"))

    assert read_contradictions(db, ORG) == ()


def test_the_status_filter_matches_a_value_the_column_actually_holds(db):
    """THE DEFECT THE LIVE RUN CAUGHT. The first cut filtered on `status = 'open'`. There is no
    such status — the column holds `active` / `dormant` / `resolved`, 183 / 47 / 2 on the pilot —
    so the read matched nothing and the module reported a CLEAN TENANT while three live
    contradictions sat in the table. A filter on a value a column never holds is
    indistinguishable from a healthy result."""
    boardy(db)

    assert len(read_contradictions(db, ORG)) == 1


def test_another_tenants_situations_never_contradict_this_ones(db):
    boardy(db, org=OTHER)

    assert read_contradictions(db, ORG) == ()
    assert len(read_contradictions(db, OTHER)) == 1


def test_an_arbiter_fact_from_another_tenant_does_not_settle_this_one(db):
    boardy(db, ball=None)
    fact(db, "p_b", "thread.ball_in_court", "them", org=OTHER)

    [found] = read_contradictions(db, ORG)

    assert not found.resolved


def test_a_quiet_tenant_is_not_an_error(db):
    assert read_contradictions(db, ORG) == ()
