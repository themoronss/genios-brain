-- 0141 · CAPTURE POLICY — who may capture what, decided by the org and narrowed by each seat.
--
-- ORG MASTER SWITCH. `capture_policies.enabled` defaults to FALSE and an org with no row is
-- disabled: no tenant uploads a single screen session until an admin turns capture on. This is
-- also the gate the privacy plan asks for (no external tenant before per-tenant store
-- encryption) — the switch simply stays off for them. A seat's own `enabled` is also FALSE until
-- that person opts in.
--
-- EVERY APP IS READ (owner decision D2, revised 2026-09-13; plan §3.7). Once both switches are
-- on, the generic reader covers any app or site that is not on the sensitive list, so
-- `generic_web_allowed` / `generic_web` default to TRUE (still switchable off). `allowed_apps` is
-- no longer an allowlist of what may be read: it names which DEDICATED readers are enabled
-- (gmail, whatsapp, linkedin, slack, outlook, gcal — all six by default).
--
-- TWO HALVES, ONE EFFECTIVE POLICY. The org row says what is ALLOWED; the seat row says what this
-- person OPTED INTO and what they additionally block. A seat can only narrow the org, never
-- widen it. The sensitive-domain list (banking, password managers, SSO, HR/health, GeniOS
-- itself) is not stored here at all: it lives in code (`platform/capture_policy.py`) and is
-- merged into every effective policy, so no row can remove it.

create table if not exists capture_policies (
    org_id               text primary key references orgs (id) on delete cascade,
    enabled              boolean not null default false,
    -- which dedicated readers are enabled; everything else goes through the generic reader
    allowed_apps         jsonb not null
                         default '["gmail", "whatsapp", "linkedin", "slack", "outlook", "gcal"]'::jsonb,
    -- ADDITIONAL blocked host patterns; the sensitive defaults are merged in code
    blocked_domains      jsonb not null default '[]'::jsonb,
    generic_web_allowed  boolean not null default true,
    draft_assist_allowed boolean not null default false,
    retention_days       integer not null default 90,
    updated_by           text,
    updated_at           timestamptz not null default now()
);
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'capture_policies_retention_check') then
        alter table capture_policies add constraint capture_policies_retention_check
            check (retention_days between 1 and 3650);
    end if;
end $$;

create table if not exists seat_capture_settings (
    org_id          text not null references orgs (id) on delete cascade,
    seat_id         text not null,
    enabled         boolean not null default false,
    draft_assist    boolean not null default false,
    generic_web     boolean not null default true,
    paused_until    timestamptz,
    blocked_apps    jsonb not null default '[]'::jsonb,
    blocked_domains jsonb not null default '[]'::jsonb,
    updated_at      timestamptz not null default now(),
    primary key (org_id, seat_id)
);
