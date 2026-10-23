-- 0251 · daily_health — one health row per org per day, and the alerts it raised (GeniOS-011 S05.U1).
--
-- WHY. Nothing measured production card volume or quality daily (audit item
-- `process-no-daily-production-card-health`): `scripts/pipeline_health.py`, `runtime_receipts.py` and
-- `l2_shadow_report.py` are manual CLIs nothing runs, the funnel's five numbers are written every pass and
-- read by nobody, and `ops_alert` fired on a crash or a timeout but never on card volume. The database
-- reached its 500 MB tier twice in 17 days (2 Oct and 19 Oct, `cross-db-tier-never-budgeted`) with no
-- daily size line anywhere. `platform/daily_health.py` writes this row once a day per org from the tables
-- that already hold the facts; `platform/scheduler.py` runs it after the heavy tick.
--
-- WHAT A ROW HOLDS — one UTC day, a whole one (the job writes YESTERDAY, never a day still in progress):
--   cards              {builder_version: {output_lane: n}}   cards created that day, by card path and lane
--   card_refusals      {rule: n}                             the card contract's refusals
--   expert_reviews     {status: n}                           valid | refused | truncated | over_budget | failed
--   reasoning_results  {status: n}                           the L2 judgment's ends
--   l2_admissions      {decision: n}                         admit | hold | reject, decided that day
--   funnel             {stage: n | null}                     the five numbers summed over the day's sweeps;
--                                                            NULL = no sweep wrote the stage (nobody looked),
--                                                            0 = it ran and counted nothing (0188's rule)
--   llm_*              calls, failures, truncations          `llm_costs` (a truncation carries its error)
--   r_site_calls       {outcome: n}                          L4's R-site consults, a skip is a row
--   database_bytes     pg_database_size when the row was written — a fact about the server, kept on each row
--   cards_median_14d   the median of the 14 days before, zeros counted — what the drop alert compared with
--   alerts             what fired for this row: cards below half the median, a lane NO DATA for the day,
--                      the database past its ceiling
--
-- ONE ROW PER (org, day), AND THE KEY IS THE CLAIM. The writer inserts `on conflict do nothing`, so a
-- second tick, a second replica or a re-run writes nothing and alerts nothing: once a day means once.
-- Bounded: the writer deletes rows older than its retention (`daily_health.RETENTION_DAYS`), so the table
-- holds a few months per tenant and never grows with sweeps — the 500 MB plan this row exists to watch.
--
-- Idempotent: safe to run twice.

create table if not exists daily_health (
    org_id             text        not null references orgs (id) on delete cascade,
    day                date        not null,
    cards              jsonb       not null default '{}'::jsonb,
    cards_total        integer     not null default 0,
    card_refusals      jsonb       not null default '{}'::jsonb,
    expert_reviews     jsonb       not null default '{}'::jsonb,
    reasoning_results  jsonb       not null default '{}'::jsonb,
    l2_admissions      jsonb       not null default '{}'::jsonb,
    funnel             jsonb       not null default '{}'::jsonb,
    llm_calls          integer     not null default 0,
    llm_failures       integer     not null default 0,
    llm_truncations    integer     not null default 0,
    r_site_calls       jsonb       not null default '{}'::jsonb,
    database_bytes     bigint,
    cards_median_14d   numeric,
    alerts             jsonb       not null default '[]'::jsonb,
    measured_at        timestamptz not null default now(),
    primary key (org_id, day),
    constraint daily_health_cards_total_ck check (cards_total >= 0),
    constraint daily_health_alerts_ck check (jsonb_typeof(alerts) = 'array')
);

-- The 30-day chart and the retention purge both read by day.
create index if not exists daily_health_by_day on daily_health (day desc);

comment on table daily_health is
  'GeniOS-011 S05.U1: one row per org per UTC day — cards by builder_version/output_lane, card_refusals by '
  'rule, expert_reviews/reasoning_results/l2_admissions by status, the funnel''s five numbers, LLM failures '
  'and truncations, database size — and the ops alerts the row raised. Written by platform/daily_health.';
