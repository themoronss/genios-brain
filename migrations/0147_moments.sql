-- 0147 · MOMENTS — the hot lane's right-now nudges (SCREEN_INTEL_P3 §2.2–2.4, plan §6.2/§6.4).
--
-- A moment is NOT a card. A card is a durable queue item; a moment is a toast about what is on the
-- seat's screen right now, with a TTL, and then it is history. Every moment is stored, shown or
-- not: `display=false` + `suppressed_reason` is how shadow mode (capture_policies.moments_display
-- off, the default), rate limits, DND and quiet hours are recorded, so the owner can read what the
-- lane WOULD have said before turning it on.
--
-- `moment_id` is the device's uuid for device-local moments (P-01/P-18, `origin='device'`, the
-- post is idempotent on it) and a server id derived from the seat + request id for evaluated ones.
-- A moment is the seat's own: history shows it to that seat only.
create table if not exists moments (
    moment_id          text primary key,
    org_id             text not null references orgs (id) on delete cascade,
    seat_id            text not null,
    device_id          text,
    origin             text not null,
    kind               text not null,
    priority           text not null,
    capability_id      text not null,
    capability_version text not null,
    subject_node_ids   text[] not null default '{}',
    headline           text not null,
    body               text,
    actions            jsonb not null default '[]'::jsonb,
    evidence           jsonb not null default '[]'::jsonb,
    display            boolean not null,
    suppressed_reason  text,
    created_at         timestamptz not null default now(),
    expires_at         timestamptz not null,
    constraint moments_origin check (origin in ('device', 'server')),
    constraint moments_kind check (kind in ('advice', 'reminder', 'verify', 'team')),
    constraint moments_priority check (priority in ('low', 'normal', 'high', 'critical'))
);
-- History (newest first) and the per-seat rate-limit counts both read this.
create index if not exists moments_by_seat on moments (org_id, seat_id, created_at desc);

-- What the person did with it. `capability_id` is copied from the moment so precision per
-- capability is one grouped read (plan §6.4 "feedback stored per capability"). A retried post of
-- the same action at the same instant is one row.
create table if not exists moment_feedback (
    org_id        text not null references orgs (id) on delete cascade,
    moment_id     text not null references moments (moment_id) on delete cascade,
    seat_id       text not null,
    capability_id text not null,
    action        text not null,
    reason        text,
    at            timestamptz not null,
    created_at    timestamptz not null default now(),
    primary key (moment_id, action, at),
    constraint moment_feedback_action check (action in
        ('shown', 'clicked', 'acted', 'dismissed', 'wrong', 'snoozed', 'useful'))
);
create index if not exists moment_feedback_by_capability
    on moment_feedback (org_id, capability_id, created_at desc);

-- Identical moment within its TTL → served from here, never recomputed and never shown twice.
-- Key = sha256(seat, capability, sorted subject nodes, trigger digest, subject graph version).
create table if not exists moment_cache (
    key        text primary key,
    org_id     text not null references orgs (id) on delete cascade,
    seat_id    text not null,
    moment     jsonb not null,
    expires_at timestamptz not null
);
create index if not exists moment_cache_by_expiry on moment_cache (expires_at);
