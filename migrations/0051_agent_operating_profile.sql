-- Agent operating profile: the richer runtime shape the dashboard already sends/expects
-- (framework, role, objective, intelligence_modules, operating_actions, response_style,
-- handoff_mode, guardrails, policy_refs). Stored as one JSONB blob so the contract can evolve
-- without a column per field. The backend previously ignored these — this makes create/read honest.

alter table agent_registry add column if not exists operating_profile            jsonb;
alter table agent_registry add column if not exists operating_profile_version    integer not null default 0;
alter table agent_registry add column if not exists operating_profile_updated_at timestamptz;
