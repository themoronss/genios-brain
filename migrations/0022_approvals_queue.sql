-- Governance: approvals_queue (dashboard → Settings → Approvals). When a policy decision is
-- 'require_approval', the action is parked here for a human to approve/reject before it executes.
-- Rows are created by policy_routes.enqueue() (wired when the engine gains a server-side action
-- path); the dashboard reads/decides them here. Ported from genios-brain.
create table if not exists approvals_queue (
    id                text primary key,
    org_id            text not null,
    agent_id          text,
    action_type       text not null,
    risk_tier         text,
    target_ref        text,
    payload           jsonb not null default '{}',
    triggered_rule_id text,
    status            text not null default 'pending',   -- pending|approved|rejected|expired|auto_executed
    reason            text,
    approved_by       text,
    approved_at       timestamptz,
    created_at        timestamptz not null default now(),
    expires_at        timestamptz
);
create index if not exists approvals_queue_by_org on approvals_queue (org_id, status, created_at desc);
