"""Who this account has written to is known from its sent mail, not only from the graph.

    pytest tests/api/test_a_cold_graph_must_not_decide_who_you_know.py -q

⛔ THE CIRCLE THIS BREAKS. `whitelist()` returns W-01 — "do not destructively drop this" — when
`ctx.sender_known`. That set was read ONLY from `graph_facts.thread.last_outbound`, which exists
only after an email has survived the gate, been extracted, and reached the graph. The gate was
therefore asking a question whose answer the gate itself produces.

On a fresh tenant the graph is empty, so NOBODY is known, so W-01 protects nobody, and the N-codes
run at full strength across the entire history. A sender becomes known only once one of their
messages happens to survive — and every earlier message from that same person is already gone.

⛔ MEASURED on the design partner's org 2026-10-04, wiped and re-synced on 03 Oct:

    522 gmail messages, 255 dropped at S1 (N-01 machine_ack, N-02 bulk_unsub, N-03 no_reply,
                                           N-04 bulk_precedence, N-06 gmail_promotions)
    TWENTY senders had some mail emitted and some dropped — the same person, opposite fates,
    decided by nothing but which page of the backfill they landed on.

    `anshul@engramme.com` lost mail to N-01 while other mail from that same address was kept.

    known set from the graph        11 people
    known set including sent mail   29 people

⛔ THE DEFINITION DOES NOT CHANGE, and `test_a_stranger_is_still_a_stranger` is why. A known
counterparty is still somebody THIS ACCOUNT HAS WRITTEN TO. `source_events.recipients` is written
at capture, before any gate, on the tenant's own outbound mail — the same fact, available a whole
pipeline earlier. Someone who merely writes IN is still a stranger, which is what the N-codes
exist to filter.
"""

from __future__ import annotations

import re

import pytest

from genios_engine.api.routes import KNOWN_COUNTERPARTY_SQL, KNOWN_FROM_SENT_SQL

pytestmark = pytest.mark.unit


def _normalised() -> str:
    """Both halves, as one string — the question is answered by the pair, not by either alone."""
    return re.sub(r"\s+", " ", f"{KNOWN_COUNTERPARTY_SQL} {KNOWN_FROM_SENT_SQL}").lower()


def test_sent_mail_counts_as_knowing_someone():
    """⛔ THE MUTATION THIS FILE REJECTS: going back to the graph alone. On every fresh tenant the
    whitelist then protects nobody for the whole of the first backfill."""
    sql = _normalised()
    assert "source_events" in sql and "recipients" in sql, (
        "the known set no longer reads outbound recipients, which is the only place this fact "
        "exists before the graph does")


def test_the_graph_half_is_still_there():
    """The other direction. Someone written to long ago, whose sent mail has aged out of
    `source_events` retention, is still known — the graph is the durable half."""
    sql = _normalised()
    assert "graph_facts" in sql and "thread.last_outbound" in sql, (
        "the graph half was replaced rather than joined; a counterparty whose outbound mail has "
        "been purged would silently become a stranger again")


def test_a_stranger_is_still_a_stranger():
    """⛔ NOT A WIDENING. An address qualifies only as a RECIPIENT of mail this account SENT.
    Reading the `actor` instead — or dropping the seat check — would make every cold-caller and
    every newsletter a known counterparty and turn the N-codes off entirely."""
    sql = _normalised()
    assert "org_seats" in sql, (
        "the sender check is gone: any inbound mail would now mark its own sender known, which "
        "disables the whole noise gate")
    assert "actor" in sql and "'email'" in sql, (
        "the outbound half no longer checks who AUTHORED the event")


def test_it_stays_scoped_to_one_tenant():
    """Both halves are per-org. A union that lost the filter on one side would leak one tenant's
    correspondents into another's gate decisions."""
    sql = _normalised()
    assert sql.count("org_id = :o") >= 2, "a half of the union is not tenant-scoped"


def test_blank_recipients_do_not_become_a_known_sender():
    """An empty string in `recipients` would otherwise match any event whose sender could not be
    parsed, and quietly whitelist the unparseable."""
    assert "nullif(trim(recipient), '')" in _normalised()


def test_the_resolver_still_reads_this_constant():
    """⛔ ON THE AST, because a behavioural test here would pass while the resolver stopped using
    the constant. This is the fourth fix in this session whose call site had to be asserted
    separately."""
    import ast
    import inspect
    import textwrap

    from genios_engine.api import routes

    tree = ast.parse(textwrap.dedent(inspect.getsource(routes.known_counterparty_keys)))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "KNOWN_COUNTERPARTY_SQL" in names, (
        "known_counterparty_keys no longer runs the graph statement")
    assert "KNOWN_FROM_SENT_SQL" in names, (
        "known_counterparty_keys no longer runs the SENT-FOLDER statement; that constant is then "
        "dead code, the cold start is circular again, and nothing above goes red — deleting the "
        "call was verified to leave 8 of 8 passing before this line existed")


def test_the_sent_half_failing_does_not_lose_the_graph_half():
    """⛔ `unnest` is Postgres-only and the hermetic suite runs this against SQLite. If the sent
    read raises, the GRAPH half must still be returned — losing it would make every known
    counterparty a stranger and hand the N-codes the whole mailbox, which is strictly worse than
    the cold start this fix exists to remove."""
    from sqlalchemy import text as _text

    from genios_engine.api.routes import known_counterparty_keys

    class _Row:
        canonical_key = "Known@Example.com"

    class _Conn:
        def execute(self, statement, _params=None):
            if "unnest" in str(statement):
                raise RuntimeError("unnest is not a function")
            assert "graph_nodes" in str(statement)
            return self

        def fetchall(self):
            return [_Row()]

    assert known_counterparty_keys(_Conn(), "org_x") == frozenset({"known@example.com"})
    assert _text  # the import is what the resolver uses; keep it honest


def test_the_two_statements_are_both_tenant_scoped():
    for sql in (KNOWN_COUNTERPARTY_SQL, KNOWN_FROM_SENT_SQL):
        assert ":o" in sql, "a half of the known set is not scoped to one tenant"
