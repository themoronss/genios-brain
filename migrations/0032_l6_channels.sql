-- GeniOS Engine · L6 Intelligence Distribution — the human channel + the outbox.
-- Until now the ONLY outbound transport was an unretried webhook to machine agents:
-- GeniOS produced grounded, scored cards that no human was ever actively told about.
-- org_channels: where a tenant wants to hear (v1: one Slack incoming-webhook per org).
-- delivery_outbox: every outbound send is a row — queued → delivered | failed_terminal,
-- with bounded retries and backoff. Delivery becomes auditable state, never a blocking
-- HTTP call inside the reasoning sweep. All statements idempotent.

create table if not exists org_channels (
    org_id           text not null,
    channel          text not null,                 -- 'slack' (v1); adapter registry keys
    config           jsonb not null default '{}',   -- {webhook_url} — never logged
    active           boolean not null default true,
    last_digest_date date,                          -- daily-digest dedup marker
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    primary key (org_id, channel)
);

create table if not exists delivery_outbox (
    id              text primary key,
    org_id          text not null,
    card_id         text not null,                  -- real card_id, or 'digest:<date>' synthetic
    channel         text not null,
    payload         jsonb not null,                 -- the rendered message (built from card fields only)
    status          text not null default 'queued', -- queued | delivered | failed_terminal
    attempts        int  not null default 0,
    next_attempt_at timestamptz not null default now(),
    last_error      text,
    created_at      timestamptz not null default now(),
    delivered_at    timestamptz
);
-- one delivery per (card, channel) per org — re-enqueue is a no-op, retries mutate in place
create unique index if not exists delivery_outbox_once
    on delivery_outbox (org_id, card_id, channel);
create index if not exists delivery_outbox_due
    on delivery_outbox (status, next_attempt_at);
