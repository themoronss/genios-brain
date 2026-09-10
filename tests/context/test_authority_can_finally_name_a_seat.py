"""RS-3 — the tenant knew who signs and could not tell them.

    pytest tests/context/test_authority_can_finally_name_a_seat.py -q

`authority_rules` is a real record: approver, delegate, value threshold, source ranking and a
half-open validity window, minted only from span-verified policy documents and refusing to let
an inferred rule bind. It knows Arjun signs anything over ₹50L.

And `approver_node_id` is a GRAPH NODE — deliberately, so the Founder Bottleneck read is a
group-by on a column rather than a string match on a name. Nothing in the engine could turn
one back into a person the delivery layer can reach. `resolve_owner`'s candidate list is
`deal.owner`, `relationship.owner`, `attrs['owner']`, `commitment.owner`, `commitment.actor`,
then the first admin — authority is not on it. So the card reached whoever happened to make
the promise, Arjun was never told a decision was waiting on him, and the account executive who
got it was offered the same action list Arjun would have been.

The system knew the answer and had no way to ask itself the question.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.authority_view import resolve
from genios_engine.contracts.authority import AuthorityRule
from genios_engine.executive.assignment import (
    PgSeatDirectory,
    StaticSeatDirectory,
    resolve_approver_seat,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
ORG = "org1"


@pytest.fixture
def live():
    """A real join, because the weld IS the join."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "canonical_key text, valid_to timestamp)"))
        c.execute(text("create table org_seats (org_id text, seat_id text, email text, "
                       "active boolean, manager_seat_id text)"))
        c.execute(text("insert into graph_nodes values (:o,'n-arjun','person',"
                       "'arjun@acme.test',null)"), {"o": ORG})
        c.execute(text("insert into graph_nodes values (:o,'n-buyer','person',"
                       "'buyer@customer.test',null)"), {"o": ORG})
        c.execute(text("insert into org_seats values (:o,'seat-arjun','arjun@acme.test',1,null)"),
                  {"o": ORG})
        yield PgSeatDirectory(conn=c, org_id=ORG)


def rule(**kw):
    base = {"rule_id": "r1", "subject_type": "contract",
            "threshold_minor_units": 5_000_000, "currency": "INR",
            "approver_node_id": "n-arjun", "source": "admin_declared",
            "evidence_ref": "doc:sop#3", "valid_from": NOW}
    return AuthorityRule(**{**base, **kw})


# =============================================================================================
# The join that was missing.
# =============================================================================================
def test_an_approver_node_finally_resolves_to_a_seat(live):
    assert live.seat_for_node("n-arjun") == "seat-arjun"


def test_a_node_who_is_not_one_of_our_seats_resolves_to_nobody(live):
    """The honest answer, and the one the caller needs: an approver the org does not employ is
    not somebody a card can be routed to, whatever the policy document says."""
    assert live.seat_for_node("n-buyer") is None


def test_no_node_is_nobody(live):
    assert live.seat_for_node(None) is None
    assert live.seat_for_node("") is None


# =============================================================================================
# Only an ENFORCEABLE answer names anybody.
# =============================================================================================
def test_an_enforceable_rule_names_the_seat_that_must_sign(live):
    answer = resolve([rule()], subject_type="contract", evaluated_at=NOW,
                     amount_minor_units=8_000_000, currency="INR")

    assert resolve_approver_seat(answer, directory=live) == "seat-arjun"


def test_a_merely_suggested_approver_names_nobody(live):
    """`suggested` means only OBSERVED BEHAVIOUR matched and a human must confirm before
    anybody signs. Routing a card to one would turn an unconfirmed observation into an
    instruction — the boundary `runtime_brains._validate_axis` raises to protect.

    THE SOURCE IS `inferred`, NOT `discovered`, and my first draft had that wrong.
    `DISCOVERED` is read out of an UPLOADED POLICY DOCUMENT and ranks 8000 — it binds, and
    should. Only `INFERRED` — observed behaviour — is refused, under the contract's own
    sentence: *"a system that infers governance from behaviour and then enforces it has
    invented the governance."*
    """
    answer = resolve([rule(source="inferred")], subject_type="contract", evaluated_at=NOW,
                     amount_minor_units=8_000_000, currency="INR")

    assert answer.enforced is False
    assert resolve_approver_seat(answer, directory=live) is None


def test_a_rule_read_out_of_an_uploaded_policy_DOES_bind(live):
    """The other side of the same line, so the guard cannot drift into refusing everything: a
    span-verified policy document is governance the company wrote, not behaviour we watched."""
    answer = resolve([rule(source="discovered")], subject_type="contract", evaluated_at=NOW,
                     amount_minor_units=8_000_000, currency="INR")

    assert resolve_approver_seat(answer, directory=live) == "seat-arjun"


def test_no_rule_at_all_names_nobody(live):
    """`no_authority_rule` is NOT "anyone may approve"."""
    answer = resolve([], subject_type="contract", evaluated_at=NOW,
                     amount_minor_units=8_000_000, currency="INR")

    assert resolve_approver_seat(answer, directory=live) is None


def test_under_the_bar_names_nobody(live):
    answer = resolve([rule()], subject_type="contract", evaluated_at=NOW,
                     amount_minor_units=1_000_000, currency="INR")

    assert resolve_approver_seat(answer, directory=live) is None


def test_none_in_none_out(live):
    assert resolve_approver_seat(None, directory=live) is None


# =============================================================================================
# The property name, which a getattr default would have hidden.
# =============================================================================================
def test_the_guard_reads_a_property_that_exists():
    """A BUG THIS CAUGHT. My first draft read `answer.enforceable`, which does not exist — the
    property is `enforced`, and its own docstring says to read it and never `rule is not None`.
    Behind a `getattr(..., False)` default that would have been False on EVERY answer: a guard
    that never fires and never says so."""
    from genios_engine.context.authority_view import AuthorityAnswer

    assert hasattr(AuthorityAnswer, "enforced")
    assert not hasattr(AuthorityAnswer, "enforceable")


def test_the_in_memory_directory_answers_the_same_question():
    directory = StaticSeatDirectory(seats={
        "seat-arjun": {"email": "arjun@acme.test", "active": True, "node_id": "n-arjun"},
        "seat-gone": {"email": "x@acme.test", "active": False, "node_id": "n-gone"},
    })

    assert directory.seat_for_node("n-arjun") == "seat-arjun"
    assert directory.seat_for_node("n-gone") is None, "an inactive seat is not a recipient"
    assert directory.seat_for_node("n-unknown") is None
