-- source_events is the lightweight dedup + decision ledger (metadata only, no content).
-- `outcome` records the gate decision so the ledger is honest about what was kept vs
-- dropped. Full content lives in raw_payloads (short TTL) for KEPT events only.
alter table source_events add column if not exists outcome text;
create index if not exists source_events_outcome on source_events (org_id, outcome);
