-- Governance: user_models + proposals (dashboard → Settings → Personas). One persona per (org, user
-- email): how that person writes (voice), decides (decision_policy), works (process_habits), what
-- they lead with (priorities), who matters (relationships), and hard nos (red_lines). field_meta
-- tracks source (seeded|learned) + confidence per field. Proposals are learned "big shift" change
-- suggestions the user approves/rejects. Ported from genios-brain (core/usermodel).
create table if not exists user_models (
    id                    text primary key,
    org_id                text not null,
    user_id               text not null,          -- the user's email
    voice_jsonb           jsonb not null default '{}',
    decision_policy_jsonb jsonb not null default '{}',
    process_habits_jsonb  jsonb not null default '{}',
    priorities_jsonb      jsonb not null default '{}',
    relationships_jsonb   jsonb not null default '{}',
    red_lines_jsonb       jsonb not null default '[]',
    field_meta_jsonb      jsonb not null default '{}',
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now(),
    unique (org_id, user_id)
);
create index if not exists user_models_by_org on user_models (org_id);

create table if not exists user_model_proposals (
    id                    text primary key,
    org_id                text not null,
    user_id               text not null,
    field                 text not null,          -- one of the 6 persona fields
    current_value_jsonb   jsonb,
    proposed_value_jsonb  jsonb,
    signal_count          int  not null default 0,
    rationale             text,
    status                text not null default 'pending',   -- pending | approved | rejected
    decided_by            text,
    decided_at            timestamptz,
    created_at            timestamptz not null default now()
);
create index if not exists user_model_proposals_by_user on user_model_proposals (org_id, user_id, status);
