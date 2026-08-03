-- GeniOS Engine · L3 · Baselines (C9). Closed-form per-key statistics computed from graph
-- history (e.g. a contact's normal reply cadence), used as rule thresholds. Versioned rows;
-- cold-start fallbacks when sample_size is too small. This is what "predictive" means here.

create table if not exists baselines (
    org_id      text not null,
    key         text not null,                -- e.g. "reply_cadence:<node_id>"
    value       numeric not null,             -- the statistic (days)
    sample_size int not null default 0,
    method      text not null default 'median',
    cold_start  boolean not null default false,
    computed_at timestamptz not null default now(),
    primary key (org_id, key)
);
