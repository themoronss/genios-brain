-- 0150 · TEAM SITUATIONS — the post-pass ledger behind team/verify cards + moments (SCREEN_INTEL_P4 §3.1).
--
-- One row per (org, kind, key): the situation a deterministic post-pass (reason/team, reason/verify)
-- told one seat about. `digest` is what was said; a rerun with the same digest writes nothing, a
-- changed digest re-emits (card refreshed in place, a new moment). `card_id` is the durable copy —
-- moment rate caps may drop the toast, never the card. `key` is the caller's own identity and
-- already names the seat when a situation is per-seat.
create table if not exists team_situations (
    org_id           text not null references orgs (id) on delete cascade,
    kind             text not null,
    key              text not null,
    subject_node_ids text[] not null default '{}',
    seat_id          text not null,
    digest           text not null,
    card_id          text,
    moment_id        text,
    state            text not null default 'open',
    first_at         timestamptz not null default now(),
    last_at          timestamptz not null default now(),
    primary key (org_id, kind, key),
    constraint team_situations_kind check (kind in ('team', 'verify')),
    constraint team_situations_state check (state in ('open', 'closed'))
);
create index if not exists team_situations_by_seat on team_situations (org_id, seat_id, last_at desc);

-- A team/verify moment points at its durable card (the device's "open card" action).
alter table moments add column if not exists card_id text;
