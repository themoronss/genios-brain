-- 0058 — Admin analytics foundation (ANALYTICS_V3_PLAN.md, Phase 1).
--
-- Three things, all prerequisites for a cross-org admin console:
--   1. orgs.is_internal — our own test/demo tenants, excluded from EVERY metric. Without it every
--      growth and revenue number is inflated by our own usage (the old PostHog dashboards deferred
--      this and that is exactly why their numbers could not be shown to an investor).
--   2. Financial retention — llm_costs / credit_ledger / subscriptions currently cascade-delete
--      with the org, so a deleted account erases the money we ACTUALLY spent and earned. Cost is
--      not the tenant's personal data: it is our accounting record. The FKs are dropped and the
--      org's identity is preserved in orgs_archive so the rows stay attributable after erasure.
--      (Graph/email/content erasure is untouched — that still wipes completely, see
--      account_routes._ORG_SCOPED_TABLES, which never contained these three tables.)
--   3. Cross-org time indexes — every existing index is (org_id, time) because every existing query
--      is single-tenant. Admin queries scan by time across all orgs and would seq-scan otherwise.

-- 1 ── internal tenant flag ---------------------------------------------------------------------
alter table orgs add column if not exists is_internal boolean not null default false;
-- Existing internal accounts are flagged by ops, not guessed here (a wrong guess silently deletes
-- real accounts from the investor numbers). Use: update orgs set is_internal=true where email in (…);
create index if not exists orgs_real_by_created
    on orgs (created_at desc) where is_internal = false;

-- Activation timestamp — the moment an account first became a real user (first intelligence query).
-- Stored rather than recomputed so the activation funnel and cohort retention stay stable and cheap.
alter table orgs add column if not exists activated_at timestamptz;
create index if not exists orgs_activated on orgs (activated_at) where activated_at is not null;

-- 2 ── financial retention ----------------------------------------------------------------------
-- Identity of a deleted tenant, kept ONLY so retained financial rows remain attributable
-- ("$412 spent by <company>"). No content, no graph, no message data — name/email/plan only.
create table if not exists orgs_archive (
    org_id           text primary key,
    name             text,
    company          text,
    email            text,
    subscription_tier text,
    is_internal      boolean not null default false,
    created_at       timestamptz,
    deleted_at       timestamptz not null default now()
);

-- Drop the cascade so spend/revenue history outlives the account. org_id stays a plain text column
-- (resolvable through orgs, else orgs_archive).
alter table llm_costs      drop constraint if exists llm_costs_org_cascade_fk;
alter table credit_ledger  drop constraint if exists credit_ledger_org_id_fkey;
alter table credit_ledger  drop constraint if exists credit_ledger_org_cascade_fk;
alter table subscriptions  drop constraint if exists subscriptions_org_id_fkey;
alter table subscriptions  drop constraint if exists subscriptions_org_cascade_fk;

-- 3 ── cross-org (time-first) indexes for admin rollups -----------------------------------------
create index if not exists llm_costs_by_time     on llm_costs (created_at desc);
create index if not exists credit_ledger_by_time on credit_ledger (occurred_at desc);
create index if not exists subscriptions_by_time on subscriptions (created_at desc);
create index if not exists audit_log_by_time     on audit_log (timestamp desc);
-- Login history / last-seen per account is the hottest admin query: audit_log filtered to the
-- handful of action types that count as real product activity.
create index if not exists audit_log_activity
    on audit_log (action, timestamp desc)
    where action in ('user_logged_in', 'decision_made', 'data_synced', 'data_accessed');
