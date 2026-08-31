-- L5-06: agent delegation gets a governed protocol.
--
-- `deliver/push.py::push_action_to_agents` is a fail-closed shim ("external action push is
-- disabled") because there was nothing to govern WITH: ExecutionState cannot express "a human
-- approved handing this to an agent" or "the agent failed it", and no ledger recorded either.
-- Rather than widening the execution state machine (whose states describe the COMMITMENT, not
-- the machinery working it), delegation gets its own small ledger: proposed by the engine,
-- approved by a named human, dispatched once, resulted exactly once. The execution stays in its
-- own lifecycle; a delegation is one governed attempt at one of its actions.
create table if not exists agent_delegations (
    org_id           text not null references orgs(id) on delete cascade,
    delegation_id    text not null,
    execution_id     text not null,
    action_id        text,
    agent_id         text not null,
    -- the exact instruction + draft the human approves; the agent may receive NOTHING else
    instruction      jsonb not null default '{}',
    state            text not null default 'proposed'
                     check (state in ('proposed', 'approved', 'rejected',
                                      'dispatched', 'succeeded', 'failed', 'expired')),
    proposed_at      timestamptz not null default now(),
    approved_by      text,
    approved_at      timestamptz,
    dispatched_at    timestamptz,
    resulted_at      timestamptz,
    result           jsonb,
    -- an approval is for ONE dispatch of ONE payload: re-running needs a fresh approval
    approval_expires_at timestamptz,
    primary key (org_id, delegation_id)
);
create index if not exists agent_delegations_exec on agent_delegations (org_id, execution_id);

comment on table agent_delegations is
  'One governed attempt at handing one execution action to one agent. proposed -> approved (named human) -> dispatched -> succeeded|failed. No approval, no dispatch — ever.';
