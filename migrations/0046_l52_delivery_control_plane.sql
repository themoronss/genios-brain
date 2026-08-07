-- GeniOS Engine · Atlas Layer 5.2 — execution-bound delivery control plane.
--
-- Layer 5 owns the commitment and its work owner. Layer 5.2 owns the final audience,
-- destination, channel, timing, interruptibility, scheduling and delivery lifecycle. Older
-- rows remain readable, but this is deliberately NOT a mixed-worker migration: stop legacy
-- producers/drainers and reconcile their last provider timeout before applying it. The table lock
-- fences database writers during adoption; it cannot fence an already-running external POST.

lock table delivery_outbox in share row exclusive mode;

-- Cards are a presentation of an ExecutionObject, never independent outbound authority.
alter table cards add column if not exists execution_id text;

-- New writes seal provider credentials with GENIOS_CRYPTO_KEY. Plain config remains during the
-- rolling migration only so already-configured tenants can be read and re-saved safely.
alter table org_channels add column if not exists config_encrypted bytea;
alter table agent_registry add column if not exists webhook_config_encrypted bytea;

update cards k
set execution_id = (
    select x.execution_id
    from executions x
    where x.org_id = k.org_id and x.signal_id = k.signal_id
    order by (x.closed_at is null) desc, x.created_at desc, x.execution_id
    limit 1
)
where k.execution_id is null
  and exists (
      select 1 from executions x
      where x.org_id = k.org_id and x.signal_id = k.signal_id
  );

create index if not exists cards_by_execution
    on cards (org_id, execution_id) where execution_id is not null;

alter table cards add constraint cards_execution_fk
    foreign key (org_id, execution_id) references executions (org_id, execution_id)
    on delete cascade not valid;

-- The immutable DeliveryObject materialised on the outbox row.
alter table delivery_outbox add column if not exists execution_id text;
alter table delivery_outbox add column if not exists execution_hash text;
alter table delivery_outbox add column if not exists execution_event_id text;
alter table delivery_outbox add column if not exists delivery_kind text not null default 'legacy_card';
alter table delivery_outbox add column if not exists audience text;
alter table delivery_outbox add column if not exists destination text;
alter table delivery_outbox add column if not exists format_kind text;
alter table delivery_outbox add column if not exists route_reason text;
alter table delivery_outbox add column if not exists dedupe_key text;
alter table delivery_outbox add column if not exists priority_class text not null default 'medium';
alter table delivery_outbox add column if not exists priority_rank smallint not null default 3;
alter table delivery_outbox add column if not exists daily_budget smallint not null default 7;
alter table delivery_outbox add column if not exists source_payload jsonb;
alter table delivery_outbox add column if not exists route_plan jsonb not null default '[]';
alter table delivery_outbox add column if not exists route_index int not null default 0;
alter table delivery_outbox add column if not exists claim_token text;
alter table delivery_outbox add column if not exists claimed_at timestamptz;
alter table delivery_outbox add column if not exists claimed_until timestamptz;
alter table delivery_outbox add column if not exists retry_generation int not null default 0;
alter table delivery_outbox add column if not exists generation_attempts int not null default 0;
alter table delivery_outbox add column if not exists destination_fingerprint text;
alter table delivery_outbox add column if not exists control_failures int not null default 0;
alter table delivery_outbox add column if not exists legacy_reconciliation_required boolean
    not null default false;
alter table delivery_outbox add column if not exists manual_replay_approved_at timestamptz;

-- A legacy worker could have POSTed and crashed before incrementing its aggregate attempt count.
-- Therefore *every* pre-control-plane pending row is ambiguous, including attempts=0. Quarantine
-- it for an owner's explicit risk acknowledgement instead of guessing that zero means unsent.
update delivery_outbox
set legacy_reconciliation_required = true,
    status = 'queued',
    claim_token = null,
    claimed_at = null,
    claimed_until = null
where delivery_kind = 'legacy_card' and status in ('queued', 'in_flight');

-- Old terminal rows are not automatically retried, but their missing physical ledger makes an
-- owner replay equally ambiguous. Preserve the terminal status and require the same explicit ack.
update delivery_outbox
set legacy_reconciliation_required = true
where delivery_kind = 'legacy_card' and status = 'failed_terminal';

