-- GeniOS Engine · Atlas Layer 6 hardening.
--
-- 0045 remains immutable. This additive migration freezes policy authority, completes the
-- LearningObject envelope, preserves visibility through every sink, adds a normalized enterprise
-- event seam, binds all child artifacts to the same tenant/object and records rejected input
-- without retaining its raw content.

-- ── Versioned policy authority ────────────────────────────────────────────────────────────────

alter table learning_policies add column if not exists revision bigint not null default 1;
alter table learning_policies add column if not exists blocked_targets text[]
    not null default array[]::text[];
alter table learning_policies add column if not exists
    require_review_for_constrained_visibility boolean not null default true;

-- Runtime is an explicit, expiring lease. The current state machine has no safe reviewed-Runtime
-- path, so normalize any legacy configuration before freezing the first revision snapshot.
update learning_policies set
    require_human_targets=array_remove(require_human_targets,'runtime'),
    updated_by='migration:0047',updated_at=now()
where require_human_targets @> array['runtime']::text[];

alter table learning_policies add constraint learning_policy_revision_positive
    check (revision > 0) not valid;
alter table learning_policies add constraint learning_policy_targets_valid
    check (
        require_human_targets <@ array[
            'organization','behavior','adaptive','runtime','metrics','knowledge_suggestion'
        ]::text[]
        and blocked_targets <@ array[
            'organization','behavior','adaptive','runtime','metrics','knowledge_suggestion'
        ]::text[]
        and require_human_targets @> array['knowledge_suggestion']::text[]
        and not (require_human_targets @> array['runtime']::text[])
    ) not valid;

insert into learning_policies (org_id,policy_key,updated_by)
select id,'default','migration:0047' from orgs
on conflict (org_id,policy_key) do nothing;

insert into learning_policies (org_id,policy_key,updated_by)
select distinct org_id,policy_key,'migration:0047' from learning_objects
on conflict (org_id,policy_key) do nothing;

create table if not exists learning_policy_revisions (
    org_id          text not null,
    policy_key      text not null,
    revision        bigint not null,
    schema_version  text not null,
    snapshot_known  boolean not null,
    policy_snapshot jsonb,
    recorded_by     text not null,
    change_reason   text not null,
    recorded_at     timestamptz not null default now(),
    primary key (org_id,policy_key,revision),
    constraint learning_policy_revision_number_valid check (revision >= 0),
    constraint learning_policy_snapshot_shape check (
        (snapshot_known and revision > 0 and policy_snapshot is not null
         and jsonb_typeof(policy_snapshot)='object')
        or (not snapshot_known and revision=0 and policy_snapshot is null)
    )
);

insert into learning_policy_revisions
    (org_id,policy_key,revision,schema_version,snapshot_known,policy_snapshot,
     recorded_by,change_reason,recorded_at)
select ref.org_id,ref.policy_key,0,'learning-policy.unknown',false,null,
       'migration:0047','legacy_unpinned',now()
from (
    select org_id,policy_key from learning_objects
    union
    select org_id,'default'::text from learning_runs
) ref
on conflict (org_id,policy_key,revision) do nothing;

insert into learning_policy_revisions
    (org_id,policy_key,revision,schema_version,snapshot_known,policy_snapshot,
     recorded_by,change_reason,recorded_at)
select p.org_id,p.policy_key,p.revision,'learning-policy.v1',true,
       jsonb_build_object(
           'learning_enabled',p.learning_enabled,
           'min_observations',p.min_observations,
           'min_distinct_days',p.min_distinct_days,
           'min_confidence_bp',p.min_confidence_bp,
           'max_noise_bp',p.max_noise_bp,
           'max_conflict_bp',p.max_conflict_bp,
           'min_business_value_bp',p.min_business_value_bp,
           'temporary_ttl_hours',p.temporary_ttl_hours,
           'max_temporary_ttl_hours',p.max_temporary_ttl_hours,
           'require_human_targets',to_jsonb(p.require_human_targets),
           'blocked_targets',to_jsonb(p.blocked_targets),
           'blocked_subject_prefixes',to_jsonb(p.blocked_subject_prefixes),
           'require_review_for_constrained_visibility',
               p.require_review_for_constrained_visibility
       ),p.updated_by,'baseline_from_0045',p.updated_at
