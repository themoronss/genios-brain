-- L2.4.6-U1 · `peer_baselines` — the cached p10/p25/p50/p75/p90 ladder per (cohort, metric).
--
-- WHY IT IS A TABLE AND NOT A QUERY. Every comparison would otherwise re-scan the whole
-- population, and L1 v2's importance formula (ALG-17) reads the org's p50 for a metric on a path
-- that must not run a percentile sweep to answer one signal. The ladder is computed once on the
-- drain that already happens (no new periodic task — the Celery broker is a quota-limited Upstash
-- instance) and read many times.
--
-- WHY `computed_at` IS IN THE PRIMARY KEY. A percentile computed in March must be reproducible in
-- September against MARCH's ladder. A baseline is therefore appended, never updated: a row is a
-- statement about a moment, and overwriting it would silently rewrite the comparison that a card
-- printed six months ago. Reads take the newest row with `computed_at <= :as_of`.
--
-- WHAT CROSSES THE TENANT BOUNDARY: NOTHING. Every row names exactly one `org_id`, and doc 04
-- L2.4.6-U2 defers the cross-org baseline explicitly. `context/analytic/peer_baseline.py` has no
-- statement that reads two tenants, and `cross_org_baseline()` there exists in order to refuse.
--
-- WHAT A ROW MAY NOT DISCLOSE, and this is the part the schema alone cannot enforce. A five-rung
-- ladder over a population of six IS the sorted population: nearest-rank p10 is the minimum and
-- p90 the maximum, so publishing it hands a reader who is one of the six the other five values.
-- The module therefore enforces a k-anonymity floor (`MIN_BASELINE_POPULATION`) and computes each
-- rung as the integer mean of a window of at least `BASELINE_SMOOTHING_WINDOW` members, so no rung
-- is any single member's reading and the extremes are never published. `population` is stored
-- alongside so a reader can dismiss a thin baseline rather than trust it.
--
-- BOUNDED. One row per (cohort, metric) per drain would grow without limit, so the module writes
-- `computed_at` as the ISO WEEK START (`history.period_start`) — the same boundary function the
-- rest of this layer uses — making a week of sweeps write ONE row per (cohort, metric) however
-- many times the drain runs, and retention drops rows older than the 24-month history horizon on
-- the same drain pass.
--
-- The table is also named in `api/account_routes._ORG_SCOPED_TABLES`, which is what makes /reset
-- erase it as well as account deletion; that loop runs with no try/except, so a name missing from
-- it leaks silently.

create table if not exists peer_baselines (
    org_id      text not null references orgs (id) on delete cascade,
    cohort_id   text not null,
    metric      text not null,
    -- The ladder, in the metric's own unit. Never null: a partially-filled ladder is a
    -- distribution nobody can read, and the module returns a refusal instead of one.
    p10_bp      bigint not null,
    p25_bp      bigint not null,
    p50_bp      bigint not null,
    p75_bp      bigint not null,
    p90_bp      bigint not null,
    -- NOT IN DOC 04's DDL AND DELIBERATE: a ladder without its unit is five numbers that render
    -- as whatever the reader's locale guesses, which is the `$84K` / `$8.4K` fault one layer up.
    unit        text not null,
    currency    text,                     -- only when unit = minor_units
    population  int  not null,            -- members with a KNOWN reading. Gaps are not zeros.
    computed_at timestamptz not null,
    primary key (org_id, cohort_id, metric, computed_at)
);

-- The read path: the newest ladder at or before an instant, for one tenant's cohort and metric.
create index if not exists peer_baselines_as_of
    on peer_baselines (org_id, cohort_id, metric, computed_at desc);
-- The RETENTION path. Neither the primary key nor the index above can answer "this org's rows
-- older than X" without walking every ladder the org has, so a per-drain prune would cost a scan
-- of the whole org on every sweep — which is how a bounding mechanism becomes the reason nobody
-- runs it. With this index a prune that deletes nothing costs one index probe.
create index if not exists peer_baselines_retention on peer_baselines (org_id, computed_at);
