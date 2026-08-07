-- Layer 4 learning authority.
--
-- Historical outcomes may tune a decision rule only when they belong to the exact
-- pack/version that produced it.  A correction is one mutable verdict per card with
-- an append-only revision trail.  Calibration is claimed once per UTC week and all
-- of its config + audit writes commit in one transaction.

-- A rule name is not globally unique. Bind the live signal projection to its pack lineage and
-- replace the legacy org/rule/entity uniqueness key with the real authority identity.
alter table reasoning_context_snapshots add column if not exists root_node_type text;
update reasoning_context_snapshots rcs
set root_node_type=rcp.payload->>'root_entity_type'
from reasoning_context_payloads rcp
where rcp.org_id=rcs.org_id
  and rcp.context_snapshot_id=rcs.context_snapshot_id
  and rcs.root_node_type is null;
alter table reasoning_context_snapshots
    add constraint reasoning_context_root_type_required
    check (root_node_type is not null and btrim(root_node_type) <> '') not valid;
alter table reasoning_context_snapshots alter column schema_version set default 2;

alter table signals add column if not exists pack_id text;
alter table signals add column if not exists pack_version text;

update signals s
set pack_id=cs.pack_id,
    pack_version=cs.effective->>'version'
from config_snapshots cs
where cs.org_id=s.org_id and cs.snapshot_id=s.config_snapshot_id
  and (s.pack_id is null or s.pack_version is null);

drop index if exists signals_one_open;
create unique index signals_one_open
    on signals (org_id, pack_id, pack_version, rule_id, subject_node_id)
    where status='open';

alter table signals add constraint signals_pack_binding_shape
    check (authority_binding_version=0 or (pack_id is not null and pack_version is not null))
    not valid;

create table if not exists reasoning_publication_watermarks (
    org_id               text primary key references orgs(id) on delete cascade,
    last_evaluation_time timestamptz not null,
    updated_at           timestamptz not null default clock_timestamp()
);

-- Human notification retries retain and re-prove the exact decision they intend to surface.
alter table delivery_outbox add column if not exists signal_id text;
alter table delivery_outbox add column if not exists reasoning_run_id text;
alter table delivery_outbox add column if not exists reasoning_decision_hash text;
alter table delivery_outbox add column if not exists authority_pack_revision bigint;
alter table delivery_outbox add column if not exists authority_expires_at timestamptz;

-- Expensive card copy generation uses a short durable lease. Multiple workers may discover the
-- same un-carded signal, but only the lease holder is allowed to invoke the renderer/LLM.
alter table signals add constraint signals_signal_org_identity unique (signal_id, org_id);
create table if not exists card_build_claims (
    signal_id    text primary key,
    org_id       text not null references orgs(id) on delete cascade,
    claim_token  text not null unique,
    claimed_at   timestamptz not null,
    expires_at   timestamptz not null,
    foreign key (signal_id, org_id) references signals(signal_id, org_id) on delete cascade,
    check (expires_at > claimed_at)
);
create index if not exists card_build_claims_expiry on card_build_claims (expires_at);

alter table rule_mutes add column if not exists pack_id text;
alter table rule_mutes add column if not exists pack_version text;
alter table rule_mutes add column if not exists judgments int;
alter table rule_mutes add column if not exists precision_lb numeric(5,4);
alter table rule_mutes add column if not exists precision_ub numeric(5,4);
alter table rule_mutes add column if not exists source_authority_revision bigint;
alter table rule_mutes add column if not exists source_capability_id text;
alter table rule_mutes add column if not exists source_capability_version text;

update rule_mutes rm
set active = false,
    pack_id = coalesce(rm.pack_id, '__legacy_unknown__'),
    pack_version = coalesce(rm.pack_version, '__legacy_unknown__'),
    reason = coalesce(rm.reason, 'quarantined: legacy row has no provable pack lineage')
where rm.pack_id is null or rm.pack_version is null;

alter table rule_mutes alter column pack_id set not null;
alter table rule_mutes alter column pack_version set not null;
alter table rule_mutes drop constraint if exists rule_mutes_pkey;
-- Deliberate conservative transfer: a mute applies across scoring/config epochs only inside the
-- same immutable pack version and rule id. Source lineage is retained for audit; a pack version
-- change clears applicability. This protects users while threshold-only authority revisions turn.
alter table rule_mutes
    add constraint rule_mutes_pkey primary key (org_id, pack_id, pack_version, rule_id);

