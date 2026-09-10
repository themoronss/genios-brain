"""AUTH-2 and PP-1 — two ways the engine named the wrong required approver.

    pytest tests/context/test_an_authority_bound_that_failed_open.py -q

AUTH-2, AND IT FAILED OPEN. `authority_rules` carries two kinds of bound: money
(`threshold_minor_units`) and RATIO (`threshold_basis_points`) — 1500 basis points is "a
discount above 15% needs the founder", and the contract keeps them as separate fields
precisely because *"1500 minor units and 1500 basis points are the same integer meaning
nothing alike."* The store's INSERT, SELECT and `row_to_rule` all omitted the ratio column, so
a ratio rule round-tripped as an UNBOUNDED one and `covers_amount` returned True for every
subject. A 2% goodwill discount named the founder as its required approver, and the Founder
Bottleneck read counted them as sole approver of the whole discount class. The mirror case is
worse: declaring the rule through the API stored NULL in both columns, so the database itself
then held an unbounded founder-approval rule with no record that a 15% bound was ever asked
for.

PP-1, AND IT BOUND A STRANGER. `resolve_approver_node` resolves a policy's "Arjun" through
three rungs. The middle rung is an OBSERVED person-name alias, written from ordinary mail — and
ordinary mail is mostly with people who do not work here. On a 12-person company whose only
Arjun is `arjun@bigcustomer.com`, a buyer at their largest account, the policy "contracts above
$50,000 require approval from Arjun" bound an EXTERNAL BUYER as the tenant's enforceable
approver, and the console showed the reviewer a sentence that was word-for-word correct.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.authority_view import _ranked, covers_amount, resolve
from genios_engine.contracts.authority import AuthorityRule
from genios_engine.packs.brains.org_discovery import resolve_approver_node

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
ORG = "org1"


def rule(**kw):
    base = {"rule_id": "r1", "subject_type": "discount", "approver_node_id": "n-founder",
            "source": "admin_declared", "evidence_ref": "doc:1", "valid_from": NOW}
    return AuthorityRule(**{**base, **kw})


# =============================================================================================
# AUTH-2 — the ratio bound.
# =============================================================================================
def test_a_small_discount_no_longer_needs_the_founder():
    """THE FAILURE, in one assertion. The rule says 15%; the discount is 2%."""
    assert covers_amount(rule(threshold_basis_points=1500), None, None, ratio_bp=200) is False


def test_a_large_discount_still_does():
    assert covers_amount(rule(threshold_basis_points=1500), None, None, ratio_bp=2000) is True


def test_a_ratio_rule_does_not_cover_a_subject_with_no_ratio():
    """Symmetric with the money arm, which already refuses an amountless subject: the bound is
    the whole content of the rule, and applying it to something it cannot measure is a
    confidently named wrong approver."""
    assert covers_amount(rule(threshold_basis_points=1500), None, None) is False


def test_the_boundary_is_ABOVE_not_at():
    """"A discount above 15%" is what the policy says."""
    r = rule(threshold_basis_points=1500)

    assert covers_amount(r, None, None, ratio_bp=1500) is False
    assert covers_amount(r, None, None, ratio_bp=1501) is True


def test_a_money_rule_is_untouched():
    r = rule(subject_type="contract", threshold_minor_units=5_000_000, currency="INR")

    assert covers_amount(r, 8_000_000, "INR") is True
    assert covers_amount(r, 1_000_000, "INR") is False
    assert covers_amount(r, 8_000_000, "USD") is False, "no conversion, ever"


def test_an_unbounded_rule_still_covers_everything():
    assert covers_amount(rule(), None, None) is True
    assert covers_amount(rule(), 999, "INR") is True


def test_a_ratio_bound_is_not_ranked_as_unbounded():
    """Sharing `_ANY_VALUE_RANK` said "any discount" and "a discount above 15%" were equally
    specific, so the tie fell to `valid_from`."""
    tight = rule(rule_id="tight", threshold_basis_points=1500, valid_from=NOW - timedelta(days=9))
    loose = rule(rule_id="loose")

    assert _ranked([loose, tight])[0].rule_id == "tight"


def test_resolve_threads_the_ratio_through():
    answer = resolve([rule(threshold_basis_points=1500)], subject_type="discount",
                     evaluated_at=NOW, ratio_bp=200)

    assert answer.approver_node_id is None, "a 2% discount matches no rule"


def test_the_store_carries_the_column_both_ways():
    """The round trip is the defect: the column existed on the table and in the contract, and
    the INSERT, the SELECT and `row_to_rule` all dropped it."""
    from genios_engine.context import authority_view as av

    assert "threshold_basis_points" in av._INSERT
    assert "threshold_basis_points" in av._SELECT
    assert "threshold_basis_points=(None if getattr(row" in \
        __import__("inspect").getsource(av.row_to_rule)


# =============================================================================================
# PP-1 — the approver who does not work here.
# =============================================================================================
@pytest.fixture
def graph():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "canonical_key text, display_name text, valid_to timestamp)"))
        c.execute(text("create table graph_aliases (org_id text, alias_type text, "
                       "alias_key text, node_id text)"))
        c.execute(text("create table org_seats (org_id text, email text, active boolean)"))
        c.execute(text("create table orgs (id text, email text)"))
        c.execute(text("create table connections (org_id text, external_account_id text)"))
        for node, email in (("n-buyer", "arjun@bigcustomer.com"),
                            ("n-staff", "arjun@acme.test")):
            c.execute(text("insert into graph_nodes values (:o, :n, 'person', :e, 'Arjun', null)"),
                      {"o": ORG, "n": node, "e": email})
        c.execute(text("insert into orgs values (:o, 'maya@acme.test')"), {"o": ORG})
        c.execute(text("insert into org_seats values (:o, 'arjun@acme.test', 1)"), {"o": ORG})
        yield c


def name_alias(conn, node_id, name="arjun"):
    conn.execute(text("delete from graph_aliases where org_id=:o"), {"o": ORG})
    conn.execute(text("insert into graph_aliases values (:o, 'person_name', :k, :n)"),
                 {"o": ORG, "k": name, "n": node_id})


def test_a_buyer_at_a_customer_is_not_bound_as_our_approver(graph):
    """THE WHOLE POINT. The only Arjun the mailbox has seen works for the customer."""
    name_alias(graph, "n-buyer")

    assert resolve_approver_node(graph, org_id=ORG, name="Arjun") is None


def test_our_own_arjun_still_resolves(graph):
    """The guard may not become "never resolve a name" — that would send every policy to human
    review and make the whole discovery lane pointless."""
    name_alias(graph, "n-staff")

    assert resolve_approver_node(graph, org_id=ORG, name="Arjun") == "n-staff"


def test_refusing_leaves_the_name_for_a_human(graph):
    """`authority_pending` IS `approver_node_id is None`, so None is a route to review with the
    name intact — not a lost rule."""
    name_alias(graph, "n-buyer")

    assert resolve_approver_node(graph, org_id=ORG, name="Arjun") is None


def test_an_unreadable_directory_does_not_bind(graph):
    """FAILS CLOSED. An unreadable directory is a deployment problem; granting an approval
    right on the strength of one is not recoverable."""
    name_alias(graph, "n-staff")
    graph.execute(text("drop table org_seats"))

    assert resolve_approver_node(graph, org_id=ORG, name="Arjun") is None


def test_a_blank_name_is_still_nobody(graph):
    assert resolve_approver_node(graph, org_id=ORG, name="   ") is None
