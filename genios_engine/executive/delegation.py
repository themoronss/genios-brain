"""Agent delegation's four verbs: propose, approve, dispatch, result — each once, in order.

`ExecutionState` deliberately does NOT grow agent states: its vocabulary describes the
COMMITMENT (pending, running, waiting, completed), and "an agent is attempting step 2" is a
fact about the machinery working it, not about where the commitment stands. Conflating the two
is how an agent crash would have read as a stalled human. A delegation is its own small ledger
row with its own lifecycle, joined to the execution it serves.

The law this encodes: **no approval, no dispatch — ever.** A proposal names the exact
instruction bytes; the approval pins a named human to those bytes with an expiry; dispatch
happens at most once inside the approval window; the result lands exactly once. Every verb is
guarded on the previous state, so a retry, a refresh or a concurrent click converges instead of
double-sending an external action.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.platform.ids import new_id

#: How long an approval authorises dispatch. Short on purpose: an approval is a human reading a
#: SPECIFIC draft at a specific moment, and the world the draft was written for moves.
APPROVAL_TTL_HOURS = 24


def propose(conn, *, org_id: str, execution_id: str, agent_id: str,
            instruction: dict, action_id: str | None = None) -> str:
    """The engine proposes handing one action to one agent. Nothing is sent."""
    delegation_id = new_id("dlg")
    conn.execute(text(
        "insert into agent_delegations (org_id, delegation_id, execution_id, action_id, "
        "agent_id, instruction) values (:o, :d, :x, :a, :ag, cast(:i as jsonb))"),
        {"o": org_id, "d": delegation_id, "x": execution_id, "a": action_id,
         "ag": agent_id, "i": json.dumps(instruction, default=str)})
    return delegation_id


def approve(conn, *, org_id: str, delegation_id: str, actor: str, at: datetime,
            reject: bool = False) -> bool:
    """A named human approves (or rejects) the proposal's exact bytes. Guarded on 'proposed'."""
    if reject:
        result = conn.execute(text(
            "update agent_delegations set state='rejected', approved_by=:by, approved_at=:at "
            "where org_id=:o and delegation_id=:d and state='proposed'"),
            {"by": actor, "at": at, "o": org_id, "d": delegation_id})
        return result.rowcount == 1
    result = conn.execute(text(
        "update agent_delegations set state='approved', approved_by=:by, approved_at=:at, "
        "approval_expires_at=:exp "
        "where org_id=:o and delegation_id=:d and state='proposed'"),
        {"by": actor, "at": at, "exp": at + timedelta(hours=APPROVAL_TTL_HOURS),
         "o": org_id, "d": delegation_id})
    return result.rowcount == 1


def claim_dispatch(conn, *, org_id: str, delegation_id: str, at: datetime) -> dict | None:
    """Claim the single dispatch slot. None = not approved, expired, or already dispatched.

    The state transition IS the mutex: two concurrent dispatchers race this UPDATE and exactly
    one wins the row. An expired approval flips to 'expired' rather than silently refusing, so
    the operator sees WHY nothing went out.
    """
    row = conn.execute(text(
        "update agent_delegations set state='dispatched', dispatched_at=:at "
        "where org_id=:o and delegation_id=:d and state='approved' "
        "and approval_expires_at > :at "
        "returning execution_id, action_id, agent_id, instruction"),
        {"at": at, "o": org_id, "d": delegation_id}).mappings().first()
    if row is not None:
        return dict(row)
    conn.execute(text(
        "update agent_delegations set state='expired' "
        "where org_id=:o and delegation_id=:d and state='approved' "
        "and approval_expires_at <= :at"),
        {"o": org_id, "d": delegation_id, "at": at})
    return None


def record_result(conn, *, org_id: str, delegation_id: str, ok: bool,
                  detail: dict, at: datetime) -> bool:
    """The agent's outcome, exactly once. Guarded on 'dispatched'."""
    result = conn.execute(text(
        "update agent_delegations set state=:st, resulted_at=:at, result=cast(:r as jsonb) "
        "where org_id=:o and delegation_id=:d and state='dispatched'"),
        {"st": "succeeded" if ok else "failed", "at": at,
         "r": json.dumps(detail, default=str), "o": org_id, "d": delegation_id})
    return result.rowcount == 1


__all__ = ["APPROVAL_TTL_HOURS", "approve", "claim_dispatch", "propose", "record_result"]
