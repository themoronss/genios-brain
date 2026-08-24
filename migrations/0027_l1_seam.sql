-- GeniOS Engine · L1 seam persistence. Before this, L1 computed PreparedContent
-- (PII-masked text + offset map), a gate route, a triage lane and domain/linkage hints —
-- then threw them ALL away, because the real L1→L2 handoff was a SQL query over
-- source_events joined to raw_payloads, and L2 re-derived clean text itself. That
-- inverted "heavy at ingestion, light at runtime" and made [start,end] evidence offsets
-- impossible. These columns + prepared_content ARE the seam, persisted.
-- All statements idempotent (the migration ledger applies this once anyway).

-- decision columns on the ledger (envelope v2 + gate/triage outputs)
alter table source_events add column if not exists source_family text;
alter table source_events add column if not exists route text;           -- gate route (structured | needs_extraction)
alter table source_events add column if not exists triage_lane text;     -- P0..P3 processing lane
alter table source_events add column if not exists domain_hints jsonb;   -- deterministic pre-classify hints
alter table source_events add column if not exists linkage_hints jsonb;  -- S3 entity hints (company domain, thread)

-- backfill family for existing rows (same mapping as capture/source_families.py)
update source_events set source_family = case
    when source in ('gmail','outlook','imap','inkbox','slack','teams','whatsapp','sms',
                    'gcal','calendar','google_calendar') then 'communication'
    when source in ('notion','gdrive','drive','google_drive','confluence','upload') then 'knowledge'
    when source in ('hubspot','salesforce','pipedrive','database','postgres','mysql') then 'enterprise_system'
    when source = 'human' then 'human_input'
    when source = 'agent' then 'ai_generated'
    when source = 'genios' then 'intelligence'
    else 'unclassified' end
where source_family is null;

-- PreparedContent, persisted: PII-masked clean text + the offset map back to source
-- characters. KEPT (emitted/parked) unstructured events only. Retained LONGER than the
-- encrypted raw payload (it is the masked, replayable form) — this is what lets an
-- improved extractor re-run over history without re-fetching or re-paying.
create table if not exists prepared_content (
    event_id              text primary key,
    org_id                text not null,
    prepared_content_id   text not null,
    clean_text            text not null,
    language              text,
    masked_spans          jsonb,
    protected_spans       jsonb,
    offset_map            jsonb,
    signature_hints       jsonb,
    preprocessor_version  text,
    created_at            timestamptz not null default now(),
    expires_at            timestamptz                          -- retention clock (180d default)
);
create index if not exists prepared_content_by_org on prepared_content (org_id, created_at);
create index if not exists prepared_content_expiry on prepared_content (expires_at);

-- per-run ingestion ledger: what each sync scanned/kept/filtered, per connection.
-- (run_sync computed this and threw it into a log line.)
create table if not exists l1_sync_runs (
    run_id        text primary key,
    org_id        text not null,
    connection_id text,
    source        text,
    mode          text,
    scanned       int not null default 0,
    emitted       int not null default 0,
    dropped       int not null default 0,
    parked        int not null default 0,
    duplicate     int not null default 0,
    quarantined   int not null default 0,
    error         text,
    started_at    timestamptz,
    finished_at   timestamptz not null default now()
);
create index if not exists l1_sync_runs_by_org on l1_sync_runs (org_id, finished_at desc);
