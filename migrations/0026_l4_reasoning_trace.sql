-- GeniOS Layer 4: immutable, replayable reasoning trace.
--
-- One completed run binds an exact context snapshot, capability/config/policy
-- versions, evaluation time, ordered reasoner results, all candidate actions,
-- every elimination/check and one deterministic decision (or no-action) output.
-- Context payloads live in a separate TTL table so sensitive derived values can
-- expire while hashes and the non-content audit trail remain.

create table if not exists reasoning_context_snapshots (
    org_id                 text not null references orgs (id) on delete cascade,
    context_snapshot_id    text not null,
    capability_id          text not null,
    capability_version     text not null,
    capability_snapshot_id text not null,
    root_node_id            text,
    graph_version           bigint not null check (graph_version >= 0),
    evaluation_time        timestamptz not null,
    selector_version       text not null,
    selector               jsonb not null,
    selector_hash          text not null,
    payload_hash           text not null,
    context_hash           text not null,
    source_manifest        jsonb not null default '[]',
    item_count             integer not null default 0 check (item_count >= 0),
    schema_version         integer not null default 1 check (schema_version > 0),
    created_at             timestamptz not null default now(),
    primary key (org_id, context_snapshot_id),
    unique (org_id, context_hash),
    check (jsonb_typeof(source_manifest) = 'array'),
    check (jsonb_typeof(selector) = 'object'),
    check (selector_hash ~ '^[0-9a-f]{64}$'),
    check (payload_hash ~ '^[0-9a-f]{64}$'),
    check (context_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists reasoning_context_by_capability
    on reasoning_context_snapshots
       (org_id, capability_id, root_node_id, evaluation_time desc);

create table if not exists reasoning_context_payloads (
    org_id              text not null,
    context_snapshot_id text not null,
    payload             jsonb not null,
    expires_at          timestamptz,
    created_at          timestamptz not null default now(),
    primary key (org_id, context_snapshot_id),
    foreign key (org_id, context_snapshot_id)
        references reasoning_context_snapshots (org_id, context_snapshot_id)
        on delete cascade,
    check (jsonb_typeof(payload) = 'object')
);

create index if not exists reasoning_context_payload_expiry
    on reasoning_context_payloads (expires_at)
    where expires_at is not null;

create table if not exists reasoning_runs (
    org_id                 text not null references orgs (id) on delete cascade,
    run_id                 text not null,
    idempotency_key        text not null,
    capability_id          text not null,
    capability_version     text not null,
    capability_snapshot_id text not null,
    context_snapshot_id    text not null,
    config_snapshot_id     text,
    policy_snapshot_id     text,
    trigger_kind           text not null,
    trigger_ref            text,
    root_node_id            text,
    mode                    text not null default 'live',
    status                  text not null default 'completed',
    evaluation_time        timestamptz not null,
    input_manifest         jsonb not null,
    input_hash             text not null,
    reasoner_plan          jsonb not null,
    reasoner_plan_hash     text not null,
    orchestrator_version   text not null,
    engine_build           text not null,
    output_hash            text not null,
    replay_of_run_id       text,
    supersedes_run_id      text,
    started_at             timestamptz not null default now(),
    completed_at           timestamptz not null default now(),
    primary key (org_id, run_id),
    unique (org_id, idempotency_key),
    foreign key (org_id, context_snapshot_id)
        references reasoning_context_snapshots (org_id, context_snapshot_id),
    foreign key (org_id, config_snapshot_id)
        references config_snapshots (org_id, snapshot_id),
    foreign key (org_id, replay_of_run_id)
        references reasoning_runs (org_id, run_id),
    foreign key (org_id, supersedes_run_id)
        references reasoning_runs (org_id, run_id),
    check (trigger_kind in ('event', 'query', 'schedule', 'manual', 'replay')),
    check (mode in ('live', 'shadow', 'simulation', 'replay')),
    check (status = 'completed'),
    check (mode <> 'replay' or replay_of_run_id is not null),
    check (jsonb_typeof(input_manifest) = 'object'),
    check (jsonb_typeof(reasoner_plan) = 'array'),
    check (input_hash ~ '^[0-9a-f]{64}$'),
    check (reasoner_plan_hash ~ '^[0-9a-f]{64}$'),
    check (output_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists reasoning_runs_by_capability
    on reasoning_runs (org_id, capability_id, completed_at desc);

create index if not exists reasoning_runs_replay
    on reasoning_runs (org_id, replay_of_run_id)
    where replay_of_run_id is not null;

create table if not exists reasoning_reasoner_results (
    org_id           text not null,
    result_id        text not null,
    run_id           text not null,
    ordinal          integer not null check (ordinal >= 0),
    reasoner_id      text not null,
    reasoner_version text not null,
    invocation_key   text not null default 'default',
    status           text not null,
    input_hash       text not null,
    output           jsonb not null default '{}',
    output_hash      text not null,
    evidence_refs    jsonb not null default '[]',
    diagnostics      jsonb not null default '{}',
    skip_reason_code text,
    error_code       text,
    created_at       timestamptz not null default now(),
    primary key (org_id, result_id),
    unique (org_id, run_id, ordinal),
    unique (org_id, run_id, reasoner_id, invocation_key),
    foreign key (org_id, run_id)
        references reasoning_runs (org_id, run_id) on delete cascade,
    check (status in ('completed', 'skipped', 'failed', 'insufficient_context')),
    check (jsonb_typeof(output) = 'object'),
    check (jsonb_typeof(evidence_refs) = 'array'),
    check (jsonb_typeof(diagnostics) = 'object'),
    check (input_hash ~ '^[0-9a-f]{64}$'),
    check (output_hash ~ '^[0-9a-f]{64}$')
);

create table if not exists reasoning_candidates (
    org_id             text not null,
    candidate_id       text not null,
    run_id             text not null,
    play_id            text not null,
    play_version       text not null,
    parameters         jsonb not null default '{}',
    score_components   jsonb not null,
    initial_utility_bp integer not null check (initial_utility_bp between 0 and 10000),
    final_utility_bp   integer check (final_utility_bp between 0 and 10000),
    confidence_bp      integer not null check (confidence_bp between 0 and 10000),
    disposition        text not null,
    rank_position      integer,
    evidence_refs      jsonb not null default '[]',
    candidate_hash     text not null,
    created_at         timestamptz not null default now(),
    primary key (org_id, candidate_id),
    unique (org_id, run_id, candidate_id),
    unique (org_id, run_id, candidate_hash),
    foreign key (org_id, run_id)
        references reasoning_runs (org_id, run_id) on delete cascade,
    check (disposition in ('eligible', 'eliminated')),
    check (rank_position is null or rank_position > 0),
    check (disposition = 'eligible' or rank_position is null),
    check (jsonb_typeof(parameters) = 'object'),
    check (jsonb_typeof(score_components) = 'object'),
    check (jsonb_typeof(evidence_refs) = 'array'),
    check (candidate_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists reasoning_candidates_by_run
    on reasoning_candidates
       (org_id, run_id, disposition, rank_position);

create unique index if not exists reasoning_candidate_rank_once
    on reasoning_candidates (org_id, run_id, rank_position)
    where disposition = 'eligible' and rank_position is not null;

create table if not exists reasoning_candidate_checks (
    org_id            text not null,
    check_id          text not null,
    run_id            text not null,
    candidate_id      text not null,
    ordinal           integer not null check (ordinal >= 0),
    stage             text not null,
    evaluator_id      text not null,
    evaluator_version text not null,
    outcome           text not null,
    reason_code       text not null,
    score_before_bp   integer,
    score_after_bp    integer,
    detail            jsonb not null default '{}',
    check_hash        text not null,
    created_at        timestamptz not null default now(),
    primary key (org_id, check_id),
    unique (org_id, run_id, candidate_id, ordinal),
    foreign key (org_id, run_id, candidate_id)
        references reasoning_candidates (org_id, run_id, candidate_id)
        on delete cascade,
    check (stage in ('precondition', 'constraint', 'policy', 'permission',
                     'safety', 'cost_benefit', 'ranking')),
    check (outcome in ('pass', 'warn', 'eliminate', 'adjust')),
    check (score_before_bp is null or score_before_bp between 0 and 10000),
    check (score_after_bp is null or score_after_bp between 0 and 10000),
    check (jsonb_typeof(detail) = 'object'),
    check (check_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists reasoning_eliminations
    on reasoning_candidate_checks (org_id, run_id, candidate_id)
    where outcome = 'eliminate';

create table if not exists reasoning_run_outputs (
    org_id                text not null,
    run_id                text not null,
    outcome_kind          text not null,
    selected_candidate_id text,
    ranked_candidate_ids  jsonb not null default '[]',
    decision_core         jsonb not null,
    decision_hash         text not null,
    confidence_bp         integer not null check (confidence_bp between 0 and 10000),
    missing_data          jsonb not null default '[]',
    created_at            timestamptz not null default now(),
    primary key (org_id, run_id),
    foreign key (org_id, run_id)
        references reasoning_runs (org_id, run_id) on delete cascade,
    foreign key (org_id, run_id, selected_candidate_id)
        references reasoning_candidates (org_id, run_id, candidate_id),
    check (outcome_kind in ('decision', 'no_action', 'defer',
                            'insufficient_context', 'blocked', 'failed')),
    check ((outcome_kind = 'decision' and selected_candidate_id is not null)
           or (outcome_kind <> 'decision' and selected_candidate_id is null)),
    check (jsonb_typeof(ranked_candidate_ids) = 'array'),
    check (jsonb_typeof(decision_core) = 'object'),
    check (jsonb_typeof(missing_data) = 'array'),
    check (decision_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists reasoning_outputs_by_hash
    on reasoning_run_outputs (org_id, decision_hash);
