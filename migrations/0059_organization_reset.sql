-- GeniOS Engine · organization_reset — the pivot primitive (Layer 6 addendum).
--
-- A declared pivot (ICP/positioning change) must invalidate evidence gathered under the old
-- business shape without deleting the org's history. This ledger is the event log: every call
-- expires stale Adaptive-brain runtime leases and records that open situations were re-scored
-- against current state, rather than waiting for the next daily L3 sweep to catch up on its own.
create table if not exists organization_resets (
    org_id            text not null,
    reset_id          text primary key,
    reason            text not null,
    triggered_by      text,
    adaptive_expired  int not null default 0,
    situations_rerun  boolean not null default false,
    created_at        timestamptz not null default now()
);
create index if not exists organization_resets_by_org
    on organization_resets (org_id, created_at desc);
