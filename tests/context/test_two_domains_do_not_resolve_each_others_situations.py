"""One anchor claimed by two domains would have resolved both domains' cards, every sweep.

    pytest tests/context/test_two_domains_do_not_resolve_each_others_situations.py -q

`_reconcile` closes the situations a sweep no longer produces, as RESOLVED BY FACT — which is
right, and is what lets an aging item close itself when its loop closes. Its caller runs it once
per domain:

    for domain, live in minted.items():
        _reconcile(c, stype=spec_for(domain).type_for(anchor), live=live, now=now)

so `live` holds only the ids this domain minted, each ending `_{domain}`. The SELECT it compared
them against read every row of that `situation_type` in the org, with no domain in the WHERE. A
`situation_type` is shared by every domain whose spec maps the anchor to the same name, so
reconciling `admin` read `customer_support`'s rows, found none of them in admin's live set, and
resolved them — then support's pass did the same to admin's. Two domains claiming one anchor
annihilate each other every sweep, by fact, with nothing in the log.

IT HAS NEVER FIRED, AND THAT IS NOT A REASON TO LEAVE IT. Checked on the design-partner tenant
2026-09-16: no `situation_type` there is claimed by more than one domain, so every reconcile has
been accidentally correct. `context/domain_spec.domains_declaring` exists precisely so that an
anchor CAN be claimed by several, and the first tenant to use that would have found this as
cards that resolved themselves overnight.

Three writers share this shape — `support_situations`, `outreach_situations` (which imports the
support copy) and `document_register` (its own copy). All three are exercised below, because a
fix in two of three is the half-landed change this codebase keeps finding.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.document_register import _reconcile as reconcile_documents
from genios_engine.context.support_situations import _reconcile as reconcile_support

pytestmark = pytest.mark.unit

ORG = "org1"
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table context_situations (org_id text, correlation_id text, "
            "situation_type text, domain text, status text, resolved_by text, "
            "resolved_at timestamp, computed_at timestamp, "
            "primary key (org_id, correlation_id))"))
        for domain in ("admin", "customer_support"):
            c.execute(text(
                "insert into context_situations (org_id, correlation_id, situation_type, "
                "domain, status) values (:o, :c, 'commitment_overdue', :d, 'active')"),
                {"o": ORG, "c": f"commitment:n1_{domain}", "d": domain})
        yield c


def status(conn, correlation_id):
    return conn.execute(text(
        "select status from context_situations where org_id=:o and correlation_id=:c"),
        {"o": ORG, "c": correlation_id}).scalar()


@pytest.mark.parametrize("reconcile", [reconcile_support, reconcile_documents],
                         ids=["support_and_outreach", "document_register"])
def test_reconciling_one_domain_leaves_the_others_rows_alone(conn, reconcile) -> None:
    """THE DEFECT. Admin's sweep produced its own situation and nothing of support's."""
    reconcile(conn, org_id=ORG, stype="commitment_overdue", domain="admin",
              live={"commitment:n1_admin"}, now=NOW)

    assert status(conn, "commitment:n1_admin") == "active"
    assert status(conn, "commitment:n1_customer_support") == "active", (
        "admin's reconcile resolved customer_support's situation — the two domains "
        "annihilate each other every sweep")


@pytest.mark.parametrize("reconcile", [reconcile_support, reconcile_documents],
                         ids=["support_and_outreach", "document_register"])
def test_a_row_this_domain_stopped_producing_is_still_closed(conn, reconcile) -> None:
    """The property that must survive the fix. Scoping by domain must not stop a domain closing
    its OWN stale rows — that would trade a silent over-resolve for a situation that never ends."""
    reconcile(conn, org_id=ORG, stype="commitment_overdue", domain="admin",
              live=set(), now=NOW)

    assert status(conn, "commitment:n1_admin") == "resolved"
    assert status(conn, "commitment:n1_customer_support") == "active"


@pytest.mark.parametrize("reconcile", [reconcile_support, reconcile_documents],
                         ids=["support_and_outreach", "document_register"])
def test_a_different_situation_type_is_never_touched(conn, reconcile) -> None:
    """The scoping that was already correct, kept under test so the new clause cannot replace it."""
    conn.execute(text(
        "insert into context_situations (org_id, correlation_id, situation_type, domain, status) "
        "values (:o, 'outreach:n9_admin', 'awaiting_response', 'admin', 'active')"), {"o": ORG})

    reconcile(conn, org_id=ORG, stype="commitment_overdue", domain="admin",
              live=set(), now=NOW)

    assert status(conn, "outreach:n9_admin") == "active"
