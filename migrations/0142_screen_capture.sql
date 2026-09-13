-- 0142 · SCREEN CAPTURE — what a device uploads, and whether it is there right now.
--
-- WHY NOT `source_events`. Screen deltas land in their own table, held (`status='held'`), until
-- the P2 promoter turns them into `screen_session` source events. Nothing in Layer 1 can pick
-- them up by accident while that promoter is unbuilt, and per-seat erasure is one delete.
--
-- IDEMPOTENCY IS THE PRIMARY KEY. A device retries uploads from a persistent queue; the same
-- (device, session, watermark) arriving three times is one row — `insert … on conflict do
-- nothing` — and a later watermark for the same session is a new delta, not an overwrite.
--
-- ENCRYPTED AT REST. `payload_enc` is the whole session (participants, messages, title) sealed
-- with the engine's Fernet key (`platform/crypto.py`, GENIOS_CRYPTO_KEY). The upload endpoint
-- refuses to store anything when no key is configured; screen text is never written in clear.

create table if not exists screen_session_deltas (
    org_id            text not null references orgs (id) on delete cascade,
    device_id         text not null,
    session_key       text not null,
    message_watermark bigint not null,
    seat_id           text not null,
    app               text not null,
    thread_key        text,
    payload_enc       bytea not null,
    message_count     integer not null default 0,
    captured_at       timestamptz,
    received_at       timestamptz not null default now(),
    status            text not null default 'held',
    primary key (org_id, device_id, session_key, message_watermark)
);
-- Per-seat reads (P2 promoter, erasure) and the seat's recent activity.
create index if not exists screen_session_deltas_by_seat
    on screen_session_deltas (org_id, seat_id, received_at);
-- The retention sweep deletes ACROSS orgs by age (each org's own `retention_days`), in batches,
-- on the in-process scheduler heartbeat. Without an age index every batch is a full scan; this
-- is the one index here that cannot lead with org_id for exactly that reason.
create index if not exists screen_session_deltas_by_received
    on screen_session_deltas (received_at);

-- One row per signed-in device: what it is focused on, and until when that is true. The app
-- heartbeats every 10 s but the row is only WRITTEN when a field changed or it is > 30 s old —
-- the session pooler is 8+4 connections and presence must not become the busiest writer we have.
create table if not exists presence_leases (
    org_id         text not null references orgs (id) on delete cascade,
    seat_id        text not null,
    device_id      text not null,
    focus_app      text,
    bundle_id      text,
    dnd            boolean not null default false,
    idle           boolean not null default false,
    app_version    text,
    policy_version text,
    updated_at     timestamptz not null default now(),
    expires_at     timestamptz not null,
    primary key (org_id, seat_id, device_id)
);
