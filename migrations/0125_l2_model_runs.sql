-- L2 model governance: every decision-affecting call is replayable and versioned.
create table if not exists l2_model_runs (
    run_id          text primary key,
    org_id          text not null references orgs (id) on delete cascade,
    site            text not null,
    subject_ref     text not null,
    prompt_version  text not null,
    prompt_hash     text not null,
    model_snapshot  text not null,
    max_tokens      integer not null check (max_tokens > 0),
    input_tokens    integer not null default 0 check (input_tokens >= 0),
    output_tokens   integer not null default 0 check (output_tokens >= 0),
    success         boolean not null,
    error           text,
    parsed_output   jsonb not null default '{}'::jsonb,
    raw_output      text not null default '',
    response_hash   text not null,
    latency_ms      integer check (latency_ms is null or latency_ms >= 0),
    called_at       timestamptz not null,
    created_at      timestamptz not null default now()
);

create index if not exists l2_model_runs_by_site
    on l2_model_runs (org_id, site, called_at desc);
create index if not exists l2_model_runs_by_prompt
    on l2_model_runs (org_id, site, subject_ref, prompt_version, prompt_hash);

comment on table l2_model_runs is
  'Replay envelope for every decision-affecting Layer 2 model call: prompt hash/version, pinned model, complete output, tokens, success and latency.';