-- Transport state remains in status. lifecycle_status records the Atlas engagement lifecycle.
alter table delivery_outbox add column if not exists lifecycle_status text not null default 'queued';
alter table delivery_outbox add column if not exists viewed_at timestamptz;
alter table delivery_outbox add column if not exists ignored_at timestamptz;
alter table delivery_outbox add column if not exists accepted_at timestamptz;
alter table delivery_outbox add column if not exists executed_at timestamptz;
alter table delivery_outbox add column if not exists expired_at timestamptz;
alter table delivery_outbox add column if not exists updated_at timestamptz not null default now();

update delivery_outbox
set lifecycle_status = case status
    when 'delivered' then 'delivered'
    when 'failed_terminal' then 'failed'
    when 'cancelled' then 'cancelled'
    when 'suppressed' then 'suppressed'
    else 'queued'
end
where lifecycle_status = 'queued';

update delivery_outbox
set priority_class = case band
    when 'critical' then 'critical'
    when 'high' then 'high'
    when 'low' then 'low'
    when 'background' then 'background'
    else 'medium'
end,
priority_rank = case band
    when 'critical' then 5
    when 'high' then 4
    when 'medium' then 3
    when 'standard' then 3
    when 'low' then 2
    when 'background' then 1
    else 3
end
where delivery_kind = 'legacy_card';

alter table delivery_outbox add constraint delivery_outbox_route_index_nonnegative
    check (route_index >= 0) not valid;
alter table delivery_outbox add constraint delivery_outbox_retry_generation_nonnegative
    check (retry_generation >= 0 and generation_attempts >= 0) not valid;
alter table delivery_outbox add constraint delivery_outbox_control_failures_bounded
    check (control_failures between 0 and 5) not valid;
alter table delivery_outbox add constraint delivery_outbox_destination_fingerprint_valid
    check (destination_fingerprint is null or destination_fingerprint ~ '^[0-9a-f]{64}$') not valid;
alter table delivery_outbox add constraint delivery_outbox_priority_rank_valid
    check (priority_rank between 1 and 5) not valid;
alter table delivery_outbox add constraint delivery_outbox_priority_class_valid
    check (priority_class in ('critical','high','medium','low','background')) not valid;
alter table delivery_outbox add constraint delivery_outbox_daily_budget_valid
    check (daily_budget between 1 and 15) not valid;
alter table delivery_outbox add constraint delivery_outbox_lifecycle_valid
    check (lifecycle_status in (
        'queued','deferred','delivered','viewed','ignored','accepted','executed',
        'failed','expired','suppressed','cancelled'
    )) not valid;
alter table delivery_outbox add constraint delivery_outbox_execution_lineage_required
    check (
        delivery_kind = 'legacy_card'
        or (execution_id is not null and execution_hash is not null and dedupe_key is not null)
    ) not valid;
alter table delivery_outbox add constraint delivery_outbox_claim_shape_valid
    check (
        (status = 'in_flight' and claim_token is not null
         and claimed_at is not null and claimed_until is not null)
        or
        (status <> 'in_flight' and claim_token is null
         and claimed_at is null and claimed_until is null)
    ) not valid;
alter table delivery_outbox add constraint delivery_outbox_route_cursor_valid
    check (
        jsonb_typeof(route_plan) = 'array'
        and (jsonb_array_length(route_plan) = 0 or route_index < jsonb_array_length(route_plan))
    ) not valid;
alter table delivery_outbox add constraint delivery_outbox_lifecycle_timestamp_valid
    check (
        (lifecycle_status not in ('delivered','viewed','ignored','accepted','executed')
         or delivered_at is not null)
        and
        (lifecycle_status <> 'viewed' or viewed_at is not null)
        and (lifecycle_status <> 'ignored' or ignored_at is not null)
        and (lifecycle_status <> 'accepted' or accepted_at is not null)
        and (lifecycle_status <> 'executed' or executed_at is not null)
        and (lifecycle_status <> 'expired' or expired_at is not null)
    ) not valid;

alter table delivery_outbox add constraint delivery_outbox_execution_fk
    foreign key (org_id, execution_id) references executions (org_id, execution_id)
    on delete cascade not valid;

-- One logical insight/event creates one delivery even when ten destinations are available.
create unique index if not exists delivery_outbox_logical_once
    on delivery_outbox (org_id, dedupe_key) where dedupe_key is not null;
create unique index if not exists delivery_outbox_org_identity
    on delivery_outbox (org_id, id);

-- Critical work wins among rows that are already due; due-time still prevents early sends.
create index if not exists delivery_outbox_priority_due
    on delivery_outbox (priority_rank desc, next_attempt_at, id)
    where status in ('queued', 'in_flight');

