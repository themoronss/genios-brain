"""A promise somebody else made is not our overdue commitment, and must not be a card at all.

WHAT NAMING THE OWNER FIXED, AND WHAT IT DID NOT. `test_commitment_owner.py` made the card say
WHOSE promise it is, which stopped the sentence being a lie. It did not stop the card existing:
`read_overdue_commitments` emits a finding for every commitment whose own stated date has passed
and never asks whether the promise points at us. Its docstring says "one finding per promise of
ours" — an assumption the code never checked.

Measured on the pilot, 9 Sep 2026. Fifteen cards reached the founder. SIX of them were somebody
else's obligation rendered as his:

    "Deliver fundraising opportunities to sanchiconnect.tech NOW"   critical, the top card
    "Deliver fundraising opportunities to healthcare leaders"       the same email again
    "Deliver six months free Growth plan access now"                Composio offered HIM this
    "Renew Growth plan at $599/month now"                           a vendor's renewal clause
    "Deliver $2,000 monthly savings to myzyner.com"                 Myzyner promised HIM this
    "Deliver $2,000 monthly savings now"                            the same one again

Of fifteen commitment nodes, twelve carry an `owns` edge and only THREE are owned by the mailbox
owner. Nine belong to counterparties, and naming them changed the copy while leaving the feed
inverted: the loudest card in the product was an incubator's marketing promise, at critical
urgency, in the founder's voice.

THE RULE, AND ITS DELIBERATE LIMIT. A commitment is refused only when the graph can positively
say it belongs to somebody else — an owner we know, and a mailbox owner to compare it against.
An unknown owner still produces a finding, because "we cannot tell whose this is" is not evidence
that it is not ours, and this reading has never been allowed to infer an owner from silence. That
is the same discipline `_mailbox_owner` already keeps for a tenant with two sending seats.
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from genios_engine.context.outreach_situations import (  # noqa: E402
    read_overdue_commitments,
)

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
OVERDUE = (NOW - timedelta(days=6)).isoformat()
US = "mrrohitswerashi@gmail.com"


def _rows(*, owner_key=None, owner_name=None, mailbox_owner=US, **over) -> dict:
    row = {"commitment.due_at": OVERDUE, "commitment.action": "provide fundraising opportunities",
           "_name": "sanchiconnect.tech"}
    if owner_key:
        row["_owner_key"] = owner_key
    if owner_name:
        row["_owner_name"] = owner_name
    row.update(over)
    rows = {"cmt_1": row}
    if mailbox_owner is not None:
        rows["_mailbox_owner"] = mailbox_owner
    return rows


def test_a_counterpartys_promise_produces_no_finding_at_all():
    """The top card on the pilot. SanchiConnect promised the founder access at their event."""
    assert read_overdue_commitments(
        _rows(owner_key="sunil.s@sanchiconnect.tech", owner_name="Sunil"), NOW, {}) == []


def test_a_vendors_renewal_clause_produces_no_finding():
    assert read_overdue_commitments(
        _rows(owner_key="billing@composio.dev", owner_name="Composio"), NOW, {}) == []


def test_our_own_promise_still_produces_its_finding():
    """The half that must not move: a promise we really made is still overdue and still a card."""
    [finding] = read_overdue_commitments(
        _rows(owner_key=US, owner_name="Rohit Swerashi"), NOW, {})
    facts = {name: value for name, value, _kind in finding.facts}
    assert facts["commitment.owner_key"] == US


def test_the_comparison_ignores_case_and_whitespace():
    """An address is the same address however the graph happened to store it."""
    assert read_overdue_commitments(
        _rows(owner_key=f"  {US.upper()} ", owner_name="Rohit"), NOW, {}) != []


def test_an_unknown_owner_is_not_treated_as_somebody_elses():
    """Absent stays absent. We cannot prove it is not ours, so it is still shown."""
    assert read_overdue_commitments(_rows(), NOW, {}) != []


def test_a_tenant_with_no_single_sending_seat_refuses_nothing():
    """`_mailbox_owner` returns None for both "no outbound observed" and "several seats", and
    neither is a basis for deciding somebody else owns a promise."""
    assert read_overdue_commitments(
        _rows(owner_key="sunil.s@sanchiconnect.tech", mailbox_owner=None), NOW, {}) != []