from learning_policies p
on conflict (org_id,policy_key,revision) do nothing;

alter table learning_policy_revisions add constraint learning_policy_revisions_org_cascade_fk
    foreign key (org_id) references orgs(id) on delete cascade not valid;

create or replace function reject_learning_policy_revision_mutation() returns trigger
language plpgsql as $$
begin
    -- Organization erasure remains authoritative: the parent row has already disappeared when
    -- its ON DELETE CASCADE reaches this trigger.  While the tenant exists, however, neither a
    -- direct UPDATE nor a direct DELETE may rewrite the policy audit ledger.
    if tg_op='DELETE' and not exists (select 1 from orgs where id=old.org_id) then
        return old;
    end if;
    raise exception 'learning policy revisions are immutable';
end;
$$;
drop trigger if exists learning_policy_revisions_immutable on learning_policy_revisions;
create trigger learning_policy_revisions_immutable
before update or delete on learning_policy_revisions
for each row execute function reject_learning_policy_revision_mutation();

-- Every current-policy write freezes its exact snapshot before the deferred pointer FK is checked.
create or replace function record_learning_policy_revision() returns trigger
language plpgsql as $$
begin
    if tg_op='UPDATE' and new.revision <= old.revision then
        raise exception 'learning policy revision must increase';
    end if;
    insert into learning_policy_revisions
        (org_id,policy_key,revision,schema_version,snapshot_known,policy_snapshot,
         recorded_by,change_reason,recorded_at)
    values (
        new.org_id,new.policy_key,new.revision,'learning-policy.v1',true,
        jsonb_build_object(
            'learning_enabled',new.learning_enabled,
            'min_observations',new.min_observations,
            'min_distinct_days',new.min_distinct_days,
            'min_confidence_bp',new.min_confidence_bp,
            'max_noise_bp',new.max_noise_bp,
            'max_conflict_bp',new.max_conflict_bp,
            'min_business_value_bp',new.min_business_value_bp,
            'temporary_ttl_hours',new.temporary_ttl_hours,
            'max_temporary_ttl_hours',new.max_temporary_ttl_hours,
            'require_human_targets',to_jsonb(new.require_human_targets),
            'blocked_targets',to_jsonb(new.blocked_targets),
            'blocked_subject_prefixes',to_jsonb(new.blocked_subject_prefixes),
            'require_review_for_constrained_visibility',
                new.require_review_for_constrained_visibility
        ),new.updated_by,
        case when tg_op='INSERT' then 'policy_created' else 'policy_updated' end,
        new.updated_at
    );
    return new;
end;
$$;

drop trigger if exists learning_policy_revision_writer on learning_policies;
create trigger learning_policy_revision_writer
after insert or update on learning_policies
for each row execute function record_learning_policy_revision();

alter table learning_policies add constraint learning_policies_current_revision_fk
    foreign key (org_id,policy_key,revision)
    references learning_policy_revisions(org_id,policy_key,revision)
    deferrable initially deferred not valid;

-- ── Weekly run authority ────────────────────────────────────────────────────────────────

alter table learning_runs add column if not exists policy_key text not null default 'default';
alter table learning_runs add column if not exists policy_revision bigint;
alter table learning_runs add column if not exists attempt_count int not null default 1;
alter table learning_runs add column if not exists last_error text;

update learning_runs set policy_revision=0 where policy_revision is null;
alter table learning_runs alter column policy_revision set not null;
alter table learning_runs add constraint learning_runs_attempts_positive
    check (attempt_count > 0) not valid;
alter table learning_runs add constraint learning_runs_policy_revision_nonnegative
    check (policy_revision >= 0) not valid;
alter table learning_runs add constraint learning_runs_failure_has_error
    check (status<>'failed' or nullif(btrim(last_error),'') is not null) not valid;
alter table learning_runs add constraint learning_runs_org_run_identity unique (org_id,run_id);
alter table learning_runs add constraint learning_runs_policy_revision_fk
    foreign key (org_id,policy_key,policy_revision)
    references learning_policy_revisions(org_id,policy_key,revision) not valid;
create index if not exists learning_runs_status_history
    on learning_runs (org_id,status,period_start desc);

-- ── LearningObject v2 envelope and lifecycle projection ─────────────────────────────────

