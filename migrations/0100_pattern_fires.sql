-- L2.6 · the fire log — the three tables that make doc 06's two failure modes MEASURABLE.
--
-- WHY THERE IS A TABLE AT ALL. Doc 06 names two ways a pattern is wrong and both are invisible in
-- code review: one fires on everything and becomes noise, the other never fires and looks exactly
-- like a pattern that correctly found nothing. Layer 1 shipped fifteen of twenty-one deep sales
-- rules in the second state — gated on a field 9% of records carried — and every test was green
-- for the entire time. The only thing that would have caught it is a COUNT on a real tenant, and
-- nobody was printing one. `scripts/pattern_fire_report.py` prints it off these tables.
--
-- WHY `pattern_runs` EXISTS BESIDE `pattern_fires`. A fire count is meaningless without its
-- denominator: twelve fires is excellent on 4,000 subscriptions and catastrophic on fifteen. The
-- run row records how many anchors were CONSIDERED, which is the only place that number can be
-- honestly recorded — after the fact nobody can reconstruct how many anchors existed at the
-- instant a sweep ran. It also records the most common REASON a pattern did not fire, which is
-- what turns "this pattern is silent" into "this pattern's third condition never holds on this
-- tenant because the field is spelled differently".
--
-- HOW THIS IS BOUNDED, because `expertise_packages` reached 181 MB over 345 rows and put this
-- database into read-only:
--   1. ONE FIRE ROW PER (pattern, version, anchor, evaluation). The unique index makes a
--      re-evaluation at the same instant an in-place update rather than a second row, so replaying
--      a sweep cannot double a tenant's fire rate.
--   2. A PER-RUN WRITE BUDGET in `context/patterns/store.FIRE_WRITE_BUDGET`. A pattern that
--      matches every one of 50,000 anchors writes the budget and records the true count in
--      `pattern_runs.fires` — the number the guard reads is never the number of rows stored.
--   3. RETENTION. `prune_fire_log` deletes rows older than `FIRE_RETENTION_DAYS` (90) on the same
--      request that writes new ones. No periodic task: the Celery broker is a quota-limited
--      Upstash instance and this layer adds none.
--
-- ACTIVATION IS PER TENANT AND PER PATTERN, in a table, exactly as doc 09 requires of Layer 2 and
-- for the reason it gives: `use_domain_compiler=False` has been set in no environment since it was
-- written and has left 152 capabilities dark. No global boolean.

create table if not exists pattern_fires (
    fire_id          text primary key,
    -- CASCADES WITH THE ACCOUNT. A fire is a statement about one tenant's own graph — which of
    -- their subscriptions is unowned, which of their people is a bottleneck — so it is content,
    -- not accounting, and `tests/test_account_erasure.py` is what enforces that distinction
    -- schema-side rather than by anybody remembering to add a table to a sweep.
    org_id           text not null references orgs (id) on delete cascade,
    pattern_id       text not null,
    pattern_version  int  not null,
    -- The anchor the pattern matched. A situation is ABOUT this node.
    anchor_node_id   text not null,
    anchor_node_type text not null,
    situation_type   text not null,
    -- `matcher.MatchResult.match_strength_bp` — integer basis points, base plus the satisfied
    -- optional weights. Never an importance: importance is BLG-18's and composes from L1 signals.
    match_strength_bp int not null,
    -- Was the pattern ACTIVATED for this tenant when it fired? A shadow fire and a live one are
    -- the same match and completely different facts about the product, and the H6 gate row reads
    -- "0 patterns ACTIVATED while exceeding their expected fire rate 10x" off this column.
    activated        boolean not null default false,
    -- The per-condition evidence, verbatim from the match. This is the receipt: "it fired because
    -- of these five facts" is unreconstructible after the graph moves on.
    evidence         jsonb not null default '[]',
    evaluated_at     timestamptz not null,
    created_at       timestamptz not null default now()
);

-- One row per (pattern, version, anchor, evaluation). Re-running a sweep at the same instant
-- updates rather than appends — see bounding mechanism 1.
create unique index if not exists pattern_fires_once
    on pattern_fires (org_id, pattern_id, pattern_version, anchor_node_id, evaluated_at);

-- The report's own read: this tenant's fires for one pattern since an instant.
create index if not exists pattern_fires_by_pattern
    on pattern_fires (org_id, pattern_id, evaluated_at desc);

create table if not exists pattern_runs (
    run_id            text primary key,
    org_id            text not null references orgs (id) on delete cascade,
    pattern_id        text not null,
    pattern_version   int  not null,
    -- THE DENOMINATOR. How many anchors of this pattern's node type existed and were evaluated.
    anchors_considered int not null,
    -- The TRUE fire count, which may exceed the number of rows in `pattern_fires` when the write
    -- budget clipped them. The guard reads this.
    fires             int not null,
    -- Which condition stopped the pattern most often, and why. The remedy for a silent pattern.
    top_failure_index  int,
    top_failure_reason text,
    top_failure_field  text,
    evaluated_at      timestamptz not null,
    created_at        timestamptz not null default now()
);

create unique index if not exists pattern_runs_once
    on pattern_runs (org_id, pattern_id, pattern_version, evaluated_at);

create index if not exists pattern_runs_by_pattern
    on pattern_runs (org_id, pattern_id, evaluated_at desc);

create table if not exists pattern_activation (
    org_id          text not null references orgs (id) on delete cascade,
    pattern_id      text not null,
    -- Null means shadow: the pattern is evaluated and logged and reaches no card.
    activated_at    timestamptz,
    activated_by    text,
    -- Why activation was REFUSED, verbatim from `registry.activation_decision`. Stored so the
    -- refusal survives the request that produced it and an operator can read what the rate was.
    blocked_reason  text,
    blocked_at      timestamptz,
    updated_at      timestamptz not null default now(),
    primary key (org_id, pattern_id)
);
