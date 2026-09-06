-- L1.2.4-U1 · the first-connect backfill window becomes a per-connection setting.
--
-- The window was a module constant (`newer_than:60d` for Gmail, 60 days for Calendar), so every
-- tenant got the same two months of history and no operator could change it without a deploy.
-- It now lives in `connections.capture_scope` under the key `backfill_days`
-- (genios_engine/capture/connectors/backfill.py), which needs no new column: capture_scope is
-- already the per-connection settings document.
--
-- WHAT THIS MIGRATION DOES, AND DELIBERATELY DOES NOT DO. New connections default to 540 days,
-- in code. Rows that ALREADY EXIST are stamped with the 60 they have always had. Widening a live
-- tenant's history is a deliberate operator action — it re-reads months of mail and spends real
-- extraction budget — and must never happen as a side effect of deploying a file. An admin
-- raises it per connection (capture/connectors/backfill.py::with_backfill_days).
update connections
   set capture_scope = coalesce(capture_scope, '{}'::jsonb) || '{"backfill_days": 60}'::jsonb
 where not (coalesce(capture_scope, '{}'::jsonb) ? 'backfill_days');