alter table learning_objects add column if not exists policy_revision bigint;
alter table learning_objects add column if not exists independent_observations int;
alter table learning_objects add column if not exists first_seen_at timestamptz;
alter table learning_objects add column if not exists last_seen_at timestamptz;
alter table learning_objects add column if not exists trace_id text;
alter table learning_objects add column if not exists visibility jsonb;
alter table learning_objects add column if not exists lineage_complete boolean not null default false;
alter table learning_objects add column if not exists subject_principal text;
alter table learning_objects add column if not exists governance_verdict text;
alter table learning_objects add column if not exists promotion_state text;
alter table learning_objects add column if not exists supersedes_learning_id text;

update learning_objects
set policy_revision=coalesce(policy_revision,0),
    independent_observations=coalesce(independent_observations,0),
    first_seen_at=coalesce(first_seen_at,observed_at),
    last_seen_at=coalesce(last_seen_at,observed_at),
    trace_id=coalesce(nullif(payload->>'trace_id',''),
                      'ltrace_' || md5(org_id || ':' || learning_id)),
    visibility=coalesce(
        visibility,
        case when jsonb_typeof(payload->'visibility')='object' then payload->'visibility'
             else '{"scope":"private","principals":[],"derived_from":"legacy:learning-v1"}'::jsonb
        end)
where policy_revision is null or independent_observations is null or first_seen_at is null
   or last_seen_at is null or trace_id is null or visibility is null;

alter table learning_objects alter column policy_revision set not null;
alter table learning_objects alter column independent_observations set not null;
alter table learning_objects alter column first_seen_at set not null;
alter table learning_objects alter column last_seen_at set not null;
alter table learning_objects alter column trace_id set not null;
alter table learning_objects alter column visibility
    set default '{"scope":"private","principals":[],"derived_from":"missing:learning-lineage"}'::jsonb;
alter table learning_objects alter column visibility set not null;

alter table learning_objects add constraint learning_object_policy_revision_valid
    check (policy_revision>=0 and (schema_version='learning.v1' or policy_revision>0)) not valid;
alter table learning_objects add constraint learning_object_schema_version_valid
    check (schema_version in ('learning.v1','learning.v2')) not valid;
alter table learning_objects add constraint learning_object_independence_valid
    check (independent_observations>=0 and independent_observations<=observations) not valid;
alter table learning_objects add constraint learning_object_seen_window_valid
    check (first_seen_at<=last_seen_at and observed_at=last_seen_at) not valid;
alter table learning_objects add constraint learning_object_trace_required
    check (nullif(btrim(trace_id),'') is not null) not valid;
alter table learning_objects add constraint learning_object_visibility_valid
    check (jsonb_typeof(visibility)='object'
           and visibility->>'scope' in ('public','org','participants','private')
           and visibility ? 'principals'
           and jsonb_typeof(visibility->'principals')='array'
           and nullif(btrim(visibility->>'derived_from'),'') is not null) not valid;
alter table learning_objects add constraint learning_object_governance_verdict_valid
    check (governance_verdict is null
           or governance_verdict in ('allowed','requires_approval','forbidden','forget')) not valid;
alter table learning_objects add constraint learning_object_promotion_state_valid
    check (promotion_state is null
           or promotion_state in ('temporary','permanent','human_review')) not valid;
alter table learning_objects add constraint learning_object_promotion_target_valid
    check (promotion_state is null or promotion_state<>'temporary' or target_brain='runtime') not valid;
alter table learning_objects add constraint learning_object_not_self_superseding
    check (supersedes_learning_id is null or supersedes_learning_id<>learning_id) not valid;
