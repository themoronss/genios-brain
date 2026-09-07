-- L2.4.4-U1 · `cohort_definitions` + `cohort_membership` — WHO a tenant is compared against.
--
-- LAW 3 OF LAYER 2: COHORTS ARE DECLARED, NEVER CLUSTERED. `predicate` is a typed tree a human
-- (or a human-approved M-9 draft) wrote, stored as jsonb and interpreted in Python by
-- `context/analytic/cohort.evaluate`. It is NEVER compiled into SQL: no statement in that module
-- interpolates any part of a predicate, which is what makes the column safe to hold whatever a
-- founder typed. A cohort from k-means could not be stored here at all — there would be nothing
-- to put in this column that a human could read, diff or correct.
--
-- WHY MEMBERSHIP IS A SECOND TABLE AND WHY IT IS HISTORICAL. `left_at` matters more than it
-- looks: *"accounts that left this cohort last month"* is itself a churn signal, and it is only
-- askable if a departure is recorded rather than deleted. Rows are therefore closed, never
-- removed, and one node's membership of one cohort over three years is a handful of rows rather
-- than a stream.
--
-- HOW THIS IS BOUNDED, because `expertise_packages` reached 181 MB over 345 rows and put this
-- database into READ-ONLY, and a membership table refreshed on every sweep is exactly that shape:
--
--   1. `joined_at` IS A PERIOD, NOT AN INSTANT. `cohort.refresh_membership` sets it to the ISO
--      week start through `history.period_start` — the one shared boundary function this layer
--      has — so a node joining produces AT MOST ONE ROW PER WEEK however many sweeps run in that
--      week, and the primary key turns every later sweep into an in-place update. Row growth is
--      set by the calendar and by real churn, never by sweep cadence. This is the mechanism that
--      matters; the rest are its backstops.
--   2. A SWEEP RUN TWICE IN ONE PERIOD WRITES NOTHING NEW. Joins upsert onto the same key, and
--      the hysteresis counter only advances where `evaluated_at < :at`, so replaying a sweep at
--      the same instant cannot walk a node out of a cohort it never left.
--   3. HYSTERESIS. `miss_streak` must reach 2 before `left_at` is set, so a flapping fact cannot
--      produce a join/leave pair per sweep.
--   4. A PER-SWEEP WRITE BUDGET in the module (`MEMBERSHIP_WRITE_BUDGET`), so a 50k-node org's
--      first pass cannot become a 500k-statement transaction. What is not done this sweep is done
--      by the next; membership is state, not a queue.
--   5. RETENTION on the drain path: CLOSED stints older than 24 months are pruned by
--      `cohort.prune_membership`, called from `context/runner.process_pending` (no new periodic
--      task — the Celery broker is a quota-limited Upstash instance). OPEN membership is never
--      pruned: a node that has been in a cohort for three years is one row, and deleting it would
--      delete the cohort.
--   6. `cohort_definitions` DOES NOT GROW ON A SWEEP. System families have STABLE ids per slot
--      and are UPSERTED — a quartile family whose boundaries moved rewrites four rows rather than
--      appending four — and authored cohorts are content-addressed, so approving the same
--      predicate twice is the same row. `MAX_COHORTS_PER_ORG` caps the total.
--
--   Steady state: rows <= nodes x active cohorts x stints-in-window. A 2,000-node org with 20
--   cohorts and quarterly churn settles near 160,000 rows and STOPS.
--
-- ORG CASCADE. Doc 04's DDL declares `org_id text not null` with no reference; the FK is added
-- here because `tests/test_account_erasure.py` replays every migration and fails any table
-- carrying an `org_id` that cannot be erased with its tenant. Membership names the tenant's own
-- counterparties — which accounts are in the bottom ARR quartile is a statement about their
-- customers — so this is not a formality. Both tables are also named in
-- `api/account_routes._ORG_SCOPED_TABLES`, which is what makes /reset erase them as well as
-- account deletion; that loop runs with NO try/except, so a name missing from it leaks silently.
--
-- MEMBERSHIP CASCADES FROM ITS DEFINITION as well as from its org: a cohort that no longer exists
-- has no members, and leaving orphaned rows behind would make the retention prune the only thing
-- that ever removed them.
--
-- NO FK ON `node_id`: `graph_nodes` is versioned and its primary key is `(node_id, version)`, so
-- there is no single column to reference — the same reason `metric_history` gives (0094).

create table if not exists cohort_definitions (
    cohort_id    text primary key,
    org_id       text not null references orgs (id) on delete cascade,
    name         text not null,          -- "Growth plan, mid-ARR, recent"
    node_type    text not null,          -- company | deal | person
    predicate    jsonb not null,         -- the typed predicate tree. NEVER compiled into SQL.
    created_by   text not null,          -- a human, or "system:default"
    created_at   timestamptz not null default now(),
    active       boolean not null default true
);
-- The sweep's read: this tenant's live cohorts.
create index if not exists cohort_definitions_by_org
    on cohort_definitions (org_id, node_type) where active;

create table if not exists cohort_membership (
    org_id       text not null references orgs (id) on delete cascade,
    cohort_id    text not null references cohort_definitions (cohort_id) on delete cascade,
    node_id      text not null,
    joined_at    timestamptz not null,   -- the PERIOD (ISO week start), not the sweep instant
    left_at      timestamptz,            -- membership is HISTORICAL, not just current
    miss_streak  int not null default 0, -- hysteresis: 2 consecutive misses before leaving
    evaluated_at timestamptz,            -- idempotency: a replayed sweep advances nothing
    primary key (org_id, cohort_id, node_id, joined_at)
);
-- The two reads the module makes: current membership (positioning, refresh) and the change feed.
create index if not exists cohort_membership_current
    on cohort_membership (org_id, cohort_id, node_id) where left_at is null;
-- Also the RETENTION path. Without a leading (org_id, left_at) index the per-drain prune would
-- scan every membership row the org has on every sweep, which is how a bounding mechanism becomes
-- the reason nobody runs it. With it, a prune that deletes nothing costs one index probe.
create index if not exists cohort_membership_changes on cohort_membership (org_id, left_at);
