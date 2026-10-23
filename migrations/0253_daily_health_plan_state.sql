-- 0253 · GeniOS-012 U12-01 · the daily health row says whether the tenant's plan had lapsed.
--
-- Since 7075014c (4 Oct) the scheduled sweep skips a tenant whose plan is EXPIRED — no capture, no reasoning,
-- no cards — and nothing said so: the founder's own org stopped on 21 Sep and nobody saw it for a month.
-- `platform/daily_health` now writes the plan state at the end of the row's day (`active` | `grace` |
-- `expired`, `platform/billing.expiry_state`; null when the org row could not be read) and raises the
-- `plan_expired` alert for an expired tenant, once a day by the row's own key.
--
-- Additive and idempotent: one nullable column; rows written before it read null ("not measured").

alter table daily_health add column if not exists plan_state text;

alter table daily_health drop constraint if exists daily_health_plan_state_ck;
alter table daily_health add constraint daily_health_plan_state_ck
    check (plan_state is null or plan_state in ('active', 'grace', 'expired'));

comment on column daily_health.plan_state is
  'GeniOS-012 U12-01: the plan at the end of the row''s day (platform/billing.expiry_state); expired = every '
  'scheduled sweep skipped the tenant. Null: not measured.';
