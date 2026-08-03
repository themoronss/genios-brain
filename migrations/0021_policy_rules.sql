-- Governance: policy_rules (dashboard → Settings → Policies). Rules-as-data: a rule is a JSON
-- condition tree + a decision (allow|warn|require_approval|block) evaluated over an action context.
-- Authoring + dry-run live here; live enforcement (open an approval on require_approval) is wired via
-- the enqueue() helper when the engine gains a server-side action path. Ported from genios-brain.
create table if not exists policy_rules (
    id           text primary key,
    org_id       text not null,
    name         text not null,
    description  text,
    action_type  text not null default '*',
    risk_tier    text,
    rule_json    jsonb not null default '{}',            -- {condition:{...}, decision:"..."}
    priority     int  not null default 100,               -- lower = evaluated first
    enabled      boolean not null default true,
    mode         text not null default 'enforce',         -- enforce | warn_only | shadow
    version      int  not null default 1,
    created_by   text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);
create index if not exists policy_rules_by_org on policy_rules (org_id, priority);
