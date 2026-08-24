-- GeniOS Engine · L5.2 Delivery Engine — the gate's memory.
--
-- Layers 4 and 5 decide *what* is worth saying and *who* owns it. Layer 6 has always known how
-- to get bytes to Slack. What sat between them was nothing: a queued row was sent the moment a
-- worker picked it up, which meant a correct, well-owned, well-worded alert could arrive at
-- 03:14 local time. That is not a delivery bug. It is the reason a tenant mutes the channel in
-- week three, and once it is muted every other layer's accuracy is worth zero.
--
-- This migration gives the gate two things it could not previously have: somewhere to read the
-- recipient's rules from, and somewhere to write down what it decided.
--
-- Four design points are worth reading before changing anything here.
--
-- 1. THE OUTBOX *IS* THE DELIVERY LEDGER. There is deliberately no `delivery_attention` table.
--    The burst limiter needs "how many intrusive messages has this person had in the last
--    hour?", and once the outbox carries `recipient` and `channel_class` that question is a
--    range scan over rows this system already writes. A second history table would be a second
--    write per send and a second thing to keep true; the one that already exists wins.
--
-- 2. DEFERRAL IS NOT FAILURE. `attempts` counts *transport* failures and is bounded — four
--    strikes and the row is `failed_terminal`. Quiet hours are not a strike. A message queued
--    at 22:00 under a four-attempt ladder would be dead by 03:00 if a hold consumed retries, so
--    `defer_count` is a separate counter that moves `next_attempt_at` and nothing else. The two
--    numbers answer two different questions and must never be added together.
--
-- 3. SUPPRESSED IS NOT CANCELLED. `cancelled` already means one specific thing in this schema:
--    the subject stopped being live before the send — a closed commitment, a revoked decision.
--    A person who turned this channel off is a different fact with a different fix, and
--    collapsing them would make "why did nothing arrive?" unanswerable from the row. The status
--    column is plain text with no check constraint, so this is a documented widening, not DDL.
--
-- 4. PREFERENCES RESOLVE, THEY DO NOT OVERRIDE. Every setting column in `delivery_preferences`
--    is nullable, and null means *inherit*, not *false*. Rows are keyed by (org, seat, channel)
--    with '*' as the "applies to all" sentinel, so an org default and one person's exception
--    are the same shape of row at different specificities. A sentinel rather than NULL because
--    NULLs in a primary key do not compare equal, which would let two org defaults coexist.
--
-- All statements idempotent; the cascade constraint at the bottom follows 0033's convention.

-- ---------------------------------------------------------------------------------------
-- The delivery object, materialised on the outbox row.
--
-- The gate is a pure function of (candidate, policy, profile, state) and the candidate's fields
-- have to come from somewhere at drain time. Carrying them on the row rather than re-deriving
-- them from `cards`/`executions` on every attempt means a retry three hours later evaluates the
-- *same* delivery it queued, and it keeps the drain query free of two more joins.
alter table delivery_outbox add column if not exists recipient text;
alter table delivery_outbox add column if not exists band text not null default 'standard';
alter table delivery_outbox add column if not exists channel_class text not null default 'chat';
alter table delivery_outbox add column if not exists interrupt boolean not null default false;

-- The gate's own bookkeeping. `defer_count` is the hold counter that must never touch
-- `attempts` (design point 2); `gate_unit`/`gate_reason` are the last verdict, so a row that is
-- sitting still explains itself without anybody reading application logs.
alter table delivery_outbox add column if not exists defer_count int not null default 0;
alter table delivery_outbox add column if not exists gate_unit text;
alter table delivery_outbox add column if not exists gate_reason text;

comment on column delivery_outbox.recipient is
  'Seat this push is aimed at. Null for org-wide surfaces (the daily digest has no one owner).';
comment on column delivery_outbox.channel_class is
  'Channel physics, not sender intent: in_app | chat | email | digest | agent. The timing gate keys on this — a digest cannot wake anybody, a chat push can.';