create index if not exists delivery_outbox_by_execution
    on delivery_outbox (org_id, execution_id, created_at)
    where execution_id is not null;

-- Append-only lifecycle evidence. Idempotency is supplied by the client/action source, so a
-- retried tap or webhook cannot count twice in analytics or Layer 6.
create table if not exists delivery_events (
    event_id        text primary key,
    org_id          text not null,
    delivery_id     text not null,
    event_type      text not null,
    reason_code     text not null,
    actor_id        text not null,
    idempotency_key text not null,
    metadata        jsonb not null default '{}',
    occurred_at     timestamptz not null default now(),
    constraint delivery_event_type_valid check (event_type in (
        'queued','deferred','delivered','viewed','ignored','accepted','executed',
        'failed','expired','suppressed','cancelled'
    )),
    unique (org_id, delivery_id, idempotency_key)
);

create index if not exists delivery_events_by_delivery
    on delivery_events (org_id, delivery_id, occurred_at, event_id);
create index if not exists delivery_events_analytics
    on delivery_events (org_id, event_type, occurred_at);

alter table delivery_events add constraint delivery_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_events add constraint delivery_events_outbox_cascade_fk
    foreign key (org_id, delivery_id) references delivery_outbox (org_id, id)
    on delete cascade not valid;

-- Every provider call is retained. The outbox is the logical intent; these rows are physical
-- attempts, which is what makes recovery and channel performance auditable without overwriting
-- the previous error on each retry.
create table if not exists delivery_attempts (
    attempt_id          text primary key,
    org_id              text not null,
    delivery_id         text not null,
    attempt_number      int not null,
    retry_generation    int not null,
    channel             text not null,
    destination_fingerprint text not null,
    claim_token         text not null,
    idempotency_key     text not null,
    outcome             text not null default 'started',
    retryable           boolean,
    provider_message_id text,
    http_status         int,
    retry_after_seconds int,
    error_class         text,
    detail              text,
    started_at          timestamptz not null,
    completed_at        timestamptz,
    constraint delivery_attempt_number_positive check (attempt_number > 0),
    constraint delivery_attempt_generation_nonnegative check (retry_generation >= 0),
    constraint delivery_attempt_outcome_valid check
        (outcome in ('started','delivered','retryable_failure','terminal_failure','unknown')),
    constraint delivery_attempt_completion_valid check (
        (outcome = 'started' and completed_at is null)
        or (outcome <> 'started' and completed_at is not null)
    ),
    unique (delivery_id, attempt_number),
    unique (claim_token)
);

create index if not exists delivery_attempts_by_delivery
    on delivery_attempts (org_id, delivery_id, attempt_number);

alter table delivery_attempts add constraint delivery_attempts_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_attempts add constraint delivery_attempts_outbox_cascade_fk
    foreign key (org_id, delivery_id) references delivery_outbox (org_id, id)
    on delete cascade not valid;

-- Postgres is the correctness authority for attention quotas. Daily budgets use a fixed local-day
-- row. Hourly reservations use exact timestamps plus a transaction advisory lock and a rolling
-- sum, so provider calls that straddle an epoch-hour boundary cannot admit a second full bucket.
create table if not exists delivery_rate_windows (
    org_id        text not null,
    recipient     text not null,
    channel_class text not null,
    window_start  timestamptz not null,
    window_seconds int not null,
    used          int not null default 0,
    updated_at    timestamptz not null default now(),
    primary key (org_id, recipient, channel_class, window_start),
    constraint delivery_rate_window_positive check (window_seconds > 0 and used >= 0)
);

create index if not exists delivery_rate_windows_expiry
    on delivery_rate_windows (window_start, window_seconds);

alter table delivery_rate_windows add constraint delivery_rate_windows_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

-- Adopt already-delivered attention before v2 workers resume. Without this baseline, concurrent
-- post-upgrade drains would see a fresh atomic table and could exceed both the rolling hour and
-- the recipient's current local-day budget. Each delivery keeps its exact timestamp so the
-- rolling window expires at the same instant as the historical send.
insert into delivery_rate_windows
    (org_id,recipient,channel_class,window_start,window_seconds,used)
select org_id,
       case when channel in ('slack','teams') then '*' else coalesce(recipient,'*') end,
       channel_class, delivered_at, 3600, count(*)::int
from delivery_outbox
where status='delivered' and delivered_at>now()-interval '1 hour'
  and channel_class='chat'
group by org_id,
         case when channel in ('slack','teams') then '*' else coalesce(recipient,'*') end,
         channel_class, delivered_at