alter table calibration_nudges add column if not exists pack_id text;
alter table calibration_nudges add column if not exists pack_version text;
alter table calibration_nudges add column if not exists judgments int;
alter table calibration_nudges add column if not exists precision_lb numeric(5,4);
alter table calibration_nudges add column if not exists precision_ub numeric(5,4);
alter table calibration_nudges add column if not exists calibration_run_id text;
alter table calibration_nudges add column if not exists period_start timestamptz;
alter table calibration_nudges add column if not exists authority_revision bigint;

update calibration_nudges cn
set pack_id = coalesce(cn.pack_id, '__legacy_unknown__'),
    pack_version = coalesce(cn.pack_version, '__legacy_unknown__')
where cn.pack_id is null or cn.pack_version is null;

alter table calibration_nudges alter column pack_id set not null;
alter table calibration_nudges alter column pack_version set not null;
drop index if exists calibration_nudges_by_org;
create index if not exists calibration_nudges_by_org
    on calibration_nudges (org_id, pack_id, pack_version, rule_id, created_at desc);

create table if not exists calibration_runs (
    run_id          text primary key,
    org_id          text not null references orgs(id) on delete cascade,
    pack_id         text not null,
    pack_version    text not null,
    authority_revision bigint not null,
    period_start    timestamptz not null,
    evaluation_time timestamptz not null,
    status          text not null default 'started',
    result          jsonb,
    created_at      timestamptz not null default now(),
    completed_at    timestamptz,
    unique (org_id, pack_id, pack_version, period_start),
    unique (run_id, org_id, pack_id, pack_version),
    check (status in ('started', 'completed'))
);

create unique index if not exists calibration_runs_authority_identity
    on calibration_runs (run_id, org_id, pack_id, pack_version);

alter table calibration_nudges drop constraint if exists calibration_nudges_run_fk;
alter table calibration_nudges
    add constraint calibration_nudges_run_fk
    foreign key (calibration_run_id, org_id, pack_id, pack_version)
    references calibration_runs(run_id, org_id, pack_id, pack_version) on delete cascade
    not valid;

create unique index if not exists calibration_nudges_once_per_run
    on calibration_nudges (calibration_run_id, rule_id, param)
    where calibration_run_id is not null;

alter table cards add constraint cards_card_org_identity unique (card_id, org_id);

create table if not exists card_feedback_verdicts (
    feedback_id        text primary key,
    org_id             text not null references orgs(id) on delete cascade,
    card_id            text not null,
    pack_id            text not null,
    pack_version       text not null,
    authority_pack_revision bigint not null,
    capability_id      text not null,
    capability_version text not null,
    rule_id            text not null,
    cause               text not null,
    reason              text,
    detail              jsonb not null default '{}',
    actor_id            text not null,
    verdict_version     bigint not null default 1,
    occurred_at         timestamptz not null default clock_timestamp(),
    created_at          timestamptz not null default clock_timestamp(),
    unique (org_id, card_id),
    unique (feedback_id, org_id, card_id),
    foreign key (card_id, org_id) references cards(card_id, org_id) on delete cascade,
    check (cause in ('run_play', 'do_it_myself', 'wrong')),
    check (cause <> 'wrong' or
           (reason is not null and reason in ('not_relevant', 'wrong_facts', 'bad_timing'))),
    check (verdict_version > 0)
);

create table if not exists card_feedback_revisions (
    revision_id        text primary key,
    feedback_id        text not null,
    org_id             text not null references orgs(id) on delete cascade,
    card_id            text not null,
    verdict_version    bigint not null,
    cause               text not null,
    reason              text,
    detail              jsonb not null default '{}',
    actor_id            text not null,
    occurred_at         timestamptz not null default clock_timestamp(),
    unique (feedback_id, verdict_version),
    foreign key (feedback_id, org_id, card_id)
        references card_feedback_verdicts(feedback_id, org_id, card_id) on delete cascade,
    foreign key (card_id, org_id) references cards(card_id, org_id) on delete cascade,
    check (cause in ('run_play', 'do_it_myself', 'wrong')),
    check (cause <> 'wrong' or
           (reason is not null and reason in ('not_relevant', 'wrong_facts', 'bad_timing')))
);

create index if not exists card_feedback_verdicts_learning
    on card_feedback_verdicts
    (org_id, pack_id, pack_version, capability_id, capability_version, occurred_at desc);
