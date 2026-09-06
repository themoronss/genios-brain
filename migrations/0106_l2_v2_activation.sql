-- X8 / H8 · the Layer 2 v2 pilot switch — per tenant, in a table, with TWO independent switches.
--
-- WHY A TABLE AND NOT A BOOLEAN. `09-Build-Order-and-Acceptance.md` ("Activation") prints this
-- DDL and prints the reason beside it: `platform/config.py`'s `use_domain_compiler=False` has been
-- set in no environment since it was written and has left 152 capabilities dark. A global flag has
-- two states and both are wrong for a migration — off means the new path is never exercised by
-- anything real, on means every tenant's behaviour changes on one deploy. Layer 1 already answered
-- this the same way (`l1_semantic_activation`, migrations 0085 + 0090) and this table is its Layer
-- 2 twin, deliberately spelled the way the plan spells it.
--
-- TWO SWITCHES, AND THEY ARE NOT THE SAME KIND OF SWITCH. The plan asks for two so that "the
-- analytic stratum can run and be validated on a tenant long before pattern matching replaces
-- anchor-based detection for them". In THIS repo they differ in one way that must be stated here
-- rather than discovered later:
--
--   * `patterns_enabled_at` is a REAL GATE. `context/patterns` is a complete package that nothing
--     on the drain calls — `evaluate_org` is reachable only from `POST /api/org/{id}/patterns/
--     evaluate`. This column is what makes `context/runner.process_pending` run the shadow
--     evaluation pass, which is the only way `pattern_fires` accumulates the seven days of fire
--     evidence H8 compares against anchor-based detection. Off, the pass does not run at all.
--
--   * `analytic_enabled_at` is a DECLARATION, not a gate. Every analytic pass (sampler, trend,
--     cohort, peer baseline, comparator, anomaly, gap-reason, importance composition) already runs
--     UNCONDITIONALLY for every tenant — it landed that way in waves X1-X5 and the runner's own
--     comments say why (a metric measured against a clock must keep sampling on a quiet inbox).
--     Gating it now would turn the stratum OFF for every existing tenant, which is a founder-
--     visible regression introduced by an activation table, and H8's last row is "founder-visible
--     regressions: 0". So this column records WHEN this tenant was declared to be in the L2 v2
--     pilot and WHO declared it; `scripts/l2_shadow_diff.py` reads it to bound and interpret its
--     window, and refuses to call a tenant measured that was never declared. It turns nothing on
--     because there is nothing left to turn on, and saying so in the column comment is the only
--     honest alternative to a switch that quietly gates nothing.
--
-- IT DOES NOT BACKFILL. `context/analytic/sampler.backfill_history_for_drain` already runs a
-- once-per-tenant 18-month reconstruction, guarded on history EXISTENCE rather than on a marker,
-- so it costs one index probe per drain after the first. Activation deliberately does not trigger
-- one: a second backfill path would double the only expensive read in the layer and would make
-- "activate twice" mean "reconstruct eighteen months twice". Idempotency here is therefore not a
-- claim about this table alone — it is that this table starts no work at all.
--
-- REVERSIBLE, AND THE ROW SURVIVES THE REVERSAL. Each switch keeps its own `disabled_at`, stamped
-- rather than nulled, for the reason migration 0090 gives one switch down: H8 reads a SEVEN-DAY
-- window, and a window that silently contains a mid-week switch-off is a diff nobody can read.
-- "Live" is `enabled_at is not null and disabled_at is null`, and every read filters on it.

create table if not exists l2_v2_activation (
    -- One row per tenant, both switches on it. Two rows (one per switch) would let a tenant be
    -- half-present in the table and would make "who is in the pilot" a union rather than a read.
    org_id                text primary key references orgs (id) on delete cascade,

    -- SWITCH 1 — the declaration. Null means this tenant was never declared to be in the L2 v2
    -- pilot. See the header: it gates no code, and it must not, because the analytic stratum is
    -- already unconditional for every tenant.
    analytic_enabled_at   timestamptz,
    analytic_disabled_at  timestamptz,

    -- SWITCH 2 — the real gate. Null (or disabled) means `context/runner.process_pending` does not
    -- run the pattern shadow pass for this tenant and `pattern_fires` stays empty.
    patterns_enabled_at   timestamptz,
    patterns_disabled_at  timestamptz,

    -- WHO. The plan prints `enabled_by text not null`; kept not-null for the reason the L1 table
    -- keeps it: a tenant whose behaviour changed needs an answer to "who decided this and when",
    -- and a switch table that stored only the org id can produce neither.
    enabled_by            text not null,
    -- WHY this tenant. The fourth column the L1 activation rule earned in migration 0090: "who"
    -- and "when" without "why" leaves the next operator guessing whether an org is a deliberate
    -- design partner or a leftover from a debugging session.
    notes                 text,
    updated_at            timestamptz not null default now()
);

-- The drain's own read: "is the pattern shadow pass on for this tenant". One index probe per
-- sweep per tenant, on the hot path of every L2 drain, so it is worth the partial index.
create index if not exists l2_v2_activation_patterns_live
    on l2_v2_activation (org_id) where patterns_enabled_at is not null
                                   and patterns_disabled_at is null;

comment on table l2_v2_activation is
  'H8 pilot activation for Layer 2 v2. Per-tenant, never a config boolean (09-Build-Order-and-Acceptance.md, "Activation"). Written only by api/admin_routes.py; read by context/runner.py (patterns switch) and scripts/l2_shadow_diff.py (both).';
comment on column l2_v2_activation.analytic_enabled_at is
  'DECLARATION, NOT A GATE. The analytic stratum runs unconditionally for every tenant (waves X1-X5); gating it here would switch it off for everyone already on it. This column records when the tenant entered the L2 v2 pilot, and is what scripts/l2_shadow_diff.py bounds and interprets its window against.';
comment on column l2_v2_activation.patterns_enabled_at is
  'REAL GATE. Non-null and not disabled makes context/runner.process_pending run the L2.6 pattern registry in SHADOW and accumulate pattern_fires. Off, that pass does not run and the fire log stays empty.';
comment on column l2_v2_activation.analytic_disabled_at is
  'When the declaration was withdrawn. Null means live. The row is kept rather than deleted so a seven-day H8 window that contains a mid-window switch-off can say so.';
comment on column l2_v2_activation.patterns_disabled_at is
  'When the pattern shadow pass was switched back off. Null means live. Kept for the same reason as analytic_disabled_at.';
comment on column l2_v2_activation.notes is
  'Why this tenant was chosen for the pilot.';