alter table learning_objects add constraint learning_object_v2_projection_matches_payload
    check (schema_version<>'learning.v2' or coalesce((
        payload->>'schema_version'='learning.v2'
        and payload->>'org_id'=org_id
        and payload->>'unit'=unit_name
        and payload->>'target'=target_brain
        and payload->>'subject_key'=subject_key
        and payload->>'policy_key'=policy_key
        and (payload#>>'{observed_at,$datetime}')::timestamptz=observed_at
        and (payload#>>'{first_seen_at,$datetime}')::timestamptz=first_seen_at
        and (payload#>>'{last_seen_at,$datetime}')::timestamptz=last_seen_at
        and (payload#>>'{expires_at,$datetime}')::timestamptz is not distinct from expires_at
        and payload->>'trace_id'=trace_id
        and payload->'visibility'=visibility
        and (payload->>'lineage_complete')::boolean=lineage_complete
        and (payload->>'subject_principal') is not distinct from subject_principal
        and (payload->'evidence'->>'observations')::int=observations
        and (payload->'evidence'->>'distinct_days')::int=distinct_days
        and (payload->'evidence'->>'positive')::int=positive_evidence
        and (payload->'evidence'->>'negative')::int=negative_evidence
        and (payload->'evidence'->>'confidence_bp')::int=confidence_bp
        and (payload->'evidence'->>'noise_bp')::int=noise_bp
        and (payload->'evidence'->>'conflict_bp')::int=conflict_bp
        and (payload->'evidence'->>'business_value_bp')::int=business_value_bp
        and jsonb_typeof(payload->'evidence'->'independent_refs')='array'
        and jsonb_array_length(payload->'evidence'->'independent_refs')
            = independent_observations
    ),false)) not valid;

alter table learning_objects add constraint learning_objects_lineage_identity
    unique (org_id,target_brain,subject_key,learning_id);
alter table learning_objects add constraint learning_objects_policy_revision_fk
    foreign key (org_id,policy_key,policy_revision)
    references learning_policy_revisions(org_id,policy_key,revision) not valid;
alter table learning_objects add constraint learning_objects_source_run_fk
    foreign key (org_id,source_run_id) references learning_runs(org_id,run_id)
    on delete cascade not valid;
alter table learning_objects add constraint learning_objects_supersedes_fk
    foreign key (org_id,target_brain,subject_key,supersedes_learning_id)
    references learning_objects(org_id,target_brain,subject_key,learning_id) not valid;

create index if not exists learning_objects_trace on learning_objects (org_id,trace_id);
create index if not exists learning_objects_run on learning_objects (org_id,source_run_id)
    where source_run_id is not null;
create index if not exists learning_objects_policy
    on learning_objects (org_id,policy_key,policy_revision);
create index if not exists learning_objects_visibility_scope
    on learning_objects (org_id,(visibility->>'scope'));

-- ── Normalized enterprise-event input seam ──────────────────────────────────────────────

create table if not exists learning_event_inbox (
    org_id           text not null,
    event_id         text not null,
    pattern_key      text not null,
    kind             text not null,
    actor_key        text,
    value            jsonb not null default '{}',
    explicit_memory  boolean not null default false,
    occurred_at      timestamptz not null,
    expires_at       timestamptz,
    trace_id         text not null,
    visibility       jsonb not null,
    independence_key text not null,
    primary key (org_id,event_id),
    constraint learning_event_value_object check (jsonb_typeof(value)='object'),
    constraint learning_event_memory_lease check (
        (explicit_memory and kind='temporary_memory' and expires_at is not null
         and expires_at>occurred_at)
        or (not explicit_memory and expires_at is null)),
    constraint learning_event_visibility_valid check (
        jsonb_typeof(visibility)='object'
        and visibility->>'scope' in ('public','org','participants','private')
        and visibility ? 'principals'
        and jsonb_typeof(visibility->'principals')='array'
        and nullif(btrim(visibility->>'derived_from'),'') is not null),
    constraint learning_event_lineage_required check (
        nullif(btrim(trace_id),'') is not null
        and nullif(btrim(independence_key),'') is not null)
);
alter table learning_event_inbox add constraint learning_event_inbox_org_cascade_fk
    foreign key (org_id) references orgs(id) on delete cascade not valid;
create index if not exists learning_event_inbox_window
    on learning_event_inbox (org_id,occurred_at desc,event_id);
create index if not exists learning_event_inbox_expiry
    on learning_event_inbox (org_id,expires_at) where explicit_memory and expires_at is not null;

-- ── Sanitized input/preflight rejection audit ───────────────────────────────────────────

-- Owner authority is frozen by the authenticated feedback writer, outside caller JSON.
alter table card_feedback_revisions add column if not exists
    organization_authorized boolean not null default false;
alter table card_feedback_revisions add constraint feedback_org_authority_shape
    check (not organization_authorized
           or coalesce(detail->'preference'->>'scope'='organization',false)) not valid;

create table if not exists learning_input_rejections (
    org_id               text not null,
    rejection_id         text not null,
    source_run_id        text,
    source_kind          text not null default 'proposal',
    source_ref           text,
    payload_hash         text,
    proposed_learning_id text,
    semantic_hash        text,
    unit_name            text,
    target_brain         text,
    subject_key          text,
    trace_id             text,
    visibility           jsonb,
    reason_code          text not null,
    detail               jsonb not null default '{}',
    occurred_at          timestamptz not null default now(),
    primary key (org_id,rejection_id),
    constraint learning_input_rejection_identity check (
        source_ref is not null or payload_hash is not null
        or proposed_learning_id is not null or semantic_hash is not null),
    constraint learning_input_rejection_payload_hash check (
        payload_hash is null or payload_hash ~ '^[0-9a-f]{64}$'),
    constraint learning_input_rejection_semantic_hash check (
        semantic_hash is null or semantic_hash ~ '^[0-9a-f]{64}$'),
    constraint learning_input_rejection_reason check (
        nullif(btrim(source_kind),'') is not null and nullif(btrim(reason_code),'') is not null),
    constraint learning_input_rejection_visibility check (
        visibility is null or (jsonb_typeof(visibility)='object'
            and visibility->>'scope' in ('public','org','participants','private')
            and jsonb_typeof(coalesce(visibility->'principals','[]'::jsonb))='array'))
);
alter table learning_input_rejections add constraint learning_input_rejections_org_cascade_fk
    foreign key (org_id) references orgs(id) on delete cascade not valid;
alter table learning_input_rejections add constraint learning_input_rejections_run_fk
    foreign key (org_id,source_run_id) references learning_runs(org_id,run_id)
    on delete cascade not valid;
create unique index if not exists learning_input_rejections_source_once
    on learning_input_rejections (org_id,source_kind,source_ref,payload_hash,reason_code)
    where source_ref is not null and payload_hash is not null;
create unique index if not exists learning_input_rejections_proposal_once
    on learning_input_rejections (org_id,proposed_learning_id,reason_code)
    where proposed_learning_id is not null;
create index if not exists learning_input_rejections_run
    on learning_input_rejections (org_id,source_run_id,occurred_at,rejection_id);
create index if not exists learning_input_rejections_reason
    on learning_input_rejections (org_id,reason_code,occurred_at desc);

-- ── Published artifact envelope and append-only supersession lineage ─────────────────────

alter table learned_brain_entries add column if not exists visibility jsonb;
alter table learned_brain_entries add column if not exists trace_id text;
alter table learned_brain_entries add column if not exists supersedes_entry_id text;
alter table temporary_memories add column if not exists visibility jsonb;
alter table temporary_memories add column if not exists trace_id text;
alter table knowledge_suggestions add column if not exists visibility jsonb;
alter table knowledge_suggestions add column if not exists trace_id text;
alter table learning_metrics add column if not exists visibility jsonb;
alter table learning_metrics add column if not exists trace_id text;

update learned_brain_entries e set visibility=o.visibility,trace_id=o.trace_id
from learning_objects o
where o.org_id=e.org_id and o.learning_id=e.learning_id
  and (e.visibility is null or e.trace_id is null);
update temporary_memories m set visibility=o.visibility,trace_id=o.trace_id
from learning_objects o
where o.org_id=m.org_id and o.learning_id=m.learning_id
  and (m.visibility is null or m.trace_id is null);
update knowledge_suggestions s set visibility=o.visibility,trace_id=o.trace_id
from learning_objects o
where o.org_id=s.org_id and o.learning_id=s.learning_id
  and (s.visibility is null or s.trace_id is null);
update learning_metrics m set visibility=o.visibility,trace_id=o.trace_id
from learning_objects o
where o.org_id=m.org_id and o.learning_id=m.learning_id
  and (m.visibility is null or m.trace_id is null);

update learned_brain_entries set
    visibility=coalesce(visibility,'{"scope":"private","principals":[],"derived_from":"legacy:learning-v1"}'::jsonb),
    trace_id=coalesce(trace_id,'ltrace_' || md5(org_id || ':' || learning_id));
update temporary_memories set
    visibility=coalesce(visibility,'{"scope":"private","principals":[],"derived_from":"legacy:learning-v1"}'::jsonb),
    trace_id=coalesce(trace_id,'ltrace_' || md5(org_id || ':' || learning_id));
update knowledge_suggestions set
    visibility=coalesce(visibility,'{"scope":"private","principals":[],"derived_from":"legacy:learning-v1"}'::jsonb),
    trace_id=coalesce(trace_id,'ltrace_' || md5(org_id || ':' || learning_id));
update learning_metrics set
    visibility=coalesce(visibility,'{"scope":"private","principals":[],"derived_from":"legacy:learning-v1"}'::jsonb),
    trace_id=coalesce(trace_id,'ltrace_' || md5(org_id || ':' || learning_id));

alter table learned_brain_entries alter column visibility set not null;
alter table learned_brain_entries alter column trace_id set not null;
alter table temporary_memories alter column visibility set not null;
alter table temporary_memories alter column trace_id set not null;
alter table knowledge_suggestions alter column visibility set not null;
alter table knowledge_suggestions alter column trace_id set not null;
alter table learning_metrics alter column visibility set not null;
alter table learning_metrics alter column trace_id set not null;

update learned_brain_entries e set supersedes_entry_id=(
    select p.entry_id from learned_brain_entries p
    where p.org_id=e.org_id and p.brain=e.brain and p.subject_key=e.subject_key
      and p.version<e.version order by p.version desc limit 1)
where e.supersedes_entry_id is null and exists (
    select 1 from learned_brain_entries p
    where p.org_id=e.org_id and p.brain=e.brain and p.subject_key=e.subject_key
      and p.version<e.version);

update learning_objects o set supersedes_learning_id=(
    select prior.learning_id
    from learned_brain_entries current_entry join learned_brain_entries prior
      on prior.org_id=current_entry.org_id
     and prior.entry_id=current_entry.supersedes_entry_id
    where current_entry.org_id=o.org_id and current_entry.learning_id=o.learning_id
    order by current_entry.version desc limit 1)
where o.supersedes_learning_id is null and exists (
    select 1 from learned_brain_entries current_entry
    where current_entry.org_id=o.org_id and current_entry.learning_id=o.learning_id
      and current_entry.supersedes_entry_id is not null);

alter table learned_brain_entries add constraint learned_brain_version_positive
    check (version>0) not valid;
alter table learned_brain_entries add constraint learned_brain_visibility_valid
    check (jsonb_typeof(visibility)='object'
           and visibility->>'scope' in ('public','org','participants','private')
           and visibility ? 'principals'
           and jsonb_typeof(visibility->'principals')='array'
           and nullif(btrim(visibility->>'derived_from'),'') is not null) not valid;
alter table learned_brain_entries add constraint learned_brain_trace_required
    check (nullif(btrim(trace_id),'') is not null) not valid;
alter table learned_brain_entries add constraint learned_brain_not_self_superseding
    check (supersedes_entry_id is null or supersedes_entry_id<>entry_id) not valid;
alter table learned_brain_entries add constraint learned_brain_end_shape
    check ((active and ended_at is null and ended_reason is null)
           or (not active and ended_at is not null
               and ended_reason in ('superseded','rolled_back','forgotten'))) not valid;
alter table learned_brain_entries add constraint learned_brain_lineage_identity
    unique (org_id,brain,subject_key,entry_id);
alter table learned_brain_entries add constraint learned_brain_supersedes_fk
    foreign key (org_id,brain,subject_key,supersedes_entry_id)
    references learned_brain_entries(org_id,brain,subject_key,entry_id) not valid;
create index if not exists learned_brain_by_learning
    on learned_brain_entries (org_id,learning_id);

alter table temporary_memories add constraint temporary_memory_visibility_valid
    check (jsonb_typeof(visibility)='object'
           and visibility->>'scope' in ('public','org','participants','private')
           and visibility ? 'principals'
           and jsonb_typeof(visibility->'principals')='array'
           and nullif(btrim(visibility->>'derived_from'),'') is not null) not valid;
alter table temporary_memories add constraint temporary_memory_trace_required
    check (nullif(btrim(trace_id),'') is not null) not valid;
alter table knowledge_suggestions add constraint knowledge_suggestion_visibility_valid
    check (jsonb_typeof(visibility)='object'
           and visibility->>'scope' in ('public','org','participants','private')
           and visibility ? 'principals'
           and jsonb_typeof(visibility->'principals')='array'
           and nullif(btrim(visibility->>'derived_from'),'') is not null) not valid;
alter table knowledge_suggestions add constraint knowledge_suggestion_trace_required
    check (nullif(btrim(trace_id),'') is not null) not valid;
alter table learning_metrics add constraint learning_metric_visibility_valid
    check (jsonb_typeof(visibility)='object'
           and visibility->>'scope' in ('public','org','participants','private')
           and visibility ? 'principals'
           and jsonb_typeof(visibility->'principals')='array'
           and nullif(btrim(visibility->>'derived_from'),'') is not null) not valid;
alter table learning_metrics add constraint learning_metric_trace_required
    check (nullif(btrim(trace_id),'') is not null) not valid;

-- ── Same-tenant artifact lineage ────────────────────────────────────────────────────────

alter table learning_transitions add constraint learning_transitions_object_fk
    foreign key (org_id,learning_id) references learning_objects(org_id,learning_id)
    on delete cascade not valid;
alter table learned_brain_entries add constraint learned_brain_entries_object_fk
    foreign key (org_id,learning_id) references learning_objects(org_id,learning_id)
    on delete cascade not valid;
alter table temporary_memories add constraint temporary_memories_object_fk
    foreign key (org_id,learning_id) references learning_objects(org_id,learning_id)
    on delete cascade not valid;
alter table knowledge_suggestions add constraint knowledge_suggestions_object_fk
    foreign key (org_id,learning_id) references learning_objects(org_id,learning_id)
    on delete cascade not valid;
alter table learning_metrics add constraint learning_metrics_object_fk
    foreign key (org_id,learning_id) references learning_objects(org_id,learning_id)
    on delete cascade not valid;
create index if not exists learning_metrics_by_learning on learning_metrics (org_id,learning_id);

-- Policy and evaluation clocks are lifecycle inputs, not LearningObject identity.  Keep one
-- append-only decision row per immutable object per claimed run so a held object can be safely
-- re-evaluated after policy changes without rewriting its evidence envelope.
alter table learning_runs add constraint learning_runs_evaluation_policy_identity
    unique (org_id,run_id,policy_key,policy_revision,evaluation_time);

create table if not exists learning_object_evaluations (
    org_id          text not null,
    run_id          text not null,
    learning_id     text not null,
    policy_key      text not null,
    policy_revision bigint not null,
    evaluation_time timestamptz not null,
    prior_state     text not null,
    result_state    text not null,
    reason_code     text not null,
    object_inserted boolean not null,
    created_at      timestamptz not null default clock_timestamp(),
    primary key (org_id,run_id,learning_id),
    foreign key (org_id,run_id,policy_key,policy_revision,evaluation_time)
        references learning_runs(
            org_id,run_id,policy_key,policy_revision,evaluation_time) on delete cascade,
    foreign key (org_id,learning_id)
        references learning_objects(org_id,learning_id) on delete cascade,
    constraint learning_object_evaluation_states check (
        prior_state in ('observed','candidate','validated','governed','temporary',
                        'human_review','promoted','published','rejected','expired',
                        'superseded','rolled_back')
        and result_state in ('observed','candidate','validated','governed','temporary',
                             'human_review','promoted','published','rejected','expired',
                             'superseded','rolled_back')),
    constraint learning_object_evaluation_reason check (nullif(btrim(reason_code),'') is not null),
    constraint learning_object_evaluation_policy_revision check (policy_revision >= 0)
);

alter table learning_object_evaluations
    add constraint learning_object_evaluations_org_cascade_fk
    foreign key (org_id) references orgs(id) on delete cascade;

create index if not exists learning_object_evaluations_history
    on learning_object_evaluations (org_id,learning_id,evaluation_time desc);

comment on table learning_policy_revisions is
  'Immutable policy snapshots. Revision 0 is the explicit legacy_unpinned sentinel.';
comment on table learning_event_inbox is
  'Normalized tenant-scoped enterprise events consumed by Layer 6; explicit memory requires TTL.';
comment on table learning_input_rejections is
  'Sanitized malformed-input and preflight rejection audit. Raw input payloads are forbidden.';
comment on table learning_object_evaluations is
  'Append-only per-run policy/time decisions for immutable LearningObjects, including held re-evaluations.';
comment on column learned_brain_entries.supersedes_entry_id is
  'Previous version for the same tenant, brain and subject; future versions use max(version)+1.';
