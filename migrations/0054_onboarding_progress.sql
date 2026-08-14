-- Onboarding / sync progress — one row per org, DB-backed so it survives a page refresh AND a
-- server restart (the old signal was an in-memory boolean, lost on both). The frontend polls this
-- to show the user WHAT IS HAPPENING RIGHT NOW in plain language (no L1/L2/L3 jargon).
--
-- phases: ordered JSON array of {key,label,state,done,total,detail}. state ∈ pending|running|done|error.
-- overall_percent: 0..100 coarse weighted progress. state: idle|running|done|error.

create table if not exists onboarding_progress (
    org_id          text primary key,
    state           text not null default 'idle',
    current_phase   text,
    overall_percent int  not null default 0,
    phases          jsonb not null default '[]'::jsonb,
    started_at      timestamptz,
    updated_at      timestamptz not null default now()
);
