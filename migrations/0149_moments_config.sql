-- 0149 · MOMENTS CONFIG — the slice version per seat, and the org's "Show popups" switch.
--
-- `seat_slice_versions.version` is monotonic per seat. It is written as
-- greatest(previous + 1, epoch milliseconds at the bump), so it is also a timestamp: a device's
-- `since` names the instant its copy was current, and the delta is "what changed after that"
-- without a per-version history table. Bumped by every org graph-version bump for the seats that
-- hold a live device (GraphStore.bump_version — the cheapest correct hook; see reason/moments/
-- slice.py), each bump announced by a `slice.delta` realtime event in the same transaction.
create table if not exists seat_slice_versions (
    org_id     text not null references orgs (id) on delete cascade,
    seat_id    text not null,
    version    bigint not null,
    updated_at timestamptz not null default now(),
    primary key (org_id, seat_id)
);

-- SHADOW FIRST (plan §15): moments are computed and logged but NOT shown until a workspace admin
-- turns this on. Default false, and an org with no capture_policies row is off too.
alter table capture_policies add column if not exists moments_display boolean not null default false;
-- Per-seat caps on SHOWN moments (plan §6.2: 6/hour, 30/day by default, org-configurable).
-- Reminders are never dropped by these caps when due.
alter table capture_policies add column if not exists moments_max_per_hour integer not null default 6;
alter table capture_policies add column if not exists moments_max_per_day integer not null default 30;

-- The slice and the one-hop moment read walk edges from BOTH ends (a person is `from` on some
-- edges and `to` on others); `graph_edges_current` only covers the `from` side.
create index if not exists graph_edges_current_to
    on graph_edges (org_id, to_node_id)
    where valid_to is null;
