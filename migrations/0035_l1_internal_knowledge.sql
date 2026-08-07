-- L1 · Internal Knowledge — company canon as a first-class provenance.
--
-- `internal_kind` records that an event is the org DELIBERATELY asserting something
-- about itself (policy / sop / pricing / …, see capture.internal_knowledge). It is the
-- carrier of AUTHORITY across the L1→L2 seam: L2 writes canon facts at rank 4, above a
-- system of record, instead of the flat rank 2 every unstructured event used to get.
--
-- Additive and nullable: every existing row stays exactly what it was (observed
-- traffic, internal_kind null), and SourceEvent goes to schema_version 3.

alter table source_events
  add column if not exists internal_kind text;

-- L2's drain reads canon by kind when rebuilding the organisation's own picture of
-- itself; partial so the index only covers the rows that have one.
create index if not exists idx_source_events_internal_kind
  on source_events (org_id, internal_kind)
  where internal_kind is not null;

comment on column source_events.internal_kind is
  'Company canon: one of capture.internal_knowledge.INTERNAL_KINDS when the org asserted this about itself (authority rank 4), else null for observed traffic (rank 2).';
