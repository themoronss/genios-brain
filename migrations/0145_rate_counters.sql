-- 0145 · RATE COUNTERS — small per-scope, per-day counters in Postgres (no Redis dependency).
--
-- First user: the screen promoter's per-seat generic cap (`kind='screen_generic'`,
-- `scope_key='<org_id>:<seat_id>'`, `window_start` = the org-local date). A counter is a number,
-- not content; old windows are pruned by the promoter's hourly housekeeping.

create table if not exists rate_counters (
    scope_key    text not null,
    kind         text not null,
    window_start date not null,
    count        integer not null default 0,
    primary key (scope_key, kind, window_start)
);
