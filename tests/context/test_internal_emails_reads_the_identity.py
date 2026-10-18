"""STEP-04 · `runner._internal_emails` is the identity's addresses — one answer to who is us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_internal_emails_reads_the_identity.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U01`. `_internal_emails` re-wrote the identity's SQL inline
(seats, `orgs.email`, connected accounts) and never read what a tenant DECLARED
(`org_self_identities`, migration 0193). Ten callers read it — the pipeline's anchor exclusion, its
outbound and inbound facts, the structured lane, the lifecycle, the calendar's actor type, the
document register, the dependency party, the resolution — so a declared address such as
`ceo@thegenios.com`, which only ever receives the founder's own mail, was an outside person to every
one of them. It now returns `platform/self_identity.identity_for(...).addresses`, so a declaration is
seen by all ten at once.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context.runner import _internal_emails
from genios_engine.platform.self_identity import identity_for

pytestmark = pytest.mark.pg
ORG = "internal_emails_identity_org"


@pytest.fixture
def store(pg_store):
    """The production shape: a Gmail founder, a cofounder's seat, a seat that left, a connected
    mailbox, and the two declarations of 06 D6 (an address that only receives, the company domain)."""
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) "
                       "values (:o, :o, 'MrRohitSwerashi@Gmail.com')"), {"o": ORG})
        c.execute(text("insert into org_seats (org_id, seat_id, email, active) values "
                       "(:o, 'seat_owner', 'mrrohitswerashi@gmail.com', true), "
                       "(:o, 'seat_cofounder', 'harsh@thegenios.com', true), "
                       "(:o, 'seat_gone', 'left@oldco.test', false)"), {"o": ORG})
        c.execute(text("insert into connections (connection_id, org_id, external_account_id) "
                       "values ('conn_internal_emails_identity', :o, 'Founder.Mailbox@gmail.com')"),
                  {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', 'ceo@thegenios.com', 'D6'), "
                       "(:o, 'domain', 'thegenios.com', 'D6')"), {"o": ORG})
    yield pg_store
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_a_declared_address_is_us_at_once(store):
    """`ceo@thegenios.com` is neither a seat nor `orgs.email` nor a connected account — only a
    declaration says it is ours, and the old inline SQL never read one."""
    assert "ceo@thegenios.com" in _internal_emails(store, ORG)


def test_the_set_is_the_identitys_addresses(store):
    """Not a second copy of the answer that can drift from it: the same addresses, normalised the
    way person keys are."""
    assert _internal_emails(store, ORG) == identity_for(store, ORG).addresses


def test_a_deactivated_seat_is_not_us(store):
    """Someone who left is a counterparty again — the identity reads active seats only."""
    emails = _internal_emails(store, ORG)
    assert "left@oldco.test" not in emails
    assert "harsh@thegenios.com" in emails and "founder.mailbox@gmail.com" in emails


def test_a_declared_domain_is_not_an_address(store):
    """The set holds addresses. A domain is asked through `SelfIdentity.is_us`, never by finding
    `thegenios.com` in a set of emails."""
    assert "thegenios.com" not in _internal_emails(store, ORG)


def test_the_handle_the_other_callers_pass_still_works(store):
    """`document_register` and `support_situations` hand `_internal_emails` a shim carrying only
    `.engine`. The answer through that handle is the same answer."""

    class _Shim:
        def __init__(self, engine):
            self.engine = engine

    assert _internal_emails(_Shim(store.engine), ORG) == _internal_emails(store, ORG)
