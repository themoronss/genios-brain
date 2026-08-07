-- GeniOS Engine · Atlas Layer 5.2 — live delivery context.
--
-- The durable delivery object and result already live in delivery_outbox. This migration adds
-- only the state that cannot be reconstructed from that ledger: what surface a recipient is on
-- right now, and whether that short-lived context makes interruption inhumane.
--
-- Presence is deliberately leased. A browser extension or mobile client can disappear without
-- sending a disconnect event; expires_at guarantees that stale "busy" state cannot hold a
-- message forever.

create table if not exists delivery_presence (
    org_id       text not null,
    seat_id      text not null,
    activity     text not null default 'unknown',
    surface      text not null default 'unknown',
    focus_mode   boolean not null default false,
    busy_until   timestamptz,
    observed_at  timestamptz not null,
    expires_at   timestamptz not null,
    metadata      jsonb not null default '{}',
    updated_at    timestamptz not null default now(),
    primary key (org_id, seat_id),
    constraint delivery_presence_valid_lease check (expires_at > observed_at)
);

create index if not exists delivery_presence_active
    on delivery_presence (org_id, expires_at desc);

alter table delivery_presence add constraint delivery_presence_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table delivery_presence is
  'Short-lived Layer 5.2 context reported by product surfaces. Expired rows are ignored.';
comment on column delivery_presence.busy_until is
  'Explicit meeting/focus end. Always bounded by expires_at by the resolver.';
