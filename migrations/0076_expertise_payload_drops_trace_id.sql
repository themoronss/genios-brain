-- The payload projection check must stop asserting a field the payload no longer carries.
--
-- `expertise_packages.payload` is the canonical form of `ExpertisePackage.to_semantic_dict()`,
-- and `trace_id` was removed from that method because it is observation metadata, not content:
-- `domain_shadow` mints a fresh `new_id("trace")` per situation per sweep, so hashing it made
-- every compile content-address to a new id, the publisher's `on conflict do nothing` never
-- fired, and unchanged knowledge was rewritten at ~238 kB a situation until this table reached
-- 995 MB — 67% of the database — and the project crossed its disk quota into read-only.
--
-- Left alone, `payload->>'trace_id' = trace_id` does not fail: `payload->>'trace_id'` is NULL,
-- NULL = <text> is NULL, and a CHECK passes on NULL. So the constraint would keep its name and
-- quietly stop checking anything — worse than dropping the clause, because the next person to
-- read it would believe the projection is still verified end to end. The remaining columns are
-- still projected, and `trace_id` remains a NOT NULL column: it is stored and still ties a
-- package to the sweep that observed it. It just is not in the payload, so it is not asserted
-- against the payload.
alter table expertise_packages drop constraint if exists expertise_payload_projection;

-- EXISTING ROWS CARRY THE OLD SHAPE, and the constraint is added against them, not only against
-- future writes. Adding it without this line fails the whole migration on any database that has
-- ever run the old publisher:
--
--   CheckViolation: check constraint "expertise_payload_projection" of relation
--   "expertise_packages" is violated by some row
--
-- which is exactly how the first deploy of this migration died at boot — `apply_migrations` runs
-- before the app serves, so the pod never came up. On production the offending rows were written
-- in the minutes AFTER the table was truncated, by the still-running old code, so "we cleared the
-- table" is not protection: the old writer refills it until the new code is live.
--
-- Stripping the key is lossless. `trace_id` remains a NOT NULL COLUMN and still ties a package to
-- the sweep that observed it; it simply stops being part of the payload, which is the whole point
-- of the change. Deleting the rows would also work — they are regenerated on the next sweep — but
-- an UPDATE keeps the content-address stable for packages whose knowledge has not changed, so the
-- publisher's `on conflict do nothing` keeps firing instead of rewriting every situation once.
update expertise_packages
   set payload = payload - 'trace_id'
 where payload ? 'trace_id';

alter table expertise_packages add constraint expertise_payload_projection check (
    payload->>'org_id' = org_id
    and payload->>'id' = expertise_id
    and payload->>'schema_version' = schema_version
    and payload->>'situation_id' = situation_id
    and payload->>'brain_snapshot_id' = brain_snapshot_id
    and payload->'visibility' = visibility
    and payload->'trace_id' is null);
