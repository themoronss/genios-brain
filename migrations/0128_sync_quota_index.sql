-- The ingestion meter counts source_events per org per billing period. Without this index that
-- count is a sequential scan of the largest table in the database, run on every sync page.
create index if not exists source_events_org_captured
    on source_events (org_id, captured_at desc);