comment on column delivery_outbox.interrupt is
  'Layer 5 asked for attention AND cleared its confidence floor. Half of the break-glass predicate, the band being the other half.';
comment on column delivery_outbox.defer_count is
  'Humane holds served. Deliberately NOT attempts — a quiet-hours hold must not spend a transport retry.';

-- The burst-limit read: intrusive sends to one seat inside a rolling window. Partial on
-- `delivered`, which is the only status the limiter counts — a queued or suppressed row never
-- rang anybody's phone.
create index if not exists delivery_outbox_attention
    on delivery_outbox (org_id, recipient, delivered_at desc)
    where status = 'delivered';

-- Held work, oldest first: the operator view for "what is the gate sitting on right now?".
create index if not exists delivery_outbox_deferred
    on delivery_outbox (org_id, next_attempt_at)
    where status = 'queued' and defer_count > 0;


-- ---------------------------------------------------------------------------------------
-- Where the rules live.
--
-- One table, three specificities, resolved most-specific-first by the reader:
--
--   (org, '*',  '*' )  → the tenant's defaults        — set by an admin
--   (org, '*',  'slack') → per-channel defaults       — "Slack is escalations only"
--   (org, seat, '*' )  → this person, everywhere      — their timezone, their quiet hours
--   (org, seat, 'slack') → this person, this channel  — "no Slack pushes, keep email"
--
-- Every column nullable so a row can state one opinion and stay silent on the rest; the reader
-- coalesces down the ladder and falls through to the code defaults in deliver/timing.py and
-- deliver/policy.py. Those code defaults are the real contract — a tenant with zero rows here
-- gets protective quiet hours and permissive policy, which is the asymmetry that keeps an
-- unconfigured account both quiet at night and useful in the morning.
create table if not exists delivery_preferences (
    org_id                  text not null,
    seat_id                 text not null default '*',      -- '*' = applies to every seat
    channel                 text not null default '*',      -- '*' = applies to every channel
    -- Policy — the "is this allowed at all?" half. See deliver/policy.py.
    delivery_enabled        boolean,                        -- tenant kill switch: false = stop
    hold_until              timestamptz,                    -- a pause with an end, not a stop
    min_band                text,                           -- floor this channel accepts
    opted_out               boolean,                        -- this person turned this off
    -- Attention — the "is this the right moment?" half. See deliver/timing.py.
    tz_name                 text,                           -- IANA zone, e.g. 'Asia/Kolkata'
    quiet_enabled           boolean,
    quiet_start_hour        int,                            -- local hour 0..23, inclusive
    quiet_end_hour          int,                            -- local hour 0..23, exclusive
    quiet_weekends          boolean,
    max_interrupts_per_hour int,
    override_band           text,                           -- band allowed to break glass
    updated_by              text,                           -- seat that last changed this
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),
    primary key (org_id, seat_id, channel)
);

comment on table delivery_preferences is
  'L5.2 delivery rules, resolved most-specific-first over (seat, channel) with a star as the wildcard. A null column means inherit, never false.';
comment on column delivery_preferences.hold_until is
  'Tenant paused until a known instant. Mutually exclusive with delivery_enabled=false — a stop and a pause are different promises and the audit row has to say which one happened.';
comment on column delivery_preferences.override_band is
  'The band that may break quiet hours, and only together with interrupt. Raising this to a band above ''critical'' is how a tenant says "never wake me".';

-- The resolution read: every row that could apply to one (org, seat, channel) triple, which is
-- at most four. Keyed on org first so a tenant's whole rule set is one page.
create index if not exists delivery_preferences_lookup
    on delivery_preferences (org_id, seat_id, channel);


-- ---------------------------------------------------------------------------------------
-- Account erasure. Every org-scoped table needs a schema-enforced delete path to orgs, proven
-- for the whole schema by tests/test_account_erasure.py rather than trusted to a checklist —
-- a notification preference that outlived its tenant's deletion request is a compliance
-- incident. Same `not valid` convention as 0033 and 0041: binds every future write without
-- taking a full-table lock on deploy.
alter table delivery_preferences add constraint delivery_preferences_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
