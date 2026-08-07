-- L1 · Source ACLs and the signal lifecycle.
--
-- Two things the architecture required of Layer 1 that the ledger had no room for.
--
-- 1. `visibility` — who could see the ORIGINAL. The spec's Permission Manager: "carries
--    source-level ACLs forward so a signal can never surface to someone who could not see
--    the original." Nothing recorded it, so a fact extracted from a two-person email
--    thread was indistinguishable from one extracted from a company-wide page, and every
--    layer above was free to deliver either to anyone in the tenant. L1 is the LAST place
--    that still knows: by L2 the email is a fact and the recipient list is gone.
--
-- 2. `expires_at` / `signal_state` — the spec's Signal Lifecycle Manager. Every signal
--    ever captured stayed equally current forever: a meeting that finished in March
--    reached the reasoning engine as live evidence beside this morning's email.
--
-- Additive and nullable. Existing rows keep their meaning: no recorded ACL backfills to
-- the org-wide default (which is the tenant boundary the row already sits inside), and a
-- null `expires_at` means "never computed", which `is_expired` reads as "does not expire"
-- — the safe direction, since the alternative would retroactively expire all of history.
-- SourceEvent goes to schema_version 4, GatedEvent to 3.

-- One `alter table` per column, deliberately: platform/schema.py parses these files as
-- the schema, and its add-column regex reads a single column per statement. A combined
-- `add column a, add column b` would create both in Postgres while the ratchet in
-- tests/test_schema_conformance.py saw only the first — schema drift the build cannot see.
alter table source_events add column if not exists visibility jsonb;
alter table source_events add column if not exists expires_at timestamptz;
alter table source_events add column if not exists signal_state text not null default 'new';

-- The sweep reads exactly this predicate (see PostgresSourceEventRepository.expire_due):
-- due, and not already settled. Partial so it only indexes rows that can ever expire.
create index if not exists idx_source_events_expiry
  on source_events (expires_at)
  where expires_at is not null and signal_state in ('new', 'active');

-- L5/L6 ask "may this person see anything derived from this evidence?" per delivery.
create index if not exists idx_source_events_visibility_scope
  on source_events ((visibility ->> 'scope'))
  where visibility is not null;

comment on column source_events.visibility is
  'Source ACL carried forward (contracts/visibility.py): {scope: public|org|participants|private, principals: [email], derived_from}. The audience of a derived insight may narrow this, never widen it.';
comment on column source_events.expires_at is
  'When this signal stops being current evidence. NULL = never (company canon) or pre-migration. Decay horizon for the SIGNAL — storage TTLs live on raw_payloads (30d) and prepared_content (180d).';
comment on column source_events.signal_state is
  'new | active | satisfied | expired | superseded. L1 writes new (at emit) and expired (the sweep); active/satisfied are L2+''s to write.';
