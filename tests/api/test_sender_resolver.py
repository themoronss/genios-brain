"""M1.C1.L-logic.V0.U06 · `sender_known` must mean "we have corresponded", not "we have seen".

    pytest tests/api/test_sender_resolver.py -q

THE REGRESSION THIS PINS. The pilot tenant's feed returned nine cards and eight were marketing:
a mentorship pitch, a course newsletter, a community blast, a cold outreach from a real person's
address. None of them were caught by the bulk-header rule even though every one of them carried
`List-Unsubscribe`, and the rule is implemented, tested and correct.

The reason is a chain, and the last link is here. `esqe/relevance._rule_verdict` asks
`sender_known` FIRST and returns RULE_KNOWN_COUNTERPARTY at 9000 bp, so `_has_bulk_headers` two
lines below is unreachable for anyone `sender_known` is true for. That ordering is deliberate and
right — `test_the_cascade_order_is_the_one_the_plan_fixed` protects it, because a counterparty we
genuinely deal with should not be dropped for sending through Mailchimp.

What was wrong was the INPUT. `sender_known` was "this address is any person node", and a stranger
becomes a person node by writing at us once. So the cascade was told a stranger was a counterparty
and behaved impeccably on a false premise.

These tests run the REAL query (`routes.KNOWN_COUNTERPARTY_SQL`) against a real database rather
than asserting about a string, because the defect being fixed was in what the SQL selects.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.api.routes import KNOWN_COUNTERPARTY_SQL, known_counterparty_keys

ORG = "org_pilot"


@pytest.fixture()
def db():
    """Minimal graph, the two tables the rule reads. `value`/`jsonb` are untouched by the query,
    so text columns are faithful enough and keep the fixture readable."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table graph_nodes (node_id text, org_id text, node_type text, "
            "canonical_key text, valid_to timestamp)"))
        c.execute(text(
            "create table graph_facts (fact_version_id text, org_id text, subject_node_id text, "
            "field text, status text)"))
    with engine.begin() as c:
        yield c


def _person(c, node_id: str, email: str, *, valid_to=None) -> None:
    c.execute(text("insert into graph_nodes values (:n, :o, 'person', :k, :v)"),
              {"n": node_id, "o": ORG, "k": email, "v": valid_to})


def _we_wrote_to(c, node_id: str, *, status: str = "active") -> None:
    """The outbound leg writes `thread.last_outbound` onto the RECIPIENT's person node."""
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_outbound', :s)"),
              {"f": f"fv_{node_id}", "o": ORG, "n": node_id, "s": status})


def _they_wrote_to_us(c, node_id: str) -> None:
    """Inbound only. This is what every one of the eight marketing senders had, and all they had."""
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_inbound', 'active')"),
              {"f": f"fv_in_{node_id}", "o": ORG, "n": node_id})


# =============================================================================================
# The rule.
# =============================================================================================
def test_a_person_we_have_written_to_is_a_known_counterparty(db):
    _person(db, "n1", "maya@acme.ai")
    _we_wrote_to(db, "n1")

    assert known_counterparty_keys(db, ORG) == {"maya@acme.ai"}


def test_a_person_who_has_only_ever_written_at_us_is_not(db):
    """The whole defect in one assertion. Before this change the address below came back known,
    which handed its next newsletter 9000 bp and put the bulk rule out of reach."""
    _person(db, "n2", "stranger@unknown-vendor.com")
    _they_wrote_to_us(db, "n2")

    assert known_counterparty_keys(db, ORG) == frozenset()


def test_a_person_node_with_no_correspondence_at_all_is_not(db):
    """A node minted by a mention, an attendee list, or a fail-open budget-guard pass. Existing
    is not corresponding."""
    _person(db, "n3", "someone@somewhere.com")

    assert known_counterparty_keys(db, ORG) == frozenset()


@pytest.mark.parametrize("email", [
    "hello@sanctuaryconnect.tech",     # community / event blast
    "mentors@expertmentorship.example",  # mentorship pitch
    "sahan@sanjula.example",           # cold outreach from a human-looking address
    "lora@loralessons.example",        # course marketing
])
def test_the_four_senders_that_produced_the_pilots_bad_cards_are_not_counterparties(db, email):
    """Named rather than described. Each one wrote at this tenant and was never written back to,
    and each one produced a card. All four must now fall through to the bulk-header rule."""
    _person(db, f"n_{email}", email)
    _they_wrote_to_us(db, f"n_{email}")

    assert email not in known_counterparty_keys(db, ORG)


# =============================================================================================
# The edges that would make the rule wrong in the other direction.
# =============================================================================================
def test_a_superseded_outbound_does_not_count(db):
    """`write_fact` supersedes rather than updates, so requiring `status='active'` is what keeps
    this from being true forever once it has been true once. If no active row remains, we have no
    current evidence we ever wrote."""
    _person(db, "n4", "old@vendor.com")
    _we_wrote_to(db, "n4", status="superseded")

    assert known_counterparty_keys(db, ORG) == frozenset()


def test_a_retired_node_is_excluded(db):
    _person(db, "n5", "departed@acme.ai", valid_to="2026-01-01")
    _we_wrote_to(db, "n5")

    assert known_counterparty_keys(db, ORG) == frozenset()


def test_another_orgs_correspondence_is_never_visible(db):
    """Tenancy. The query filters org on BOTH tables; dropping either half leaks."""
    _person(db, "n6", "maya@acme.ai")
    db.execute(text("insert into graph_facts values ('fv_x', 'org_other', 'n6', "
                    "'thread.last_outbound', 'active')"))

    assert known_counterparty_keys(db, ORG) == frozenset()


def test_keys_are_lowercased_so_the_membership_test_cannot_miss_on_case(db):
    """The caller lowercases the incoming sender; if this side did not, `Maya@Acme.ai` in the
    graph would never match and a real counterparty would silently become a stranger."""
    _person(db, "n7", "Maya@Acme.AI")
    _we_wrote_to(db, "n7")

    assert known_counterparty_keys(db, ORG) == {"maya@acme.ai"}


def test_the_query_reads_both_tables(db):
    """A guard on the shape of the fix, not its behaviour: if a later edit reverts this to a
    plain `graph_nodes` scan, every test above still passes on a fixture that happens to have
    correspondence, and only this one fails."""
    assert "graph_facts" in KNOWN_COUNTERPARTY_SQL
    assert "thread.last_outbound" in KNOWN_COUNTERPARTY_SQL
