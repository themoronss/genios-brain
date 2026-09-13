-- 0155 · MEETING TRANSCRIPTS (SCREEN_INTEL_P5 §3, §4).
--
-- One row per transcript a seat handed us (upload) or its Drive produced (a Meet transcript Doc).
-- The row is the frozen transcript object of §3 minus the text: the text itself travels as
-- `meeting_transcript` source events (encrypted raw payloads), and `enc_text` keeps the normalised
-- transcript ENCRYPTED so a speaker re-map can re-ingest without the original file.
--
-- `(org_id, source, source_ref)` is the idempotency key: an upload's ref is its content hash +
-- scope + seat, a Drive transcript's ref is the Drive file id.
create table if not exists transcripts (
    transcript_id     text primary key,
    org_id            text not null references orgs (id) on delete cascade,
    source            text not null,                         -- upload | gdrive
    source_ref        text not null,
    file_id           text,                                  -- resource_uploads.file_id (uploads)
    seat_id           text,                                  -- the uploading seat, when known
    uploader_email    text,
    provider          text not null default 'other'
                      check (provider in ('gmeet', 'granola', 'fireflies', 'otter', 'zoom',
                                          'teams', 'other')),
    scope             text not null default 'attendees'
                      check (scope in ('attendees', 'personal')),
    calendar_event_id text,
    meeting_node_id   text,
    title             text,
    started_at        timestamptz,
    ended_at          timestamptz,
    meeting           jsonb not null default '{}'::jsonb,    -- the §3 `meeting` object, verbatim
    speakers          jsonb not null default '[]'::jsonb,    -- §3 `speakers`
    attendees         jsonb not null default '[]'::jsonb,    -- §3 `attendees` (mapping dropdown)
    principals        text[] not null default '{}',          -- who may read it (lowercased emails)
    parts             integer not null default 0,
    event_ids         text[] not null default '{}',          -- the current version's part events
    content_hash      text not null,
    content_version   text,                                  -- hash + speaker-map hash
    enc_text          bytea,
    status            text not null default 'queued'
                      check (status in ('queued', 'extracting', 'extracted', 'failed')),
    error             text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),
    unique (org_id, source, source_ref)
);
create index if not exists transcripts_by_org on transcripts (org_id, created_at desc);
create index if not exists transcripts_by_meeting on transcripts (org_id, meeting_node_id)
    where meeting_node_id is not null;
create index if not exists transcripts_by_principal on transcripts using gin (principals);

-- Org opt-in for transcripts the CONNECTORS find (Drive Meet transcript Docs). Off by default: a
-- seat's upload is deliberate and needs no switch, a Drive sweep reading every meeting is not.
alter table capture_policies add column if not exists transcripts boolean not null default false;
