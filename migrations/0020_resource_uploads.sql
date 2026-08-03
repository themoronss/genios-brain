-- Resource uploads (dashboard → Resources → Uploads). A file the user uploads as a data source:
-- stored to disk, parsed to text, chunked, and fed through the SAME L2 extraction path as a
-- connector sync (each chunk becomes a source_events row with source='upload', then process_pending
-- extracts entities+facts into graph_nodes/graph_facts). This table is the per-file record the UI
-- lists + polls for status/counts. The extracted graph data links back via source_item_prefix.
create table if not exists resource_uploads (
    file_id            text primary key,
    org_id             text not null,
    file_name          text not null,
    file_type          text,
    file_size_bytes    bigint not null default 0,
    storage_path       text,
    tag                text,
    status             text not null default 'queued',   -- queued | extracting | indexed | failed
    source_item_prefix text,                              -- 'upload:<file_id>' — dedup_key prefix of its events
    chunks             int  not null default 0,
    facts_count        int  not null default 0,
    entities_count     int  not null default 0,
    error              text,
    uploaded_by        text,
    uploaded_at        timestamptz not null default now(),
    processed_at       timestamptz
);
create index if not exists resource_uploads_by_org on resource_uploads (org_id, uploaded_at desc);
