-- GeniOS Engine · L2 processing-run ledger. The DONE-marker + attempt tracker keyed by EVENT_ID
-- (independent of the content-hash extraction cache). Fixes two P0s:
--   • runaway re-charge: a failed/parked event with no ledger row was re-pulled every batch and
--     re-sent to the LLM. Now every terminal outcome writes a row → _pull excludes it.
--   • lost work on a blip: transient failures retry up to a cap, then park 'model_unavailable'
--     (visible, never a silent black hole).
create table if not exists l2_processing_runs (
    org_id     text not null,
    event_id   text not null,
    status     text not null default 'failed',   -- done | parked | failed(transient, still retryable)
    attempts   int  not null default 0,
    last_error text,
    updated_at timestamptz not null default now(),
    primary key (org_id, event_id)
);
create index if not exists l2_runs_terminal on l2_processing_runs (org_id, status);
