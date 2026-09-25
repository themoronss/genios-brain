-- 0182 · `teams` reaches the column default, which is where the policy actually comes from.
--
-- WHAT WAS WRONG. P15 added Teams as a work surface and put it in `platform/capture_policy.APP_IDS`
-- — seven ids — while `capture_policies.allowed_apps` kept 0141's SIX-id column default. The two
-- are not decorative duplicates of each other: `effective_policy` computes
--
--     set(org.allowed_apps) & set(APP_IDS) - set(seat.blocked_apps)
--
-- and `org.allowed_apps` is READ FROM THE ROW. So on every tenant whose policy row took the column
-- default, `teams` was intersected away and the dedicated Teams reader never ran — while
-- `GET /v1/capture/policy`, which answers from the in-code default when no row exists yet, reported
-- Teams as allowed. A switch that reads as on and captures nothing is the same failure
-- `l3_activation` shipped with, in a different table.
--
-- Found by `tests/test_device_api_pg.py` on a real Postgres: the in-memory lane never creates the
-- row, so the six-against-seven disagreement is invisible to the hermetic suite by construction.
--
-- WHY THE BACKFILL IS NARROW, and this is the whole design of this file. An operator who has
-- edited a tenant's `allowed_apps` has made a policy decision about what may be read from their
-- staff's screens, and widening it from a migration would be this system granting itself a
-- capture permission nobody asked it for. So the UPDATE matches ONLY rows that still hold 0141's
-- exact six-id default — untouched rows, where the value is not a decision but an artefact of the
-- day the row was created. Any row that differs in any way is left exactly as it is, and an
-- operator who wants Teams there switches it on in the console.
--
-- Idempotent: re-running matches nothing the first run did not already move.

alter table capture_policies
  alter column allowed_apps
  set default '["gmail", "whatsapp", "linkedin", "slack", "outlook", "gcal", "teams"]'::jsonb;

update capture_policies
   set allowed_apps = '["gmail", "whatsapp", "linkedin", "slack", "outlook", "gcal", "teams"]'::jsonb
 where allowed_apps = '["gmail", "whatsapp", "linkedin", "slack", "outlook", "gcal"]'::jsonb;

comment on column capture_policies.allowed_apps is
  'Which DEDICATED readers are enabled for this org. Keep the default in step with '
  'platform/capture_policy.APP_IDS — effective_policy intersects the two, so an id missing here '
  'is a reader that silently never runs.';
