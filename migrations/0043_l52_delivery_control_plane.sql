-- GeniOS Engine · Layer 5.2 — the Delivery Control Plane (= the spec's 0046).
--
-- 0042 gave the gate a memory: somewhere to read a recipient's rules and write down its verdict.
-- This migration turns the outbox into a full control plane: one hash-verified ExecutionObject
-- becomes one durable, fenced, deduped logical delivery with its own engagement lifecycle, a
-- primary→fallback route ladder, a five-class scheduling priority, an atomic attention budget,
-- and an append-only history of every lifecycle event and every provider attempt.
--
-- Design points worth reading before touching anything:
--
--  1. ONE LOGICAL DELIVERY, ONE ROW. `delivery_id` is the insight's identity; ten destinations
--     produce one delivery with a route ladder, not ten impressions. `(org_id, dedupe_key)` is
--     globally unique for non-legacy rows so the deduper has a hard floor.
--  2. FENCING, NOT TRUST. A worker claims a row with an expiring token (`claimed_by`,
--     `claim_expires_at`, `fence_token`). The physical `started` attempt commits with the
--     attention reservation BEFORE network I/O, so a crash cannot create an invisible provider
--     call. An expired claim's unfinished attempt is marked `unknown`, never silently retried.
--  3. RETRY GENERATION SEPARATES SAFE REPLAY FROM AMBIGUITY. Provider idempotency key is
--     `delivery_id:retry_generation:channel`. A definite non-delivery bumps the generation; an
--     ambiguous outcome does not, because the person may already have been interrupted.
--  4. FAIL-CLOSED MATERIALISATION. A malformed frozen object lands in
--     `delivery_materialization_failures`, never crashing all tenants and never vanishing; it is
--     marked resolved once the source is repaired and materialised.
--
-- Every statement is idempotent (if-not-exists / guarded); compatibility constraints are NOT
-- VALID so representative legacy rows can be repaired without blocking rollout. New writes are
-- enforced. Cascade FKs follow 0033/0041/0042 convention.

-- ---------------------------------------------------------------------------------------
-- Cards become explicitly subordinate to an ExecutionObject: a card is a read-model and cannot
-- independently authorise an outward notification.
alter table cards add column if not exists execution_id text;

-- ---------------------------------------------------------------------------------------
-- The v2 DeliveryObject, projected onto the outbox row (contract: delivery-result.v2).
alter table delivery_outbox add column if not exists delivery_id text;             -- logical identity
alter table delivery_outbox add column if not exists execution_id text;            -- Layer 5 lineage
alter table delivery_outbox add column if not exists execution_hash text;          -- exact ExecutionObject hash
alter table delivery_outbox add column if not exists audience text;                -- owner|manager|admin|agent|...
alter table delivery_outbox add column if not exists destination text;             -- registered destination id
alter table delivery_outbox add column if not exists fmt text;                     -- inline_suggestion|card|chat_message|...
alter table delivery_outbox add column if not exists priority text not null default 'medium';  -- 5-class scheduling
alter table delivery_outbox add column if not exists daily_budget int;             -- snapshotted attention ceiling
alter table delivery_outbox add column if not exists source jsonb;                 -- frozen source payload
alter table delivery_outbox add column if not exists route_ladder jsonb;           -- ["slack","in_app"]
alter table delivery_outbox add column if not exists route_cursor int not null default 0;
alter table delivery_outbox add column if not exists retry_generation int not null default 0;
alter table delivery_outbox add column if not exists lifecycle text not null default 'queued';  -- engagement state
alter table delivery_outbox add column if not exists dedupe_key text;
alter table delivery_outbox add column if not exists claimed_by text;              -- fencing: worker id
alter table delivery_outbox add column if not exists claim_expires_at timestamptz; -- fencing: lease end
alter table delivery_outbox add column if not exists fence_token text;             -- fencing: monotonic token
alter table delivery_outbox add column if not exists replay_approved_at timestamptz;  -- owner ack of duplicate risk
alter table delivery_outbox add column if not exists legacy_reconcile boolean not null default false;  -- pre-control-plane marker
alter table delivery_outbox add column if not exists viewed_at timestamptz;
alter table delivery_outbox add column if not exists accepted_at timestamptz;
alter table delivery_outbox add column if not exists executed_at timestamptz;
alter table delivery_outbox add column if not exists ignored_at timestamptz;

comment on column delivery_outbox.delivery_id is
  'Logical delivery identity — one per insight. Ten destinations = one row with a route ladder.';
comment on column delivery_outbox.retry_generation is
  'Provider idempotency scope: delivery_id:retry_generation:channel. Bumped only by a DEFINITE non-delivery replay, never by ambiguity.';
comment on column delivery_outbox.legacy_reconcile is
  'A pre-control-plane pending/terminal-failed row an old worker may have POSTed before crashing. The v2 materializer cannot adopt it; only an owner ambiguous-risk replay clears it.';

-- One logical delivery per dedupe key, non-legacy only. This is the deduper's hard floor.
create unique index if not exists delivery_outbox_dedupe
    on delivery_outbox (org_id, dedupe_key)
    where dedupe_key is not null and legacy_reconcile = false;

-- Priority/fairness claim order: highest priority, oldest first, only claimable rows.
create index if not exists delivery_outbox_due
    on delivery_outbox (org_id, priority, created_at)
    where status = 'queued' and legacy_reconcile = false;

-- Expired-claim recovery scan.
create index if not exists delivery_outbox_claims
    on delivery_outbox (claim_expires_at)
    where claimed_by is not null;

-- ---------------------------------------------------------------------------------------
-- Append-only engagement history. Every lifecycle move writes one row in the same transaction as
-- the state change; client idempotency keys make repeated taps no-ops.
create table if not exists delivery_events (
    id               text primary key,
    org_id           text not null,
    delivery_id      text not null,
    kind             text not null,          -- queued|deferred|delivered|viewed|ignored|accepted|executed|failed|suppressed|cancelled|expired
    occurred_at      timestamptz not null default now(),
    actor            text,                   -- who/what recorded it (worker, seat, provider)
    idempotency_key  text,                   -- client-supplied; dedupes repeated receipts
    detail           jsonb,
    created_at       timestamptz not null default now()
);
create unique index if not exists delivery_events_idem
    on delivery_events (org_id, delivery_id, idempotency_key)
    where idempotency_key is not null;
create index if not exists delivery_events_by_delivery
    on delivery_events (org_id, delivery_id, occurred_at);

-- Append-only provider-call ledger. One row per physical attempt; the fenced `started` attempt
-- commits with the attention reservation before dispatch, so quota can never be spent untraceably.
create table if not exists delivery_attempts (
    id                text primary key,
    org_id            text not null,
    delivery_id       text not null,
    retry_generation  int not null default 0,
    channel           text not null,
    attempt_no        int not null,
    claim_token       text,                  -- the fencing token that owns this attempt
    started_at        timestamptz not null default now(),
    settled_at        timestamptz,
    outcome           text,                  -- started|delivered|failed|deferred|unknown
    provider_status   text,                  -- raw provider code/text, for the dead-letter view
    detail            jsonb,
    created_at        timestamptz not null default now()
);
create index if not exists delivery_attempts_by_delivery
    on delivery_attempts (org_id, delivery_id, started_at);

-- Atomic attention windows. PostgreSQL conditionally reserves the final hourly/daily slot, so two
-- workers cannot both spend it. Slack/Teams share a tenant-wide rolling hour; local-day is per
-- recipient (mixed timezones). Reservation and attempt-start commit together.
create table if not exists delivery_rate_windows (
    org_id        text not null,
    recipient     text not null,             -- seat id, or a channel-family key for shared streams
    window_kind   text not null,             -- 'hour' | 'day'
    window_start  timestamptz not null,
    used          int not null default 0,
    budget        int,                        -- snapshotted ceiling; null = unbounded
    updated_at    timestamptz not null default now(),
    primary key (org_id, recipient, window_kind, window_start)
);

-- Durable failures of materialisation. A corrupt source object is visible to operations, not lost.
create table if not exists delivery_materialization_failures (
    id            text primary key,
    org_id        text not null,
    execution_id  text,
    reason_code   text not null,
    detail        jsonb,
    created_at    timestamptz not null default now(),
    resolved_at   timestamptz                -- set when the source is repaired and materialised
);
create index if not exists delivery_matfail_open
    on delivery_materialization_failures (org_id, created_at)
    where resolved_at is null;

-- ---------------------------------------------------------------------------------------
-- Sealed provider credentials. New writes seal with GENIOS_CRYPTO_KEY (Fernet); list APIs return
-- masked metadata. Existing plaintext `config` stays as a rolling-migration fallback until rotated.
alter table org_channels   add column if not exists secret_ciphertext text;
alter table org_channels   add column if not exists secret_sealed_at  timestamptz;
alter table agent_registry add column if not exists secret_ciphertext text;
alter table agent_registry add column if not exists secret_sealed_at  timestamptz;

-- ---------------------------------------------------------------------------------------
-- New-write constraints. NOT VALID so legacy rows can be repaired post-deploy; new writes bound.
alter table delivery_outbox add constraint delivery_outbox_priority_ck
    check (priority in ('critical','high','medium','low','background')) not valid;
alter table delivery_outbox add constraint delivery_outbox_lifecycle_ck
    check (lifecycle in ('queued','deferred','delivered','viewed','ignored','accepted',
                         'executed','failed','suppressed','cancelled','expired')) not valid;
alter table delivery_outbox add constraint delivery_outbox_cursor_ck
    check (route_cursor >= 0 and retry_generation >= 0) not valid;
-- A claim is all-or-nothing: a worker id and a lease end travel together.
alter table delivery_outbox add constraint delivery_outbox_claim_shape_ck
    check ((claimed_by is null) = (claim_expires_at is null)) not valid;

-- Account erasure: every new org-scoped table gets a schema-enforced delete path to orgs.
alter table delivery_events add constraint delivery_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_attempts add constraint delivery_attempts_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_rate_windows add constraint delivery_rate_windows_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_materialization_failures add constraint delivery_matfail_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
