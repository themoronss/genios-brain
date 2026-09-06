-- L1.1-U2 · REGISTRY HONESTY — the other half: what happens after "coming soon".
--
-- THE DEFECT THIS CLOSES. `BUILDABLE_SOURCES` decides, in both connect endpoints
-- (api/routes.py connect/initiate and auth/{tool}/connect), whether a tenant may connect a
-- source at all — and nothing ever exposed it, so the dashboard kept its own hardcoded list of
-- clickable tiles. Four of the nine it listed (slack, jira, gsheets, gdocs) are hard-refused by
-- the endpoint the tile calls: a founder clicks a tile the UI promised would work and gets a
-- 400. `GET /sources/catalog` now serves the derived truth; this table is where the click that
-- can no longer connect anything is KEPT instead of discarded.
--
-- WHY A TABLE RATHER THAN A LOG LINE. "Which system does this tenant's work actually live in"
-- is the highest-signal answer Layer 1 can collect and the one we have never had: it decides
-- what gets built next, and it is the list of people to tell when it ships. A log line answers
-- neither question.
--
-- WHAT IS DELIBERATELY NOT A COLUMN: family, capability, and whether the source is built yet.
-- All three are read back from `capture/source_registry.py` at query time. Storing them would
-- recreate the fifth hand-maintained list that module exists to have deleted, and it would go
-- stale in the way that matters most — the day Slack ships, every stored row would still say
-- "not built", and the report that should say "these 12 tenants can be told it is ready" would
-- say nothing.
--
-- UNREGISTERED IDS ARE ALLOWED. `source` is not FK'd to anything and is not restricted to the
-- registry: a tenant asking for `clickup` is asking for a system we have not even described,
-- which is the one form of demand no internal list can produce. It is bounded instead — a
-- slug, at most 64 characters, enforced both in `capture/source_waitlist.normalize_source` and
-- by the check below, so the column cannot decay into free text.
--
-- ONE ROW PER (org, source). Re-asking increments `requests` in SQL rather than inserting
-- again, so two seats asking at the same moment cannot both read 1 and write 2, and the count
-- is a real strength-of-demand number rather than a duplicate.
--
-- Tenant erasure: added to `_ORG_SCOPED_TABLES` in `genios_engine/api/account_routes.py` (that
-- loop runs with no try/except by design, so a table missing from it leaks rows past an account
-- deletion); the org FK below is the second lock on the same door.

create table if not exists source_waitlist (
    org_id              text        not null references orgs(id) on delete cascade,
    source              text        not null check (source ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
    requests            int         not null default 1 check (requests > 0),
    first_requested_at  timestamptz not null default now(),
    last_requested_at   timestamptz not null default now(),
    latest_note         text        check (latest_note is null or length(latest_note) <= 500),
    latest_requested_by text,
    primary key (org_id, source)
);

-- The product question: across every tenant, what is asked for most and who asked recently.
-- Cross-org by design — the per-tenant read is already served by the primary key.
create index if not exists source_waitlist_demand
    on source_waitlist (source, last_requested_at desc);

comment on table source_waitlist is
  'L1.1-U2: sources a tenant wants but cannot connect. One row per (org, source), re-asking increments requests. family/capability/built-yet are NEVER stored — they are derived from capture/source_registry.py at read time.';
comment on column source_waitlist.source is
  'Canonical registry id where one exists (aliases collapse first), otherwise the tenant''s own slug for a system GeniOS has not described — that second case is the demand signal no internal list can produce.';