on conflict (org_id,recipient,channel_class,window_start) do update
set used=delivery_rate_windows.used+excluded.used, updated_at=now();

with delivered_local as (
    select d.org_id,coalesce(d.recipient,'*') as recipient,d.delivered_at,
           coalesce((
               select p.tz_name
               from delivery_preferences p
               where p.org_id=d.org_id and p.tz_name is not null
                 and p.seat_id in (coalesce(d.recipient,'*'),'*')
                 and p.channel in (d.channel,'*')
                 and exists (select 1 from pg_timezone_names tz where tz.name=p.tz_name)
               order by case
                   when p.seat_id=coalesce(d.recipient,'*') and p.channel=d.channel then 0
                   when p.seat_id=coalesce(d.recipient,'*') and p.channel='*' then 1
                   when p.seat_id='*' and p.channel=d.channel then 2
                   else 3 end
               limit 1
           ),'UTC') as tz_name
    from delivery_outbox d
    where d.status='delivered' and d.channel_class='chat'
      and d.delivered_at>now()-interval '26 hours'
), current_day as (
    select org_id,recipient,delivered_at,tz_name,
           date_trunc('day',now() at time zone tz_name) at time zone tz_name as window_start,
           (date_trunc('day',now() at time zone tz_name)+interval '1 day')
               at time zone tz_name as window_end
    from delivered_local
)
insert into delivery_rate_windows
    (org_id,recipient,channel_class,window_start,window_seconds,used)
select org_id,recipient,'daily',window_start,
       greatest(1,extract(epoch from (window_end-window_start))::int),count(*)::int
from current_day
where delivered_at>=window_start
group by org_id,recipient,window_start,window_end
on conflict (org_id,recipient,channel_class,window_start) do update
set used=delivery_rate_windows.used+excluded.used, updated_at=now();

-- A malformed frozen ExecutionObject cannot be turned into a delivery safely. Keep that failure
-- durable and tenant-scoped instead of retrying invisibly on every heartbeat. A later repaired
-- row is retried normally and the orchestrator marks this record resolved.
create table if not exists delivery_materialization_failures (
    org_id             text not null,
    execution_id       text not null,
    execution_event_id text not null,
    error_class        text not null,
    detail             text not null,
    occurrences        int not null default 1,
    first_seen_at      timestamptz not null,
    last_seen_at       timestamptz not null,
    resolved_at        timestamptz,
    primary key (org_id, execution_id, execution_event_id),
    constraint delivery_materialization_occurrences_positive check (occurrences > 0)
);

create index if not exists delivery_materialization_unresolved
    on delivery_materialization_failures (org_id, last_seen_at desc)
    where resolved_at is null;

alter table delivery_materialization_failures
    add constraint delivery_materialization_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_materialization_failures
    add constraint delivery_materialization_execution_cascade_fk
    foreign key (org_id, execution_id) references executions (org_id, execution_id)
    on delete cascade not valid;

comment on column executions.assignee is
  'Layer 5 work owner and Layer 5.2 audience seed; never final delivery authority.';
comment on column executions.channel_id is
  'Deprecated ExecutionObject v1 delivery preference; Layer 5.2 resolves the final channel.';
comment on column executions.interrupt is
  'Deprecated ExecutionObject v1 salience hint; Layer 5.2 owns final interruptibility.';
comment on column delivery_outbox.dedupe_key is
  'Logical execution/event key. One insight across many destinations creates one delivery.';
comment on column delivery_outbox.route_plan is
  'Deterministic primary-to-fallback channel ladder selected by Layer 5.2.';
comment on column delivery_outbox.lifecycle_status is
  'Public delivery lifecycle, independent of transport retry state in status.';
comment on column delivery_outbox.claim_token is
  'Fencing token. Only the worker holding this token may complete the current attempt.';
comment on column delivery_outbox.destination_fingerprint is
  'Non-secret hash of the exact provider destination/config bound to the retry generation.';
comment on column delivery_outbox.control_failures is
  'Bounded consecutive internal admission/projection failures; does not count provider attempts.';
comment on column delivery_outbox.legacy_reconciliation_required is
  'True for pending or terminal-failed rows present at the v2 cutover; owner must acknowledge possible prior delivery before replay.';
comment on column delivery_outbox.manual_replay_approved_at is
  'Audit timestamp for explicit owner acknowledgement of ambiguous legacy delivery risk.';
comment on column org_channels.config_encrypted is
  'Fernet-sealed provider credentials. config contains non-secret routing metadata only for new writes.';
