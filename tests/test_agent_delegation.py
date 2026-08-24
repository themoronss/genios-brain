"""L5-06: no approval, no dispatch — ever.

`ExecutionState` deliberately does not grow agent states: its vocabulary describes the
COMMITMENT, and "an agent is attempting step 2" is a fact about the machinery working it.
Conflating them is how an agent crash would read as a stalled human. A delegation is its own
ledger row: proposed → approved (named human, TTL) → dispatched (single winner) → resulted.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.executive.delegation import (
    approve,
    claim_dispatch,
    propose,
    record_result,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""
            create table agent_delegations (
                org_id text not null, delegation_id text not null,
                execution_id text not null, action_id text, agent_id text not null,
                instruction text not null default '{}',
                state text not null default 'proposed',
                proposed_at timestamp, approved_by text, approved_at timestamp,
                dispatched_at timestamp, resulted_at timestamp, result text,
                approval_expires_at timestamp,
                primary key (org_id, delegation_id))"""))
    with engine.begin() as c:
        yield c


def _proposed(conn):
    return propose(conn, org_id="o", execution_id="x1", agent_id="a1",
                   instruction={"draft": "text"})


def test_no_approval_no_dispatch(conn):
    d = _proposed(conn)
    assert claim_dispatch(conn, org_id="o", delegation_id=d, at=NOW) is None


def test_approval_authorises_exactly_one_dispatch(conn):
    """The state transition IS the mutex: two concurrent dispatchers race the UPDATE and
    exactly one wins the row."""
    d = _proposed(conn)
    assert approve(conn, org_id="o", delegation_id=d, actor="harsh", at=NOW)
    first = claim_dispatch(conn, org_id="o", delegation_id=d, at=NOW + timedelta(minutes=1))
    second = claim_dispatch(conn, org_id="o", delegation_id=d, at=NOW + timedelta(minutes=2))
    assert first is not None and second is None


def test_an_expired_approval_refuses_loudly_not_silently(conn):
    """The row flips to 'expired' so the operator sees WHY nothing went out — an approval is a
    human reading a SPECIFIC draft at a specific moment, and the world moves."""
    d = _proposed(conn)
    approve(conn, org_id="o", delegation_id=d, actor="harsh", at=NOW)
    late = NOW + timedelta(hours=25)
    assert claim_dispatch(conn, org_id="o", delegation_id=d, at=late) is None
    state = conn.execute(text("select state from agent_delegations where delegation_id=:d"),
                         {"d": d}).scalar()
    assert state == "expired"


def test_a_rejection_is_terminal(conn):
    d = _proposed(conn)
    assert approve(conn, org_id="o", delegation_id=d, actor="harsh", at=NOW, reject=True)
    assert claim_dispatch(conn, org_id="o", delegation_id=d, at=NOW) is None
    # a second approval of a rejected proposal is a no-op, not a resurrection
    assert not approve(conn, org_id="o", delegation_id=d, actor="harsh", at=NOW)


def test_a_result_lands_exactly_once(conn):
    d = _proposed(conn)
    approve(conn, org_id="o", delegation_id=d, actor="harsh", at=NOW)
    claim_dispatch(conn, org_id="o", delegation_id=d, at=NOW + timedelta(minutes=1))
    assert record_result(conn, org_id="o", delegation_id=d, ok=False,
                         detail={"error": "timeout"}, at=NOW + timedelta(minutes=5))
    assert not record_result(conn, org_id="o", delegation_id=d, ok=True,
                             detail={}, at=NOW + timedelta(minutes=6))
    state = conn.execute(text("select state from agent_delegations where delegation_id=:d"),
                         {"d": d}).scalar()
    assert state == "failed"


def test_the_broadcast_shim_stays_fail_closed():
    from genios_engine.deliver.push import push_action_to_agents

    with pytest.raises(RuntimeError, match="approved delegation"):
        push_action_to_agents(None, "o", "card_1")
