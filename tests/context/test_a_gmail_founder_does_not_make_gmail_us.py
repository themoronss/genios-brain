"""⛔ STEP-04 · a Gmail founder does not make every gmail.com sender one of us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_gmail_founder_does_not_make_gmail_us.py -q

`context/support_situations._internal` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U10`). The support
lane added the DOMAIN of `orgs.email` to who we are, with no exception for public mail. The design
partner's founder signed up with a Gmail address, so `gmail.com` became "ours": every customer
writing from Gmail read as a colleague, their request as already answered by us, and the
first-response clock never started for any of them.

The domain half is now the DECLARED domains only (`platform/self_identity`, which refuses a public
mail domain): the founder's exact address is ours, another gmail.com address is not, and an address
at the company domain the tenant declared is.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.support_situations import (
    ResponsePolicy,
    gather,
    refresh_support_situations,
)

pytestmark = pytest.mark.pg

ORG = "gmail_founder_org"
NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
#: `orgs.email` is UNIQUE, so this file's founder has an address no other test file inserts.
FOUNDER = "founder.support.desk@gmail.com"
CUSTOMER = "asha.customer@gmail.com"          # another Gmail address — a customer, not us
COLLEAGUE = "harsh@thegenios.com"              # not a seat, not declared — at the declared domain


@pytest.fixture
def store(pg_store):
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'Founder.Support.Desk@gmail.com')"),
                  {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'domain', 'thegenios.com', 'test')"), {"o": ORG})
        # The founder's own connected mailbox. `composio_user_id` as every production writer
        # sets it (see `tests/test_support_situations_persistence._seed_connection`).
        c.execute(text("insert into connections (connection_id, org_id, external_account_id, "
                       "  composio_user_id, status) values ('conn_gmail_founder', :o, :a, "
                       "  'cu_gmail_founder', 'connected')"), {"o": ORG, "a": FOUNDER})
    yield pg_store
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})       # cascades


def _message(c, n: int, thread: str, sender: str, at: datetime, body: str = "") -> None:
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "  source_object_id, parent_object_id, dedup_key, actor, occurred_at, recipients) "
        "values (:e, :o, 'conn_gmail_founder', 'gmail', 'message', :soid, :thread, :e, "
        "  cast(:actor as jsonb), :at, cast(:rcpt as text[]))"),
        {"e": f"ev_gf_{n}", "o": ORG, "soid": f"m_gf_{n}", "thread": thread,
         "actor": '{"email": "%s"}' % sender, "at": at, "rcpt": "{" + FOUNDER + "}"})
    if body:
        c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, "
                       "  clean_text) values (:e, :o, :p, :t)"),
                  {"e": f"ev_gf_{n}", "o": ORG, "p": f"pc_gf_{n}", "t": body})


def _customer_request(c) -> None:
    """A customer's request from Gmail, six days old, never answered — and its thread node."""
    _message(c, 1, "th_gf_customer", CUSTOMER, NOW - timedelta(days=6),
             "the nightly export is broken, how do I download the file?")
    c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                   "values ('node_gf_thread', :o, 'thread', 'thread:th_gf_customer', "
                   "  'Thread with Asha')"), {"o": ORG})


def _internal_by_sender(store) -> dict[str, bool]:
    desk = gather(store, ORG, now=NOW, policy=ResponsePolicy())
    return {m.sender: m.internal for m in desk.messages}


def test_a_customer_writing_from_another_gmail_address_is_not_one_of_us(store):
    with store.engine.begin() as c:
        _customer_request(c)
        _message(c, 2, "th_gf_own", FOUNDER, NOW - timedelta(days=4), "an update from the founder")
    internal = _internal_by_sender(store)
    assert internal[FOUNDER] is True, "the founder's own Gmail address is ours"
    assert internal[CUSTOMER] is False, (
        "a customer writing from gmail.com was read as one of us, because the founder's mail "
        "domain is gmail.com")


def test_gmail_is_never_one_of_our_domains(store):
    desk = gather(store, ORG, now=NOW, policy=ResponsePolicy())
    assert "gmail.com" not in desk.internal_domains, desk.internal_domains
    assert desk.internal_domains == frozenset({"thegenios.com"}), "the declared domain is ours"


def test_an_address_at_a_declared_company_domain_is_one_of_us(store):
    with store.engine.begin() as c:
        _message(c, 3, "th_gf_team", COLLEAGUE, NOW - timedelta(days=3), "looping in the team")
    assert _internal_by_sender(store)[COLLEAGUE] is True, (
        "a colleague at the company domain the tenant declared read as an outside stranger")


def test_the_gmail_customers_unanswered_request_starts_the_first_response_clock(store):
    """What the false "us" cost: a request nobody answered was read as our own message, so the
    first-response clock never started and no situation was opened for it."""
    with store.engine.begin() as c:
        _customer_request(c)
    refresh_support_situations(store, ORG, now=NOW)
    with store.engine.connect() as c:
        anchors = {r.anchor_node_id for r in c.execute(text(
            "select anchor_node_id from context_situations where org_id = :o and status = 'active'"),
            {"o": ORG})}
    assert "node_gf_thread" in anchors, (
        "the Gmail customer's unanswered request opened no situation — it was read as ours")
