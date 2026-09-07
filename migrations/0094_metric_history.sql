-- L2.4.1-U1 · `metric_history` — the table that answers *"what was true then?"*.
--
-- WHY A SECOND TABLE AND NOT A COLUMN. `context/derived.py:108-109` states the existing rule in
-- its own words: *"a derived value is a RECOMPUTE, not a new observation of history: it
-- overwrites its own deterministic version id rather than appending a row per drain."* That was
-- correct for its stated reason — appending per drain would grow `graph_facts` by three rows per
-- node for ever, and a reader picking "latest" would sift duplicates. The consequence is that
-- nothing in this system can answer "is this declining?": every number it holds is the current
-- one, and a trend needs the previous ones.
--
--   THE TWO-TABLE RULE. `graph_facts` answers "what is true NOW" and keeps overwriting.
--   `metric_history` answers "what was true THEN" and only ever appends. Conflating them is why
--   six of the six customer expectations doc 04 lists are unrepresentable today.
--
-- HOW THIS TABLE IS BOUNDED, because an append-only store sampled on every sweep is EXACTLY the
-- shape that put this database into read-only once already (`expertise_packages`, 181 MB over
-- 345 rows). Four mechanisms, and none of them is a comment:
--
--   1. NOTHING WRITES A ROW PER SWEEP. `observed_at` is the PERIOD the value describes, and the
--      primary key is that period — so a metric sampled every drain for a month produces ONE
--      row, updated in place, not thirty. The row count is set by the calendar, never by the
--      sweep cadence. This is the mechanism that matters; the other three are its backstops.
--   2. A GAP COSTS NOTHING. `value_bp` is NOT NULL on purpose: a period with no reading is
--      stored as NO ROW, and `read_series` materialises it as `known=False, value_bp=None`. An
--      unconnected source therefore writes nothing at all rather than a run of nulls.
--   3. PER-SERIES CAP, on the write path. Every `put` trims the series it just touched to the
--      newest `retention_periods` points (<= 104, `history.MAX_RETAINED_PERIODS`). A series
--      cannot exceed its cap even for one transaction.
--   4. WALL-CLOCK RETENTION, on the drain path. `prune` deletes everything older than 24 months
--      (`history.RETENTION_MONTHS`), which is what bounds a series that STOPPED being written —
--      a node that went cold keeps its capped points otherwise for ever. It is called from
--      `context/runner.process_pending`, the sweep that already runs once per org per drain, so
--      there is no new periodic task and no new Celery beat entry (the broker is a quota-limited
--      Upstash instance).
--
--   Steady state, monthly grain: rows <= nodes_sampled x metrics x 24. A 2,000-node org with
--   five monthly metrics settles at 240,000 rows (~30 MB with indexes) and STOPS — 10,000 rows
--   a month arrive and 10,000 fall out the back.
--
-- `value_bp` IS BIGINT. Money is stored in minor units, and a 40 crore contract in paise
-- overflows a 32-bit int at a value the tenant would actually type.
--
-- `observed_at` IS THE PERIOD, NOT THE COMPUTE TIME. A sampler that stamped its run time would
-- make every backfilled month look like this morning, and a trend over those stamps would be a
-- trend over when we happened to look. Backfill and live sampling are indistinguishable to a
-- reader BECAUSE both compute this column with the one shared function
-- (`context/analytic/history.period_start`) — the doc's named mitigation for phantom
-- changepoints.
--
-- `sampled_at` IS THE ARRIVAL TIME, and it is what makes a point-in-time read exact: asking for
-- a series "as at" a past instant filters on `sampled_at <= as_at`, so a trend computed in March
-- replays in September from the points that existed in March. The store's upsert deliberately
-- does NOT touch this column when a re-sample carries an identical reading, because a re-sample
-- that moved it would delete a point from every earlier as-at read.
--
-- ORG CASCADE. Doc 04's DDL declares `org_id text not null` with no reference; the FK is added
-- here because `tests/test_account_erasure.py` replays every migration and fails any table
-- carrying an `org_id` that cannot be erased with its tenant. `subject_node_id` is a graph node
-- and the series is a behavioural record of one of the tenant's counterparties, so this is not a
-- formality. The table is also named in `api/account_routes._ORG_SCOPED_TABLES`, which is what
-- makes /reset erase it as well as account deletion; that loop runs with no try/except, so a
-- name missing from it leaks silently.
--
-- NO FK ON `subject_node_id`: `graph_nodes` is versioned and its primary key is
-- `(node_id, version)`, so there is no single column to reference. The org cascade is the
-- guarantee that matters, and a node deleted without its org leaves points that `read_series`
-- never asks for.

create table if not exists metric_history (
    org_id          text not null references orgs (id) on delete cascade,
    subject_node_id text not null,
    metric          text not null,          -- "engagement.touch_count", "deal.stage_age_days"
    value_bp        bigint not null,        -- integer. money in minor units, ratios in bp
    unit            text not null,          -- "count" | "days" | "bp" | "minor_units"
    currency        text,                   -- only when unit = minor_units
    observed_at     timestamptz not null,   -- the PERIOD this value describes
    sampled_at      timestamptz not null default now(),
    sample_reason   text not null,          -- "scheduled" | "changepoint" | "backfill"
    coverage_ready  boolean,                -- from L1 v2 — absence vs zero
    primary key (org_id, subject_node_id, metric, observed_at)
);

-- Doc 04's two read paths.
create index if not exists mh_by_metric on metric_history (org_id, metric, observed_at desc);
create index if not exists mh_by_node   on metric_history (org_id, subject_node_id, metric, observed_at desc);
-- The third index is the RETENTION path and it is not in the doc. Neither index above can
-- answer "this org's rows older than X" without walking every entry the org has, because both
-- put a discriminator ahead of `observed_at` — so the per-drain prune would cost a scan of the
-- whole org on every sweep, which is how a bounding mechanism becomes the reason nobody runs it.
-- With this index a prune that deletes nothing costs one index probe.
create index if not exists mh_retention on metric_history (org_id, observed_at);
